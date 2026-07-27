"""handle_scheduling — the meeting-booking step, channel-agnostic.

Called by the Inbox/Connect conversation handlers once a prospect is ready to
talk. It computes our real open slots, lets the SchedulingAgent decide + phrase,
and — critically — only books a slot that is genuinely free (validated here, not
trusted from the model). Returns the reply to send + whether a booking happened.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from modules.common.logger import get_logger
from modules.pulse.scheduling import availability, config
from modules.pulse.scheduling.schemas import (
    BookingRequest,
    SchedulingAction,
    TimeSlot,
)

logger = get_logger("pulse.scheduling.flow")

_agent = None
_PROMPT_SLOT_LIMIT = 15


def _tz():
    try:
        return ZoneInfo(config.TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


def _match_slot(iso: str, slots: list[TimeSlot]) -> TimeSlot | None:
    """Find the offered slot whose start equals `iso` (same instant)."""
    try:
        want = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    for s in slots:
        if abs((s.start - want).total_seconds()) < 60:
            return s
    return None


def _propose_text(slots: list[TimeSlot], tz, prefix: str) -> str:
    offered = slots[: config.SLOTS_TO_OFFER]
    lines = "\n".join(f"• {s.label(tz)}" for s in offered)
    return f"{prefix}\n{lines}\n\nAll times {config.TIMEZONE}. Which works — or share a window that suits you?"


def handle_scheduling(*, attendee_name: str, company: str, thread: str, latest_reply: str,
                      channel: str = "email", known_email: str = "",
                      pending_slot_iso: str | None = None, existing_event_id: str = "",
                      existing_slot_iso: str | None = None, now: datetime | None = None,
                      provider=None, agent=None, dry_run: bool = False) -> dict:
    """Advance the booking conversation one turn. Returns:
    {action, reply, booked, slot, join_url, pending_slot_iso, attendee_email}.

    On LinkedIn, a client agreeing to a time first triggers ``confirm_email``
    (confirm the on-file email / provide one / offer a Meet link); the agreed
    slot is held in ``pending_slot_iso`` until the next turn resolves the email.
    """
    global _agent
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    tz = _tz()
    if provider is None:
        from modules.pulse.scheduling.providers import get_calendar_provider
        provider = get_calendar_provider()

    slots = availability.free_slots(now, provider=provider, limit=_PROMPT_SLOT_LIMIT)
    # Keep any pending (already-agreed) slot available for booking even if it
    # falls outside the freshly-computed list edge.
    pending_slot = _match_slot(pending_slot_iso, slots) if pending_slot_iso else None
    if not slots and not pending_slot:
        return {"action": "ask", "reply": "Let me find a couple of open times and come "
                "right back to you — what days generally work?", "booked": False,
                "slot": None, "join_url": "", "pending_slot_iso": None, "attendee_email": ""}

    if agent is None:
        if _agent is None:
            from modules.pulse.scheduling.agent import SchedulingAgent
            _agent = SchedulingAgent()
        agent = _agent

    now_label = now.astimezone(tz).strftime("%A %b %-d, %-I:%M %p")
    pending_label = pending_slot.label(tz) if pending_slot else ""
    existing_dt = _parse_iso(existing_slot_iso)
    existing_label = existing_dt.astimezone(tz).strftime("%a %b %-d, %-I:%M %p") if existing_dt else ""
    decision = agent.run(attendee_name, company, thread, latest_reply, slots, now_label,
                         config.TIMEZONE, channel=channel, known_email=known_email,
                         pending_slot_label=pending_label, existing_booking_label=existing_label)

    base = {"booked": False, "slot": None, "join_url": "", "pending_slot_iso": None,
            "attendee_email": "", "event_id": "", "cancelled": False}

    # CANCEL — drop the existing booking, no new time.
    if decision.action == SchedulingAction.CANCEL:
        if existing_event_id and not dry_run:
            provider.cancel_event(existing_event_id)
        logger.info("Cancelled booking %s for %s", existing_event_id or "(none)", attendee_name)
        return {**base, "action": "cancel", "reply": decision.reply_text, "cancelled": True}

    # CONFIRM_EMAIL (LinkedIn) — hold the agreed slot, ask about the email/Meet link.
    if decision.action == SchedulingAction.CONFIRM_EMAIL and decision.chosen_slot_start:
        slot = _match_slot(decision.chosen_slot_start, slots)
        if slot is not None:
            return {**base, "action": "confirm_email", "reply": decision.reply_text,
                    "pending_slot_iso": slot.iso()}
        return {**base, "action": "negotiate",
                "reply": _propose_text(slots, tz, "That time just filled — here are the closest openings:")}

    # BOOK — only a genuinely free slot (or the held pending slot).
    if decision.action == SchedulingAction.BOOK:
        slot = pending_slot or _match_slot(decision.chosen_slot_start, slots)
        if slot is not None:
            invite_email = "" if decision.meet_link_only else (decision.attendee_email or
                           (known_email if channel == "email" else ""))
            if dry_run:
                return {**base, "action": "book", "reply": decision.reply_text, "booked": True,
                        "slot": slot, "join_url": "https://meet.example/dry",
                        "attendee_email": invite_email, "event_id": existing_event_id or "dry-evt"}
            req = BookingRequest(
                attendee_name=attendee_name, attendee_email=invite_email, slot=slot,
                title=config.MEETING_TITLE.format(company=company or "your team"),
                description=config.MEETING_DESCRIPTION)
            if existing_event_id:
                # RESCHEDULE: move the SAME event (one "updated" invite, not
                # cancel + brand-new). Fall back to cancel+rebook if unsupported.
                res = provider.update_event(existing_event_id, req)
                if not res.ok:
                    res = provider.create_event(req)
                    if res.ok:
                        provider.cancel_event(existing_event_id)
                else:
                    logger.info("Rescheduled event %s → %s", existing_event_id, slot.iso())
            else:
                res = provider.create_event(req)
            if res.ok:
                reply = decision.reply_text
                if res.join_url and (decision.meet_link_only or not invite_email):
                    reply = f"{reply}\n\nHere's the link: {res.join_url}"
                logger.info("Booked %s for %s (invite=%s)", slot.iso(), attendee_name, invite_email or "meet-only")
                return {**base, "action": "book", "reply": reply, "booked": True,
                        "slot": slot, "join_url": res.join_url, "attendee_email": invite_email,
                        "event_id": res.event_id}
            logger.warning("Booking failed (%s) — proposing instead.", res.error)
        return {**base, "action": "negotiate",
                "reply": _propose_text(slots, tz, "That time just got taken — here are the closest openings:")}

    # PROPOSE / NEGOTIATE / ASK / DECLINE — send the agent's reply as-is.
    return {**base, "action": decision.action.value, "reply": decision.reply_text}
