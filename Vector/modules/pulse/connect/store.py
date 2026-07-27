"""SQLite persistence for Connect (LinkedIn outreach).

Same approach as Inbox's store, in its own DB (``data/pulse/connect.db``).
Connect READS leads from ``data/Leads/*.json`` and writes all campaign +
prospect state here. Passwords/cookies are never stored — the provider resolves
credentials from the environment at send time.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from modules.common.logger import get_logger
from modules.pulse.connect.config import DB_PATH, PULSE_DIR
from modules.pulse.connect.schemas import (
    AccountStatus,
    Campaign,
    CampaignStatus,
    ConnectMessage,
    LinkedInAccount,
    MessageKind,
    MessageStatus,
    Prospect,
    ProspectStatus,
    Reply,
    ReplyClass,
    SequenceStep,
    StepKind,
    Variant,
    utcnow_iso,
)

logger = get_logger("pulse.connect.store")

_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT DEFAULT '',
    provider TEXT DEFAULT 'mock',
    provider_account_id TEXT DEFAULT '',
    daily_invite_cap INTEGER DEFAULT 20,
    weekly_invite_cap INTEGER DEFAULT 100,
    daily_message_cap INTEGER DEFAULT 40,
    warmup_started_on TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL,
    UNIQUE(provider, provider_account_id)
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    icp_min_score INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sequence_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    name TEXT DEFAULT '',
    kind TEXT DEFAULT 'message',
    angle TEXT DEFAULT '',
    wait_days INTEGER DEFAULT 0,
    UNIQUE(campaign_id, step_order)
);

CREATE TABLE IF NOT EXISTS variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id INTEGER NOT NULL REFERENCES sequence_steps(id) ON DELETE CASCADE,
    name TEXT DEFAULT '',
    angle TEXT DEFAULT '',
    template TEXT DEFAULT '',
    sent_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    alpha REAL DEFAULT 1.0,
    beta REAL DEFAULT 1.0,
    is_winner INTEGER DEFAULT 0,
    is_paused INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    lead_slug TEXT DEFAULT '',
    company TEXT DEFAULT '',
    name TEXT DEFAULT '',
    title TEXT DEFAULT '',
    role_category TEXT DEFAULT '',
    linkedin_url TEXT NOT NULL,
    email TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    current_step INTEGER DEFAULT 0,
    account_id INTEGER REFERENCES accounts(id),
    next_action_at TEXT,
    invited_at TEXT,
    accepted_at TEXT,
    last_action_at TEXT,
    replied_at TEXT,
    enrolled_at TEXT NOT NULL,
    context TEXT DEFAULT '{}',
    UNIQUE(campaign_id, linkedin_url)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER REFERENCES prospects(id) ON DELETE CASCADE,
    campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
    step_id INTEGER REFERENCES sequence_steps(id),
    variant_id INTEGER REFERENCES variants(id),
    account_id INTEGER REFERENCES accounts(id),
    kind TEXT DEFAULT 'message',
    body TEXT DEFAULT '',
    provider_ref TEXT DEFAULT '',
    status TEXT DEFAULT 'queued',
    error TEXT DEFAULT '',
    queued_at TEXT NOT NULL,
    sent_at TEXT
);

CREATE TABLE IF NOT EXISTS replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER REFERENCES prospects(id) ON DELETE CASCADE,
    body TEXT DEFAULT '',
    received_at TEXT NOT NULL,
    provider_id TEXT DEFAULT '',
    classification TEXT DEFAULT 'other',
    classification_confidence REAL DEFAULT 0.0,
    resume_at TEXT,
    UNIQUE(provider_id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER,
    campaign_id INTEGER,
    type TEXT NOT NULL,
    data TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kv_state (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prospects_due ON prospects(status, next_action_at);
CREATE INDEX IF NOT EXISTS idx_messages_acct ON messages(account_id, kind, status, sent_at);
"""


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        PULSE_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.execute("PRAGMA journal_mode = WAL")
        _conn.executescript(SCHEMA)
        cols = {r["name"] for r in _conn.execute("PRAGMA table_info(prospects)").fetchall()}
        if "email" not in cols:
            _conn.execute("ALTER TABLE prospects ADD COLUMN email TEXT DEFAULT ''")
        _conn.commit()
        logger.info("Connect DB ready at %s", DB_PATH)
    return _conn


