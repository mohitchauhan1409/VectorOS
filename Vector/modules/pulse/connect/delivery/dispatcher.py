"""Dispatcher — coordination over the LinkedIn provider + DB state.

Keeps the provider dumb; everything that mutates campaign/prospect state lives
here:

  send_step(...)        send an invite or a message → record + advance state
  sync_acceptances()    detect accepted invites (gate) + expire stale ones
  poll_replies()        pull inbound DMs → match → classify → converse

The scheduler (C3) calls send_step; the autopilot (C4) calls sync_acceptances
and poll_replies. ``dry_run`` exercises the whole flow without hitting the
provider (used with the mock in tests and for safe dry demos).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from modules.common.logger import get_logger
from modules.pulse.connect import config, store
from modules.pulse.connect.providers import get_provider
from modules.pulse.connect.schemas import (
    ConnectDraft,
    ConnectMessage,
    ConversationAction,
    LinkedInAccount,
    MessageKind,
    MessageStatus,
    Prospect,
    ProspectStatus,
    Reply,
    ReplyClass,
    SequenceStep,
    StepKind,
    Variant,
    utcnow_iso,
)

logger = get_logger("pulse.connect.dispatcher")

_SLUG_RE = re.compile(r"linkedin\.com/in/([^/?#]+)", re.IGNORECASE)
_CONVERSATIONAL = {ReplyClass.INTERESTED, ReplyClass.NOT_INTERESTED, ReplyClass.OBJECTION,
                   ReplyClass.REFERRAL, ReplyClass.OTHER}
_POSITIVE = {ReplyClass.INTERESTED, ReplyClass.OBJECTION, ReplyClass.REFERRAL}


def _slug(url: str) -> str:
    m = _SLUG_RE.search(url or "")
    return (m.group(1) if m else "").rstrip("/").lower()


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO timestamp (handles trailing 'Z'); None if unparseable."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _reply_baseline(prospect: Prospect) -> datetime | None:
    """The cutoff after which an inbound message counts as a real reply: our most
    recent outbound to this prospect, else when they were enrolled."""
    sent = [m.sent_at for m in store.messages_for_prospect(prospect.id) if m.sent_at]
    return _parse_dt(max(sent)) if sent else _parse_dt(prospect.enrolled_at)


def _account_for(prospect: Prospect) -> LinkedInAccount | None:
    if prospect.account_id:
        acct = store.get_account(prospect.account_id)
        if acct:
            return acct
    accts = store.list_accounts(active_only=True)
    return accts[0] if accts else None


# ---------------------------------------------------------------------------
# Sending a sequence step (invite or message)
# ---------------------------------------------------------------------------
def send_step(prospect: Prospect, step: SequenceStep, variant: Variant, draft: ConnectDraft,
              account: LinkedInAccount, dry_run: bool = False) -> ConnectMessage:
    """Send one step's action via the provider and record the outcome."""
    kind = MessageKind.INVITE if step.kind == StepKind.INVITE else MessageKind.MESSAGE
    msg = store.create_message(ConnectMessage(
        prospect_id=prospect.id, campaign_id=prospect.campaign_id, step_id=step.id,
        variant_id=variant.id, account_id=account.id, kind=kind, body=draft.body,
        status=MessageStatus.QUEUED))

    if dry_run:
        result_ok, ref, err = True, "dry-run", ""
    else:
        provider = get_provider()
        res = (provider.send_invite(account, prospect.linkedin_url, draft.body)
               if kind == MessageKind.INVITE
               else provider.send_message(account, prospect.linkedin_url, draft.body))
        result_ok, ref, err = res.ok, res.provider_ref, res.error

    if not result_ok:
        store.update_message(msg.id, status=MessageStatus.FAILED, error=err)
        msg.status, msg.error = MessageStatus.FAILED, err
        store.log_event("send_failed", prospect_id=prospect.id, campaign_id=prospect.campaign_id,
                        data={"kind": kind.value, "error": err})
        logger.warning("Send failed for %s: %s", prospect.name, err)
        return msg

    now = utcnow_iso()
    store.update_message(msg.id, status=MessageStatus.SENT, sent_at=now, provider_ref=ref)
    msg.status, msg.sent_at = MessageStatus.SENT, now

    fields = {"current_step": step.step_order, "last_action_at": now, "account_id": account.id}
    if kind == MessageKind.INVITE:
        fields["status"] = ProspectStatus.INVITE_SENT
        fields["invited_at"] = now
    store.update_prospect(prospect.id, **fields)
    if variant.id is not None:
        store.update_variant_stats(variant.id, sent_delta=1)
    if account.id is not None and account.warmup_started_on is None:
        store.mark_account_warmup_started(account.id)
    store.log_event("sent", prospect_id=prospect.id, campaign_id=prospect.campaign_id,
                    data={"kind": kind.value, "step": step.step_order})
    return msg


