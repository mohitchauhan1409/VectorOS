# PULSE · Inbox

Email outreach engine for Vector. Turns Scout's qualified leads + decision-makers
into **personalized, multi-step email sequences**, sends them over plain
SMTP/IMAP (no paid Smartlead/Instantly APIs), tracks every send and reply, and
uses agents to A/B-optimize the copy that converts.

Everything here is free and self-hosted: sending is `smtplib`, reply-reading is
`imaplib`, storage is SQLite — all Python stdlib.

## How it works

```
Scout leads (data/Leads/*.json)              ← qualified companies + decision-makers
        │  enrollment.py  (verified emails only, ICP filter, signal snapshot)
        ▼
Campaign ── SequenceStep ── Variant (A/B arm)         stored in data/pulse/inbox.db
        │
        ▼
Scheduler.tick()   ── picks who's due, a mailbox with headroom, and (via bandit)
        │              which arm; composes + sends; schedules the next step
        ├── WriterAgent        step 1  — signal-led personalized cold email
        ├── FollowUpAgent      step 2+ — thread-aware, non-repeating follow-ups
        ├── SmtpSender         send with RFC threading headers
        │
        ▼
ImapReader → dispatcher.poll_replies()
        └── ReplyClassifierAgent  — interested / not / OOO / unsubscribe / referral
              → stops, pauses (OOO resume), or suppresses the recipient
```

## Deliverability (earned, not bought)

The scheduler protects a young domain's reputation with: randomized human-like
send delays, per-mailbox **daily caps + warmup ramp**, **mailbox rotation**,
and a business-hours **send window**. `DeliverabilityGuardian` preflights
SPF/DKIM/DMARC and scans copy for spam triggers before you send.

## A/B optimization (multi-armed bandit)

`ABOptimizerAgent` generates several distinct persuasion *angles* per step.
`analytics/ab_testing.py` treats each as a Beta posterior and uses **Thompson
sampling** to route more sends to whichever arm is probably winning, then
auto-promotes a winner once it's statistically safe (`WINNER_CONFIDENCE`).
Angles steer the Writer, so tests generalize across every lead.

## Autonomous mode (Autopilot)

Runs Pulse hands-off. Each **cycle**: intake new Scout leads (split across the
experiment) → poll replies + auto-respond (ConversationAgent) → advance every
sequence → promote A/B winners. Once a **week**: evolve the experiment (retire
the worst sequence, spawn a challenger).

```bash
# daemon — hourly in production; use a short interval to watch it work
PULSE_AUTO_REPLY=true python -m modules.pulse.inbox.autopilot --interval 3600
PULSE_AUTO_REPLY=true python -m modules.pulse.inbox.autopilot --interval 120   # testing (2 min)

# one-shot, ideal for system cron ("0 * * * *")
python -m modules.pulse.inbox.autopilot --once
python -m modules.pulse.inbox.autopilot --once --dry   # decide/compose, send nothing
python -m modules.pulse.inbox.autopilot --weekly        # force the weekly evolution
```

The **ConversationAgent** reads each reply + the full thread and acts: proposes
times / shares a booking link (→ *meeting*), answers questions and nudges to a
call (→ *in-conversation*), closes gracefully (→ *not-interested*), or escalates
anything sensitive (→ *needs-human*). Guardrails: caps auto-replies per thread,
escalates on low confidence, and never sends unless `PULSE_AUTO_REPLY=true`.

## Campaign-level experiment (4 competing sequences)

```bash
python -m modules.pulse.inbox --setup-experiment    # design 4 themed sequences + allocate leads
python -m modules.pulse.inbox --experiment-status   # sequence leaderboard + next-batch split
```

Leads are split across the sequences by performance — cold start is even, then
the winner gets the lion's share (8 leads → 4/2/1/1) while losers keep being
explored. The weekly sync retires the worst and spawns a fresh challenger.

## CLI (single campaign)

```bash
python -m modules.pulse.inbox                # preview step-1 emails (dry-run)
python -m modules.pulse.inbox --full         # preview a full sequence for 1 recipient
python -m modules.pulse.inbox --setup-ab     # generate A/B arms for every step
python -m modules.pulse.inbox --preflight    # SPF/DKIM/DMARC + spam-copy checks
python -m modules.pulse.inbox --run          # LIVE: run one send tick (bandit)
python -m modules.pulse.inbox --run --force  # ignore the business-hours window
python -m modules.pulse.inbox --run --dry    # compose real copy, send nothing
python -m modules.pulse.inbox --poll         # fetch + classify replies over IMAP
python -m modules.pulse.inbox --metrics      # campaign + per-variant performance
```

## Configuration

Sending mailbox(es) come from the environment — see the `PULSE_*` block in
`.env.example`. One mailbox (`PULSE_EMAIL` + app password) or a rotating pool
(`PULSE_MAILBOXES` JSON). Tuning (caps, warmup, send window, sendable email
statuses, sequence, bandit thresholds, LLM tiers) lives in `config.py`.

## Layout

| Path | Role |
|------|------|
| `config.py` | caps, warmup, send window, sequence, bandit, mailbox env loading |
| `schemas.py` | Pydantic domain models (Campaign, Recipient, Message, Reply, Variant…) |
| `store.py` | SQLite persistence (`data/pulse/inbox.db`) |
| `enrollment.py` | read Scout leads + mailboxes → build/enroll a campaign |
| `compose/` | `WriterAgent` + `personalizer` (signal → personalized copy) |
| `delivery/` | `smtp_sender`, `imap_reader`, `accounts` (pool/caps), `dispatcher` |
| `sequences/` | `scheduler` — the send/timing/stop-on-reply engine |
| `analytics/` | `ab_testing` (bandit) + `metrics` |
| `agents/` | reply classifier, follow-up, A/B optimizer, deliverability guardian |
```
