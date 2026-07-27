# Vector CRM

A professional GTM command center — the front-end dashboard for the **Vector** go-to-market engine. Every lead, company, buying signal, and multi-channel outreach sequence produced by Vector's Scout / Pulse / Closer modules surfaces here in one clean, dense, operator-grade interface.

> **Phase 1** — runs entirely on realistic sample data that mirrors Vector's real schemas (`Lead`, `DecisionMaker`, `Campaign`/`SequenceStep`/`Variant`, `Recipient`, `Prospect`). No pipeline integration yet.

## Stack

- **Vite + React 18 + TypeScript**
- **Tailwind CSS** (tokens tuned to `DESIGN_SPEC.md`)
- **React Router**, **lucide-react**, **date-fns**
- Light theme, no gradients, no external UI kit — a hand-built, consistent design system.

## Run it

```bash
cd vector-crm
npm install
npm run dev
```

Then open **http://localhost:5273**.

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
| `/sequences` | **Sequences (Pulse)** — email & LinkedIn plays; a step-by-step builder with A/B variants, editable subject/body, merge-tag chips, per-step stats, and the LinkedIn invite→accept→message flow |
| `/analytics` | **Analytics** — funnel, reply-rate trend, per-sequence performance |

## Design reference

`DESIGN_SPEC.md` is the single source of truth for the visual language (colors, type, spacing, component states, page wireframes). Tokens live in `tailwind.config.js`.

## Data model

All sample data is generated deterministically in `src/lib/data.ts` from seed pools, shaped to match the Vector engine exactly. Types live in `src/lib/types.ts`; derived views in `src/lib/queries.ts`. To wire real data in Phase 2, swap the exports in `src/lib/data.ts` for API calls — the rest of the app reads through `queries.ts`.
