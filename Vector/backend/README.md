# Vector Backend

FastAPI + SQLite service that unifies the Vector GTM engine (Scout → Pulse → Closer)
behind one API and one database, and powers the CRM frontend.

## What it does

- **Unified persistence** — one SQLite DB (`data/vector.db`, WAL mode) replaces the old
  per-company JSON files and the separate `inbox.db` / `connect.db` stores. Fully
  normalized schema (no JSON blobs), everything scoped to a `workspace`.
- **Auth** — email/password with PBKDF2 hashing and signed bearer tokens (stdlib only).
- **Two account modes**
  - **Demo account** (`demo@vector.ai` / `demo1234`) — seeded on startup with a rich,
    deterministic sample pipeline. Read-only for edits so it's always demo-ready.
  - **Real accounts** — register to get a fresh, empty workspace, then trigger a live
    engine run that finds companies/people and builds outreach — all persisted and shown
    in the UI. The frontend is display-only except sequence message edits.
- **Live orchestration** — `POST /api/pipeline/run` runs Scout's news radar + detective
  (LLM + search + email enrichment) and Pulse's campaign build + enrollment, importing
  every result into the workspace. Progress is tracked in `pipeline_runs`.

## Data model (`backend/models.py`)

```
Workspace ─┬─ User
           ├─ Company ─┬─ ICPCriterion   (matched / concern)
           │           ├─ Signal          (buying-signal history)
           │           └─ Person           (decision-makers)
           ├─ Campaign ─ Sequence(email|linkedin) ─ SequenceStep ─ Variant
           ├─ Enrollment   (person ↔ sequence)
           ├─ Message       (email/linkedin, outbound/inbound)
           ├─ Event         (activity timeline)
           └─ PipelineRun   (engine run tracking)
```

A **Campaign owns exactly two Sequences** — one email, one LinkedIn.

## Run it

```bash
# from repo root, with the venv active / deps installed (see requirements.txt)
python run_api.py                     # http://localhost:8787  (auto-creates schema + seeds demo)
# or:
uvicorn backend.app:app --port 8787 --reload
```

Environment (all optional; live runs need the engine keys already in `.env`):
- `VECTOR_DB_PATH` — SQLite path (default `data/vector.db`)
- `VECTOR_SECRET_KEY` — token signing secret (set in production)
- `VECTOR_CORS_ORIGINS` — comma-separated allowed origins (default includes localhost:5273)

## API surface

`/api/auth/{register,login,me}` · `/api/companies` (+`/facets`,`/{slug}`) ·
`/api/people` (+`/facets`,`/{id}`) · `/api/campaigns` (+`/{id}`,`/{id}/enrollments`,
`PATCH /variants/{id}`, `PATCH /{id}/status`) · `/api/dashboard` · `/api/analytics` ·
`/api/search` · `/api/pipeline/{run,runs}` · `/api/health`.

Interactive docs at `http://localhost:8787/docs`.
