"""PULSE · INBOX — outreach engine, live in the terminal.

Commands:
    python -m modules.pulse.inbox                 # dry-run: preview step-1 emails
    python -m modules.pulse.inbox --full          # dry-run: preview full sequence (1 recipient)
    python -m modules.pulse.inbox --limit 5       # cap recipients previewed
    python -m modules.pulse.inbox --setup-ab      # generate A/B arms for every step
    python -m modules.pulse.inbox --preflight     # deliverability checks (SPF/DKIM/DMARC + copy)
    python -m modules.pulse.inbox --run           # LIVE: activate + run one send tick (bandit)
    python -m modules.pulse.inbox --run --force   # LIVE: ignore the business-hours window
    python -m modules.pulse.inbox --run --dry     # tick with real copy but no mail sent
    python -m modules.pulse.inbox --poll          # fetch + classify replies
    python -m modules.pulse.inbox --metrics       # campaign + per-variant performance

Sending needs a mailbox configured via PULSE_* env (see .env.example).
"""

from __future__ import annotations

import logging
import sys

from rich import box
from rich.console import Console
from rich.panel import Panel

from modules.pulse.inbox import config, enrollment, store
from modules.pulse.inbox.compose import WriterAgent
from modules.pulse.inbox.schemas import RecipientStatus

console = Console()

logging.getLogger().setLevel(logging.WARNING)
for noisy in ("httpx", "httpcore", "anthropic", "pulse.inbox.store", "pulse.inbox.smtp",
              "pulse.inbox.enrollment", "detective.store", "pulse.inbox.scheduler",
              "pulse.inbox.dispatcher", "pulse.inbox.imap"):
    logging.getLogger(noisy).setLevel(logging.ERROR)

CAMPAIGN_NAME = "Konfyd Outreach"


def _flag(name: str) -> bool:
    return name in sys.argv


def _opt(name: str, default: int) -> int:
    if name in sys.argv:
        try:
            return int(sys.argv[sys.argv.index(name) + 1])
        except (IndexError, ValueError):
            pass
    return default


def _setup(quiet: bool = False):
    """Sync mailboxes, build the campaign, enroll leads. Returns (campaign, mailboxes)."""
    mailboxes = enrollment.sync_mailboxes_from_env()
    campaign = enrollment.build_campaign(
        CAMPAIGN_NAME, description="Auto-built from Scout qualified leads.", icp_min_score=0)
    summary = enrollment.enroll_campaign(campaign)
    if not quiet:
        if mailboxes:
            console.print(f"[dim]Mailbox pool:[/] {', '.join(m.email for m in mailboxes)}")
        else:
            console.print("[yellow]No mailboxes configured[/] [dim](preview only; see .env.example)[/]")
        console.print(
            f"[dim]Campaign:[/] [bold]{campaign.name}[/] [dim](#{campaign.id})[/]  ·  "
            f"[green]{summary['enrolled']}[/] enrolled, "
            f"[dim]{summary['duplicates']} existing, {summary['contactable']} contactable[/]")
        console.print("[dim]Sequence:[/] " + " → ".join(
            f"[bold]{s.name}[/][dim](+{s.wait_days}d)[/]" for s in campaign.steps))
    return campaign, mailboxes


def main() -> None:
    console.print(Panel.fit(
        "[bold magenta]📨  PULSE · INBOX[/]   [dim]·[/]   Personalized Outreach",
        border_style="magenta", padding=(1, 4)))

    if _flag("--setup-experiment"):
        _cmd_setup_experiment()
    elif _flag("--experiment-status"):
        _cmd_experiment_status()
    elif _flag("--setup-ab"):
        _cmd_setup_ab()
    elif _flag("--preflight"):
        _cmd_preflight()
    elif _flag("--run"):
        _cmd_run()
    elif _flag("--poll"):
        _cmd_poll()
    elif _flag("--metrics"):
        _cmd_metrics()
    else:
        _cmd_preview()


