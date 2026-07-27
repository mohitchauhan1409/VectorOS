"""Database engine & session management for the Vector backend.

Single SQLite database, tuned for concurrent read-heavy access from the API
while the orchestrator writes results of live engine runs. This replaces the
old per-company JSON files and the separate inbox.db / connect.db stores.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# DB lives under the repo's data/ dir (gitignored) unless overridden.
_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "vector.db"
DB_PATH = Path(os.getenv("VECTOR_DB_PATH", str(_DEFAULT_PATH)))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
    """Enable the pragmas that make SQLite fast and safe under concurrency."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.execute("PRAGMA temp_store=MEMORY")
    cur.execute("PRAGMA cache_size=-16000")  # ~16MB page cache
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first release. `create_all` only creates missing
# TABLES, never missing columns, and there's no Alembic in this project — so
# additive schema changes are declared here and applied on every boot.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("campaigns", "send_mode", "VARCHAR(20) DEFAULT 'manual'"),
    ("enrollments", "launched_at", "DATETIME"),
    ("enrollments", "launched_by", "VARCHAR(200)"),
    ("companies", "intent_score", "INTEGER DEFAULT 0"),
    ("companies", "signal_age_days", "INTEGER DEFAULT 0"),
)


def _migrate(conn) -> None:  # noqa: ANN001
    """Add any missing columns in place (idempotent, data-preserving)."""
    from sqlalchemy import text

    existing = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    for table, column, ddl in _ADDED_COLUMNS:
        if table not in existing:
            continue  # create_all will build it with the column already present
        cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
        if column not in cols:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def init_db() -> None:
    """Create all tables and apply additive column migrations (idempotent)."""
    from backend import models  # noqa: F401  (register mappers)

    with engine.begin() as conn:
        _migrate(conn)
    Base.metadata.create_all(engine)
