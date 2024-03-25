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
import datetime
import logging
from collections import defaultdict

from aiconsole.api.websockets.connection_manager import connection_manager
from aiconsole.api.websockets.server_messages import AssetsUpdatedServerMessage
from aiconsole.core.assets.types import Asset, AssetType

_log = logging.getLogger(__name__)


class Assets:
    async def reload(self, initial: bool = False):
        _log.info("Reloading assets ...")

        li: dict[str, list[Asset]] = defaultdict(list)
        for asset_type in [AssetType.AGENT, AssetType.MATERIAL, AssetType.CHAT, AssetType.USER]:
            d = await load_all_assets(asset_type)

            # This might not be bulletproof, what if the settings are loaded after the assets? the backend should not use .enabled directly ...
            # How to properly mix dynamic data or even per user data (chat options) with static data (assets, chats etc.)?
            for k, v in d.items():
                for asset in v:
                    asset.enabled = self.is_enabled(asset.id)

            for k, v in d.items():
                li[k].extend(v)
        self.cached_assets = li

        await connection_manager().send_to_all(
            AssetsUpdatedServerMessage(
                initial=(
                    initial
                    or not (
                        not self._suppress_notification_until
                        or self._suppress_notification_until < datetime.datetime.now()
                    )
                ),
                count=len(self.cached_assets),
            )
        )

