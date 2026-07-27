"""Dispatcher — the coordination layer over send + reply-poll + DB state.

Keeps the raw transports (:mod:`smtp_sender`, :mod:`imap_reader`) dumb and
side-effect-free; everything that touches campaign state lives here:

  send_message(...)   compose row → SMTP send → update message/recipient/variant
  poll_replies(...)   IMAP fetch → match to our sends → save reply → classify →
                      stop/pause the sequence as the label dictates

The scheduler (P3) calls :func:`send_message`; a poller loop calls
:func:`poll_replies`. Both are safe to run repeatedly.
"""

from __future__ import annotations

from datetime import datetime, timezone

from modules.common.logger import get_logger
from modules.pulse.inbox import config, store
from modules.pulse.inbox.delivery import accounts
from modules.pulse.inbox.delivery.imap_reader import ImapReader
from modules.pulse.inbox.delivery.smtp_sender import DryRunSender, SmtpSender, SmtpSendError
from modules.pulse.inbox.schemas import (
    EmailDraft,
    Mailbox,
    Message,
    MessageStatus,
    Recipient,
    ReplyClass,
    Reply,
    RecipientStatus,
    SequenceStep,
    Variant,
    utcnow_iso,
)

logger = get_logger("pulse.inbox.dispatcher")


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------
def send_message(
    recipient: Recipient,
    step: SequenceStep,
    variant: Variant,
    draft: EmailDraft,
    mailbox: Mailbox,
    sender: SmtpSender | None = None,
    dry_run: bool = False,
) -> Message:
    """Send one composed email and record the full outcome.

    Threads correctly: a step > 1 reply-links to the recipient's existing
    thread. Updates message status, the recipient's progress, the variant's
    bandit stats, and warmup state. Returns the persisted Message (status
    ``sent`` or ``failed``). With ``dry_run`` no mail is sent but state advances
    identically (uses :class:`DryRunSender`).
    """
    if sender is None:
        sender = DryRunSender() if dry_run else SmtpSender()

    msg = _deliver(recipient, mailbox, draft.subject, draft.body,
                   step_id=step.id, variant_id=variant.id, sender=sender, dry_run=dry_run)
    if msg.status != MessageStatus.SENT:
        return msg

    # Sequence-specific bookkeeping: advance the step + credit the variant trial.
    store.update_recipient(recipient.id, current_step=step.step_order,
                           last_sent_at=msg.sent_at, mailbox_id=mailbox.id)
    if variant.id is not None:
        store.update_variant_stats(variant.id, sent_delta=1)
    store.log_event("sent", recipient_id=recipient.id, campaign_id=recipient.campaign_id,
                    data={"step": step.step_order, "variant_id": variant.id, "mailbox": mailbox.email})
    return msg


def _deliver(recipient: Recipient, mailbox: Mailbox, subject: str, body: str, *,
             step_id: int | None, variant_id: int | None,
             sender: SmtpSender, dry_run: bool) -> Message:
    """Core send: thread-link, persist, transmit, mark sent/failed. Shared by
    sequence sends and conversation replies."""
    thread_id = store.latest_thread_id(recipient.id) if recipient.id else ""
    in_reply_to = ""
    if thread_id:
        prev = store.messages_for_recipient(recipient.id)
        if prev:
            in_reply_to = prev[-1].rfc_message_id      # reply to the most recent message

    msg = store.create_message(Message(
        recipient_id=recipient.id, campaign_id=recipient.campaign_id, step_id=step_id,
        variant_id=variant_id, mailbox_id=mailbox.id, to_email=recipient.email,
        from_email=mailbox.email, subject=subject, body=body,
        thread_id=thread_id, in_reply_to=in_reply_to, status=MessageStatus.QUEUED,
    ))

    credentials = {} if dry_run else accounts.get_credentials(mailbox.email)
    if credentials is None:
        return _fail(msg, recipient, f"No credentials for {mailbox.email}")
    try:
        sender.send(mailbox, credentials, msg)
    except SmtpSendError as exc:
        return _fail(msg, recipient, str(exc))

    now = utcnow_iso()
    store.update_message(msg.id, status=MessageStatus.SENT, sent_at=now,
                         rfc_message_id=msg.rfc_message_id, thread_id=msg.thread_id,
                         from_email=msg.from_email)
    msg.status, msg.sent_at = MessageStatus.SENT, now
    accounts.note_send(mailbox)
    return msg


