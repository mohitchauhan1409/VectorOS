"""Test the wired Pulse autonomy on dummy data — SAFE mode, nothing is sent.

Run:  VECTOR_DB_PATH=/tmp/vtest_pulse.db python -m scripts.test_pulse_wiring

Exercises, against the sample leads in data/Leads/*.json:
  • enrollment from Scout output (email + LinkedIn)
  • multi-step sequencing across simulated days (Scheduler + wait_days)
  • warmup ramp (10 → +5/day) and daily caps
  • Thompson-sampling A/B variant selection + promotion wiring
  • LinkedIn invite → (mock) accept → message gate
  • reply → conversation → meeting booking (mock calendar)  [best-effort, uses LLM]
  • sync of all engine state into the unified DB for the CRM
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

# ---- SAFE MODE must be set before importing any pulse module ----
os.environ["VECTOR_PULSE_LIVE"] = "0"
os.environ["PULSE_CONNECT_PROVIDER"] = "mock"
os.environ["PULSE_CALENDAR_PROVIDER"] = "mock"
os.environ["PULSE_AUTO_REPLY"] = "true"  # so the meeting-booking chain can act (mock/dry only)

from backend import pulse_runtime  # noqa: E402
pulse_runtime.apply_safe_env()

from backend.db import SessionLocal, init_db  # noqa: E402
from backend.models import (  # noqa: E402
    Campaign, Enrollment, LinkedInAccount, Mailbox, Meeting, Message, Sequence, Workspace,
)
from backend import pulse_sync  # noqa: E402
from backend.orchestrator import pulse_cycle, PULSE_CAMPAIGN_NAME  # noqa: E402

from modules.pulse.inbox import enrollment as ibx_enroll, store as ibx_store  # noqa: E402
from modules.pulse.inbox.schemas import CampaignStatus as IbxStatus  # noqa: E402
from modules.pulse.inbox.delivery import accounts as ibx_accounts  # noqa: E402
from modules.pulse.connect import enrollment as cnx_enroll, store as cnx_store  # noqa: E402
from modules.pulse.connect.schemas import CampaignStatus as CnxStatus  # noqa: E402
from sqlalchemy import select, func  # noqa: E402

PASS, FAIL = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{PASS if ok else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def main() -> None:
    print(f"\nPulse wiring test · mode = {pulse_runtime.mode_label()}\n")

    # Clean engine stores for a deterministic run.
    ibx_store.reset_db()
    cnx_store.reset_db()

    init_db()
    db = SessionLocal()
    ws = Workspace(name="Pulse Test", is_demo=False)
    db.add(ws)
    db.commit()
    ws_id = ws.id

    # --- build + enroll from the sample leads ---
    ibx_enroll.sync_mailboxes_from_env()
    cnx_enroll.sync_account()
    email_camp = ibx_enroll.build_campaign(PULSE_CAMPAIGN_NAME, icp_min_score=35)
    li_camp = cnx_enroll.build_campaign(PULSE_CAMPAIGN_NAME, icp_min_score=35)
    ibx_store.set_campaign_status(email_camp.id, IbxStatus.ACTIVE)
    cnx_store.set_campaign_status(li_camp.id, CnxStatus.ACTIVE)
    e_res = ibx_enroll.enroll_campaign(email_camp, icp_min_score=35)
    l_res = cnx_enroll.enroll_campaign(li_camp, icp_min_score=35)
    print(f"Enrolled — email: {e_res.get('enrolled')} · linkedin: {l_res.get('enrolled')}")
    check("email enrollment produced recipients", (e_res.get("enrolled") or 0) > 0)
    check("linkedin enrollment produced prospects", (l_res.get("enrolled") or 0) > 0)

    # --- run several autopilot cycles across simulated days ---
    clock = {"t": datetime.now(timezone.utc)}
    for day in range(5):
        clock["t"] = datetime.now(timezone.utc) + timedelta(days=day * 5)
        pulse_cycle(email_camp.id, li_camp.id, now_fn=lambda: clock["t"])

    # --- assert multi-step progression ---
    recips = ibx_store.list_recipients(email_camp.id)
    max_email_step = max((r.current_step for r in recips), default=0)
    check("email advanced past step 1 (multi-step sequencing)", max_email_step >= 2,
          f"max step reached = {max_email_step}")

    prospects = cnx_store.list_prospects(li_camp.id)
    accepted = [p for p in prospects if p.accepted_at]
    messaged = [p for p in prospects if p.current_step >= 2]
    check("linkedin invites were accepted (mock) ", len(accepted) > 0, f"{len(accepted)} accepted")
    check("linkedin messaged after accept (gate works)", len(messaged) > 0, f"{len(messaged)} messaged")

    # --- warmup ramp formula: day 0 = 10, +5/day, capped at 40 ---
    from datetime import date
    from modules.pulse.inbox.schemas import Mailbox as IbxMailbox
    check("a mailbox exists (from env)", len(ibx_store.list_mailboxes(active_only=False)) > 0)
    ramp = [
        ibx_accounts.daily_allowance(
            IbxMailbox(email="x@y.com", daily_cap=40,
                       warmup_started_on=(date.today() - timedelta(days=d)).isoformat()))
        for d in range(7)
    ]
    check("warmup ramp = 10,15,20,25,30,35,40", ramp == [10, 15, 20, 25, 30, 35, 40], f"ramp = {ramp}")

    # --- reply → conversation → meeting (best-effort; uses LLM + mock calendar) ---
    meeting_ok = False
    try:
        from modules.pulse.connect.delivery import dispatcher as cnx_dispatcher
        from modules.pulse.connect.providers import get_provider
        target = next((p for p in prospects if p.accepted_at), None)
        if target:
            get_provider().queue_reply(target.linkedin_url, "Sounds interesting — can we grab 30 min next week?")
            cnx_dispatcher.poll_replies(dry_run=False)
            p2 = cnx_store.get_prospect(target.id)
            meeting_ok = p2.status.value in ("meeting", "booked")
            check("reply handled → conversation/scheduling ran", p2.status.value not in ("accepted",),
                  f"status now = {p2.status.value}")
    except Exception as e:  # noqa: BLE001
        check("reply→meeting chain (LLM/mock)", False, f"skipped: {type(e).__name__}: {e}")

    # --- sync into the unified DB and verify the CRM would see it ---
    sync_res = pulse_sync.sync_workspace(db, ws_id, campaign_name=PULSE_CAMPAIGN_NAME)
    print(f"\nSynced to unified DB: {sync_res}")

    camp = db.scalar(select(Campaign).where(Campaign.workspace_id == ws_id))
    seqs = db.scalars(select(Sequence).where(Sequence.campaign_id == camp.id)).all() if camp else []
    n_enroll = db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.workspace_id == ws_id))
    n_msg = db.scalar(select(func.count()).select_from(Message).where(Message.workspace_id == ws_id))
    n_mb = db.scalar(select(func.count()).select_from(Mailbox).where(Mailbox.workspace_id == ws_id))
    n_li = db.scalar(select(func.count()).select_from(LinkedInAccount).where(LinkedInAccount.workspace_id == ws_id))
    n_meet = db.scalar(select(func.count()).select_from(Meeting).where(Meeting.workspace_id == ws_id))

    check("unified: 1 campaign with 2 sequences (email+linkedin)", camp is not None and len(seqs) == 2,
          f"sequences = {sorted(s.channel for s in seqs)}")
    check("unified: enrollments synced", (n_enroll or 0) > 0, f"{n_enroll}")
    check("unified: messages synced", (n_msg or 0) > 0, f"{n_msg}")
    check("unified: mailbox capacity synced", (n_mb or 0) > 0, f"{n_mb}")
    check("unified: linkedin account synced", (n_li or 0) > 0, f"{n_li}")
    if meeting_ok:
        check("unified: meeting synced", (n_meet or 0) > 0, f"{n_meet}")

    db.close()

    print(f"\n{sum(results)}/{len(results)} checks passed.\n")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
