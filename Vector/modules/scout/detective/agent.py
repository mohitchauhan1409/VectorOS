"""Detective agent (SCOUT module).

The DetectiveAgent uncovers the decision-makers at qualified companies and their
contact data (email, LinkedIn). It orchestrates the Detective pipeline:
web-search profiles -> AI extraction -> Apollo enrichment -> save.
"""

from __future__ import annotations

from typing import Any

from modules.common.logger import get_logger
from modules.scout.detective.pipeline import DetectivePipeline


class DetectiveAgent:
    """Finds decision-makers for the leads Radar qualified.

    Args:
        dry_run: When True (or when no Apollo key is set), profiles are found
                 but Apollo is never called — no credits are spent.
    """

    name = "scout-detective-agent"

    def __init__(self, dry_run: bool = False) -> None:
        self.logger = get_logger(self.name)
        self._pipeline = DetectivePipeline(dry_run=dry_run)

    def run(self, max_companies: int | None = None, **_: Any) -> list[dict]:
        """Run Detective over qualified leads; return a per-company summary."""
        self.logger.info("Running %s", self.name)
        return self._pipeline.run(max_companies=max_companies)
