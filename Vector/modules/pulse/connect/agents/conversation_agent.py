"""ConversationAgent — autonomous handling of LinkedIn replies.

Same brain as Inbox's conversation agent, tuned for LinkedIn DM tone. Given the
thread + the prospect's latest reply, it decides one action and drafts a short
reply: propose times / share booking link (→ meeting), answer + nudge
(→ in_conversation), handle an objection, close politely (→ not_interested), or
escalate anything sensitive (→ needs_human). The dispatcher enforces the hard
guardrails (auto-reply cap, confidence floor, global on/off).
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.pulse.connect import config
from modules.pulse.connect.compose import personalizer
from modules.pulse.connect.config import CONVERSATION_LLM
from modules.pulse.connect.schemas import ConversationDecision, Prospect

_SYSTEM = """You are a sharp, human-sounding SDR handling LinkedIn DM replies.
Goal: turn genuine interest into a booked call, handle everything else
gracefully. You represent OUR COMPANY. You get the PROSPECT + their buying
SIGNAL, the THREAD so far, and their LATEST REPLY.

Pick exactly one action and (when appropriate) draft the reply:
- ask_availability: they'll talk, no booking link → propose 2-3 concrete windows. new_status MEETING.
- share_booking: they'll talk AND a BOOKING LINK is provided → share it in one line. new_status MEETING.
- answer_question: they asked something → answer briefly + propose a quick call. new_status IN_CONVERSATION.
- handle_objection: pushback → acknowledge, one concrete reframe, soft nudge. new_status IN_CONVERSATION.
- polite_close: not interested → thank them, no pressure, door open. should_send true. new_status NOT_INTERESTED.
- acknowledge_referral: pointed elsewhere → thank + ask for the intro. new_status IN_CONVERSATION.
- escalate: pricing/legal/security, angry/complex, or you're unsure → do NOT draft. should_send false. new_status NEEDS_HUMAN.

Style: LinkedIn DM — short (1-4 sentences), warm, no email formalities, no
subject, and NO sign-off/signature (never end with your name or company —
LinkedIn shows who you are). One clear next step, never pushy. Never invent
facts/prices/dates. Set confidence honestly (0-1); under ~0.6 prefer escalate.
Put the message in reply_body (plain text)."""


class ConversationAgent(BaseAgent):
    name = "connect-conversation"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=CONVERSATION_LLM["provider"], model=CONVERSATION_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(ConversationDecision)

    def run(self, prospect: Prospect, thread: str, latest_reply: str,
            sender_name: str = "") -> ConversationDecision:
        booking = config.MEETING_LINK or "(none — ask for their availability instead)"
        prompt = (
            f"{_SYSTEM}\n\n"
            f"=== OUR COMPANY ===\n{personalizer.sender_block()}\n\n"
            f"=== PROSPECT + SIGNAL ===\n{personalizer.prospect_block(prospect)}\n\n"
            f"BOOKING LINK: {booking}\n\n"
            f"=== THREAD SO FAR ===\n{thread}\n\n"
            f"=== THEIR LATEST REPLY ===\n{latest_reply}\n\n"
            f"Decide the action and draft the reply."
        )
        decision = self._structured.invoke(prompt)
        fn = personalizer.first_name(prospect.name)
        decision.reply_body = (decision.reply_body or "").replace("{{first_name}}", fn).strip()
        self.logger.info("Conversation %s: %s (send=%s, conf=%.2f)",
                         prospect.name, decision.action.value, decision.should_send, decision.confidence)
        return decision
