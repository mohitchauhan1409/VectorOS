"""Test the complete NewsRadar over a few pages of one source.

Runs the full autonomous flow end-to-end (fetch -> AI selectors -> parse ->
AI lead extraction -> enrich -> AI ICP rating -> save) but bounded to a couple
of pages and a lead cap so it's fast and cheap to observe.

Tweak the knobs below. Run:  python -m scripts.test_newsradar
"""

from __future__ import annotations

import dataclasses

from modules.common.logger import get_logger
from modules.scout.radar.config import NEWS_SOURCES
from modules.scout.radar.NewsRadar import NewsRadarPipeline

logger = get_logger("test")

# --- knobs ---
SOURCE_INDEX = 0     # which NEWS_SOURCES entry to scan
MAX_PAGES = 2        # how many listing pages to walk
MAX_LEADS = 5        # stop after this many leads are saved
SAVE_FLOOR = 0       # keep every lead so we can see all scores (qualified mark still applied)


def main() -> None:
    base = NEWS_SOURCES[SOURCE_INDEX]
    # Limit pagination to MAX_PAGES for the test.
    source = dataclasses.replace(base, page_start=1, page_end=MAX_PAGES)

    logger.info("TEST: %s | pages 1-%d | max_leads=%d", source.name, MAX_PAGES, MAX_LEADS)

    pipeline = NewsRadarPipeline(save_floor=SAVE_FLOOR)
    leads = pipeline.run(sources=[source], max_leads=MAX_LEADS)

    print("\n" + "=" * 72)
    print(f"  RESULT: {len(leads)} lead(s) saved to data/Leads/")
    print("=" * 72)
    # Sort best-fit first for readability.
    for lead in sorted(leads, key=lambda l: l.icp.score, reverse=True):
        mark = "✅ QUALIFIED" if lead.qualified else "· not qualified"
        print(f"\n▶ {lead.company_name}   [ICP {lead.icp.score}/100 · tier {lead.icp.tier.value}] {mark}")
        print(f"   signal  : {lead.signal_type.value}")
        print(f"   why now : {lead.reason_to_target}")
        print(f"   website : {lead.website_url or '—'}")
        print(f"   linkedin: {lead.linkedin_url or '—'}")
        print(f"   icp why : {lead.icp.rationale}")
        print(f"   article : {lead.article_headline}")


if __name__ == "__main__":
    main()
