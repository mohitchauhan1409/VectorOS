"""MockCalendarProvider — an in-memory calendar for tests + dry demos.

Holds busy intervals a test can set, and records booked events (which also
become busy, so double-booking is impossible). Zero setup, zero cost.
"""

from __future__ import annotations

from datetime import datetime

from modules.common.logger import get_logger
from modules.pulse.scheduling.schemas import BookingRequest, BookingResult, BusyInterval

logger = get_logger("pulse.scheduling.mock")


class MockCalendarProvider:
    name = "mock"

    def __init__(self) -> None:
        self._busy: list[BusyInterval] = []
        self._events: list[BookingRequest] = []
        self._counter = 0
        self._by_id: dict[str, BusyInterval] = {}   # event_id → its busy block

    # -- test controls ------------------------------------------------------
    def add_busy(self, start: datetime, end: datetime) -> None:
        self._busy.append(BusyInterval(start=start, end=end))

    @property
    def events(self) -> list[BookingRequest]:
        return self._events

    # -- provider interface -------------------------------------------------
    def health_check(self) -> tuple[bool, str]:
        return True, "mock calendar (simulated)"

    def free_busy(self, start: datetime, end: datetime) -> list[BusyInterval]:
        return [b for b in self._busy if b.end > start and b.start < end]

    def create_event(self, request: BookingRequest) -> BookingResult:
        # Refuse to double-book (a booked slot is now busy).
        for b in self._busy:
            if b.end > request.slot.start and b.start < request.slot.end:
                return BookingResult(ok=False, error="slot no longer free")
        busy = BusyInterval(start=request.slot.start, end=request.slot.end)
        self._busy.append(busy)
        self._events.append(request)
        self._counter += 1
        event_id = f"mock-evt-{self._counter}"
        self._by_id[event_id] = busy
        logger.info("[mock] booked %s for %s (%s)", request.slot.iso(), request.attendee_name, event_id)
        return BookingResult(ok=True, event_id=event_id, join_url="https://meet.example/mock")

    def cancel_event(self, event_id: str) -> bool:
        busy = self._by_id.pop(event_id, None)
        if busy is None:
            return False
        self._busy = [b for b in self._busy if b is not busy]
        logger.info("[mock] cancelled %s", event_id)
        return True

    def update_event(self, event_id: str, request: BookingRequest) -> BookingResult:
        old = self._by_id.get(event_id)
        if old is None:
            return BookingResult(ok=False, error="no such event")
        self._busy = [b for b in self._busy if b is not old]
        new = BusyInterval(start=request.slot.start, end=request.slot.end)
        self._busy.append(new)
        self._by_id[event_id] = new
        logger.info("[mock] moved %s → %s", event_id, request.slot.iso())
        return BookingResult(ok=True, event_id=event_id, join_url="https://meet.example/mock")
