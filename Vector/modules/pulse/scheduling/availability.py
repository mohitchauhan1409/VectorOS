"""Availability — turn a calendar's free/busy into concrete bookable slots.

Deterministic (no LLM): generates candidate slots on the configured granularity
within working hours/weekdays over the lookahead window, drops any that overlap
a busy interval or fall inside the lead-time buffer, and returns them in the
host's timezone. The SchedulingAgent then reasons over these real openings.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from modules.pulse.scheduling import config
from modules.pulse.scheduling.schemas import BusyInterval, TimeSlot


def _tz():
    try:
        return ZoneInfo(config.TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def _overlaps(start: datetime, end: datetime, busy: list[BusyInterval]) -> bool:
    return any(b.end > start and b.start < end for b in busy)


def free_slots(now: datetime, provider=None, limit: int | None = None) -> list[TimeSlot]:
    """Return open slots (host tz) between the lead-time buffer and lookahead."""
    if provider is None:
        from modules.pulse.scheduling.providers import get_calendar_provider
        provider = get_calendar_provider()

    tz = _tz()
    now = now.astimezone(timezone.utc)
    window_start = now + timedelta(hours=config.MIN_LEAD_HOURS)
    window_end = now + timedelta(days=config.LOOKAHEAD_DAYS)
    busy = provider.free_busy(window_start, window_end)

    duration = timedelta(minutes=config.MEETING_DURATION_MIN)
    step = config.SLOT_GRANULARITY_MIN
    slots: list[TimeSlot] = []

    day = window_start.astimezone(tz).date()
    last_day = window_end.astimezone(tz).date()
    while day <= last_day:
        if day.weekday() in config.WORK_WEEKDAYS:
            minute = config.WORK_START_HOUR * 60
            end_minute = config.WORK_END_HOUR * 60
            while minute + config.MEETING_DURATION_MIN <= end_minute:
                start = datetime(day.year, day.month, day.day,
                                 minute // 60, minute % 60, tzinfo=tz)
                start_utc = start.astimezone(timezone.utc)
                end_utc = start_utc + duration
                if (window_start <= start_utc and end_utc <= window_end
                        and not _overlaps(start_utc, end_utc, busy)):
                    slots.append(TimeSlot(start=start, end=start + duration))
                minute += step
        day += timedelta(days=1)

    slots.sort(key=lambda s: s.start)
    return slots[:limit] if limit else slots
