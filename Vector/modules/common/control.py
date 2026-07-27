"""Vector — single control panel for the whole engine.

Every behavioural knob and on/off switch across all modules lives HERE, grouped
by module. Module `config.py` files import their values from this file (keeping
their existing names), so this is the one place to tune or toggle the engine.

Rules:
  * Env-var names and defaults are unchanged from the old per-module configs, so
    switching this in changes nothing about behaviour — only WHERE it's decided.
  * The master safety switch (`PULSE_LIVE`) is baked in: when off, outreach
    providers are forced to mock/dry no matter what else is set.
  * Big *content* (news sources, ICP profile, sequence copy, provider endpoints,
    credentials) stays in its module — this file is for CONTROLS, not content.
"""

from __future__ import annotations

import os

from modules.common.config import get_settings

_settings = get_settings()  # ensures .env is loaded


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# ═══════════════════════════════════════════════════════════════════════════
# 0 · MASTER SAFETY SWITCH
# ═══════════════════════════════════════════════════════════════════════════
# The ONE switch that decides whether the engine may touch the outside world
# with outreach. OFF (default) = safe: email is dry-run, LinkedIn + calendar use
# in-memory mock providers. Set VECTOR_PULSE_LIVE=1 to actually send.
PULSE_LIVE: bool = _flag("VECTOR_PULSE_LIVE", False)

# Effective outreach providers — forced to mock unless we're live.
CONNECT_PROVIDER: str = (
    os.getenv("PULSE_CONNECT_PROVIDER", "mock").strip().lower() if PULSE_LIVE else "mock"
)
CALENDAR_PROVIDER: str = (
    os.getenv("PULSE_CALENDAR_PROVIDER", "mock").strip().lower() if PULSE_LIVE else "mock"
)
# Email has no mock transport; the safe path is dry-run (no SMTP/IMAP sockets).
EMAIL_DRY_RUN: bool = not PULSE_LIVE


def mode_label() -> str:
    return "LIVE" if PULSE_LIVE else "SAFE (dry-run email · mock LinkedIn · mock calendar)"


# ═══════════════════════════════════════════════════════════════════════════
# 1 · LLM TIERS  (switch models for the whole engine here)
# ═══════════════════════════════════════════════════════════════════════════
DEFAULT_LLM_PROVIDER: str = _settings.default_llm_provider
NORMAL_LLM: dict = {"provider": "claude", "model": "claude-haiku-4-5-20251001"}
HIGH_EFFORT_LLM: dict = {"provider": "claude", "model": "claude-opus-4-8"}


# ═══════════════════════════════════════════════════════════════════════════
# 2 · SCOUT · RADAR
# ═══════════════════════════════════════════════════════════════════════════
RADAR_MAX_PAGES: int = 20                 # default pages per source (sources may override)
RADAR_MIN_ICP_SCORE: int = 35             # persist/qualify leads at/above this (0 = keep all)
RADAR_MAX_HTML_CHARS_FOR_SELECTOR: int = 18_000
# Gap between page fetches against the same source. Several payments outlets
# return 403 when hit back-to-back, so this keeps the scan working, not just polite.
RADAR_FETCH_DELAY_SECONDS: float = float(os.getenv("VECTOR_RADAR_FETCH_DELAY", "2.0"))


# ═══════════════════════════════════════════════════════════════════════════
# 3 · SCOUT · DETECTIVE
# ═══════════════════════════════════════════════════════════════════════════
# Konfyd sells into the risk, credit and treasury side of a payment processor —
# not engineering, and not commercial. Ordered highest-priority first.
DETECTIVE_TARGET_ROLES: tuple[str, ...] = (
    "Chief Risk Officer",
    "Chief Credit Officer",
    "Head of Merchant Risk",
    "VP Merchant Underwriting",
    "Head of Treasury",
    "Chief Financial Officer",
    "Head of Portfolio Risk",
    "Head of Merchant Acquiring",
)

# At a payment processor, "Chief Risk Officer" very often means FRAUD and AML,
# not merchant credit. Those people cannot buy risk transfer and will not reply,
# so the profile agent requires evidence of credit/merchant scope and rejects
# financial-crime scope unless it appears alongside it.
DETECTIVE_ROLE_MUST_MATCH: tuple[str, ...] = (
    "merchant", "credit", "underwriting", "portfolio", "settlement",
    "counterparty", "treasury", "capital",
)
DETECTIVE_ROLE_EXCLUDE: tuple[str, ...] = (
    "fraud", "aml", "anti-money", "financial crime", "kyc", "sanctions",
    "compliance", "infosec", "information security",
)
DETECTIVE_MAX_DECISION_MAKERS_PER_COMPANY: int = 3
DETECTIVE_RESULTS_PER_ROLE: int = 5