def reset_db() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
    for suffix in ("", "-wal", "-shm"):
        Path(str(DB_PATH) + suffix).unlink(missing_ok=True)


def _commit() -> None:
    get_conn().commit()


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
def upsert_account(acct: LinkedInAccount) -> LinkedInAccount:
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM accounts WHERE provider=? AND provider_account_id=?",
        (acct.provider, acct.provider_account_id)).fetchone()
    if row:
        conn.execute(
            """UPDATE accounts SET name=?, daily_invite_cap=?, weekly_invite_cap=?,
               daily_message_cap=?, status=? WHERE id=?""",
            (acct.name, acct.daily_invite_cap, acct.weekly_invite_cap,
             acct.daily_message_cap, acct.status.value, row["id"]))
        acct.id = row["id"]
    else:
        cur = conn.execute(
            """INSERT INTO accounts (name, provider, provider_account_id, daily_invite_cap,
               weekly_invite_cap, daily_message_cap, warmup_started_on, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (acct.name, acct.provider, acct.provider_account_id, acct.daily_invite_cap,
             acct.weekly_invite_cap, acct.daily_message_cap, acct.warmup_started_on,
             acct.status.value, acct.created_at))
        acct.id = cur.lastrowid
    _commit()
    return acct


def _row_to_account(r: sqlite3.Row) -> LinkedInAccount:
    return LinkedInAccount(
        id=r["id"], name=r["name"], provider=r["provider"],
        provider_account_id=r["provider_account_id"], daily_invite_cap=r["daily_invite_cap"],
        weekly_invite_cap=r["weekly_invite_cap"], daily_message_cap=r["daily_message_cap"],
        warmup_started_on=r["warmup_started_on"], status=AccountStatus(r["status"]),
        created_at=r["created_at"])


def list_accounts(active_only: bool = True) -> list[LinkedInAccount]:
    q = "SELECT * FROM accounts"
    if active_only:
        q += " WHERE status='active'"
    q += " ORDER BY id"
    return [_row_to_account(r) for r in get_conn().execute(q).fetchall()]


def get_account(account_id: int) -> LinkedInAccount | None:
    r = get_conn().execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
    return _row_to_account(r) if r else None


def mark_account_warmup_started(account_id: int, on: str | None = None) -> None:
    on = on or date.today().isoformat()
    get_conn().execute(
        "UPDATE accounts SET warmup_started_on=? WHERE id=? AND warmup_started_on IS NULL",
        (on, account_id))
    _commit()


def invites_today(account_id: int, on: str | None = None) -> int:
    on = on or date.today().isoformat()
    r = get_conn().execute(
        """SELECT COUNT(*) n FROM messages WHERE account_id=? AND kind='invite'
           AND status IN ('sent','replied') AND substr(sent_at,1,10)=?""",
        (account_id, on)).fetchone()
    return r["n"]


def invites_this_week(account_id: int) -> int:
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    r = get_conn().execute(
        """SELECT COUNT(*) n FROM messages WHERE account_id=? AND kind='invite'
           AND status IN ('sent','replied') AND sent_at >= ?""",
        (account_id, since)).fetchone()
    return r["n"]


def messages_today(account_id: int, on: str | None = None) -> int:
    on = on or date.today().isoformat()
    r = get_conn().execute(
        """SELECT COUNT(*) n FROM messages WHERE account_id=? AND kind='message'
           AND status IN ('sent','replied') AND substr(sent_at,1,10)=?""",
        (account_id, on)).fetchone()
    return r["n"]


# ---------------------------------------------------------------------------
# Campaigns / steps / variants
# ---------------------------------------------------------------------------
def create_campaign(campaign: Campaign) -> Campaign:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO campaigns (name, description, status, icp_min_score, created_at) VALUES (?,?,?,?,?)",
        (campaign.name, campaign.description, campaign.status.value, campaign.icp_min_score,
         campaign.created_at))
    campaign.id = cur.lastrowid
    for step in campaign.steps:
        step.campaign_id = campaign.id
        scur = conn.execute(
            "INSERT INTO sequence_steps (campaign_id, step_order, name, kind, angle, wait_days) VALUES (?,?,?,?,?,?)",
            (step.campaign_id, step.step_order, step.name, step.kind.value, step.angle, step.wait_days))
        step.id = scur.lastrowid
        for v in step.variants:
            v.step_id = step.id
            _insert_variant(conn, v)
    _commit()
    logger.info("Created campaign #%s '%s' (%d steps)", campaign.id, campaign.name, len(campaign.steps))
    return campaign


def _insert_variant(conn: sqlite3.Connection, v: Variant) -> Variant:
    cur = conn.execute(
        """INSERT INTO variants (step_id, name, angle, template, sent_count, reply_count,
           alpha, beta, is_winner, is_paused, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (v.step_id, v.name, v.angle, v.template, v.sent_count, v.reply_count, v.alpha, v.beta,
         int(v.is_winner), int(v.is_paused), v.created_at))
    v.id = cur.lastrowid
    return v


def add_variant(v: Variant) -> Variant:
    v = _insert_variant(get_conn(), v)
    _commit()
    return v


def _row_to_variant(r: sqlite3.Row) -> Variant:
    return Variant(
        id=r["id"], step_id=r["step_id"], name=r["name"], angle=r["angle"], template=r["template"],
        sent_count=r["sent_count"], reply_count=r["reply_count"], alpha=r["alpha"], beta=r["beta"],
        is_winner=bool(r["is_winner"]), is_paused=bool(r["is_paused"]), created_at=r["created_at"])


def get_step_variants(step_id: int, include_paused: bool = False) -> list[Variant]:
    q = "SELECT * FROM variants WHERE step_id=?"
    if not include_paused:
        q += " AND is_paused=0"
    q += " ORDER BY id"
    return [_row_to_variant(r) for r in get_conn().execute(q, (step_id,)).fetchall()]


def update_variant_stats(variant_id: int, *, sent_delta: int = 0, reply_delta: int = 0) -> None:
    failures = sent_delta - reply_delta
    get_conn().execute(
        """UPDATE variants SET sent_count=sent_count+?, reply_count=reply_count+?,
           alpha=alpha+?, beta=beta+? WHERE id=?""",
        (sent_delta, reply_delta, reply_delta, failures, variant_id))
    _commit()


def promote_variant(step_id: int, winner_id: int) -> None:
    conn = get_conn()
    conn.execute("UPDATE variants SET is_winner=0, is_paused=1 WHERE step_id=?", (step_id,))
    conn.execute("UPDATE variants SET is_winner=1, is_paused=0 WHERE id=?", (winner_id,))
    _commit()


def get_campaign_by_name(name: str) -> Campaign | None:
    r = get_conn().execute("SELECT * FROM campaigns WHERE name=?", (name,)).fetchone()
    return _load_campaign(r) if r else None


def get_campaign(campaign_id: int) -> Campaign | None:
    r = get_conn().execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
    return _load_campaign(r) if r else None


def list_campaigns(status: CampaignStatus | None = None) -> list[Campaign]:
    q = "SELECT * FROM campaigns"
    params: list[Any] = []
    if status is not None:
        q += " WHERE status=?"
        params.append(status.value)
    q += " ORDER BY id"
    return [_load_campaign(r) for r in get_conn().execute(q, params).fetchall()]


def _load_campaign(r: sqlite3.Row) -> Campaign:
    conn = get_conn()
    steps: list[SequenceStep] = []
    for sr in conn.execute(
        "SELECT * FROM sequence_steps WHERE campaign_id=? ORDER BY step_order", (r["id"],)).fetchall():
        variants = [_row_to_variant(vr) for vr in conn.execute(
            "SELECT * FROM variants WHERE step_id=? ORDER BY id", (sr["id"],)).fetchall()]
        steps.append(SequenceStep(
            id=sr["id"], campaign_id=sr["campaign_id"], step_order=sr["step_order"],
            name=sr["name"], kind=StepKind(sr["kind"]), angle=sr["angle"],
            wait_days=sr["wait_days"], variants=variants))
    return Campaign(
        id=r["id"], name=r["name"], description=r["description"],
        status=CampaignStatus(r["status"]), icp_min_score=r["icp_min_score"],
        created_at=r["created_at"], steps=steps)


def set_campaign_status(campaign_id: int, status: CampaignStatus) -> None:
    get_conn().execute("UPDATE campaigns SET status=? WHERE id=?", (status.value, campaign_id))
    _commit()


# ---------------------------------------------------------------------------
# Prospects
# ---------------------------------------------------------------------------
def enroll_prospect(p: Prospect) -> Prospect | None:
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO prospects (campaign_id, lead_slug, company, name, title, role_category,
               linkedin_url, email, status, current_step, account_id, next_action_at, invited_at,
               accepted_at, last_action_at, replied_at, enrolled_at, context)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p.campaign_id, p.lead_slug, p.company, p.name, p.title, p.role_category, p.linkedin_url,
             p.email, p.status.value, p.current_step, p.account_id, p.next_action_at, p.invited_at,
             p.accepted_at, p.last_action_at, p.replied_at, p.enrolled_at,
             json.dumps(p.context, ensure_ascii=False)))
    except sqlite3.IntegrityError:
        return None
    p.id = cur.lastrowid
    _commit()
    return p


