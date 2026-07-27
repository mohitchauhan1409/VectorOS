"""Analytics & dashboard aggregates + global search."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.metrics import campaign_metrics, workspace_stats
from backend.models import Campaign, Company, Event, Person, User
from backend.security import get_current_user
from backend.serializers import campaign_out, company_out, event_out, person_out

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics")
def analytics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stats = workspace_stats(db, user.workspace_id)
    camps = db.scalars(
        select(Campaign)
        .where(Campaign.workspace_id == user.workspace_id)
        .options(selectinload(Campaign.sequences))
    ).all()
    return {
        "stats": stats,
        "campaigns": [campaign_out(c, metrics=campaign_metrics(db, c.id, c)) for c in camps],
    }


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = user.workspace_id
    stats = workspace_stats(db, ws)

    top = db.scalars(
        select(Company)
        .where(Company.workspace_id == ws)
        .options(selectinload(Company.people), selectinload(Company.criteria))
        .order_by(Company.icp_score.desc())
        .limit(6)
    ).all()
    fresh = db.scalars(
        select(Company)
        .where(Company.workspace_id == ws)
        .options(selectinload(Company.people), selectinload(Company.criteria))
        .order_by(Company.discovered_at.desc())
        .limit(5)
    ).all()
    recent = db.scalars(
        select(Event).where(Event.workspace_id == ws).order_by(Event.created_at.desc()).limit(8)
    ).all()
    active_camps = db.scalars(
        select(Campaign)
        .where(Campaign.workspace_id == ws, Campaign.status == "active")
        .options(selectinload(Campaign.sequences))
    ).all()

    return {
        "stats": stats,
        "top_companies": [company_out(c, people_count=len(c.people)) for c in top],
        "fresh_signals": [company_out(c, people_count=len(c.people)) for c in fresh],
        "recent_activity": [event_out(e) for e in recent],
        "active_campaigns": [
            campaign_out(c, metrics=campaign_metrics(db, c.id, c)) for c in active_camps
        ],
    }


@router.get("/search")
def search(q: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = user.workspace_id
    like = f"%{q.lower()}%"
    if not q.strip():
        return {"people": [], "companies": [], "campaigns": []}
    people = db.scalars(
        select(Person)
        .where(Person.workspace_id == ws, func.lower(Person.name).like(like))
        .options(selectinload(Person.company))
        .limit(5)
    ).all()
    companies = db.scalars(
        select(Company)
        .where(Company.workspace_id == ws, func.lower(Company.name).like(like))
        .options(selectinload(Company.criteria))
        .limit(5)
    ).all()
    campaigns = db.scalars(
        select(Campaign)
        .where(Campaign.workspace_id == ws, func.lower(Campaign.name).like(like))
        .options(selectinload(Campaign.sequences))
        .limit(4)
    ).all()
    return {
        "people": [person_out(p, p.company) for p in people],
        "companies": [company_out(c) for c in companies],
        "campaigns": [campaign_out(c) for c in campaigns],
    }
