"""EmailFinder — resolves decision-maker emails via a configurable chain.

Order per person:
  1. the configured primary provider (EMAIL_PROVIDER: pdl / apollo / none)
  2. the keyless pattern generator + SMTP fallback (if EMAIL_PATTERN_FALLBACK)

Results are cached on disk by LinkedIn URL (or name+domain) so a person is never
looked up — or paid for — twice. Never raises.
"""

from __future__ import annotations

import json

from modules.common.config import DATA_DIR
from modules.common.logger import get_logger
from modules.scout.detective.config import EMAIL_PATTERN_FALLBACK, EMAIL_PROVIDER
from modules.scout.detective.email.base import EmailProvider, EmailResult
from modules.scout.detective.email.pattern_provider import PatternEmailProvider
from modules.scout.detective.schemas import DecisionMaker

logger = get_logger("detective.email")

_CACHE_PATH = DATA_DIR / "cache" / "emails.json"


def _build_primary(provider: str) -> EmailProvider | None:
    if provider == "pdl":
        from modules.scout.detective.email.pdl_provider import PDLProvider
        return PDLProvider()
    if provider == "apollo":
        from modules.scout.detective.email.apollo_provider import ApolloProvider
        return ApolloProvider()
    return None


def _key(person: DecisionMaker, domain: str | None) -> str:
    if person.linkedin_url:
        return person.linkedin_url.split("?")[0].rstrip("/").lower()
    return f"{person.name.lower()}|{(domain or '').lower()}"


class EmailFinder:
    """Finds emails using the configured provider, then a keyless fallback."""

    def __init__(self, provider: str | None = None, use_fallback: bool | None = None) -> None:
        self.provider_name = provider or EMAIL_PROVIDER
        self.primary = _build_primary(self.provider_name)
        self.use_fallback = EMAIL_PATTERN_FALLBACK if use_fallback is None else use_fallback
        self.fallback = PatternEmailProvider() if self.use_fallback else None
        self._cache = self._load_cache()

    def _load_cache(self) -> dict[str, dict]:
        if _CACHE_PATH.exists():
            try:
                return json.loads(_CACHE_PATH.read_text())
            except (ValueError, OSError):
                return {}
        return {}

    def _save_cache(self) -> None:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(self._cache, indent=2))

    def enrich(self, people: list[DecisionMaker], domain: str | None) -> None:
        """Resolve and attach emails to each person in place."""
        for person in people:
            key = _key(person, domain)
            if key in self._cache:
                self._apply(person, self._cache[key])
                continue

            result = self._find_one(person, domain)
            self._cache[key] = (
                {"email": result.email, "status": result.status, "source": result.source}
                if result else {}
            )
            if result:
                self._apply(person, self._cache[key])
            person.enriched = True
        self._save_cache()

    def _find_one(self, person: DecisionMaker, domain: str | None) -> EmailResult | None:
        if self.primary is not None:
            result = self.primary.find(person, domain)
            if result:
                return result
            logger.info("%s: primary provider (%s) found nothing", person.name, self.provider_name)
        if self.fallback is not None:
            return self.fallback.find(person, domain)
        return None

    @staticmethod
    def _apply(person: DecisionMaker, cached: dict) -> None:
        if cached.get("email"):
            person.email = cached["email"]
            person.email_status = cached.get("status")
            person.email_source = cached.get("source")
