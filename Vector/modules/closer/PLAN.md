# CLOSER — design plan (for review, not yet built)

> Vector's third module. Scout finds the deal, Pulse opens it, **Closer closes it.**
> Everything below is free-tier / self-hosted only. No paid SaaS anywhere in the
> default path; paid options are named but always optional providers.

---

## 0 · What "closing a deal" actually mechanically requires

The intro call is over. Deals from here are won or lost on eight mechanics — Closer
automates each one:

| # | Mechanic | Who owns it in Closer |
|---|----------|----------------------|
| 1 | Recap within hours: what we heard, agreed next step, timeline | `compass` → `RecapWriterAgent` |
| 2 | Qualification memory (MEDDICC): pain, metric, economic buyer, decision process, competition, timeline | `compass` → `FactExtractorAgent` + `deal_facts` |
| 3 | Momentum: a next event always exists on the calendar | `compass` → reuse `pulse.scheduling` |
| 4 | Commercial shaped by what they actually said, priced from a real price book | `quote` |
| 5 | Objection handling (price, security, build-it-ourselves, not-now, no budget) | `compass` → `ObjectionAgent` + battlecards |
| 6 | Multi-threading: pull in the stakeholders named on the call | `compass` → feeds Scout Detective |
| 7 | Nudge cadence that ends in yes / no / a date | `followup.py` |
| 8 | Forecast: which deals are real | `health.py` + weekly `ForecastAgent` |

---

## 1 · Sub-module layout (mirrors Scout/Pulse conventions)

```
modules/closer/
├── config.py            # module config; all knobs imported from common/control.py §8
├── schemas.py           # Pydantic domain models + enums (mirrors inbox/schemas.py)
├── store.py             # SQLite -> data/closer/closer.db (mirrors inbox/store.py)
├── pipeline.py          # deal stage machine — deterministic transitions
├── health.py            # deal health / probability formula (no LLM)
├── followup.py          # post-meeting nudge cadence + stall detection
├── conversation.py      # inbound reply handler for deals (called from Pulse dispatcher)
├── executor.py          # runs planned actions through the guardrails
├── autopilot.py         # the autonomous loop (intake→capture→digest→decide→act→chase→sync)
├── __main__.py          # CLI: status, ingest, digest, decide, act, deal <id>, quote ...
│
├── scribe/              # ── 1. GET THE MEETING IN ──────────────────────────
│   ├── providers/
│   │   ├── base.py      # TranscriptProvider protocol
│   │   ├── manual.py    # watched drop folder + paste (DEFAULT, zero setup)
│   │   ├── gemini.py    # audio -> Gemini free tier -> diarized transcript
│   │   ├── whisper.py   # audio -> faster-whisper locally (offline, no quota)
│   │   ├── meet.py      # Google Meet REST API transcripts (needs paid Workspace)
│   │   ├── bot.py       # self-hosted Vexa/Attendee bot (phase 3, optional)
│   │   └── mock.py      # canned transcript for tests/dry runs
│   ├── recorder.py      # optional ffmpeg + BlackHole dual-track capture (macOS)
│   ├── matcher.py       # match a transcript/audio file -> the right meeting (rules first)
│   └── ingest.py        # normalize (vtt/srt/txt/json), dedupe by checksum, segment, store
│
├── compass/             # ── 2. THINK + DECIDE ──────────────────────────────
│   ├── agent.py         # CompassAgent (exists as stub) -> NextStepDecision
│   └── agents/
│       ├── summarizer_agent.py    # transcript -> MeetingSummary (map-reduce, evidence-cited)
│       ├── fact_extractor_agent.py# transcript -> deal facts (MEDDICC slots) + confidence
│       ├── recap_writer_agent.py  # post-meeting recap email
│       ├── objection_agent.py     # objection reply grounded in battlecards
│       ├── followup_agent.py      # cadence copy, escalating, breakup
│       └── forecast_agent.py      # weekly deal-health commentary + risk flags
│
└── quote/               # ── 3. COMMERCIALS ─────────────────────────────────
    ├── catalog.py       # OUR price book: SKUs, tiers, units, terms, discount policy
    ├── pricing.py       # deterministic math (Python, never the LLM)
    ├── agent.py         # ProposalAgent: picks package + writes narrative only
    └── renderer.py      # quote -> Markdown / self-contained HTML / PDF / Google Doc
```

