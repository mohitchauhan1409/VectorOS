"""ConversationAgent — the autonomous SDR that works the reply queue.

Given the full thread, the lead's buying signal, and the prospect's latest
reply, it decides ONE action and drafts the response:

  * ready to talk        → propose times (or share the booking link) · MEETING
  * asks a question      → answer + nudge to a short call · IN_CONVERSATION
  * pushes back          → address the objection + nudge · IN_CONVERSATION
  * not interested       → gracious close, door left open · NOT_INTERESTED
  * points to someone    → thank + ask for the intro · IN_CONVERSATION
  * sensitive / unsure   → ESCALATE, don't auto-send · NEEDS_HUMAN

The agent only *proposes*; the caller enforces the hard guardrails (auto-reply
cap, confidence floor, global on/off). Runs on the strong tier — it's talking
to real buyers.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.pulse.inbox import config
from modules.pulse.inbox.compose import personalizer
from modules.pulse.inbox.config import CONVERSATION_LLM
from modules.pulse.inbox.schemas import ConversationDecision, Recipient

_SYSTEM = """You are a sharp, human-sounding SDR handling replies to cold outreach.
Your goal: turn genuine interest into a booked meeting, and handle everything
else gracefully. You represent OUR COMPANY (below). You are given the RECIPIENT,
their original buying SIGNAL, the full THREAD so far, and their LATEST REPLY.

Choose exactly one action and, when appropriate, draft the reply:

- ask_availability: they're open to talking but no booking link is available →
  warmly propose 2-3 concrete time windows and ask what suits. Set status MEETING.
- share_booking: they're open to talking AND a BOOKING LINK is provided → share
  it in one friendly line. Set status MEETING.
- answer_question: they asked something → answer briefly and specifically from
  OUR COMPANY's value, then propose a quick 15-min call. Status IN_CONVERSATION.
- handle_objection: they pushed back (timing, price, "already use X") →
  acknowledge, reframe with one concrete point, soft nudge. Status IN_CONVERSATION.
- polite_close: clearly not interested → thank them sincerely, no pressure,
  leave the door open for the future. should_send true. Status NOT_INTERESTED.
- acknowledge_referral: they pointed to someone else → thank them and ask for a
  quick intro or the best contact. Status IN_CONVERSATION.
- escalate: pricing negotiation, legal/security/contract, an angry or complex
  message, or you are NOT confident → do NOT draft a send. should_send false.
  Status NEEDS_HUMAN.

Rules for any drafted reply:
- Short, warm, human. Plain text. No corporate filler, no "I hope this finds you well".
- Reply in-thread; keep the subject as "Re: <their subject>".
- One clear next step. Never pushy. Sign off as the SENDER named in OUR COMPANY.
- Never invent facts, prices, dates, or commitments. If it needs a promise you
  can't make, escalate instead.
- Set confidence honestly (0-1). If under ~0.6, prefer escalate."""


class ConversationAgent(BaseAgent):
    """Decides + drafts the reply to a prospect's message."""

    name = "pulse-inbox-conversation"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=CONVERSATION_LLM["provider"], model=CONVERSATION_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(ConversationDecision)

    def run(self, recipient: Recipient, thread: str, latest_reply: str,
            sender_name: str = "") -> ConversationDecision:
        booking = config.MEETING_LINK or "(none — ask for their availability instead)"
        prompt = (
            f"{_SYSTEM}\n\n"
            f"=== OUR COMPANY ===\n{personalizer.sender_block(sender_name)}\n\n"
            f"=== RECIPIENT + BUYING SIGNAL ===\n{personalizer.recipient_block(recipient)}\n\n"
            f"BOOKING LINK: {booking}\n\n"
            f"=== THREAD SO FAR ===\n{thread}\n\n"
            f"=== THEIR LATEST REPLY ===\n{latest_reply}\n\n"
            f"Decide the action and draft the reply."
        )
        decision = self._structured.invoke(prompt)
        fn = personalizer.first_name(recipient.name)
        decision.reply_subject = (decision.reply_subject or "").replace("{{first_name}}", fn).strip()
        decision.reply_body = (decision.reply_body or "").replace("{{first_name}}", fn).strip()
        self.logger.info("Conversation for %s: %s (send=%s, conf=%.2f)",
                         recipient.email, decision.action.value, decision.should_send, decision.confidence)
        return decision
