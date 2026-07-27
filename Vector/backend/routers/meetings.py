"""Meeting routes — the one part of the CRM a human drives by hand.

Everything else in this API is display-only (the engine owns the data), but a
meeting is something an operator books, holds, and writes up themselves. Closer
will later fill in `summary` + extracted points from the notes; until then a
manually-entered recap is a first-class citizen.

Unlike sequence-copy edits, meeting writes ARE allowed on the demo workspace —
they're additive and the feature is undemonstrable otherwise. `python -m
backend.manage seed-demo --force` resets it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.models import MEETING_STATUSES, ContactMeeting, Deal, Event, Person, User
from backend.security import get_current_user
from backend.serializers import meeting_out

router = APIRouter(prefix="/api", tags=["meetings"])

MEETING_KINDS = ("intro", "discovery", "demo", "technical", "pricing", "exec", "other")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


class MeetingIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    kind: str = "intro"
    occurred_at: str
    duration_min: int = Field(default=30, ge=5, le=600)
    attendees: str = ""
    location: str = ""
    notes: str = ""
    status: str | None = None  # inferred from the date when omitted
    sentiment: str = "neutral"


class MeetingPatch(BaseModel):
    title: str | None = None
    kind: str | None = None
    status: str | None = None
    occurred_at: str | None = None
    duration_min: int | None = Field(default=None, ge=5, le=600)
    attendees: str | None = None
    location: str | None = None
    notes: str | None = None
    summary: str | None = None
    sentiment: str | None = None


def _load(db: Session, user: User, meeting_id: int) -> ContactMeeting:
    m = db.scalar(
        select(ContactMeeting)
        .where(ContactMeeting.id == meeting_id, ContactMeeting.workspace_id == user.workspace_id)
        .options(selectinload(ContactMeeting.points))
    )
    if not m:
        raise HTTPException(404, "Meeting not found")
    return m


@router.get("/people/{person_id}/meetings")
def list_meetings(
    person_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(ContactMeeting)
        .where(
            ContactMeeting.person_id == person_id,
            ContactMeeting.workspace_id == user.workspace_id,
        )
        .options(selectinload(ContactMeeting.points))
        .order_by(ContactMeeting.occurred_at.desc())
    ).all()
    return {"items": [meeting_out(m) for m in rows], "total": len(rows)}


@router.post("/people/{person_id}/meetings", status_code=201)
def create_meeting(
    person_id: int,
    body: MeetingIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    person = db.scalar(
        select(Person).where(Person.id == person_id, Person.workspace_id == user.workspace_id)
    )
    if not person:
        raise HTTPException(404, "Person not found")

    when = _parse_dt(body.occurred_at)
    if when is None:
        raise HTTPException(422, "occurred_at must be an ISO 8601 datetime")
    if body.kind not in MEETING_KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(MEETING_KINDS)}")

    # A meeting in the past has already happened unless told otherwise.
    status = body.status or ("completed" if when <= datetime.utcnow() else "scheduled")
    if status not in MEETING_STATUSES:
        raise HTTPException(422, f"status must be one of {', '.join(MEETING_STATUSES)}")

    deal = db.scalar(select(Deal).where(Deal.person_id == person_id))
    meeting = ContactMeeting(
        workspace_id=user.workspace_id,
        person_id=person_id,
        deal_id=deal.id if deal else None,
        title=body.title.strip(),
        kind=body.kind,
        status=status,
        occurred_at=when,
        duration_min=body.duration_min,
        attendees=body.attendees.strip(),
        location=body.location.strip(),
        notes=body.notes.strip(),
        sentiment=body.sentiment,
        source="manual",
    )
    db.add(meeting)
    db.flush()

    db.add(Event(
        workspace_id=user.workspace_id, person_id=person_id, company_id=person.company_id,
        type="meeting_booked" if status == "scheduled" else "meeting_held",
        channel=None, title=meeting.title,
        detail=f"{meeting.duration_min}-min {meeting.kind} · added manually",
        created_at=meeting.occurred_at,
    ))
    db.commit()
    db.refresh(meeting)
    return meeting_out(meeting)


@router.patch("/meetings/{meeting_id}")
def update_meeting(
    meeting_id: int,
    body: MeetingPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = _load(db, user, meeting_id)
    fields = body.model_dump(exclude_unset=True)

    if "status" in fields and fields["status"] not in MEETING_STATUSES:
        raise HTTPException(422, f"status must be one of {', '.join(MEETING_STATUSES)}")
    if "kind" in fields and fields["kind"] not in MEETING_KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(MEETING_KINDS)}")
    if "occurred_at" in fields:
        when = _parse_dt(fields.pop("occurred_at"))
        if when is None:
            raise HTTPException(422, "occurred_at must be an ISO 8601 datetime")
        m.occurred_at = when

    for key, value in fields.items():
        setattr(m, key, value)
    db.commit()
    db.refresh(m)
    return meeting_out(m)


@router.delete("/meetings/{meeting_id}", status_code=204)
def delete_meeting(
    meeting_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.delete(_load(db, user, meeting_id))
    db.commit()