def send_reply(recipient: Recipient, subject: str, body: str,
               sender: SmtpSender | None = None, dry_run: bool = False) -> Message | None:
    """Send an autonomous conversation reply in the recipient's existing thread.

    Uses the recipient's sticky mailbox (the one that owns the thread) and is
    NOT subject to daily caps — replying to an engaged prospect always goes out.
    Not a sequence step: step_id/variant_id stay NULL. Returns the Message, or
    None if no mailbox is resolvable.
    """
    if sender is None:
        sender = DryRunSender() if dry_run else SmtpSender()
    mailbox = store.get_mailbox(recipient.mailbox_id) if recipient.mailbox_id else None
    if mailbox is None:
        mailbox = accounts.pick_mailbox()
    if mailbox is None:
        logger.warning("No mailbox to send reply to %s", recipient.email)
        return None

    msg = _deliver(recipient, mailbox, subject, body,
                   step_id=None, variant_id=None, sender=sender, dry_run=dry_run)
    if msg.status == MessageStatus.SENT:
        store.update_recipient(recipient.id, last_sent_at=msg.sent_at, mailbox_id=mailbox.id)
        store.log_event("auto_reply_sent", recipient_id=recipient.id,
                        campaign_id=recipient.campaign_id, data={"subject": subject})
    return msg


def _fail(msg: Message, recipient: Recipient, error: str) -> Message:
    logger.warning("Send failed for %s: %s", recipient.email, error)
    store.update_message(msg.id, status=MessageStatus.FAILED, error=error)
    msg.status, msg.error = MessageStatus.FAILED, error
    store.log_event("send_failed", recipient_id=recipient.id,
                    campaign_id=recipient.campaign_id, data={"error": error})
    return msg


# ---------------------------------------------------------------------------
# Reply polling + autonomous conversation handling
# ---------------------------------------------------------------------------
# Classes the ConversationAgent works (genuine human replies). auto_reply /
# out_of_office / unsubscribe are handled mechanically before the agent.
_CONVERSATIONAL = {
    ReplyClass.INTERESTED, ReplyClass.NOT_INTERESTED,
    ReplyClass.OBJECTION, ReplyClass.REFERRAL, ReplyClass.OTHER,
}
_POSITIVE = {ReplyClass.INTERESTED, ReplyClass.OBJECTION, ReplyClass.REFERRAL}


