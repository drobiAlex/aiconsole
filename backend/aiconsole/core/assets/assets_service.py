import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Type

from aiconsole.core.assets.assets_storage import AssetsStorage
from aiconsole.core.assets.types import Asset, AssetLocation, AssetType
from aiconsole.core.settings.settings import settings
from aiconsole.utils.events import InternalEvent, internal_events
from aiconsole.utils.notifications import Notifications
from aiconsole_toolkit.settings.partial_settings_data import PartialSettingsData

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AssetsUpdatedEvent(InternalEvent):
    pass


class Assets:
    _storage: AssetsStorage | None = None
    _notifications: Notifications | None = None

    async def configure(self, storage: AssetsStorage) -> None:
        """
        Configures the assets storage and notifications.

        :param storage_type: The type of assets storage to use.
        :param kwargs: Additional keyword arguments for the storage initialization.
        """
        self.clean_up()

        await storage.setup()
        self._storage = storage
        self._notifications = Notifications()

        internal_events().subscribe(
            AssetsUpdatedEvent,
            self._when_reloaded,
        )

        _log.info("Settings configured")

    # TODO: needs to have filters on location, enabled, ...
    @property
    def unified_assets(self) -> dict[str, list[Asset]]:
        """
        Retrives all assets from given sources.

        :return: A dict of unified assets.
        """
        if not self._storage or not self._notifications:
            _log.error("Assets not configured.")
            raise ValueError("Assets not configured")

        return self._storage.assets

    def clean_up(self) -> None:
        """
        Cleans up resources used by the assets, such as storage and notifications.
        """
        if self._storage:
            self._storage.destroy()

        self._storage = None
        self._notifications = None

        internal_events().unsubscribe(
            AssetsUpdatedEvent,
            self._when_reloaded,
        )

    # TODO: add notification message
    async def _when_reloaded(self, AssetsUpdatedEvent) -> None:
        """
        Handles the assets updated event asynchronously.

        :param AssetsUpdatedEvent: The event indicating that assets have been updated.
        """
        if not self._storage or not self._notifications:
            _log.error("Assets not configured.")
            raise ValueError("Assets not configured")

        await self._notifications.notify()

    def get_asset(self, asset_id, location: AssetLocation | None = None, enabled: bool | None = None) -> Asset | None:
        if not self._storage or not self._notifications:
            _log.error("Assets not configured.")
            raise ValueError("Assets not configured")

        if asset_id not in self.unified_assets or len(self.unified_assets[asset_id]) == 0:
            return None

        for asset in self.unified_assets[asset_id]:
            if location is None or asset.defined_in == location:
                if enabled is not None and self.is_asset_enabled(asset.id) != enabled:
                    return None
                return asset

        return None

    # TODO: Why do we need to suppress for all or maybe supress to a specific connection
    async def create_asset(self, asset: Asset) -> None:
        if not self._storage or not self._notifications:
            _log.error("Assets not configured.")
            raise ValueError("Assets not configured")

        self._notifications.suppress_next_notification()
        await self._storage.create_asset(asset)

    async def update_asset(self, original_asset_id: str, updated_asset: Asset, scope: str | None = None):
        if not self._storage or not self._notifications:
            _log.error("Assets not configured.")
            raise ValueError("Assets not configured")

        self._notifications.suppress_next_notification()
        await self._storage.update_asset(original_asset_id, updated_asset, scope)

    async def delete_asset(self, asset_id: str) -> None:
        if not self._storage or not self._notifications:
            _log.error("Assets not configured.")
            raise ValueError("Assets not configured")

        self._notifications.suppress_next_notification()
        await self._storage.delete_asset(asset_id)

    # TODO: this has to be done on asset load
    def is_asset_enabled(self, asset_id: str) -> bool:
        if not self._storage or not self._notifications:
            _log.error("Assets not configured.")
            raise ValueError("Assets not configured")

        settings_data = settings().unified_settings

        if asset_id in settings_data.assets:
            return settings_data.assets[asset_id]

        asset = self.unified_assets[asset_id][0]
        default_status = asset.enabled_by_default if asset else True
        return default_status

    def set_enabled(self, asset_id: str, enabled: bool, to_global: bool = False) -> None:
        settings().save(PartialSettingsData(assets={asset_id: enabled}), to_global=to_global)

    # TODO: this thing only renames in settigns, no changes to actual name
    def rename_asset(self, old_id: str, new_id: str) -> None:
        partial_settings = PartialSettingsData(
            assets_to_reset=[old_id],
            assets={new_id: self.is_asset_enabled(old_id)},
        )
        settings().save(partial_settings, to_global=False)


@lru_cache
def assets() -> Assets:
    """
    Returns a cached instance of the Assets class.

    :return: A singleton instance of the Assets class.
    """
    return Assets()
