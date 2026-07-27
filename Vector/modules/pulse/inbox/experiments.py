"""Experiments — campaign-level A/B: several competing sequences, one lead pool.

An *experiment* (campaign group) runs N distinct sequences at once. Incoming
leads are split across them, weighted by how each is performing, so the best
sequence gets most of the traffic while the others keep getting explored. Every
week the loser is retired and a fresh challenger sequence is spawned in its
place — a keep-winners / kill-losers evolution.

Allocation model:
  * Cold start (any arm below EXPERIMENT_MIN_SENDS_FOR_RANKING) → even split.
  * Warm → rank by a Bayesian-smoothed positive-reply rate, then apportion the
    batch by CAMPAIGN_ALLOCATION_WEIGHTS (default 4/2/1/1 for 4 arms) using
    largest-remainder rounding.
"""

from __future__ import annotations

from modules.common.logger import get_logger
from modules.pulse.inbox import config, store
from modules.pulse.inbox.enrollment import iter_contactable
from modules.pulse.inbox.schemas import (
    Campaign,
    CampaignGroup,
    CampaignStatus,
    Recipient,
    SequenceStep,
    Variant,
)

logger = get_logger("pulse.inbox.experiments")


# ---------------------------------------------------------------------------
# Building an experiment
# ---------------------------------------------------------------------------
def _steps_from_design(design) -> list[SequenceStep]:
    steps: list[SequenceStep] = []
    for i, s in enumerate(design.steps, start=1):
        steps.append(SequenceStep(
            step_order=i, name=s.name, angle=s.angle,
            wait_days=(0 if i == 1 else int(s.wait_days)),
            variants=[Variant(name="A", angle=s.angle)],
        ))
    return steps


def create_experiment(name: str, themes: tuple[str, ...] = config.EXPERIMENT_THEMES,
                      size: int = config.EXPERIMENT_SIZE, icp_min_score: int = 0,
                      designer=None) -> CampaignGroup:
    """Create a group of ``size`` competing campaigns, one per theme.

    Idempotent on name. Each campaign is `active` with a themed sequence
    designed by :class:`SequenceDesignerAgent`.
    """
    existing = store.get_group_by_name(name)
    if existing:
        logger.info("Experiment '%s' already exists (#%s).", name, existing.id)
        return existing

    from modules.pulse.inbox.agents.sequence_designer_agent import SequenceDesignerAgent
    designer = designer or SequenceDesignerAgent()

    group = store.create_group(CampaignGroup(name=name, size=size))
    for i, theme in enumerate(list(themes)[:size]):
        design = designer.run(theme, n_steps=len(config.DEFAULT_SEQUENCE))
        campaign = Campaign(
            name=f"{name} · {_theme_label(theme)}",
            description=theme, status=CampaignStatus.ACTIVE, icp_min_score=icp_min_score,
            group_id=group.id, theme=theme, priority=i, steps=_steps_from_design(design))
        store.create_campaign(campaign)
    logger.info("Created experiment '%s' with %d campaigns.", name, min(size, len(themes)))
    return group


def _theme_label(theme: str) -> str:
    """A short human label from a theme sentence (text before the first ':')."""
    return theme.split(":")[0].strip()[:40] or "variant"


# ---------------------------------------------------------------------------
# Scoring + ranking
# ---------------------------------------------------------------------------
def _counts(campaign_id: int) -> tuple[int, int]:
    """(emails_sent, positive_replies) for a campaign."""
    conn = store.get_conn()
    sent = conn.execute(
        "SELECT COUNT(*) n FROM messages WHERE campaign_id=? AND step_id IS NOT NULL "
        "AND status IN ('sent','opened','replied')", (campaign_id,)).fetchone()["n"]
    pos = conn.execute(
        "SELECT COUNT(*) n FROM replies r JOIN messages m ON m.id=r.message_id "
        "WHERE m.campaign_id=? AND r.classification IN ('interested','objection','referral')",
        (campaign_id,)).fetchone()["n"]
    return sent, pos


