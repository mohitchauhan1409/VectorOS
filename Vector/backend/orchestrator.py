"""End-to-end GTM orchestration.

Ties the previously-separate modules into one live pipeline and persists
everything into the unified SQLite DB (no more per-company JSON, no separate
inbox.db/connect.db):

    Scout.radar  -> find companies + buying signals   (live: LLM + news scrape)
    Scout.detective -> find + enrich decision-makers  (live: search + email)
    Pulse        -> build a campaign (email + LinkedIn sequences), enroll
                    contactable people, stage first-touch messages

Runs are tracked in the pipeline_runs table so the UI can show progress.
Real accounts trigger this; the demo account is pre-seeded instead.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db import SessionLocal
from backend.models import (
    Campaign,
    Company,
    Enrollment,
    Event,
    ICPCriterion,
    Message,
    Person,
    PipelineRun,
    Sequence,
    SequenceStep,
    Variant,
)

# Name used for the workspace's default multi-channel campaign. The engine's
# inbox + connect stores each get a campaign under this name; the sync layer
# pairs them into one unified Campaign with an email + a LinkedIn sequence.
PULSE_CAMPAIGN_NAME = "Outbound — Qualified Leads"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


# --------------------------------------------------------------------------- #
# Public entry
# --------------------------------------------------------------------------- #

def run_pipeline(workspace_id: int, run_id: int, max_leads: int = 10) -> None:
    """Execute a full live pipeline for a workspace. Runs in a background thread.

    Pulse runs in whatever mode backend.pulse_runtime dictates (SAFE by default:
    dry-run email + mock LinkedIn/calendar — nothing is actually sent)."""
    from backend import pulse_runtime

    pulse_runtime.apply_safe_env()  # must run before importing modules.pulse.*

    db = SessionLocal()
    run = db.get(PipelineRun, run_id)
    try:
        _set(db, run, stage="scout_radar")
        _run_scout(db, workspace_id, run, max_leads)

        _set(db, run, stage="pulse_outreach")
        enrolled, messaged = _run_pulse(db, workspace_id, run)
        run.enrolled = enrolled
        run.messages_sent = messaged

        run.status = "succeeded"
        run.stage = "done"
        run.finished_at = _now()
        db.commit()
    except Exception as exc:  # noqa: BLE001 — surface any engine/keys/network failure
        db.rollback()
        run = db.get(PipelineRun, run_id)
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"[:2000]
        run.finished_at = _now()
        db.commit()
    finally:
        db.close()


def _set(db: Session, run: PipelineRun, **fields) -> None:
    for k, v in fields.items():
        setattr(run, k, v)
    db.commit()


# --------------------------------------------------------------------------- #
# Scout — live radar + detective, imported into the unified DB
# --------------------------------------------------------------------------- #

def _run_scout(db: Session, workspace_id: int, run: PipelineRun, max_leads: int) -> int:
    """Run the live news radar + detective, importing each result into the DB."""
    # Lazy import — keeps the API bootable even if engine deps are heavy.
    from modules.scout.radar.NewsRadar.pipeline import NewsRadarPipeline
    from modules.scout.radar.config import MIN_ICP_SCORE

    found = 0
    run_slugs: set[str] = set()

    def on_lead(lead) -> None:  # noqa: ANN001 — engine Lead pydantic model
        nonlocal found
        company = _upsert_company_from_lead(db, workspace_id, lead)
        run_slugs.add(company.slug)
        found += 1
        run.companies_found = found
        db.commit()

    radar = NewsRadarPipeline(save_floor=MIN_ICP_SCORE)
    radar.run(max_leads=max_leads, on_lead=on_lead)

    # Detective enriches the JSON leads with decision-makers; then import only the
    # companies THIS run discovered (the engine's leads dir may hold prior runs).
    _set(db, run, stage="scout_detective")
    from modules.scout.detective.pipeline import DetectivePipeline
    from modules.scout.detective import store as det_store

    DetectivePipeline(dry_run=False).run(max_companies=max_leads, only_qualified=True)

    people_found = 0
    for record in det_store.load_qualified_leads(only_qualified=True):
        slug = record.get("company_slug") or record.get("slug")
        if run_slugs and slug not in run_slugs:
            continue
        company = _upsert_company_from_record(db, workspace_id, record)
        for dm in record.get("decision_makers", []):
            if _upsert_person(db, workspace_id, company, dm):
                people_found += 1
    run.people_found = people_found
    db.commit()
    return found


def _upsert_company_from_lead(db: Session, ws: int, lead) -> Company:  # noqa: ANN001
    data = lead.model_dump(mode="json") if hasattr(lead, "model_dump") else dict(lead)
    return _upsert_company_from_record(db, ws, data)


def _upsert_company_from_record(db: Session, ws: int, rec: dict) -> Company:
    slug = rec.get("company_slug") or rec.get("slug") or (rec.get("company_name", "").lower().replace(" ", "-"))
    company = db.scalar(
        select(Company).where(Company.workspace_id == ws, Company.slug == slug)
    )
    icp = rec.get("icp", {}) or {}
    if not company:
        company = Company(workspace_id=ws, slug=slug, name=rec.get("company_name", slug))
        db.add(company)
    company.name = rec.get("company_name", company.name)
    company.website_url = rec.get("website_url")
    company.linkedin_url = rec.get("linkedin_url")
    company.signal_type = rec.get("signal_type", "other")
    company.reason_to_target = rec.get("reason_to_target")
    company.confidence = rec.get("confidence", 0.0) or 0.0
    company.icp_score = int(icp.get("score", 0) or 0)
    company.icp_tier = icp.get("tier", "D") or "D"
    company.icp_rationale = icp.get("rationale", "") or ""
    company.qualified = bool(rec.get("qualified", company.icp_score >= 35))
    company.source_radar = rec.get("source_radar", "news")
    company.source_name = rec.get("source_name", "")
    company.article_headline = rec.get("article_headline", "")
    company.article_url = rec.get("article_url", "")
    company.published_date = rec.get("published_date")
    if not company.industry:
        company.industry = rec.get("industry", "")
    # carry the real discovery timestamp from the engine when present
    disc = rec.get("discovered_at")
    if disc:
        parsed = _parse_iso(disc)
        if parsed:
            company.discovered_at = parsed
    db.flush()

    # refresh criteria
    if icp:
        db.query(ICPCriterion).filter(ICPCriterion.company_id == company.id).delete()
        for t in icp.get("matched_criteria", []) or []:
            db.add(ICPCriterion(company_id=company.id, kind="matched", text=t))
        for t in icp.get("concerns", []) or []:
            db.add(ICPCriterion(company_id=company.id, kind="concern", text=t))

    # merge signals (by article_url)
    existing_urls = {s.article_url for s in company.signals}
    signals = rec.get("signals") or [
        {
            "signal_type": rec.get("signal_type"),
            "reason_to_target": rec.get("reason_to_target"),
            "confidence": rec.get("confidence"),
            "article_headline": rec.get("article_headline"),
            "article_url": rec.get("article_url"),
            "published_date": rec.get("published_date"),
            "source_name": rec.get("source_name"),
        }
    ]
    from backend.models import Signal

    for s in signals:
        if s.get("article_url") in existing_urls:
            continue
        sig = Signal(
            signal_type=s.get("signal_type", "other") or "other",
            reason_to_target=s.get("reason_to_target"),
            confidence=s.get("confidence", 0.0) or 0.0,
            article_headline=s.get("article_headline", "") or "",
            article_url=s.get("article_url", "") or "",
            published_date=s.get("published_date"),
            source_name=s.get("source_name", "") or "",
        )
        sdisc = _parse_iso(s.get("discovered_at"))
        if sdisc:
            sig.discovered_at = sdisc
        company.signals.append(sig)
    db.flush()
    return company


def _upsert_person(db: Session, ws: int, company: Company, dm: dict) -> bool:
    name = dm.get("name", "").strip()
    if not name:
        return False
    existing = db.scalar(
        select(Person).where(
            Person.workspace_id == ws, Person.company_id == company.id, Person.name == name
        )
    )
    is_new = existing is None
    p = existing or Person(workspace_id=ws, company_id=company.id, name=name)
    p.title = dm.get("title", "") or ""
    p.role_category = dm.get("role_category", "") or ""
    p.linkedin_url = dm.get("linkedin_url", "") or ""
    p.confidence = dm.get("confidence", 0.0) or 0.0
    p.email = dm.get("email")
    p.email_status = dm.get("email_status")
    p.email_source = dm.get("email_source")
    p.apollo_id = dm.get("apollo_id")
    p.city = dm.get("city")
    p.country = dm.get("country")
    p.enriched = bool(dm.get("enriched", False))
    if is_new:
        db.add(p)
        db.flush()
        db.add(Event(
            workspace_id=ws, person_id=p.id, company_id=company.id, type="decision_maker_found",
            title=f"Identified as {p.role_category or 'contact'} at {company.name}",
            detail=f"Scout matched {p.name} with {round(p.confidence * 100)}% confidence.",
        ))
    return is_new


# --------------------------------------------------------------------------- #
# Pulse — drive the REAL engine (enrollment + scheduler + warmup/caps + bandit
# + acceptance sync + reply/conversation + A/B promotion), then sync to the UI.
# Runs in SAFE mode by default (dry-run email, mock LinkedIn/calendar).
# --------------------------------------------------------------------------- #

def _run_pulse(db: Session, ws: int, run: PipelineRun) -> tuple[int, int]:
    from backend import pulse_runtime, pulse_sync
    from modules.pulse.inbox import enrollment as ibx_enroll, store as ibx_store
    from modules.pulse.inbox.schemas import CampaignStatus as IbxStatus
    from modules.pulse.connect import enrollment as cnx_enroll, store as cnx_store
    from modules.pulse.connect.schemas import CampaignStatus as CnxStatus

    icp_min = 35

    # 1) Register the sending accounts (mailbox pool + LinkedIn account) from env.
    ibx_enroll.sync_mailboxes_from_env()
    cnx_enroll.sync_account()

    # 2) Build the campaign on each channel (idempotent by name) and activate.
    email_camp = ibx_enroll.build_campaign(
        PULSE_CAMPAIGN_NAME, description="Multi-channel outreach built and run by Pulse.",
        icp_min_score=icp_min)
    li_camp = cnx_enroll.build_campaign(
        PULSE_CAMPAIGN_NAME, description="Multi-channel outreach built and run by Pulse.",
        icp_min_score=icp_min)
    ibx_store.set_campaign_status(email_camp.id, IbxStatus.ACTIVE)
    cnx_store.set_campaign_status(li_camp.id, CnxStatus.ACTIVE)

    # 3) Enroll contactable decision-makers from Scout output (JSON leads).
    ibx_enroll.enroll_campaign(email_camp, icp_min_score=icp_min)
    cnx_enroll.enroll_campaign(li_camp, icp_min_score=icp_min)

    # 4) Run ONE autopilot cycle (send/act pass). Multi-day sequencing continues
    #    on subsequent runs; warmup/caps/window are enforced by the engine.
    #    In manual sending mode the gate below holds every un-approved first touch.
    gate = build_send_gate(db, ws)
    pulse_cycle(email_camp.id, li_camp.id, gate=gate)

    # 5) Mirror the engine's live Pulse state into the unified DB for the CRM.
    res = pulse_sync.sync_workspace(db, ws, campaign_name=PULSE_CAMPAIGN_NAME)
    return res.get("enrollments", 0), res.get("messages", 0)


class SendGate:
    """Enforces the CRM's manual sending mode inside the engine's schedulers.

    Manual mode holds the FIRST touch only: a person mid-sequence keeps flowing,
    because the human already approved them once. Anyone still at step 0 is held
    until someone releases them in the CRM.
    """

    def __init__(self, *, manual: bool, emails: set[str], linkedin: set[str]) -> None:
        self.manual = manual
        self.emails = emails
        self.linkedin = linkedin

    def allow_recipient(self, rec) -> bool:  # noqa: ANN001 — engine Recipient
        if not self.manual or rec.current_step >= 1:
            return True
        return (rec.email or "").strip().lower() in self.emails

    def allow_prospect(self, p) -> bool:  # noqa: ANN001 — engine Prospect
        if not self.manual or p.current_step >= 1:
            return True
        return (p.linkedin_url or "").split("?")[0].rstrip("/").lower() in self.linkedin


def build_send_gate(db: Session, workspace_id: int) -> SendGate:
    """Read the workspace's sending mode + released people out of the CRM DB."""
    from backend.models import Person

    mode = db.scalar(
        select(Campaign.send_mode).where(Campaign.workspace_id == workspace_id).limit(1)
    )
    rows = db.execute(
        select(Enrollment.channel, Person.email, Person.linkedin_url)
        .join(Person, Person.id == Enrollment.person_id)
        .where(
            Enrollment.workspace_id == workspace_id,
            Enrollment.launched_at.is_not(None),
        )
    ).all()
    emails = {(e or "").strip().lower() for ch, e, _ in rows if ch == "email" and e}
    linkedin = {
        (u or "").split("?")[0].rstrip("/").lower()
        for ch, _, u in rows
        if ch == "linkedin" and u
    }
    return SendGate(manual=(mode or "manual") == "manual", emails=emails, linkedin=linkedin)