def poll_replies(reader: ImapReader | None = None, classifier=None,
                 conversation_agent=None, dry_run: bool = False) -> list[Reply]:
    """Poll every mailbox, match replies to our sends, save + classify them, and
    route each through the autonomous conversation handler.

    Mechanical cases: unsubscribe → suppress; out-of-office → pause + resume;
    auto-reply → ignore (sequence keeps running). Genuine replies stop the
    sequence and are handed to the ConversationAgent, which may auto-send a
    threaded response (subject to the guardrails in :func:`_route_reply`).
    Agents are created lazily. Returns the newly-recorded replies.
    """
    reader = reader or ImapReader()
    if classifier is None:
        from modules.pulse.inbox.agents import ReplyClassifierAgent
        classifier = ReplyClassifierAgent()

    known_ids = store.outbound_message_ids()
    known_senders = store.active_recipient_emails()

    # 1) Gather NEW inbound, matched to a recipient (by thread id OR sender), and
    # only if newer than our last outbound to them (ignores old thread history).
    grouped: dict[int, list[dict]] = {}
    baselines: dict[int, "datetime | None"] = {}
    for mailbox in store.list_mailboxes(active_only=True):
        credentials = accounts.get_credentials(mailbox.email)
        if credentials is None:
            continue
        try:
            hits = reader.fetch_replies(mailbox, credentials, known_ids=known_ids,
                                        known_senders=known_senders)
        except Exception as exc:  # noqa: BLE001 — network/auth issues shouldn't kill the loop
            logger.warning("IMAP poll failed for %s: %s", mailbox.email, exc)
            continue
        for hit in hits:
            if store.reply_uid_seen(hit["uid"]):
                continue
            rid = _match_recipient(hit)
            if rid is None:
                continue
            if rid not in baselines:
                baselines[rid] = _reply_baseline(rid)
            received = _parse_dt(hit.get("received_at"))
            base = baselines[rid]
            if received is None or (base is not None and received <= base):
                continue  # historical message in the thread, not a fresh reply
            grouped.setdefault(rid, []).append(hit)

    # 2) Per recipient: record all new messages (dedupe), converse once on newest.
    recorded: list[Reply] = []
    for rid, hits in grouped.items():
        hits.sort(key=lambda h: h.get("received_at") or "")
        for h in hits[:-1]:
            store.save_reply(Reply(recipient_id=rid, from_email=h.get("from_email", ""),
                                   subject=h.get("subject", ""), body=h.get("body", ""),
                                   received_at=h.get("received_at", utcnow_iso()),
                                   imap_uid=h["uid"], classification=ReplyClass.OTHER))
        newest = hits[-1]
        original = store.get_message_by_recipient_latest(rid)
        cls = classifier.run(newest.get("subject", ""), newest.get("body", ""),
                             original.subject if original else "")
        reply = Reply(
            recipient_id=rid, message_id=original.id if original else None,
            from_email=newest.get("from_email", ""), subject=newest.get("subject", ""),
            body=newest.get("body", ""), received_at=newest.get("received_at", utcnow_iso()),
            imap_uid=newest["uid"], classification=cls.classification,
            classification_confidence=cls.confidence, resume_at=_resume_iso(cls.resume_date))
        if store.save_reply(reply) is None:
            continue
        recorded.append(reply)
        if original and original.id is not None:
            store.update_message(original.id, status=MessageStatus.REPLIED)
        conversation_agent = _route_reply(rid, reply, conversation_agent, dry_run)
    logger.info("Poll complete: %d recipient(s) replied.", len(recorded))
    return recorded


def _match_recipient(hit: dict) -> int | None:
    """Match an inbound message to a recipient: first by our Message-ID in its
    In-Reply-To/References, else by sender address → a known recipient."""
    outbound = store.find_message_by_rfc_id(hit.get("in_reply_to", ""))
    if outbound is None:
        for ref in hit.get("references", []):
            outbound = store.find_message_by_rfc_id(ref)
            if outbound is not None:
                break
    if outbound is not None:
        return outbound.recipient_id
    rec = store.find_recipient_by_email(hit.get("from_email", ""))
    return rec.id if rec else None


def _parse_dt(value: str | None):
    from datetime import datetime, timezone
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _reply_baseline(recipient_id: int):
    """Cutoff after which inbound counts as a real reply: our latest outbound to
    them, else their enrollment time."""
    sent = [m.sent_at for m in store.messages_for_recipient(recipient_id) if m.sent_at]
    if sent:
        return _parse_dt(max(sent))
    rec = store.get_recipient(recipient_id)
    return _parse_dt(rec.enrolled_at) if rec else None


def _route_reply(recipient_id: int | None, reply: Reply, conversation_agent, dry_run: bool):
    """Decide what happens to a recipient after a reply, and (optionally)
    auto-respond. Returns the (possibly lazily-created) conversation agent."""
    if recipient_id is None:
        return conversation_agent
    cls = reply.classification

    if cls == ReplyClass.AUTO_REPLY:
        return conversation_agent  # ignore — keep the sequence running

    if cls == ReplyClass.OUT_OF_OFFICE:
        store.update_recipient(recipient_id, status=RecipientStatus.PAUSED,
                               next_send_at=reply.resume_at)
        store.log_event("reply_ooo", recipient_id=recipient_id, data={"resume_at": reply.resume_at})
        return conversation_agent

    if cls == ReplyClass.UNSUBSCRIBE:
        store.update_recipient(recipient_id, status=RecipientStatus.UNSUBSCRIBED,
                               replied_at=reply.received_at)
        store.log_event("reply_unsubscribe", recipient_id=recipient_id)
        return conversation_agent

    if cls not in _CONVERSATIONAL:
        return conversation_agent

    # Genuine human reply → the sequence stops; the conversation agent takes over.
    _credit_variant(reply.message_id, positive=cls in _POSITIVE)
    store.log_event(f"reply_{cls.value}", recipient_id=recipient_id,
                    data={"confidence": reply.classification_confidence})

    recipient = store.get_recipient(recipient_id)
    if recipient is None:
        return conversation_agent

    if conversation_agent is None:
        from modules.pulse.inbox.agents.conversation_agent import ConversationAgent
        conversation_agent = ConversationAgent()

    handle_conversation(recipient, reply, conversation_agent, dry_run=dry_run)
    return conversation_agent