Naming rationale: `scribe` (captures the meeting), `compass` (decides direction — the
stub already there), `quote` (the commercial). Same "noun-per-capability" style as
`radar` / `detective` / `inbox` / `connect` / `scheduling`.

---

## 2 · The crucial part: where the transcript comes from (all free)

Google Meet **does not** give transcripts on a free `@gmail.com` account — saved
transcripts and Gemini notes are gated behind paid Workspace editions, and the Meet
REST API can only return a transcript artifact that Meet itself generated. So the
Meet API is built as an *optional* provider, never the default. Third-party free
tiers (Otter/Fireflies/Tactiq) gate their **API** behind paid plans, so they're out.

Provider chain, tried in configured order (`CLOSER_TRANSCRIPT_PROVIDERS`):

### Tier 0 — `manual` (default, zero setup, zero dependency)
A watched folder `data/closer/inbox/`. Drop either:
* a transcript — `.txt` `.md` `.vtt` `.srt` `.json` (Meet/Zoom/Otter exports all work), or
* a recording — `.m4a` `.mp3` `.wav` `.mp4` (QuickTime / Zoom local recording / OBS — all free)

Or paste notes: `python -m modules.closer ingest --deal 12 --file notes.txt`.
This path works on day one and is the fallback for every other tier.

### Tier 1 — `gemini` (recommended default once a recording exists)
Audio/video → **Gemini 2.5 Flash** → diarized, timestamped transcript.
* Uses the `GOOGLE_API_KEY` already in `.env`; `google-generativeai` is already a dependency.
* Free tier is generous (~1,500 requests/day on 2.5 Flash at time of writing — re-verify at build time); audio ≈ 32 tokens/sec, so a 30-min call ≈ 58k tokens — comfortably inside one request.
* Long calls are chunked with `ffmpeg` (free) and stitched with offsets.
* Trade-off to accept knowingly: free-tier Gemini data may be used for product improvement. Flagged in the README + a `CLOSER_CLOUD_STT_OK` switch.

### Tier 2 — `whisper` (offline, unlimited, private)
`faster-whisper` (CTranslate2, pip, MIT) `small`/`base` int8 on CPU. No quota, no network.

**The free-diarization trick:** record two tracks — your mic (= us) and system audio
via **BlackHole** (free virtual audio device) (= them) — then transcribe each track
separately and interleave by timestamp. Perfect two-speaker labelling with no
`pyannote`, no HF token, no GPU. `scribe/recorder.py` sets this up with one ffmpeg
command and can auto-start/stop around a booked calendar event.

### Tier 3 — `meet` (real Meet transcripts — only if you ever have paid Workspace)
`conferenceRecords.transcripts` + `.entries`, matched to our stored `event_id`.
Reuses the existing Google OAuth token file with added scopes. Note: transcript
**entries are deleted 30 days** after the conference, so autopilot polls promptly
and stores the text locally. Built, documented, **off by default.**

### Tier 4 — `bot` (self-hosted meeting bot — optional phase 3)
Vexa (Apache-2.0) or Attendee, self-hosted via Docker: a headless bot joins the
Meet, records, transcribes with local Whisper, exposes REST + webhooks. Free but
heavy (Docker, headless Chrome, a burner Google account, and someone must admit the
bot). Shipped as a provider stub + setup doc, not a default.

### Matching a file to a deal (rules first, LLM last)
1. Filename convention `deal12_...` / `<company>-2026-07-26...` → exact.
2. Else: nearest `meeting` row whose window contains the file's recording time (mtime − duration), within ±`MATCH_WINDOW_HOURS`.
3. Else: fuzzy-match company/attendee names found in the first ~40 lines of the transcript.
4. Else: `needs_human` with the candidate list. **Never a silent guess.**

Dedupe by SHA-256 of normalized text, so re-dropping a file is a no-op.

### Consent
`CLOSER_RECORDING_CONSENT_LINE` is appended to invites/recaps when recording is on;
`CLOSER_REQUIRE_CONSENT` blocks ingestion of recordings for deals not flagged consented.

---

## 3 · Handoff: Pulse → Closer (one small seam)

