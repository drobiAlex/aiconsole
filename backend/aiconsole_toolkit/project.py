from typing import cast

from aiconsole.core.assets.agents.agent import AICAgent
from aiconsole.core.assets.assets_service import assets
from aiconsole.core.assets.materials.material import AICMaterial
from aiconsole.core.assets.types import AssetType


async def get_all_agents() -> list[AICAgent]:
    lists = assets().filter_unified_assets(asset_type=AssetType.AGENT).values()
    return cast(list[AICAgent], (list[0] for list in lists))


async def get_all_materials() -> list[AICMaterial]:
    lists = assets().filter_unified_assets(asset_type=AssetType.MATERIAL).values()
    return cast(list[AICMaterial], (list[0] for list in lists))
