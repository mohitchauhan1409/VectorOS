"""NewsRadar pipeline — the end-to-end lead-discovery flow.

For each configured news source and page:
  1. fetch raw HTML                         (fetcher)
  2. get CSS selectors                       (cache -> SelectorAgent, self-healing)
  3. parse structured articles               (parser)
  4. extract company + why-target signal     (LeadExtractionAgent, Gemini)
  5. enrich with website + LinkedIn          (CompanyEnricher / GoogleSearchTool)
  6. rate against our ICP                     (ICPRatingAgent, Gemini)
  7. persist high-fit leads as JSON          (store -> data/Leads)

Selectors are cached per-domain; if parsing yields nothing, the pipeline
re-infers them once and updates the cache.
"""

from __future__ import annotations

import json
from pathlib import Path

from modules.common.config import DATA_DIR
from modules.common.logger import get_logger
from modules.scout.radar.agents import (
    ICPRatingAgent,
    LeadExtractionAgent,
    SelectorAgent,
)
from modules.scout.radar.config import (
    FETCH_DELAY_SECONDS,
    MAX_HTML_CHARS_FOR_SELECTOR,
    MIN_ICP_SCORE,
    NEWS_SOURCES,
    NewsSource,
)
from modules.scout.radar.schemas import ArticleSelectors, Lead
from modules.scout.radar.NewsRadar import store
from modules.scout.radar.NewsRadar.cleaner import clean_for_llm
from modules.scout.radar.NewsRadar.enrichment import CompanyEnricher
from modules.scout.radar.NewsRadar.fetcher import fetch_html
from modules.scout.radar.NewsRadar.parser import parse_articles

logger = get_logger("newsradar.pipeline")

_CACHE_PATH = DATA_DIR / "cache" / "news_selectors.json"


