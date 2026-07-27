"""Scheduler — decides which LinkedIn action to take next, for whom, now.

The state machine, one ``tick()`` at a time:
  * PENDING      → send the connection invite (if invite capacity allows)
  * INVITE_SENT  → wait (the autopilot's acceptance sync flips these to ACCEPTED)
  * ACCEPTED     → send the next message step (intro, nudge, break-up); when the
                   last message is sent with no reply → COMPLETED
A reply moves the prospect out of the sequence (the conversation agent drives).

Safety playbook enforced here regardless of provider: weekly + daily invite
caps, warmup ramp, message cap, working-hours window, human-like jitter,
account rotation. ``dry_run`` + ``now_fn`` make it fully simulatable.
"""

from __future__ import annotations

import random
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from modules.common.logger import get_logger
from modules.pulse.connect import config, store
from modules.pulse.connect.delivery import dispatcher
from modules.pulse.connect.schemas import (
    Campaign,
    ConnectDraft,
    LinkedInAccount,
    MessageStatus,
    Prospect,
    ProspectStatus,
    SequenceStep,
    StepKind,
    Variant,
)

logger = get_logger("pulse.connect.scheduler")


def default_variant_selector(step: SequenceStep) -> Variant | None:
    pool = [v for v in step.variants if not v.is_paused] or step.variants
    return pool[0] if pool else None


def _days_since(iso_date: str | None) -> int:
    if not iso_date:
        return 0
    try:
        return max(0, (date.today() - date.fromisoformat(iso_date)).days)
    except ValueError:
        return 0


