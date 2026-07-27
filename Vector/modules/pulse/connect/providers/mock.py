"""MockProvider — a deterministic, in-memory LinkedIn simulator.

Lets the entire Connect module be built and tested with zero cost and zero ban
risk. It records invites/messages and lets a test drive the two things a real
LinkedIn would do back to us: accept an invite and send a reply.

Controls (set on the instance in tests):
  * ``auto_accept``  — if True (default), every invited URL shows up as accepted
    on the next ``fetch_accepted`` (simulates the prospect accepting).
  * ``accept(url)``  — mark a specific URL accepted (when auto_accept is False).
  * ``queue_reply(url, text)`` — enqueue an inbound reply the next poll returns.
"""

from __future__ import annotations

from modules.common.logger import get_logger
from modules.pulse.connect.schemas import ActionResult, InboundMessage, LinkedInAccount, utcnow_iso

logger = get_logger("pulse.connect.mock")


class MockProvider:
    name = "mock"

    def __init__(self, auto_accept: bool = True) -> None:
        self.auto_accept = auto_accept
        self._invited: set[str] = set()
        self._accepted: set[str] = set()
        self._connected: set[str] = set()   # already 1st-degree (no invite needed)
        self._messages: list[tuple[str, str]] = []
        self._reply_queue: list[InboundMessage] = []
        self._counter = 0

    # -- test controls ------------------------------------------------------
    def accept(self, linkedin_url: str) -> None:
        self._accepted.add(linkedin_url)

    def pre_connect(self, linkedin_url: str) -> None:
        """Mark a profile as already a 1st-degree connection (no invite needed)."""
        self._connected.add(linkedin_url)
        self._accepted.add(linkedin_url)

    def queue_reply(self, linkedin_url: str, text: str, received_at: str | None = None) -> None:
        self._counter += 1
        self._reply_queue.append(InboundMessage(
            linkedin_url=linkedin_url, provider_id=f"mock-reply-{self._counter}",
            text=text, received_at=received_at or utcnow_iso()))

    # -- provider interface -------------------------------------------------
    def send_invite(self, account: LinkedInAccount, linkedin_url: str, note: str) -> ActionResult:
        self._invited.add(linkedin_url)
        self._counter += 1
        logger.info("[mock] invite → %s (%d chars note)", linkedin_url, len(note or ""))
        return ActionResult(ok=True, provider_ref=f"mock-invite-{self._counter}")

    def send_message(self, account: LinkedInAccount, linkedin_url: str, text: str) -> ActionResult:
        self._messages.append((linkedin_url, text))
        self._counter += 1
        logger.info("[mock] message → %s", linkedin_url)
        return ActionResult(ok=True, provider_ref=f"mock-msg-{self._counter}")

    def fetch_accepted(self, account: LinkedInAccount, linkedin_urls: list[str]) -> set[str]:
        wanted = set(linkedin_urls)
        if self.auto_accept:
            self._accepted |= (self._invited & wanted)
        return (self._accepted | self._connected) & wanted

    def fetch_replies(self, account: LinkedInAccount, since_iso: str) -> list[InboundMessage]:
        drained, self._reply_queue = self._reply_queue, []
        return drained

    def health_check(self) -> tuple[bool, str]:
        return True, "mock provider (simulated)"
