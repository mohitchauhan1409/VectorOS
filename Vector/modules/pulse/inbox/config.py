"""Inbox configuration (PULSE module).

Single source of truth for how Inbox sends: mailbox pool, sending throttle +
warmup, send windows, which emails are safe to contact, the default outreach
sequence, and A/B (bandit) settings.

Nothing here is paid. Sending is plain SMTP (``smtplib``) and reply-reading is
plain IMAP (``imaplib``) — both Python stdlib — so any mailbox with an app
password (Gmail/Workspace, Zoho, Fastmail, a custom domain, …) works.

Credentials never live in this file. They come from the environment, loaded by
``modules.common.config`` (which runs ``load_dotenv``). Two ways to configure:

  1. Single mailbox — the ``PULSE_*`` vars below.
  2. A pool — ``PULSE_MAILBOXES`` as a JSON array of mailbox objects.

See ``.env.example`` for the exact keys.
"""

from __future__ import annotations

import json
import os

from modules.common import control
from modules.common.config import DATA_DIR, get_settings

# Ensure .env is loaded (importing common.config runs load_dotenv). We read a
# few Pulse-specific vars directly with os.getenv since they don't belong in the
# shared Settings object.
get_settings()

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
# Scout keeps leads as JSON documents; outreach is relational + stateful
# (status transitions, "who's awaiting a reply", per-variant reply rates), so
# Inbox uses a local SQLite DB. Zero dependencies, zero cost. Scout is untouched.
PULSE_DIR = DATA_DIR / "pulse"
DB_PATH = PULSE_DIR / "inbox.db"

# ---------------------------------------------------------------------------
# Sending throttle & warmup  (this is where "free" deliverability is earned)
# ---------------------------------------------------------------------------
# All controlling knobs come from the central control panel (control.py).
MIN_SEND_DELAY_SECONDS = control.EMAIL_MIN_SEND_DELAY_SECONDS
MAX_SEND_DELAY_SECONDS = control.EMAIL_MAX_SEND_DELAY_SECONDS
DEFAULT_DAILY_CAP = control.EMAIL_DEFAULT_DAILY_CAP

# Warmup: fresh mailbox starts low and ramps to the cap. (10 then +5/day.)
WARMUP_ENABLED = control.EMAIL_WARMUP_ENABLED
WARMUP_START = control.EMAIL_WARMUP_START
WARMUP_INCREMENT = control.EMAIL_WARMUP_INCREMENT

# ---------------------------------------------------------------------------
# Send window  (only send during business hours, on weekdays)
# ---------------------------------------------------------------------------
SEND_WINDOW_START_HOUR = control.EMAIL_SEND_WINDOW_START_HOUR
SEND_WINDOW_END_HOUR = control.EMAIL_SEND_WINDOW_END_HOUR
SEND_WEEKDAYS = control.EMAIL_SEND_WEEKDAYS
SEND_TIMEZONE = control.SEND_TIMEZONE

# ---------------------------------------------------------------------------
# Who is safe to email
# ---------------------------------------------------------------------------
SENDABLE_EMAIL_STATUSES: tuple[str, ...] = control.SENDABLE_EMAIL_STATUSES
ALLOW_GUESSED_EMAILS = control.ALLOW_GUESSED_EMAILS

# ---------------------------------------------------------------------------
# Default outreach sequence
# ---------------------------------------------------------------------------
# A campaign is a series of steps. `wait_days` is the delay AFTER the previous
# step (step 1's wait_days is the delay after enrollment, usually 0 = send now).
# `angle` seeds the Writer/AB agents with the persuasion angle for that step.
# `variants` is how many A/B variants the AB optimizer generates for the step.
DEFAULT_SEQUENCE: tuple[dict, ...] = (
    {"name": "Intro", "wait_days": 0,
     "angle": "signal-led intro: name the event, then the specific capital/risk "
              "consequence it creates for their merchant book"},
    {"name": "Value nudge", "wait_days": 3,
     "angle": "quantify in bps of TPV — realised merchant credit loss versus what is "
              "held in reserves and sponsor collateral against it"},
    {"name": "Short bump", "wait_days": 4,
     "angle": "one sharp diagnostic question about how they price merchant "
              "insolvency risk today; very short, easy to answer"},
    {"name": "Breakup", "wait_days": 5,
     "angle": "polite break-up, leave the underwriting-loss benchmark behind"},
)

