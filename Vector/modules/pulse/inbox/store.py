"""SQLite persistence for Inbox (PULSE module).

Outreach state is relational and mutates constantly (sequence progress, message
lifecycle, per-variant reply counts, "who is due for a send now"). A local
SQLite DB — stdlib, no server, no cost — is the right fit and leaves Scout's
per-lead JSON model untouched. Inbox READS leads from ``data/Leads/*.json`` and
WRITES all campaign state to ``data/pulse/inbox.db``.

Everything here is plain functions over a shared connection. Rows map to the
Pydantic models in ``schemas.py``. Passwords are never stored — a mailbox row
keeps a ``secret_ref`` (env var name) instead.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from modules.common.logger import get_logger
from modules.pulse.inbox.config import DB_PATH, PULSE_DIR
from modules.pulse.inbox.schemas import (
    Campaign,
    CampaignGroup,
    CampaignStatus,
    Mailbox,
    MailboxStatus,
    Message,
    MessageStatus,
    Recipient,
    RecipientStatus,
    Reply,
    ReplyClass,
    SequenceStep,
    Variant,
    utcnow_iso,
)

logger = get_logger("pulse.inbox.store")

_conn: sqlite3.Connection | None = None


# ---------------------------------------------------------------------------
# Connection + schema
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS mailboxes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    from_name TEXT DEFAULT '',
    provider TEXT DEFAULT '',
    smtp_host TEXT DEFAULT '',
    smtp_port INTEGER DEFAULT 465,
    imap_host TEXT DEFAULT '',
    imap_port INTEGER DEFAULT 993,
    secret_ref TEXT DEFAULT '',
    daily_cap INTEGER DEFAULT 40,
    warmup_started_on TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'active',
    size INTEGER DEFAULT 4,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    icp_min_score INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    group_id INTEGER REFERENCES campaign_groups(id),
    theme TEXT DEFAULT '',
    priority INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS kv_state (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sequence_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    name TEXT DEFAULT '',
    angle TEXT DEFAULT '',
    wait_days INTEGER DEFAULT 0,
    UNIQUE(campaign_id, step_order)
);

CREATE TABLE IF NOT EXISTS variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id INTEGER NOT NULL REFERENCES sequence_steps(id) ON DELETE CASCADE,
    name TEXT DEFAULT '',
    angle TEXT DEFAULT '',
    subject_template TEXT DEFAULT '',
    body_template TEXT DEFAULT '',
    sent_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    alpha REAL DEFAULT 1.0,
    beta REAL DEFAULT 1.0,
    is_winner INTEGER DEFAULT 0,
    is_paused INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    lead_slug TEXT DEFAULT '',
    company TEXT DEFAULT '',
    name TEXT DEFAULT '',
    email TEXT NOT NULL,
    title TEXT DEFAULT '',
    role_category TEXT DEFAULT '',
    email_status TEXT DEFAULT '',
    current_step INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    mailbox_id INTEGER REFERENCES mailboxes(id),
    next_send_at TEXT,
    last_sent_at TEXT,
    replied_at TEXT,
    enrolled_at TEXT NOT NULL,
    context TEXT DEFAULT '{}',
    UNIQUE(campaign_id, email)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER REFERENCES recipients(id) ON DELETE CASCADE,
    campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
    step_id INTEGER REFERENCES sequence_steps(id),
    variant_id INTEGER REFERENCES variants(id),
    mailbox_id INTEGER REFERENCES mailboxes(id),
    to_email TEXT DEFAULT '',
    from_email TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    rfc_message_id TEXT DEFAULT '',
    thread_id TEXT DEFAULT '',
    in_reply_to TEXT DEFAULT '',
    status TEXT DEFAULT 'queued',
    error TEXT DEFAULT '',
    queued_at TEXT NOT NULL,
    sent_at TEXT,
    opened_at TEXT
);

CREATE TABLE IF NOT EXISTS replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER REFERENCES recipients(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES messages(id),
    from_email TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    received_at TEXT NOT NULL,
    imap_uid TEXT DEFAULT '',
    classification TEXT DEFAULT 'other',
    classification_confidence REAL DEFAULT 0.0,
    resume_at TEXT,
    UNIQUE(imap_uid)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER,
    campaign_id INTEGER,
    type TEXT NOT NULL,
    data TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_recipients_due
    ON recipients(status, next_send_at);
CREATE INDEX IF NOT EXISTS idx_messages_mailbox_sent
    ON messages(mailbox_id, status, sent_at);
CREATE INDEX IF NOT EXISTS idx_messages_rfc ON messages(rfc_message_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);
"""