def handle_conversation(recipient: Recipient, reply: Reply, agent, dry_run: bool = False) -> dict:
    """Run the conversation agent on a reply and act on its decision, enforcing
    the guardrails. Returns a small outcome dict for logging/UX.

    Guardrails (in code, not trusting the model):
      - hard cap on auto-replies per thread → escalate to a human
      - only auto-send when AUTO_REPLY_ENABLED and confidence >= floor
      - ESCALATE / low confidence / cap → set NEEDS_HUMAN and store the draft
        (unsent) so a person can review + send.
    """
    from modules.pulse.inbox.schemas import ConversationAction, RecipientStatus as RS

    recipient = store.get_recipient(recipient.id) or recipient

    # Scheduling a time, or already booked (reschedule/cancel) → booking flow.
    if recipient.status in (RS.MEETING, RS.BOOKED):
        return _scheduling_turn(recipient, reply, dry_run)

    mailbox = store.get_mailbox(recipient.mailbox_id) if recipient.mailbox_id else None
    sender_name = mailbox.from_name if mailbox else ""
    thread = _render_thread(recipient.id)
    decision = agent.run(recipient, thread, reply.body, sender_name=sender_name)

    sent_count = store.count_conversation_messages(recipient.id)
    cap_hit = sent_count >= config.MAX_AUTO_REPLIES
    confident = decision.confidence >= config.CONVERSATION_MIN_CONFIDENCE
    escalate = decision.action == ConversationAction.ESCALATE

    send_ok = (config.AUTO_REPLY_ENABLED and decision.should_send and confident
               and not escalate and not cap_hit)

    # Ready to talk → hand to the booking flow (real slots, not fabricated times).
    if send_ok and decision.action in (ConversationAction.ASK_AVAILABILITY,
                                       ConversationAction.SHARE_BOOKING):
        return _scheduling_turn(recipient, reply, dry_run)

    subject = decision.reply_subject or _reply_subject(reply.subject)

    if send_ok:
        msg = send_reply(recipient, subject, decision.reply_body, dry_run=dry_run)
        ok = msg is not None and msg.status == MessageStatus.SENT
        store.update_recipient(recipient.id,
                               status=decision.new_status if ok else RS.NEEDS_HUMAN,
                               replied_at=reply.received_at)
        outcome = {"action": decision.action.value, "sent": ok,
                   "status": (decision.new_status if ok else RS.NEEDS_HUMAN).value}
    else:
        # Assisted mode / escalation: store the draft unsent for human review.
        if decision.reply_body:
            store.create_message(Message(
                recipient_id=recipient.id, campaign_id=recipient.campaign_id,
                mailbox_id=recipient.mailbox_id, to_email=recipient.email,
                subject=subject, body=decision.reply_body, status=MessageStatus.QUEUED))
        reason = ("cap_reached" if cap_hit else "escalated" if escalate
                  else "low_confidence" if not confident else "auto_reply_off")
        store.update_recipient(recipient.id, status=RS.NEEDS_HUMAN, replied_at=reply.received_at)
        outcome = {"action": decision.action.value, "sent": False,
                   "status": RS.NEEDS_HUMAN.value, "reason": reason}

    store.log_event("conversation_handled", recipient_id=recipient.id,
                    campaign_id=recipient.campaign_id, data=outcome)
    logger.info("Conversation %s → %s", recipient.email, outcome)
    return outcome