def score_campaign(campaign_id: int) -> float:
    """Bayesian-smoothed positive-reply rate — the Beta(1+pos, 1+neg) mean.

    Smoothing keeps a zero-reply-but-few-sends arm from looking artificially
    worse (or better) than one with real data."""
    sent, pos = _counts(campaign_id)
    return (1 + pos) / (2 + sent)


def rank_campaigns(group_id: int) -> list[dict]:
    """Live campaigns ranked best-first with their score + send count."""
    ranked = []
    for c in store.list_group_campaigns(group_id, active_only=True):
        sent, pos = _counts(c.id)
        ranked.append({"campaign": c, "score": score_campaign(c.id), "sent": sent, "positive": pos})
    ranked.sort(key=lambda d: (d["score"], d["sent"]), reverse=True)
    return ranked


def update_priorities(group_id: int) -> None:
    """Write current rank (0 = best) back onto each campaign."""
    for rank, d in enumerate(rank_campaigns(group_id)):
        store.update_campaign(d["campaign"].id, priority=rank)


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------
def _apportion(weights: list[float], n: int) -> list[int]:
    """Split ``n`` items across buckets by weight (largest-remainder rounding)."""
    total = sum(weights)
    if n <= 0 or total <= 0:
        return [0] * len(weights)
    raw = [w / total * n for w in weights]
    floors = [int(x) for x in raw]
    remainder = n - sum(floors)
    # Hand the leftover to the largest fractional parts.
    order = sorted(range(len(weights)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in range(remainder):
        floors[order[i % len(order)]] += 1
    return floors


def allocate(group_id: int, n_leads: int) -> list[dict]:
    """Return an allocation plan: ranked campaigns each with an assigned count.

    Cold start (any arm under the ranking threshold) → even split. Warm → the
    performance-weighted split (4/2/1/1-style)."""
    ranked = rank_campaigns(group_id)
    if not ranked or n_leads <= 0:
        return [{**d, "allocated": 0} for d in ranked]

    warm = all(d["sent"] >= config.EXPERIMENT_MIN_SENDS_FOR_RANKING for d in ranked)
    if warm:
        weights = list(config.CAMPAIGN_ALLOCATION_WEIGHTS)[:len(ranked)]
        weights += [1] * (len(ranked) - len(weights))     # pad if more arms than weights
    else:
        weights = [1] * len(ranked)                        # explore evenly

    counts = _apportion(weights, n_leads)
    return [{**d, "allocated": counts[i]} for i, d in enumerate(ranked)]


# ---------------------------------------------------------------------------
# Enrolling leads into the experiment
# ---------------------------------------------------------------------------
def enroll_into_experiment(group_id: int, icp_min_score: int = 0,
                           contactable: list[dict] | None = None) -> dict:
    """Distribute contactable decision-makers across the group's campaigns per
    the current allocation, and enroll each into its assigned campaign."""
    items = contactable if contactable is not None else iter_contactable(icp_min_score)
    plan = allocate(group_id, len(items))
    summary = {"group_id": group_id, "total": len(items), "per_campaign": [], "enrolled": 0}

    cursor = 0
    for row in plan:
        c: Campaign = row["campaign"]
        take = items[cursor:cursor + row["allocated"]]
        cursor += row["allocated"]
        enrolled = 0
        for it in take:
            dm, ctx, lead = it["dm"], it["context"], it["lead"]
            rec = Recipient(
                campaign_id=c.id, lead_slug=lead.get("company_slug", ""),
                company=lead.get("company_name", ""), name=dm.get("name", ""),
                email=dm.get("email", ""), title=dm.get("title", ""),
                role_category=dm.get("role_category", ""),
                email_status=dm.get("email_status", ""), context=ctx)
            if store.enroll_recipient(rec) is not None:
                enrolled += 1
        summary["enrolled"] += enrolled
        summary["per_campaign"].append(
            {"campaign": c.name, "theme": _theme_label(c.theme),
             "allocated": row["allocated"], "enrolled": enrolled, "score": round(row["score"], 4)})
    logger.info("Experiment %s: enrolled %d/%d leads across %d campaigns.",
                group_id, summary["enrolled"], len(items), len(plan))
    return summary


def intake_new(group_id: int, icp_min_score: int = 0) -> dict:
    """Enroll only leads NOT already in the experiment, allocated by current rank.

    This is what the autopilot calls each cycle: newly-generated Scout leads get
    distributed across the competing sequences without re-touching anyone already
    enrolled (so the allocation split reflects only fresh leads)."""
    already = store.group_emails(group_id)
    fresh = [it for it in iter_contactable(icp_min_score)
             if it["dm"].get("email", "").lower() not in already]
    if not fresh:
        return {"group_id": group_id, "total": 0, "enrolled": 0, "per_campaign": []}
    return enroll_into_experiment(group_id, contactable=fresh)


# ---------------------------------------------------------------------------
# Weekly evolution
# ---------------------------------------------------------------------------
def weekly_sync(group_id: int, designer=None) -> dict:
    """Re-rank, then (if warranted) retire the worst campaign and spawn a fresh
    challenger sequence in its place. Retires at most one arm per pass."""
    update_priorities(group_id)
    ranked = rank_campaigns(group_id)
    result = {"group_id": group_id,
              "ranking": [{"campaign": d["campaign"].name, "theme": _theme_label(d["campaign"].theme),
                           "score": round(d["score"], 4), "sent": d["sent"]} for d in ranked],
              "retired": None, "spawned": None}
    if len(ranked) < 2:
        return result

    leader, loser = ranked[0], ranked[-1]
    if (loser["sent"] >= config.RETIRE_MIN_SENDS
            and loser["score"] < leader["score"] * config.RETIRE_SCORE_GAP):
        store.update_campaign(loser["campaign"].id, status=CampaignStatus.ARCHIVED)
        result["retired"] = {"campaign": loser["campaign"].name, "score": round(loser["score"], 4)}
        store.log_event("campaign_retired", campaign_id=loser["campaign"].id,
                        data={"score": loser["score"]})

        challenger = _pick_challenger(group_id)
        if challenger:
            from modules.pulse.inbox.agents.sequence_designer_agent import SequenceDesignerAgent
            designer = designer or SequenceDesignerAgent()
            design = designer.run(challenger, n_steps=len(config.DEFAULT_SEQUENCE))
            group = store.get_group_by_name(_group_name(group_id)) or None
            base = _group_name(group_id)
            camp = Campaign(name=f"{base} · {_theme_label(challenger)} #{loser['campaign'].id}",
                            description=challenger, status=CampaignStatus.ACTIVE,
                            icp_min_score=loser["campaign"].icp_min_score, group_id=group_id,
                            theme=challenger, priority=len(ranked), steps=_steps_from_design(design))
            store.create_campaign(camp)
            result["spawned"] = {"theme": _theme_label(challenger)}
            store.log_event("campaign_spawned", campaign_id=camp.id, data={"theme": challenger})

    update_priorities(group_id)
    logger.info("Weekly sync %s: retired=%s spawned=%s", group_id,
                bool(result["retired"]), bool(result["spawned"]))
    return result


def _group_name(group_id: int) -> str:
    r = store.get_conn().execute("SELECT name FROM campaign_groups WHERE id=?", (group_id,)).fetchone()
    return r["name"] if r else "Experiment"


def _pick_challenger(group_id: int) -> str | None:
    """A challenger theme not already used by any campaign in the group."""
    conn = store.get_conn()
    used = {r["theme"] for r in conn.execute(
        "SELECT theme FROM campaigns WHERE group_id=?", (group_id,)).fetchall()}
    for theme in config.CHALLENGER_THEMES:
        if theme not in used:
            return theme
    return None
