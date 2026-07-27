"""Scheduling configuration (shared by Inbox + Connect).

The meeting-booking layer: check a calendar's free/busy, propose real open
slots, and book once the client confirms — negotiating to a common time. The
calendar backend is swappable via ``PULSE_CALENDAR_PROVIDER``:

  * ``mock``   — in-memory calendar; zero setup, used for tests + dry demos.
  * ``google`` — real Google Calendar (free): freebusy + event insert + Meet link.
"""

from __future__ import annotations

import os

from modules.common import control

# Provider selection + meeting shape/window come from the central control panel
# (control.CALENDAR_PROVIDER is forced to "mock" whenever the engine isn't LIVE).
PROVIDER = control.CALENDAR_PROVIDER

# --- Google Calendar (real backend) credentials — endpoints/creds stay here ---
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary").strip()
GOOGLE_OAUTH_CLIENT_FILE = os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "").strip()
GOOGLE_OAUTH_TOKEN_FILE = os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "").strip()

# ---------------------------------------------------------------------------
# Meeting shape + availability window (all controlled from control.py)
# ---------------------------------------------------------------------------
MEETING_DURATION_MIN = control.MEETING_DURATION_MIN
MEETING_TITLE = control.MEETING_TITLE
MEETING_DESCRIPTION = control.MEETING_DESCRIPTION
MEETING_ADD_CONFERENCE = control.MEETING_ADD_CONFERENCE

TIMEZONE = control.MEETING_TIMEZONE
WORK_START_HOUR = control.MEETING_WORK_START_HOUR
WORK_END_HOUR = control.MEETING_WORK_END_HOUR
WORK_WEEKDAYS = control.MEETING_WORK_WEEKDAYS
SLOT_GRANULARITY_MIN = control.MEETING_SLOT_GRANULARITY_MIN
MIN_LEAD_HOURS = control.MEETING_MIN_LEAD_HOURS
LOOKAHEAD_DAYS = control.MEETING_LOOKAHEAD_DAYS
SLOTS_TO_OFFER = control.MEETING_SLOTS_TO_OFFER

# LLM tier — talking to real prospects about times → strong model.
SCHEDULER_LLM = control.HIGH_EFFORT_LLM
