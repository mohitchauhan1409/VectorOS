"""Enrollment — bridges Scout leads + the sending account into Connect state.

Registers the sending LinkedIn account for the active provider, builds a
campaign from a sequence spec, and enrolls every decision-maker that has a
usable ``linkedin_url`` (Detective's output), snapshotting the lead signal for
reproducible personalization.
"""

from __future__ import annotations

from modules.common.logger import get_logger
from modules.pulse.connect import config, store
from modules.pulse.connect.schemas import (
    Campaign,
    CampaignStatus,
    LinkedInAccount,
    Prospect,
    SequenceStep,
    StepKind,
    Variant,
)
from modules.scout.detective import store as det_store

logger = get_logger("pulse.connect.enrollment")


# ---------------------------------------------------------------------------
# Sending account
# ---------------------------------------------------------------------------
def sync_account() -> LinkedInAccount:
    """Register (or update) the sending account for the active provider."""
    provider = config.PROVIDER
    if provider == "unipile":
        pid = config.UNIPILE_ACCOUNT_ID or "unipile-account"
    elif provider == "phantombuster":
        pid = "phantombuster-account"
    else:
        pid = "mock-account"
    # The real sender's name (env), else a neutral fallback. Never a provider label —
    # it can leak into copy as a "signature".
    name = config.CONNECT_FROM_NAME or "LinkedIn Sender"
    acct = LinkedInAccount(
        name=name, provider=provider, provider_account_id=pid,
        daily_invite_cap=config.DAILY_INVITE_CAP, weekly_invite_cap=config.WEEKLY_INVITE_CAP,
        daily_message_cap=config.DAILY_MESSAGE_CAP)
    saved = store.upsert_account(acct)
    logger.info("Synced sending account #%s (%s / %s).", saved.id, provider, pid)
    return saved


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------
def build_campaign(name: str, description: str = "",
                   sequence: tuple[dict, ...] = config.DEFAULT_SEQUENCE,
                   icp_min_score: int = 0) -> Campaign:
    """Create (and persist) a LinkedIn campaign from a sequence spec.

    Each step gets one default variant carrying its angle; the A/B optimizer can
    add more later. Idempotent on name."""
    existing = store.get_campaign_by_name(name)
    if existing:
        logger.info("Campaign '%s' already exists (#%s).", name, existing.id)
        return existing

    steps: list[SequenceStep] = []
    for i, spec in enumerate(sequence, start=1):
        steps.append(SequenceStep(
            step_order=i, name=spec.get("name", f"Step {i}"),
            kind=StepKind(spec.get("kind", "message")),
            angle=spec.get("angle", ""), wait_days=int(spec.get("wait_days", 0)),
            variants=[Variant(name="A", angle=spec.get("angle", ""))]))
    campaign = Campaign(name=name, description=description, status=CampaignStatus.DRAFT,
                        icp_min_score=icp_min_score, steps=steps)
    return store.create_campaign(campaign)


# ---------------------------------------------------------------------------
# Reading contactable decision-makers (must have a LinkedIn profile URL)
# ---------------------------------------------------------------------------
def _has_linkedin(url: str | None) -> bool:
    return bool(url) and "linkedin.com/in/" in (url or "").lower()


def _lead_context(lead: dict) -> dict:
    icp = lead.get("icp", {}) or {}
    return {
        "company_name": lead.get("company_name", ""),
        "website_url": lead.get("website_url", ""),
        "signal_type": lead.get("signal_type", ""),
        "reason_to_target": lead.get("reason_to_target", ""),
        "article_headline": lead.get("article_headline", ""),
        "published_date": lead.get("published_date", ""),
        "icp_score": icp.get("score"),
        "icp_tier": icp.get("tier"),
        "matched_criteria": icp.get("matched_criteria", []),
    }


def iter_contactable(icp_min_score: int = 0) -> list[dict]:
    """Decision-makers with a usable LinkedIn URL, across qualified leads.
    De-duplicated by profile URL."""
    out: list[dict] = []
    seen: set[str] = set()
    for lead in det_store.load_qualified_leads(only_qualified=True):
        if ((lead.get("icp") or {}).get("score") or 0) < icp_min_score:
            continue
        ctx = _lead_context(lead)
        for dm in lead.get("decision_makers", []) or []:
            url = dm.get("linkedin_url", "")
            if not _has_linkedin(url) or url.lower() in seen:
                continue
            seen.add(url.lower())
            out.append({"lead": lead, "dm": dm, "context": ctx})
    return out


def enroll_campaign(campaign: Campaign, icp_min_score: int | None = None) -> dict:
    """Enroll every contactable decision-maker into ``campaign``."""
    floor = campaign.icp_min_score if icp_min_score is None else icp_min_score
    contactable = iter_contactable(icp_min_score=floor)
    enrolled = duplicates = 0
    for item in contactable:
        dm, ctx, lead = item["dm"], item["context"], item["lead"]
        rec = Prospect(
            campaign_id=campaign.id, lead_slug=lead.get("company_slug", ""),
            company=lead.get("company_name", ""), name=dm.get("name", ""),
            title=dm.get("title", ""), role_category=dm.get("role_category", ""),
            linkedin_url=dm.get("linkedin_url", ""), email=dm.get("email", "") or "", context=ctx)
        if store.enroll_prospect(rec) is None:
            duplicates += 1
        else:
            enrolled += 1
    summary = {"campaign": campaign.name, "contactable": len(contactable),
               "enrolled": enrolled, "duplicates": duplicates}
    logger.info("Enrolled %d into '%s' (%d dupes, %d contactable).",
                enrolled, campaign.name, duplicates, len(contactable))
    return summary
