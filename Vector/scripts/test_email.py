"""Test email finding through our code — ONE person (Soumith Chintala).

Exercises the configured provider (PDL) + keyless pattern fallback via
EmailFinder. Costs at most ~1 PDL credit; the result is cached so re-runs are
free. Run:  python -m scripts.test_email
"""

from __future__ import annotations

import json

from modules.scout.detective.email import EmailFinder
from modules.scout.detective.email.pattern_provider import PatternEmailProvider
from modules.scout.detective.schemas import DecisionMaker
from modules.scout.detective import store


def main() -> None:
    lead = next(l for l in store.load_qualified_leads(only_qualified=False)
                if l["company_slug"] == "thinking-machines")
    domain = lead.get("website_url")
    dm = lead["decision_makers"][0]
    person = DecisionMaker(name=dm["name"], title=dm.get("title", ""),
                           linkedin_url=dm.get("linkedin_url", ""))

    print(f"Person : {person.name}")
    print(f"Domain : {domain}")
    print(f"LinkedIn: {person.linkedin_url or '(none)'}\n")

    # 1) Full chain: configured provider (PDL) -> pattern fallback
    EmailFinder().enrich([person], domain)
    print("=== EmailFinder result (provider + fallback) ===")
    print(json.dumps(person.model_dump(mode="json"), indent=2))

    # 2) Show the keyless fallback on its own (provider forced off)
    only_fallback = DecisionMaker(name=dm["name"], linkedin_url=dm.get("linkedin_url", ""))
    res = PatternEmailProvider().find(only_fallback, domain)
    print("\n=== Pattern fallback alone ===")
    print(res)


if __name__ == "__main__":
    main()
