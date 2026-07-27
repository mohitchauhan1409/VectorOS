"""Personalizer — renders a recipient's signal context into a prompt block.

Keeping prompt-building here (not inside the agent) makes it reusable: the
Writer agent, the A/B optimizer, and the follow-up agent all describe the same
recipient the same way, and it's independently testable.

The context comes from the lead-signal snapshot taken at enrollment
(``Recipient.context``) — so the copy references the *real* reason this company
is worth contacting (funding, launch, hire) rather than generic filler.
"""

from __future__ import annotations

from modules.pulse.inbox.schemas import Recipient
from modules.scout.radar.config import COMPANY_PROFILE


def sender_block(sender_name: str = "") -> str:
    """Who WE are — the fixed half of every email's framing.

    ``sender_name`` (the sending mailbox's display name) becomes the human who
    signs the email, so the sign-off matches the From header instead of being
    invented by the model.
    """
    block = COMPANY_PROFILE.as_prompt()
    if sender_name:
        block += (f"\nSENDER (sign the email as this person): {sender_name}"
                  f" — a real person at {COMPANY_PROFILE.company_name}.")
    return block


def recipient_block(recipient: Recipient) -> str:
    """Everything the writer needs about the person + their buying signal."""
    ctx = recipient.context or {}
    matched = ctx.get("matched_criteria") or []
    matched_str = "; ".join(matched[:3]) if matched else "—"
    lines = [
        f"RECIPIENT NAME: {recipient.name or '(unknown)'}",
        f"RECIPIENT TITLE: {recipient.title or '(unknown)'}",
        f"ROLE CATEGORY: {recipient.role_category or '(unknown)'}",
        f"COMPANY: {recipient.company or ctx.get('company_name', '')}",
        f"COMPANY WEBSITE: {ctx.get('website_url', '—')}",
        "",
        "BUYING SIGNAL (why now):",
        f"  signal type: {ctx.get('signal_type', '—')}",
        f"  what happened: {ctx.get('reason_to_target', '—')}",
        f"  news headline: {ctx.get('article_headline', '—')}",
        f"  published: {ctx.get('published_date', '—')}",
        "",
        f"ICP FIT: score={ctx.get('icp_score', '?')} tier={ctx.get('icp_tier', '?')}",
        f"WHY THEY FIT: {matched_str}",
    ]
    return "\n".join(lines)


def first_name(full_name: str) -> str:
    """Best-effort first name for greetings."""
    parts = (full_name or "").strip().split()
    return parts[0] if parts else "there"
