"""Inbox agent (PULSE module).

The InboxAgent is the module's orchestrator. It owns the copy-generation step
(via WriterAgent) and, in later phases, coordinates sending, reply handling,
sequences, and A/B optimization. Sending itself lives in ``delivery/`` and
scheduling in ``sequences/`` — this class wires them together.
"""

from __future__ import annotations

from typing import Any

from modules.common.base_agent import BaseAgent
from modules.pulse.inbox.compose import WriterAgent
from modules.pulse.inbox.schemas import EmailDraft, Recipient, SequenceStep


class InboxAgent(BaseAgent):
    """Crafts personalized emails, builds sequences, and (later) sends them."""

    name = "pulse-inbox-agent"

    def __init__(self, **llm_kwargs: Any) -> None:
        super().__init__(**llm_kwargs)
        # The writer runs on its own (strong) tier, independent of this agent's LLM.
        self.writer = WriterAgent()

    def compose(self, recipient: Recipient, step: SequenceStep, angle: str | None = None) -> EmailDraft:
        """Write a single personalized email for a recipient + sequence step."""
        return self.writer.run(recipient, step, angle=angle)

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Entry point. Use the CLI (``python -m modules.pulse.inbox``) for the
        interactive preview / send flows; call :meth:`compose` for one email."""
        self.logger.info("Running %s", self.name)
        raise NotImplementedError(
            "Use InboxAgent.compose() or the CLI. Full run orchestration lands with the scheduler (P3)."
        )
