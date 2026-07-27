"""Autopilot — runs Connect hands-off (LinkedIn).

Each cycle (hourly by default):
  1. intake   — enroll freshly-generated Scout leads (with LinkedIn URLs)
  2. accept   — detect accepted invites (gate) + expire stale ones
  3. poll     — pull replies, classify, and let the ConversationAgent respond
  4. send     — advance every active campaign (invites + messages, bandit-picked,
                caps/warmup/window enforced)
  5. promote  — lock in any A/B winner that's now significant

Run as a daemon (``--interval``) or one-shot for cron (``--once``). ``--dry``
runs the full loop without hitting the provider.
"""

from __future__ import annotations

import sys
import time

from modules.common.logger import get_logger
from modules.pulse.connect import config, enrollment, store
from modules.pulse.connect.analytics import ab_testing
from modules.pulse.connect.schemas import CampaignStatus

logger = get_logger("pulse.connect.autopilot")


class Autopilot:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._classifier = None
        self._conversation = None

    def cycle(self) -> dict:
        report = {"intake": 0, "accepted": 0, "expired": 0, "replies": 0,
                  "invited": 0, "messaged": 0, "completed": 0, "promoted": 0, "errors": []}
        self._safe(report, "intake", self._intake)
        self._safe(report, "accept", self._accept)
        self._safe(report, "poll", self._poll)
        self._safe(report, "send", self._send)
        self._safe(report, "promote", self._promote)
        logger.info("Cycle: %s", {k: v for k, v in report.items() if k != "errors"})
        return report

    def _safe(self, report, phase, fn) -> None:
        try:
            fn(report)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Phase %s failed: %s", phase, exc)
            report["errors"].append(f"{phase}: {exc}")

    def _intake(self, report) -> None:
        for campaign in store.list_campaigns(status=CampaignStatus.ACTIVE):
            report["intake"] += enrollment.enroll_campaign(campaign)["enrolled"]

    def _accept(self, report) -> None:
        from modules.pulse.connect.delivery import dispatcher
        res = dispatcher.sync_acceptances(dry_run=self.dry_run)
        report["accepted"] += res["accepted"]
        report["expired"] += res["expired"]

    def _poll(self, report) -> None:
        from modules.pulse.connect.delivery import dispatcher
        if self._classifier is None:
            from modules.pulse.connect.agents import ReplyClassifierAgent
            self._classifier = ReplyClassifierAgent()
        if self._conversation is None:
            from modules.pulse.connect.agents import ConversationAgent
            self._conversation = ConversationAgent()
        replies = dispatcher.poll_replies(classifier=self._classifier,
                                          conversation_agent=self._conversation, dry_run=self.dry_run)
        report["replies"] += len(replies)

    def _send(self, report) -> None:
        from modules.pulse.connect.sequences import Scheduler
        for campaign in store.list_campaigns(status=CampaignStatus.ACTIVE):
            sched = Scheduler(campaign.id, dry_run=self.dry_run, throttle=not self.dry_run,
                              respect_window=True, variant_selector=ab_testing.bandit_selector)
            r = sched.tick()
            report["invited"] += r["invited"]
            report["messaged"] += r["messaged"]
            report["completed"] += r["completed"]

    def _promote(self, report) -> None:
        for campaign in store.list_campaigns(status=CampaignStatus.ACTIVE):
            for step in campaign.steps:
                if ab_testing.evaluate_and_promote(step.id) is not None:
                    report["promoted"] += 1

    def run(self, interval_seconds: int = 3600, max_cycles: int | None = None) -> None:
        n = 0
        while True:
            self.cycle()
            n += 1
            if max_cycles is not None and n >= max_cycles:
                return
            time.sleep(interval_seconds)


def _opt_int(name: str, default: int) -> int:
    if name in sys.argv:
        try:
            return int(sys.argv[sys.argv.index(name) + 1])
        except (IndexError, ValueError):
            pass
    return default


def main() -> None:
    dry = "--dry" in sys.argv
    auto = Autopilot(dry_run=dry)
    if "--once" in sys.argv:
        report = auto.cycle()
        print("Connect autopilot cycle:", {k: v for k, v in report.items() if k != "errors"})
        if report["errors"]:
            print("Errors:", report["errors"])
        return
    interval = _opt_int("--interval", config.AUTOPILOT_INTERVAL)
    max_cycles = _opt_int("--max-cycles", 0) or None
    logger.info("Connect autopilot starting (interval=%ss, provider=%s, auto_reply=%s, dry=%s).",
                interval, config.PROVIDER, config.AUTO_REPLY_ENABLED, dry)
    try:
        auto.run(interval_seconds=interval, max_cycles=max_cycles)
    except KeyboardInterrupt:
        logger.info("Connect autopilot stopped.")


if __name__ == "__main__":
    main()
