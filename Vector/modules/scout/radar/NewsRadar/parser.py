"""Applies inferred selectors to a page's HTML to produce structured articles."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from modules.common.logger import get_logger
from modules.scout.radar.schemas import ArticleSelectors, RawArticle

logger = get_logger("newsradar.parser")


def _text(container, selector: str | None) -> str | None:
    if not selector:
        return None
    el = container.select_one(selector)
    return el.get_text(strip=True) if el else None


def parse_articles(
    html: str,
    selectors: ArticleSelectors,
    *,
    base_url: str,
    source_name: str,
) -> list[RawArticle]:
    """Extract articles from ``html`` using ``selectors``.

    Returns an empty list if the container selector matches nothing — the
    pipeline treats that as a signal to re-infer selectors (self-healing).
    """
    soup = BeautifulSoup(html, "lxml")
    containers = soup.select(selectors.article_container)
    logger.info("Selector %r matched %d containers", selectors.article_container, len(containers))

    articles: list[RawArticle] = []
    for container in containers:
        headline = _text(container, selectors.headline_selector)
        link_el = container.select_one(selectors.link_selector)
        raw_url = link_el.get(selectors.link_attribute) if link_el else None

        if not headline or not raw_url:
            continue  # incomplete item — skip

        articles.append(
            RawArticle(
                headline=headline,
                url=urljoin(base_url, raw_url),
                published_date=_text(container, selectors.date_selector),
                summary=_text(container, selectors.summary_selector),
                source_name=source_name,
            )
        )

    logger.info("Parsed %d complete articles", len(articles))
    return articles