def get_conn() -> sqlite3.Connection:
    """Return the shared connection, creating + initializing the DB on first use."""
    global _conn
    if _conn is None:
        PULSE_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.execute("PRAGMA journal_mode = WAL")
        _conn.executescript(SCHEMA)
        _migrate(_conn)
        _conn.commit()
        logger.info("Inbox DB ready at %s", DB_PATH)
    return _conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns to older DBs created before the experiment feature."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(campaigns)").fetchall()}
    for col, ddl in (("group_id", "INTEGER"), ("theme", "TEXT DEFAULT ''"),
                     ("priority", "INTEGER DEFAULT 0")):
        if col not in cols:
            conn.execute(f"ALTER TABLE campaigns ADD COLUMN {col} {ddl}")


def reset_db() -> None:
    """Drop the whole DB file (used by tests / a clean re-run)."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
    Path(DB_PATH).unlink(missing_ok=True)
    Path(str(DB_PATH) + "-wal").unlink(missing_ok=True)
    Path(str(DB_PATH) + "-shm").unlink(missing_ok=True)


def _commit() -> None:
    get_conn().commit()


# ---------------------------------------------------------------------------
# Mailboxes
# ---------------------------------------------------------------------------
def upsert_mailbox(mb: Mailbox) -> Mailbox:
    """Insert a mailbox by email, or update its config if it already exists.

    The password is intentionally dropped — only ``secret_ref`` is stored.
    """
    conn = get_conn()
    row = conn.execute("SELECT id FROM mailboxes WHERE email = ?", (mb.email,)).fetchone()
    if row:
        conn.execute(
            """UPDATE mailboxes SET from_name=?, provider=?, smtp_host=?, smtp_port=?,
               imap_host=?, imap_port=?, secret_ref=?, daily_cap=?, status=?
               WHERE email=?""",
            (mb.from_name, mb.provider, mb.smtp_host, mb.smtp_port, mb.imap_host,
             mb.imap_port, mb.secret_ref, mb.daily_cap, mb.status.value, mb.email),
        )
        mb.id = row["id"]
    else:
        cur = conn.execute(
            """INSERT INTO mailboxes (email, from_name, provider, smtp_host, smtp_port,
               imap_host, imap_port, secret_ref, daily_cap, warmup_started_on, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (mb.email, mb.from_name, mb.provider, mb.smtp_host, mb.smtp_port, mb.imap_host,
             mb.imap_port, mb.secret_ref, mb.daily_cap, mb.warmup_started_on,
             mb.status.value, mb.created_at),
        )
        mb.id = cur.lastrowid
    _commit()
    return mb


def _row_to_mailbox(r: sqlite3.Row) -> Mailbox:
    return Mailbox(
        id=r["id"], email=r["email"], from_name=r["from_name"], provider=r["provider"],
        smtp_host=r["smtp_host"], smtp_port=r["smtp_port"], imap_host=r["imap_host"],
        imap_port=r["imap_port"], secret_ref=r["secret_ref"], daily_cap=r["daily_cap"],
        warmup_started_on=r["warmup_started_on"], status=MailboxStatus(r["status"]),
        created_at=r["created_at"],
    )


def list_mailboxes(active_only: bool = True) -> list[Mailbox]:
    q = "SELECT * FROM mailboxes"
    if active_only:
        q += " WHERE status = 'active'"
    q += " ORDER BY id"
    return [_row_to_mailbox(r) for r in get_conn().execute(q).fetchall()]


def get_mailbox(mailbox_id: int) -> Mailbox | None:
    r = get_conn().execute("SELECT * FROM mailboxes WHERE id = ?", (mailbox_id,)).fetchone()
    return _row_to_mailbox(r) if r else None


def mark_mailbox_warmup_started(mailbox_id: int, on: str | None = None) -> None:
    """Record the first-send date so the warmup ramp has a day-0 to count from."""
    on = on or date.today().isoformat()
    get_conn().execute(
        "UPDATE mailboxes SET warmup_started_on = ? WHERE id = ? AND warmup_started_on IS NULL",
        (on, mailbox_id),
    )
    _commit()


