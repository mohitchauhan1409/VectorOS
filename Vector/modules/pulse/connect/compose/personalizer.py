"""Personalizer — renders a prospect's signal context for the LinkedIn writers.

Reuses Inbox's sender framing (who we are) and adds a LinkedIn-prospect block.
Keeping this here means the note writer, message writer, and conversation agent
all describe a prospect identically.
"""

from __future__ import annotations

# Reuse the shared sender framing + name helper from Inbox (channel-agnostic).
from modules.pulse.inbox.compose.personalizer import first_name, sender_block  # noqa: F401
from modules.pulse.connect.schemas import Prospect


def prospect_block(prospect: Prospect) -> str:
    ctx = prospect.context or {}
    matched = ctx.get("matched_criteria") or []
    lines = [
        f"PROSPECT NAME: {prospect.name or '(unknown)'}",
        f"PROSPECT TITLE: {prospect.title or '(unknown)'}",
        f"ROLE: {prospect.role_category or '(unknown)'}",
        f"COMPANY: {prospect.company or ctx.get('company_name', '')}",
        "",
        "BUYING SIGNAL (why now):",
        f"  signal type: {ctx.get('signal_type', '—')}",
        f"  what happened: {ctx.get('reason_to_target', '—')}",
        f"  headline: {ctx.get('article_headline', '—')}",
        "",
        f"WHY THEY FIT: {'; '.join(matched[:3]) if matched else '—'}",
    ]
    return "\n".join(lines)
