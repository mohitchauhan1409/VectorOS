"""Connect configuration (PULSE module).

Connect is the LinkedIn sibling of Inbox: it sends connection requests, runs
message sequences once accepted, tracks acceptances + replies, and converts
leads — the same "brain" as Inbox, with a swappable transport for the risky
LinkedIn part.

Transport is chosen by ``PULSE_CONNECT_PROVIDER``:
  * ``mock``          — default; simulates LinkedIn (zero cost, zero ban risk).
                        Used to build + test the whole module safely.
  * ``phantombuster`` — real sending via PhantomBuster's cloud API (free tier
                        has API access + ~30 min/mo execution — enough for demos).
  * ``unipile``       — real sending via Unipile's unified messaging API (7-day
                        free trial, no card). Cleanest fit: native LinkedIn
                        invite / accepted-detection / messaging endpoints.

We never run raw cookie/Voyager automation ourselves; the provider carries that
risk. Our scheduler still enforces the conservative safety playbook (weekly +
daily invite caps, warmup ramp, working-hours window, human-like jitter) no
matter which backend is active.
"""

from __future__ import annotations

import os

from modules.common import control
from modules.common.config import DATA_DIR, get_settings

get_settings()  # ensure .env is loaded

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
PULSE_DIR = DATA_DIR / "pulse"
DB_PATH = PULSE_DIR / "connect.db"

# ---------------------------------------------------------------------------
# Provider selection — from the control panel (forced to "mock" unless LIVE).
# ---------------------------------------------------------------------------
PROVIDER = control.CONNECT_PROVIDER

# Display name of the human whose LinkedIn account is sending.
CONNECT_FROM_NAME = control.CONNECT_FROM_NAME

# --- PhantomBuster (real backend) ---
# API key from account settings; the phantom "agent" IDs are created once in the
# PhantomBuster UI (each phantom is pre-wired with your LinkedIn session cookie).
PB_API_KEY = os.getenv("PHANTOMBUSTER_API_KEY", "").strip()
PB_BASE_URL = os.getenv("PHANTOMBUSTER_BASE_URL", "https://api.phantombuster.com/api/v2").strip()
PB_SESSION_COOKIE = os.getenv("PHANTOMBUSTER_LI_AT", "").strip()   # LinkedIn li_at cookie
PB_USER_AGENT = os.getenv("PHANTOMBUSTER_USER_AGENT", "").strip()
# Agent (phantom) ids for each action:
PB_CONNECT_AGENT_ID = os.getenv("PB_CONNECT_AGENT_ID", "").strip()   # LinkedIn Auto Connect
PB_MESSAGE_AGENT_ID = os.getenv("PB_MESSAGE_AGENT_ID", "").strip()   # LinkedIn Message Sender
PB_PROFILE_AGENT_ID = os.getenv("PB_PROFILE_AGENT_ID", "").strip()   # Profile Scraper (degree)
PB_INBOX_AGENT_ID = os.getenv("PB_INBOX_AGENT_ID", "").strip()       # Message/Inbox extractor
PB_LAUNCH_TIMEOUT = float(os.getenv("PB_LAUNCH_TIMEOUT", "180"))     # secs to await a container

# --- Unipile (real backend, unified messaging API) ---
# DSN is the per-tenant host+port shown in your Unipile dashboard, e.g.
# "api8.unipile.com:13443". API key + the connected LinkedIn account id also
# come from the dashboard (connect the account once via the Hosted Auth wizard).
UNIPILE_DSN = os.getenv("UNIPILE_DSN", "").strip()
UNIPILE_API_KEY = os.getenv("UNIPILE_API_KEY", "").strip()
UNIPILE_ACCOUNT_ID = os.getenv("UNIPILE_ACCOUNT_ID", "").strip()

# ---------------------------------------------------------------------------
# Safety playbook — caps, warmup, window  (LinkedIn is far stricter than email)
# ---------------------------------------------------------------------------
# The reliably-supported hard limit is the WEEKLY connection-invite cap
# (~100-200/week, account-dependent). We stay conservatively under it.
WEEKLY_INVITE_CAP = control.LINKEDIN_WEEKLY_INVITE_CAP
DAILY_INVITE_CAP = control.LINKEDIN_DAILY_INVITE_CAP
# Warmup ramp for a fresh account (invites/day), climbing to DAILY_INVITE_CAP.
WARMUP_ENABLED = control.LINKEDIN_WARMUP_ENABLED
WARMUP_START = control.LINKEDIN_WARMUP_START
WARMUP_INCREMENT = control.LINKEDIN_WARMUP_INCREMENT
# Messages to existing connections are safer but still capped.
DAILY_MESSAGE_CAP = control.LINKEDIN_DAILY_MESSAGE_CAP

