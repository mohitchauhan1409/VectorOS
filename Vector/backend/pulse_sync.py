"""Mirror the engine's Pulse state (inbox.db + connect.db) into the unified DB.

The engine's outreach machinery (scheduler, warmup, caps, bandit, replies,
scheduling) runs against its own SQLite stores. After a Pulse cycle we mirror
that live state into a workspace in vector.db so the CRM shows the real thing:
multi-step progress, sent/queued messages, replies + classification, meetings,
per-variant bandit stats, and mailbox / LinkedIn-account warmup + capacity.

Idempotent: it rebuilds the pulse-owned rows for the workspace each call.
Scout-owned rows (companies/people/signals + decision_maker_found events) are
preserved and only augmented if a recipient references someone not yet present.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.models import (
    Campaign,
    Company,
    Enrollment,
    Event,
    LinkedInAccount,
    Mailbox,
    Meeting,
    Message,
    Person,
    Sequence,
    SequenceStep,
    Variant,
)

# engine stores
from modules.pulse.inbox import store as ibx
from modules.pulse.inbox.delivery import accounts as ibx_accounts
from modules.pulse.connect import store as cnx
from modules.pulse.connect import config as cnx_cfg

PULSE_EVENT_TYPES = (
    "email_sent", "email_opened", "email_replied", "linkedin_invite_sent",
    "linkedin_accepted", "linkedin_replied", "meeting_booked", "note", "status_change",
)


def _dt(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _days_since(iso_date: str | None) -> int:
    if not iso_date:
        return 0
    try:
        return max(0, (date.today() - date.fromisoformat(iso_date)).days)
    except ValueError:
        return 0


def _li_invite_allowance(acct) -> int:
    if acct.warmup_started_on is None:
        return min(cnx_cfg.WARMUP_START, acct.daily_invite_cap)
    ramped = cnx_cfg.WARMUP_START + cnx_cfg.WARMUP_INCREMENT * _days_since(acct.warmup_started_on)
    return min(ramped, acct.daily_invite_cap)


# --------------------------------------------------------------------------- #

def _snapshot_launches(db: Session, ws: int) -> tuple[dict[tuple[int, str], tuple], str | None]:
    """Preserve human launch decisions + the campaign's send mode across a wipe.

    The engine stores know nothing about either — they're CRM-side decisions —
    so without this every rebuild would silently un-approve everyone.
    """
    launches = {
        (e.person_id, e.channel): (e.launched_at, e.launched_by)
        for e in db.scalars(
            select(Enrollment).where(
                Enrollment.workspace_id == ws, Enrollment.launched_at.is_not(None)
            )
        ).all()
    }
    mode = db.scalar(select(Campaign.send_mode).where(Campaign.workspace_id == ws).limit(1))
    return launches, mode


def sync_workspace(db: Session, workspace_id: int, *, campaign_name: str) -> dict:
    """Rebuild pulse-owned rows for a workspace from the engine stores."""
    launches, prior_mode = _snapshot_launches(db, workspace_id)
    _wipe(db, workspace_id)
    stats = {"campaigns": 0, "enrollments": 0, "messages": 0, "meetings": 0}

    _sync_mailboxes(db, workspace_id)
    _sync_accounts(db, workspace_id)

    # Pair the engine's inbox + connect campaigns (same name) into one unified campaign.
    ibx_camp = ibx.get_campaign_by_name(campaign_name)
    cnx_camp = cnx.get_campaign_by_name(campaign_name)
    if not ibx_camp and not cnx_camp:
        db.commit()
        return stats

    camp = Campaign(
        workspace_id=workspace_id,
        name=campaign_name,
        description="Multi-channel outreach built and run by Pulse.",
        status=(ibx_camp.status.value if ibx_camp else cnx_camp.status.value),
        # Manual unless the operator had already switched this workspace over.
        send_mode=prior_mode or "manual",
        icp_min_score=(ibx_camp.icp_min_score if ibx_camp else cnx_camp.icp_min_score),
        theme=getattr(ibx_camp, "theme", "") or "",
    )
    db.add(camp)
    db.flush()
    stats["campaigns"] = 1

    email_seq = li_seq = None
    if ibx_camp:
        email_seq = _mirror_email_sequence(db, camp, ibx_camp)
    if cnx_camp:
        li_seq = _mirror_linkedin_sequence(db, camp, cnx_camp)

    if ibx_camp and email_seq:
        stats["enrollments"] += _sync_recipients(db, workspace_id, camp, email_seq, ibx_camp)
    if cnx_camp and li_seq:
        stats["enrollments"] += _sync_prospects(db, workspace_id, camp, li_seq, cnx_camp)

    # Re-apply the launch approvals the rebuild just dropped.
    if launches:
        db.flush()
        for e in db.scalars(
            select(Enrollment).where(Enrollment.workspace_id == workspace_id)
        ).all():
            prior = launches.get((e.person_id, e.channel))
            if prior:
                e.launched_at, e.launched_by = prior

    stats["messages"] = db.scalar(
        select(Message.id).where(Message.workspace_id == workspace_id).limit(1)
    ) is not None and db.query(Message).filter(Message.workspace_id == workspace_id).count() or 0
    stats["meetings"] = db.query(Meeting).filter(Meeting.workspace_id == workspace_id).count()
    db.commit()
    return stats


def _wipe(db: Session, ws: int) -> None:
    db.execute(delete(Message).where(Message.workspace_id == ws))
    db.execute(delete(Meeting).where(Meeting.workspace_id == ws))
    db.execute(delete(Enrollment).where(Enrollment.workspace_id == ws))
    db.execute(delete(Event).where(Event.workspace_id == ws, Event.type.in_(PULSE_EVENT_TYPES)))
    db.execute(delete(Mailbox).where(Mailbox.workspace_id == ws))
    db.execute(delete(LinkedInAccount).where(LinkedInAccount.workspace_id == ws))
    # campaigns cascade to sequences/steps/variants
    db.execute(delete(Campaign).where(Campaign.workspace_id == ws))
    db.flush()


def _sync_mailboxes(db: Session, ws: int) -> None:
    for mb in ibx.list_mailboxes(active_only=False):
        db.add(Mailbox(
            workspace_id=ws, email=mb.email, from_name=mb.from_name, provider=mb.provider,
            daily_cap=mb.daily_cap, daily_allowance=ibx_accounts.daily_allowance(mb),
            sent_today=ibx.sent_today(mb.id) if mb.id else 0,
            warmup_started_on=mb.warmup_started_on,
            status=mb.status.value if hasattr(mb.status, "value") else str(mb.status),
        ))


def _sync_accounts(db: Session, ws: int) -> None:
    for a in cnx.list_accounts(active_only=False):
        db.add(LinkedInAccount(
            workspace_id=ws, name=a.name, provider=a.provider,
            daily_invite_cap=a.daily_invite_cap, weekly_invite_cap=a.weekly_invite_cap,
            daily_message_cap=a.daily_message_cap, invite_allowance=_li_invite_allowance(a),
            invites_today=cnx.invites_today(a.id) if a.id else 0,
            invites_week=cnx.invites_this_week(a.id) if a.id else 0,
            messages_today=cnx.messages_today(a.id) if a.id else 0,
            warmup_started_on=a.warmup_started_on,
            status=a.status.value if hasattr(a.status, "value") else str(a.status),
        ))


def _mirror_email_sequence(db: Session, camp: Campaign, ibx_camp) -> Sequence:
    seq = Sequence(campaign=camp, channel="email", name="Email sequence",
                   status=ibx_camp.status.value)
    for st in sorted(ibx_camp.steps, key=lambda s: s.step_order):
        step = SequenceStep(sequence=seq, step_order=st.step_order, name=st.name,
                            angle=st.angle, wait_days=st.wait_days, kind=None)
        for v in st.variants:
            step.variants.append(Variant(
                name=v.name, angle=v.angle, subject_template=v.subject_template,
                body_template=v.body_template, sent_count=v.sent_count, reply_count=v.reply_count,
                alpha=v.alpha, beta=v.beta, is_winner=v.is_winner, is_paused=v.is_paused,
            ))
    db.add(seq)
    db.flush()
    return seq


def _mirror_linkedin_sequence(db: Session, camp: Campaign, cnx_camp) -> Sequence:
    seq = Sequence(campaign=camp, channel="linkedin", name="LinkedIn sequence",
                   status=cnx_camp.status.value)
    for st in sorted(cnx_camp.steps, key=lambda s: s.step_order):
        step = SequenceStep(sequence=seq, step_order=st.step_order, name=st.name,
                            angle=st.angle, wait_days=st.wait_days,
                            kind=st.kind.value if hasattr(st.kind, "value") else str(st.kind))
        for v in st.variants:
            step.variants.append(Variant(
                name=v.name, angle=v.angle, subject_template=None, body_template=v.template,
                sent_count=v.sent_count, reply_count=v.reply_count, alpha=v.alpha, beta=v.beta,
                is_winner=v.is_winner, is_paused=v.is_paused,
            ))
    db.add(seq)
    db.flush()
    return seq


def _find_or_make_person(db: Session, ws: int, *, name, email, company_name, lead_slug,
                         title, role_category, linkedin_url="") -> Person:
    q = select(Person).where(Person.workspace_id == ws)
    person = None
    if email:
        person = db.scalar(q.where(Person.email == email))
    if not person and linkedin_url:
        person = db.scalar(q.where(Person.linkedin_url == linkedin_url))
    if not person:
        person = db.scalar(q.where(Person.name == name))
    if person:
        return person
    # create minimal company + person from the enrollment context
    slug = lead_slug or company_name.lower().replace(" ", "-")
    company = db.scalar(select(Company).where(Company.workspace_id == ws, Company.slug == slug))
    if not company:
        company = Company(workspace_id=ws, slug=slug, name=company_name or slug,
                          industry="", qualified=True)
        db.add(company)
        db.flush()
    person = Person(workspace_id=ws, company_id=company.id, name=name, title=title,
                    role_category=role_category, email=email or None, linkedin_url=linkedin_url or "")
    db.add(person)
    db.flush()
    return person


def _add_event(db, ws, person, company_id, type_, channel, title, detail, meta, at):
    db.add(Event(workspace_id=ws, person_id=person.id, company_id=company_id, type=type_,
                 channel=channel, title=title, detail=detail, meta=meta, created_at=at or datetime.now(timezone.utc)))


def _sync_recipients(db, ws, camp, seq, ibx_camp) -> int:
    n = 0
    for rec in ibx.list_recipients(ibx_camp.id):
        person = _find_or_make_person(
            db, ws, name=rec.name, email=rec.email, company_name=rec.company,
            lead_slug=rec.lead_slug, title=rec.title, role_category=rec.role_category)
        enr = Enrollment(
            workspace_id=ws, campaign_id=camp.id, sequence_id=seq.id, channel="email",
            person_id=person.id, current_step=rec.current_step, status=rec.status.value,
            next_action_at=_dt(rec.next_send_at), last_action_at=_dt(rec.last_sent_at),
            replied_at=_dt(rec.replied_at), enrolled_at=_dt(rec.enrolled_at) or datetime.now(timezone.utc),
        )
        db.add(enr)
        db.flush()
        n += 1
        # messages
        for m in ibx.messages_for_recipient(rec.id):
            db.add(Message(
                workspace_id=ws, enrollment_id=enr.id, person_id=person.id, campaign_id=camp.id,
                sequence_id=seq.id, channel="email", direction="outbound",
                step_name=_step_name(seq, m.step_id, ibx_camp), subject=m.subject, body=m.body,
                status=m.status.value if hasattr(m.status, "value") else str(m.status),
                at=_dt(m.sent_at) or _dt(m.queued_at) or datetime.now(timezone.utc)))
            if (m.status.value if hasattr(m.status, "value") else str(m.status)) in ("sent", "opened", "replied"):
                _add_event(db, ws, person, person.company_id, "email_sent", "email",
                           f"Email sent — {_step_name(seq, m.step_id, ibx_camp)}", m.subject or "",
                           camp.name, _dt(m.sent_at))
        # replies
        for r in ibx.replies_for_recipient(rec.id):
            rc = r.classification.value if hasattr(r.classification, "value") else str(r.classification)
            db.add(Message(
                workspace_id=ws, enrollment_id=enr.id, person_id=person.id, campaign_id=camp.id,
                sequence_id=seq.id, channel="email", direction="inbound", step_name="Reply",
                subject=r.subject, body=r.body, reply_class=rc,
                at=_dt(r.received_at) or datetime.now(timezone.utc)))
            _add_event(db, ws, person, person.company_id, "email_replied", "email",
                       f"Replied — {rc.replace('_', ' ')}", r.body[:180], camp.name, _dt(r.received_at))
        _maybe_meeting(db, ws, person, camp, "email", rec.status.value)
    return n


def _sync_prospects(db, ws, camp, seq, cnx_camp) -> int:
    n = 0
    for p in cnx.list_prospects(cnx_camp.id):
        person = _find_or_make_person(
            db, ws, name=p.name, email=p.email, company_name=p.company, lead_slug=p.lead_slug,
            title=p.title, role_category=p.role_category, linkedin_url=p.linkedin_url)
        enr = Enrollment(
            workspace_id=ws, campaign_id=camp.id, sequence_id=seq.id, channel="linkedin",
            person_id=person.id, current_step=p.current_step, status=p.status.value,
            next_action_at=_dt(p.next_action_at), last_action_at=_dt(p.last_action_at),
            replied_at=_dt(p.replied_at), invited_at=_dt(p.invited_at), accepted_at=_dt(p.accepted_at),
            enrolled_at=_dt(p.enrolled_at) or datetime.now(timezone.utc))
        db.add(enr)
        db.flush()
        n += 1
        if p.invited_at:
            _add_event(db, ws, person, person.company_id, "linkedin_invite_sent", "linkedin",
                       "LinkedIn invite sent", "", camp.name, _dt(p.invited_at))
        if p.accepted_at:
            _add_event(db, ws, person, person.company_id, "linkedin_accepted", "linkedin",
                       "LinkedIn invite accepted", f"{person.name} accepted the request.", camp.name, _dt(p.accepted_at))
        for m in cnx.messages_for_prospect(p.id):
            db.add(Message(
                workspace_id=ws, enrollment_id=enr.id, person_id=person.id, campaign_id=camp.id,
                sequence_id=seq.id, channel="linkedin", direction="outbound",
                step_name=(m.kind.value if hasattr(m.kind, "value") else str(m.kind)), body=m.body,
                status=m.status.value if hasattr(m.status, "value") else str(m.status),
                at=_dt(m.sent_at) or _dt(m.queued_at) or datetime.now(timezone.utc)))
        for r in cnx.replies_for_prospect(p.id):
            rc = r.classification.value if hasattr(r.classification, "value") else str(r.classification)
            db.add(Message(
                workspace_id=ws, enrollment_id=enr.id, person_id=person.id, campaign_id=camp.id,
                sequence_id=seq.id, channel="linkedin", direction="inbound", step_name="Reply",
                body=r.body, reply_class=rc, at=_dt(r.received_at) or datetime.now(timezone.utc)))
            _add_event(db, ws, person, person.company_id, "linkedin_replied", "linkedin",
                       f"Replied — {rc.replace('_', ' ')}", r.body[:180], camp.name, _dt(r.received_at))
        _maybe_meeting(db, ws, person, camp, "linkedin", p.status.value)
    return n


def _step_name(seq: Sequence, step_id, engine_camp) -> str:
    if not step_id:
        return "Message"
    for st in engine_camp.steps:
        if st.id == step_id:
            return st.name
    return "Message"


def _maybe_meeting(db, ws, person, camp, channel, status) -> None:
    if status in ("meeting", "booked"):
        db.add(Meeting(
            workspace_id=ws, person_id=person.id, campaign_id=camp.id, channel=channel,
            status="booked" if status == "booked" else "proposed",
            attendee_email=person.email))
        _add_event(db, ws, person, person.company_id, "meeting_booked", channel,
                   "Intro call booked", f"Meeting scheduled with {person.name}.", camp.name, None)
