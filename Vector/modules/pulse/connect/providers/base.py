"""LinkedInProvider — the transport interface every backend implements.

Deliberately small and channel-shaped so the scheduler/dispatcher never knows
which backend is live. Batch-friendly reads (``fetch_accepted`` /
``fetch_replies``) suit cloud tools like PhantomBuster that scrape in bulk,
while the per-action sends map cleanly onto both mock and API backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.pulse.connect.schemas import ActionResult, InboundMessage, LinkedInAccount


class LinkedInProvider(ABC):
    """Abstract LinkedIn transport."""

    #: short identifier, e.g. "mock" / "phantombuster"
    name: str = "base"

    @abstractmethod
    def send_invite(self, account: LinkedInAccount, linkedin_url: str, note: str) -> ActionResult:
        """Send a connection request (with an optional ≤300-char note)."""

    @abstractmethod
    def send_message(self, account: LinkedInAccount, linkedin_url: str, text: str) -> ActionResult:
        """Send a direct message (only valid once connected)."""

    @abstractmethod
    def fetch_accepted(self, account: LinkedInAccount, linkedin_urls: list[str]) -> set[str]:
        """Return which of ``linkedin_urls`` are now 1st-degree connections
        (i.e. our pending invites that have been accepted)."""

    @abstractmethod
    def fetch_replies(self, account: LinkedInAccount, since_iso: str) -> list[InboundMessage]:
        """Return inbound messages received since ``since_iso`` (from prospects)."""

    def health_check(self) -> tuple[bool, str]:
        """Return (ok, detail) — whether the provider is configured/reachable."""
        return True, "ok"
