"""Finds candidate LinkedIn profiles for a company's decision-makers.

Uses the shared GoogleSearchTool (Google CSE, DuckDuckGo fallback). For each
target role it searches "<company> <role> linkedin" and keeps only
linkedin.com/in/ profile results — the raw candidates the profile agent then
disambiguates. This step is free (no Apollo credits).
"""

from __future__ import annotations

import re

from modules.common.logger import get_logger
from modules.common.tools import GoogleSearchTool

logger = get_logger("detective.finder")

_PROFILE_RE = re.compile(r"linkedin\.com/in/", re.IGNORECASE)


class ProfileFinder:
    """Searches the web for decision-maker LinkedIn profiles."""

    def __init__(self, search: GoogleSearchTool | None = None) -> None:
        self.search = search or GoogleSearchTool()

    def find_candidates(
        self, company_name: str, roles: list[str], results_per_role: int = 5
    ) -> list[dict]:
        """Return deduped {title, url, snippet} candidates across all roles."""
        seen: set[str] = set()
        candidates: list[dict] = []
        for role in roles:
            query = f"{company_name} {role} LinkedIn"
            for result in self.search.run(query, num_results=results_per_role):
                if not _PROFILE_RE.search(result.url):
                    continue
                # Normalise to the profile path to dedupe query-string variants.
                key = result.url.split("?")[0].rstrip("/")
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    {"title": result.title, "url": result.url, "snippet": result.snippet}
                )
        logger.info("%s -> %d profile candidate(s) across %d roles",
                    company_name, len(candidates), len(roles))
        return candidates
