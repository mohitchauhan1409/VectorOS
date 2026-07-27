"""Compass agent (CLOSER module).

The CompassAgent analyzes meeting notes and decides the next best step.
"""

from __future__ import annotations

from typing import Any

from modules.common.base_agent import BaseAgent


class CompassAgent(BaseAgent):
    """Agent that analyzes meeting notes and decides the next best step."""

    name = "closer-compass-agent"

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the compass workflow.

        TODO: implement the compass logic.
        """
        self.logger.info("Running %s", self.name)
        raise NotImplementedError("CompassAgent.run is not implemented yet.")