def _row_to_prospect(r: sqlite3.Row) -> Prospect:
    return Prospect(
        id=r["id"], campaign_id=r["campaign_id"], lead_slug=r["lead_slug"], company=r["company"],
        name=r["name"], title=r["title"], role_category=r["role_category"],
        linkedin_url=r["linkedin_url"], email=(r["email"] if "email" in r.keys() else ""),
        status=ProspectStatus(r["status"]),
        current_step=r["current_step"], account_id=r["account_id"], next_action_at=r["next_action_at"],
        invited_at=r["invited_at"], accepted_at=r["accepted_at"], last_action_at=r["last_action_at"],
        replied_at=r["replied_at"], enrolled_at=r["enrolled_at"], context=json.loads(r["context"] or "{}"))


def list_prospects(campaign_id: int, status: ProspectStatus | None = None) -> list[Prospect]:
    q = "SELECT * FROM prospects WHERE campaign_id=?"
    params: list[Any] = [campaign_id]
    if status is not None:
        q += " AND status=?"
        params.append(status.value)
    q += " ORDER BY id"
    return [_row_to_prospect(r) for r in get_conn().execute(q, params).fetchall()]


def get_prospect(prospect_id: int) -> Prospect | None:
    r = get_conn().execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    return _row_to_prospect(r) if r else None


