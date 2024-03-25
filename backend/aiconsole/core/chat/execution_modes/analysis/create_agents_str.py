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

import random

from aiconsole.core.assets.types import AssetType
from aiconsole.core.chat.execution_modes.analysis.agents_to_choose_from import (
    agents_to_choose_from,
)
from aiconsole.core.project import project


def create_agents_str(agent_id) -> str:
    """
    Randomization of agents is done because LLMs have a tendency to overfit to the first few examples.
    """

    # Forced agents if available or enabled agents otherwise
    if agent_id:
        agent = project.get_project_assets().get_asset(agent_id, enabled=True)

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        possible_agent_choices = [agent]
    else:
        possible_agent_choices = agents_to_choose_from()

    random.shuffle(possible_agent_choices)

    new_line = "\n"
    random_agents = new_line.join([f"* {c.id} - {c.usage}" for c in possible_agent_choices])

    return random_agents
