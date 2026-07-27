"""ReplyClassifierAgent — reads an inbound reply and labels the intent.

The label drives automation downstream: an ``interested`` reply stops the
sequence and is handed to Closer; ``unsubscribe`` suppresses the contact;
``out_of_office`` pauses and resumes on the stated date; ``auto_reply`` is
ignored. Runs on the cheap tier — this is high-volume triage, not deep writing.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.pulse.inbox.config import CLASSIFIER_LLM
from modules.pulse.inbox.schemas import ReplyClassification

_SYSTEM = """You classify replies to a cold sales email. Return the single best label.

Labels:
- interested: positive/curious — wants to learn more, book a call, asks a real question.
- not_interested: a clear no, "not now", "we're all set", "no budget".
- objection: engaged but pushing back (price, timing, "already use X") — not a flat no.
- referral: points you to a different person/team ("talk to our CTO", forwards you on).
- out_of_office: automated away/OOO/vacation autoresponder. If a return date is
  stated, put it in resume_date as an ISO date (YYYY-MM-DD).
- unsubscribe: asks to stop / remove / "don't email me" / "unsubscribe".
- auto_reply: other automated messages (delivery receipts, ticket auto-acks, bounce notices).
- other: anything that fits none of the above.

Base the label ONLY on the reply text. Give a confidence 0-1 and one short reason."""


class ReplyClassifierAgent(BaseAgent):
    """Classifies a reply into a :class:`ReplyClassification`."""

    name = "pulse-inbox-reply-classifier"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=CLASSIFIER_LLM["provider"], model=CLASSIFIER_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(ReplyClassification)

    def run(self, subject: str, body: str, original_subject: str = "") -> ReplyClassification:
        prompt = (
            f"{_SYSTEM}\n\n"
            f"OUR ORIGINAL SUBJECT: {original_subject or '(unknown)'}\n"
            f"REPLY SUBJECT: {subject}\n"
            f"REPLY BODY:\n{body[:2000]}\n\n"
            f"Classify this reply."
        )
        result = self._structured.invoke(prompt)
        self.logger.info("Reply classified: %s (%.2f)", result.classification.value, result.confidence)
        return result
