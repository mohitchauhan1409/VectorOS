"""Mailbox pool management — rotation, daily caps, and warmup.

This is where free-tier deliverability is enforced. Every send asks the pool:
"which mailbox can send right now, and does it still have headroom today?"

- Credentials never touch the DB. They're resolved on demand from the live env
  config (``config.load_mailboxes_from_env``), matched by email.
- A mailbox's daily allowance ramps during warmup: a brand-new mailbox starts
  at WARMUP_START and climbs WARMUP_INCREMENT/day until it reaches its cap.
- Rotation picks the active mailbox with the most remaining headroom, so volume
  spreads evenly across the pool instead of hammering one address.
"""

from __future__ import annotations

from datetime import date

from modules.common.logger import get_logger
from modules.pulse.inbox import config, store
from modules.pulse.inbox.schemas import Mailbox

logger = get_logger("pulse.inbox.accounts")


def get_credentials(email: str) -> dict | None:
    """Resolve the live SMTP/IMAP credentials for a mailbox email, or None."""
    for cfg in config.load_mailboxes_from_env():
        if cfg["email"].lower() == email.lower():
            return cfg
    return None


def _days_since(iso_date: str | None) -> int:
    if not iso_date:
        return 0
    try:
        started = date.fromisoformat(iso_date)
    except ValueError:
        return 0
    return max(0, (date.today() - started).days)


def daily_allowance(mailbox: Mailbox) -> int:
    """How many emails this mailbox may send TODAY, honoring warmup.

    Day 0 (first send day) → WARMUP_START. Each later day adds
    WARMUP_INCREMENT, capped at the mailbox's ``daily_cap``.
    """
    if not config.WARMUP_ENABLED:
        return mailbox.daily_cap
    if mailbox.warmup_started_on is None:
        # Not warmed up yet — day-0 allowance until the first send is recorded.
        return min(config.WARMUP_START, mailbox.daily_cap)
    ramped = config.WARMUP_START + config.WARMUP_INCREMENT * _days_since(mailbox.warmup_started_on)
    return min(ramped, mailbox.daily_cap)


def remaining_today(mailbox: Mailbox) -> int:
    """Allowance minus what's already gone out today (never negative)."""
    if mailbox.id is None:
        return 0
    return max(0, daily_allowance(mailbox) - store.sent_today(mailbox.id))


def pick_mailbox(preferred_id: int | None = None) -> Mailbox | None:
    """Choose a mailbox with capacity right now.

    Prefers ``preferred_id`` (a recipient's sticky mailbox — keeps a thread on
    one address) when it still has headroom. Otherwise returns the active
    mailbox with the most remaining capacity. Returns None if the whole pool is
    tapped out for the day.
    """
    pool = store.list_mailboxes(active_only=True)
    if not pool:
        return None

    if preferred_id is not None:
        pref = next((m for m in pool if m.id == preferred_id), None)
        if pref and remaining_today(pref) > 0:
            return pref

    with_capacity = [(remaining_today(m), m) for m in pool]
    with_capacity = [(cap, m) for cap, m in with_capacity if cap > 0]
    if not with_capacity:
        return None
    with_capacity.sort(key=lambda t: t[0], reverse=True)
    return with_capacity[0][1]


def pool_capacity_today() -> int:
    """Total remaining sends across the whole active pool today."""
    return sum(remaining_today(m) for m in store.list_mailboxes(active_only=True))


def note_send(mailbox: Mailbox) -> None:
    """Record the first-send date so the warmup ramp has a day-0 anchor."""
    if mailbox.id is not None and mailbox.warmup_started_on is None:
        store.mark_mailbox_warmup_started(mailbox.id)
        mailbox.warmup_started_on = date.today().isoformat()