# Email finding ------------------------------------------------------------
# Primary provider: "pdl" | "apollo" | "none" (go straight to keyless fallback).
# Apollo & PDL are fully built; they consume API credits, so default is "none".
EMAIL_PROVIDER: str = os.getenv("VECTOR_EMAIL_PROVIDER", "none").strip().lower()
EMAIL_PATTERN_FALLBACK: bool = _flag("VECTOR_EMAIL_PATTERN_FALLBACK", True)
EMAIL_SMTP_VERIFY: bool = _flag("VECTOR_EMAIL_SMTP_VERIFY", True)
EMAIL_SMTP_TIMEOUT: float = float(os.getenv("VECTOR_EMAIL_SMTP_TIMEOUT", "10.0"))
EMAIL_SMTP_PROBE_FROM: str = os.getenv("VECTOR_EMAIL_SMTP_PROBE_FROM", "verify@example.com")
EMAIL_WEB_INFERENCE: bool = _flag("VECTOR_EMAIL_WEB_INFERENCE", True)
EMAIL_GRAVATAR_CHECK: bool = _flag("VECTOR_EMAIL_GRAVATAR_CHECK", True)
EMAIL_INFERENCE_GRAVATAR_MAX_CHECKS: int = 6
PDL_MIN_LIKELIHOOD: int = 4
APOLLO_MAX_BATCH: int = 10
APOLLO_REVEAL_PERSONAL_EMAILS: bool = _flag("VECTOR_APOLLO_REVEAL_PERSONAL_EMAILS", False)
APOLLO_REVEAL_PHONE_NUMBER: bool = _flag("VECTOR_APOLLO_REVEAL_PHONE_NUMBER", False)


# ═══════════════════════════════════════════════════════════════════════════
# 4 · PULSE · EMAIL (Inbox)
# ═══════════════════════════════════════════════════════════════════════════
# Throttle + warmup (deliverability)
EMAIL_MIN_SEND_DELAY_SECONDS: int = 45
EMAIL_MAX_SEND_DELAY_SECONDS: int = 180
EMAIL_DEFAULT_DAILY_CAP: int = 40
EMAIL_WARMUP_ENABLED: bool = _flag("VECTOR_EMAIL_WARMUP_ENABLED", True)
EMAIL_WARMUP_START: int = _int("VECTOR_EMAIL_WARMUP_START", 10)      # day-1 allowance
EMAIL_WARMUP_INCREMENT: int = _int("VECTOR_EMAIL_WARMUP_INCREMENT", 5)  # +/day up to cap

# Send window (only send in business hours, weekdays)
EMAIL_SEND_WINDOW_START_HOUR: int = _int("VECTOR_EMAIL_WINDOW_START", 8)
EMAIL_SEND_WINDOW_END_HOUR: int = _int("VECTOR_EMAIL_WINDOW_END", 18)
EMAIL_SEND_WEEKDAYS: tuple[int, ...] = (0, 1, 2, 3, 4)
SEND_TIMEZONE: str = os.getenv("PULSE_TIMEZONE", "UTC")

# Who is safe to email
SENDABLE_EMAIL_STATUSES: tuple[str, ...] = ("verified",)
ALLOW_GUESSED_EMAILS: bool = _flag("VECTOR_ALLOW_GUESSED_EMAILS", False)

# A/B bandit (Thompson sampling)
EMAIL_VARIANTS_PER_STEP: int = 3
BANDIT_PRIOR_ALPHA: float = 1.0
BANDIT_PRIOR_BETA: float = 1.0
EMAIL_MIN_SENDS_BEFORE_PROMOTION: int = 30
EMAIL_WINNER_CONFIDENCE: float = 0.95

# IMAP reply polling
IMAP_LOOKBACK_DAYS: int = _int("PULSE_IMAP_LOOKBACK_DAYS", 1)
IMAP_MAILBOX_FOLDER: str = "INBOX"

# Autopilot + experiments
EMAIL_AUTOPILOT_INTERVAL: int = _int("PULSE_AUTOPILOT_INTERVAL", 3600)
EXPERIMENT_SIZE: int = 4
CAMPAIGN_ALLOCATION_WEIGHTS: tuple[int, ...] = (4, 2, 1, 1)
EXPERIMENT_MIN_SENDS_FOR_RANKING: int = 20
WEEKLY_SYNC_DAYS: int = 7
RETIRE_MIN_SENDS: int = 40
RETIRE_SCORE_GAP: float = 0.5