# ---------------------------------------------------------------------------
# preview (dry-run compose)
# ---------------------------------------------------------------------------
def _cmd_preview() -> None:
    console.rule("[bold]Setup[/] — campaign & enrollment")
    campaign, mailboxes = _setup()
    sender_name = mailboxes[0].from_name if mailboxes else ""

    recipients = store.list_recipients(campaign.id)
    if not recipients:
        console.print("\n[yellow]No contactable recipients.[/] [dim]Run Scout first, or set "
                      "ALLOW_GUESSED_EMAILS=True in inbox/config.py.[/]\n")
        return

    writer = WriterAgent()
    full = _flag("--full")
    if full:
        rec = recipients[0]
        console.rule(f"[bold]Preview[/] — full {len(campaign.steps)}-step sequence for {rec.name}")
        for step in campaign.steps:
            with console.status(f"[magenta]Writing step {step.step_order}…[/]", spinner="dots"):
                draft = writer.run(rec, step, sender_name=sender_name)
            _render_email(rec, step, draft, show_recipient=(step.step_order == 1))
    else:
        limit = _opt("--limit", 25)
        step1 = campaign.steps[0]
        console.rule(f"[bold]Preview[/] — “{step1.name}” (step 1) · up to {limit} recipient(s)")
        for rec in recipients[:limit]:
            with console.status(f"[magenta]Writing to {rec.name}…[/]", spinner="dots"):
                draft = writer.run(rec, step1, sender_name=sender_name)
            _render_email(rec, step1, draft)


# ---------------------------------------------------------------------------
# run (live / dry send tick)
# ---------------------------------------------------------------------------
def _cmd_run() -> None:
    from modules.pulse.inbox.analytics import ab_testing
    from modules.pulse.inbox.schemas import CampaignStatus
    from modules.pulse.inbox.sequences import Scheduler

    console.rule("[bold]Run[/] — one send tick (bandit selection)")
    campaign, mailboxes = _setup()
    dry = _flag("--dry")
    if not mailboxes and not dry:
        console.print("\n[red]No mailboxes configured.[/] Add PULSE_* env (see .env.example), "
                      "or use [bold]--run --dry[/] to compose without sending.\n")
        return

    store.set_campaign_status(campaign.id, CampaignStatus.ACTIVE)
    # Thompson-sampling bandit chooses which A/B arm each send uses.
    sched = Scheduler(campaign.id, dry_run=dry, throttle=not dry,
                      respect_window=not _flag("--force"),
                      variant_selector=ab_testing.bandit_selector)

    active = len(store.list_recipients(campaign.id, RecipientStatus.ACTIVE))
    with console.status(f"[magenta]Sending due step(s) to {active} active recipient(s)…[/]", spinner="dots"):
        report = sched.tick()
    _render_report("Send tick" + (" (dry)" if dry else ""), report)

    # Promote any arm that's now a statistically-safe winner.
    promoted = [ab_testing.evaluate_and_promote(s.id) for s in campaign.steps]
    for p in filter(None, promoted):
        console.print(f"[green]🏆 Promoted A/B winner:[/] [bold]{p.name}[/] [dim]{p.angle}[/]")


EXPERIMENT_NAME = "Konfyd Experiment"


def _cmd_setup_experiment() -> None:
    from modules.pulse.inbox import experiments

    console.rule("[bold]Experiment[/] — designing competing sequences")
    enrollment.sync_mailboxes_from_env()
    with console.status(f"[magenta]Designing {config.EXPERIMENT_SIZE} themed sequences…[/]", spinner="dots"):
        group = experiments.create_experiment(EXPERIMENT_NAME, icp_min_score=0)
    campaigns = store.list_group_campaigns(group.id)
    console.print(f"[dim]Experiment:[/] [bold]{group.name}[/] [dim](#{group.id})[/] · "
                  f"{len(campaigns)} competing sequences")
    for c in campaigns:
        console.print(f"  [cyan]▸[/] [bold]{c.theme.split(':')[0]}[/] "
                      f"[dim]{' → '.join(s.name for s in c.steps)}[/]")
    with console.status("[magenta]Allocating leads across sequences…[/]", spinner="dots"):
        summary = experiments.intake_new(group.id)
    console.print(f"\n[dim]Intake:[/] [green]{summary['enrolled']}[/] lead(s) allocated")
    for row in summary.get("per_campaign", []):
        console.print(f"  [cyan]•[/] {row['theme']}: [bold]{row['allocated']}[/] "
                      f"[dim](score {row['score']})[/]")


