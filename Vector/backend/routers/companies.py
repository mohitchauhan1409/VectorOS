"""Company routes — list with filters/search/sort, and detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.metrics import STATUS_RANK, COMPANY_STAGES, company_pipeline_map, empty_pipeline
from backend.models import Company, Deal, Enrollment, Person, Sponsorship, User
from backend.security import get_current_user
from backend.serializers import company_out

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("")
def list_companies(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    q: str | None = None,
    tier: list[str] | None = Query(None),
    signal: list[str] | None = Query(None),
    industry: list[str] | None = Query(None),
    size: list[str] | None = Query(None),
    stage: list[str] | None = Query(None),
    sort: str = "icp",
):
    stmt = (
        select(Company)
        .where(Company.workspace_id == user.workspace_id)
        .options(selectinload(Company.criteria), selectinload(Company.people))
    )
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Company.name).like(like),
                func.lower(Company.industry).like(like),
                func.lower(Company.website_url).like(like),
            )
        )
    if tier:
        stmt = stmt.where(Company.icp_tier.in_(tier))
    if signal:
        stmt = stmt.where(Company.signal_type.in_(signal))
    if industry:
        stmt = stmt.where(Company.industry.in_(industry))
    if size:
        stmt = stmt.where(Company.employee_range.in_(size))

    if sort == "recent":
        stmt = stmt.order_by(Company.discovered_at.desc())
    elif sort == "intent":
        # Timing first: who is worth calling this week, regardless of raw fit.
        stmt = stmt.order_by(Company.intent_score.desc(), Company.icp_score.desc())
    else:
        stmt = stmt.order_by(Company.icp_score.desc(), Company.intent_score.desc())
    rows = db.scalars(stmt).all()

    pipelines = company_pipeline_map(db, user.workspace_id)
    items = [
        company_out(c, people_count=len(c.people), pipeline=pipelines.get(c.id) or empty_pipeline())
        for c in rows
    ]
    if stage:
        wanted = set(stage)
        items = [d for d in items if d["pipeline"]["stage"] in wanted]
    if sort == "stage":
        order = {s: i for i, s in enumerate(COMPANY_STAGES)}
        items.sort(key=lambda d: (-order.get(d["pipeline"]["stage"], 0), -d["icp"]["score"]))
    return {"items": items, "total": len(items)}


@router.get("/facets")
def facets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Distinct values for building filter dropdowns."""
    ws = user.workspace_id
    industries = db.scalars(
        select(Company.industry).where(Company.workspace_id == ws).distinct()
    ).all()
    sizes = db.scalars(
        select(Company.employee_range).where(Company.workspace_id == ws).distinct()
    ).all()
    signals = db.scalars(
        select(Company.signal_type).where(Company.workspace_id == ws).distinct()
    ).all()
    stages = {p["stage"] for p in company_pipeline_map(db, ws).values()}
    return {
        "industries": sorted(x for x in industries if x),
        "sizes": sorted(x for x in sizes if x),
        "signals": sorted(x for x in signals if x),
        "stages": [s for s in COMPANY_STAGES if s in stages],
    }


@router.get("/{slug}")
def get_company(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.scalar(
        select(Company)
        .where(Company.workspace_id == user.workspace_id, Company.slug == slug)
        .options(
            selectinload(Company.criteria),
            selectinload(Company.signals),
            selectinload(Company.people),
        )
    )
    if not c:
        raise HTTPException(404, "Company not found")
    pipeline = company_pipeline_map(db, user.workspace_id).get(c.id) or empty_pipeline()
    data = company_out(c, detail=True, people_count=len(c.people), pipeline=pipeline)

    # Per-person engagement rollup — what the company's stage is actually derived from.
    enrolls = db.scalars(
        select(Enrollment).where(Enrollment.person_id.in_([p.id for p in c.people] or [-1]))
    ).all()
    by_person: dict[int, list] = {}
    for e in enrolls:
        by_person.setdefault(e.person_id, []).append(e)
    deals = {
        d.person_id: d
        for d in db.scalars(select(Deal).where(Deal.company_id == c.id)).all()
    }
    data["engagement"] = [
        {
            "person_id": str(p.id),
            "name": p.name,
            "title": p.title,
            "role_category": p.role_category,
            "channels": sorted({e.channel for e in by_person.get(p.id, [])}),
            "status": (
                max(by_person[p.id], key=lambda e: STATUS_RANK.get(e.status, 0)).status
                if by_person.get(p.id)
                else None
            ),
            "deal_stage": deals[p.id].stage if p.id in deals else None,
        }
        for p in c.people
    ]
    data["engagement"].sort(key=lambda d: -STATUS_RANK.get(d["status"] or "", 0))

    # Sponsorship edges both ways. If this account is sponsored, the collateral
    # decision may sit with the sponsor — which changes who to sell to. If it IS a
    # sponsor, every entity on its book is reachable through one relationship.
    def _brief(ids: list[int]) -> list[dict]:
        if not ids:
            return []
        rows = db.scalars(
            select(Company).where(Company.id.in_(ids)).options(selectinload(Company.people))
        ).all()
        pm = company_pipeline_map(db, user.workspace_id)
        return [
            {
                "company_slug": x.slug, "company_name": x.name, "industry": x.industry,
                "fit_score": x.icp_score, "intent_score": x.intent_score,
                "pipeline_stage": (pm.get(x.id) or empty_pipeline())["stage"],
            }
            for x in rows
        ]

    data["sponsors_portfolio"] = _brief(
        [r for (r,) in db.execute(
            select(Sponsorship.sponsored_id).where(Sponsorship.sponsor_id == c.id)
        )]
    )
    data["sponsored_by"] = _brief(
        [r for (r,) in db.execute(
            select(Sponsorship.sponsor_id).where(Sponsorship.sponsored_id == c.id)
        )]
    )
    return data
