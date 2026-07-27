"""Scheduler — decides what to send, to whom, right now.

One ``tick()`` is the unit of work:

  1. Reactivate any out-of-office recipients whose resume time has arrived.
  2. If we're outside the business-hours send window, do nothing (wait).
  3. For every recipient whose next step is due: pick a mailbox with headroom
     (rotation + warmup + daily cap), compose the step (Writer for step 1,
     FollowUp for later steps), send, then schedule the following step.
  4. When a recipient finishes the last step with no reply, mark them completed.

Stop-on-reply is enforced upstream by the dispatcher (a reply flips the
recipient out of ``active``), so a replied/unsubscribed contact simply never
comes back as "due". Sending honours throttle jitter and per-mailbox caps.

Everything time-related goes through ``now_fn`` and sending through ``dry_run``,
so the whole engine runs in accelerated, network-free simulation for tests.
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from modules.common.logger import get_logger
from modules.pulse.inbox import config, store
from modules.pulse.inbox.delivery import accounts, dispatcher
from modules.pulse.inbox.schemas import (
    Campaign,
    EmailDraft,
    MessageStatus,
    Recipient,
    RecipientStatus,
    SequenceStep,
    Variant,
)

logger = get_logger("pulse.inbox.scheduler")


def default_variant_selector(step: SequenceStep) -> Variant | None:
    """P3 default: use the step's first active variant. The A/B bandit (P4)
    replaces this with a Thompson-sampling selector."""
    active = [v for v in step.variants if not v.is_paused]
    pool = active or step.variants
    return pool[0] if pool else None


class Scheduler:
    """Drives a single campaign's sequence forward, one tick at a time."""

    def __init__(
        self,
        campaign_id: int,
        *,
        dry_run: bool = False,
        throttle: bool = True,
        respect_window: bool = True,
        now_fn=None,
        variant_selector=None,
        composer=None,
        recipient_filter=None,
    ) -> None:
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
        # Optional veto: called with each due Recipient; returning False holds
        # them for this tick. Used by the CRM's manual sending mode to keep a
        # first touch from going out before a human approves it.
        self.recipient_filter = recipient_filter

        # Writer/FollowUp agents are created lazily (only if the default composer
        # is actually used) so pure-logic simulations need no API key.
        self._writer = None
        self._followup = None
        # Display name of the mailbox chosen for the current send, so the default
        # composer signs the email as the real sender. Set in tick() before compose.
        self._sender_name = ""

    # -- composition --------------------------------------------------------
    def _default_composer(self, recipient: Recipient, step: SequenceStep, prior: list) -> EmailDraft:
        variant = self.variant_selector(step)
        angle = variant.angle if variant else step.angle
        if step.step_order == 1 or not prior:
            if self._writer is None:
                from modules.pulse.inbox.compose import WriterAgent
                self._writer = WriterAgent()
            return self._writer.run(recipient, step, angle=angle, sender_name=self._sender_name)
        if self._followup is None:
            from modules.pulse.inbox.agents.follow_up_agent import FollowUpAgent
            self._followup = FollowUpAgent()
        return self._followup.run(recipient, step, prior, angle=angle, sender_name=self._sender_name)

    # -- time / window ------------------------------------------------------
    def _now(self) -> datetime:
        return self._now_fn()

    def in_send_window(self, now: datetime) -> bool:
        """True if ``now`` is within the configured weekday + business-hours window."""
        try:
            tz = ZoneInfo(config.SEND_TIMEZONE)
        except (ZoneInfoNotFoundError, ValueError):
            tz = timezone.utc
        local = now.astimezone(tz)
        if local.weekday() not in config.SEND_WEEKDAYS:
            return False
        return config.SEND_WINDOW_START_HOUR <= local.hour < config.SEND_WINDOW_END_HOUR

    # -- the tick -----------------------------------------------------------
    def tick(self, max_sends: int | None = None) -> dict:
        """Process everything currently due. Returns a per-tick action report."""
        now = self._now()
        now_iso = now.isoformat()
        report = {
            "reactivated": store.reactivate_due_paused(now_iso, self.campaign.id),
            "considered": 0, "sent": 0, "completed": 0,
            "skipped_window": 0, "skipped_capacity": 0, "skipped_hold": 0, "failed": 0,
        }

        if self.respect_window and not self.in_send_window(now):
            report["skipped_window"] = 1
            logger.info("Outside send window (%s) — holding.", now_iso)
            return report

        due = store.due_recipients(now_iso, self.campaign.id)
        for rec in due:
            report["considered"] += 1
            if max_sends is not None and report["sent"] >= max_sends:
                break

            if self.recipient_filter is not None and not self.recipient_filter(rec):
                report["skipped_hold"] += 1
                continue

            next_order = rec.current_step + 1
            step = self.steps_by_order.get(next_order)
            if step is None:                      # no more steps → done, no reply
                store.update_recipient(rec.id, status=RecipientStatus.COMPLETED)
                report["completed"] += 1
                continue

            mailbox = accounts.pick_mailbox(rec.mailbox_id)
            if mailbox is None:                   # whole pool is tapped for today
                report["skipped_capacity"] += 1
                continue

            variant = self.variant_selector(step)
            if variant is None:
                report["failed"] += 1
                continue

            prior = store.messages_for_recipient(rec.id)
            self._sender_name = mailbox.from_name or ""
            try:
                draft = self.composer(rec, step, prior)
            except Exception as exc:              # noqa: BLE001 — one bad compose shouldn't halt the tick
                logger.warning("Compose failed for %s: %s", rec.email, exc)
                report["failed"] += 1
                continue

            msg = dispatcher.send_message(rec, step, variant, draft, mailbox, dry_run=self.dry_run)
            if msg.status == MessageStatus.SENT:
                report["sent"] += 1
                self._schedule_next(rec, step, now)
                if self.throttle:
                    time.sleep(random.uniform(config.MIN_SEND_DELAY_SECONDS,
                                              config.MAX_SEND_DELAY_SECONDS))
            else:
                report["failed"] += 1

        logger.info("Tick @ %s: %s", now_iso, report)
        return report

    def _schedule_next(self, rec: Recipient, step_sent: SequenceStep, now: datetime) -> None:
        """Queue the following step, or mark the recipient completed."""
        nxt = self.steps_by_order.get(step_sent.step_order + 1)
        if nxt is None:
            store.update_recipient(rec.id, status=RecipientStatus.COMPLETED)
        else:
            due_at = now + timedelta(days=nxt.wait_days)
            store.update_recipient(rec.id, next_send_at=due_at.isoformat())
