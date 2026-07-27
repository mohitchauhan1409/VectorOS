"""FollowUpAgent — writes a follow-up that builds on the existing thread.

Unlike a canned "just bumping this" line, this reads what we already sent and
writes a genuinely new touch: a fresh angle, no repetition, shorter than the
first email, and threaded onto the same conversation. Runs on the strong tier —
follow-ups are where most sequences lose the reader, so copy quality matters.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.pulse.inbox.compose import personalizer
from modules.pulse.inbox.config import WRITER_LLM
from modules.pulse.inbox.schemas import EmailDraft, Message, Recipient, SequenceStep

_SYSTEM = """You write ONE follow-up email in an ongoing cold-outreach thread.

You get OUR COMPANY, the RECIPIENT + their buying signal, the PRIOR EMAILS we
already sent them (which got no reply), and the ANGLE for this follow-up.

Rules:
- Do NOT repeat what earlier emails already said. Add a NEW reason to engage
  (a different benefit, a proof point, a lighter ask, or a graceful break-up).
- Shorter than the first email: 30-70 words. Follow-ups should feel effortless.
- Reference the thread naturally ("circling back", "one more thought") without
  guilt-tripping ("did you see my email?").
- Exactly one low-friction CTA. A break-up step should make it easy to say no.
- Subject: keep the thread's subject feel. Prefer replying in-thread, so a short
  subject is fine; no "Re: Re: Re:" pileups, no emojis, no exclamation marks.
- Body is plain text. You MAY use "{{first_name}}" once. No other placeholders.
- Sign off as the sender in OUR COMPANY."""


class FollowUpAgent(BaseAgent):
    """Writes a thread-aware follow-up (:class:`EmailDraft`)."""

    name = "pulse-inbox-followup"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=WRITER_LLM["provider"], model=WRITER_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(EmailDraft)

    def run(self, recipient: Recipient, step: SequenceStep, prior: list[Message],
            angle: str | None = None, sender_name: str = "") -> EmailDraft:
        angle = angle or step.angle
        thread = "\n\n".join(
            f"--- Email {i} (subject: {m.subject}) ---\n{m.body}"
            for i, m in enumerate(prior, start=1)
        ) or "(none)"
        prompt = (
            f"{_SYSTEM}\n\n"
            f"=== OUR COMPANY ===\n{personalizer.sender_block(sender_name)}\n\n"
            f"=== RECIPIENT + BUYING SIGNAL ===\n{personalizer.recipient_block(recipient)}\n\n"
            f"=== PRIOR EMAILS (no reply yet) ===\n{thread}\n\n"
            f"=== THIS FOLLOW-UP ===\n"
            f"Step {step.step_order} — \"{step.name}\". ANGLE: {angle}\n\n"
            f"Write the follow-up subject and body now."
        )
        draft = self._structured.invoke(prompt)
        fn = personalizer.first_name(recipient.name)
        draft.subject = (draft.subject or "").replace("{{first_name}}", fn).strip()
        draft.body = (draft.body or "").replace("{{first_name}}", fn).strip()
        self.logger.info("Follow-up step %s for %s: %r", step.step_order, recipient.email, draft.subject)
        return draft
