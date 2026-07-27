"""Test Detective on one company — DRY RUN (no Apollo credits spent).

Runs: web-search LinkedIn profiles -> AI picks decision-makers -> (Apollo
skipped in dry-run) -> save into the lead JSON.

only_qualified=False so it works the existing demo leads even though they
scored below the qualification bar. Run:  python -m scripts.test_detective
"""

from __future__ import annotations

from modules.common.logger import get_logger
from modules.scout.detective import DetectivePipeline

logger = get_logger("test")

MAX_COMPANIES = 1  # keep web-search volume small for the test


def main() -> None:
    pipeline = DetectivePipeline(dry_run=True)  # never calls Apollo
    summary = pipeline.run(max_companies=MAX_COMPANIES, only_qualified=False)

    print("\n" + "=" * 72)
    print("  DETECTIVE (dry run) — decision-makers found")
    print("=" * 72)
    for entry in summary:
        print(f"\n▶ {entry['company']}")
        if not entry["decision_makers"]:
            print("   (none found)")
        for p in entry["decision_makers"]:
            print(f"   • {p.name}  —  {p.title}  [{p.role_category}, conf {p.confidence:.2f}]")
            print(f"     linkedin: {p.linkedin_url}")
            print(f"     email   : {p.email or '(not enriched — dry run)'}")


if __name__ == "__main__":
    main()