# ---------------------------------------------------------------------------
# Acceptance gate
# ---------------------------------------------------------------------------
def sync_acceptances(dry_run: bool = False) -> dict:
    """Detect accepted invites (invite_sent → accepted, ready to message) and
    expire invites older than the window (invite_sent → invite_expired)."""
    report = {"accepted": 0, "expired": 0}
    pending = store.prospects_by_status(ProspectStatus.INVITE_SENT)
    if not pending:
        return report

    now = datetime.now(timezone.utc)
    expiry_cutoff = now - timedelta(days=config.INVITE_EXPIRY_DAYS)

    # Group by account for a batched provider read.
    by_account: dict[int, list[Prospect]] = {}
    for p in pending:
        by_account.setdefault(p.account_id or 0, []).append(p)

    provider = get_provider()
    for account_id, group in by_account.items():
        account = store.get_account(account_id) if account_id else _account_for(group[0])
        urls = [p.linkedin_url for p in group]
        accepted_urls: set[str] = set()
        if not dry_run and account is not None:
            try:
                accepted_urls = provider.fetch_accepted(account, urls)
            except Exception as exc:  # noqa: BLE001
                logger.warning("fetch_accepted failed: %s", exc)

        for p in group:
            if p.linkedin_url in accepted_urls:
                # next_action_at = NULL → "due now": the intro message fires on
                # the next scheduler tick (in the send window).
                store.update_prospect(p.id, status=ProspectStatus.ACCEPTED,
                                      accepted_at=utcnow_iso(), next_action_at=None)
                store.log_event("invite_accepted", prospect_id=p.id, campaign_id=p.campaign_id)
                report["accepted"] += 1
            elif p.invited_at and datetime.fromisoformat(p.invited_at) < expiry_cutoff:
                store.update_prospect(p.id, status=ProspectStatus.INVITE_EXPIRED)
                store.log_event("invite_expired", prospect_id=p.id, campaign_id=p.campaign_id)
                report["expired"] += 1
    return report


# ---------------------------------------------------------------------------
# Replies
# ---------------------------------------------------------------------------
def is_connected(account: LinkedInAccount, linkedin_url: str, dry_run: bool = False) -> bool:
    """True if the profile is already a 1st-degree connection (skip the invite)."""
    if dry_run:
        return False
    try:
        return linkedin_url in get_provider().fetch_accepted(account, [linkedin_url])
    except Exception as exc:  # noqa: BLE001
        logger.warning("is_connected check failed for %s: %s", linkedin_url, exc)
        return False


