# Vector CRM

A professional GTM command center — the front-end dashboard for the **Vector** go-to-market engine. Every lead, company, buying signal, and multi-channel outreach sequence produced by Vector's Scout / Pulse / Closer modules surfaces here in one clean, dense, operator-grade interface.

> **Requires the backend.** This app reads all of its data from the Vector API at `http://localhost:8787` and has a login screen — it will not work on its own. Start `Vector/run_api.py` first. See the [root README](../README.md) for full setup instructions.

## Stack

- **Vite + React 18 + TypeScript**
- **Tailwind CSS** (tokens tuned to `DESIGN_SPEC.md`)
- **React Router**, **lucide-react**, **date-fns**
- Light theme, no gradients, no external UI kit — a hand-built, consistent design system.

## Run it

Start the backend first (in another terminal), then:

```bash
cd vector-crm
npm install
npm run dev
```

Then open **http://localhost:5273** and sign in with the demo account — `demo@vector.ai` / `demo1234`.

Point it at a non-default API host with `vector-crm/.env.local`:

```env
VITE_API_URL=http://localhost:9000
```

Other scripts:

```bash
npm run build     # type-check + production build
npm run preview   # serve the production build
```

## What's inside

| Route | View |
|---|---|
| `/` | **Dashboard** — KPIs, pipeline funnel, fresh buying signals, top accounts, active sequences, activity feed |
| `/people` | **People** — dense table of decision-makers with global + list search, multi-field filters, bulk actions, and a rich detail drawer |
| `/companies` | **Companies** — accounts ranked by ICP fit, signal timeline, decision-makers, ICP rationale drawer |
| `/campaigns` | **Campaigns (Pulse)** — email & LinkedIn plays; a step-by-step builder with A/B variants, editable subject/body, merge-tag chips, per-step stats, and the LinkedIn invite→accept→message flow |
| `/analytics` | **Analytics** — funnel, reply-rate trend, per-sequence performance |

Placeholders (routed, not yet built): `/lists`, `/inbox`, `/signals`, `/settings`, `/help`.

## Design reference

`DESIGN_SPEC.md` is the single source of truth for the visual language (colors, type, spacing, component states, page wireframes). Tokens live in `tailwind.config.js`.

## Data model

Every network call lives in `src/lib/api.ts` — components never call `fetch` directly, so auth headers, 401 handling, and error shaping stay in one place. Shared types are in `src/lib/types.ts`, login state in `src/lib/auth.tsx`, and the async-fetch hook in `src/lib/useAsync.ts`.

The backend seeds a demo workspace (47 companies, 102 people) on first boot, so the UI is populated without running the live engine. Rebuild it any time with `python -m backend.manage seed-demo --force` from the `Vector/` folder.
