"""People Data Labs email provider.

Uses PDL Person Enrichment (GET /v5/person/enrich). We match primarily by
LinkedIn URL (the strongest key), falling back to name + company. PDL charges
~1 credit only when it returns a match (HTTP 200); a 404 "no match" is free.
We pass min_likelihood to avoid paying for weak matches.
"""

from __future__ import annotations

import re

import httpx

from modules.common.config import get_settings
from modules.common.logger import get_logger
from modules.scout.detective.config import PDL_ENRICH_URL, PDL_MIN_LIKELIHOOD
from modules.scout.detective.email.base import EmailProvider, EmailResult
from modules.scout.detective.schemas import DecisionMaker

logger = get_logger("detective.email.pdl")


def _real_email(value: object) -> str | None:
    """Return the value only if it's a genuine email string (not a masked flag)."""
    return value if isinstance(value, str) and "@" in value else None


def _clean_profile(url: str) -> str:
    """Normalise a LinkedIn URL to the form PDL expects (linkedin.com/in/slug)."""
    url = re.sub(r"^https?://", "", url.strip()).rstrip("/")
    url = re.sub(r"^[a-z]{2}\.linkedin\.com", "linkedin.com", url)  # drop country subdomain
    return url


class PDLProvider(EmailProvider):
    """Finds a work email via People Data Labs person enrichment."""

    name = "pdl"

    def __init__(self, timeout: float = 20.0) -> None:
        self._api_key = get_settings().pdl_api_key
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def find(self, person: DecisionMaker, domain: str | None) -> EmailResult | None:
        if not self.is_configured:
            return None

        params: dict[str, str | int] = {"min_likelihood": PDL_MIN_LIKELIHOOD}
        if person.linkedin_url:
            params["profile"] = _clean_profile(person.linkedin_url)
        else:
            # Fall back to name + company matching.
            parts = person.name.split()
            if len(parts) < 2:
                return None
            params["first_name"], params["last_name"] = parts[0], parts[-1]
            if domain:
                params["company"] = domain

        try:
            resp = httpx.get(
                PDL_ENRICH_URL,
                params=params,
                headers={"X-Api-Key": self._api_key},
                timeout=self._timeout,
            )
        except httpx.RequestError as exc:
            logger.warning("PDL request error for %s: %s", person.name, exc)
            return None

        if resp.status_code == 404:
            logger.info("PDL: no match for %s (0 credits)", person.name)
            return None
        if resp.status_code != 200:
            logger.warning("PDL %s for %s: %s", resp.status_code, person.name, resp.text[:200])
            return None

        data = (resp.json() or {}).get("data") or {}

        email = _real_email(data.get("work_email"))
        if not email:
            emails = data.get("emails")
            for item in emails if isinstance(emails, list) else []:
                addr = item.get("address") if isinstance(item, dict) else item
                if _real_email(addr):
                    email = addr
                    break

        if not email:
            # On free/limited PDL plans, PII (emails) come back as boolean flags
            # (work_email: true) rather than values — treat as "not found" so we
            # fall through to the pattern generator.
            if data.get("work_email") is True or data.get("emails") is True:
                logger.info("PDL matched %s but email is masked (plan lacks PII) — falling back",
                            person.name)
            else:
                logger.info("PDL matched %s but returned no email", person.name)
            return None

        # Enrich a couple of extra identity fields (strings only).
        loc = data.get("location_locality")
        country = data.get("location_country")
        person.city = person.city or (loc if isinstance(loc, str) else None)
        person.country = person.country or (country if isinstance(country, str) else None)
        logger.info("PDL found email for %s", person.name)
        return EmailResult(email=email, status="verified", source="pdl", candidates=[email])
