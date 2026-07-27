"""PULSE · Scheduling — calendar-aware meeting booking, shared by Inbox + Connect."""

from modules.pulse.scheduling.availability import free_slots
from modules.pulse.scheduling.flow import handle_scheduling
from modules.pulse.scheduling.providers import get_calendar_provider

__all__ = ["free_slots", "get_calendar_provider", "handle_scheduling"]