# Human-like gap between two actions from the same account (seconds).
MIN_ACTION_DELAY_SECONDS = control.LINKEDIN_MIN_ACTION_DELAY_SECONDS
MAX_ACTION_DELAY_SECONDS = control.LINKEDIN_MAX_ACTION_DELAY_SECONDS

# Working-hours window (local), weekdays only.
SEND_WINDOW_START_HOUR = control.LINKEDIN_SEND_WINDOW_START_HOUR
SEND_WINDOW_END_HOUR = control.LINKEDIN_SEND_WINDOW_END_HOUR
SEND_WEEKDAYS = control.LINKEDIN_SEND_WEEKDAYS
SEND_TIMEZONE = control.SEND_TIMEZONE

# Give up waiting for an invite to be accepted after this many days.
INVITE_EXPIRY_DAYS = control.LINKEDIN_INVITE_EXPIRY_DAYS

# ---------------------------------------------------------------------------
# Sequence  (invite → [acceptance gate] → messages)
# ---------------------------------------------------------------------------
# kind "invite" sends a connection request (optional note ≤300 chars). kind
# "message" only fires AFTER the invite is accepted. wait_days is measured from
# the previous step (for the first message, from the acceptance time).
DEFAULT_SEQUENCE: tuple[dict, ...] = (
    {"name": "Connection request", "kind": "invite", "wait_days": 0,
     "angle": "signal-led, peer-to-peer, credible reason to connect — reference the "
              "specific payments event, no pitch (fits in 300 chars)"},
    {"name": "Intro message", "kind": "message", "wait_days": 0,
     "angle": "thank for connecting, then one soft diagnostic question about how "
              "they handle merchant reserves / insolvency exposure today"},
    {"name": "Value nudge", "kind": "message", "wait_days": 3,
     "angle": "one concrete number — capital released or losses caught early — "
              "then a low-friction ask"},
    {"name": "Breakup", "kind": "message", "wait_days": 4,
     "angle": "polite last touch, easy to say no"},
)

# ---------------------------------------------------------------------------
# Autonomous conversation (reuses Inbox's switches so behavior is consistent)
# ---------------------------------------------------------------------------
AUTO_REPLY_ENABLED = control.AUTO_REPLY_ENABLED
MAX_AUTO_REPLIES = control.MAX_AUTO_REPLIES
CONVERSATION_MIN_CONFIDENCE = control.CONVERSATION_MIN_CONFIDENCE
MEETING_LINK = control.MEETING_LINK

# ---------------------------------------------------------------------------
# A/B bandit (per-step note/message variants) — same model as Inbox
# ---------------------------------------------------------------------------
VARIANTS_PER_STEP = control.LINKEDIN_VARIANTS_PER_STEP
BANDIT_PRIOR_ALPHA = control.BANDIT_PRIOR_ALPHA
BANDIT_PRIOR_BETA = control.BANDIT_PRIOR_BETA
MIN_SENDS_BEFORE_PROMOTION = control.LINKEDIN_MIN_SENDS_BEFORE_PROMOTION
WINNER_CONFIDENCE = control.LINKEDIN_WINNER_CONFIDENCE

# ---------------------------------------------------------------------------
# Reply polling / autopilot
# ---------------------------------------------------------------------------
REPLY_LOOKBACK_DAYS = control.LINKEDIN_REPLY_LOOKBACK_DAYS
AUTOPILOT_INTERVAL = control.LINKEDIN_AUTOPILOT_INTERVAL

# ---------------------------------------------------------------------------
# LLM tiers (from the central control panel)
# ---------------------------------------------------------------------------
HIGH_EFFORT_LLM = control.HIGH_EFFORT_LLM
NORMAL_LLM = control.NORMAL_LLM

NOTE_LLM = NORMAL_LLM            # short connection note — cheap tier is plenty
MESSAGE_LLM = HIGH_EFFORT_LLM    # actual messages to prospects — quality-critical
CLASSIFIER_LLM = NORMAL_LLM
CONVERSATION_LLM = HIGH_EFFORT_LLM
