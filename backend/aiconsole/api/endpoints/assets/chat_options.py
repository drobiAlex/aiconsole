from typing import Optional

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from aiconsole.core.chat.load_chat_history import load_chat_history
from aiconsole.core.project.project import get_project_assets

router = APIRouter()


class PatchChatOptions(BaseModel):
    agent_id: Optional[str] = None
    materials_ids: Optional[list[str]] = None
    ai_can_add_extra_materials: Optional[bool] = None
    draft_command: Optional[str] = None


@router.patch("/{chat_id}/chat_options")
async def chat_options(chat_id: str, chat_options: PatchChatOptions):
    chat = await load_chat_history(id=chat_id)

    if chat_options.agent_id is not None:
        chat.chat_options.agent_id = chat_options.agent_id

    if chat_options.materials_ids is not None:
        chat.chat_options.materials_ids = chat_options.materials_ids

    if chat_options.ai_can_add_extra_materials is not None:
        chat.chat_options.ai_can_add_extra_materials = chat_options.ai_can_add_extra_materials

    if chat_options.draft_command is not None:
        chat.chat_options.draft_command = chat_options.draft_command

    await get_project_assets().update_asset(chat.id, chat, scope="chat_options")
    return Response(status_code=status.HTTP_200_OK)
