import json
import logging
import os
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import aiofiles
import aiofiles.os as async_os
import rtoml
from send2trash import send2trash

from aiconsole.core.assets.agents.agent import AICAgent
from aiconsole.core.assets.assets_service import AssetsUpdatedEvent
from aiconsole.core.assets.fs.exceptions import UserIsAnInvalidAgentIdError
from aiconsole.core.assets.fs.load_asset_from_fs import load_asset_from_fs
from aiconsole.core.assets.materials.material import AICMaterial, MaterialContentType
from aiconsole.core.assets.types import Asset, AssetLocation, AssetType
from aiconsole.core.assets.users.users import AICUserProfile
from aiconsole.core.chat.list_possible_historic_chat_ids import (
    list_possible_historic_chat_ids,
)
from aiconsole.core.chat.load_chat_history import load_chat_history
from aiconsole.core.project.paths import (
    get_core_assets_directory,
    get_project_assets_directory,
)
from aiconsole.utils.events import InternalEvent, internal_events
from aiconsole.utils.file_observer import FileObserver
from aiconsole.utils.list_files_in_file_system import list_files_in_file_system

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AssetLoadErrorEvent(InternalEvent):
    pass


@dataclass(frozen=True, slots=True)
class AssetDoesNotExisitErrorEvent(InternalEvent):
    pass