def poll_replies(classifier=None, conversation_agent=None, dry_run: bool = False) -> list[Reply]:
    """Pull inbound DMs across accounts, match to prospects, and respond ONCE
    per prospect per poll (to the newest message) — never a reply per inbound
    message, so a prospect who sent several messages gets a single response."""
    if classifier is None:
        from modules.pulse.connect.agents import ReplyClassifierAgent
        classifier = ReplyClassifierAgent()

    since = (datetime.now(timezone.utc) - timedelta(days=config.REPLY_LOOKBACK_DAYS)).isoformat()
    provider = get_provider()

    # 1) Gather NEW inbound messages, matched to prospects, grouped by prospect.
    # A message only counts as a reply if it arrived AFTER our most recent
    # outbound to that prospect — otherwise old chat history (from before this
    # sequence started) would be mistaken for fresh replies.
    grouped: dict[int, list] = {}
    prospects: dict[int, Prospect] = {}
    baselines: dict[int, datetime | None] = {}
    for account in store.list_accounts(active_only=True):
        try:
            inbound = provider.fetch_replies(account, since)
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_replies failed for account %s: %s", account.id, exc)
            continue
        for msg in inbound:
            if store.reply_id_seen(msg.provider_id):
                continue
            prospect = (store.find_prospect_by_url(msg.linkedin_url)
                        or store.find_prospect_by_slug(_slug(msg.linkedin_url)))
            if prospect is None:
                continue
            if prospect.id not in baselines:
                baselines[prospect.id] = _reply_baseline(prospect)
            received = _parse_dt(msg.received_at)
            base = baselines[prospect.id]
            if received is None or (base is not None and received <= base):
                continue  # historical message, not a fresh reply
            grouped.setdefault(prospect.id, []).append(msg)
            prospects[prospect.id] = prospect

    # 2) Per prospect: record all new messages (dedupe), converse once on the newest.
    recorded: list[Reply] = []
    for pid, msgs in grouped.items():
        prospect = prospects[pid]
        msgs.sort(key=lambda m: m.received_at or "")
        newest = msgs[-1]
        # Record older messages for history without triggering a response.
        for m in msgs[:-1]:
            store.save_reply(Reply(prospect_id=pid, body=m.text, received_at=m.received_at,
                                   provider_id=m.provider_id, classification=ReplyClass.OTHER))
        cls = classifier.run("LinkedIn reply", newest.text, "")
        reply = Reply(prospect_id=pid, body=newest.text, received_at=newest.received_at,
                      provider_id=newest.provider_id, classification=cls.classification,
                      classification_confidence=cls.confidence)
        if store.save_reply(reply) is None:
            continue
        recorded.append(reply)
        conversation_agent = _route_reply(prospect, reply, conversation_agent, dry_run)

    logger.info("Poll complete: %d prospect(s) replied.", len(recorded))
    return recorded


def _route_reply(prospect: Prospect, reply: Reply, conversation_agent, dry_run):
    cls = reply.classification
    if cls in (ReplyClass.AUTO_REPLY, ReplyClass.OUT_OF_OFFICE):
        return conversation_agent
    if cls == ReplyClass.UNSUBSCRIBE:
        store.update_prospect(prospect.id, status=ProspectStatus.UNSUBSCRIBED, replied_at=reply.received_at)
        store.log_event("reply_unsubscribe", prospect_id=prospect.id)
        return conversation_agent
    if cls not in _CONVERSATIONAL:
        return conversation_agent

    _credit_variant(prospect.id, positive=cls in _POSITIVE)
    store.log_event(f"reply_{cls.value}", prospect_id=prospect.id,
                    data={"confidence": reply.classification_confidence})
    if conversation_agent is None:
        from modules.pulse.connect.agents import ConversationAgent
        conversation_agent = ConversationAgent()
    handle_conversation(prospect, reply, conversation_agent, dry_run=dry_run)
    return conversation_agent