def sent_today(mailbox_id: int, on: str | None = None) -> int:
    """Count emails already SENT from a mailbox today (drives cap enforcement)."""
    on = on or date.today().isoformat()
    r = get_conn().execute(
        """SELECT COUNT(*) AS n FROM messages
           WHERE mailbox_id = ? AND status IN ('sent','opened','replied')
           AND substr(sent_at, 1, 10) = ?""",
        (mailbox_id, on),
    ).fetchone()
    return r["n"]


# ---------------------------------------------------------------------------
# Campaigns / steps / variants
# ---------------------------------------------------------------------------
def create_campaign(campaign: Campaign) -> Campaign:
    """Persist a campaign plus its steps and variants (one transaction)."""
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO campaigns (name, description, status, icp_min_score, created_at, "
        "group_id, theme, priority) VALUES (?,?,?,?,?,?,?,?)",
        (campaign.name, campaign.description, campaign.status.value, campaign.icp_min_score,
         campaign.created_at, campaign.group_id, campaign.theme, campaign.priority),
    )
    campaign.id = cur.lastrowid
    for step in campaign.steps:
        step.campaign_id = campaign.id
        scur = conn.execute(
            "INSERT INTO sequence_steps (campaign_id, step_order, name, angle, wait_days) VALUES (?,?,?,?,?)",
            (step.campaign_id, step.step_order, step.name, step.angle, step.wait_days),
        )
        step.id = scur.lastrowid
        for v in step.variants:
            v.step_id = step.id
            _insert_variant(conn, v)
    _commit()
    logger.info("Created campaign #%s '%s' (%d steps)", campaign.id, campaign.name, len(campaign.steps))
    return campaign


