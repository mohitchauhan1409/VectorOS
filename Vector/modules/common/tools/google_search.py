"""Web search tool (shared).

Provides web search to any agent from one place, with two backends:

  1. Google Programmable Search (Custom Search JSON API) — used when
     ``GOOGLE_CSE_API_KEY`` and ``GOOGLE_CSE_CX`` are set and the API is enabled.
  2. DuckDuckGo (keyless) — automatic fallback so search works with no setup.

If Google CSE is unavailable (unconfigured, disabled, quota, or error), the tool
transparently falls back to DuckDuckGo. If everything fails, it returns an empty
list rather than raising, so pipelines keep running.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from modules.common.config import get_settings
from modules.common.logger import get_logger
from modules.common.tools.base_tool import BaseTool

_CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
logger = get_logger("tool.google-search")


@dataclass(frozen=True)
class SearchResult:
    """A single web search result."""

    title: str
    url: str
    snippet: str


class GoogleSearchTool(BaseTool):
    """Search the web (Google CSE with a keyless DuckDuckGo fallback)."""

    name = "google-search"
    description = "Search the web and return a list of {title, url, snippet} results."

    def __init__(self, timeout: float = 15.0) -> None:
        settings = get_settings()
        self._api_key = settings.google_cse_api_key
        self._cx = settings.google_cse_cx
        self._timeout = timeout

    @property
    def cse_configured(self) -> bool:
        """True when Google CSE credentials are present."""
        return bool(self._api_key and self._cx)

    # This tool can always search (DuckDuckGo needs no credentials).
    is_configured = True

    def run(self, query: str, *, num_results: int = 5) -> list[SearchResult]:
        """Run a search, returning up to ``num_results`` results (never raises)."""
        if self.cse_configured:
            results = self._cse_search(query, num_results)
            if results:
                return results
            logger.info("CSE returned no usable results; falling back to DuckDuckGo.")
        return self._ddg_search(query, num_results)

    def first_url(self, query: str, *, must_contain: str | None = None) -> str | None:
        """Return the first result URL, optionally requiring a substring match."""
        for result in self.run(query, num_results=10):
            if must_contain is None or must_contain in result.url:
                return result.url
        return None

    # ---- backends ----
    def _cse_search(self, query: str, num_results: int) -> list[SearchResult]:
        params = {
            "key": self._api_key,
            "cx": self._cx,
            "q": query,
            "num": max(1, min(num_results, 10)),  # API caps at 10 per request
        }
        try:
            resp = httpx.get(_CSE_ENDPOINT, params=params, timeout=self._timeout)
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Google CSE failed for %r: %s", query, exc)
            return []
        return [
            SearchResult(item.get("title", ""), item.get("link", ""), item.get("snippet", ""))
            for item in items
        ]

    def _ddg_search(self, query: str, num_results: int) -> list[SearchResult]:
        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                hits = ddgs.text(query, max_results=num_results)
        except Exception as exc:  # noqa: BLE001 - search must never break the pipeline
            logger.warning("DuckDuckGo search failed for %r: %s", query, exc)
            return []
        return [
            SearchResult(h.get("title", ""), h.get("href", ""), h.get("body", ""))
            for h in hits
        ]