def _cmd_experiment_status() -> None:
    from rich.table import Table
    from modules.pulse.inbox import experiments

    console.rule("[bold]Experiment status[/] — sequence leaderboard")
    group = store.get_group_by_name(EXPERIMENT_NAME)
    if group is None:
        console.print("[yellow]No experiment yet.[/] Run [bold]--setup-experiment[/] first.")
        return
    ranked = experiments.rank_campaigns(group.id)
    table = Table(box=box.ROUNDED, header_style="bold cyan")
    for col in ("Rank", "Sequence", "Sent", "Positive", "Score", "Next-batch of 8"):
        table.add_column(col)
    plan = {r["campaign"].id: r["allocated"] for r in experiments.allocate(group.id, 8)}
    for i, d in enumerate(ranked):
        c = d["campaign"]
        table.add_row(f"{i+1}{'  🏆' if i == 0 else ''}", c.theme.split(':')[0],
                      str(d["sent"]), str(d["positive"]), f"{d['score']:.3f}",
                      str(plan.get(c.id, 0)))
    console.print(table)


def _cmd_setup_ab() -> None:
    from modules.pulse.inbox.agents import setup_ab_variants

    console.rule("[bold]A/B setup[/] — generating test arms per step")
    campaign, _ = _setup(quiet=True)
    with console.status(f"[magenta]Generating {config.VARIANTS_PER_STEP} arms/step…[/]", spinner="dots"):
        summary = setup_ab_variants(campaign, config.VARIANTS_PER_STEP)
    fresh = store.get_campaign(campaign.id)
    for step in fresh.steps:
        console.print(f"\n[bold]Step {step.step_order} · {step.name}[/] "
                      f"[dim]({summary.get(step.name, 0)} arms)[/]")
        for v in step.variants:
            console.print(f"  [cyan]•[/] [bold]{v.name}[/]: [dim]{v.angle}[/]")


def _cmd_preflight() -> None:
    from modules.pulse.inbox.agents import DeliverabilityGuardian

    console.rule("[bold]Preflight[/] — deliverability checks")
    _setup(quiet=True)
    guardian = DeliverabilityGuardian()
    with console.status("[magenta]Checking SPF/DKIM/DMARC + copy…[/]", spinner="dots"):
        report = guardian.preflight(sample=(
            "quick question", "Hi there, saw your recent raise — worth a quick look at how we help? Thanks"))
    if not report["domains"]:
        console.print("[yellow]No mailboxes configured — nothing to check.[/]")
    for d in report["domains"]:
        ok = lambda b: "[green]✓[/]" if b else "[red]✗[/]"  # noqa: E731
        console.print(f"  [bold]{d['domain']}[/]  SPF {ok(d['spf'])}  DMARC {ok(d['dmarc'])}  "
                      f"DKIM {ok(d['dkim'])}[dim]{(' · ' + d['dkim_selector']) if d['dkim'] else ''}[/]")
    for w in report["copy_warnings"]:
        color = "yellow" if w["level"] == "warn" else "dim"
        console.print(f"  [{color}]▲ {w['check']}:[/] {w['detail']}")
    verdict = "[green]ready to send[/]" if report["ok"] else "[red]fix auth records before sending[/]"
    console.print(f"\n[bold]Verdict:[/] {verdict}\n")