def _scheduling_turn(recipient: Recipient, reply: Reply, dry_run: bool = False) -> dict:
    """Delegate a meeting reply to the calendar-aware scheduler: propose real
    open slots, negotiate, and book to a common time."""
    from modules.pulse.inbox.schemas import RecipientStatus as RS
    from modules.pulse.scheduling import handle_scheduling

    if not config.AUTO_REPLY_ENABLED or \
            store.count_conversation_messages(recipient.id) >= config.MAX_AUTO_REPLIES:
        reason = "auto_reply_off" if not config.AUTO_REPLY_ENABLED else "cap_reached"
        store.update_recipient(recipient.id, status=RS.NEEDS_HUMAN, replied_at=reply.received_at)
        return {"action": "schedule", "sent": False, "status": "needs_human", "reason": reason}

    ctx = dict(recipient.context or {})
    res = handle_scheduling(
        attendee_name=recipient.name, company=recipient.company, channel="email",
        known_email=recipient.email, thread=_render_thread(recipient.id),
        latest_reply=reply.body, existing_event_id=ctx.get("booked_event_id", ""),
        existing_slot_iso=ctx.get("booked_slot_iso"), dry_run=dry_run)
    subject = _reply_subject(reply.subject)
    msg = send_reply(recipient, subject, res["reply"], dry_run=dry_run)
    ok = msg is not None and msg.status == MessageStatus.SENT

    if res["booked"]:
        status = RS.BOOKED
        ctx["booked_event_id"] = res.get("event_id", "")           # for later reschedule/cancel
        ctx["booked_slot_iso"] = res["slot"].iso() if res.get("slot") else ""
        store.log_event("meeting_booked", recipient_id=recipient.id, campaign_id=recipient.campaign_id,
                        data={"slot": ctx["booked_slot_iso"], "join_url": res.get("join_url", ""),
                              "rescheduled": bool(res.get("event_id") and recipient.status == RS.BOOKED)})
    elif res.get("cancelled"):
        status = RS.NOT_INTERESTED
        ctx.pop("booked_event_id", None); ctx.pop("booked_slot_iso", None)
        store.log_event("meeting_cancelled", recipient_id=recipient.id, campaign_id=recipient.campaign_id)
    elif res["action"] == "decline":
        status = RS.NOT_INTERESTED
    else:
        status = RS.MEETING
    store.update_recipient(recipient.id, status=status if ok else RS.NEEDS_HUMAN,
                           replied_at=reply.received_at, context=ctx)
    outcome = {"action": f"schedule:{res['action']}", "sent": ok,
               "status": (status if ok else RS.NEEDS_HUMAN).value, "booked": res["booked"]}
    store.log_event("conversation_handled", recipient_id=recipient.id,
                    campaign_id=recipient.campaign_id, data=outcome)
    logger.info("Scheduling %s → %s", recipient.email, outcome)
    return outcome


def _render_thread(recipient_id: int) -> str:
    """Chronological transcript of the thread for the conversation agent."""
    items: list[tuple[str, str, str]] = []
    for m in store.messages_for_recipient(recipient_id):
        if m.status in (MessageStatus.SENT, MessageStatus.OPENED, MessageStatus.REPLIED):
            items.append((m.sent_at or m.queued_at, "US", f"{m.subject}\n{m.body}"))
    for r in store.replies_for_recipient(recipient_id):
        items.append((r.received_at, "THEM", f"{r.subject}\n{r.body}"))
    items.sort(key=lambda t: t[0] or "")
    return "\n\n".join(f"[{who}] {text}" for _, who, text in items) or "(no prior messages)"


def _reply_subject(their_subject: str) -> str:
    s = (their_subject or "").strip()
    return s if s.lower().startswith("re:") else f"Re: {s}"


def _credit_variant(message_id: int | None, positive: bool) -> None:
    if not positive or message_id is None:
        return
    msg = store.get_message(message_id)
    if msg and msg.variant_id is not None:
        store.update_variant_stats(msg.variant_id, reply_delta=1)


def _resume_iso(resume_date: str | None) -> str | None:
    if not resume_date:
        return None
    try:
        # Normalize a bare date to an ISO timestamp at midnight UTC.
        dt = datetime.fromisoformat(resume_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return None
