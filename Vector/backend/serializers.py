"""ORM -> JSON serializers. Central place that defines the API's response shape,
kept close to what the CRM frontend consumes."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.models import (
    Campaign,
    Company,
    ContactMeeting,
    Deal,
    Enrollment,
    Event,
    Message,
    Person,
    Sequence,
    SequenceStep,
    Signal,
    User,
    Variant,
)


def _iso(dt: datetime | None) -> str | None:
    """Serialize as an explicitly UTC ISO string.

    SQLite hands back naive datetimes, and everything we store is UTC. Emitting
    them without a zone makes every JS `new Date(...)` parse them as *local*
    time, shifting every timestamp by the viewer's offset — so the suffix is
    load-bearing, not cosmetic.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def user_out(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "is_demo": u.is_demo,
        "workspace_id": u.workspace_id,
    }


def signal_out(s: Signal) -> dict:
    return {
        "signal_type": s.signal_type,
        "reason_to_target": s.reason_to_target,
        "confidence": s.confidence,
        "article_headline": s.article_headline,
        "article_url": s.article_url,
        "published_date": s.published_date,
        "source_name": s.source_name,
        "discovered_at": _iso(s.discovered_at),
    }


def person_out(p: Person, company: Company | None = None) -> dict:
    company = company or p.company
    return {
        "id": str(p.id),
        "name": p.name,
        "title": p.title,
        "role_category": p.role_category,
        "linkedin_url": p.linkedin_url,
        "confidence": p.confidence,
        "email": p.email,
        "email_status": p.email_status,
        "email_source": p.email_source,
        "apollo_id": p.apollo_id,
        "city": p.city,
        "country": p.country,
        "enriched": p.enriched,
        "company_id": p.company_id,
        "company_slug": company.slug if company else "",
        "company_name": company.name if company else "",
    }


def meeting_out(m: ContactMeeting) -> dict:
    def points(kind: str) -> list[str]:
        return [p.text for p in m.points if p.kind == kind]

    return {
        "id": str(m.id),
        "person_id": str(m.person_id),
        "deal_id": str(m.deal_id) if m.deal_id else None,
        "title": m.title,
        "kind": m.kind,
        "status": m.status,
        "occurred_at": _iso(m.occurred_at),
        "duration_min": m.duration_min,
        "attendees": [a.strip() for a in (m.attendees or "").split(",") if a.strip()],
        "location": m.location,
        "sentiment": m.sentiment,
        "notes": m.notes,
        "summary": m.summary,
        "source": m.source,
        "recording_url": m.recording_url,
        "has_summary": bool(m.summary),
        "takeaways": points("takeaway"),
        "objections": points("objection"),
        "questions": points("question"),
        "commitments": points("commitment"),
    }


def deal_out(d: Deal, *, detail: bool = True) -> dict:
    data = {
        "id": str(d.id),
        "person_id": str(d.person_id),
        "company_id": d.company_id,
        "campaign_id": str(d.campaign_id) if d.campaign_id else None,
        "stage": d.stage,
        "health": d.health,
        "probability": d.probability,
        "value_usd": d.value_usd,
        "owner": d.owner,
        "source_channel": d.source_channel,
        "summary": d.summary,
        "opened_at": _iso(d.opened_at),
        "expected_close": d.expected_close,
        "last_activity_at": _iso(d.last_activity_at),
        # Meetings live on the contact (Meetings tab) — the deal only counts them.
        "meeting_count": sum(1 for m in d.meetings if m.status == "completed"),
        "open_step_count": sum(1 for s in d.next_steps if s.status != "done"),
    }
    if detail:
        data["next_steps"] = [
            {
                "id": str(s.id),
                "step_order": s.step_order,
                "title": s.title,
                "detail": s.detail,
                "owner": s.owner,
                "due_date": s.due_date,
                "priority": s.priority,
                "status": s.status,
                "rationale": s.rationale,
            }
            for s in d.next_steps
        ]
        data["highlights"] = [
            {"id": str(h.id), "kind": h.kind, "text": h.text, "confidence": h.confidence}
            for h in d.highlights
        ]
    return data


