from typing import cast

from aiconsole.consts import DIRECTOR_AGENT_ID
from aiconsole.core.assets.agents.agent import AICAgent
from aiconsole.core.assets.types import AssetType
from aiconsole.core.project import project


def agents_to_choose_from() -> list[AICAgent]:
    assets = project.get_project_assets().filter_unified_assets(enabled=True, asset_type=AssetType.AGENT).values()

    # Filter to agents except for director
    assets = [asset[0] for asset in assets if asset[0].id != DIRECTOR_AGENT_ID]

    return cast(list[AICAgent], assets)
