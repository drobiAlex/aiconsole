# The AIConsole Project
#
# Copyright 2023 10Clouds
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import logging
import os

import aiofiles
import aiofiles.os
import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydub import AudioSegment  # type: ignore

from aiconsole.consts import DIR_WITH_AICONSOLE_PACKAGE
from aiconsole.core.settings.settings import settings

_log = logging.getLogger(__name__)

router = APIRouter()


async def run_in_threadpool(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)


def convert_audio_to_mp3_sync(source_path: str, target_path: str):
    old_path = os.environ["PATH"]

    # HACK: SAFARI WORKAROUND FOR OPENAI NOT SUPPORTING MP4
    # This will not work for electron setup, but electron uses Chrome, so it should not be a problem
    # It requires ffmpeg to be downloaded to the project root ffmpeg directory
    os.environ["PATH"] += os.pathsep + os.path.join(DIR_WITH_AICONSOLE_PACKAGE.parent, "ffmpeg")

    AudioSegment.from_file(source_path).export(target_path, format="mp3")

    os.environ["PATH"] = old_path


async def convert_audio_to_mp3(source_path: str, target_path: str):
    await run_in_threadpool(convert_audio_to_mp3_sync, source_path, target_path)


@router.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    # Initialize the OpenAI client
    openai_key = settings().unified_settings.openai_api_key

    _log.info(audio.headers)

    mp3_temp_file_path = None

    try:
        # This does not have to be a WAV file, but it has to have the correct extension
        file_suffix = ".wav"

        async with aiofiles.tempfile.NamedTemporaryFile(delete=True, suffix=file_suffix) as temp_file:
            content = await audio.read()
            await temp_file.write(content)
            await temp_file.flush()
            temp_file_path = str(temp_file.name)

            # HACK: SAFARI WORKAROUND FOR OPENAI NOT SUPPORTING MP4
            # Convert Safari format to mp3 which is correctly supported by OpenAI (mp4 does not work, despite the docs)
            if audio.headers["content-type"] == "audio/mp4":
                mp3_temp_file_path = temp_file_path.replace(file_suffix, ".mp3")
                await convert_audio_to_mp3(temp_file_path, mp3_temp_file_path)
                temp_file_path = mp3_temp_file_path

            async with aiofiles.open(temp_file_path, "rb") as tmp_file:
                file_content = await tmp_file.read()

                # We can not use the official OpenAI Python client, because it does not support async
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {openai_key}"},
                        files={"file": (str(temp_file.name), file_content)},
                        data={"model": "whisper-1"},
                    )
                    transcription = response.json()

                if transcription.get("error"):
                    raise HTTPException(status_code=500, detail=transcription["error"])

                return {"transcription": transcription["text"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Ensure the MP3 temporary file is deleted
        if mp3_temp_file_path:
            await aiofiles.os.remove(mp3_temp_file_path)
