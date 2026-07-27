"""Detective pipeline — finds decision-makers for qualified leads.

Flow per qualified company:
  1. web-search LinkedIn profiles for each target role     (finder, free)
  2. AI agent picks the real decision-makers               (ProfileExtractionAgent)
  3. Apollo bulk-enriches contact data (email)             (ApolloClient, credit-frugal)
  4. write decision_makers back into the lead JSON         (store)

`dry_run=True` (default when no Apollo key) runs steps 1-2 and skips Apollo, so
the flow is fully testable without spending credits.
"""

from __future__ import annotations

from modules.common.logger import get_logger
from modules.scout.detective.agents import ProfileExtractionAgent
from modules.scout.detective.config import (
    MAX_DECISION_MAKERS_PER_COMPANY,
    RESULTS_PER_ROLE,
    TARGET_ROLES,
)
from modules.scout.detective.email import EmailFinder
from modules.scout.detective.finder import ProfileFinder
from modules.scout.detective.schemas import DecisionMaker
from modules.scout.detective import store

logger = get_logger("detective.pipeline")


class DetectivePipeline:
    """Finds (and optionally enriches) decision-makers for qualified leads."""

    def __init__(self, dry_run: bool = False) -> None:
        self.finder = ProfileFinder()
        self.profile_agent = ProfileExtractionAgent()
        self.email_finder = EmailFinder()
        # dry_run: find profiles but skip email enrichment (no provider calls).
        self.dry_run = dry_run

    def run(self, max_companies: int | None = None, only_qualified: bool = True) -> list[dict]:
        """Process leads; return a per-company summary.

        Args:
            max_companies: Cap the number of companies processed.
            only_qualified: When True (default), only leads marked qualified
                (ICP >= MIN_ICP_SCORE) are worked. Set False for testing.
        """
        leads = store.load_qualified_leads(only_qualified=only_qualified)
        if max_companies is not None:
            leads = leads[:max_companies]
        if self.dry_run:
            logger.info("Detective DRY-RUN: profiles only, no email enrichment.")
        else:
            logger.info("Detective email provider: %s (fallback=%s)",
                        self.email_finder.provider_name, self.email_finder.use_fallback)

        summary: list[dict] = []
        for lead in leads:
            people = self._process_company(lead)
            summary.append({"company": lead["company_name"], "decision_makers": people})
        logger.info("Detective finished. %d companies processed.", len(summary))
        return summary

    def _process_company(self, lead: dict) -> list[DecisionMaker]:
        company = lead["company_name"]
        logger.info("=== %s ===", company)

        candidates = self.finder.find_candidates(
            company, list(TARGET_ROLES), results_per_role=RESULTS_PER_ROLE
        )
        if not candidates:
            logger.info("No profile candidates for %s", company)
            store.save_decision_makers(lead["_path"], [])
            return []

        people = self.profile_agent.run(company, list(TARGET_ROLES), candidates).people
        self._validate_profile_urls(people)
        # Keep the most confident, capped per company.
        people.sort(key=lambda p: p.confidence, reverse=True)
        people = people[:MAX_DECISION_MAKERS_PER_COMPANY]

        # Email enrichment via the configured provider + keyless fallback.
        if not self.dry_run:
            self.email_finder.enrich(people, lead.get("website_url"))
        else:
            logger.info("DRY RUN: skipping email enrichment for %s", company)

        store.save_decision_makers(lead["_path"], people)
        return people

    @staticmethod
    def _validate_profile_urls(people: list[DecisionMaker]) -> None:
        """Drop a LinkedIn URL when its /in/ slug doesn't match the person's name.

        Keyless search sometimes staples a namesake's profile to the right
        person. If the slug shares no name token, we can't trust it — blank the
        URL (so Apollo won't waste a lookup on it) and lower confidence.
        """
        import re

        for p in people:
            m = re.search(r"linkedin\.com/in/([^/?#]+)", p.linkedin_url or "", re.IGNORECASE)
            if not m:
                continue
            slug = re.sub(r"[^a-z]", "", m.group(1).lower())
            tokens = [t for t in re.split(r"[^a-z]+", p.name.lower()) if len(t) > 2]
            if tokens and not any(t in slug for t in tokens):
                logger.info("Rejecting mismatched profile for %s: %s", p.name, p.linkedin_url)
                p.linkedin_url = ""
                p.confidence = min(p.confidence, 0.3)


def run(
    dry_run: bool = False, max_companies: int | None = None, only_qualified: bool = True
) -> list[dict]:
    """Convenience entry point."""
    return DetectivePipeline(dry_run=dry_run).run(
        max_companies=max_companies, only_qualified=only_qualified
    )


if __name__ == "__main__":
    run()
