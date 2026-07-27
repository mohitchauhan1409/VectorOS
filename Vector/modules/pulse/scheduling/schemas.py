"""Data models for scheduling."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class BusyInterval(BaseModel):
    """A busy block on the host's calendar."""

    start: datetime
    end: datetime


class TimeSlot(BaseModel):
    """A bookable opening (start + end, timezone-aware)."""

    start: datetime
    end: datetime

    def label(self, tz=None) -> str:
        """Human label like 'Tue Jul 22, 3:00 PM'."""
        dt = self.start.astimezone(tz) if tz else self.start
        return dt.strftime("%a %b %-d, %-I:%M %p")

    def iso(self) -> str:
        return self.start.isoformat()


class BookingRequest(BaseModel):
    attendee_name: str = ""
    attendee_email: str = ""
    slot: TimeSlot
    title: str = "Intro call"
    description: str = ""


class BookingResult(BaseModel):
    ok: bool = False
    event_id: str = ""
    join_url: str = ""
    error: str = ""


class SchedulingAction(str, Enum):
    PROPOSE = "propose"        # offer open slots
    BOOK = "book"              # client confirmed a time we can honor → book now
    CONFIRM_EMAIL = "confirm_email"  # time agreed (LinkedIn) → confirm/collect email 1st
    NEGOTIATE = "negotiate"    # their time is taken → counter with alternatives
    ASK = "ask"                # ask for their availability
    CANCEL = "cancel"          # they want to cancel the booked meeting entirely
    DECLINE = "decline"        # they no longer want to meet → stop scheduling


class SchedulingDecision(BaseModel):
    """Structured output of the SchedulingAgent."""

    action: SchedulingAction
    chosen_slot_start: str | None = Field(
        default=None,
        description="ISO start of the slot to BOOK/confirm (must be one of the free slots).")
    attendee_email: str = Field(
        default="",
        description="Email to send the calendar invite to (confirmed/provided by client). "
                    "Empty means book with a Meet link only (no invite email).")
    meet_link_only: bool = Field(
        default=False,
        description="True if the client wants just a Meet link (no email invite).")
    reply_text: str = Field(description="The message to send the client.")
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reasoning: str = ""
