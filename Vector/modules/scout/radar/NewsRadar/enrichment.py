"""Company enrichment — finds a company's website and LinkedIn URL.

Built on the shared GoogleSearchTool so any radar/agent can reuse the same
capability. Best-effort: if search finds nothing, the field stays None and the
pipeline continues.

Search rankings are noisy (especially keyless DuckDuckGo, which rotates
backends), so we don't trust position. Instead we *score every candidate by how
well its domain matches the company name* and pick the best — e.g. for "SpaceX"
that makes ``spacex.com`` beat a higher-ranked lookalike like ``spacexusa.org``.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from modules.common.logger import get_logger
from modules.common.tools import GoogleSearchTool
from modules.scout.radar.schemas import Enrichment

logger = get_logger("newsradar.enrichment")

# Domains that are never a company's *own* website.
_NON_WEBSITE_DOMAINS = (
    "linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "youtube.com", "crunchbase.com", "wikipedia.org", "grokipedia.com",
    "bloomberg.com", "reuters.com", "techcrunch.com", "fortune.com", "cnbc.com",
    "medium.com", "github.com", "reddit.com", "tradingview.com", "startpage.com",
    "yahoo.com", "bing.com", "google.com",
)
_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu"}
_TLD_BONUS = {"com": 5, "ai": 4, "io": 3, "co": 2, "app": 1}


def _norm(text: str) -> str:
    """Lowercase, alphanumerics only (e.g. 'SpaceX, Inc.' -> 'spacexinc')."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _host(url: str) -> str:
    net = urlparse(url).netloc.lower()
    return net.removeprefix("www.")


def _sld(host: str) -> str:
    """Registrable label, handling ccTLDs like 'co.uk' (example.co.uk -> example)."""
    parts = host.split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in _SECOND_LEVEL:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else host


class CompanyEnricher:
    """Resolves external identifiers for a company by name."""

    def __init__(self, search: GoogleSearchTool | None = None) -> None:
        self.search = search or GoogleSearchTool()

    def enrich(self, company_name: str) -> Enrichment:
        """Find the company's website and LinkedIn company page."""
        website = self._find_website(company_name)
        linkedin = self._find_linkedin(company_name)
        logger.info("Enriched %s -> website=%s linkedin=%s", company_name, website, linkedin)
        return Enrichment(website_url=website, linkedin_url=linkedin)

    def _gather(self, queries: list[str], num_results: int = 10):
        """Run several queries and merge deduped results (better coverage)."""
        seen: set[str] = set()
        for query in queries:
            for result in self.search.run(query, num_results=num_results):
                if result.url and result.url not in seen:
                    seen.add(result.url)
                    yield result

    # ---- website ----
    def _find_website(self, company_name: str) -> str | None:
        cslug = _norm(company_name)
        tokens = [t for t in re.split(r"[^a-z0-9]+", company_name.lower()) if len(t) > 2]

        best_url, best_score, fallback = None, -1, None
        candidates = self._gather([f"{company_name} official website", company_name])
        for result in candidates:
            host = _host(result.url)
            if not host or any(host.endswith(bad) for bad in _NON_WEBSITE_DOMAINS):
                continue
            fallback = fallback or result.url  # first plausible, name-agnostic
            score = self._domain_score(host, cslug, tokens)
            if score > best_score:
                best_score, best_url = score, result.url

        # Require some name overlap to trust the scored pick; else fall back.
        chosen = best_url if best_score >= 40 else fallback
        return self._root(chosen) if chosen else None

    @staticmethod
    def _domain_score(host: str, cslug: str, tokens: list[str]) -> int:
        sld = _sld(host)
        if sld == cslug:
            score = 100
        elif cslug and (sld.startswith(cslug) or cslug.startswith(sld)):
            score = 80
        elif tokens and all(tok in host for tok in tokens):
            score = 60
        elif any(tok in sld for tok in tokens):
            score = 40
        else:
            score = 10
        score += _TLD_BONUS.get(host.rsplit(".", 1)[-1], 0)
        score += max(0, 2 - host.count("."))  # prefer shorter, apex-ish domains
        return score

    @staticmethod
    def _root(url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"

    # ---- linkedin ----
    def _find_linkedin(self, company_name: str) -> str | None:
        cslug = _norm(company_name)
        best_url, best_score = None, -1
        candidates = self._gather([f"{company_name} LinkedIn", f"{company_name} LinkedIn company"])
        for result in candidates:
            m = re.search(r"linkedin\.com/company/([^/?#]+)", result.url)
            if not m:
                continue
            slug = _norm(m.group(1))
            if slug == cslug:
                score = 100
            elif slug.startswith(cslug) or cslug.startswith(slug):
                score = 80
            else:
                score = 30
            if score > best_score:
                best_score, best_url = score, f"https://www.linkedin.com/company/{m.group(1)}"
        return best_url
