"""SchedulingAgent — the brain that converges a prospect to a booked time.

Given the thread, the client's latest message, the CURRENT time, and our REAL
open slots, it decides one action and writes the reply:

  * propose   — offer a few concrete open slots
  * book      — the client accepted/named a time we can honor (chosen_slot_start
                MUST be one of the free slots — the caller validates this)
  * negotiate — their requested time is taken → counter with the nearest openings
  * ask       — nothing concrete yet → ask what works
  * decline   — they no longer want to meet

It only ever books a slot that's genuinely free (the caller double-checks), so
it can't invent availability. It reasons over natural-language times ("Thursday
afternoon", "next week") using the provided current date + timezone.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.pulse.scheduling import config
from modules.pulse.scheduling.config import SCHEDULER_LLM
from modules.pulse.scheduling.schemas import SchedulingDecision, TimeSlot

_SYSTEM = """You are a scheduling assistant booking an intro call between US and a CLIENT.
You are given the CURRENT date/time + timezone, the CHANNEL (email or linkedin),
the EMAIL ON FILE (may be blank), a PENDING SLOT (set only when we've agreed a
time and are now collecting the email), the conversation, the client's LATEST
message, and OUR REAL OPEN SLOTS (the only times we may offer or book — never
invent a time outside this list).

Decide ONE action:
- propose: no specific time yet, or "you pick"/"whenever" → offer the first 2-3
  open slots. No chosen_slot_start.
- negotiate: they asked for a time NOT in our open slots (we're busy) → say it's
  taken, offer the 2-3 closest open slots. No chosen_slot_start.
- ask: positive but zero timing signal → ask what window suits (hint you're open
  this week). No chosen_slot_start.
- confirm_email: USE THIS on the LINKEDIN channel the moment the client agrees to
  a specific open time AND we don't yet have a confirmed email (PENDING SLOT is
  empty). Put the agreed slot in chosen_slot_start. In the reply:
    * if EMAIL ON FILE is present: "Perfect, <day/time> works. I'll send a
      calendar invite to <email> — is that the best address? Or I can just drop a
      Google Meet link right here."
    * if EMAIL ON FILE is blank: "Perfect, <day/time> works. What's the best email
      for the calendar invite? Or I can just send a Google Meet link here."
- book: we're ready to actually book. Set chosen_slot_start (the agreed slot; on
  linkedin this equals PENDING SLOT). Then resolve the email:
    * if the client confirmed/gave an email → put it in attendee_email.
    * if the client said "just the link"/"no email"/"send the meet link" → set
      meet_link_only=true and leave attendee_email blank.
    * on the EMAIL channel there's no confirm step — book directly with
      attendee_email = EMAIL ON FILE.
  Write a short confirmation ("Locked in for <day/time> — invite on its way" /
  "…here's the Meet link").
- cancel: there is an EXISTING BOOKING and the client wants to cancel entirely
  (not move it). Confirm the cancellation warmly, leave the door open.
- decline: they no longer want to meet. Short, gracious.

RESCHEDULE: if there is an EXISTING BOOKING and the client wants to MOVE it, treat
it like normal scheduling — propose/negotiate a new open slot, and when they pick
one use action=book (the system cancels the old event automatically). Only use
'cancel' when they want no meeting at all.

Rules:
- NEVER write a meeting URL / Meet link yourself — the system attaches the real
  link automatically. Just say the link is coming (e.g. "Meet link below").
- Short, warm, human. At most 3 time options. Always state the timezone.
- Never promise a time that isn't in OUR OPEN SLOTS. When unsure, propose.
- LINKEDIN: never claim you've sent an invite until you have an email OR the
  client chose the Meet-link option. Use confirm_email first.
- No sign-off/signature. Match natural-language times to real slots via CURRENT date."""


class SchedulingAgent(BaseAgent):
    name = "pulse-scheduling-agent"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=SCHEDULER_LLM["provider"], model=SCHEDULER_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(SchedulingDecision)

    def run(self, attendee: str, company: str, thread: str, latest_reply: str,
            slots: list[TimeSlot], now_label: str, tz_label: str,
            channel: str = "email", known_email: str = "",
            pending_slot_label: str = "", existing_booking_label: str = "") -> SchedulingDecision:
        slot_lines = "\n".join(f"- {s.label()} ({tz_label})  [iso: {s.iso()}]" for s in slots) \
            or "(no open slots in range)"
        prompt = (
            f"{_SYSTEM}\n\n"
            f"CURRENT: {now_label} ({tz_label})\n"
            f"CHANNEL: {channel}\n"
            f"EMAIL ON FILE: {known_email or '(none)'}\n"
            f"EXISTING BOOKING (already on the calendar): {existing_booking_label or '(none)'}\n"
            f"PENDING SLOT (email being collected for this agreed time): {pending_slot_label or '(none)'}\n"
            f"CLIENT: {attendee}{(' at ' + company) if company else ''}\n\n"
            f"=== CONVERSATION SO FAR ===\n{thread}\n\n"
            f"=== CLIENT'S LATEST MESSAGE ===\n{latest_reply}\n\n"
            f"=== OUR OPEN SLOTS (offer/book only from these) ===\n{slot_lines}\n\n"
            f"Decide the action and write the reply."
        )
        decision = self._structured.invoke(prompt)
        self.logger.info("Scheduling %s: %s (slot=%s, conf=%.2f)",
                         attendee, decision.action.value, decision.chosen_slot_start, decision.confidence)
        return decision
