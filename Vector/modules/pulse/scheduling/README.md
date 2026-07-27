# PULSE · Scheduling

Calendar-aware meeting booking, shared by Inbox and Connect. When a prospect is
ready to talk, the reply agent hands off here to **check real availability,
propose open slots, negotiate to a common time, and book** — autonomously.

## How it works

```
free_slots(calendar)  →  SchedulingAgent (reads client msg + our real openings)
                              │
      ┌───────────────┬───────┴────────┬─────────────┬──────────┐
   propose          book            negotiate       ask       decline
 offer 2-3 slots  client picked   their time is    what        no longer
                  a FREE slot →   taken → offer     works?      interested
                  create_event    nearest openings
```

**Anti-hallucination:** the agent may only book a slot that's genuinely in the
computed free list — `flow.handle_scheduling` validates the chosen time against
real availability before calling `create_event`, so it can never confirm a time
the host isn't actually free for. If the model picks a taken slot, it falls back
to proposing real ones (never a false "you're booked").

## Convergence

- Client accepts an offered slot → **book**.
- Client names a time that's free → **book**.
- Client names a time that's taken → **negotiate** with the closest open slots.
- Client gives a preference ("Thursday afternoon") → propose matching slots.
- No timing signal → propose top slots (or ask).

## Providers (`PULSE_CALENDAR_PROVIDER`)

| Provider | Cost | Notes |
|---|---|---|
| `mock` | free | in-memory; tests + dry demos; refuses double-booking |
| `google` | free | Google Calendar API: `freebusy` + `events.insert` + Meet link, OAuth |

Google setup: `pip install google-api-python-client google-auth-httplib2
google-auth-oauthlib`, download a Desktop OAuth client JSON, set
`GOOGLE_OAUTH_CLIENT_FILE`; first run opens consent and saves the token file for
reuse. (CalDAV/Outlook could be added as further providers behind the same
interface.)

## Config

Availability window, duration, slot granularity, lead-time buffer, lookahead,
and timezone all live in `config.py` (env-overridable — see `.env.example`).

## Layout

| Path | Role |
|------|------|
| `config.py` | working hours, duration, granularity, lookahead, provider, LLM tier |
| `schemas.py` | TimeSlot, BusyInterval, BookingRequest/Result, SchedulingDecision |
| `providers/` | `base` + `mock`, `google` |
| `availability.py` | deterministic free-slot computation from free/busy |
| `agent.py` | SchedulingAgent — interprets the client + writes the reply |
| `flow.py` | `handle_scheduling` — orchestrates, validates, books |
```
