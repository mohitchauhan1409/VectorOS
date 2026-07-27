"""PULSE · CONNECT — LinkedIn outreach engine, live in the terminal.

Commands:
    python -m modules.pulse.connect                # preview note + intro (dry-run)
    python -m modules.pulse.connect --run          # run one send tick (invites/messages)
    python -m modules.pulse.connect --run --dry    # compose real copy, send nothing
    python -m modules.pulse.connect --run --force  # ignore the business-hours window
    python -m modules.pulse.connect --sync         # detect accepted invites (gate)
    python -m modules.pulse.connect --poll         # fetch + classify replies
    python -m modules.pulse.connect --metrics      # funnel + per-variant performance

Provider is chosen by PULSE_CONNECT_PROVIDER (mock | phantombuster | unipile).
Autonomous mode: python -m modules.pulse.connect.autopilot
"""

from __future__ import annotations

import logging
import sys

from rich import box
from rich.console import Console
from rich.panel import Panel

from modules.pulse.connect import config, enrollment, store
from modules.pulse.connect.compose import MessageWriterAgent, NoteWriterAgent
from modules.pulse.connect.providers import get_provider
from modules.pulse.connect.schemas import CampaignStatus

console = Console()
logging.getLogger().setLevel(logging.WARNING)
for noisy in ("httpx", "httpcore", "anthropic", "pulse.connect.store", "pulse.connect.enrollment",
              "detective.store", "pulse.connect.scheduler", "pulse.connect.dispatcher",
              "pulse.connect.mock", "pulse.connect.ab"):
    logging.getLogger(noisy).setLevel(logging.ERROR)

CAMPAIGN_NAME = "Konfyd LinkedIn"


def _flag(n: str) -> bool:
    return n in sys.argv


def _setup(quiet: bool = False):
    account = enrollment.sync_account()
    campaign = enrollment.build_campaign(CAMPAIGN_NAME, description="Auto-built from Scout leads.")
    summary = enrollment.enroll_campaign(campaign)
    provider = get_provider()
    ok, detail = provider.health_check()
    if not quiet:
        badge = "[green]✓[/]" if ok else "[yellow]○[/]"
        console.print(f"[dim]Provider:[/] [bold]{provider.name}[/] {badge} [dim]{detail}[/]")
        console.print(f"[dim]Account:[/] {account.name}  [dim]caps: {account.daily_invite_cap}/day, "
                      f"{account.weekly_invite_cap}/wk invites[/]")
        console.print(f"[dim]Campaign:[/] [bold]{campaign.name}[/] [dim](#{campaign.id})[/] · "
                      f"[green]{summary['enrolled']}[/] enrolled, {summary['contactable']} contactable")
        console.print("[dim]Sequence:[/] " + " → ".join(
            f"[bold]{s.name}[/][dim]({s.kind.value})[/]" for s in campaign.steps))
    return campaign, account


def main() -> None:
    console.print(Panel.fit("[bold blue]🔗  PULSE · CONNECT[/]   [dim]·[/]   LinkedIn Outreach",
                            border_style="blue", padding=(1, 4)))
    if _flag("--run"):
        _cmd_run()
    elif _flag("--sync"):
        _cmd_sync()
    elif _flag("--poll"):
        _cmd_poll()
    elif _flag("--metrics"):
        _cmd_metrics()
    else:
        _cmd_preview()


def _cmd_preview() -> None:
    console.rule("[bold]Setup[/] — account & enrollment")
    campaign, account = _setup()
    prospects = store.list_prospects(campaign.id)
    if not prospects:
        console.print("\n[yellow]No prospects with LinkedIn URLs.[/] [dim]Run Scout/Detective first.[/]\n")
        return
    p = prospects[0]
    invite_step = next(s for s in campaign.steps if s.kind.value == "invite")
    intro_step = next(s for s in campaign.steps if s.kind.value == "message")
    with console.status(f"[blue]Writing note + intro for {p.name}…[/]", spinner="dots"):
        note = NoteWriterAgent().run(p, invite_step, sender_name=account.name)
        intro = MessageWriterAgent().run(p, intro_step, prior=[], sender_name=account.name)
    console.print(Panel(
        f"[bold white]{p.name}[/] [dim]— {p.title} ({p.company})[/]\n[dim]{p.linkedin_url}[/]\n\n"
        f"[bold blue]① Connection note[/] [dim]({len(note.body)}/200 chars)[/]\n{note.body}\n\n"
        f"[bold blue]② Intro message[/] [dim](after they accept)[/]\n{intro.body}",
        border_style="blue", box=box.ROUNDED, padding=(1, 2)))