def handle_conversation(prospect: Prospect, reply: Reply, agent, dry_run: bool = False) -> dict:
    """Run the conversation agent and act on it, enforcing the guardrails.

    Meeting-intent replies (and everything once a prospect is in MEETING state)
    are handed to the calendar-aware scheduling flow, which proposes real open
    slots and books to a common time."""
    prospect = store.get_prospect(prospect.id) or prospect

    # Negotiating a time, or already booked (reschedule/cancel) → scheduling flow.
    if prospect.status in (ProspectStatus.MEETING, ProspectStatus.BOOKED):
        return _scheduling_turn(prospect, reply, dry_run)

    account = _account_for(prospect)
    sender_name = account.name if account else ""
    thread = _render_thread(prospect.id)
    decision = agent.run(prospect, thread, reply.body, sender_name=sender_name)

    cap_hit = store.count_conversation_messages(prospect.id) >= config.MAX_AUTO_REPLIES
    confident = decision.confidence >= config.CONVERSATION_MIN_CONFIDENCE
    escalate = decision.action == ConversationAction.ESCALATE
    send_ok = (config.AUTO_REPLY_ENABLED and decision.should_send and confident
               and not escalate and not cap_hit)

    # They're ready to talk → switch into the booking flow (real slots, not fabricated).
    if send_ok and decision.action in (ConversationAction.ASK_AVAILABILITY,
                                       ConversationAction.SHARE_BOOKING):
        return _scheduling_turn(prospect, reply, dry_run)

    if send_ok:
        msg = send_conversation_reply(prospect, decision.reply_body, account, dry_run=dry_run)
        ok = msg is not None and msg.status == MessageStatus.SENT
        new_status = _to_prospect_status(decision.new_status) if ok else ProspectStatus.NEEDS_HUMAN
        store.update_prospect(prospect.id, status=new_status, replied_at=reply.received_at)
        outcome = {"action": decision.action.value, "sent": ok, "status": new_status.value}
    else:
        reason = ("cap_reached" if cap_hit else "escalated" if escalate
                  else "low_confidence" if not confident else "auto_reply_off")
        store.update_prospect(prospect.id, status=ProspectStatus.NEEDS_HUMAN, replied_at=reply.received_at)
        outcome = {"action": decision.action.value, "sent": False,
                   "status": ProspectStatus.NEEDS_HUMAN.value, "reason": reason,
                   "draft": decision.reply_body}
    store.log_event("conversation_handled", prospect_id=prospect.id, campaign_id=prospect.campaign_id,
                    data={k: v for k, v in outcome.items() if k != "draft"})
    logger.info("Conversation %s → %s", prospect.name, {k: outcome[k] for k in ("action", "sent", "status")})
    return outcome


def _scheduling_turn(prospect: Prospect, reply: Reply, dry_run: bool = False) -> dict:
    """Delegate a meeting reply to the calendar-aware scheduler: propose real
    slots, negotiate, and book to a common time."""
    from modules.pulse.scheduling import handle_scheduling

    if not config.AUTO_REPLY_ENABLED or \
            store.count_conversation_messages(prospect.id) >= config.MAX_AUTO_REPLIES:
        reason = "auto_reply_off" if not config.AUTO_REPLY_ENABLED else "cap_reached"
        store.update_prospect(prospect.id, status=ProspectStatus.NEEDS_HUMAN, replied_at=reply.received_at)
        return {"action": "schedule", "sent": False, "status": "needs_human", "reason": reason}

    account = _account_for(prospect)
    ctx = dict(prospect.context or {})
    res = handle_scheduling(
        attendee_name=prospect.name, company=prospect.company, channel="linkedin",
        known_email=prospect.email, pending_slot_iso=ctx.get("pending_slot_iso"),
        existing_event_id=ctx.get("booked_event_id", ""), existing_slot_iso=ctx.get("booked_slot_iso"),
        thread=_render_thread(prospect.id), latest_reply=reply.body, dry_run=dry_run)
    msg = send_conversation_reply(prospect, res["reply"], account, dry_run=dry_run)
    ok = msg is not None and msg.status == MessageStatus.SENT

    # Persist / clear held slot + booking id between turns.
    ctx["pending_slot_iso"] = res.get("pending_slot_iso")
    if res["booked"]:
        status = ProspectStatus.BOOKED
        ctx["booked_event_id"] = res.get("event_id", "")
        ctx["booked_slot_iso"] = res["slot"].iso() if res.get("slot") else ""
        store.log_event("meeting_booked", prospect_id=prospect.id, campaign_id=prospect.campaign_id,
                        data={"slot": ctx["booked_slot_iso"], "join_url": res.get("join_url", ""),
                              "invite_email": res.get("attendee_email", ""),
                              "rescheduled": bool(res.get("event_id") and prospect.status == ProspectStatus.BOOKED)})
    elif res.get("cancelled"):
        status = ProspectStatus.NOT_INTERESTED
        ctx.pop("booked_event_id", None); ctx.pop("booked_slot_iso", None)
        store.log_event("meeting_cancelled", prospect_id=prospect.id, campaign_id=prospect.campaign_id)
    elif res["action"] == "decline":
        status = ProspectStatus.NOT_INTERESTED
    else:
        status = ProspectStatus.MEETING
    store.update_prospect(prospect.id, status=status if ok else ProspectStatus.NEEDS_HUMAN,
                          replied_at=reply.received_at, context=ctx)
    outcome = {"action": f"schedule:{res['action']}", "sent": ok,
               "status": (status if ok else ProspectStatus.NEEDS_HUMAN).value, "booked": res["booked"]}
    store.log_event("conversation_handled", prospect_id=prospect.id, campaign_id=prospect.campaign_id, data=outcome)
    logger.info("Scheduling %s → %s", prospect.name, outcome)
    return outcome


