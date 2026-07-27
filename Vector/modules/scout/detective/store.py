"""Reads qualified leads and writes decision-makers back into their JSON.

Detective enriches the same ``data/Leads/<slug>.json`` records Radar created,
adding a ``decision_makers`` array — company and its people stay in one file.
"""

from __future__ import annotations

import json
from pathlib import Path

from modules.common.logger import get_logger
from modules.scout.detective.schemas import DecisionMaker
from modules.scout.radar.NewsRadar.store import LEADS_DIR

logger = get_logger("detective.store")


def load_qualified_leads(only_qualified: bool = True) -> list[dict]:
    """Return saved lead records, by default only those marked qualified."""
    leads: list[dict] = []
    if not LEADS_DIR.exists():
        return leads
    for path in sorted(LEADS_DIR.glob("*.json")):
        if path.name.startswith("."):
            continue
        try:
            record = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if only_qualified and not record.get("qualified"):
            continue
        record["_path"] = str(path)
        leads.append(record)
    logger.info("Loaded %d lead(s) (%s).", len(leads),
                "qualified only" if only_qualified else "all")
    return leads


def save_decision_makers(lead_path: str, people: list[DecisionMaker]) -> None:
    """Write ``decision_makers`` onto an existing lead JSON file."""
    path = Path(lead_path)
    record = json.loads(path.read_text())
    record["decision_makers"] = [p.model_dump(mode="json") for p in people]
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    logger.info("Saved %d decision-maker(s) -> %s", len(people), path.name)
