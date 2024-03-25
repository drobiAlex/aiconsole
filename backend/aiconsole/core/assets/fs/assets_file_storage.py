import json
import logging
import os
from collections import defaultdict
from pathlib import Path

import aiofiles
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
from aiconsole.utils.events import internal_events
from aiconsole.utils.file_observer import FileObserver
from aiconsole.utils.list_files_in_file_system import list_files_in_file_system

_log = logging.getLogger(__name__)


class AssetsFileStorage:
    paths: list[Path] | None

    def __init__(
        self,
        disable_observer: bool = False,
    ):
        if not disable_observer:
            self._observer = FileObserver()
        else:
            self._observer = None

    def setup(self, paths: list[Path]) -> tuple[bool, Exception | None]:
        try:
            self.paths = paths
            for asset_type in AssetType:
                # TODO: decouple to paths
                get_project_assets_directory(asset_type).mkdir(parents=True, exist_ok=True)

            if self._observer:
                self._observer.start(file_paths=paths, on_changed=self._reload)

            return True, None
        except Exception as e:
            _log.exception(f"[{self.__class__.__name__}] Failed to setup: \n{e}")
            return False, e

    async def _reload(self):
        # reload
        await internal_events().emit(AssetsUpdatedEvent())

    def destroy(self):
        if self._observer:
            self._observer.stop()
            del self._observer

    def get_asset(self, asset_id: str) -> Asset | None:  # fmt: off
        ...

    async def get_all_assets(self, asset_type: AssetType) -> dict[str, list[Asset]]:
        assets: dict[str, list[Asset]] = defaultdict(list)

        for asset_type in AssetType:
            if asset_type == AssetType.CHAT:
                for chat_id in list_possible_historic_chat_ids():
                    try:
                        chat = await load_chat_history(chat_id)

                        if chat:
                            assets[chat_id].append(chat)

                    except Exception as e:
                        _log.exception(e)
                        _log.error(f"Failed to get history: {e} {chat_id}")
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
                            assets[id].append(await load_asset_from_fs(asset_type, id, location))
                        except Exception as e:
                            await connection_manager().send_to_all(
                                ErrorServerMessage(
                                    error=f"Invalid {asset_type} {id} {e}",
                                )
                            )
                            continue

        return assets

    async def update_asset(
        self,
        asset_id: str,
    ) -> Asset | None:
        pass

    async def create_asset(self, asset: Asset):
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

    def _get_asset_file_path(self, asset: Asset, directory_path: Path) -> Path:
        extension = "json" if asset.type == AssetType.CHAT else "toml"
        return directory_path / f"{asset.id}.{extension}"

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
