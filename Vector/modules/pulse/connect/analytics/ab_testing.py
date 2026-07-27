"""A/B testing as a Thompson-sampling bandit (same model as Inbox).

Each variant is a Beta(alpha, beta) posterior over its reply rate; the selector
samples each arm and sends via the highest draw, so traffic flows to the winning
note/message while still exploring. A winner is promoted once it's statistically
safe. Reads/writes the Connect store.
"""

from __future__ import annotations

import random

from modules.common.logger import get_logger
from modules.pulse.connect import config, store
from modules.pulse.connect.schemas import SequenceStep, Variant

logger = get_logger("pulse.connect.ab")


def thompson_select(variants: list[Variant]) -> Variant | None:
    eligible = [v for v in variants if not v.is_paused]
    if not eligible:
        return None
    winner = next((v for v in eligible if v.is_winner), None)
    if winner is not None:
        return winner
    best, best_draw = eligible[0], -1.0
    for v in eligible:
        draw = random.betavariate(max(v.alpha, 1e-6), max(v.beta, 1e-6))
        if draw > best_draw:
            best, best_draw = v, draw
    return best


def bandit_selector(step: SequenceStep) -> Variant | None:
    """Scheduler-facing selector reading FRESH variant stats from the store."""
    return thompson_select(store.get_step_variants(step.id, include_paused=False))


def probability_best(variants: list[Variant], samples: int = 4000) -> dict[int, float]:
    active = [v for v in variants if not v.is_paused and v.id is not None]
    wins = {v.id: 0 for v in active}
    if len(active) < 2:
        return {v.id: 1.0 for v in active}
    for _ in range(samples):
        best_id, best_draw = None, -1.0
        for v in active:
            draw = random.betavariate(max(v.alpha, 1e-6), max(v.beta, 1e-6))
            if draw > best_draw:
                best_id, best_draw = v.id, draw
        wins[best_id] += 1
    return {vid: n / samples for vid, n in wins.items()}


def evaluate_and_promote(step_id: int) -> Variant | None:
    variants = store.get_step_variants(step_id, include_paused=False)
    if len(variants) < 2 or any(v.is_winner for v in variants):
        return next((v for v in variants if v.is_winner), None)
    if any(v.sent_count < config.MIN_SENDS_BEFORE_PROMOTION for v in variants):
        return None
    probs = probability_best(variants)
    best_id = max(probs, key=probs.get)
    if probs[best_id] >= config.WINNER_CONFIDENCE:
        store.promote_variant(step_id, best_id)
        winner = next(v for v in variants if v.id == best_id)
        logger.info("Promoted variant #%s on step %s (P(best)=%.3f)", best_id, step_id, probs[best_id])
        return winner
    return None
