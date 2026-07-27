"""A/B testing as a multi-armed bandit (Thompson sampling).

Why a bandit instead of a fixed 50/50 split? A split wastes half your sends on
the loser until the test ends. Thompson sampling treats each variant as a
Beta(alpha, beta) posterior over its reply rate and, for every send, draws one
sample per arm and picks the highest — so traffic flows to whichever arm is
*probably* best while still exploring the others. You converge on the winner
with far fewer wasted sends, and it self-corrects if early luck was noise.

State lives on each variant row: ``alpha = prior + replies``,
``beta = prior + (sends - replies)`` (maintained by
``store.update_variant_stats``). This module only reads that state to choose and
to decide when a winner is statistically safe to promote.
"""

from __future__ import annotations

import random

from modules.common.logger import get_logger
from modules.pulse.inbox import config, store
from modules.pulse.inbox.schemas import SequenceStep, Variant

logger = get_logger("pulse.inbox.ab")


def thompson_select(variants: list[Variant]) -> Variant | None:
    """Pick a variant by sampling each arm's Beta posterior and taking the max.

    A promoted winner (``is_winner``) short-circuits to always-on. Paused arms
    are ignored. Returns None only if there are no eligible variants.
    """
    eligible = [v for v in variants if not v.is_paused]
    if not eligible:
        return None
    winner = next((v for v in eligible if v.is_winner), None)
    if winner is not None:
        return winner
    # Draw one sample per arm; highest sampled reply-rate wins this send.
    best, best_draw = eligible[0], -1.0
    for v in eligible:
        draw = random.betavariate(max(v.alpha, 1e-6), max(v.beta, 1e-6))
        if draw > best_draw:
            best, best_draw = v, draw
    return best


def bandit_selector(step: SequenceStep) -> Variant | None:
    """Scheduler-facing selector: reads FRESH variant stats from the store
    (the cached campaign snapshot goes stale as replies arrive) and
    Thompson-samples. Drop-in replacement for ``default_variant_selector``."""
    variants = store.get_step_variants(step.id, include_paused=False)
    return thompson_select(variants)


def probability_best(variants: list[Variant], samples: int = 5000) -> dict[int, float]:
    """Monte-Carlo estimate of P(arm is the best) for each variant.

    Draws ``samples`` joint samples from all arms' posteriors and counts how
    often each arm is the maximum. Keyed by variant id.
    """
    active = [v for v in variants if not v.is_paused and v.id is not None]
    wins = {v.id: 0 for v in active}
    if len(active) < 2:
        # Trivial: a lone arm is "best" with probability 1.
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
    """Promote a winner if the test is conclusive; otherwise do nothing.

    Guard rails: every arm must have at least ``MIN_SENDS_BEFORE_PROMOTION``
    sends (so we don't call it on thin data), and one arm's P(best) must reach
    ``WINNER_CONFIDENCE``. On success the winner is flagged and its siblings are
    paused, so all future sends use the winner. Returns the promoted variant.
    """
    variants = store.get_step_variants(step_id, include_paused=False)
    if len(variants) < 2:
        return None
    if any(v.is_winner for v in variants):
        return next(v for v in variants if v.is_winner)
    if any(v.sent_count < config.MIN_SENDS_BEFORE_PROMOTION for v in variants):
        return None

    probs = probability_best(variants)
    best_id = max(probs, key=probs.get)
    if probs[best_id] >= config.WINNER_CONFIDENCE:
        store.promote_variant(step_id, best_id)
        winner = next(v for v in variants if v.id == best_id)
        logger.info("Promoted variant #%s '%s' on step %s (P(best)=%.3f)",
                    best_id, winner.name, step_id, probs[best_id])
        store.log_event("variant_promoted", data={
            "step_id": step_id, "variant_id": best_id, "p_best": probs[best_id]})
        return winner
    logger.info("Step %s: no winner yet (top P(best)=%.3f < %.2f)",
                step_id, probs[best_id], config.WINNER_CONFIDENCE)
    return None
