"""SequenceDesignerAgent — designs a whole themed outreach sequence.

Each competing campaign in an experiment is built around a distinct *theme*
(e.g. "direct ROI", "story-driven", "ultra-short & casual", "contrarian take").
This agent turns a theme into a coherent multi-step sequence — intro → nudges →
break-up — where every step's angle expresses that theme. The weekly evolution
loop calls it to spawn fresh challengers when a theme underperforms.

Cheap tier: this is one-time ideation per campaign, not per-recipient writing.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.pulse.inbox.compose import personalizer
from modules.pulse.inbox.config import SEQUENCE_DESIGNER_LLM
from modules.pulse.inbox.schemas import SequenceDesign

_SYSTEM = """You design a cold-email SEQUENCE for a B2B outreach experiment.

Given OUR COMPANY and a THEME (an overall creative/persuasion strategy), design
a coherent {n}-step sequence that expresses that theme end to end. The steps
should escalate naturally: an intro, one or two value nudges, and a graceful
break-up — all consistent with the theme's voice.

For each step provide: name (short label), angle (1-2 sentence instruction the
copywriter follows for THIS step, in the theme's voice), wait_days (days after
the previous step; step 1 is 0). Keep the whole sequence distinct from a generic
template — the theme should be obvious in how each step is framed."""


class SequenceDesignerAgent(BaseAgent):
    """Generates a :class:`SequenceDesign` (themed multi-step sequence)."""

    name = "pulse-inbox-sequence-designer"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=SEQUENCE_DESIGNER_LLM["provider"],
                         model=SEQUENCE_DESIGNER_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(SequenceDesign)

    def run(self, theme: str, n_steps: int = 4) -> SequenceDesign:
        prompt = (
            f"{_SYSTEM.replace('{n}', str(n_steps))}\n\n"
            f"=== OUR COMPANY ===\n{personalizer.sender_block()}\n\n"
            f"=== THEME ===\n{theme}\n\n"
            f"Design the {n_steps}-step sequence now."
        )
        design = self._structured.invoke(prompt)
        if not design.theme:
            design.theme = theme
        self.logger.info("Designed sequence '%s' (%d steps).", theme, len(design.steps))
        return design
