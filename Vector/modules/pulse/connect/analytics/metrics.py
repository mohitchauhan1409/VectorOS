"""Metrics — LinkedIn campaign performance from the DB.

Key funnel: invites sent → accepted (acceptance rate) → replies (reply rate) →
positive. Per-step variant stats include each arm's P(best) for the bandit.
"""

from __future__ import annotations

from modules.pulse.connect import store
from modules.pulse.connect.analytics.ab_testing import probability_best


def _rate(num: int, den: int) -> float:
    return (num / den) if den else 0.0


def campaign_metrics(campaign_id: int) -> dict:
    conn = store.get_conn()
    status_counts = {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) n FROM prospects WHERE campaign_id=? GROUP BY status",
        (campaign_id,)).fetchall()}
    invites = conn.execute(
        "SELECT COUNT(*) n FROM messages WHERE campaign_id=? AND kind='invite' AND status='sent'",
        (campaign_id,)).fetchone()["n"]
    accepted = conn.execute(
        "SELECT COUNT(*) n FROM prospects WHERE campaign_id=? AND accepted_at IS NOT NULL",
        (campaign_id,)).fetchone()["n"]
    dms = conn.execute(
        "SELECT COUNT(*) n FROM messages WHERE campaign_id=? AND kind='message' AND status IN ('sent','replied')",
        (campaign_id,)).fetchone()["n"]
    reply_rows = conn.execute(
        """SELECT r.classification c, COUNT(*) n FROM replies r
           JOIN prospects p ON p.id=r.prospect_id WHERE p.campaign_id=? GROUP BY r.classification""",
        (campaign_id,)).fetchall()
    replies_by_class = {row["c"]: row["n"] for row in reply_rows}
    total_replies = sum(replies_by_class.values())
    positive = sum(replies_by_class.get(k, 0) for k in ("interested", "objection", "referral"))

    return {
        "campaign_id": campaign_id,
        "prospects_by_status": status_counts,
        "prospects_total": sum(status_counts.values()),
        "invites_sent": invites,
        "accepted": accepted,
        "acceptance_rate": round(_rate(accepted, invites), 4),
        "messages_sent": dms,
        "replies_total": total_replies,
        "replies_by_class": replies_by_class,
        "positive_replies": positive,
        "reply_rate": round(_rate(total_replies, accepted), 4),
        "steps": step_metrics(campaign_id),
    }


def step_metrics(campaign_id: int) -> list[dict]:
    conn = store.get_conn()
    out: list[dict] = []
    for s in conn.execute(
        "SELECT id, step_order, name, kind FROM sequence_steps WHERE campaign_id=? ORDER BY step_order",
        (campaign_id,)).fetchall():
        variants = store.get_step_variants(s["id"], include_paused=True)
        probs = probability_best([v for v in variants if not v.is_paused]) if variants else {}
        arms = [{
            "name": v.name, "sent": v.sent_count, "replies": v.reply_count,
            "reply_rate": round(_rate(v.reply_count, v.sent_count), 4),
            "p_best": round(probs.get(v.id, 0.0), 4), "is_winner": v.is_winner,
        } for v in variants]
        out.append({"step_order": s["step_order"], "name": s["name"], "kind": s["kind"],
                    "variants": arms})
    return out
