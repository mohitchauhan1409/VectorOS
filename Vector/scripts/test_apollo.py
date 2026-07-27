"""Test the Apollo integration through our code — ONE person only.

Enriches just Thinking Machines' first decision-maker (Soumith Chintala) via
ApolloClient.bulk_match, so this costs at most ~1 credit. The result is cached,
so re-running this script spends 0 further credits.

Run:  python -m scripts.test_apollo
"""

from __future__ import annotations

import json

from modules.common.config import get_settings
from modules.scout.detective.apollo_client import ApolloClient, _CACHE_PATH
from modules.scout.detective.schemas import DecisionMaker
from modules.scout.detective import store


def main() -> None:
    settings = get_settings()
    print("APOLLO_API_KEY loaded:", bool(settings.apollo_api_key),
          f"(…{settings.apollo_api_key[-4:]})" if settings.apollo_api_key else "")

    # Pull Soumith straight from the saved lead so we use real data.
    lead = next(l for l in store.load_qualified_leads(only_qualified=False)
                if l["company_slug"] == "thinking-machines")
    dm_raw = lead["decision_makers"][0]
    soumith = DecisionMaker(
        name=dm_raw["name"],
        title=dm_raw.get("title", ""),
        role_category=dm_raw.get("role_category", ""),
        linkedin_url=dm_raw["linkedin_url"],
    )
    print(f"\nEnriching: {soumith.name}  ({soumith.linkedin_url})")

    client = ApolloClient(dry_run=False)  # real call
    print("dry_run:", client.dry_run)
    client.enrich([soumith])

    print("\n=== RESULT ===")
    print(json.dumps(soumith.model_dump(mode="json"), indent=2))
    print(f"\n~credits used this run: {client.credits_used_estimate}")

    # Show exactly what Apollo returned (from cache) for inspection.
    cached = json.loads(_CACHE_PATH.read_text())
    key = soumith.linkedin_url.split("?")[0].rstrip("/").lower()
    raw = cached.get(key, {})
    print("\n=== raw Apollo fields returned ===")
    if raw:
        for k in ("id", "name", "title", "email", "email_status", "linkedin_url", "city", "country"):
            print(f"  {k}: {raw.get(k)}")
    else:
        print("  (no match / empty — 0 credits charged)")


if __name__ == "__main__":
    main()
