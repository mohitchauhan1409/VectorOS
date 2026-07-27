"""Apollo email provider.

Thin adapter over the existing credit-frugal ApolloClient (bulk_match, work
email only, cached). Note: Apollo people enrichment requires a PAID plan — on a
free plan this returns None (plan-blocked) and the finder falls through.
"""

from __future__ import annotations

from modules.common.logger import get_logger
from modules.scout.detective.apollo_client import ApolloClient
from modules.scout.detective.email.base import EmailProvider, EmailResult
from modules.scout.detective.schemas import DecisionMaker

logger = get_logger("detective.email.apollo")


class ApolloProvider(EmailProvider):
    """Finds a work email via Apollo people enrichment."""

    name = "apollo"

    def __init__(self, client: ApolloClient | None = None) -> None:
        self.client = client or ApolloClient()

    def find(self, person: DecisionMaker, domain: str | None) -> EmailResult | None:
        self.client.enrich([person])  # mutates person in place, cached
        if person.email:
            return EmailResult(
                email=person.email,
                status=person.email_status or "verified",
                source="apollo",
                candidates=[person.email],
            )
        return None