def prospects_by_status(status: ProspectStatus, campaign_id: int | None = None) -> list[Prospect]:
    q = "SELECT * FROM prospects WHERE status=?"
    params: list[Any] = [status.value]
    if campaign_id is not None:
        q += " AND campaign_id=?"
        params.append(campaign_id)
    q += " ORDER BY id"
    return [_row_to_prospect(r) for r in get_conn().execute(q, params).fetchall()]


def due_prospects(now_iso: str, statuses: tuple[str, ...], campaign_id: int | None = None) -> list[Prospect]:
    placeholders = ",".join("?" for _ in statuses)
    q = (f"SELECT * FROM prospects WHERE status IN ({placeholders}) "
         f"AND (next_action_at IS NULL OR next_action_at <= ?)")
    params: list[Any] = [*statuses, now_iso]
    if campaign_id is not None:
        q += " AND campaign_id=?"
        params.append(campaign_id)
    q += " ORDER BY next_action_at IS NULL DESC, next_action_at ASC, id ASC"
    return [_row_to_prospect(r) for r in get_conn().execute(q, params).fetchall()]


def find_prospect_by_url(linkedin_url: str) -> Prospect | None:
    r = get_conn().execute(
        "SELECT * FROM prospects WHERE linkedin_url=? ORDER BY id LIMIT 1", (linkedin_url,)).fetchone()
    return _row_to_prospect(r) if r else None


def find_prospect_by_slug(slug: str) -> Prospect | None:
    """Match a prospect by the LinkedIn ``/in/<slug>`` handle — robust to URL
    format differences (www vs country subdomain, trailing slash, query)."""
    if not slug:
        return None
    r = get_conn().execute(
        "SELECT * FROM prospects WHERE linkedin_url LIKE ? ORDER BY id LIMIT 1",
        (f"%/in/{slug}%",)).fetchone()
    return _row_to_prospect(r) if r else None