# TODO: Check if CRUD operations need to modify _assets or are reloaded with each modification
class AssetsFileStorage:
    paths: list[Path]
    _observer: FileObserver | None

    def __init__(
        self,
        paths: list[Path],
        disable_observer: bool = False,
    ):
        self.paths = paths
        self._assets: dict[str, list[Asset]] = defaultdict(list)

        if not disable_observer:
            self._observer = FileObserver()
        else:
            self._observer = None

    # TODO: handle exeption via external event
    async def setup(self) -> tuple[bool, Exception | None]:
        try:
            for asset_type in AssetType:
                # TODO: decouple to paths
                get_project_assets_directory(asset_type).mkdir(parents=True, exist_ok=True)

            await self._load_assets()
            # FIXME: seems like between loading and spawning observer smth can happen
            if self._observer:
                self._observer.start(file_paths=self.paths, on_changed=self._reload)

            return True, None
        except Exception as e:
            _log.exception(f"[{self.__class__.__name__}] Failed to setup: \n{e}")
            return False, e

    async def _reload(self) -> None:
        await self._load_assets()
        await internal_events().emit(AssetsUpdatedEvent())

    def destroy(self) -> None:
        if self._observer:
            self._observer.stop()
            del self._observer

    @property
    def assets(self) -> dict[str, list[Asset]]:
        return self._assets

    # TODO: verify if assets with core location rise error
    async def update_asset(self, original_asset_id: str, updated_asset: Asset, scope: str | None = None) -> None:
        self._validate_asset_id(updated_asset)

        project_assets_directory_path = get_project_assets_directory(updated_asset.type)

        original_asset_file_path = self._get_asset_file_path(
            original_asset_id, updated_asset.type, project_assets_directory_path
        )
        updated_asset_file_path = self._get_asset_file_path(
            updated_asset.id, updated_asset.type, project_assets_directory_path
        )

        # TODO: is this still needed?
        # if asset.type == AssetType.CHAT and await need_to_delete_chat_asset(asset, file_path):
        #     await async_os.remove(file_path)
        #     return

        # Imagene you just wanted to rename the chat and it goes to the top of assets (unwanted behaviour)
        original_st_mtime = await self.get_original_mtime_if_exists(original_asset_file_path)
        update_last_modified = True

        if updated_asset.type == AssetType.CHAT:
            update_last_modified = True
            new_content = updated_asset.model_dump(exclude={"id", "last_modified"})

            if original_asset_file_path.exists():
                async with aiofiles.open(original_asset_file_path, "r", encoding="utf8", errors="replace") as f:
                    old_content = json.loads(await f.read())
                    if scope == "chat_options" and (
                        "chat_options" not in old_content or old_content["chat_options"] != new_content["chat_options"]
                    ):
                        old_draft_command = old_content.get("chat_options", {}).get("draft_command") or ""
                        new_draft_command = new_content.get("chat_options", {}).get("draft_command") or ""

                        if old_draft_command != new_draft_command and (
                            "@" not in set(old_draft_command) ^ set(new_draft_command)
                        ):
                            update_last_modified = True
                        else:
                            update_last_modified = False
                        old_content["chat_options"] = new_content["chat_options"]
                        new_content = old_content
                    elif scope == "message_groups" and old_content["message_groups"] != new_content["message_groups"]:
                        old_content["message_groups"] = new_content["message_groups"]
                        new_content = old_content
                    elif scope == "name" and ("name" not in old_content or old_content["name"] != new_content["name"]):
                        old_content["name"] = new_content["name"]
                        old_content["title_edited"] = True
                        new_content = old_content
                        update_last_modified = False

            async with aiofiles.open(updated_asset_file_path, "w", encoding="utf8", errors="replace") as f:
                await f.write(json.dumps(new_content))
        else:
            try:
                original_asset = await load_asset_from_fs(updated_asset.type, original_asset_id)
                current_version = original_asset.version
            except KeyError:
                original_asset = None
                current_version = "0.0.1"

            update_last_modified = not self.only_name_changed(original_asset, updated_asset)

            current_version_parts = current_version.split(".")
            current_version_parts[-1] = str(int(current_version_parts[-1]) + 1)
            updated_asset.version = ".".join(current_version_parts)

            toml_data = {
                "name": updated_asset.name,
                "version": updated_asset.version,
                "usage": updated_asset.usage,
                "usage_examples": updated_asset.usage_examples,
                "enabled_by_default": updated_asset.enabled_by_default,
            }

            if isinstance(updated_asset, AICMaterial):
                material: AICMaterial = updated_asset
                toml_data["content_type"] = updated_asset.content_type.value
                content_key = {
                    MaterialContentType.STATIC_TEXT: "content_static_text",
                    MaterialContentType.DYNAMIC_TEXT: "content_dynamic_text",
                    MaterialContentType.API: "content_api",
                }[updated_asset.content_type]
                toml_data[content_key] = self._make_sure_starts_and_ends_with_newline(material.content)

            if isinstance(updated_asset, AICAgent):
                toml_data.update(
                    {
                        "system": updated_asset.system,
                        "gpt_mode": str(updated_asset.gpt_mode),
                        "execution_mode": updated_asset.execution_mode,
                        "execution_mode_params_values": updated_asset.execution_mode_params_values,
                    }
                )

            if isinstance(updated_asset, AICUserProfile):
                toml_data.update(
                    {
                        "display_name": updated_asset.display_name,
                        "profile_picture": updated_asset.profile_picture,
                    }
                )

            if original_asset and original_asset_file_path != updated_asset_file_path:
                original_asset_file_path.rename(updated_asset_file_path)

            rtoml.dump(toml_data, updated_asset_file_path)

            extensions = [".jpeg", ".jpg", ".png", ".gif", ".SVG"]
            for extension in extensions:
                old_file_path = project_assets_directory_path / f"{original_asset_id}{extension}"
                new_file_path = project_assets_directory_path / f"{updated_asset.id}{extension}"
                if old_file_path.exists() and old_file_path != new_file_path:
                    if new_file_path.exists():
                        raise Exception("Both filepaths exist, when only one must be present")
                    old_file_path.rename(new_file_path)
                    continue

                core_file_path = get_core_assets_directory(updated_asset.type) / f"{original_asset_id}{extension}"
                if not new_file_path.exists() and core_file_path.exists():
                    shutil.copy(core_file_path, new_file_path)

        if original_st_mtime and not update_last_modified:
            os.utime(updated_asset_file_path, (original_st_mtime, original_st_mtime))

    # TODO: verify that assets with id that already exists rise error
    async def create_asset(self, asset: Asset) -> None:
        self._validate_asset_id(asset)

        project_assets_directory_path = get_project_assets_directory(asset.type)
        file_path = self._get_asset_file_path(asset.id, asset.type, project_assets_directory_path)

        if asset.type == AssetType.CHAT:
            async with aiofiles.open(file_path, "w", encoding="utf8", errors="replace") as f:
                await f.write(json.dumps(asset.model_dump(exclude={"id", "last_modified"})))

        else:
            toml_data = {
                "name": asset.name,
                "version": asset.version,
                "usage": asset.usage,
                "usage_examples": asset.usage_examples,
                "enabled_by_default": asset.enabled_by_default,
            }

            if isinstance(asset, AICMaterial):
                if asset.content_type in (
                    MaterialContentType.DYNAMIC_TEXT,
                    MaterialContentType.API,
                ) and not asset.content.startswith("file://"):
                    file_path = await AICMaterial.save_content_to_file(asset.id, asset.content)
                    asset.content = f"file://{file_path}"

                toml_data["content_type"] = asset.content_type.value
                content_key = {
                    MaterialContentType.STATIC_TEXT: "content_static_text",
                    MaterialContentType.DYNAMIC_TEXT: "content_dynamic_text",
                    MaterialContentType.API: "content_api",
                }[asset.content_type]
                toml_data[content_key] = self._make_sure_starts_and_ends_with_newline(asset.content)

            if isinstance(asset, AICAgent):
                toml_data.update(
                    {
                        "system": asset.system,
                        "gpt_mode": str(asset.gpt_mode),
                        "execution_mode": asset.execution_mode,
                        "execution_mode_params_values": asset.execution_mode_params_values,
                    }
                )

            if isinstance(asset, AICUserProfile):
                toml_data.update(
                    {
                        "display_name": asset.display_name,
                        "profile_picture": asset.profile_picture,
                    }
                )

            async with aiofiles.open(file_path, "w", encoding="utf8", errors="replace") as f:
                await f.write(rtoml.dumps(toml_data, pretty=True))

    # TODO: rework for proper async
    async def delete_asset(self, asset_id: str) -> None:
        """
        Delete a specific asset.
        """
        # TODO: does including this makes sence?
        try:
            asset = self._assets[asset_id].pop(0)

            if len(self._assets[asset_id]) == 0:
                del self._assets[asset_id]
        except IndexError as e:
            _log.exception(e)
            await internal_events().emit(
                AssetDoesNotExisitErrorEvent(), details="Failed to delete asset, because it doesn't exist!"
            )
            return

        match asset.type:
            case AssetType.AGENT:
                extensions = [".toml", ".jpeg", ".jpg", ".png", ".gif", ".SVG"]
            case AssetType.CHAT:
                extensions = [".json"]
            case AssetType.MATERIAL:
                extensions = [".toml"]
            case _:
                _log.exception("Unmached AssetType")
                extensions = []

        for extension in extensions:
            asset_file_path = get_project_assets_directory(asset.type) / f"{asset_id}{extension}"
            if asset_file_path.exists():
                send2trash(asset_file_path)

    async def _load_assets(self) -> None:
        self._assets.clear()

        for asset_type in AssetType:
            if asset_type == AssetType.CHAT:
                for chat_id in list_possible_historic_chat_ids():
                    try:
                        chat = await load_chat_history(chat_id)

                        if chat:
                            self._assets[chat_id].append(chat)

                    except Exception as e:
                        _log.exception(e)
                        await internal_events().emit(
                            AssetLoadErrorEvent(), details=f"Failed to get history: {e} {chat_id}"
                        )
            else:
                locations = [
                    [AssetLocation.PROJECT_DIR, get_project_assets_directory(asset_type)],
                    [AssetLocation.AICONSOLE_CORE, get_core_assets_directory(asset_type)],
                ]

                for [location, dir] in locations:
                    ids = set(
                        [
                            os.path.splitext(os.path.basename(path))[0]
                            for path in list_files_in_file_system(dir)
                            if os.path.splitext(Path(path))[-1] == ".toml"
                        ]
                    )

                    for id in ids:
                        try:
                            self._assets[id].append(await load_asset_from_fs(asset_type, id, location))
                        except Exception as e:
                            _log.exception(e)
                            await internal_events().emit(
                                AssetLoadErrorEvent(), details=f"Error loading asset `{id}`, error is `{e}`"
                            )
                            continue

    def _get_asset_file_path(self, asset_id: str, asset_type: AssetType, directory_path: Path) -> Path:
        extension = "json" if asset_type == AssetType.CHAT else "toml"
        return directory_path / f"{asset_id}.{extension}"

    def _make_sure_starts_and_ends_with_newline(self, s: str) -> str:
        if not s.startswith("\n"):
            s = "\n" + s

        if not s.endswith("\n"):
            s = s + "\n"

        return s

    def _validate_asset_id(self, asset: Asset) -> None:
        if isinstance(asset, AICAgent) and asset.id == "user":
            raise UserIsAnInvalidAgentIdError()

        if asset.id == "new":
            raise ValueError("Cannot save asset with id 'new'")

    async def get_original_mtime_if_exists(self, file_path: Path) -> float | None:
        if file_path.exists():
            return (await async_os.stat(file_path)).st_mtime
        return None

    def only_name_changed(self, old_asset: Asset | None, asset: Asset) -> bool:
        if not old_asset:
            return False

        old_asset_dict = old_asset.model_dump()
        asset_dict = asset.model_dump()
        return any(key != "name" and asset_dict.get(key) != old_asset_dict.get(key) for key in asset_dict)
