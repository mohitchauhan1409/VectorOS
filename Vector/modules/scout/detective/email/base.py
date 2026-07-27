"""Email-finding provider interface.

An email provider takes a person (name + linkedin_url) and a company domain and
tries to return an email. Providers should be cheap-first and never raise —
return None when they can't find anything so the finder can fall through.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from modules.scout.detective.schemas import DecisionMaker


@dataclass(frozen=True)
class EmailResult:
    """The outcome of an email lookup."""

    email: str
    status: str        # "verified" | "guessed" | "unverified"
    source: str        # "pdl" | "apollo" | "pattern"
    # Ranked alternatives (top == `email`). On catch-all domains SMTP can't pick
    # the real format, so we surface every candidate for outreach to try.
    candidates: list[str] = field(default_factory=list)


class EmailProvider(ABC):
    """Base class for all email-finding providers."""

    name: str = "provider"

    @abstractmethod
    def find(self, person: DecisionMaker, domain: str | None) -> EmailResult | None:
        """Return an EmailResult for ``person`` or None if not found."""
        raise NotImplementedError
