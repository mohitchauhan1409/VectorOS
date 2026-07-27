"""Backend management CLI — the only way to create accounts and run the engine.

    python -m backend.manage list
    python -m backend.manage create-account --email team@vector.ai --password vector123 --name "Vector Team"
    python -m backend.manage run-pipeline --email team@vector.ai --max-leads 6
    python -m backend.manage seed-demo

Signup is disabled in the API on purpose; provision accounts here.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from backend.accounts import create_account
from backend.db import SessionLocal, init_db
from backend.models import Company, Person, PipelineRun, User, Workspace
from backend.orchestrator import run_pipeline
from backend.seed import seed_demo


def _cmd_list(_args) -> None:
    db = SessionLocal()
    users = db.scalars(select(User).order_by(User.id)).all()
    if not users:
        print("No accounts yet.")
    for u in users:
        ws = db.get(Workspace, u.workspace_id)
        n_comp = db.scalar(select(Company).where(Company.workspace_id == u.workspace_id).limit(1))
        n_people = db.query(Person).filter(Person.workspace_id == u.workspace_id).count()
        n_companies = db.query(Company).filter(Company.workspace_id == u.workspace_id).count()
        tag = "demo" if u.is_demo else "live"
        print(f"  [{u.id}] {u.email:28s} {tag:5s} ws={ws.name!r:24s} companies={n_companies} people={n_people}")
    db.close()


def _cmd_create(args) -> None:
    db = SessionLocal()
    try:
        user = create_account(
            db,
            email=args.email,
            password=args.password,
            name=args.name,
            workspace_name=args.workspace,
            is_demo=args.demo,
        )
        print(f"Created account [{user.id}] {user.email} (workspace {user.workspace_id}, demo={user.is_demo})")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def _cmd_run(args) -> None:
    db = SessionLocal()
    user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
    if not user:
        print(f"No account for {args.email}", file=sys.stderr)
        sys.exit(1)
    if user.is_demo:
        print("Refusing to run the live engine on the demo account.", file=sys.stderr)
        sys.exit(1)
    run = PipelineRun(workspace_id=user.workspace_id, status="running", stage="queued", mode="live")
    db.add(run)
    db.commit()
    run_id = run.id
    ws_id = user.workspace_id
    db.close()

    print(f"Running live pipeline for {args.email} (max_leads={args.max_leads})… this can take a few minutes.")
    run_pipeline(ws_id, run_id, args.max_leads)

    db = SessionLocal()
    r = db.get(PipelineRun, run_id)
    print(f"Run {r.id}: status={r.status} stage={r.stage} "
          f"companies={r.companies_found} people={r.people_found} "
          f"enrolled={r.enrolled} messages={r.messages_sent}")
    if r.error:
        print(f"  error: {r.error}", file=sys.stderr)
    db.close()


def _cmd_seed(args) -> None:
    db = SessionLocal()
    if getattr(args, "force", False):
        existing = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
        if existing:
            db.delete(existing)  # cascades to every demo row; real workspaces untouched
            db.commit()
            print("Dropped the existing demo workspace.")
    ws = seed_demo(db)
    print(f"Demo workspace ready: {ws.name} (id={ws.id})")
    db.close()


def _cmd_config(_args) -> None:
    """Show the single control panel — every switch/knob for the engine."""
    from modules.common import control
    print("Vector control panel (modules/common/control.py)\n")
    print(f"  MODE: {control.mode_label()}\n")
    groups = {
        "Safety / providers": [
            ("PULSE_LIVE", control.PULSE_LIVE), ("CONNECT_PROVIDER", control.CONNECT_PROVIDER),
            ("CALENDAR_PROVIDER", control.CALENDAR_PROVIDER), ("EMAIL_DRY_RUN", control.EMAIL_DRY_RUN),
        ],
        "Scout": [
            ("RADAR_MIN_ICP_SCORE", control.RADAR_MIN_ICP_SCORE),
            ("EMAIL_PROVIDER", control.EMAIL_PROVIDER),
            ("EMAIL_PATTERN_FALLBACK", control.EMAIL_PATTERN_FALLBACK),
            ("EMAIL_SMTP_VERIFY", control.EMAIL_SMTP_VERIFY),
            ("DETECTIVE_MAX_DECISION_MAKERS_PER_COMPANY", control.DETECTIVE_MAX_DECISION_MAKERS_PER_COMPANY),
        ],
        "Pulse · Email": [
            ("EMAIL_WARMUP_ENABLED", control.EMAIL_WARMUP_ENABLED),
            ("EMAIL_WARMUP_START/INCREMENT/CAP", f"{control.EMAIL_WARMUP_START}/{control.EMAIL_WARMUP_INCREMENT}/{control.EMAIL_DEFAULT_DAILY_CAP}"),
            ("EMAIL_SEND_WINDOW", f"{control.EMAIL_SEND_WINDOW_START_HOUR}-{control.EMAIL_SEND_WINDOW_END_HOUR}"),
            ("ALLOW_GUESSED_EMAILS", control.ALLOW_GUESSED_EMAILS),
            ("EMAIL_MIN_SENDS_BEFORE_PROMOTION", control.EMAIL_MIN_SENDS_BEFORE_PROMOTION),
        ],
        "Pulse · LinkedIn": [
            ("LINKEDIN_WARMUP_START/INCREMENT", f"{control.LINKEDIN_WARMUP_START}/{control.LINKEDIN_WARMUP_INCREMENT}"),
            ("LINKEDIN_DAILY/WEEKLY_INVITE_CAP", f"{control.LINKEDIN_DAILY_INVITE_CAP}/{control.LINKEDIN_WEEKLY_INVITE_CAP}"),
            ("LINKEDIN_INVITE_EXPIRY_DAYS", control.LINKEDIN_INVITE_EXPIRY_DAYS),
        ],
        "Conversation / Scheduling": [
            ("AUTO_REPLY_ENABLED", control.AUTO_REPLY_ENABLED),
            ("MAX_AUTO_REPLIES", control.MAX_AUTO_REPLIES),
            ("MEETING_SLOTS_TO_OFFER", control.MEETING_SLOTS_TO_OFFER),
            ("MEETING_DURATION_MIN", control.MEETING_DURATION_MIN),
        ],
        "LLM": [("NORMAL_LLM", control.NORMAL_LLM["model"]), ("HIGH_EFFORT_LLM", control.HIGH_EFFORT_LLM["model"])],
    }
    for group, items in groups.items():
        print(f"  {group}")
        for k, v in items:
            print(f"    {k:42s} = {v}")
        print()


def main() -> None:
    init_db()
    parser = argparse.ArgumentParser(prog="backend.manage")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=_cmd_list)
    sub.add_parser("config").set_defaults(func=_cmd_config)

    s = sub.add_parser("seed-demo")
    s.add_argument("--force", action="store_true", help="drop and rebuild the demo workspace")
    s.set_defaults(func=_cmd_seed)

    c = sub.add_parser("create-account")
    c.add_argument("--email", required=True)
    c.add_argument("--password", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--workspace", default=None)
    c.add_argument("--demo", action="store_true")
    c.set_defaults(func=_cmd_create)

    r = sub.add_parser("run-pipeline")
    r.add_argument("--email", required=True)
    r.add_argument("--max-leads", type=int, default=6)
    r.set_defaults(func=_cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
