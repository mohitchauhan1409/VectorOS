"""Campaign routes.

A Campaign owns exactly two Sequences: one email, one LinkedIn.
Read endpoints are display-only for the FE; the write endpoints here are the
"few things the FE controls" — editing a variant's message and toggling
campaign / step status.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.metrics import campaign_metrics
from backend.models import (
    SEND_MODES,
    Campaign,
    Enrollment,
    Event,
    Person,
    Sequence,
    SequenceStep,
    User,
    Variant,
)
from backend.security import get_current_user
from backend.serializers import campaign_out, enrollment_out, is_awaiting_launch

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


def _load(db: Session, ws: int, campaign_id: int) -> Campaign:
    c = db.scalar(
        select(Campaign)
        .where(Campaign.id == campaign_id, Campaign.workspace_id == ws)
        .options(
            selectinload(Campaign.sequences)
            .selectinload(Sequence.steps)
            .selectinload(SequenceStep.variants)
        )
    )
    if not c:
        raise HTTPException(404, "Campaign not found")
    return c


@router.get("")
def list_campaigns(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Campaign)
        .where(Campaign.workspace_id == user.workspace_id)
        .options(selectinload(Campaign.sequences))
        .order_by(Campaign.created_at.desc())
    ).all()
    return {
        "items": [campaign_out(c, metrics=campaign_metrics(db, c.id, c)) for c in rows],
        "total": len(rows),
    }


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _load(db, user.workspace_id, campaign_id)
    data = campaign_out(c, detail=True, metrics=campaign_metrics(db, c.id, c))
    return data


@router.get("/{campaign_id}/enrollments")
def campaign_enrollments(
    campaign_id: int,
    channel: str | None = None,
    q: str | None = None,
    status: list[str] | None = Query(None),
    held: bool | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Every person enrolled in this campaign, across both channels by default."""
    camp = _load(db, user.workspace_id, campaign_id)
    stmt = select(Enrollment).where(Enrollment.campaign_id == campaign_id)
    if channel:
        stmt = stmt.where(Enrollment.channel == channel)
    if status:
        stmt = stmt.where(Enrollment.status.in_(status))
    enrolls = db.scalars(stmt.order_by(Enrollment.enrolled_at.desc())).all()

    people = {
        p.id: p
        for p in db.scalars(
            select(Person)
            .where(Person.id.in_([e.person_id for e in enrolls] or [-1]))
            .options(selectinload(Person.company))
        ).all()
    }
    step_counts: dict[int, int] = {}
    for e in enrolls:
        if e.sequence_id not in step_counts:
            step_counts[e.sequence_id] = (
                db.scalar(
                    select(func.count()).select_from(SequenceStep).where(
                        SequenceStep.sequence_id == e.sequence_id
                    )
                )
                or 0
            )
    out = []
    for e in enrolls:
        person = people.get(e.person_id)
        if q:
            needle = q.lower()
            haystack = " ".join(
                filter(None, [
                    person.name if person else "",
                    person.title if person else "",
                    person.email if person else "",
                    person.company.name if person and person.company else "",
                ])
            ).lower()
            if needle not in haystack:
                continue
        d = enrollment_out(e, person, camp)
        if held is not None and d["awaiting_launch"] is not held:
            continue
        d["total_steps"] = step_counts.get(e.sequence_id, 0)
        out.append(d)
    return {"items": out, "total": len(out)}


# ---- sending mode + per-person launch ----

class SendModePatch(BaseModel):
    send_mode: str