# ═══════════════════════════════════════════════════════════════════════════
# 5 · PULSE · LINKEDIN (Connect)
# ═══════════════════════════════════════════════════════════════════════════
CONNECT_FROM_NAME: str = os.getenv("PULSE_CONNECT_FROM_NAME", "").strip()
# Caps + warmup (LinkedIn is stricter than email)
LINKEDIN_WEEKLY_INVITE_CAP: int = 100
LINKEDIN_DAILY_INVITE_CAP: int = 20
LINKEDIN_WARMUP_ENABLED: bool = _flag("VECTOR_LINKEDIN_WARMUP_ENABLED", True)
LINKEDIN_WARMUP_START: int = _int("VECTOR_LINKEDIN_WARMUP_START", 5)
LINKEDIN_WARMUP_INCREMENT: int = _int("VECTOR_LINKEDIN_WARMUP_INCREMENT", 3)
LINKEDIN_DAILY_MESSAGE_CAP: int = 40
LINKEDIN_MIN_ACTION_DELAY_SECONDS: int = _int("PULSE_CONNECT_MIN_DELAY", 60)
LINKEDIN_MAX_ACTION_DELAY_SECONDS: int = _int("PULSE_CONNECT_MAX_DELAY", 300)
LINKEDIN_SEND_WINDOW_START_HOUR: int = _int("PULSE_CONNECT_WINDOW_START", 8)
LINKEDIN_SEND_WINDOW_END_HOUR: int = _int("PULSE_CONNECT_WINDOW_END", 18)
LINKEDIN_SEND_WEEKDAYS: tuple[int, ...] = (0, 1, 2, 3, 4)
LINKEDIN_INVITE_EXPIRY_DAYS: int = 21
# A/B bandit
LINKEDIN_VARIANTS_PER_STEP: int = 2
LINKEDIN_MIN_SENDS_BEFORE_PROMOTION: int = 20
LINKEDIN_WINNER_CONFIDENCE: float = 0.95
# Reply polling + autopilot
LINKEDIN_REPLY_LOOKBACK_DAYS: int = _int("PULSE_CONNECT_LOOKBACK_DAYS", 3)
LINKEDIN_AUTOPILOT_INTERVAL: int = _int("PULSE_CONNECT_INTERVAL", 3600)


# ═══════════════════════════════════════════════════════════════════════════
# 6 · PULSE · CONVERSATION  (shared by email + LinkedIn reply handling)
# ═══════════════════════════════════════════════════════════════════════════
# Master auto-reply switch. When OFF, replies are still fetched + classified and
# the sequence stops, but NO auto-reply is sent (a draft is stored for review).
AUTO_REPLY_ENABLED: bool = _flag("PULSE_AUTO_REPLY", False)
MAX_AUTO_REPLIES: int = 4                 # per-thread cap before escalating to a human
CONVERSATION_MIN_CONFIDENCE: float = 0.6  # below this, escalate instead of auto-send
MEETING_LINK: str = os.getenv("PULSE_MEETING_LINK", "").strip()


# ═══════════════════════════════════════════════════════════════════════════
# 7 · PULSE · SCHEDULING (meeting booking)
# ═══════════════════════════════════════════════════════════════════════════
MEETING_DURATION_MIN: int = _int("PULSE_MEETING_DURATION_MIN", 30)
MEETING_TITLE: str = os.getenv("PULSE_MEETING_TITLE", "Intro call — {company}")
MEETING_DESCRIPTION: str = os.getenv(
    "PULSE_MEETING_DESCRIPTION", "Quick intro call to explore fit. Booked automatically by Pulse.")
MEETING_ADD_CONFERENCE: bool = _flag("VECTOR_MEETING_ADD_CONFERENCE", True)
MEETING_TIMEZONE: str = os.getenv("PULSE_MEETING_TIMEZONE", os.getenv("PULSE_TIMEZONE", "UTC"))
MEETING_WORK_START_HOUR: int = _int("PULSE_MEETING_START_HOUR", 9)
MEETING_WORK_END_HOUR: int = _int("PULSE_MEETING_END_HOUR", 17)
MEETING_WORK_WEEKDAYS: tuple[int, ...] = (0, 1, 2, 3, 4)
MEETING_SLOT_GRANULARITY_MIN: int = _int("PULSE_SLOT_GRANULARITY_MIN", 30)
MEETING_MIN_LEAD_HOURS: int = _int("PULSE_MEETING_MIN_LEAD_HOURS", 12)
MEETING_LOOKAHEAD_DAYS: int = _int("PULSE_MEETING_LOOKAHEAD_DAYS", 10)
MEETING_SLOTS_TO_OFFER: int = _int("PULSE_SLOTS_TO_OFFER", 3)


def summary() -> dict:
    """Compact view of the on/off + provider switches (for CLI/health/debug)."""
    return {
        "mode": mode_label(),
        "pulse_live": PULSE_LIVE,
        "connect_provider": CONNECT_PROVIDER,
        "calendar_provider": CALENDAR_PROVIDER,
        "email_dry_run": EMAIL_DRY_RUN,
        "email_provider": EMAIL_PROVIDER,
        "email_pattern_fallback": EMAIL_PATTERN_FALLBACK,
        "email_warmup_enabled": EMAIL_WARMUP_ENABLED,
        "linkedin_warmup_enabled": LINKEDIN_WARMUP_ENABLED,
        "auto_reply_enabled": AUTO_REPLY_ENABLED,
        "allow_guessed_emails": ALLOW_GUESSED_EMAILS,
    }
