"""CalendarProvider — the calendar interface every backend implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from modules.pulse.scheduling.schemas import BookingRequest, BookingResult, BusyInterval


class CalendarProvider(ABC):
    name: str = "base"

    @abstractmethod
    def free_busy(self, start: datetime, end: datetime) -> list[BusyInterval]:
        """Return the host's busy intervals within [start, end)."""

    @abstractmethod
    def create_event(self, request: BookingRequest) -> BookingResult:
        """Book a meeting on the host's calendar (optionally with a video link)."""

    def cancel_event(self, event_id: str) -> bool:
        """Cancel a previously-booked event. Default: unsupported → False."""
        return False

    def update_event(self, event_id: str, request: BookingRequest) -> BookingResult:
        """Move an existing event to a new time (reschedule) — keeps the same
        event + invite, just changes the time. Default: unsupported → not ok,
        so the caller can fall back to cancel + rebook."""
        return BookingResult(ok=False, error="update not supported")

    def health_check(self) -> tuple[bool, str]:
        return True, "ok"