# ---------------------------------------------------------------------------
# A/B testing (multi-armed bandit — Thompson sampling)
# ---------------------------------------------------------------------------
VARIANTS_PER_STEP = control.EMAIL_VARIANTS_PER_STEP
BANDIT_PRIOR_ALPHA = control.BANDIT_PRIOR_ALPHA
BANDIT_PRIOR_BETA = control.BANDIT_PRIOR_BETA
MIN_SENDS_BEFORE_PROMOTION = control.EMAIL_MIN_SENDS_BEFORE_PROMOTION
WINNER_CONFIDENCE = control.EMAIL_WINNER_CONFIDENCE

# ---------------------------------------------------------------------------
# Autonomous conversation handling (the "reply queue")
# ---------------------------------------------------------------------------
# Master switch. When False, replies are still fetched, classified, and the
# sequence is stopped, but NO auto-reply is sent (drafts are stored for review).
# Flip on only once you trust the copy — it emails real prospects unattended.
AUTO_REPLY_ENABLED = control.AUTO_REPLY_ENABLED
MAX_AUTO_REPLIES = control.MAX_AUTO_REPLIES
CONVERSATION_MIN_CONFIDENCE = control.CONVERSATION_MIN_CONFIDENCE
MEETING_LINK = control.MEETING_LINK
AUTOPILOT_INTERVAL = control.EMAIL_AUTOPILOT_INTERVAL

# ---------------------------------------------------------------------------
# Campaign-level experiment (competing sequences)
# ---------------------------------------------------------------------------
# How many distinct sequences compete at once.
EXPERIMENT_SIZE = control.EXPERIMENT_SIZE

# Seed themes — one full sequence is designed per theme. When the weekly
# evolution retires a loser, a fresh challenger theme is drawn from CHALLENGER_THEMES.
EXPERIMENT_THEMES: tuple[str, ...] = (
    "Balance-sheet led: lead with the capital locked behind reserves and capital "
    "equivalency, and what the processor could underwrite if it were released.",
    "Loss-event led: open with the merchant-insolvency scenario they've already "
    "lived through — the collapse that landed as chargebacks on their book.",
    "Growth-led: frame it as revenue they currently decline, not risk they carry — "
    "the high-margin verticals underwriting says no to.",
    "Regulatory/network-change led: anchor on the rule or capital requirement that "
    "just moved, then reframe around pricing the tail risk instead of collateralising it.",
)
CHALLENGER_THEMES: tuple[str, ...] = (
    "Peer-benchmark led: what comparable processors hold in reserves versus actual "
    "realised merchant-default losses.",
    "Question-first: one sharp diagnostic question about how they price merchant "
    "insolvency risk at onboarding today.",
    "Operator-to-operator: candid note from someone who has run an acquiring book, "
    "no vendor language.",
    "Contrarian: argue that merchant reserves are the most expensive form of credit "
    "insurance a processor can buy, then show the alternative.",
)

# Lead allocation across ranked campaigns (rank 0 = best). Scaled to the batch
# size by largest-remainder apportionment. Default halves down the ranks so the
# winner gets the lion's share while losers keep getting explored. Example with
# 8 leads → 4 / 2 / 1 / 1.
CAMPAIGN_ALLOCATION_WEIGHTS: tuple[int, ...] = control.CAMPAIGN_ALLOCATION_WEIGHTS
EXPERIMENT_MIN_SENDS_FOR_RANKING = control.EXPERIMENT_MIN_SENDS_FOR_RANKING
WEEKLY_SYNC_DAYS = control.WEEKLY_SYNC_DAYS
RETIRE_MIN_SENDS = control.RETIRE_MIN_SENDS
RETIRE_SCORE_GAP = control.RETIRE_SCORE_GAP

# ---------------------------------------------------------------------------
# IMAP reply polling
# ---------------------------------------------------------------------------
# How far back (days) to scan a mailbox for replies on each poll. Kept short:
# with frequent polling, replies always arrive inside a 1-day window, and a
# tighter window keeps every poll fast. Override via PULSE_IMAP_LOOKBACK_DAYS.
IMAP_LOOKBACK_DAYS = control.IMAP_LOOKBACK_DAYS
IMAP_MAILBOX_FOLDER = control.IMAP_MAILBOX_FOLDER

