"""Fetches the raw HTML ("inspected code") of a news page.

Uses httpx with browser-like headers. This returns the server-rendered HTML;
JS-heavy sites that render article lists client-side may need a headless
browser later — that can slot in behind this same interface.
"""

from __future__ import annotations

import httpx

from modules.common.logger import get_logger

logger = get_logger("newsradar.fetcher")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_html(url: str, *, timeout: float = 20.0) -> str | None:
    """Return the raw HTML for ``url``, or None if the request fails."""
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None
    logger.info("Fetched %s (%d bytes)", url, len(resp.text))
    return resp.text
