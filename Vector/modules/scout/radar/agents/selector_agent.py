"""SelectorAgent — infers extraction selectors from raw page HTML.

Given the cleaned "inspected code" of a news listing page, this agent works out
the CSS selectors needed to pull each article's headline, link, date and
summary. The pipeline caches the result per-domain and only re-runs this agent
when a site's structure changes (self-healing extraction).

Runs on the NORMAL tier (a cheap, fast model) — this is structural
pattern-matching, not deep reasoning, so we keep it token-efficient.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.scout.radar.config import NORMAL_LLM
from modules.scout.radar.schemas import ArticleSelectors

_SYSTEM = """You are an expert web-scraping engineer.
You are given the cleaned HTML of a NEWS LISTING page (scripts and styles removed).
Your job is to return CSS selectors, compatible with BeautifulSoup's .select(),
that extract the list of article items on the page.

Rules:
- `article_container` MUST match each individual article item in the listing
  (e.g. "article", "li.post", "div.card"). It should match MANY elements, one per article.
- `headline_selector` and `link_selector` are evaluated RELATIVE to each container match.
- Prefer stable, semantic selectors (tag + class) over brittle nth-child chains.
- The link element is usually an <a>; set `link_attribute` to the attribute holding
  the URL (normally "href").
- Only set `date_selector` / `summary_selector` if such elements clearly exist.
- If unsure between options, choose the one that most reliably matches every article."""


class SelectorAgent(BaseAgent):
    """Infers `ArticleSelectors` for a news listing page."""

    name = "radar-selector-agent"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=NORMAL_LLM["provider"], model=NORMAL_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(ArticleSelectors)

    def run(self, html: str, page_url: str) -> ArticleSelectors:
        """Return the CSS selectors for extracting articles from ``html``."""
        self.logger.info("Inferring selectors for %s", page_url)
        prompt = (
            f"{_SYSTEM}\n\n"
            f"PAGE URL: {page_url}\n\n"
            f"CLEANED HTML:\n{html}"
        )
        return self._structured.invoke(prompt)
