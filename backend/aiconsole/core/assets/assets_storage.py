from typing import Protocol

from .types import Asset


class AssetsStorage(Protocol):
    @property
    def assets(self) -> dict[str, list[Asset]]:  # fmt: off
        ...

    async def update_asset(
        self, original_asset_id: str, updated_asset: Asset, scope: str | None = None
    ) -> None:  # fmt: off
        ...

    async def create_asset(self, asset: Asset) -> None:  # fmt: off
        ...

    async def delete_asset(self, asset_id: str) -> None:  # fmt: off
        ...

    async def setup(self) -> tuple[bool, Exception | None]:  # fmt: off
        ...

    def destroy(self) -> None:  # fmt: off
        ...
