"""Demo: run NewsRadar on the FIRST news source and save the first 2 leads.

This is a smoke test of the full autonomous flow:
  fetch raw HTML  ->  AI infers extraction logic  ->  parse articles
  ->  AI extracts company + why-target  ->  enrich (website/LinkedIn)
  ->  AI rates ICP  ->  save JSON to data/Leads

Run:  python -m scripts.demo_newsradar
"""

from __future__ import annotations

import json

from modules.common.logger import get_logger
from modules.scout.radar.config import NEWS_SOURCES
from modules.scout.radar.NewsRadar import NewsRadarPipeline

logger = get_logger("demo")


def main() -> None:
    first_source = NEWS_SOURCES[0]
    logger.info("DEMO: scanning first source only -> %s", first_source.name)

    # save_floor=0 so the demo reliably fills 2 leads regardless of fit
    # (the real ICP score + `qualified` mark are still computed on each lead).
    pipeline = NewsRadarPipeline(save_floor=0)
    leads = pipeline.run(sources=[first_source], max_leads=2)

    print("\n" + "=" * 70)
    print(f"  {len(leads)} demo lead(s) saved to data/Leads/")
    print("=" * 70)
    for lead in leads:
        print(f"\n▶ {lead.company_name}  (ICP {lead.icp.score}/100, tier {lead.icp.tier.value})")
        print(f"   signal : {lead.signal_type.value}")
        print(f"   why    : {lead.reason_to_target}")
        print(f"   website: {lead.website_url}")
        print(f"   linkedin: {lead.linkedin_url}")
        print(f"   article: {lead.article_headline}")
        print(json.dumps(lead.model_dump(mode="json"), indent=2)[:0])  # (full JSON is on disk)


if __name__ == "__main__":
    main()