def company_out(
    c: Company,
    *,
    detail: bool = False,
    people_count: int | None = None,
    pipeline: dict | None = None,
) -> dict:
    matched = [x.text for x in c.criteria if x.kind == "matched"]
    concerns = [x.text for x in c.criteria if x.kind == "concern"]
    data = {
        "id": c.id,
        "company_slug": c.slug,
        "company_name": c.name,
        "website_url": c.website_url,
        "linkedin_url": c.linkedin_url,
        "industry": c.industry,
        "employee_range": c.employee_range,
        "location": c.location,
        "signal_type": c.signal_type,
        "reason_to_target": c.reason_to_target,
        "confidence": c.confidence,
        # `fit` is the durable structural score; `intent` decays with signal age.
        "fit_score": c.icp_score,
        "intent_score": c.intent_score,
        "signal_age_days": c.signal_age_days,
        "icp": {
            "score": c.icp_score,
            "tier": c.icp_tier,
            "rationale": c.icp_rationale,
            "matched_criteria": matched,
            "concerns": concerns,
        },
        "qualified": c.qualified,
        "source_radar": c.source_radar,
        "source_name": c.source_name,
        "article_headline": c.article_headline,
        "article_url": c.article_url,
        "published_date": c.published_date,
        "discovered_at": _iso(c.discovered_at),
        "people_count": people_count if people_count is not None else len(c.people),
    }
    if pipeline is not None:
        data["pipeline"] = pipeline
    if detail:
        data["signals"] = [signal_out(s) for s in c.signals]
        data["decision_makers"] = [person_out(p, c) for p in c.people]
    return data


def variant_out(v: Variant) -> dict:
    return {
        "id": str(v.id),
        "name": v.name,
        "angle": v.angle,
        "subject_template": v.subject_template,
        "body_template": v.body_template,
        "sent_count": v.sent_count,
        "reply_count": v.reply_count,
        "alpha": v.alpha,
        "beta": v.beta,
        "is_winner": v.is_winner,
        "is_paused": v.is_paused,
    }


def step_out(s: SequenceStep) -> dict:
    return {
        "id": str(s.id),
        "step_order": s.step_order,
        "name": s.name,
        "angle": s.angle,
        "wait_days": s.wait_days,
        "kind": s.kind,
        "variants": [variant_out(v) for v in s.variants],
    }


def sequence_out(seq: Sequence) -> dict:
    return {
        "id": str(seq.id),
        "channel": seq.channel,
        "name": seq.name,
        "status": seq.status,
        "steps": [step_out(s) for s in seq.steps],
    }


def campaign_out(c: Campaign, *, detail: bool = False, metrics: dict | None = None) -> dict:
    data = {
        "id": str(c.id),
        "name": c.name,
        "description": c.description,
        "status": c.status,
        "send_mode": c.send_mode,
        "icp_min_score": c.icp_min_score,
        "theme": c.theme,
        "created_at": _iso(c.created_at),
        "channels": sorted({s.channel for s in c.sequences}),
    }
    if metrics is not None:
        data["metrics"] = metrics
    if detail:
        data["sequences"] = [sequence_out(s) for s in c.sequences]
    return data


# Statuses that mean "enrolled but the first touch hasn't gone out yet".
NOT_YET_STARTED = ("active", "pending")


def is_awaiting_launch(e: Enrollment, campaign: Campaign | None) -> bool:
    """True when a manual-mode campaign is holding this person's first touch."""
    if campaign is None or campaign.send_mode != "manual":
        return False
    if e.launched_at is not None:
        return False
    return e.current_step == 0 and e.status in NOT_YET_STARTED


def enrollment_out(e: Enrollment, person: Person | None = None, campaign: Campaign | None = None) -> dict:
    return {
        "id": str(e.id),
        "campaign_id": str(e.campaign_id),
        "sequence_id": str(e.sequence_id),
        "channel": e.channel,
        "person_id": str(e.person_id),
        "name": person.name if person else "",
        "title": person.title if person else "",
        "company": (person.company.name if person and person.company else ""),
        "company_slug": (person.company.slug if person and person.company else ""),
        "email": person.email if person else None,
        "linkedin_url": person.linkedin_url if person else None,
        "role_category": person.role_category if person else "",
        "campaign_name": campaign.name if campaign else "",
        "current_step": e.current_step,
        "status": e.status,
        "next_action_at": _iso(e.next_action_at),
        "last_action_at": _iso(e.last_action_at),
        "replied_at": _iso(e.replied_at),
        "enrolled_at": _iso(e.enrolled_at),
        "invited_at": _iso(e.invited_at),
        "accepted_at": _iso(e.accepted_at),
        "launched_at": _iso(e.launched_at),
        "launched_by": e.launched_by,
        "awaiting_launch": is_awaiting_launch(e, campaign),
    }


def message_out(m: Message) -> dict:
    return {
        "id": str(m.id),
        "person_id": str(m.person_id),
        "campaign_id": str(m.campaign_id) if m.campaign_id else None,
        "channel": m.channel,
        "direction": m.direction,
        "step_name": m.step_name,
        "subject": m.subject,
        "body": m.body,
        "status": m.status,
        "reply_class": m.reply_class,
        "at": _iso(m.at),
    }


def event_out(e: Event) -> dict:
    return {
        "id": str(e.id),
        "person_id": str(e.person_id) if e.person_id else None,
        "company_id": e.company_id,
        "type": e.type,
        "channel": e.channel,
        "title": e.title,
        "detail": e.detail,
        "meta": e.meta,
        "created_at": _iso(e.created_at),
    }
