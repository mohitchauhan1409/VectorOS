"""Derived analytics — campaign metrics and workspace-level stats.
Pure SQL aggregations over the unified DB (fast, indexed)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import OPEN_DEAL_STAGES, Campaign, Company, Deal, Enrollment, Person

# `in_deal` is the post-first-meeting engagement status: the intro call happened
# and the conversation has moved on to what it takes to close.
REPLY_ISH = ("replied", "in_conversation", "meeting", "booked", "in_deal")
MEETING_ISH = ("meeting", "booked", "in_deal")
DEAL_ISH = ("in_deal",)
ENGAGED_ISH = ("replied", "in_conversation", "needs_human")
ACTIVE_ISH = ("active", "invite_sent", "accepted", "in_conversation", "pending", "in_deal")

# Company pipeline stages, least → most advanced. `lost` is terminal-negative and
# only surfaces when nothing better exists.
COMPANY_STAGES = ("not_started", "outreach", "engaged", "meeting", "deal", "won", "lost")

# How "advanced" each engagement status is. Used to pick a single representative
# status when a person is enrolled on more than one channel.
STATUS_RANK = {
    "pending": 1, "invite_expired": 1, "bounced": 1, "unsubscribed": 1, "not_interested": 1,
    "active": 2, "invite_sent": 2,
    "accepted": 3, "completed": 3,
    "needs_human": 4, "replied": 5, "in_conversation": 6, "meeting": 7, "booked": 8, "in_deal": 9,
}

COMPANY_STAGE_LABELS = {
    "not_started": "Not started",
    "outreach": "Outreach",
    "engaged": "Engaged",
    "meeting": "Meeting",
    "deal": "In deal",
    "won": "Closed won",
    "lost": "Closed lost",
}


def campaign_metrics(db: Session, campaign_id: int, campaign: Campaign | None = None) -> dict:
    from backend.serializers import is_awaiting_launch

    rows = db.scalars(select(Enrollment).where(Enrollment.campaign_id == campaign_id)).all()
    if campaign is None:
        campaign = db.get(Campaign, campaign_id)
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    total = len(rows)
    # Held = manual mode, first touch not released yet.
    awaiting = sum(1 for r in rows if is_awaiting_launch(r, campaign))
    replied = sum(1 for r in rows if r.status in REPLY_ISH)
    meetings = sum(1 for r in rows if r.status in MEETING_ISH)
    booked = sum(1 for r in rows if r.status == "booked")
    deals = sum(1 for r in rows if r.status in DEAL_ISH)
    active = sum(1 for r in rows if r.status in ACTIVE_ISH)
    return {
        "enrolled": total,
        "active": active,
        "replied": replied,
        "positive": replied,
        "meetings": meetings,
        "booked": booked,
        "deals": deals,
        "awaiting_launch": awaiting,
        "launched": total - awaiting,
        "reply_rate": (replied / total) if total else 0.0,
        "by_status": by_status,
    }


# --------------------------------------------------------------------------- #
# Company pipeline stage — derived from the engagement of the people inside it
# --------------------------------------------------------------------------- #

def _stage_from(counts: dict[str, int], deals: dict[str, int]) -> str:
    """Most-advanced-wins, with `lost` only when nothing better exists."""
    if deals.get("won"):
        return "won"
    if deals.get("open") or counts.get("deal"):
        return "deal"
    if deals.get("lost"):
        return "lost"
    if counts.get("meeting"):
        return "meeting"
    if counts.get("engaged"):
        return "engaged"
    if counts.get("enrolled"):
        return "outreach"
    return "not_started"


def company_pipeline_map(db: Session, workspace_id: int) -> dict[int, dict]:
    """Pipeline stage + rollup for every company in the workspace, in 2 queries.

    Bucketed from each company's people: how many are merely enrolled, engaged
    (replied / in conversation), have met, or are in an open deal — plus the
    total value of the deals attached to the account.
    """
    # Reduce to ONE status per person first — someone enrolled on both email and
    # LinkedIn must not be counted in two buckets, nor inflate `enrolled`.
    best: dict[tuple[int, int], str] = {}
    for company_id, person_id, status in db.execute(
        select(Person.company_id, Person.id, Enrollment.status)
        .join(Enrollment, Enrollment.person_id == Person.id)
        .where(Person.workspace_id == workspace_id)
    ):
        key = (company_id, person_id)
        if key not in best or STATUS_RANK.get(status, 0) > STATUS_RANK.get(best[key], 0):
            best[key] = status

    buckets: dict[int, dict[str, int]] = {}
    for (company_id, _person_id), status in best.items():
        b = buckets.setdefault(company_id, {})
        b["enrolled"] = b.get("enrolled", 0) + 1
        if status in DEAL_ISH:
            b["deal"] = b.get("deal", 0) + 1
        elif status in MEETING_ISH:
            b["meeting"] = b.get("meeting", 0) + 1
        elif status in ENGAGED_ISH:
            b["engaged"] = b.get("engaged", 0) + 1

    deal_rows = db.execute(
        select(Deal.company_id, Deal.stage, func.count(Deal.id), func.sum(Deal.value_usd))
        .where(Deal.workspace_id == workspace_id)
        .group_by(Deal.company_id, Deal.stage)
    ).all()
    deals: dict[int, dict[str, int]] = {}
    for company_id, stage, n, value in deal_rows:
        d = deals.setdefault(company_id, {})
        key = "open" if stage in OPEN_DEAL_STAGES else ("won" if stage == "closed_won" else "lost")
        d[key] = d.get(key, 0) + n
        d["value"] = d.get("value", 0) + int(value or 0)

    out: dict[int, dict] = {}
    for company_id in set(buckets) | set(deals):
        counts, d = buckets.get(company_id, {}), deals.get(company_id, {})
        out[company_id] = {
            "stage": _stage_from(counts, d),
            "people_enrolled": counts.get("enrolled", 0),
            "people_engaged": counts.get("engaged", 0),
            "people_met": counts.get("meeting", 0),
            "people_in_deal": counts.get("deal", 0),
            "open_deals": d.get("open", 0),
            "won_deals": d.get("won", 0),
            "lost_deals": d.get("lost", 0),
            "deal_value": d.get("value", 0),
        }
    return out


def empty_pipeline() -> dict:
    return {
        "stage": "not_started", "people_enrolled": 0, "people_engaged": 0, "people_met": 0,
        "people_in_deal": 0, "open_deals": 0, "won_deals": 0, "lost_deals": 0, "deal_value": 0,
    }


def company_pipeline(db: Session, company: Company) -> dict:
    """Single-company variant, for the detail endpoint."""
    return company_pipeline_map(db, company.workspace_id).get(company.id, empty_pipeline())


def workspace_stats(db: Session, workspace_id: int) -> dict:
    total_people = db.scalar(
        select(func.count(Person.id)).where(Person.workspace_id == workspace_id)
    ) or 0
    total_companies = db.scalar(
        select(func.count(Company.id)).where(Company.workspace_id == workspace_id)
    ) or 0
    qualified = db.scalar(
        select(func.count(Company.id)).where(
            Company.workspace_id == workspace_id, Company.qualified.is_(True)
        )
    ) or 0

    enrolls = db.scalars(
        select(Enrollment).where(Enrollment.workspace_id == workspace_id)
    ).all()
    contacted = len({e.person_id for e in enrolls})
    replies = sum(1 for e in enrolls if e.status in REPLY_ISH)
    meetings = sum(1 for e in enrolls if e.status in MEETING_ISH)

    by_tier: dict[str, int] = {}
    by_signal: dict[str, int] = {}
    for tier, signal in db.execute(
        select(Company.icp_tier, Company.signal_type).where(Company.workspace_id == workspace_id)
    ):
        by_tier[tier] = by_tier.get(tier, 0) + 1
        by_signal[signal] = by_signal.get(signal, 0) + 1

    # Deals (Closer stage)
    by_deal_stage: dict[str, int] = {}
    open_value = won_value = 0
    for stage, n, value in db.execute(
        select(Deal.stage, func.count(Deal.id), func.sum(Deal.value_usd))
        .where(Deal.workspace_id == workspace_id)
        .group_by(Deal.stage)
    ):
        by_deal_stage[stage] = n
        if stage in OPEN_DEAL_STAGES:
            open_value += int(value or 0)
        elif stage == "closed_won":
            won_value += int(value or 0)
    open_deals = sum(n for s, n in by_deal_stage.items() if s in OPEN_DEAL_STAGES)

    return {
        "total_people": total_people,
        "total_companies": total_companies,
        "qualified": qualified,
        "contacted": contacted,
        "replies": replies,
        "meetings": meetings,
        "reply_rate": (replies / contacted) if contacted else 0.0,
        "by_tier": by_tier,
        "by_signal": by_signal,
        "open_deals": open_deals,
        "won_deals": by_deal_stage.get("closed_won", 0),
        "lost_deals": by_deal_stage.get("closed_lost", 0),
        "open_deal_value": open_value,
        "won_deal_value": won_value,
        "by_deal_stage": by_deal_stage,
    }
