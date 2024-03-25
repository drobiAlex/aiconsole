import json
import logging
import os
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


class AssetsFileStorage:
    paths: list[Path] | None

    def __init__(
        self,
        disable_observer: bool = False,
    ):
        self.assets: dict[str, list[Asset]] = defaultdict(list)

        if not disable_observer:
            self._observer = FileObserver()
        else:
            self._observer = None

    # TODO: handle exeption via external event
    async def setup(self, paths: list[Path]) -> tuple[bool, Exception | None]:
        try:
            self.paths = paths
            for asset_type in AssetType:
                # TODO: decouple to paths
                get_project_assets_directory(asset_type).mkdir(parents=True, exist_ok=True)

            if self._observer:
                self._observer.start(file_paths=paths, on_changed=self._reload)

            await self._load_assets()

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

    async def update_asset(self, original_asset_id: str, updated_asset: Asset) -> Asset | None:
        self._validate_asset_id(updated_asset)

        project_assets_directory_path = get_project_assets_directory(updated_asset.type)
        file_path = self._get_asset_file_path(updated_asset.id, updated_asset.type, project_assets_directory_path)

        # if asset.type == AssetType.CHAT and await need_to_delete_chat_asset(asset, file_path):
        #     await async_os.remove(file_path)
        #     return

        original_st_mtime = await self.get_original_mtime_if_exists(file_path)
        update_last_modified = True

        if updated_asset.type == AssetType.CHAT:
            await handle_chat_asset(file_path, updated_asset, scope)
        else:
            try:
                old_asset = await load_asset_from_fs(asset.type, asset.id)
                current_version = old_asset.version
            except KeyError:
                old_asset = None
                current_version = "0.0.1"

            update_last_modified = not only_name_changed(old_asset, asset)

            current_version_parts = current_version.split(".")

            # Increment version number
            current_version_parts[-1] = str(int(current_version_parts[-1]) + 1)

            # Join version number
            asset.version = ".".join(current_version_parts)

            toml_data = {
                "name": asset.name,
                "version": asset.version,
                "usage": asset.usage,
                "usage_examples": asset.usage_examples,
                "enabled_by_default": asset.enabled_by_default,
            }

            if isinstance(asset, AICMaterial):
                material: AICMaterial = asset
                toml_data["content_type"] = asset.content_type.value
                content_key = {
                    MaterialContentType.STATIC_TEXT: "content_static_text",
                    MaterialContentType.DYNAMIC_TEXT: "content_dynamic_text",
                    MaterialContentType.API: "content_api",
                }[asset.content_type]
                toml_data[content_key] = make_sure_starts_and_ends_with_newline(material.content)

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

            rtoml.dump(toml_data, file_path)

        if original_st_mtime and not update_last_modified:
            os.utime(file_path, (original_st_mtime, original_st_mtime))

        extensions = [".jpeg", ".jpg", ".png", ".gif", ".SVG"]
        for extension in extensions:
            old_file_path = get_core_assets_directory(asset.type) / f"{old_asset_id}{extension}"
            new_file_path = project_assets_directory_path / f"{asset.id}{extension}"
            if old_file_path.exists():
                shutil.copy(old_file_path, new_file_path)

    async def create_asset(self, asset: Asset) -> Asset | AICUserProfile | AICAgent | AICMaterial:
        self._validate_asset_id(asset)

        project_assets_directory_path = get_project_assets_directory(asset.type)
        file_path = self._get_asset_file_path(asset, project_assets_directory_path)

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

        return asset

    # TODO: change to async
    def delete_asset(self, asset_id: str, asset_type: AssetType) -> None:
        """
        Delete a specific asset.
        """
        match asset_type:
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
            asset_file_path = get_project_assets_directory(asset_type) / f"{asset_id}{extension}"
            if asset_file_path.exists():
                send2trash(asset_file_path)

    async def _load_assets(self) -> None:
        self.assets.clear()

        for asset_type in AssetType:
            if asset_type == AssetType.CHAT:
                for chat_id in list_possible_historic_chat_ids():
                    try:
                        chat = await load_chat_history(chat_id)

                        if chat:
                            self.assets[chat_id].append(chat)

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
                            self.assets[id].append(await load_asset_from_fs(asset_type, id, location))
                        except Exception as e:
                            _log.exception(e)
                            await internal_events().emit(
                                AssetLoadErrorEvent(), details=f"Error loading asset `{id}`, error is `{e}`"
                            )
                            continue

    def _get_asset_file_path(self, asset_id: str, asset_type: AssetType, directory_path: Path) -> Path:
        extension = "json" if asset_type == AssetType.CHAT else "toml"
        return directory_path / f"{asset_id}.{extension}"

    def _make_sure_starts_and_ends_with_newline(self, s: str):
        if not s.startswith("\n"):
            s = "\n" + s

        if not s.endswith("\n"):
            s = s + "\n"

        return s

    def _validate_asset_id(self, asset: Asset):
        if isinstance(asset, AICAgent) and asset.id == "user":
            raise UserIsAnInvalidAgentIdError()

        if asset.id == "new":
            raise ValueError("Cannot save asset with id 'new'")

    async def get_original_mtime_if_exists(self, file_path: Path) -> float | None:
        if file_path.exists():
            return (await async_os.stat(file_path)).st_mtime
        return None