def _cmd_metrics() -> None:
    from rich.table import Table
    from modules.pulse.inbox.analytics import metrics

    console.rule("[bold]Metrics[/] — campaign performance")
    campaign, _ = _setup(quiet=True)
    m = metrics.campaign_metrics(campaign.id)
    console.print(
        f"[bold]{campaign.name}[/]  ·  [green]{m['emails_sent']} sent[/]  ·  "
        f"[cyan]{m['replies_total']} replies[/] ([bold]{m['reply_rate']:.0%}[/])  ·  "
        f"[green]{m['positive_replies']} positive[/] ({m['positive_reply_rate']:.0%})")
    console.print(f"[dim]Recipients:[/] " + "  ".join(
        f"{k}={v}" for k, v in m["recipients_by_status"].items()) or "[dim]none[/]")

    table = Table(box=box.ROUNDED, show_lines=False, header_style="bold cyan")
    for col in ("Step", "Arm", "Sent", "Replies", "Rate", "P(best)", ""):
        table.add_column(col)
    for step in m["steps"]:
        for i, a in enumerate(step["variants"]):
            flag = "🏆" if a["is_winner"] else ("⏸" if a["is_paused"] else "")
            table.add_row(
                f"{step['step_order']}·{step['name']}" if i == 0 else "",
                a["name"], str(a["sent"]), str(a["replies"]),
                f"{a['reply_rate']:.0%}", f"{a['p_best']:.0%}", flag)
    console.print(table)


# ---------------------------------------------------------------------------
# poll (fetch + classify replies)
# ---------------------------------------------------------------------------
def _cmd_poll() -> None:
    from modules.pulse.inbox.delivery import dispatcher

    console.rule("[bold]Poll[/] — fetch & classify replies")
    campaign, mailboxes = _setup(quiet=True)
    if not mailboxes:
        console.print("\n[red]No mailboxes configured[/] — nothing to poll.\n")
        return
    with console.status("[magenta]Polling mailboxes over IMAP…[/]", spinner="dots"):
        replies = dispatcher.poll_replies()
    if not replies:
        console.print("[dim]No new replies matched to our sent messages.[/]")
        return
    for r in replies:
        color = {"interested": "green", "unsubscribe": "red",
                 "out_of_office": "yellow"}.get(r.classification.value, "cyan")
        console.print(f"  [{color}]●[/] [bold]{r.classification.value}[/] "
                      f"[dim]({r.classification_confidence:.0%})[/] from [bold]{r.from_email}[/]")
        console.print(f"    [dim]{r.subject}[/]")


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
def _render_email(rec, step, draft, show_recipient: bool = True) -> None:
    header = ""
    if show_recipient:
        header = (f"[bold white]{rec.name}[/]  [dim]—[/] {rec.title or '?'}  [dim]({rec.company})[/]\n"
                  f"[dim]✉  {rec.email}  ·  signal: {rec.context.get('signal_type', '—')}[/]\n\n")
    console.print(Panel(
        f"{header}[bold]Step {step.step_order} · {step.name}[/]  [dim]angle: {step.angle}[/]\n"
        f"[dim]────────────────────────────────────────[/]\n"
        f"[bold cyan]Subject:[/] {draft.subject}\n\n{draft.body}",
        border_style="magenta", box=box.ROUNDED, padding=(1, 2)))


def _render_report(title: str, report: dict) -> None:
    parts = [f"[green]{report['sent']} sent[/]"]
    if report.get("completed"):
        parts.append(f"[cyan]{report['completed']} completed[/]")
    if report.get("reactivated"):
        parts.append(f"[cyan]{report['reactivated']} resumed[/]")
    if report.get("skipped_window"):
        parts.append("[yellow]held (outside send window — use --force)[/]")
    if report.get("skipped_capacity"):
        parts.append(f"[yellow]{report['skipped_capacity']} held (daily cap)[/]")
    if report.get("failed"):
        parts.append(f"[red]{report['failed']} failed[/]")
    console.print(f"\n[bold]{title}:[/] " + "  ·  ".join(parts) + "\n")


if __name__ == "__main__":
    main()
