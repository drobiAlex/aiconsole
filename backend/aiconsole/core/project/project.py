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

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import BackgroundTasks

from aiconsole.api.websockets.connection_manager import (
    AICConnection,
    connection_manager,
)
from aiconsole.api.websockets.server_messages import (
    InitialProjectStatusServerMessage,
    ProjectClosedServerMessage,
    ProjectLoadingServerMessage,
    ProjectOpenedServerMessage,
)
from aiconsole.core.assets.types import AssetLocation
from aiconsole.core.assets.users.users import AICUserProfile
from aiconsole.core.code_running.run_code import reset_code_interpreters
from aiconsole.core.code_running.virtual_env.create_dedicated_venv import (
    create_dedicated_venv,
)
from aiconsole.core.settings.fs.settings_file_storage import SettingsFileStorage
from aiconsole.core.settings.settings import settings

if TYPE_CHECKING:
    from aiconsole.core.assets import assets_service


_assets: "assets_service.Assets | None" = None
_project_initialized = False


async def _clear_project():
    global _assets
    global _project_initialized

    if _assets:
        _assets.clean_up()

    reset_code_interpreters()

    _assets = None
    _project_initialized = False


# TODO: move to API sending a message
async def send_project_init(connection: AICConnection):
    from aiconsole.core.project.paths import get_project_directory, get_project_name

    await connection.send(
        InitialProjectStatusServerMessage(
            project_name=get_project_name() if is_project_initialized() else None,
            project_path=str(get_project_directory()) if is_project_initialized() else None,
        )
    )


def get_project_assets() -> "assets_service.Assets":
    if not _assets:
        raise ValueError("Project materials are not initialized")
    return _assets


def is_project_initialized() -> bool:
    return _project_initialized


async def close_project():
    await _clear_project()

    await connection_manager().send_to_all(ProjectClosedServerMessage())

    settings().configure(SettingsFileStorage, project_path=None)


# TODO: move to API sending a message
async def reinitialize_project():
    from aiconsole.core.assets.assets_service import assets
    from aiconsole.core.assets.fs.assets_file_storage import AssetsFileStorage
    from aiconsole.core.project.paths import get_project_directory, get_project_name
    from aiconsole.core.recent_projects.recent_projects import add_to_recent_projects

    await connection_manager().send_to_all(ProjectLoadingServerMessage())

    global _assets
    global _project_initialized

    await _clear_project()

    _project_initialized = True

    project_dir = get_project_directory()

    await add_to_recent_projects(project_dir)

    _assets = assets()

    # TODO: check if loading assets before settings cause problems
    await _assets.configure(
        AssetsFileStorage(
            paths=[
                project_dir,
            ]
        )
    )
    settings().configure(SettingsFileStorage, project_path=project_dir)

    # Save user info to assets
    user_profile = settings().unified_settings.user_profile
    if user_profile:
        aic_user_profile = _assets.get_asset(user_profile.id)
        if not aic_user_profile:
            await _assets.create_asset(
                AICUserProfile(
                    id=user_profile.id,
                    name=user_profile.display_name or f"User-{user_profile.id}",
                    display_name=user_profile.display_name,
                    profile_picture=user_profile.profile_picture,
                    usage="",
                    usage_examples=[],
                    defined_in=AssetLocation.PROJECT_DIR,
                    override=False,
                    last_modified=datetime.now(),
                )
            )
        else:
            assert user_profile.id
            aic_user_profile.last_modified = datetime.now()
            await _assets.update_asset(user_profile.id, aic_user_profile)

    await connection_manager().send_to_all(
        ProjectOpenedServerMessage(path=str(get_project_directory()), name=get_project_name())
    )


async def choose_project(path: Path, background_tasks: BackgroundTasks):
    if not path.exists():
        raise ValueError(f"Path {path} does not exist")

    # Change cwd and import path
    os.chdir(path)
    sys.path[0] = str(path)

    await reinitialize_project()

    background_tasks.add_task(create_dedicated_venv)
