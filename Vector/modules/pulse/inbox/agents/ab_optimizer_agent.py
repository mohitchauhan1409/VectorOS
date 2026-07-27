"""ABOptimizerAgent — proposes diverse A/B arms for a sequence step.

Each arm is a distinct persuasion *angle* (pain-led, ROI/proof, curiosity,
peer/social, contrarian, …), not a frozen email. At send time the Writer
personalizes real copy for the recipient using the arm's angle, so the bandit
tests strategies that generalize across every lead rather than one hand-written
email. Runs on the cheap tier — this is ideation, done once per campaign setup.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.pulse.inbox import store
from modules.pulse.inbox.compose import personalizer
from modules.pulse.inbox.config import VARIANT_LLM
from modules.pulse.inbox.schemas import Campaign, SequenceStep, Variant, VariantSpecSet

_SYSTEM = """You design A/B test arms for one step of a cold-email sequence.

Given OUR COMPANY, the STEP (its name + base angle + position in the sequence),
and how many arms to produce, output that many DISTINCT persuasion angles worth
testing against each other. Each arm is an instruction the copywriter will
follow to personalize each email — NOT a finished email.

Make the arms genuinely different in strategy (e.g. pain/cost-of-inaction,
concrete ROI or proof point, sharp curiosity/pattern-interrupt, peer/social
proof, short & direct, contrarian take). Keep each arm consistent with the
step's role in the sequence (an intro vs. a nudge vs. a break-up).

For each arm give: name (short label), angle (1-2 sentence strategy the writer
follows), subject_hint (a short note on subject-line style for this arm)."""


class ABOptimizerAgent(BaseAgent):
    """Generates :class:`VariantSpec` arms for a step."""

    name = "pulse-inbox-ab-optimizer"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=VARIANT_LLM["provider"], model=VARIANT_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(VariantSpecSet)

    def run(self, step: SequenceStep, n: int) -> VariantSpecSet:
        prompt = (
            f"{_SYSTEM}\n\n"
            f"=== OUR COMPANY ===\n{personalizer.sender_block()}\n\n"
            f"=== STEP ===\n"
            f"Step {step.step_order}: \"{step.name}\" — base angle: {step.angle}\n\n"
            f"Produce exactly {n} distinct arms."
        )
        result = self._structured.invoke(prompt)
        self.logger.info("Step %s: generated %d A/B arm(s).", step.step_order, len(result.variants))
        return result


def setup_ab_variants(campaign: Campaign, n: int, agent: ABOptimizerAgent | None = None) -> dict:
    """Generate + persist ``n`` A/B arms for every step of a fresh campaign.

    Only replaces placeholder arms that have no send history — steps already
    accumulating data are left untouched so a mid-flight test isn't reset.
    Returns a per-step count summary.
    """
    agent = agent or ABOptimizerAgent()
    summary: dict[str, int] = {}
    for step in campaign.steps:
        existing = store.get_step_variants(step.id, include_paused=True)
        if any(v.sent_count > 0 for v in existing):
            summary[step.name] = len(existing)  # in-flight; leave as-is
            continue
        store.delete_variants(step.id, only_unsent=True)
        specs = agent.run(step, n).variants
        for spec in specs:
            store.add_variant(Variant(
                step_id=step.id, name=spec.name, angle=spec.angle,
                subject_template=spec.subject_hint,
            ))
        summary[step.name] = len(specs)
    return summary