class NewsRadarPipeline:
    """Runs the full NewsRadar lead-discovery flow."""

    def __init__(self, save_floor: int = 0) -> None:
        # save_floor: hard ICP floor below which a lead is not even saved
        # (default 0 = save everything). Qualification is a separate mark
        # (MIN_ICP_SCORE) applied to every saved lead.
        self.save_floor = save_floor
        # Agents are instantiated once and reused across all articles.
        self.selector_agent = SelectorAgent()
        self.lead_agent = LeadExtractionAgent()
        self.icp_agent = ICPRatingAgent()
        self.enricher = CompanyEnricher()
        self._selector_cache = self._load_cache()

    # ---- selector cache (self-healing extraction) ----
    def _load_cache(self) -> dict[str, dict]:
        if _CACHE_PATH.exists():
            try:
                return json.loads(_CACHE_PATH.read_text())
            except (ValueError, OSError):
                return {}
        return {}

    def _save_cache(self) -> None:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(self._selector_cache, indent=2))

    def _get_selectors(self, domain: str, html: str, page_url: str, *, force: bool = False) -> ArticleSelectors:
        """Return selectors for a domain, using cache unless forced to re-infer."""
        if not force and domain in self._selector_cache:
            return ArticleSelectors(**self._selector_cache[domain])

        cleaned = clean_for_llm(html, max_chars=MAX_HTML_CHARS_FOR_SELECTOR)
        selectors = self.selector_agent.run(cleaned, page_url)
        self._selector_cache[domain] = selectors.model_dump()
        self._save_cache()
        return selectors

    # ---- main flow ----
    def run(
        self,
        sources: list[NewsSource] | None = None,
        max_leads: int | None = None,
        on_lead=None,
        on_progress=None,
        on_article=None,
        max_evaluated: int | None = None,
    ) -> list[Lead]:
        """Scan news sources and return the leads that were saved.

        Args:
            sources: Sources to scan. Defaults to all *enabled* NEWS_SOURCES.
                     When passed explicitly, the ``enabled`` flag is ignored.
            max_leads: Stop after this many leads are SAVED (None = no limit).
                       With ``save_floor=MIN_ICP_SCORE`` this means "this many
                       qualified leads".
            on_lead: Callback invoked with each Lead as it's saved.
            on_progress: Callback(evaluated, saved) invoked per article.
            max_evaluated: Safety cap — stop after evaluating this many articles
                       even if ``max_leads`` isn't reached (avoids runaway scans
                       when qualified leads are rare).
        """
        if sources is None:
            sources = [s for s in NEWS_SOURCES if s.enabled]

        seen = store.load_seen_urls()
        saved: list[Lead] = []
        self._evaluated = 0

        for source in sources:
            if max_leads is not None and len(saved) >= max_leads:
                break
            if max_evaluated is not None and self._evaluated >= max_evaluated:
                break
            logger.info("=== Source: %s ===", source.name)
            remaining = None if max_leads is None else max_leads - len(saved)
            saved.extend(self._run_source(
                source, seen, max_leads=remaining, on_lead=on_lead,
                on_progress=on_progress, on_article=on_article, max_evaluated=max_evaluated,
            ))

        store.save_seen_urls(seen)
        logger.info("NewsRadar finished. %d leads saved (%d articles evaluated).",
                    len(saved), self._evaluated)
        return saved

    def _run_source(
        self, source: NewsSource, seen: set[str], max_leads: int | None = None,
        on_lead=None, on_progress=None, on_article=None, max_evaluated: int | None = None,
    ) -> list[Lead]:
        import time
        from urllib.parse import urlparse

        saved: list[Lead] = []
        first_page = True
        for page_url in source.iter_pages():
            if max_leads is not None and len(saved) >= max_leads:
                break
            if max_evaluated is not None and self._evaluated >= max_evaluated:
                break
            # Space out requests to the same host — several payments outlets 403
            # when paged back-to-back.
            if not first_page and FETCH_DELAY_SECONDS > 0:
                time.sleep(FETCH_DELAY_SECONDS)
            first_page = False
            domain = urlparse(page_url).netloc
            html = fetch_html(page_url)
            if not html:
                continue

            selectors = self._get_selectors(domain, html, page_url)
            articles = parse_articles(
                html, selectors, base_url=page_url, source_name=source.name
            )

            # Self-heal: selectors produced nothing -> re-infer once and retry.
            if not articles:
                logger.info("No articles with cached selectors; re-inferring for %s", domain)
                selectors = self._get_selectors(domain, html, page_url, force=True)
                articles = parse_articles(
                    html, selectors, base_url=page_url, source_name=source.name
                )

            for article in articles:
                if max_leads is not None and len(saved) >= max_leads:
                    break
                if max_evaluated is not None and self._evaluated >= max_evaluated:
                    break
                if article.url in seen:
                    continue
                seen.add(article.url)
                self._evaluated += 1
                lead, outcome = self._process_article(article)
                if on_article is not None:
                    on_article(article, outcome, lead is not None)
                if lead is not None:
                    saved.append(lead)
                    if on_lead is not None:
                        on_lead(lead)
                if on_progress is not None:
                    on_progress(self._evaluated, len(saved))
        return saved

    def _process_article(self, article) -> tuple[Lead | None, str]:
        """Run an article through extraction -> enrichment -> ICP -> save.

        Returns (lead_or_None, outcome) where outcome is a short human-readable
        reason ("not a company", "ICP 12 < 35", "ICP 42 ✓") for live display.
        """
        try:
            insight = self.lead_agent.run(article)
        except Exception as exc:  # noqa: BLE001 - never let one article kill the run
            logger.warning("Lead extraction failed for %r: %s", article.headline, exc)
            return None, "extraction error"

        if not insight.is_lead or not insight.company_name:
            return None, "not a company"

        try:
            enrichment = self.enricher.enrich(insight.company_name)
            rating = self.icp_agent.run(insight, enrichment)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qualification failed for %s: %s", insight.company_name, exc)
            return None, "qualification error"

        if rating.score < self.save_floor:
            logger.info("Below floor: %s (ICP %d < %d)",
                        insight.company_name, rating.score, self.save_floor)
            return None, f"{insight.company_name}: ICP {rating.score} < {self.save_floor}"

        qualified = rating.score >= MIN_ICP_SCORE
        logger.info("%s ICP=%d -> %s", insight.company_name, rating.score,
                    "QUALIFIED" if qualified else "not qualified")

        lead = Lead(
            company_name=insight.company_name,
            company_slug=store.slugify(insight.company_name),
            signal_type=insight.signal_type,
            reason_to_target=insight.reason_to_target,
            confidence=insight.confidence,
            website_url=enrichment.website_url,
            linkedin_url=enrichment.linkedin_url,
            icp=rating,
            qualified=qualified,
            source_name=article.source_name,
            article_headline=article.headline,
            article_url=article.url,
            published_date=article.published_date,
            discovered_at="",  # stamped in store.save_lead
        )
        store.save_lead(lead)
        return lead, f"{insight.company_name}: ICP {rating.score} ✓ QUALIFIED"


def run() -> list[Lead]:
    """Convenience entry point."""
    return NewsRadarPipeline().run()


if __name__ == "__main__":
    run()
