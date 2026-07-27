"""WriterAgent — writes one personalized cold email for a recipient + step.

This is the quality-critical agent, so it runs on the strong tier (WRITER_LLM).
It takes who-we-are (COMPANY_PROFILE), who-they-are + their buying signal
(Recipient.context), and the step's persuasion angle, and returns a finished
``EmailDraft`` (subject + plain-text body) — fully personalized, no
mail-merge placeholders left behind.

Cold-email craft is baked into the system prompt: short, specific to the
signal, one soft CTA, human tone, nothing that trips spam filters.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.pulse.inbox.compose import personalizer
from modules.pulse.inbox.config import WRITER_LLM
from modules.pulse.inbox.schemas import EmailDraft, Recipient, SequenceStep

_SYSTEM = """You are an elite B2B cold-email copywriter. You write emails that get replies.

You are given OUR COMPANY (what we sell), a RECIPIENT and their real BUYING
SIGNAL (a recent event that makes now the right time to reach out), and the
ANGLE for this specific email in a sequence.

Write ONE short cold email. Rules:
- Open with a specific, genuine reference to THEIR buying signal — never generic
  flattery. Prove you actually know why you're reaching out to *them*.
- Connect their situation to a concrete problem OUR product solves. Be specific,
  not buzzwordy. No "I hope this finds you well", no "I wanted to reach out".
- 50-110 words in the body. Short sentences. Sound like a real person typing to
  one person, not a marketing blast.
- Exactly one soft, low-friction call to action (a question, or "worth a quick
  look?"). Never demand a meeting time in a first touch.
- Subject line: 3-6 words, lowercase-ish, curiosity or specificity — NOT salesy.
  No "Re:" fakery, no ALL CAPS, no emojis, no exclamation marks.
- Follow the ANGLE for this step (e.g. an intro vs. a value nudge vs. a break-up).
- Output the body as plain text. You MAY use "{{first_name}}" once in the
  greeting if natural; no other placeholders, no brackets, no [Company].
- Do NOT invent facts about the recipient beyond the signal provided.
- Sign off as the sender described in OUR COMPANY (first name + company)."""


class WriterAgent(BaseAgent):
    """Generates a personalized ``EmailDraft`` for a recipient + sequence step."""

    name = "pulse-inbox-writer"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=WRITER_LLM["provider"], model=WRITER_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(EmailDraft)

    def run(self, recipient: Recipient, step: SequenceStep, angle: str | None = None,
            sender_name: str = "") -> EmailDraft:
        """Write the email for ``recipient`` at ``step``.

        Args:
            recipient: The enrolled person (carries the signal context).
            step: The sequence step (name + default angle + order).
            angle: Optional override for the persuasion angle (used by the A/B
                optimizer to steer a specific variant). Falls back to the step's.
            sender_name: Display name of the sending mailbox — used to sign off.
        """
        angle = angle or step.angle
        prompt = (
            f"{_SYSTEM}\n\n"
            f"=== OUR COMPANY ===\n{personalizer.sender_block(sender_name)}\n\n"
            f"=== RECIPIENT + BUYING SIGNAL ===\n{personalizer.recipient_block(recipient)}\n\n"
            f"=== THIS EMAIL ===\n"
            f"Step {step.step_order} of the sequence — \"{step.name}\".\n"
            f"ANGLE: {angle}\n\n"
            f"Write the subject and body now."
        )
        draft = self._structured.invoke(prompt)
        draft = self._finalize(draft, recipient)
        self.logger.info("Wrote step %s for %s <%s>: %r",
                         step.step_order, recipient.name, recipient.email, draft.subject)
        return draft

    @staticmethod
    def _finalize(draft: EmailDraft, recipient: Recipient) -> EmailDraft:
        """Fill the one allowed placeholder and tidy whitespace."""
        fn = personalizer.first_name(recipient.name)
        draft.subject = (draft.subject or "").replace("{{first_name}}", fn).strip()
        draft.body = (draft.body or "").replace("{{first_name}}", fn).strip()
        return draft
