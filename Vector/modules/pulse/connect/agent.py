"""Connect agent (PULSE module).

The ConnectAgent is the module's orchestrator for LinkedIn outreach. It owns
copy generation (connection notes + messages) and, together with the scheduler
and autopilot, drives connection requests, message sequences, acceptance
tracking, reply handling, and lead conversion — the LinkedIn sibling of Inbox.
"""

from __future__ import annotations

from typing import Any

from modules.common.base_agent import BaseAgent
from modules.pulse.connect.compose import MessageWriterAgent, NoteWriterAgent
from modules.pulse.connect.schemas import ConnectDraft, ConnectMessage, Prospect, SequenceStep, StepKind


class ConnectAgent(BaseAgent):
    """Crafts LinkedIn connection notes + messages and (via scheduler/autopilot)
    runs sequences for decision-makers."""

    name = "pulse-connect-agent"

    def __init__(self, **llm_kwargs: Any) -> None:
        super().__init__(**llm_kwargs)
        self.note_writer = NoteWriterAgent()
        self.message_writer = MessageWriterAgent()

    def compose(self, prospect: Prospect, step: SequenceStep,
                prior: list[ConnectMessage] | None = None, sender_name: str = "") -> ConnectDraft:
        """Write the note or message for a prospect + step."""
        if step.kind == StepKind.INVITE:
            return self.note_writer.run(prospect, step, sender_name=sender_name)
        return self.message_writer.run(prospect, step, prior=prior, sender_name=sender_name)

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Entry point. Use the CLI (``python -m modules.pulse.connect``) or the
        autopilot (``python -m modules.pulse.connect.autopilot``); call
        :meth:`compose` for a single note/message."""
        self.logger.info("Running %s", self.name)
        raise NotImplementedError(
            "Use ConnectAgent.compose(), the CLI, or the autopilot runner.")
