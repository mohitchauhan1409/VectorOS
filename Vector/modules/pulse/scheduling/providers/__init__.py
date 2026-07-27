"""Calendar providers — swappable free/busy + event booking backends."""

from __future__ import annotations

from modules.pulse.scheduling import config
from modules.pulse.scheduling.providers.base import CalendarProvider
from modules.pulse.scheduling.providers.mock import MockCalendarProvider

__all__ = ["CalendarProvider", "MockCalendarProvider", "get_calendar_provider"]

_instance: CalendarProvider | None = None


def get_calendar_provider(name: str | None = None) -> CalendarProvider:
    global _instance
    choice = (name or config.PROVIDER or "mock").lower()
    if _instance is not None and _instance.name == choice:
        return _instance
    if choice == "google":
        from modules.pulse.scheduling.providers.google import GoogleCalendarProvider
        _instance = GoogleCalendarProvider()
    else:
        _instance = MockCalendarProvider()
    return _instance