def _cmd_run() -> None:
    from modules.pulse.connect.analytics import ab_testing
    from modules.pulse.connect.sequences import Scheduler

    console.rule("[bold]Run[/] — one send tick (bandit)")
    campaign, account = _setup()
    dry = _flag("--dry")
    store.set_campaign_status(campaign.id, CampaignStatus.ACTIVE)
    sched = Scheduler(campaign.id, dry_run=dry, throttle=not dry,
                      respect_window=not _flag("--force"), variant_selector=ab_testing.bandit_selector)
    with console.status("[blue]Sending due invites/messages…[/]", spinner="dots"):
        rep = sched.tick()
    parts = [f"[green]{rep['invited']} invites[/]", f"[green]{rep['messaged']} messages[/]"]
    if rep["completed"]:
        parts.append(f"[cyan]{rep['completed']} completed[/]")
    if rep["skipped_window"]:
        parts.append("[yellow]held (outside window — use --force)[/]")
    if rep["skipped_capacity"]:
        parts.append(f"[yellow]{rep['skipped_capacity']} held (cap)[/]")
    console.print(f"\n[bold]Tick{' (dry)' if dry else ''}:[/] " + "  ·  ".join(parts) + "\n")


def _cmd_sync() -> None:
    from modules.pulse.connect.delivery import dispatcher
    console.rule("[bold]Sync[/] — detecting accepted invites")
    _setup(quiet=True)
    with console.status("[blue]Checking acceptances…[/]", spinner="dots"):
        res = dispatcher.sync_acceptances()
    console.print(f"[green]{res['accepted']} accepted[/] · [dim]{res['expired']} expired[/]")


def _cmd_poll() -> None:
    from modules.pulse.connect.delivery import dispatcher
    console.rule("[bold]Poll[/] — fetch & classify replies")
    _setup(quiet=True)
    with console.status("[blue]Polling…[/]", spinner="dots"):
        replies = dispatcher.poll_replies()
    if not replies:
        console.print("[dim]No new replies matched to prospects.[/]")
        return
    for r in replies:
        color = {"interested": "green", "unsubscribe": "red"}.get(r.classification.value, "cyan")
        console.print(f"  [{color}]●[/] [bold]{r.classification.value}[/] "
                      f"[dim]({r.classification_confidence:.0%})[/]  {r.body[:80]}")


def _cmd_metrics() -> None:
    from rich.table import Table
    from modules.pulse.connect.analytics import metrics
    console.rule("[bold]Metrics[/] — LinkedIn funnel")
    campaign, _ = _setup(quiet=True)
    m = metrics.campaign_metrics(campaign.id)
    console.print(
        f"[bold]{campaign.name}[/]  ·  [green]{m['invites_sent']} invites[/] → "
        f"[cyan]{m['accepted']} accepted[/] ([bold]{m['acceptance_rate']:.0%}[/])  ·  "
        f"[green]{m['messages_sent']} msgs[/]  ·  [cyan]{m['replies_total']} replies[/] "
        f"([bold]{m['reply_rate']:.0%}[/] of connected)")
    console.print("[dim]Prospects:[/] " + "  ".join(f"{k}={v}" for k, v in m["prospects_by_status"].items()))
    table = Table(box=box.ROUNDED, header_style="bold blue")
    for col in ("Step", "Kind", "Arm", "Sent", "Replies", "Rate", "P(best)"):
        table.add_column(col)
    for step in m["steps"]:
        for i, a in enumerate(step["variants"]):
            table.add_row(f"{step['step_order']}·{step['name']}" if i == 0 else "",
                          step["kind"] if i == 0 else "", a["name"], str(a["sent"]),
                          str(a["replies"]), f"{a['reply_rate']:.0%}",
                          f"{a['p_best']:.0%}{' 🏆' if a['is_winner'] else ''}")
    console.print(table)


if __name__ == "__main__":
    main()