def send_conversation_reply(prospect: Prospect, text: str, account: LinkedInAccount | None,
                            dry_run: bool = False) -> ConnectMessage | None:
    account = account or _account_for(prospect)
    if account is None:
        logger.warning("No account to reply to %s", prospect.name)
        return None
    msg = store.create_message(ConnectMessage(
        prospect_id=prospect.id, campaign_id=prospect.campaign_id, account_id=account.id,
        kind=MessageKind.MESSAGE, body=text, status=MessageStatus.QUEUED))
    if dry_run:
        ok, ref, err = True, "dry-run", ""
    else:
        res = get_provider().send_message(account, prospect.linkedin_url, text)
        ok, ref, err = res.ok, res.provider_ref, res.error
    if ok:
        store.update_message(msg.id, status=MessageStatus.SENT, sent_at=utcnow_iso(), provider_ref=ref)
        msg.status = MessageStatus.SENT
        store.log_event("auto_reply_sent", prospect_id=prospect.id)
    else:
        store.update_message(msg.id, status=MessageStatus.FAILED, error=err)
        msg.status = MessageStatus.FAILED
    return msg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _credit_variant(prospect_id: int, positive: bool) -> None:
    if not positive:
        return
    msgs = [m for m in store.messages_for_prospect(prospect_id) if m.variant_id is not None]
    if msgs:
        store.update_variant_stats(msgs[-1].variant_id, reply_delta=1)


def _render_thread(prospect_id: int) -> str:
    items: list[tuple[str, str, str]] = []
    for m in store.messages_for_prospect(prospect_id):
        if m.status in (MessageStatus.SENT, MessageStatus.REPLIED):
            label = "US (invite note)" if m.kind == MessageKind.INVITE else "US"
            items.append((m.sent_at or m.queued_at, label, m.body))
    for r in store.replies_for_prospect(prospect_id):
        items.append((r.received_at, "THEM", r.body))
    items.sort(key=lambda t: t[0] or "")
    return "\n\n".join(f"[{who}] {text}" for _, who, text in items) or "(no prior messages)"


def _to_prospect_status(rec_status) -> ProspectStatus:
    """Map the conversation agent's status (shared enum) onto a ProspectStatus."""
    try:
        return ProspectStatus(rec_status.value)
    except (ValueError, AttributeError):
        return ProspectStatus.IN_CONVERSATION
