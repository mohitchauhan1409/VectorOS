"""People routes — list with filters/search, detail with enrollments/timeline/thread."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.models import (
    Campaign,
    Company,
    ContactMeeting,
    Deal,
    Enrollment,
    Event,
    Message,
    Person,
    SequenceStep,
    User,
)
from backend.db import get_db
from backend.metrics import STATUS_RANK
from backend.security import get_current_user
from backend.serializers import (
    deal_out,
    enrollment_out,
    event_out,
    meeting_out,
    message_out,
    person_out,
)

router = APIRouter(prefix="/api/people", tags=["people"])


@router.get("")
def list_people(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    q: str | None = None,
    role: list[str] | None = Query(None),
    email_status: list[str] | None = Query(None),
    tier: list[str] | None = Query(None),
    company: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    page: int = 1,
    page_size: int = 25,
):
    ws = user.workspace_id
    stmt = (
        select(Person)
        .join(Company, Person.company_id == Company.id)
        .where(Person.workspace_id == ws)
        .options(selectinload(Person.company))
    )
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Person.name).like(like),
                func.lower(Person.title).like(like),
                func.lower(Person.email).like(like),
                func.lower(Company.name).like(like),
            )
        )
    if role:
        stmt = stmt.where(Person.role_category.in_(role))
    if email_status:
        stmt = stmt.where(Person.email_status.in_(email_status))
    if tier:
        stmt = stmt.where(Company.icp_tier.in_(tier))
    if company:
        stmt = stmt.where(Company.slug.in_(company))
    if status:
        sub = select(Enrollment.person_id).where(Enrollment.status.in_(status))
        stmt = stmt.where(Person.id.in_(sub))

    stmt = stmt.order_by(Company.icp_score.desc(), Person.confidence.desc())
    rows = db.scalars(stmt).all()
    total = len(rows)

    # engagement + stage need enrollments; batch fetch for the page slice
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]
    pid_list = [p.id for p in page_rows]
    enrolls_by_person: dict[int, list[Enrollment]] = {}
    if pid_list:
        for e in db.scalars(
            select(Enrollment).where(Enrollment.person_id.in_(pid_list))
        ).all():
            enrolls_by_person.setdefault(e.person_id, []).append(e)

    seq_steps_cache: dict[int, int] = {}

    def stage_for(pid: int) -> dict | None:
        es = enrolls_by_person.get(pid, [])
        if not es:
            return None
        top = max(es, key=lambda e: e.current_step)
        if top.sequence_id not in seq_steps_cache:
            seq_steps_cache[top.sequence_id] = (
                db.scalar(
                    select(func.count())
                    .select_from(SequenceStep)
                    .where(SequenceStep.sequence_id == top.sequence_id)
                )
                or 0
            )
        return {
            "text": f"Step {top.current_step}/{seq_steps_cache[top.sequence_id]}",
            "channel": top.channel,
            "status": top.status,
        }

    deal_stages: dict[int, str] = {}
    if pid_list:
        deal_stages = {
            person_id: stage
            for person_id, stage in db.execute(
                select(Deal.person_id, Deal.stage).where(Deal.person_id.in_(pid_list))
            )
        }

    items = []
    for p in page_rows:
        d = person_out(p, p.company)
        es = enrolls_by_person.get(p.id, [])
        # Surface the most advanced status, not an arbitrary one — `in_deal` should
        # never be hidden behind a stale `active` email enrollment.
        d["engagement_status"] = (
            max(es, key=lambda e: STATUS_RANK.get(e.status, 0)).status if es else None
        )
        d["stage"] = stage_for(p.id)
        d["company_tier"] = p.company.icp_tier if p.company else None
        d["deal_stage"] = deal_stages.get(p.id)
        items.append(d)

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/facets")
def facets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = user.workspace_id
    roles = db.scalars(
        select(Person.role_category).where(Person.workspace_id == ws).distinct()
    ).all()
    companies = db.execute(
        select(Company.slug, Company.name).where(Company.workspace_id == ws).order_by(Company.name)
    ).all()
    statuses = db.scalars(
        select(Enrollment.status).where(Enrollment.workspace_id == ws).distinct()
    ).all()
    return {
        "roles": sorted(x for x in roles if x),
        "companies": [{"value": s, "label": n} for s, n in companies],
        "statuses": sorted(x for x in statuses if x),
    }


@router.get("/{person_id}")
def get_person(person_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.scalar(
        select(Person)
        .where(Person.id == person_id, Person.workspace_id == user.workspace_id)
        .options(selectinload(Person.company))
    )
    if not p:
        raise HTTPException(404, "Person not found")

    enrolls = db.scalars(select(Enrollment).where(Enrollment.person_id == p.id)).all()
    camp_ids = {e.campaign_id for e in enrolls}
    camps = {
        c.id: c
        for c in db.scalars(select(Campaign).where(Campaign.id.in_(camp_ids or {-1}))).all()
    }
    def steps_count(seq_id: int) -> int:
        return db.scalar(
            select(func.count()).select_from(SequenceStep).where(SequenceStep.sequence_id == seq_id)
        ) or 0

    enroll_data = []
    for e in enrolls:
        d = enrollment_out(e, p, camps.get(e.campaign_id))
        d["total_steps"] = steps_count(e.sequence_id)
        enroll_data.append(d)

    events = db.scalars(
        select(Event).where(Event.person_id == p.id).order_by(Event.created_at.desc())
    ).all()
    thread = db.scalars(
        select(Message).where(Message.person_id == p.id).order_by(Message.at.asc())
    ).all()

    data = person_out(p, p.company)
    data["company"] = None
    if p.company:
        from backend.serializers import company_out

        data["company"] = company_out(p.company)
    data["enrollments"] = enroll_data
    data["timeline"] = [event_out(e) for e in events]
    data["thread"] = [message_out(m) for m in thread]

    # Meetings are person-level and always present (possibly empty).
    data["meetings"] = [
        meeting_out(m)
        for m in db.scalars(
            select(ContactMeeting)
            .where(ContactMeeting.person_id == p.id, ContactMeeting.workspace_id == user.workspace_id)
            .options(selectinload(ContactMeeting.points))
            .order_by(ContactMeeting.occurred_at.desc())
        ).all()
    ]

    # Closer stage — present only once the first meeting has happened and the
    # conversation moved into a deal. Powered by the Closer module (in dev);
    # seeded for the demo workspace today.
    deal = db.scalar(
        select(Deal)
        .where(Deal.person_id == p.id, Deal.workspace_id == user.workspace_id)
        .options(
            selectinload(Deal.meetings),
            selectinload(Deal.next_steps),
            selectinload(Deal.highlights),
        )
    )
    data["deal"] = deal_out(deal) if deal else None
    return data