def _insert_variant(conn: sqlite3.Connection, v: Variant) -> Variant:
    cur = conn.execute(
        """INSERT INTO variants (step_id, name, angle, subject_template, body_template,
           sent_count, reply_count, alpha, beta, is_winner, is_paused, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (v.step_id, v.name, v.angle, v.subject_template, v.body_template, v.sent_count,
         v.reply_count, v.alpha, v.beta, int(v.is_winner), int(v.is_paused), v.created_at),
    )
    v.id = cur.lastrowid
    return v


def add_variant(v: Variant) -> Variant:
    v = _insert_variant(get_conn(), v)
    _commit()
    return v


def get_campaign_by_name(name: str) -> Campaign | None:
    r = get_conn().execute("SELECT * FROM campaigns WHERE name = ?", (name,)).fetchone()
    return _load_campaign(r) if r else None


def get_campaign(campaign_id: int) -> Campaign | None:
    r = get_conn().execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    return _load_campaign(r) if r else None


def _load_campaign(r: sqlite3.Row) -> Campaign:
    conn = get_conn()
    steps: list[SequenceStep] = []
    for sr in conn.execute(
        "SELECT * FROM sequence_steps WHERE campaign_id = ? ORDER BY step_order", (r["id"],)
    ).fetchall():
        variants = [
            _row_to_variant(vr)
            for vr in conn.execute(
                "SELECT * FROM variants WHERE step_id = ? ORDER BY id", (sr["id"],)
            ).fetchall()
        ]
        steps.append(SequenceStep(
            id=sr["id"], campaign_id=sr["campaign_id"], step_order=sr["step_order"],
            name=sr["name"], angle=sr["angle"], wait_days=sr["wait_days"], variants=variants,
        ))
    keys = r.keys()
    return Campaign(
        id=r["id"], name=r["name"], description=r["description"],
        status=CampaignStatus(r["status"]), icp_min_score=r["icp_min_score"],
        created_at=r["created_at"], steps=steps,
        group_id=r["group_id"] if "group_id" in keys else None,
        theme=r["theme"] if "theme" in keys else "",
        priority=r["priority"] if "priority" in keys else 0,
    )


def _row_to_variant(r: sqlite3.Row) -> Variant:
    return Variant(
        id=r["id"], step_id=r["step_id"], name=r["name"], angle=r["angle"],
        subject_template=r["subject_template"], body_template=r["body_template"],
        sent_count=r["sent_count"], reply_count=r["reply_count"],
        alpha=r["alpha"], beta=r["beta"], is_winner=bool(r["is_winner"]),
        is_paused=bool(r["is_paused"]), created_at=r["created_at"],
    )


def delete_variants(step_id: int, only_unsent: bool = True) -> int:
    """Remove a step's variants (default: only those with no sends yet).

    Used when the A/B optimizer replaces placeholder arms before a campaign
    starts. Never deletes an arm that already has send history.
    """
    q = "DELETE FROM variants WHERE step_id = ?"
    if only_unsent:
        q += " AND sent_count = 0"
    cur = get_conn().execute(q, (step_id,))
    _commit()
    return cur.rowcount


def get_step_variants(step_id: int, include_paused: bool = False) -> list[Variant]:
    q = "SELECT * FROM variants WHERE step_id = ?"
    if not include_paused:
        q += " AND is_paused = 0"
    q += " ORDER BY id"
    return [_row_to_variant(r) for r in get_conn().execute(q, (step_id,)).fetchall()]


def update_variant_stats(variant_id: int, *, sent_delta: int = 0, reply_delta: int = 0) -> None:
    """Bump a variant's observed counts AND its Beta(alpha,beta) posterior.

    A send is a trial; a reply is a success. alpha += successes,
    beta += failures — this is exactly what Thompson sampling needs.
    """
    conn = get_conn()
    failures = sent_delta - reply_delta
    conn.execute(
        """UPDATE variants
           SET sent_count = sent_count + ?, reply_count = reply_count + ?,
               alpha = alpha + ?, beta = beta + ?
           WHERE id = ?""",
        (sent_delta, reply_delta, reply_delta, failures, variant_id),
    )
    _commit()


def promote_variant(step_id: int, winner_id: int) -> None:
    """Mark one variant the winner and pause its siblings on the same step."""
    conn = get_conn()
    conn.execute("UPDATE variants SET is_winner = 0, is_paused = 1 WHERE step_id = ?", (step_id,))
    conn.execute("UPDATE variants SET is_winner = 1, is_paused = 0 WHERE id = ?", (winner_id,))
    _commit()


def set_campaign_status(campaign_id: int, status: CampaignStatus) -> None:
    get_conn().execute("UPDATE campaigns SET status = ? WHERE id = ?", (status.value, campaign_id))
    _commit()


def update_campaign(campaign_id: int, **fields: Any) -> None:
    """Update campaign columns (status/group_id/theme/priority/…)."""
    if not fields:
        return
    cols, params = [], []
    for k, v in fields.items():
        if hasattr(v, "value"):
            v = v.value
        cols.append(f"{k} = ?")
        params.append(v)
    params.append(campaign_id)
    get_conn().execute(f"UPDATE campaigns SET {', '.join(cols)} WHERE id = ?", params)
    _commit()


# ---------------------------------------------------------------------------
# Campaign groups (experiments)
# ---------------------------------------------------------------------------
def create_group(group: CampaignGroup) -> CampaignGroup:
    cur = get_conn().execute(
        "INSERT INTO campaign_groups (name, status, size, created_at) VALUES (?,?,?,?)",
        (group.name, group.status, group.size, group.created_at))
    group.id = cur.lastrowid
    _commit()
    return group


def get_group_by_name(name: str) -> CampaignGroup | None:
    r = get_conn().execute("SELECT * FROM campaign_groups WHERE name = ?", (name,)).fetchone()
    return CampaignGroup(id=r["id"], name=r["name"], status=r["status"], size=r["size"],
                         created_at=r["created_at"]) if r else None


def list_campaigns(status: CampaignStatus | None = None) -> list[Campaign]:
    """All campaigns, optionally filtered by status (used by the autopilot)."""
    q = "SELECT * FROM campaigns"
    params: list[Any] = []
    if status is not None:
        q += " WHERE status = ?"
        params.append(status.value)
    q += " ORDER BY id"
    return [_load_campaign(r) for r in get_conn().execute(q, params).fetchall()]


def list_groups(active_only: bool = True) -> list[CampaignGroup]:
    q = "SELECT * FROM campaign_groups"
    if active_only:
        q += " WHERE status = 'active'"
    q += " ORDER BY id"
    return [CampaignGroup(id=r["id"], name=r["name"], status=r["status"], size=r["size"],
                          created_at=r["created_at"]) for r in get_conn().execute(q).fetchall()]


def group_emails(group_id: int) -> set[str]:
    """Every recipient email already enrolled anywhere in a group (for intake dedupe)."""
    rows = get_conn().execute(
        "SELECT DISTINCT r.email FROM recipients r JOIN campaigns c ON c.id = r.campaign_id "
        "WHERE c.group_id = ?", (group_id,)).fetchall()
    return {row["email"].lower() for row in rows}


def list_group_campaigns(group_id: int, active_only: bool = True) -> list[Campaign]:
    q = "SELECT * FROM campaigns WHERE group_id = ?"
    if active_only:
        q += " AND status = 'active'"
    q += " ORDER BY priority, id"
    return [_load_campaign(r) for r in get_conn().execute(q, (group_id,)).fetchall()]


# ---------------------------------------------------------------------------
# Key/value state (autopilot bookkeeping)
# ---------------------------------------------------------------------------
def kv_get(key: str, default: str | None = None) -> str | None:
    r = get_conn().execute("SELECT value FROM kv_state WHERE key = ?", (key,)).fetchone()
    return r["value"] if r else default


def kv_set(key: str, value: str) -> None:
    get_conn().execute(
        "INSERT INTO kv_state (key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, utcnow_iso()))
    _commit()


# ---------------------------------------------------------------------------
# Recipients
# ---------------------------------------------------------------------------
def enroll_recipient(rec: Recipient) -> Recipient | None:
    """Insert a recipient; returns None if this email is already in the campaign."""
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO recipients (campaign_id, lead_slug, company, name, email, title,
               role_category, email_status, current_step, status, mailbox_id, next_send_at,
               last_sent_at, replied_at, enrolled_at, context)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rec.campaign_id, rec.lead_slug, rec.company, rec.name, rec.email, rec.title,
             rec.role_category, rec.email_status, rec.current_step, rec.status.value,
             rec.mailbox_id, rec.next_send_at, rec.last_sent_at, rec.replied_at,
             rec.enrolled_at, json.dumps(rec.context, ensure_ascii=False)),
        )
    except sqlite3.IntegrityError:
        return None
    rec.id = cur.lastrowid
    _commit()
    return rec


def _row_to_recipient(r: sqlite3.Row) -> Recipient:
    return Recipient(
        id=r["id"], campaign_id=r["campaign_id"], lead_slug=r["lead_slug"], company=r["company"],
        name=r["name"], email=r["email"], title=r["title"], role_category=r["role_category"],
        email_status=r["email_status"], current_step=r["current_step"],
        status=RecipientStatus(r["status"]), mailbox_id=r["mailbox_id"],
        next_send_at=r["next_send_at"], last_sent_at=r["last_sent_at"],
        replied_at=r["replied_at"], enrolled_at=r["enrolled_at"],
        context=json.loads(r["context"] or "{}"),
    )


def list_recipients(campaign_id: int, status: RecipientStatus | None = None) -> list[Recipient]:
    q = "SELECT * FROM recipients WHERE campaign_id = ?"
    params: list[Any] = [campaign_id]
    if status is not None:
        q += " AND status = ?"
        params.append(status.value)
    q += " ORDER BY id"
    return [_row_to_recipient(r) for r in get_conn().execute(q, params).fetchall()]


def get_recipient(recipient_id: int) -> Recipient | None:
    r = get_conn().execute("SELECT * FROM recipients WHERE id = ?", (recipient_id,)).fetchone()
    return _row_to_recipient(r) if r else None


def due_recipients(now_iso: str, campaign_id: int | None = None) -> list[Recipient]:
    """Active recipients whose next step is due (next_send_at <= now)."""
    q = ("SELECT * FROM recipients WHERE status = 'active' "
         "AND (next_send_at IS NULL OR next_send_at <= ?)")
    params: list[Any] = [now_iso]
    if campaign_id is not None:
        q += " AND campaign_id = ?"
        params.append(campaign_id)
    q += " ORDER BY next_send_at IS NULL DESC, next_send_at ASC, id ASC"
    return [_row_to_recipient(r) for r in get_conn().execute(q, params).fetchall()]


def reactivate_due_paused(now_iso: str, campaign_id: int | None = None) -> int:
    """Flip PAUSED recipients (e.g. out-of-office) back to ACTIVE once their
    ``next_send_at`` resume time has arrived. Returns how many were reactivated."""
    conn = get_conn()
    q = ("UPDATE recipients SET status = 'active' WHERE status = 'paused' "
         "AND next_send_at IS NOT NULL AND next_send_at <= ?")
    params: list[Any] = [now_iso]
    if campaign_id is not None:
        q += " AND campaign_id = ?"
        params.append(campaign_id)
    cur = conn.execute(q, params)
    _commit()
    return cur.rowcount


def update_recipient(recipient_id: int, **fields: Any) -> None:
    """Update arbitrary recipient columns. Enum values are unwrapped; context is JSON-encoded."""
    if not fields:
        return
    cols, params = [], []
    for k, v in fields.items():
        if hasattr(v, "value"):          # enum → its string value
            v = v.value
        if k == "context" and isinstance(v, dict):
            v = json.dumps(v, ensure_ascii=False)
        cols.append(f"{k} = ?")
        params.append(v)
    params.append(recipient_id)
    get_conn().execute(f"UPDATE recipients SET {', '.join(cols)} WHERE id = ?", params)
    _commit()


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
def create_message(msg: Message) -> Message:
    cur = get_conn().execute(
        """INSERT INTO messages (recipient_id, campaign_id, step_id, variant_id, mailbox_id,
           to_email, from_email, subject, body, rfc_message_id, thread_id, in_reply_to,
           status, error, queued_at, sent_at, opened_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (msg.recipient_id, msg.campaign_id, msg.step_id, msg.variant_id, msg.mailbox_id,
         msg.to_email, msg.from_email, msg.subject, msg.body, msg.rfc_message_id,
         msg.thread_id, msg.in_reply_to, msg.status.value, msg.error, msg.queued_at,
         msg.sent_at, msg.opened_at),
    )
    msg.id = cur.lastrowid
    _commit()
    return msg


def _row_to_message(r: sqlite3.Row) -> Message:
    return Message(
        id=r["id"], recipient_id=r["recipient_id"], campaign_id=r["campaign_id"],
        step_id=r["step_id"], variant_id=r["variant_id"], mailbox_id=r["mailbox_id"],
        to_email=r["to_email"], from_email=r["from_email"], subject=r["subject"],
        body=r["body"], rfc_message_id=r["rfc_message_id"], thread_id=r["thread_id"],
        in_reply_to=r["in_reply_to"], status=MessageStatus(r["status"]), error=r["error"],
        queued_at=r["queued_at"], sent_at=r["sent_at"], opened_at=r["opened_at"],
    )


def update_message(message_id: int, **fields: Any) -> None:
    if not fields:
        return
    cols, params = [], []
    for k, v in fields.items():
        if hasattr(v, "value"):
            v = v.value
        cols.append(f"{k} = ?")
        params.append(v)
    params.append(message_id)
    get_conn().execute(f"UPDATE messages SET {', '.join(cols)} WHERE id = ?", params)
    _commit()


def get_message(message_id: int) -> Message | None:
    r = get_conn().execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    return _row_to_message(r) if r else None


# NB: 'booked' is intentionally NOT terminal — a booked recipient can still
# reply to reschedule/cancel, so we keep matching their messages.
_TERMINAL_STATUSES = ("bounced", "unsubscribed", "completed", "not_interested")


def active_recipient_emails() -> set[str]:
    """Emails of recipients who might still reply (not in a terminal state) —
    lets the poller surface replies that thread to an older message."""
    q = ("SELECT DISTINCT email FROM recipients WHERE email != '' AND status NOT IN "
         f"({','.join('?' for _ in _TERMINAL_STATUSES)})")
    rows = get_conn().execute(q, _TERMINAL_STATUSES).fetchall()
    return {r["email"].lower() for r in rows}


def find_recipient_by_email(email: str) -> Recipient | None:
    """Most recent non-terminal recipient with this email (for reply matching)."""
    if not email:
        return None
    q = ("SELECT * FROM recipients WHERE lower(email) = ? AND status NOT IN "
         f"({','.join('?' for _ in _TERMINAL_STATUSES)}) ORDER BY id DESC LIMIT 1")
    r = get_conn().execute(q, (email.lower(), *_TERMINAL_STATUSES)).fetchone()
    return _row_to_recipient(r) if r else None


def outbound_message_ids() -> set[str]:
    """Every non-empty Message-ID we've sent — lets the IMAP reader pre-filter
    the inbox to just messages that reference one of our emails."""
    rows = get_conn().execute(
        "SELECT rfc_message_id FROM messages WHERE rfc_message_id != ''").fetchall()
    return {r["rfc_message_id"] for r in rows}


def find_message_by_rfc_id(rfc_message_id: str) -> Message | None:
    """Match an inbound reply's In-Reply-To/References back to our outbound message."""
    if not rfc_message_id:
        return None
    r = get_conn().execute(
        "SELECT * FROM messages WHERE rfc_message_id = ?", (rfc_message_id,)
    ).fetchone()
    return _row_to_message(r) if r else None


def get_message_by_recipient_latest(recipient_id: int) -> Message | None:
    """The most recent outbound message to a recipient (for reply threading)."""
    r = get_conn().execute(
        "SELECT * FROM messages WHERE recipient_id = ? ORDER BY id DESC LIMIT 1",
        (recipient_id,)).fetchone()
    return _row_to_message(r) if r else None


def messages_for_recipient(recipient_id: int) -> list[Message]:
    rows = get_conn().execute(
        "SELECT * FROM messages WHERE recipient_id = ? ORDER BY id", (recipient_id,)
    ).fetchall()
    return [_row_to_message(r) for r in rows]


def latest_thread_id(recipient_id: int) -> str:
    """The thread token to reply within (first sent message's id), or ''."""
    r = get_conn().execute(
        "SELECT thread_id FROM messages WHERE recipient_id = ? AND thread_id != '' ORDER BY id LIMIT 1",
        (recipient_id,),
    ).fetchone()
    return r["thread_id"] if r else ""


# ---------------------------------------------------------------------------
# Replies
# ---------------------------------------------------------------------------
def save_reply(reply: Reply) -> Reply | None:
    """Store an inbound reply; returns None if this IMAP UID was already saved."""
    try:
        cur = get_conn().execute(
            """INSERT INTO replies (recipient_id, message_id, from_email, subject, body,
               received_at, imap_uid, classification, classification_confidence, resume_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (reply.recipient_id, reply.message_id, reply.from_email, reply.subject,
             reply.body, reply.received_at, reply.imap_uid, reply.classification.value,
             reply.classification_confidence, reply.resume_at),
        )
    except sqlite3.IntegrityError:
        return None
    reply.id = cur.lastrowid
    _commit()
    return reply


def reply_uid_seen(imap_uid: str) -> bool:
    r = get_conn().execute("SELECT 1 FROM replies WHERE imap_uid = ?", (imap_uid,)).fetchone()
    return r is not None


def _row_to_reply(r: sqlite3.Row) -> Reply:
    return Reply(
        id=r["id"], recipient_id=r["recipient_id"], message_id=r["message_id"],
        from_email=r["from_email"], subject=r["subject"], body=r["body"],
        received_at=r["received_at"], imap_uid=r["imap_uid"],
        classification=ReplyClass(r["classification"]),
        classification_confidence=r["classification_confidence"], resume_at=r["resume_at"],
    )


def replies_for_recipient(recipient_id: int) -> list[Reply]:
    rows = get_conn().execute(
        "SELECT * FROM replies WHERE recipient_id = ? ORDER BY received_at, id", (recipient_id,)
    ).fetchall()
    return [_row_to_reply(r) for r in rows]


def count_conversation_messages(recipient_id: int) -> int:
    """How many agent-sent conversation replies (step_id IS NULL) we've sent in
    this thread — drives the auto-reply safety cap."""
    r = get_conn().execute(
        "SELECT COUNT(*) n FROM messages WHERE recipient_id = ? AND step_id IS NULL "
        "AND status IN ('sent','opened','replied')", (recipient_id,)).fetchone()
    return r["n"]


# ---------------------------------------------------------------------------
# Events (lightweight audit trail for analytics / timelines)
# ---------------------------------------------------------------------------
def log_event(type: str, *, recipient_id: int | None = None,
              campaign_id: int | None = None, data: dict | None = None) -> None:
    get_conn().execute(
        "INSERT INTO events (recipient_id, campaign_id, type, data, created_at) VALUES (?,?,?,?,?)",
        (recipient_id, campaign_id, type, json.dumps(data or {}, ensure_ascii=False), utcnow_iso()),
    )
    _commit()
