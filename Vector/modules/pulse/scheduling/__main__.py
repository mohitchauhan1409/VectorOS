"""PULSE · SCHEDULING — verify the calendar + book a test meeting.

    python -m modules.pulse.scheduling                 # health check + next open slots
    python -m modules.pulse.scheduling --book          # book a test meeting in the first free slot
    python -m modules.pulse.scheduling --book --email you@x.com   # + send an invite

For the Google provider, the FIRST run opens a browser for one-time consent and
saves the token file — after that it's silent. Use --book to confirm a real
event shows up on your calendar (then delete it).
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from rich.console import Console

from modules.pulse.scheduling import availability, config
from modules.pulse.scheduling.providers import get_calendar_provider
from modules.pulse.scheduling.schemas import BookingRequest

console = Console()


def _opt(name: str, default: str = "") -> str:
    if name in sys.argv:
        i = sys.argv.index(name) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def main() -> None:
    console.rule("[bold]PULSE · Scheduling[/]")
    provider = get_calendar_provider()
    console.print(f"[dim]Provider:[/] [bold]{provider.name}[/]  ·  "
                  f"[dim]tz {config.TIMEZONE}, {config.WORK_START_HOUR:02d}:00-"
                  f"{config.WORK_END_HOUR:02d}:00, {config.MEETING_DURATION_MIN}min[/]")

    with console.status("[cyan]Authenticating + reading calendar…[/]", spinner="dots"):
        ok, detail = provider.health_check()
    console.print(("[green]✓[/] " if ok else "[red]✗[/] ") + detail)
    if not ok:
        console.print("\n[yellow]Set up the provider first (see .env.example / scheduling README).[/]")
        return

    now = datetime.now(timezone.utc)
    with console.status("[cyan]Computing open slots…[/]", spinner="dots"):
        slots = availability.free_slots(now, provider=provider, limit=8)
    if not slots:
        console.print("[yellow]No open slots in the window.[/] Widen hours/lookahead in config.")
        return
    console.print(f"\n[bold]Next {len(slots)} open slot(s):[/]")
    for s in slots:
        console.print(f"  • {s.label()}  [dim]{config.TIMEZONE}[/]")

    if "--book" in sys.argv:
        slot = slots[0]
        email = _opt("--email")
        console.print(f"\n[cyan]Booking a TEST meeting at[/] [bold]{slot.label()} {config.TIMEZONE}[/]"
                      + (f" [dim](invite → {email})[/]" if email else " [dim](no invite email)[/]"))
        res = provider.create_event(BookingRequest(
            attendee_name="Pulse Test", attendee_email=email, slot=slot,
            title="Pulse test meeting (safe to delete)",
            description="Created by `python -m modules.pulse.scheduling --book`."))
        if res.ok:
            console.print(f"[green]✓ Booked.[/] event id: {res.event_id}"
                          + (f"\n  join: {res.join_url}" if res.join_url else ""))
            console.print("[dim]Check your calendar — then delete this test event.[/]")
        else:
            console.print(f"[red]✗ Booking failed:[/] {res.error}")


if __name__ == "__main__":
    main()