@router.patch("/{campaign_id}/send-mode")
def patch_send_mode(
    campaign_id: int,
    body: SendModePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Switch between holding every first touch for approval and letting the
    engine send them as they come due."""
    if body.send_mode not in SEND_MODES:
        raise HTTPException(422, f"send_mode must be one of {', '.join(SEND_MODES)}")
    c = _load(db, user.workspace_id, campaign_id)
    c.send_mode = body.send_mode
    db.commit()
    return campaign_out(c, metrics=campaign_metrics(db, c.id, c))


class LaunchIn(BaseModel):
    enrollment_ids: list[int] | None = None
    #: Release every held person in the campaign (optionally one channel only).
    all: bool = False
    channel: str | None = None


def _release(db: Session, e: Enrollment, who: str) -> None:
    e.launched_at = datetime.now(timezone.utc)
    e.launched_by = who
    # Make it due immediately so the next engine cycle picks it up.
    e.next_action_at = e.next_action_at or datetime.now(timezone.utc)


@router.post("/{campaign_id}/launch")
def launch_enrollments(
    campaign_id: int,
    body: LaunchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Release held first touches — one person, a selection, or everyone."""
    camp = _load(db, user.workspace_id, campaign_id)

    stmt = select(Enrollment).where(
        Enrollment.campaign_id == campaign_id, Enrollment.workspace_id == user.workspace_id
    )
    if not body.all:
        if not body.enrollment_ids:
            raise HTTPException(422, "Pass enrollment_ids, or all=true")
        stmt = stmt.where(Enrollment.id.in_(body.enrollment_ids))
    if body.channel:
        stmt = stmt.where(Enrollment.channel == body.channel)

    rows = db.scalars(stmt).all()
    if not body.all and len(rows) != len(body.enrollment_ids or []):
        raise HTTPException(404, "One or more enrollments not found in this campaign")

    released = []
    for e in rows:
        # Only ever releases a held first touch; re-running is a no-op.
        if not is_awaiting_launch(e, camp):
            continue
        _release(db, e, user.name or user.email)
        person = db.get(Person, e.person_id)
        db.add(Event(
            workspace_id=user.workspace_id, person_id=e.person_id,
            company_id=person.company_id if person else None,
            type="campaign_launched", channel=e.channel,
            title=f"{'Email' if e.channel == 'email' else 'LinkedIn'} outreach released",
            detail=f"First touch approved by {user.name or user.email}.",
            meta=camp.name,
        ))
        released.append(e)

    db.commit()
    people = {
        p.id: p
        for p in db.scalars(
            select(Person)
            .where(Person.id.in_([e.person_id for e in released] or [-1]))
            .options(selectinload(Person.company))
        ).all()
    }
    return {
        "released": len(released),
        "items": [enrollment_out(e, people.get(e.person_id), camp) for e in released],
        "metrics": campaign_metrics(db, camp.id, camp),
    }


# ---- writes (the bits the FE is allowed to control) ----

class VariantPatch(BaseModel):
    subject_template: str | None = None
    body_template: str | None = None
    name: str | None = None
    angle: str | None = None
    is_paused: bool | None = None


@router.patch("/variants/{variant_id}")
def patch_variant(
    variant_id: int,
    body: VariantPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    v = db.get(Variant, variant_id)
    if not v:
        raise HTTPException(404, "Variant not found")
    # ownership check
    step = db.get(SequenceStep, v.step_id)
    seq = db.get(Sequence, step.sequence_id)
    camp = db.get(Campaign, seq.campaign_id)
    if not camp or camp.workspace_id != user.workspace_id:
        raise HTTPException(403, "Not allowed")
    if user.is_demo:
        raise HTTPException(403, "The demo workspace is read-only for edits")

    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(v, field, val)
    db.commit()
    db.refresh(v)
    from backend.serializers import variant_out

    return variant_out(v)


class StatusPatch(BaseModel):
    status: str


@router.patch("/{campaign_id}/status")
def patch_campaign_status(
    campaign_id: int,
    body: StatusPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Operational controls (status / send mode / launch) are allowed on the demo
    # workspace — they're reversible and the feature is undemonstrable otherwise.
    # Content edits (variant copy) stay protected above.
    c = _load(db, user.workspace_id, campaign_id)
    c.status = body.status
    db.commit()
    return campaign_out(c, metrics=campaign_metrics(db, c.id, c))
