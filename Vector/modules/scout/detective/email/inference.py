"""Keyless signals for picking the RIGHT email on hard (catch-all) domains.

Three helpers, all free:
  * harvest_domain_emails — scrape real "<local>@domain" addresses off the web
    (team/press pages, papers, GitHub, etc.), minus role inboxes.
  * infer_style          — from those samples, guess the domain's format
    (uses a dot? first-name only?) so we can re-rank generated candidates.
  * gravatar_exists      — hash a candidate and ask Gravatar if it's a real,
    registered account. Bypasses SMTP entirely, so it works on catch-all domains.
"""

from __future__ import annotations

import hashlib
import re

import httpx

from modules.common.logger import get_logger
from modules.common.tools import GoogleSearchTool

logger = get_logger("detective.email.inference")

# Non-personal inboxes that tell us nothing about a person's format.
_ROLE_PREFIXES = {
    "info", "hello", "hi", "hey", "contact", "support", "help", "sales", "press",
    "media", "marketing", "admin", "team", "jobs", "careers", "hr", "legal",
    "privacy", "security", "billing", "accounts", "noreply", "no-reply",
    "donotreply", "mail", "postmaster", "webmaster", "abuse", "notifications",
    "updates", "news", "newsletter", "feedback", "service", "office", "general",
    "enquiries", "inquiries", "partnerships", "partner", "business", "invest",
    "ir", "pr", "ops", "dev", "api", "root", "example", "email", "your",
}


def harvest_domain_emails(
    domain: str, hints: list[str], search: GoogleSearchTool | None = None, max_queries: int = 3
) -> set[str]:
    """Return real personal ``local@domain`` addresses discovered on the web."""
    search = search or GoogleSearchTool()
    rx = re.compile(r"([a-z0-9][a-z0-9._%+\-]*)@" + re.escape(domain), re.IGNORECASE)

    queries = [f'"@{domain}"'] + [f'{h} "@{domain}"' for h in hints]
    found: set[str] = set()
    for query in queries[:max_queries]:
        for result in search.run(query, num_results=6):
            blob = f"{result.title} {result.snippet} {result.url}"
            for m in rx.finditer(blob):
                local = m.group(1).lower()
                if local.split("+")[0] not in _ROLE_PREFIXES:
                    found.add(f"{local}@{domain.lower()}")
    if found:
        logger.info("Harvested %d personal address(es) at %s", len(found), domain)
    return found


def infer_style(locals_: list[str]) -> dict:
    """Guess the domain's format from sample local-parts."""
    if not locals_:
        return {"dot": False, "first_only": False}
    dot = sum("." in l for l in locals_)
    first_only = sum(l.isalpha() and len(l) <= 9 for l in locals_)
    n = len(locals_)
    return {"dot": dot > n / 2, "first_only": first_only > n / 2}


def gravatar_exists(email: str, timeout: float = 5.0) -> bool:
    """True if ``email`` is a registered Gravatar account (works on catch-all)."""
    digest = hashlib.md5(email.strip().lower().encode()).hexdigest()
    try:
        resp = httpx.get(
            f"https://www.gravatar.com/avatar/{digest}",
            params={"d": "404"}, timeout=timeout,
        )
        return resp.status_code == 200
    except httpx.HTTPError:
        return False