Pulse already produces everything Closer needs to start:
`RecipientStatus.BOOKED` + `context["booked_event_id"]` + `context["booked_slot_iso"]`
+ a `meeting_booked` event (see `pulse/inbox/delivery/dispatcher.py:403`).

* **Intake:** Closer's autopilot scans `inbox.db` / `connect.db` for BOOKED recipients with no deal → creates a `Deal` at stage `meeting_scheduled`. (Precedent: Inbox reads Scout's JSON; Closer reads Pulse's stores and writes only its own DB.)
* **Reply routing:** Pulse keeps IMAP polling (dedupe by UID, threading, classification all exist). One new branch in `handle_conversation`: if a Closer deal exists **and** the first meeting has already happened → delegate to `modules.closer.conversation.handle_reply(...)`. Adds `RecipientStatus.CLOSING`.
* **Sending:** Closer sends through `pulse.inbox.delivery.dispatcher.send_reply` → same mailbox, same thread, existing warmup/throttle/window logic. No new transport.
* **Booking the next meeting:** reuse `pulse.scheduling.handle_scheduling` — it already does propose / negotiate / book / reschedule / cancel against real free-busy. One small extension needed: per-call **duration + title override** (a demo is 45 min, not the global 30) threaded through `availability.free_slots` and `flow.handle_scheduling`.

---

## 4 · Data model (`data/closer/closer.db`, SQLite — stdlib, free)

