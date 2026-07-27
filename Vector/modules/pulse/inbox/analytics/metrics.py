"""Metrics — campaign, step, and variant performance from the DB.

Reply rate is the north-star KPI (opens are unreliable without tracking infra).
All figures are derived from ``messages``/``replies``/``recipients`` so numbers
always reconcile with what actually happened.
"""

from __future__ import annotations

from modules.pulse.inbox import store
from modules.pulse.inbox.analytics.ab_testing import probability_best


def _rate(num: int, den: int) -> float:
    return (num / den) if den else 0.0


def campaign_metrics(campaign_id: int) -> dict:
    """Return a full performance snapshot for a campaign."""
    conn = store.get_conn()

    status_counts = {
        r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) n FROM recipients WHERE campaign_id=? GROUP BY status",
            (campaign_id,)).fetchall()
    }
    sent = conn.execute(
        "SELECT COUNT(*) n FROM messages WHERE campaign_id=? AND status IN "
        "('sent','opened','replied')", (campaign_id,)).fetchone()["n"]
    failed = conn.execute(
        "SELECT COUNT(*) n FROM messages WHERE campaign_id=? AND status='failed'",
        (campaign_id,)).fetchone()["n"]

    reply_rows = conn.execute(
        """SELECT r.classification c, COUNT(*) n FROM replies r
           JOIN messages m ON m.id = r.message_id
           WHERE m.campaign_id=? GROUP BY r.classification""", (campaign_id,)).fetchall()
    replies_by_class = {row["c"]: row["n"] for row in reply_rows}
    total_replies = sum(replies_by_class.values())
    positive = sum(replies_by_class.get(k, 0) for k in ("interested", "objection", "referral"))

    return {
        "campaign_id": campaign_id,
        "recipients_by_status": status_counts,
        "recipients_total": sum(status_counts.values()),
        "emails_sent": sent,
        "emails_failed": failed,
        "replies_total": total_replies,
        "replies_by_class": replies_by_class,
        "positive_replies": positive,
        "reply_rate": round(_rate(total_replies, sent), 4),
        "positive_reply_rate": round(_rate(positive, sent), 4),
        "steps": step_metrics(campaign_id),
    }


def step_metrics(campaign_id: int) -> list[dict]:
    """Per-step variant performance, including each arm's P(best)."""
    conn = store.get_conn()
    out: list[dict] = []
    steps = conn.execute(
        "SELECT id, step_order, name FROM sequence_steps WHERE campaign_id=? ORDER BY step_order",
        (campaign_id,)).fetchall()
    for s in steps:
        variants = store.get_step_variants(s["id"], include_paused=True)
        probs = probability_best([v for v in variants if not v.is_paused]) if variants else {}
        arms = [{
            "id": v.id, "name": v.name, "angle": v.angle,
            "sent": v.sent_count, "replies": v.reply_count,
            "reply_rate": round(_rate(v.reply_count, v.sent_count), 4),
            "posterior_mean": round(v.alpha / (v.alpha + v.beta), 4),
            "p_best": round(probs.get(v.id, 0.0), 4),
            "is_winner": v.is_winner, "is_paused": v.is_paused,
        } for v in variants]
        out.append({
            "step_order": s["step_order"], "name": s["name"],
            "variants": arms,
            "sent": sum(a["sent"] for a in arms),
            "replies": sum(a["replies"] for a in arms),
        })
    return out
