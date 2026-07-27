"""Radar agent (SCOUT module).

The RadarAgent finds companies and leads across multiple sources.
"""

from __future__ import annotations

from typing import Any

from modules.common.base_agent import BaseAgent


class RadarAgent(BaseAgent):
    """Agent that finds companies and leads across multiple sources."""

    name = "scout-radar-agent"

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the radar workflow.

        TODO: implement the radar logic.
        """
        self.logger.info("Running %s", self.name)
        raise NotImplementedError("RadarAgent.run is not implemented yet.")
