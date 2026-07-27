"""SCOUT — end-to-end lead engine, live in the terminal.

Runs Radar (find leads) -> Detective (decision-makers + emails) for LEADS_LIMIT
leads, with a live rich UI.

Usage:
    python -m modules.scout            # uses LEADS_LIMIT from config
    python -m modules.scout 5          # override: generate 5 leads
"""

from __future__ import annotations

import logging
import sys

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from modules.scout.config import LEADS_LIMIT
from modules.scout.detective import DetectivePipeline
from modules.scout.detective import store as det_store
from modules.scout.detective.config import (
    MAX_DECISION_MAKERS_PER_COMPANY,
    RESULTS_PER_ROLE,
    TARGET_ROLES,
)
from modules.scout.radar.config import MIN_ICP_SCORE
from modules.scout.radar.NewsRadar import NewsRadarPipeline

console = Console()

# Keep the UI clean — silence library/module chatter (real errors still show).
logging.getLogger().setLevel(logging.WARNING)
for noisy in (
    "httpx", "httpcore", "primp", "google_genai", "google_genai._api_client",
    "tool.google-search",  # CSE 403s are expected (we fall back to DuckDuckGo)
):
    logging.getLogger(noisy).setLevel(logging.ERROR)


def _email_color(status: str | None) -> str:
    return {"verified": "green", "unverified": "yellow", "guessed": "yellow"}.get(status or "", "white")


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else LEADS_LIMIT

    console.print(Panel.fit(
        "[bold cyan]🛰  SCOUT[/]   [dim]·[/]   GTM Lead Engine\n"
        "[dim]Radar → Detective → Emails[/]",
        border_style="cyan", padding=(1, 4),
    ))
    console.print(
        f"[dim]Target:[/] [bold]{limit}[/] [bold green]qualified[/] lead(s) "
        f"[dim](ICP ≥ {MIN_ICP_SCORE})[/] with full decision-maker data\n"
    )

    # ---------------- Phase 1 · Radar ----------------
    console.rule("[bold]Phase 1 · Radar[/] — discovering qualified leads")
    # save_floor = MIN_ICP_SCORE => only leads at/above the bar are saved, so
    # max_leads counts QUALIFIED leads and we scan until we have `limit` of them.
    radar = NewsRadarPipeline(save_floor=MIN_ICP_SCORE)
    found: list = []

    def on_lead(lead) -> None:
        found.append(lead)

    def on_article(article, outcome: str, is_lead: bool) -> None:
        # Live feed of every scanned article URL + its outcome.
        color = "green" if is_lead else ("yellow" if " < " in outcome else "dim")
        mark = "✓" if is_lead else "·"
        console.print(
            f"  [{color}]{mark}[/] [dim]{article.url[:74]}[/]  [{color}]{outcome}[/]"
        )

    with console.status("[cyan]Scanning news sources…[/]", spinner="dots") as status:
        def on_progress(evaluated: int, saved: int) -> None:
            status.update(
                f"[cyan]Scanning news…[/] [dim]{evaluated} articles evaluated ·[/] "
                f"[bold]{saved}/{limit}[/] qualified"
            )
        radar.run(max_leads=limit, on_lead=on_lead, on_progress=on_progress,
                  on_article=on_article)

    evaluated = getattr(radar, "_evaluated", 0)
    if not found:
        console.print(
            f"\n[yellow]No qualified leads (ICP ≥ {MIN_ICP_SCORE}) found[/] after evaluating "
            f"{evaluated} article(s).\n[dim]Options: lower MIN_ICP_SCORE or MAX_PAGES in "
            f"radar/config.py, or add more targeted sources.[/]"
        )
        return
    if len(found) < limit:
        console.print(
            f"\n[yellow]Found {len(found)}/{limit} qualified lead(s) after evaluating "
            f"{evaluated} article(s) (sources exhausted).[/]"
        )

    # ---------------- Phase 2 · Detective ----------------
    console.rule("[bold]Phase 2 · Detective[/] — decision-makers & emails")
    detective = DetectivePipeline(dry_run=False)
    leads = det_store.load_qualified_leads(only_qualified=True)[:limit]
    results: list[tuple[dict, list]] = []

    for lead in leads:
        company, domain = lead["company_name"], lead.get("website_url")
        console.print(f"\n[bold white]{company}[/]  [dim]{domain or ''}[/]")

        with console.status("[cyan]Searching LinkedIn profiles…[/]", spinner="dots"):
            candidates = detective.finder.find_candidates(
                company, list(TARGET_ROLES), results_per_role=RESULTS_PER_ROLE
            )
        with console.status("[cyan]Identifying decision-makers…[/]", spinner="dots"):
            people = detective.profile_agent.run(company, list(TARGET_ROLES), candidates).people
            detective._validate_profile_urls(people)
            people.sort(key=lambda p: p.confidence, reverse=True)
            people = people[:MAX_DECISION_MAKERS_PER_COMPANY]
        with console.status("[cyan]Finding & verifying emails…[/]", spinner="dots"):
            detective.email_finder.enrich(people, domain)

        det_store.save_decision_makers(lead["_path"], people)

        if not people:
            console.print("   [yellow]· no decision-makers found[/]")
        for p in people:
            console.print(f"   [green]•[/] [bold]{p.name}[/]  [dim]—[/] {p.title or '?'}  "
                          f"[dim]({p.role_category or '?'})[/]")
            console.print(f"     [dim]{p.linkedin_url or '—'}[/]")
            ec = _email_color(p.email_status)
            console.print(f"     ✉  [{ec}]{p.email or '—'}[/]  "
                          f"[dim]· {p.email_status or 'n/a'} · via {p.email_source or '—'}[/]")
        results.append((lead, people))

    _render_summary(results)


def _render_summary(results: list[tuple[dict, list]]) -> None:
    console.rule("[bold]Summary[/]")
    table = Table(box=box.ROUNDED, show_lines=True, header_style="bold cyan")
    table.add_column("Company")
    table.add_column("ICP", justify="center")
    table.add_column("Decision-maker")
    table.add_column("Email")
    table.add_column("Status", justify="center")

    total_people = total_emails = 0
    for lead, people in results:
        icp = str(lead["icp"]["score"])
        if not people:
            table.add_row(lead["company_name"], icp, "[dim]—[/]", "[dim]—[/]", "[dim]—[/]")
            continue
        for i, p in enumerate(people):
            total_people += 1
            if p.email:
                total_emails += 1
            ec = _email_color(p.email_status)
            table.add_row(
                f"[bold]{lead['company_name']}[/]" if i == 0 else "",
                icp if i == 0 else "",
                f"{p.name}\n[dim]{p.title or ''}[/]",
                f"[{ec}]{p.email or '—'}[/]",
                f"[{ec}]{p.email_status or '—'}[/]\n[dim]{p.email_source or ''}[/]",
            )
    console.print(table)
    console.print(
        f"\n[bold green]Done.[/] {len(results)} lead(s) · {total_people} decision-maker(s) · "
        f"{total_emails} email(s) found.  [dim]Saved to data/Leads/[/]\n"
    )


if __name__ == "__main__":
    main()