| Table | Purpose |
|-------|---------|
| `deals` | recipient_id, channel, company, contact, campaign, **stage**, amount, currency, probability, health_score, next_action + next_action_at, target_close_date, needs_human_reason, timestamps |
| `meetings` | deal_id, kind (`intro`\|`demo`\|`technical`\|`stakeholder`\|`commercial`\|`closing`), event_id, slot_start/end, join_url, attendees, status (`scheduled`\|`held`\|`no_show`\|`cancelled`), transcript_id |
| `transcripts` | meeting_id, source, language, duration, full text, segments JSON, speaker_map, checksum (dedupe) |
| `summaries` | meeting_id, tldr, agenda_covered, pains, objections, action_items (ours/theirs + due), buying_signals, risks, sentiment, verbatim evidence quotes, proposed_next_step, confidence |
| `deal_facts` | **the accumulating deal brain** — deal_id, key (meddicc slot or custom: pain, metric, budget, timeline, economic_buyer, champion, competitor, tech_stack, team_size…), value, confidence, source_meeting_id, evidence_quote, updated_at |
| `quotes` | deal_id, version, package, line_items JSON, units, term_months, list_total, discount_pct, net_total, valid_until, status (`draft`\|`pending_approval`\|`sent`\|`accepted`\|`rejected`\|`superseded`), rendered_path, approved_by |
| `actions` | **the outbox** — deal_id, type, payload, status (`planned`\|`due`\|`executing`\|`done`\|`skipped`\|`failed`), due_at, confidence, requires_approval, result |
| `events` | audit timeline (same shape as inbox's) |
| `kv_state` | autopilot bookkeeping (last weekly run, etc.) |

The `actions` table is deliberate: **Compass only plans; the executor performs.** Every
autonomous move is inspectable, approvable, retryable, and idempotent.

### Deal stages (deterministic machine in `pipeline.py`)
```
meeting_scheduled → awaiting_transcript → meeting_held → recap_sent
   → awaiting_next_step ⇄ next_meeting_booked
   → proposal_requested → proposal_sent → negotiation
   → verbal_commit → contract_sent → closed_won
                                   ↘ closed_lost | nurture (long-term)
```
The LLM *proposes* a transition; `pipeline.py` decides whether it's legal.

---

## 5 · What is LLM and what is code (the safety line)

**Code only — never the model:** slot availability & booking validation · all pricing
arithmetic · discount thresholds and approval gates · cadence timing, caps, business
hours · stage transitions · transcript↔deal matching · health score · dedupe.

**LLM (structured output via `with_structured_output`, like every existing agent):**

| Agent | Tier | Output |
|-------|------|--------|
| `SummarizerAgent` | HIGH | `MeetingSummary` — map-reduce over chunks, **every action item must carry a verbatim quote** or it's dropped in code |
| `FactExtractorAgent` | NORMAL | `DealFact[]` with confidence + evidence; merge policy (latest-wins, confidence-weighted) is code |
| `CompassAgent` | HIGH | `NextStepDecision` — action, rationale, urgency, what to ask/offer, confidence. Inputs: summary, deal brain, **MEDDICC gaps**, stage, action history, playbook |
| `RecapWriterAgent` | HIGH | thread-aware recap email: what we heard, action items, one clear ask, optional times |
| `ProposalAgent` | HIGH | picks package + quantities **from the catalog** and writes narrative sections only |
| `ObjectionAgent` | HIGH | objection reply grounded in `catalog.BATTLECARDS` |
| `FollowupAgent` | NORMAL | nudge copy per cadence step, escalating, then breakup |
| `ForecastAgent` | NORMAL, weekly | health commentary, risk flags, "what would move this" |

Same tiering discipline as Pulse: client-facing writing = `HIGH_EFFORT_LLM`, triage/extraction = `NORMAL_LLM`.

---

## 6 · The autonomous loop (`closer/autopilot.py`)

Every cycle (default 30 min; `--once` for cron, `--dry` for no side effects — identical
CLI shape to `pulse.inbox.autopilot`). Each phase wrapped in `_safe()` so one failure
never aborts the cycle.

1. **intake** — new BOOKED recipients → deals; reconcile calendar changes (moved/cancelled events).
2. **capture** — for meetings past `end + GRACE`: walk the provider chain, ingest, dedupe. No transcript after `NO_TRANSCRIPT_HOURS` → apply `NO_TRANSCRIPT_POLICY` (`wait` \| `neutral_followup` \| `escalate`) and flag possible no-show.
3. **digest** — summarize + extract facts for un-digested transcripts; update the deal brain; recompute health.
4. **decide** — Compass proposes next actions for deals lacking one → `actions` rows.
5. **act** — executor runs due actions through guardrails: send recap / propose times & book / send proposal / handle objection / escalate. Auto-send only if allowed + confident + inside caps; otherwise stored as a draft with `requires_approval`.
6. **chase** — cadence + stall detection: overdue follow-up, no reply in N days → nudge → final nudge → `closed_lost`/`nurture` per policy.
7. **sync** — mirror into `vector.db` so the CRM shows it (mirrors `backend/pulse_sync.py`).

**Weekly:** forecast review + playbook learning — recap styles and proposal framings
become bandit arms exactly like Pulse's variants, with **stage advancement** as the
reward signal instead of reply rate.

---

## 7 · Guardrails (mirroring the `PULSE_LIVE` philosophy)

* `CLOSER_LIVE` — master switch. Off ⇒ no email, no booking, no file leaves the machine; everything is drafted. Default **off**.
* `CLOSER_AUTO_SEND` — recaps/follow-ups auto-send. Default off.
* `CLOSER_AUTO_PROPOSAL` — proposals auto-send. Default **off**: money-bearing documents get a human by default.
* Discount policy in `catalog.py`: `MAX_AUTO_DISCOUNT_PCT`, `MAX_AUTO_ACV`, floor price. Beyond it ⇒ `pending_approval`.
* The renderer **asserts** every number in the document matches the `quotes` row — the model cannot state a price it didn't compute.
* Recap action items without transcript evidence are dropped in code (anti-hallucination on commitments).
* Per-deal caps: max auto-emails/week, min hours between touches, business-hours window (reuses `control.py` windows).
* Always human: legal/security review, contract redlines, procurement, angry threads, anything under the confidence floor.

---

## 8 · Commercials (`quote/`) — how "write the commercial" works

1. `catalog.py` holds the **price book as config** (same spirit as `COMPANY_PROFILE` in
   `radar/config.py`): packages, unit prices, minimum terms, add-ons, discount policy,
   payment terms, and `BATTLECARDS` (objection → proof points).
2. `ProposalAgent` reads the deal brain + summaries and chooses package, quantities,
   term, and the narrative: their situation in their words, the outcomes they said they
   wanted, scope, success criteria, why now.
3. `pricing.py` does all arithmetic and applies the policy → a `quotes` row.
4. `renderer.py` emits: Markdown → self-contained **HTML** (zero-dep, default) → optional
   **PDF** via `reportlab` (pure-Python, free) → optional **Google Doc** created + exported
   via the existing Google OAuth (free, gives a shareable link).
5. Delivery: attached/linked in-thread by the executor; status tracked
   `draft → pending_approval → sent → accepted/rejected`, with versioning on every
   renegotiation.

---

## 9 · CRM surface (phase 6, optional)

New ORM models `Deal`, `DealMeeting`, `DealFact`, `Quote`, `DealAction`; `backend/closer_sync.py`
(mirrors `pulse_sync.py`, idempotent rebuild per workspace); router `/api/deals`
(list, detail+timeline, approve/reject an action, approve a quote, upload a transcript);
frontend `DealsPage` (kanban by stage) + `DealDrawer` (summary · deal brain · quote ·
pending actions with Approve buttons) replacing a `PlaceholderPage`.

---

## 10 · Cost sheet (everything default-path is free)

| Need | Free choice | Paid alternative (optional) |
|------|-------------|------------------------------|
| Transcription | Gemini free tier **or** faster-whisper local | Workspace Business Standard+ Meet transcripts, Recall.ai |
| Recording | QuickTime/OBS + ffmpeg + BlackHole | — |
| Meeting bot | self-hosted Vexa / Attendee (Docker) | Recall.ai, MeetingBaas |
| Calendar + Meet link | Google Calendar API (already wired) | — |
| Email send/receive | SMTP + IMAP (already wired) | — |
| Reasoning | existing Anthropic / Gemini keys | — |
| Proposal doc | HTML + reportlab, or Google Docs export | PandaDoc/DocuSign |
| Storage | SQLite | — |

---

## 11 · Touches to existing code (small, explicit — please approve)

1. `modules/common/control.py` → new `§8 · CLOSER` block (all knobs, one place, as per that file's rule).
2. `modules/pulse/scheduling/{availability,flow}.py` → optional `duration_min` / `title` override per booking (demo ≠ intro length).
3. `modules/pulse/inbox/schemas.py` → add `RecipientStatus.CLOSING`.
4. `modules/pulse/inbox/delivery/dispatcher.py` → one delegation branch into `closer.conversation`.
5. `requirements.txt` → optional extras, commented like the existing Google block (`faster-whisper`, `reportlab`).
6. `main.py` → register Closer in `build_engine()`; `.env.example` → `CLOSER_*` keys.
7. `Vector/README.md` → Closer section.

Nothing in Scout or Pulse changes behaviour when Closer is off.

---

## 12 · Build order (each phase independently runnable + smoke-tested)

| Phase | Deliverable | Smoke test |
|-------|-------------|-----------|
| 1 | `config` · `schemas` · `store` · `pipeline` · `control §8` · CLI skeleton · `mock` provider | `scripts/test_closer_store.py` — create deal, transition stages, log events |
| 2 | `scribe`: manual + gemini + whisper + meet(stub) providers, matcher, ingest | `scripts/test_closer_scribe.py` — drop a file, get a stored transcript on the right deal |
| 3 | `compass`: summarizer, fact extractor, CompassAgent, health | `scripts/test_closer_digest.py` — canned transcript → summary + MEDDICC brain + next-step decision |
| 4 | recap writer, executor, next-meeting booking, followup cadence, reply handler + dispatcher seam | `scripts/test_closer_act.py --dry` — full post-meeting turn without sending |
| 5 | `quote`: catalog, pricing, ProposalAgent, renderer, approvals, negotiation guardrails | `scripts/test_closer_quote.py` — deal → priced proposal HTML/PDF, discount gate fires |
| 6 | `autopilot`, `closer_sync`, `/api/deals`, (optional) CRM UI | `python -m modules.closer.autopilot --once --dry` end-to-end |

---

## 13 · Decisions needed from you

1. **Default transcript source** — Gemini free tier (easiest, cloud) vs local Whisper (offline, private) vs manual-only to start?
2. **Do you have paid Google Workspace** on the meeting account? If yes, the `meet` provider becomes a first-class path and recording becomes unnecessary.
3. **Price book** — real Humwork packages/prices to encode in `catalog.py`, or placeholder structure you fill in later?
4. **Proposal autonomy** — human-approve before any commercial goes out (recommended), or fully autonomous?
5. **Scope now** — engine only (phases 1–6 backend), or include the CRM Deals UI in this build?