class Scheduler:
    def __init__(self, campaign_id: int, *, dry_run: bool = False, throttle: bool = True,
                 respect_window: bool = True, now_fn=None, variant_selector=None, composer=None,
                 prospect_filter=None) -> None:
        campaign = store.get_campaign(campaign_id)
        if campaign is None:
            raise ValueError(f"No campaign #{campaign_id}")
        self.campaign: Campaign = campaign
        self.steps_by_order = {s.step_order: s for s in campaign.steps}
        self.dry_run = dry_run
        self.throttle = throttle and not dry_run
        self.respect_window = respect_window
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.variant_selector = variant_selector or default_variant_selector
        self.composer = composer or self._default_composer
        # Optional veto: returning False holds this prospect for the tick. Used
        # by the CRM's manual sending mode to gate the connection invite.
        self.prospect_filter = prospect_filter
        self._note_agent = None
        self._msg_agent = None

    # -- composition --------------------------------------------------------
    def _default_composer(self, prospect: Prospect, step: SequenceStep, prior: list) -> ConnectDraft:
        variant = self.variant_selector(step)
        angle = variant.angle if variant else step.angle
        account = dispatcher._account_for(prospect)
        sender = account.name if account else ""
        if step.kind == StepKind.INVITE:
            if self._note_agent is None:
                from modules.pulse.connect.compose import NoteWriterAgent
                self._note_agent = NoteWriterAgent()
            return self._note_agent.run(prospect, step, angle=angle, sender_name=sender)
        if self._msg_agent is None:
            from modules.pulse.connect.compose import MessageWriterAgent
            self._msg_agent = MessageWriterAgent()
        return self._msg_agent.run(prospect, step, prior=prior, angle=angle, sender_name=sender)

    # -- time / window ------------------------------------------------------
    def _now(self) -> datetime:
        return self._now_fn()

    def in_send_window(self, now: datetime) -> bool:
        try:
            tz = ZoneInfo(config.SEND_TIMEZONE)
        except (ZoneInfoNotFoundError, ValueError):
            tz = timezone.utc
        local = now.astimezone(tz)
        if local.weekday() not in config.SEND_WEEKDAYS:
            return False
        return config.SEND_WINDOW_START_HOUR <= local.hour < config.SEND_WINDOW_END_HOUR

    # -- capacity (safety playbook) ----------------------------------------
    def daily_invite_allowance(self, account: LinkedInAccount) -> int:
        if not config.WARMUP_ENABLED:
            return account.daily_invite_cap
        if account.warmup_started_on is None:
            return min(config.WARMUP_START, account.daily_invite_cap)
        ramped = config.WARMUP_START + config.WARMUP_INCREMENT * _days_since(account.warmup_started_on)
        return min(ramped, account.daily_invite_cap)

    def invite_capacity(self, account: LinkedInAccount) -> int:
        if account.id is None:
            return 0
        daily_left = self.daily_invite_allowance(account) - store.invites_today(account.id)
        weekly_left = account.weekly_invite_cap - store.invites_this_week(account.id)
        return max(0, min(daily_left, weekly_left))

    def message_capacity(self, account: LinkedInAccount) -> int:
        if account.id is None:
            return 0
        return max(0, account.daily_message_cap - store.messages_today(account.id))

    def _pick_account(self, prospect: Prospect, for_invite: bool) -> LinkedInAccount | None:
        if prospect.account_id:
            acct = store.get_account(prospect.account_id)
            if acct:
                return acct
        accounts = store.list_accounts(active_only=True)
        cap = self.invite_capacity if for_invite else self.message_capacity
        with_room = sorted(((cap(a), a) for a in accounts), key=lambda t: t[0], reverse=True)
        return with_room[0][1] if with_room and with_room[0][0] > 0 else (accounts[0] if accounts else None)

    # -- the tick -----------------------------------------------------------
    def tick(self, max_actions: int | None = None) -> dict:
        now = self._now()
        now_iso = now.isoformat()
        report = {"considered": 0, "invited": 0, "messaged": 0, "completed": 0,
                  "already_connected": 0, "skipped_reply": 0, "skipped_hold": 0,
                  "skipped_window": 0, "skipped_capacity": 0, "failed": 0}

        if self.respect_window and not self.in_send_window(now):
            report["skipped_window"] = 1
            return report

        due = store.due_prospects(now_iso, ("pending", "accepted"), self.campaign.id)
        for p in due:
            report["considered"] += 1
            if max_actions is not None and (report["invited"] + report["messaged"]) >= max_actions:
                break

            if self.prospect_filter is not None and not self.prospect_filter(p):
                report["skipped_hold"] += 1
                continue

            step = self.steps_by_order.get(p.current_step + 1)
            if step is None:
                store.update_prospect(p.id, status=ProspectStatus.COMPLETED)
                report["completed"] += 1
                continue

            is_invite = step.kind == StepKind.INVITE
            account = self._pick_account(p, for_invite=is_invite)
            if account is None:
                report["skipped_capacity"] += 1
                continue

            # Already a 1st-degree connection → skip the invite, jump to messaging.
            if is_invite and dispatcher.is_connected(account, p.linkedin_url, dry_run=self.dry_run):
                store.update_prospect(p.id, status=ProspectStatus.ACCEPTED, current_step=step.step_order,
                                      accepted_at=now.isoformat(), account_id=account.id, next_action_at=None)
                store.log_event("already_connected", prospect_id=p.id, campaign_id=self.campaign.id)
                report["already_connected"] += 1
                continue

            cap = self.invite_capacity(account) if is_invite else self.message_capacity(account)
            if cap <= 0:
                report["skipped_capacity"] += 1
                continue

            variant = self.variant_selector(step)
            if variant is None:
                report["failed"] += 1
                continue
            prior = store.messages_for_prospect(p.id)

            # Don't send the scripted intro if they already replied — let the
            # conversation agent handle their message instead.
            first_message = not is_invite and not any(m.kind.value == "message" for m in prior)
            if first_message and store.replies_for_prospect(p.id):
                report["skipped_reply"] += 1
                continue
            try:
                draft = self.composer(p, step, prior)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Compose failed for %s: %s", p.name, exc)
                report["failed"] += 1
                continue

            msg = dispatcher.send_step(p, step, variant, draft, account, dry_run=self.dry_run)
            if msg.status != MessageStatus.SENT:
                report["failed"] += 1
                continue

            if is_invite:
                report["invited"] += 1
                # Gate: dispatcher set status=invite_sent; stop scheduling until accepted.
                store.update_prospect(p.id, next_action_at=None)
            else:
                report["messaged"] += 1
                self._schedule_next_message(p, step, now)
            if self.throttle:
                time.sleep(random.uniform(config.MIN_ACTION_DELAY_SECONDS, config.MAX_ACTION_DELAY_SECONDS))

        logger.info("Tick @ %s: %s", now_iso, report)
        return report

    def _schedule_next_message(self, prospect: Prospect, step_sent: SequenceStep, now: datetime) -> None:
        nxt = self.steps_by_order.get(step_sent.step_order + 1)
        if nxt is None:
            store.update_prospect(prospect.id, status=ProspectStatus.COMPLETED)
        else:
            due_at = now + timedelta(days=nxt.wait_days)
            store.update_prospect(prospect.id, next_action_at=due_at.isoformat())
