"""Persists leads as JSON files under ``data/Leads``.

One file per company (``<company-slug>.json``). If a company reappears with a
new signal, its signals are merged so we keep a single, richer record instead
of duplicates.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from modules.common.config import DATA_DIR
from modules.common.logger import get_logger
from modules.scout.radar.schemas import Lead

logger = get_logger("newsradar.store")

LEADS_DIR = DATA_DIR / "Leads"


def slugify(name: str) -> str:
    """Turn a company name into a filesystem-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown"


def _seen_urls_path() -> Path:
    return LEADS_DIR / ".seen_urls.json"


def load_seen_urls() -> set[str]:
    """Article URLs already processed (used to skip duplicates across runs)."""
    path = _seen_urls_path()
    if path.exists():
        try:
            return set(json.loads(path.read_text()))
        except (ValueError, OSError):
            return set()
    return set()


def save_seen_urls(urls: set[str]) -> None:
    LEADS_DIR.mkdir(parents=True, exist_ok=True)
    _seen_urls_path().write_text(json.dumps(sorted(urls), indent=2))


def save_lead(lead: Lead) -> Path:
    """Write ``lead`` to ``data/Leads/<slug>.json`` (merging signals if it exists)."""
    LEADS_DIR.mkdir(parents=True, exist_ok=True)
    lead.discovered_at = datetime.now(timezone.utc).isoformat()

    path = LEADS_DIR / f"{lead.company_slug}.json"
    record = lead.model_dump(mode="json")

    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except (ValueError, OSError):
            existing = {}
        signals = existing.get("signals", [])
    else:
        signals = []

    # Append this run's signal to the company's signal history.
    signals.append(
        {
            "signal_type": record["signal_type"],
            "reason_to_target": record["reason_to_target"],
            "confidence": record["confidence"],
            "article_headline": record["article_headline"],
            "article_url": record["article_url"],
            "published_date": record["published_date"],
            "source_name": record["source_name"],
            "discovered_at": record["discovered_at"],
        }
    )
    record["signals"] = signals

    path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    logger.info("Saved lead -> %s", path)
    return path