def update_prospect(prospect_id: int, **fields: Any) -> None:
    if not fields:
        return
    cols, params = [], []
    for k, v in fields.items():
        if hasattr(v, "value"):
            v = v.value
        if k == "context" and isinstance(v, dict):
            v = json.dumps(v, ensure_ascii=False)
        cols.append(f"{k}=?")
        params.append(v)
    params.append(prospect_id)
    get_conn().execute(f"UPDATE prospects SET {', '.join(cols)} WHERE id=?", params)
    _commit()


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
def create_message(m: ConnectMessage) -> ConnectMessage:
    cur = get_conn().execute(
        """INSERT INTO messages (prospect_id, campaign_id, step_id, variant_id, account_id, kind,
           body, provider_ref, status, error, queued_at, sent_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (m.prospect_id, m.campaign_id, m.step_id, m.variant_id, m.account_id, m.kind.value,
         m.body, m.provider_ref, m.status.value, m.error, m.queued_at, m.sent_at))
    m.id = cur.lastrowid
    _commit()
    return m


def _row_to_message(r: sqlite3.Row) -> ConnectMessage:
    return ConnectMessage(
        id=r["id"], prospect_id=r["prospect_id"], campaign_id=r["campaign_id"], step_id=r["step_id"],
        variant_id=r["variant_id"], account_id=r["account_id"], kind=MessageKind(r["kind"]),
        body=r["body"], provider_ref=r["provider_ref"], status=MessageStatus(r["status"]),
        error=r["error"], queued_at=r["queued_at"], sent_at=r["sent_at"])


def update_message(message_id: int, **fields: Any) -> None:
    if not fields:
        return
    cols, params = [], []
    for k, v in fields.items():
        if hasattr(v, "value"):
            v = v.value
        cols.append(f"{k}=?")
        params.append(v)
    params.append(message_id)
    get_conn().execute(f"UPDATE messages SET {', '.join(cols)} WHERE id=?", params)
    _commit()


def messages_for_prospect(prospect_id: int) -> list[ConnectMessage]:
    rows = get_conn().execute(
        "SELECT * FROM messages WHERE prospect_id=? ORDER BY id", (prospect_id,)).fetchall()
    return [_row_to_message(r) for r in rows]


def count_conversation_messages(prospect_id: int) -> int:
    r = get_conn().execute(
        """SELECT COUNT(*) n FROM messages WHERE prospect_id=? AND step_id IS NULL
           AND kind='message' AND status IN ('sent','replied')""", (prospect_id,)).fetchone()
    return r["n"]


# ---------------------------------------------------------------------------
# Replies
# ---------------------------------------------------------------------------
def save_reply(reply: Reply) -> Reply | None:
    try:
        cur = get_conn().execute(
            """INSERT INTO replies (prospect_id, body, received_at, provider_id, classification,
               classification_confidence, resume_at) VALUES (?,?,?,?,?,?,?)""",
            (reply.prospect_id, reply.body, reply.received_at, reply.provider_id,
             reply.classification.value, reply.classification_confidence, reply.resume_at))
    except sqlite3.IntegrityError:
        return None
    reply.id = cur.lastrowid
    _commit()
    return reply


def reply_id_seen(provider_id: str) -> bool:
    r = get_conn().execute("SELECT 1 FROM replies WHERE provider_id=?", (provider_id,)).fetchone()
    return r is not None


def replies_for_prospect(prospect_id: int) -> list[Reply]:
    rows = get_conn().execute(
        "SELECT * FROM replies WHERE prospect_id=? ORDER BY received_at, id", (prospect_id,)).fetchall()
    return [Reply(id=r["id"], prospect_id=r["prospect_id"], body=r["body"], received_at=r["received_at"],
                  provider_id=r["provider_id"], classification=ReplyClass(r["classification"]),
                  classification_confidence=r["classification_confidence"], resume_at=r["resume_at"])
            for r in rows]


# ---------------------------------------------------------------------------
# Events + kv
# ---------------------------------------------------------------------------
def log_event(type: str, *, prospect_id: int | None = None,
              campaign_id: int | None = None, data: dict | None = None) -> None:
    get_conn().execute(
        "INSERT INTO events (prospect_id, campaign_id, type, data, created_at) VALUES (?,?,?,?,?)",
        (prospect_id, campaign_id, type, json.dumps(data or {}, ensure_ascii=False), utcnow_iso()))
    _commit()


def kv_get(key: str, default: str | None = None) -> str | None:
    r = get_conn().execute("SELECT value FROM kv_state WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def kv_set(key: str, value: str) -> None:
    get_conn().execute(
        "INSERT INTO kv_state (key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, utcnow_iso()))
    _commit()
