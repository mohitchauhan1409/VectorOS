"""NoteWriterAgent — writes the short note on a LinkedIn connection request.

LinkedIn caps the note at ~200 characters (non-Premium), so this is a different
craft from an email: one warm, specific sentence or two that earns the accept.
Runs on the cheap tier (it's short) and hard-enforces the length limit.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.pulse.connect.compose import personalizer
from modules.pulse.connect.config import NOTE_LLM
from modules.pulse.connect.schemas import ConnectDraft, Prospect, SequenceStep

NOTE_MAX_CHARS = 200

_SYSTEM = """You write the short note attached to a LinkedIn connection request.

Given OUR COMPANY, the PROSPECT and their buying SIGNAL, and the ANGLE, write ONE
warm, specific note that earns the accept.

Hard rules:
- STRICT LIMIT: aim for 140-180 characters, NEVER exceed 190. Hard LinkedIn cap.
- Write a COMPLETE note that ends on a finished sentence. Do NOT cram — if you're
  running long, cut a clause; never leave a dangling fragment like "Worth a".
- Reference their real signal in a few words (the funding/launch/hire) — prove
  it's not a mass invite. NO generic "I'd like to add you to my network".
- Peer-to-peer tone, not salesy. Do NOT pitch here — the goal is just to connect.
  One light reason we'd be worth knowing. Brevity beats completeness.
- No links, no emojis, no hashtags. Plain text. You may greet by first name.
- NO sign-off/signature — do NOT end with your name or company. LinkedIn shows
  who's sending it; a signature in a connection note looks automated.
- Return only the note text in ``body``."""


class NoteWriterAgent(BaseAgent):
    """Generates a ≤300-char connection-request note (:class:`ConnectDraft`)."""

    name = "connect-note-writer"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=NOTE_LLM["provider"], model=NOTE_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(ConnectDraft)

    def run(self, prospect: Prospect, step: SequenceStep, angle: str | None = None,
            sender_name: str = "") -> ConnectDraft:
        angle = angle or step.angle
        prompt = (
            f"{_SYSTEM}\n\n"
            f"=== OUR COMPANY ===\n{personalizer.sender_block()}\n\n"
            f"=== PROSPECT + SIGNAL ===\n{personalizer.prospect_block(prospect)}\n\n"
            f"=== THIS NOTE ===\nANGLE: {angle}\n\nWrite the connection note now (≤300 chars)."
        )
        draft = self._structured.invoke(prompt)
        fn = personalizer.first_name(prospect.name)
        body = (draft.body or "").replace("{{first_name}}", fn).strip()
        if len(body) > NOTE_MAX_CHARS:                       # hard safety fallback
            body = self._trim(body, NOTE_MAX_CHARS)
        draft.body = body
        self.logger.info("Note for %s (%d chars).", prospect.name, len(body))
        return draft

    @staticmethod
    def _trim(text: str, limit: int) -> str:
        """Trim to ``limit`` without leaving a dangling fragment: prefer cutting
        back to the last complete sentence; else clean word-boundary cut."""
        clipped = text[:limit]
        for end in (". ", "? ", "! ", ".", "?", "!"):
            idx = clipped.rfind(end)
            if idx >= limit * 0.5:                           # keep a sensible amount
                return clipped[: idx + 1].strip()
        return clipped.rsplit(" ", 1)[0].rstrip(" ,;:-") + "."
