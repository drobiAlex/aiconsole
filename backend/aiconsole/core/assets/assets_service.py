import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Type

from aiconsole.core.assets.assets_storage import AssetsStorage
from aiconsole.core.assets.types import Asset, AssetLocation
from aiconsole.utils.events import InternalEvent, internal_events
from aiconsole.utils.notifications import Notifications

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AssetsUpdatedEvent(InternalEvent):
    pass


class Assets:
    _storage: AssetsStorage | None = None
    _notifications: Notifications | None = None

    def configure(self, storage_type: Type[AssetsStorage], **kwargs) -> None:
        """
        Configures the assets storage and notifications.

        :param storage_type: The type of assets storage to use.
        :param kwargs: Additional keyword arguments for the storage initialization.
        """
        self.clean_up()

        self._storage = storage_type(**kwargs)
        self._notifications = Notifications()

        internal_events().subscribe(
            AssetsUpdatedEvent,
            self._when_reloaded,
        )

        _log.info("Settings configured")

    @property
    def unified_assets(self) -> list[Asset]:
        """
        Retrives all assets from given sources.

        :return: A list of unified assets.
        """
        if not self._storage or not self._notifications:
            _log.error("Assets not configured.")
            raise ValueError("Assets not configured")
        ...

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

    async def _when_reloaded(self, AssetsUpdatedEvent) -> None:
        """
        Handles the assets updated event asynchronously.

        :param AssetsUpdatedEvent: The event indicating that assets have been updated.
        """
        if not self._storage or not self._notifications:
            _log.error("Assets not configured.")
            raise ValueError("Assets not configured")

        # await self._notifications.notify()


@lru_cache
def assets() -> Assets:
    """
    Returns a cached instance of the Assets class.

    :return: A singleton instance of the Assets class.
    """
    return Assets()
