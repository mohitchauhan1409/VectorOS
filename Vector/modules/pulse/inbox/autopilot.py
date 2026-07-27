"""Autopilot — the autonomous loop that runs Pulse hands-off.

Each **cycle** (hourly by default):
  1. intake  — enroll freshly-generated Scout leads into the experiment,
               split across the competing sequences by current performance
  2. poll    — fetch replies, classify them, and let the ConversationAgent
               auto-respond (book calls, answer questions, close politely)
  3. send    — advance every active campaign's sequence (bandit picks the arm)
  4. promote — lock in any within-campaign A/B winner that's now significant

Once a **week** it also runs the experiment evolution: re-rank the sequences,
retire the worst, spawn a fresh challenger.

Run it two ways:
  * daemon    — ``python -m modules.pulse.inbox.autopilot --interval 3600``
  * cron/one-shot — ``python -m modules.pulse.inbox.autopilot --once`` every hour

State (last weekly sync) lives in the DB, so one-shot cron invocations behave
exactly like a long-running loop. ``--dry`` composes/decides without sending.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone

from modules.common.logger import get_logger
from modules.pulse.inbox import config, experiments, store
from modules.pulse.inbox.analytics import ab_testing
from modules.pulse.inbox.schemas import CampaignStatus

logger = get_logger("pulse.inbox.autopilot")

_LAST_WEEKLY_KEY = "last_weekly_sync"


class Autopilot:
    """Runs Pulse autonomously: intake → poll/converse → send → promote, plus
    a weekly experiment evolution."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        # Reused across cycles so we don't rebuild LLM clients every tick.
        self._classifier = None
        self._conversation = None

    # -- one full cycle -----------------------------------------------------
    def cycle(self) -> dict:
        report = {"intake": 0, "replies": 0, "sent": 0, "completed": 0,
                  "promoted": 0, "errors": []}
        self._safe(report, "intake", self._intake)
        self._safe(report, "poll", self._poll)
        self._safe(report, "send", self._send)
        self._safe(report, "promote", self._promote)
        logger.info("Cycle done: %s", {k: v for k, v in report.items() if k != "errors"})
        return report

    def _safe(self, report: dict, phase: str, fn) -> None:
        """Run a phase; a failure in one phase never aborts the cycle."""
        try:
            fn(report)
        except Exception as exc:  # noqa: BLE001 — autonomy must survive transient errors
            logger.warning("Phase %s failed: %s", phase, exc)
            report["errors"].append(f"{phase}: {exc}")

    def _intake(self, report: dict) -> None:
        for group in store.list_groups(active_only=True):
            summary = experiments.intake_new(group.id)
            report["intake"] += summary.get("enrolled", 0)

    def _poll(self, report: dict) -> None:
        from modules.pulse.inbox.delivery import dispatcher
        if self._classifier is None:
            from modules.pulse.inbox.agents import ReplyClassifierAgent
            self._classifier = ReplyClassifierAgent()
        if self._conversation is None:
            from modules.pulse.inbox.agents import ConversationAgent
            self._conversation = ConversationAgent()
        replies = dispatcher.poll_replies(classifier=self._classifier,
                                          conversation_agent=self._conversation,
                                          dry_run=self.dry_run)
        report["replies"] += len(replies)

    def _send(self, report: dict) -> None:
        from modules.pulse.inbox.sequences import Scheduler
        for campaign in store.list_campaigns(status=CampaignStatus.ACTIVE):
            sched = Scheduler(campaign.id, dry_run=self.dry_run, throttle=not self.dry_run,
                              respect_window=True, variant_selector=ab_testing.bandit_selector)
            tick = sched.tick()
            report["sent"] += tick["sent"]
            report["completed"] += tick["completed"]

    def _promote(self, report: dict) -> None:
        for campaign in store.list_campaigns(status=CampaignStatus.ACTIVE):
            for step in campaign.steps:
                if ab_testing.evaluate_and_promote(step.id) is not None:
                    report["promoted"] += 1

    # -- weekly evolution ---------------------------------------------------
    def weekly_due(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        last = store.kv_get(_LAST_WEEKLY_KEY)
        if not last:
            return True
        try:
            last_dt = datetime.fromisoformat(last)
        except ValueError:
            return True
        return now - last_dt >= timedelta(days=config.WEEKLY_SYNC_DAYS)

    def run_weekly(self) -> list[dict]:
        results = []
        for group in store.list_groups(active_only=True):
            results.append(experiments.weekly_sync(group.id))
        store.kv_set(_LAST_WEEKLY_KEY, datetime.now(timezone.utc).isoformat())
        logger.info("Weekly evolution run for %d group(s).", len(results))
        return results

    # -- the loop -----------------------------------------------------------
    def run(self, interval_seconds: int = 3600, max_cycles: int | None = None) -> None:
        """Loop forever (or ``max_cycles`` times): cycle, weekly-if-due, sleep."""
        n = 0
        while True:
            self.cycle()
            if self.weekly_due():
                self.run_weekly()
            n += 1
            if max_cycles is not None and n >= max_cycles:
                return
            time.sleep(interval_seconds)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
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

    if "--weekly" in sys.argv:
        for res in auto.run_weekly():
            print(res)
        return

    if "--once" in sys.argv:
        report = auto.cycle()
        if auto.weekly_due():
            auto.run_weekly()
        print("Autopilot cycle:", {k: v for k, v in report.items() if k != "errors"})
        if report["errors"]:
            print("Errors:", report["errors"])
        return

    interval = _opt_int("--interval", config.AUTOPILOT_INTERVAL)
    max_cycles = _opt_int("--max-cycles", 0) or None
    logger.info("Autopilot starting (interval=%ss, auto_reply=%s, dry_run=%s). Ctrl-C to stop.",
                interval, config.AUTO_REPLY_ENABLED, dry)
    try:
        auto.run(interval_seconds=interval, max_cycles=max_cycles)
    except KeyboardInterrupt:
        logger.info("Autopilot stopped.")


if __name__ == "__main__":
    main()
