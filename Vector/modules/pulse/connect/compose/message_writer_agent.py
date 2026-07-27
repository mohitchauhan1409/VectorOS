"""MessageWriterAgent — writes LinkedIn DMs once a prospect has connected.

Handles the intro (right after they accept), value nudges, and the break-up,
and is thread-aware: later messages read the prior ones so they never repeat.
LinkedIn DMs are shorter and more casual than email — no subject line, no
sign-off block. Runs on the strong tier (these go to real buyers).
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.pulse.connect.compose import personalizer
from modules.pulse.connect.config import MESSAGE_LLM
from modules.pulse.connect.schemas import ConnectDraft, ConnectMessage, Prospect, SequenceStep

_SYSTEM = """You write ONE LinkedIn direct message in an outreach sequence.

You get OUR COMPANY, the PROSPECT + their buying SIGNAL, the ANGLE for this
message, and any PRIOR MESSAGES already sent in this chat (they connected with
us, so messaging is allowed).

Rules:
- LinkedIn DM style: short (2-5 sentences), warm, conversational, like a real
  person typing in the chat box. No email formalities, no subject.
- NO sign-off or signature of ANY kind — do NOT end with "— Name", "Name,
  Company", or a company name. LinkedIn already shows who you are; a signature
  looks like a bot. Just end on your last sentence.
- If PRIOR MESSAGES exist, do NOT repeat them — add a new angle and reference the
  thread naturally.
- The first message should thank them for connecting and tie their signal to one
  concrete way we help, ending in one light question.
- Exactly one low-friction call to action. A break-up message makes it easy to
  say no and leaves the door open.
- No links unless essential, no emojis spam, no hashtags. You may use the first
  name once. Return only the message text in ``body``."""


class MessageWriterAgent(BaseAgent):
    """Generates a LinkedIn DM (:class:`ConnectDraft`), thread-aware."""

    name = "connect-message-writer"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=MESSAGE_LLM["provider"], model=MESSAGE_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(ConnectDraft)

    def run(self, prospect: Prospect, step: SequenceStep, prior: list[ConnectMessage] | None = None,
            angle: str | None = None, sender_name: str = "") -> ConnectDraft:
        angle = angle or step.angle
        prior = prior or []
        thread = "\n\n".join(
            f"--- Message {i} ---\n{m.body}" for i, m in enumerate(prior, start=1)
            if m.kind.value == "message") or "(none — this is the first message)"
        prompt = (
            f"{_SYSTEM}\n\n"
            f"=== OUR COMPANY ===\n{personalizer.sender_block()}\n\n"
            f"=== PROSPECT + SIGNAL ===\n{personalizer.prospect_block(prospect)}\n\n"
            f"=== PRIOR MESSAGES ===\n{thread}\n\n"
            f"=== THIS MESSAGE ===\nStep \"{step.name}\". ANGLE: {angle}\n\nWrite the message now."
        )
        draft = self._structured.invoke(prompt)
        fn = personalizer.first_name(prospect.name)
        draft.body = (draft.body or "").replace("{{first_name}}", fn).strip()
        self.logger.info("Message '%s' for %s.", step.name, prospect.name)
        return draft