# ---------------------------------------------------------------------------
# LLM tiers (from the central control panel)
# ---------------------------------------------------------------------------
HIGH_EFFORT_LLM = control.HIGH_EFFORT_LLM
NORMAL_LLM = control.NORMAL_LLM

# Writing the actual outreach copy is the quality-critical step → strong model.
WRITER_LLM = HIGH_EFFORT_LLM
# Classifying replies / generating variants is high-volume triage → cheap model.
CLASSIFIER_LLM = NORMAL_LLM
VARIANT_LLM = NORMAL_LLM
# Talking to real prospects autonomously — quality-critical → strong model.
CONVERSATION_LLM = HIGH_EFFORT_LLM
# Designing a whole themed sequence for the experiment → cheap/ideation.
SEQUENCE_DESIGNER_LLM = NORMAL_LLM


# ---------------------------------------------------------------------------
# Mailbox pool — loaded from the environment
# ---------------------------------------------------------------------------
def _int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def load_mailboxes_from_env() -> list[dict]:
    """Return mailbox config dicts from the environment.

    Precedence: if ``PULSE_MAILBOXES`` (a JSON array) is set, it wins and may
    define a whole pool. Otherwise a single mailbox is assembled from the
    individual ``PULSE_*`` vars. Returns ``[]`` when nothing is configured
    (so dry-run / preview flows still work without credentials).

    Passwords are read here but only held in memory — the store never persists
    them; it keeps a ``secret_ref`` (the env var name) instead.
    """
    raw = os.getenv("PULSE_MAILBOXES", "").strip()
    if raw:
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            items = []
        return [_normalize_mailbox(m) for m in items if m.get("email")]

    email = os.getenv("PULSE_EMAIL", "").strip()
    if not email:
        return []
    return [_normalize_mailbox({
        "email": email,
        "password": os.getenv("PULSE_EMAIL_PASSWORD", ""),
        "from_name": os.getenv("PULSE_FROM_NAME", ""),
        "smtp_host": os.getenv("PULSE_SMTP_HOST", ""),
        "smtp_port": os.getenv("PULSE_SMTP_PORT", ""),
        "imap_host": os.getenv("PULSE_IMAP_HOST", ""),
        "imap_port": os.getenv("PULSE_IMAP_PORT", ""),
        "secret_ref": "PULSE_EMAIL_PASSWORD",
    })]


# Sensible SMTP/IMAP defaults inferred from the email domain, so a Gmail user
# only has to set PULSE_EMAIL + PULSE_EMAIL_PASSWORD.
_PROVIDER_DEFAULTS = {
    "gmail.com": ("smtp.gmail.com", 465, "imap.gmail.com", 993),
    "googlemail.com": ("smtp.gmail.com", 465, "imap.gmail.com", 993),
    "outlook.com": ("smtp-mail.outlook.com", 587, "outlook.office365.com", 993),
    "hotmail.com": ("smtp-mail.outlook.com", 587, "outlook.office365.com", 993),
    "office365.com": ("smtp.office365.com", 587, "outlook.office365.com", 993),
    "zoho.com": ("smtp.zoho.com", 465, "imap.zoho.com", 993),
    "yahoo.com": ("smtp.mail.yahoo.com", 465, "imap.mail.yahoo.com", 993),
    "fastmail.com": ("smtp.fastmail.com", 465, "imap.fastmail.com", 993),
}


def _normalize_mailbox(m: dict) -> dict:
    """Fill in host/port defaults from the email domain and coerce types."""
    email = m["email"].strip()
    domain = email.split("@")[-1].lower()
    d_smtp_host, d_smtp_port, d_imap_host, d_imap_port = _PROVIDER_DEFAULTS.get(
        domain, ("", 465, "", 993)
    )
    return {
        "email": email,
        "password": m.get("password", ""),
        "secret_ref": m.get("secret_ref", ""),
        "from_name": m.get("from_name", "") or email.split("@")[0],
        "smtp_host": (m.get("smtp_host") or d_smtp_host).strip(),
        "smtp_port": _int(m.get("smtp_port"), d_smtp_port),
        "imap_host": (m.get("imap_host") or d_imap_host).strip(),
        "imap_port": _int(m.get("imap_port"), d_imap_port),
        "daily_cap": _int(m.get("daily_cap"), DEFAULT_DAILY_CAP),
    }
