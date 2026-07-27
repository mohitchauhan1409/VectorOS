"""Analytics sub-package — A/B bandit selection, winner promotion, metrics."""

from modules.pulse.inbox.analytics.ab_testing import (
    bandit_selector,
    evaluate_and_promote,
    probability_best,
    thompson_select,
)

__all__ = [
    "bandit_selector",
    "evaluate_and_promote",
    "probability_best",
    "thompson_select",
]