def pulse_cycle(
    email_campaign_id: int, li_campaign_id: int, *, now_fn=None, gate: SendGate | None = None
) -> dict:
    """One autopilot cycle across both channels, in the current safety mode.

    Order mirrors the engine autopilots: accept LinkedIn invites, send/advance
    email + LinkedIn steps (bandit-selected variants), then promote A/B winners.
    ``gate`` (optional) vetoes un-approved first touches in manual sending mode.
    """
    from backend import pulse_runtime
    from modules.pulse.inbox.sequences.scheduler import Scheduler as EmailScheduler
    from modules.pulse.inbox.analytics import ab_testing as ibx_ab
    from modules.pulse.inbox import store as ibx_store
    from modules.pulse.connect.sequences.scheduler import Scheduler as ConnectScheduler
    from modules.pulse.connect.analytics import ab_testing as cnx_ab
    from modules.pulse.connect import store as cnx_store
    from modules.pulse.connect.delivery import dispatcher as cnx_dispatcher

    respect_window = pulse_runtime.is_live()  # SAFE mode ignores the send window so it always acts

    # LinkedIn: detect accepted invites (mock provider auto-accepts) so messaging can proceed.
    cnx_dispatcher.sync_acceptances(dry_run=False)

    email_report = EmailScheduler(
        email_campaign_id, dry_run=pulse_runtime.email_dry_run(), throttle=False,
        respect_window=respect_window, variant_selector=ibx_ab.bandit_selector, now_fn=now_fn,
        recipient_filter=(gate.allow_recipient if gate else None),
    ).tick()

    li_report = ConnectScheduler(
        li_campaign_id, dry_run=pulse_runtime.connect_dry_run(), throttle=False,
        respect_window=respect_window, variant_selector=cnx_ab.bandit_selector, now_fn=now_fn,
        prospect_filter=(gate.allow_prospect if gate else None),
    ).tick()

    # Promote A/B winners once arms have enough data.
    for store, ab, cid in ((ibx_store, ibx_ab, email_campaign_id), (cnx_store, cnx_ab, li_campaign_id)):
        camp = store.get_campaign(cid)
        if camp:
            for step in camp.steps:
                if step.id:
                    ab.evaluate_and_promote(step.id)

    return {"email": email_report, "linkedin": li_report}
