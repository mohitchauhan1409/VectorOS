"""Apollo enrichment client — deliberately frugal with credits.

Cost-saving design (Apollo trial credits are precious):
  * We only enrich profiles we ALREADY found (by LinkedIn URL) — no broad
    People Search that would surface (and could charge for) extra people.
  * We use bulk_match (up to 10 people per HTTP call) instead of one call each.
  * We reveal WORK EMAIL ONLY. Personal emails and phones are left off —
    a mobile phone alone costs +8 credits per person.
  * Every result (including misses) is CACHED on disk by LinkedIn URL, so a
    person is never enriched — or paid for — twice across runs.
  * `dry_run` (auto-on when no API key) finds people but never calls Apollo,
    so the whole flow is testable for free.

Credit model (per Apollo docs): ~1 credit per person when email/demographics
are found, 0 when nothing is found.
"""

from __future__ import annotations

import json

import httpx

from modules.common.config import DATA_DIR, get_settings
from modules.common.logger import get_logger
from modules.scout.detective.config import (
    APOLLO_BULK_MATCH_URL,
    APOLLO_MAX_BATCH,
    APOLLO_REVEAL_PERSONAL_EMAILS,
    APOLLO_REVEAL_PHONE_NUMBER,
)
from modules.scout.detective.schemas import DecisionMaker

logger = get_logger("detective.apollo")

_CACHE_PATH = DATA_DIR / "cache" / "apollo_people.json"


def _key(linkedin_url: str) -> str:
    return linkedin_url.split("?")[0].rstrip("/").lower()


class ApolloClient:
    """Frugal Apollo bulk-enrichment client with on-disk caching."""

    def __init__(self, dry_run: bool = False, timeout: float = 30.0) -> None:
        self._api_key = get_settings().apollo_api_key
        # No key -> force dry_run so nothing (and no credits) is ever spent.
        self.dry_run = dry_run or not self._api_key
        self._timeout = timeout
        self._cache = self._load_cache()
        self.credits_used_estimate = 0
        # Set True if Apollo rejects the endpoint as paid-only (free plan).
        self.plan_blocked = False

    # ---- cache ----
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

    # ---- public ----
    def enrich(self, people: list[DecisionMaker]) -> None:
        """Fill contact fields on ``people`` in place (cached + batched)."""
        # 1. Apply cache; collect the ones we still need to look up.
        pending: list[DecisionMaker] = []
        for person in people:
            if not person.linkedin_url:
                continue
            cached = self._cache.get(_key(person.linkedin_url))
            if cached is not None:
                self._apply(person, cached)
            else:
                pending.append(person)

        if not pending:
            return
        if self.dry_run:
            logger.info("DRY RUN: would enrich %d person(s) via Apollo (skipped)", len(pending))
            return

        # 2. Look up the rest in batches of <= APOLLO_MAX_BATCH.
        for i in range(0, len(pending), APOLLO_MAX_BATCH):
            batch = pending[i:i + APOLLO_MAX_BATCH]
            ok, matches = self._bulk_match(batch)
            if not ok:
                # API error / plan block — do NOT cache (so a later paid run
                # can retry these people). Stop if the whole plan is blocked.
                if self.plan_blocked:
                    break
                continue
            for person, match in zip(batch, matches):
                self._cache[_key(person.linkedin_url)] = match or {}  # cache genuine result/miss
                if match:
                    self._apply(person, match)
                    if match.get("email"):
                        self.credits_used_estimate += 1
        self._save_cache()
        logger.info("Apollo enrichment done (~%d credits used).", self.credits_used_estimate)

    # ---- internals ----
    def _bulk_match(self, batch: list[DecisionMaker]) -> tuple[bool, list[dict | None]]:
        """Return (ok, matches). ok=False on error/plan-block (don't cache)."""
        payload = {
            "details": [
                {
                    "linkedin_url": p.linkedin_url,
                    "name": p.name,
                    # organization hints help matching but aren't required
                }
                for p in batch
            ]
        }
        params = {
            "reveal_personal_emails": str(APOLLO_REVEAL_PERSONAL_EMAILS).lower(),
            "reveal_phone_number": str(APOLLO_REVEAL_PHONE_NUMBER).lower(),
        }
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self._api_key,
        }
        try:
            resp = httpx.post(
                APOLLO_BULK_MATCH_URL, params=params, headers=headers,
                json=payload, timeout=self._timeout,
            )
        except httpx.RequestError as exc:
            logger.warning("Apollo request error: %s", exc)
            return False, [None] * len(batch)

        # Free plans reject people-enrichment endpoints outright — report it
        # clearly (once) rather than as a generic failure.
        if resp.status_code == 403:
            try:
                code = resp.json().get("error_code")
            except ValueError:
                code = None
            if code == "API_INACCESSIBLE":
                self.plan_blocked = True
                logger.warning(
                    "Apollo bulk_match requires a PAID plan — the free plan blocks "
                    "people enrichment. No emails will be retrieved (0 credits used)."
                )
            else:
                logger.warning("Apollo 403: %s", resp.text[:200])
            return False, [None] * len(batch)

        try:
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Apollo bulk_match failed: %s", exc)
            return False, [None] * len(batch)
        # Apollo returns matches in request order under "matches".
        matches = data.get("matches") or []
        matches += [None] * (len(batch) - len(matches))
        return True, matches[: len(batch)]

    @staticmethod
    def _apply(person: DecisionMaker, match: dict) -> None:
        """Copy Apollo fields onto a DecisionMaker (safe for empty/miss dicts)."""
        if not match:
            person.enriched = True  # looked up, no data
            return
        org = match.get("organization") or {}
        person.email = match.get("email")
        person.email_status = match.get("email_status")
        person.apollo_id = match.get("id")
        person.city = match.get("city")
        person.country = match.get("country")
        # Fill title/linkedin if search missed them.
        person.title = person.title or match.get("title") or ""
        person.linkedin_url = person.linkedin_url or match.get("linkedin_url") or ""
        _ = org  # organization data available if needed later
        person.enriched = True
