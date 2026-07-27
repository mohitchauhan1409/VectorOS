# PULSE · Connect

LinkedIn outreach for Vector — the sibling of Inbox. Same "brain" (enrollment
from Scout, personalized compose, multi-step sequences, autonomous conversation,
A/B bandit, analytics, autopilot); the risky LinkedIn send layer is isolated
behind a **swappable provider** so it can be built and tested with zero ban risk.

## Providers (swap with `PULSE_CONNECT_PROVIDER`)

| Provider | Cost | Notes |
|---|---|---|
| `mock` | free | Simulates LinkedIn. Default. Powers all tests + dev — zero risk. |
| `phantombuster` | free tier | API on all plans + ~30 min/mo execution — good for demos. Runs on PhantomBuster's cloud + proxies. |
| `unipile` | 7-day free trial | Cleanest native LinkedIn API (invite / accepted-detection / messaging). Hosts session + proxy for you. |

We never run raw cookie/Voyager automation ourselves — the provider carries that
risk. Our scheduler enforces the safety playbook regardless of backend.

## The LinkedIn flow (state machine)

```
PENDING ──invite──▶ INVITE_SENT ──(accepted?)──▶ ACCEPTED ──messages──▶ COMPLETED
                         │                           │
                    (expires 21d)                 (reply) ──▶ IN_CONVERSATION / MEETING
                         ▼                                    / NOT_INTERESTED / NEEDS_HUMAN
                   INVITE_EXPIRED
```

An invite must be **accepted before we can message** — acceptance is a gate the
autopilot detects each cycle. A reply hands the prospect to the ConversationAgent
(book a call / answer / close / escalate) and stops the sequence.

## Safety playbook (enforced by our scheduler)

Weekly invite cap (~100, conservative) + daily cap + **warmup ramp**, daily
message cap, **working-hours window**, human-like jittered delays, account
rotation, and invite-expiry cleanup — applied no matter which provider is live.

## CLI

```bash
python -m modules.pulse.connect                # preview note + intro (dry-run)
python -m modules.pulse.connect --run          # one send tick (invites/messages, bandit)
python -m modules.pulse.connect --run --dry    # compose real copy, send nothing
python -m modules.pulse.connect --sync         # detect accepted invites (gate)
python -m modules.pulse.connect --poll         # fetch + classify replies
python -m modules.pulse.connect --metrics      # funnel + per-variant performance

# autonomous:
python -m modules.pulse.connect.autopilot --interval 3600      # hourly daemon
python -m modules.pulse.connect.autopilot --once               # one-shot (cron)
python -m modules.pulse.connect.autopilot --once --dry         # safe dry cycle
```

## Configuration

Provider + credentials come from the environment (see the Connect block in
`.env.example`). Caps, warmup, window, sequence, bandit, and LLM tiers live in
`config.py`. State is SQLite at `data/pulse/connect.db` (Scout's leads are read,
never modified).

## Layout

| Path | Role |
|------|------|
| `config.py` | caps/warmup/window, provider selection, sequence, LLM tiers |
| `schemas.py` | Prospect state machine, Campaign, Step(kind), Variant, Message, Reply |
| `store.py` | SQLite persistence |
| `enrollment.py` | account + campaign + read Scout LinkedIn URLs |
| `providers/` | `base` interface + `mock`, `phantombuster`, `unipile` |
| `compose/` | connection-note + LinkedIn-message writers |
| `delivery/dispatcher.py` | send / acceptance-sync / reply + conversation |
| `sequences/scheduler.py` | state machine, gate, caps, window |
| `analytics/` | A/B bandit + metrics |
| `agents/` | conversation agent (reply classifier reused from Inbox) |
| `autopilot.py` | hourly cycle: intake → accept → poll → send → promote |
```
