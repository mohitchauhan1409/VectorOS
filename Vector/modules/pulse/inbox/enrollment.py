"""Enrollment — bridges Scout's leads and mailbox config into Inbox state.

Two jobs:
  1. Register the mailbox pool (from env) into the DB so the scheduler can
     rotate + rate-limit across it.
  2. Read qualified leads + their decision-makers from ``data/Leads/*.json``
     (Detective's output) and enroll the contactable ones into a campaign,
     snapshotting the lead signal so personalization is reproducible.
"""

from __future__ import annotations

from modules.common.logger import get_logger
from modules.pulse.inbox import config, store
from modules.pulse.inbox.schemas import (
    Campaign,
    CampaignStatus,
    Mailbox,
    Recipient,
    SequenceStep,
    Variant,
)
from modules.scout.detective import store as det_store

logger = get_logger("pulse.inbox.enrollment")


# ---------------------------------------------------------------------------
# Mailboxes
# ---------------------------------------------------------------------------
def sync_mailboxes_from_env() -> list[Mailbox]:
    """Upsert every env-configured mailbox into the DB. Returns the pool."""
    saved: list[Mailbox] = []
    for cfg in config.load_mailboxes_from_env():
        mb = Mailbox(
            email=cfg["email"],
            from_name=cfg["from_name"],
            smtp_host=cfg["smtp_host"],
            smtp_port=cfg["smtp_port"],
            imap_host=cfg["imap_host"],
            imap_port=cfg["imap_port"],
            secret_ref=cfg["secret_ref"] or "",
            daily_cap=cfg["daily_cap"],
        )
        saved.append(store.upsert_mailbox(mb))
    logger.info("Synced %d mailbox(es) from env.", len(saved))
    return saved


# ---------------------------------------------------------------------------
# Campaign construction
# ---------------------------------------------------------------------------
def build_campaign(
    name: str,
    description: str = "",
    sequence: tuple[dict, ...] = config.DEFAULT_SEQUENCE,
    icp_min_score: int = 0,
) -> Campaign:
    """Create (and persist) a campaign from a sequence spec.

    Each step is seeded with ONE default variant carrying the step's angle. The
    A/B optimizer (P4) later adds more variants; until then the single variant
    is the arm every send uses. Idempotent on name: returns the existing
    campaign if one already exists.
    """
    existing = store.get_campaign_by_name(name)
    if existing:
        logger.info("Campaign '%s' already exists (#%s).", name, existing.id)
        return existing

    steps: list[SequenceStep] = []
    for i, spec in enumerate(sequence, start=1):
        steps.append(SequenceStep(
            step_order=i,
            name=spec.get("name", f"Step {i}"),
            angle=spec.get("angle", ""),
            wait_days=int(spec.get("wait_days", 0)),
            variants=[Variant(name="A", angle=spec.get("angle", ""))],
        ))
    campaign = Campaign(
        name=name, description=description,
        status=CampaignStatus.DRAFT, icp_min_score=icp_min_score, steps=steps,
    )
    return store.create_campaign(campaign)


# ---------------------------------------------------------------------------
# Reading contactable decision-makers from Scout leads
# ---------------------------------------------------------------------------
def _is_sendable(email_status: str | None) -> bool:
    status = (email_status or "").lower()
    if status in config.SENDABLE_EMAIL_STATUSES:
        return True
    if config.ALLOW_GUESSED_EMAILS and status in ("guessed", "unverified"):
        return True
    return False


def _lead_context(lead: dict) -> dict:
    """Snapshot the personalization-relevant signal from a lead record."""
    icp = lead.get("icp", {}) or {}
    return {
        "company_name": lead.get("company_name", ""),
        "website_url": lead.get("website_url", ""),
        "signal_type": lead.get("signal_type", ""),
        "reason_to_target": lead.get("reason_to_target", ""),
        "article_headline": lead.get("article_headline", ""),
        "article_url": lead.get("article_url", ""),
        "published_date": lead.get("published_date", ""),
        "icp_score": icp.get("score"),
        "icp_tier": icp.get("tier"),
        "icp_rationale": icp.get("rationale", ""),
        "matched_criteria": icp.get("matched_criteria", []),
    }


def iter_contactable(icp_min_score: int = 0) -> list[dict]:
    """Return contactable decision-makers across all qualified leads.

    Each item: ``{"lead": <lead dict>, "dm": <decision_maker dict>,
    "context": <signal snapshot>}``. Filters by ICP floor + sendable email.
    """
    out: list[dict] = []
    for lead in det_store.load_qualified_leads(only_qualified=True):
        score = (lead.get("icp") or {}).get("score") or 0
        if score < icp_min_score:
            continue
        ctx = _lead_context(lead)
        for dm in lead.get("decision_makers", []) or []:
            if not dm.get("email") or not _is_sendable(dm.get("email_status")):
                continue
            out.append({"lead": lead, "dm": dm, "context": ctx})
    return out


def enroll_campaign(campaign: Campaign, icp_min_score: int | None = None) -> dict:
    """Enroll every contactable decision-maker into ``campaign``.

    Returns a summary: enrolled / skipped-duplicate / total-contactable.
    """
    floor = campaign.icp_min_score if icp_min_score is None else icp_min_score
    contactable = iter_contactable(icp_min_score=floor)

    enrolled = 0
    duplicates = 0
    for item in contactable:
        dm, ctx, lead = item["dm"], item["context"], item["lead"]
        rec = Recipient(
            campaign_id=campaign.id,
            lead_slug=lead.get("company_slug", ""),
            company=lead.get("company_name", ""),
            name=dm.get("name", ""),
            email=dm.get("email", ""),
            title=dm.get("title", ""),
            role_category=dm.get("role_category", ""),
            email_status=dm.get("email_status", ""),
            context=ctx,
        )
        if store.enroll_recipient(rec) is None:
            duplicates += 1
        else:
            enrolled += 1
    summary = {
        "campaign": campaign.name,
        "contactable": len(contactable),
        "enrolled": enrolled,
        "duplicates": duplicates,
    }
    logger.info("Enrolled %d into '%s' (%d dupes, %d contactable).",
                enrolled, campaign.name, duplicates, len(contactable))
    return summary
