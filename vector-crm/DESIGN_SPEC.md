# Vector — Design System Specification

**Product:** Vector — Autonomous GTM (go-to-market) engine + CRM
**Document type:** Implementation-ready design system reference
**Theme:** Light only (no dark mode)
**Author:** Product Design / UI Lead
**Status:** Build reference — hand directly to engineering

> This document is the single source of truth for Vector's visual language. Every value here is intended to be tokenized. Engineers should implement these as CSS custom properties / Tailwind theme tokens and reference them by name — never hardcode raw hex in components.

---

## 0. How to read this spec

- All colors are exact HEX. Where opacity is used it is called out explicitly.
- Spacing, radius, and sizing use a **4px base grid**. Tokens are named `space-1` (4px) … `space-16` (64px).
- Component states are always specified in the order: **default → hover → active/pressed → focus → disabled**.
- "Restraint" is a hard requirement. When in doubt: less color, less shadow, less radius, more whitespace, more alignment.

---

## 1. Design Principles

1. **Data is the interface.** The product's value is the density and trustworthiness of GTM data. Chrome recedes; rows, values, and signals lead. We optimize for scanning hundreds of records, not decorating a few.
2. **Calm authority.** This is an expensive, serious B2B tool used all day by revenue teams. Neutral grays dominate; a single restrained brand accent carries intent. Nothing pulses, glows, or shouts.
3. **Every pixel earns its place.** No decorative gradients, no glassmorphism, no oversized rounded bubbles, no emoji in the UI. If an element doesn't aid comprehension or action, remove it.
4. **Truth is visible.** Data confidence (email verification, ICP tier, signal freshness) is surfaced through consistent, subtle status semantics — never hidden, never exaggerated.
5. **Fast, legible hierarchy.** Weight and size — not color — establish hierarchy in text. Color is reserved for status, links, and primary actions.
6. **Consistency over cleverness.** One table pattern, one badge pattern, one drawer pattern reused everywhere. Users should learn the system once.
7. **Keyboard-first, dense-by-default.** Power users live here. Support keyboard navigation, tight (but breathable) row heights, and bulk actions everywhere lists appear.

---

## 2. Color Palette

### 2.1 Neutral gray scale (the backbone)

A cool, slightly blue-leaning gray — reads as "software," not "warm paper." This scale carries ~90% of the UI.

| Token | HEX | Usage |
|---|---|---|
| `gray-50`  | `#F8FAFC` | App background, table zebra (optional), hover fills |
| `gray-100` | `#F1F5F9` | Subtle surface, hover on white rows, chip background |
| `gray-200` | `#E5E9F0` | Default borders, dividers, table gridlines |
| `gray-300` | `#D3DAE6` | Stronger borders, input borders, disabled surface edge |
| `gray-400` | `#A6B0C0` | Placeholder text, disabled text, muted icons |
| `gray-500` | `#6B7688` | text-muted, secondary icons |
| `gray-600` | `#4B5563` | text-secondary |
| `gray-700` | `#374151` | Strong secondary text, table cell primary |
| `gray-800` | `#1F2733` | text-primary, headings |
| `gray-900` | `#0F1420` | Display headings, highest-contrast text |

> Pure white `#FFFFFF` is used for cards/surfaces and sits on `gray-50`. Never use pure black `#000000` for text — top text is `gray-900`.

### 2.2 Brand / primary accent

**Vector Indigo** — a deep, professional indigo-slate. Confident, not neon, no gradient.

| Token | HEX | Usage |
|---|---|---|
| `brand-50`  | `#EEF1FB` | Tinted backgrounds (selected nav, primary badge bg) |
| `brand-100` | `#DDE3F7` | Hover on tinted surfaces |
| `brand-200` | `#BCC7EF` | Borders on brand-tinted elements |
| `brand-400` | `#5B6ED0` | Hover state accents |
| `brand-500` | `#3E4FB8` | Focus ring base (used at reduced opacity) |
| `brand-600` | `#33409B` | **Primary** — buttons, links, active nav indicator |
| `brand-700` | `#2A3580` | Primary hover / pressed |
| `brand-800` | `#212A66` | Primary pressed on dark contexts |

Primary action color = `brand-600` `#33409B`. This is the only "loud-ish" color in the product and it is reserved for the single most important action per view.

### 2.3 Semantic colors

Each semantic has a **tint** (bg), **base** (icon/border), and **text** (accessible label on tint).

| Semantic | tint (bg) | base | text |
|---|---|---|---|
| Success | `#E7F6EE` | `#1F9D57` | `#116335` |
| Warning | `#FBF3E2` | `#C9871B` | `#8A5A0B` |
| Danger  | `#FBEAEA` | `#D24141` | `#8E2727` |
| Info    | `#E9F0FB` | `#2F6FD0` | `#1E4A8F` |

### 2.4 Token roles (semantic → primitive mapping)

| Role | Token | Value |
|---|---|---|
| `background` | app canvas | `gray-50` `#F8FAFC` |
| `surface` | cards, table, drawer, top bar | `#FFFFFF` |
| `surface-sunken` | inset areas, code/template blocks | `gray-100` `#F1F5F9` |
| `border` | default | `gray-200` `#E5E9F0` |
| `border-strong` | inputs, emphasized dividers | `gray-300` `#D3DAE6` |
| `text-primary` | body/headings | `gray-800` `#1F2733` |
| `text-secondary` | supporting text | `gray-600` `#4B5563` |
| `text-muted` | meta, placeholder, timestamps | `gray-500` `#6B7688` |
| `text-link` | inline links | `brand-600` `#33409B` |
| `focus-ring` | focus outline | `brand-500` at 35% → `rgba(62,79,184,0.35)` |
| `selection-bg` | selected row / selected text | `brand-50` `#EEF1FB` |

### 2.5 Status badge mappings

All badges use the subtle pattern: **tinted background + darker text + optional 1px border of the same hue at ~15% darker**. No solid loud fills. See §6.7 for badge geometry.

**email_status**

| Value | bg | text | note |
|---|---|---|---|
| verified   | `#E7F6EE` | `#116335` | check-circle icon |
| guessed     | `#FBF3E2` | `#8A5A0B` | help-circle icon |
| unverified | `#F1F5F9` | `#4B5563` | neutral, circle-dashed icon |

**ICP tier** (companies) — tiers get a slightly more saturated, still subtle treatment because they're decision-critical:

| Tier | bg | text | meaning |
|---|---|---|---|
| A | `#E7F6EE` | `#116335` | Ideal fit |
| B | `#E9F0FB` | `#1E4A8F` | Strong fit |
| C | `#FBF3E2` | `#8A5A0B` | Moderate fit |
| D | `#F1F5F9` | `#4B5563` | Low fit |

> The numeric ICP score (0–100) is shown next to the tier as a thin horizontal meter (see §6.13). Meter fill color follows tier text color.

**Signal types** (buying signals) — use `info`-family and neutral tints; keep hue variety low so no single signal reads as "alarm":

| Signal | bg | text | lucide icon |
|---|---|---|---|
| funding          | `#E7F6EE` | `#116335` | `banknote` |
| hiring           | `#E9F0FB` | `#1E4A8F` | `users` |
| expansion        | `#EEF1FB` | `#2A3580` | `trending-up` |
| product_launch   | `#FBF3E2` | `#8A5A0B` | `rocket` |
| leadership_hire  | `#F3EDFB` | `#5B3F9E` | `user-plus` |
| tech_adoption    | `#F1F5F9` | `#4B5563` | `cpu` |
| news_mention     | `#F1F5F9` | `#4B5563` | `newspaper` |

*(The one violet tint `#F3EDFB`/`#5B3F9E` is intentionally rare — used only for leadership_hire — so it stands out without a rainbow of colors.)*

**Engagement statuses** — mapped to a lifecycle. Neutral early, brand/success mid, danger/muted terminal:

| Status | bg | text | dot color |
|---|---|---|---|
| active           | `#E9F0FB` | `#1E4A8F` | `#2F6FD0` |
| replied          | `#EEF1FB` | `#2A3580` | `#33409B` |
| in_conversation  | `#E7F6EE` | `#116335` | `#1F9D57` |
| meeting          | `#E7F6EE` | `#116335` | `#1F9D57` |
| booked           | `#DDF0E4` | `#0B5128` | `#0F7A3D` |
| not_interested   | `#F1F5F9` | `#4B5563` | `#6B7688` |
| needs_human      | `#FBF3E2` | `#8A5A0B` | `#C9871B` |
| bounced          | `#FBEAEA` | `#8E2727` | `#D24141` |
| unsubscribed     | `#FBEAEA` | `#8E2727` | `#D24141` |
| completed        | `#F1F5F9` | `#374151` | `#6B7688` |

Pattern: each engagement badge is a **6px dot + label** (dot uses `dot color`, label uses `text`, background uses `bg`). This gives a consistent "status pill" read across the app.

---

## 3. Typography

**Font family:** **Inter** (variable), with a system fallback. Inter is the correct choice for dense data UIs — excellent at small sizes, tabular figures, tight tracking control.

```
--font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
--font-mono: "JetBrains Mono", "SF Mono", ui-monospace, "Menlo", monospace;
```

**Global rules**
- Enable `font-feature-settings: "cv11", "ss01"; font-variant-numeric: tabular-nums;` on all numeric/table contexts so digits align in columns.
- Default letter-spacing `0`. Headings ≥ 24px use `-0.01em` (`-0.02em` for display). ALL-CAPS labels use `+0.04em`.
- Base body size **14px** (this is a dense B2B app, not a marketing site).
- Antialiasing: `-webkit-font-smoothing: antialiased`.

### Type scale

| Token | Size / Line-height | Weight | Tracking | Usage |
|---|---|---|---|---|
| `display`   | 30px / 36px | 700 | -0.02em | Page hero numbers, analytics headline stat |
| `h1`        | 24px / 32px | 650 | -0.01em | Page title (e.g., "People") |
| `h2`        | 20px / 28px | 600 | -0.01em | Section headers, drawer name |
| `h3`        | 16px / 24px | 600 | 0 | Card titles, sub-section |
| `h4`        | 14px / 20px | 600 | 0 | Group labels, small card titles |
| `body`      | 14px / 22px | 400 | 0 | Default paragraph / description text |
| `body-strong` | 14px / 22px | 550 | 0 | Emphasized body, primary cell text |
| `small`     | 13px / 18px | 400 | 0 | Secondary meta, helper text |
| `caption`   | 12px / 16px | 400 | 0 | Timestamps, footnotes |
| `table-cell`| 13px / 18px | 400 | 0 | Data table body cells |
| `table-cell-strong` | 13px / 18px | 550 | 0 | First/name column in tables |
| `label`     | 12px / 16px | 600 | +0.04em, UPPERCASE | Field labels, column-group labels, badge text uses 11px |
| `badge`     | 11px / 14px | 550 | +0.01em | Badge/pill text |
| `button`    | 13px / 16px | 550 | 0 | Button labels (14px for large buttons) |

> Weights: use 400 / 550 / 600 / 650 / 700. (Inter variable supports arbitrary weights; 550 and 650 give a refined "medium/semibold-minus" that reads more premium than default 500/700.)

---

## 4. Spacing / Radius / Shadows / Borders

### 4.1 Spacing scale (4px base)

| Token | px |
|---|---|
| `space-0` | 0 |
| `space-0.5` | 2 |
| `space-1` | 4 |
| `space-2` | 8 |
| `space-3` | 12 |
| `space-4` | 16 |
| `space-5` | 20 |
| `space-6` | 24 |
| `space-8` | 32 |
| `space-10` | 40 |
| `space-12` | 48 |
| `space-16` | 64 |

Common paddings: card `space-5` (20px), drawer `space-6` (24px), table cell horizontal `space-4` (16px), between form fields `space-4` (16px), page gutter `space-8` (32px).

### 4.2 Border radius (restrained — 8px max on cards)

| Token | px | Usage |
|---|---|---|
| `radius-xs` | 4 | Badges, chips, small inputs, checkboxes |
| `radius-sm` | 6 | Buttons, inputs, dropdown menus, avatars(square-ish rounded) |
| `radius-md` | 8 | Cards, drawer, modal, KPI tiles, sequence-step cards |
| `radius-full` | 9999 | Status dots, avatar circles, toggle knobs |

Never exceed 8px for structural containers. No "pill everything" look. Avatars are circular (`radius-full`); everything else is rectangular-restrained.

### 4.3 Shadows (minimal — this is explicit)

Shadows are used **only** for elements that float above the plane (dropdowns, popovers, drawer, modal, sticky bars on scroll). Flat surfaces (cards, table) use **borders, not shadows**.

| Token | Value | Usage |
|---|---|---|
| `shadow-none` | none | Cards, table, tiles at rest (use `border` instead) |
| `shadow-xs` | `0 1px 2px rgba(15,20,32,0.04)` | Optional hairline lift on hoverable cards |
| `shadow-sm` | `0 2px 6px rgba(15,20,32,0.06)` | Dropdowns, tooltips, filter menus |
| `shadow-md` | `0 8px 24px rgba(15,20,32,0.10)` | Right detail drawer, popovers |
| `shadow-lg` | `0 16px 48px rgba(15,20,32,0.14)` | Center modals, command palette |

No colored shadows. No `0 0 blur` glows anywhere.

### 4.4 Borders

- Default border: **1px solid `gray-200` `#E5E9F0`**.
- Input / emphasized border: **1px solid `gray-300` `#D3DAE6`**.
- Table gridlines: **1px `gray-200`**, horizontal only by default (no vertical gridlines — vertical alignment carries the grid).
- Focus: **2px** outline in `focus-ring` `rgba(62,79,184,0.35)` + inner 1px `brand-600` border, `outline-offset: 1px`.
- Dividers inside cards: 1px `gray-200`, full-bleed or inset by card padding depending on context.

---

## 5. Layout — App Shell

```
┌──────────────┬──────────────────────────────────────────────────────────┐
│              │  TOP BAR  (h 56px, sticky, bg #FFFFFF, border-bottom)      │
│   SIDEBAR    ├──────────────────────────────────────────────────────────┤
│   240px      │                                                            │
│   fixed      │   MAIN CONTENT  (bg gray-50, padding 32px, max 1440px)     │
│   bg #FFFFFF │                                                            │
│   border-    │   ┌── optional right DETAIL DRAWER: 480px, overlays ──┐    │
│   right      │   │    from right edge, shadow-md                     │    │
│              │   └───────────────────────────────────────────────────┘    │
└──────────────┴──────────────────────────────────────────────────────────┘
```

### 5.1 Left sidebar — **240px fixed width** (collapsible to 64px icon-rail)

- Background `#FFFFFF`, `border-right: 1px solid gray-200`. Full height, fixed.
- Top: **workspace switcher** row (h 56px, aligns with top bar). Vector wordmark/logo left (20px mark + "Vector" in `h4` weight 650), chevron for org switch on the right.
- Nav is grouped into sections with `label`-style section headers (12px uppercase, `gray-500`, 12px letter-spacing +0.04em, padding `12px 16px 4px`).
- Bottom pinned: **Settings**, **Help**, and a **user chip** (avatar + name + role, 12px muted).
- Nav vertical rhythm: each item 36px tall, 8px gap between items, 16px section gap.

**Sidebar sections & items**

```
WORKSPACE ▸ (switcher)

  ── OVERVIEW
  ▸ Dashboard        (layout-dashboard)
  ▸ Analytics        (bar-chart-3)

  ── DATA
  ▸ People           (users)          [count badge]
  ▸ Companies        (building-2)      [count badge]
  ▸ Lists            (bookmark)

  ── OUTREACH (Pulse)
  ▸ Sequences        (git-branch)      [count badge]
  ▸ Inbox            (inbox)           [unread dot]
  ▸ Signals          (radar)

  ── (pinned bottom)
  ▸ Settings         (settings)
  ▸ Help & docs      (life-buoy)
  ▸ [User chip]
```

### 5.2 Top bar — **56px height**, sticky, `#FFFFFF`, `border-bottom: 1px gray-200`

Left → right:
1. **Global search** — 380px wide search field (see §6.4), `⌘K` hint chip on the right inside the field. Expands to command palette on focus.
2. **Contextual filter bar** — when on a list page, filter chips render here or directly under the page title (see per-page). 
3. Right cluster: **"+ New"** primary-ish split button (create person/company/sequence), **notifications** bell (`bell`), **user avatar** menu.

Top bar has no shadow at rest; on content scroll it keeps only the border (no shadow) to stay flat.

### 5.3 Main content

- Background `gray-50`. Horizontal padding **32px**, top padding **24px**. Content max-width **1440px**, centered when viewport is wider.
- Standard page header block: `h1` title + count/subtitle on the left, primary action + view controls on the right; 16px below it the filter/search row; then the content (table/cards).

### 5.4 Right detail drawer — **480px** (wide variant 560px for sequences)

Overlays content from the right, `#FFFFFF`, `shadow-md`, 1px left border. Scrim behind at `rgba(15,20,32,0.20)`. Closes on Esc / scrim click / X. Does not push content (overlay, not split) — keeps list context intact.

### 5.5 Responsive

- ≥ 1280px: full 240px sidebar.
- 1024–1280px: sidebar auto-collapses to 64px icon rail (label on hover tooltip).
- < 1024px: sidebar becomes an overlay drawer triggered by a hamburger; tables become horizontally scrollable with the first (name) column pinned.

---

## 6. Component Specs

State order everywhere: **default → hover → active/pressed → focus → disabled**.

### 6.1 Sidebar nav item

- Size: full width minus 8px side margin, height **36px**, padding `8px 12px`, `radius-sm`, icon (16px) + 10px gap + label (`13px / 550`).
- **default:** transparent bg, icon `gray-500`, label `gray-700`.
- **hover:** bg `gray-100`, icon `gray-700`, label `gray-900`.
- **active (current route):** bg `brand-50` `#EEF1FB`, label `brand-700`, icon `brand-600`, **plus a 3px `brand-600` left indicator bar** (inset, rounded 2px) OR left-edge indicator. Font weight 600.
- **focus:** focus ring.
- Count badge (right-aligned): 20px min-width, 16px tall, `gray-100` bg, `gray-600` text, 11px, `radius-full`. On active item badge bg becomes `brand-100`.

### 6.2 Buttons

Height tiers: **sm 28px**, **md 32px (default)**, **lg 40px**. Horizontal padding md = 12px (14px if icon+label). Radius `radius-sm` (6px). Label `button` type (13px/550). Icon 16px, 6px gap. Focus ring on all.

**Primary**
- default: bg `brand-600` `#33409B`, text `#FFFFFF`, no border.
- hover: bg `brand-700` `#2A3580`.
- active: bg `brand-800` `#212A66`.
- disabled: bg `gray-200`, text `gray-400`, no pointer.

**Secondary (default/outline)**
- default: bg `#FFFFFF`, text `gray-700`, `border 1px gray-300`.
- hover: bg `gray-50`, border `gray-400`, text `gray-900`.
- active: bg `gray-100`.
- disabled: bg `#FFFFFF`, text `gray-400`, border `gray-200`.

**Ghost / tertiary**
- default: transparent, text `gray-600`, no border.
- hover: bg `gray-100`, text `gray-900`.
- active: bg `gray-200`.
- Used for icon buttons (32px square, icon 16px, centered) and low-priority row actions.

**Danger** (destructive confirm only)
- default: bg `#FFFFFF`, text `#8E2727`, border 1px `#E7B4B4`. Hover: bg `#FBEAEA`. Solid danger (bg `#D24141`, white text) reserved for the final destructive action inside a confirmation modal.

**Split button** ("+ New ▾"): primary segment + 1px divider + chevron segment opening a menu.

### 6.3 Input field

- Height **32px** (md), `radius-sm`, `border 1px gray-300`, bg `#FFFFFF`, padding `0 12px`, text 13px `gray-800`, placeholder `gray-400`.
- Optional leading icon (16px, `gray-400`) with 8px gap; text shifts right.
- hover: border `gray-400`.
- focus: border `brand-600` + focus ring (2px `rgba(62,79,184,0.35)`), no shadow.
- error: border `#D24141`, helper text `#8E2727` 12px below.
- disabled: bg `gray-100`, text `gray-400`, border `gray-200`.
- Label above: `label` type (12px uppercase 600 `gray-600`), 6px gap. Helper/caption below: 12px `gray-500`.

### 6.4 Search field (global + list)

- Global: 380px wide, 36px tall in top bar, leading `search` icon `gray-400`, placeholder "Search people, companies, sequences…", trailing `⌘K` kbd chip (11px, `gray-500`, bg `gray-100`, `radius-xs`, padding `2px 6px`).
- List-scoped search: 280px, 32px tall, same styling, placeholder "Search this list…", clears with trailing `x` when populated.
- Focus behavior: global search opens command palette (centered modal 640px, `shadow-lg`) with grouped results (People / Companies / Sequences / Actions), arrow-key nav, `↵` to open.

### 6.5 Filter chip & dropdown

**Filter chip (add-filter trigger + applied filters)**
- Applied filter chip: height 28px, `radius-sm`, bg `gray-100`, border 1px `gray-200`, padding `0 8px 0 10px`. Format: `Label: value ×`. Label `gray-500` 12px, value `gray-800` 12px/550, trailing `x` icon 14px `gray-400` (hover `gray-700`). When a filter is active/populated, border becomes `brand-200` and bg `brand-50`.
- "+ Add filter" chip: dashed 1px `gray-300` border, `plus` icon + "Filter", ghost feel; opens filter menu.

**Filter dropdown menu**
- `shadow-sm`, `radius-md`, bg `#FFFFFF`, border 1px `gray-200`, min-width 240px, padding 4px.
- Header: field search input. Body: checkbox list (multi-select) or radio (single). Item height 32px, hover bg `gray-100`. Footer: "Clear" (ghost) + "Apply" (primary sm), 1px top border.
- Supports operators for some fields (is / is not / contains / is empty) via a small select at top.

### 6.6 Data table (the core component)

**Geometry**
- Surface: `#FFFFFF`, `radius-md`, `border 1px gray-200`, `shadow-none`. Rounded corners clip header/rows.
- **Row height: 44px** (comfortable-dense default). Compact mode toggle → 36px. Cell horizontal padding **16px** (12px in compact).
- Horizontal gridlines only: 1px `gray-200` between rows. No vertical lines.
- Column min-widths defined per column; text truncates with ellipsis + tooltip on overflow.

**Header row**
- Height 40px, bg `gray-50`, `label`-ish text: 12px, weight 600, `gray-500`, letter-spacing +0.02em (Title Case, not shouty caps — use Title Case here for readability; reserve full caps for section labels). `border-bottom: 1px gray-200`.
- **Sticky** on vertical scroll (position sticky, top = top bar height). When stuck, apply `shadow-xs` bottom edge only.
- Sortable columns: hover shows `chevrons-up-down` icon `gray-400`; active sort shows `arrow-up`/`arrow-down` in `gray-700`.

**Cells**
- text-primary cells `gray-800` 13px; first/name column `table-cell-strong` (550) with avatar (24px) + 10px gap, name on top line, secondary (title/domain) 12px `gray-500` below on two-line cells.
- Badges rendered inline per §6.7. Numeric columns right-aligned, tabular figures.

**Row states**
- default: bg `#FFFFFF`.
- hover: bg `gray-50`; row-action buttons (ghost icon buttons) fade in on the right; a `⋯` overflow menu appears.
- selected: bg `brand-50` `#EEF1FB`, left 2px `brand-600` accent optional; checkbox checked.
- focused (keyboard): 2px inset focus ring.

**Selection & bulk bar**
- Leading checkbox column (44px wide). Header checkbox = select-all (indeterminate state supported).
- When ≥1 row selected, a **bulk action bar** slides up anchored to the bottom of the table area (or replaces the header row): "N selected" + actions (Add to sequence, Add to list, Export, Delete) + "Clear". Bar bg `gray-900` `#0F1420`, white text? — **No**, keep it light: bg `#FFFFFF`, `shadow-md`, border 1px `gray-200`, `radius-md`, floating 16px above bottom, centered over content. Actions are secondary/ghost buttons.

**Pagination**
- Footer bar 48px, `border-top 1px gray-200`, bg `#FFFFFF`. Left: "Showing 1–50 of 2,431" (13px `gray-500`). Right: rows-per-page select (25/50/100) + prev/next chevron buttons (ghost icon) + page number. Prefer cursor pagination; infinite scroll acceptable for People/Companies with a sticky "Load more" fallback.

**Column controls**
- A `sliders-horizontal` "Columns" button opens a menu to show/hide/reorder columns (drag handles). Persisted per view.

### 6.7 Badge / pill

- Geometry: height **20px**, `radius-xs` (4px), padding `0 8px`, text `badge` (11px/550), inline-flex, 4px gap for icon/dot.
- Fill = semantic `tint` bg + `text` color. Optional 1px inner border at hue -10% for definition (subtle). No solid saturated fills, no shadows.
- Variants: **dot-badge** (6px `radius-full` dot + label, used for engagement statuses), **icon-badge** (12px lucide leading icon, used for signals & email_status), **plain** (text only, used for tiers with adjacent meter).
- Count badge variant: neutral `gray-100`/`gray-600`, `radius-full`, min-width 20px, for nav & tab counts.

### 6.8 Avatar (initials-based — NO photos)

- Shape: circle `radius-full`. Sizes: **xs 20px, sm 24px, md 32px, lg 40px, xl 56px** (drawer header).
- Content: 1–2 uppercase initials, Inter 550, centered. Text 40% of avatar size.
- **Color:** deterministic from a fixed 8-swatch muted palette hashed by name — each swatch is a tint bg + darker text (never white-on-saturated). Palette:
  | # | bg | text |
  |---|---|---|
  | 1 | `#E9F0FB` | `#1E4A8F` |
  | 2 | `#E7F6EE` | `#116335` |
  | 3 | `#FBF3E2` | `#8A5A0B` |
  | 4 | `#F3EDFB` | `#5B3F9E` |
  | 5 | `#EEF1FB` | `#2A3580` |
  | 6 | `#FBEAEA` | `#8E2727` |
  | 7 | `#F1F5F9` | `#374151` |
  | 8 | `#E3F1F1` | `#0E5C5C` |
- Company avatars: same system but **rounded-square** (`radius-sm`, 6px) to distinguish companies from people at a glance; use company initial(s) or favicon if available (favicon rendered inside the rounded square with 4px inset).
- Avatar group (stacked): -8px overlap, 2px white ring per avatar, "+N" trailing chip.

### 6.9 Tabs

- Underline style. Tab item: 36px tall, padding `0 4px` with 20px gap between tabs, text 13px `gray-500` (550). 
- active: text `gray-900`, **2px `brand-600` underline** flush to the bottom border of the tab strip (which is a 1px `gray-200` full-width line).
- hover: text `gray-800`.
- Optional trailing count badge (neutral). Focus ring on tab.
- Used in Person/Company/Sequence detail. Secondary "segmented control" variant (for table view toggles like Table/Board): pill group, 28px, bg `gray-100`, active segment bg `#FFFFFF` + `shadow-xs` + text `gray-900`.

### 6.10 Right detail drawer / panel

- Width 480px (560px sequences), `#FFFFFF`, `shadow-md`, left border 1px `gray-200`, slides in 180ms ease-out.
- **Header** (sticky, 72px): xl avatar (56) or 40px + name (`h2`), subtitle (title @ company / domain) `gray-500`, primary status badge. Right: quick actions (icon buttons: open-full `maximize-2`, more `⋯`, close `x`).
- **Action row** below header: primary button ("Add to sequence" / "Message") + secondary ("Edit") + ghost icons (email, linkedin, copy).
- **Tabs**: Overview / Activity / Emails / Notes.
- **Body:** scrollable, 24px padding. Uses **key-value rows**: label (`label` 12px uppercase `gray-500`) left at fixed 120px, value right (`gray-800` 13px). Sections separated by 1px `gray-200` dividers with `h4` group titles.
- **Footer** (optional sticky): contextual, e.g., pagination "‹ Prev / Next ›" to move through the list without closing.

### 6.11 Cards

- `#FFFFFF`, `radius-md` (8px), `border 1px gray-200`, `shadow-none`, padding `20px`.
- Header: `h3`/`h4` title left, optional action (ghost/secondary sm) right, optional `border-bottom` divider before body.
- Hover (only if the whole card is clickable): border `gray-300` + `shadow-xs`, cursor pointer.
- Never nest more than one card level; use dividers inside instead of nested cards.

### 6.12 Empty states

- Centered within the content region, max-width 420px, 48px vertical padding.
- Composition: 40px lucide icon in a 64px `gray-100` rounded-square container (`radius-md`, icon `gray-400`) → `h3` title `gray-800` → `body` description `gray-500` → primary CTA. No illustrations that feel "playful"; keep it geometric and calm.
- Distinct copy for: no data yet (onboarding CTA), no results (filter/search — offer "Clear filters"), error (retry), loading (skeleton rows, not spinners, for tables — 6–8 shimmer rows using `gray-100`/`gray-50`).

### 6.13 Tooltip

- bg `gray-900` `#0F1420`, text `#FFFFFF` 12px, `radius-xs` (4px)... — **exception to flat**: tooltips use `shadow-sm`. Padding `6px 8px`, max-width 260px, 8px offset from anchor, small caret. Delay 300ms in, 0 out. Used for truncated text, icon-only buttons, badge definitions.

### 6.14 KPI / stat tile

- Card geometry (§6.11) but padding `16px 20px`, `radius-md`. In a responsive grid (4 across ≥1200px, 2 across tablet).
- Content: `label` (12px uppercase `gray-500`) → value `display`(30px/700 `gray-900`, tabular) → delta row: small badge with `arrow-up`/`arrow-down` (success `#116335` for good, danger `#8E2727` for bad) + "vs last 30d" `gray-500` 12px.
- Optional 40px-tall inline sparkline (stroke `brand-600` 1.5px, no fill, or fill `brand-50`). No gridlines on sparkline.

### 6.15 Activity timeline item

- Left rail: 24px column with a 8px status dot (semantic color) and a 1px `gray-200` connector line running through the column between items.
- Content: `body-strong` action title (e.g., "Email opened") + inline actor/target links (`brand-600`), then `small` `gray-500` detail line, then `caption` timestamp `gray-400` (relative: "2h ago", absolute on hover tooltip).
- Icon chip option: 24px `gray-100` rounded circle with 14px lucide icon (mail-open, reply, calendar-check, user-plus, etc.) instead of a bare dot for richer events.
- Grouped by day with a sticky `label` day header ("Today", "Yesterday", "Jul 18").

### 6.16 Sequence-step card

Shared frame: `#FFFFFF`, `radius-md`, `border 1px gray-200`, padding `16px 20px`. Steps connected vertically by a 1px `gray-200` line with a **wait-badge** node between cards (`clock` icon + "Wait 2 days", neutral badge centered on the connector). Left edge of each card has a 32px step index circle (`gray-100` bg, `gray-700` number, `radius-full`).

**Email step card**
```
┌───────────────────────────────────────────────────────────┐
│ (1)  ✉  Email · Step 1        [Angle: Pain-point]   ⋯ edit  │
│      ─────────────────────────────────────────────────────  │
│      Variant A  ● live   |   Variant B  ● live               │  ← A/B tabs (segmented)
│      Subject:  "Cutting {{company}}'s ramp time in half"     │
│      ┌ body preview (surface-sunken, 3 lines, mono-ish) ──┐  │
│      │ Hi {{first_name}}, noticed {{company}} just …      │  │
│      └────────────────────────────────────────────────────┘  │
│      Reply rate 8.4%  ·  Open 61%  ·  Sent 1,204            │  ← stats row
└───────────────────────────────────────────────────────────┘
```
- Header: channel icon (`mail`) + "Email · Step N" (`h4`) + angle badge (neutral/info) + right actions (edit `pencil`, duplicate, delete, drag handle `grip-vertical`).
- Stats row: inline metric chips, values in `gray-800` 13px 550, labels `gray-500` 12px. Reply rate is the hero metric (slightly larger).

**LinkedIn step card**
```
┌───────────────────────────────────────────────────────────┐
│ (2)  in  LinkedIn · Connection Invite         ⋯ edit        │
│      ─────────────────────────────────────────────────────  │
│      Flow:  Invite ─▸ Accept ─▸ Message                      │  ← stage chips
│      Message: "Hi {{first_name}}, saw {{company}}'s …"       │
│      Acceptance 42%  ·  Reply 12%                            │
└───────────────────────────────────────────────────────────┘
```
- Channel icon uses LinkedIn `in` mark (monochrome `gray-600`, not brand blue) to stay on-system.
- Flow chips: small neutral pills connected by `arrow-right` (14px `gray-400`), the current/edited stage highlighted with `brand-50` bg.
- No wait-badge before an "Accept" stage (it's event-driven) — instead show "Waits for acceptance" caption.

### 6.17 Variant / A-B card

- Presented as a **segmented control** at top of the email step (Variant A / B / + Add variant) with a live/paused dot per variant.
- Each variant panel: Subject input, Body editor (see below), and a compact stats strip. A subtle **"winner" tag** (success badge "Leading +2.1pp") appears on the higher reply-rate variant once statistically meaningful (≥ threshold sends).
- Body editor: `surface-sunken` bg, mono-leaning 13px, merge-tags `{{first_name}}` rendered as inline chips (`brand-50` bg, `brand-700` text, `radius-xs`, non-editable atoms). Toolbar: bold/italic/link/merge-tag/preview toggle.

---

## 7. Page-by-page Wireframes

### (a) People list

```
┌─ SIDEBAR ─┬────────────────────────────────────────────────────────────────┐
│           │ TOPBAR: [🔎 Search people, companies…  ⌘K]        + New ▾  🔔 (A)│
│ People •  ├────────────────────────────────────────────────────────────────┤
│ Companies │  People                                          [ Import ] [+ Add]│
│ …         │  2,431 contacts                                                   │
│           │                                                                   │
│           │  [🔎 Search this list] [+ Filter] Role:Founder×  Email:Verified× │  ← filter bar
│           │                                        [Columns ▾] [Compact] [⇧] │
│           │  ┌──────────────────────────────────────────────────────────────┐│
│           │  │☐│ Name              │ Title / Role   │ Company   │ Email    │…││ header (sticky)
│           │  ├──────────────────────────────────────────────────────────────┤│
│           │  │☐│(av) Jane Doe      │ CEO · Founder  │ Acme (sq)│ ✓verified│…││ row 44px
│           │  │  │     jane@…       │                │          │          │  ││
│           │  │☐│(av) Sam Ford      │ Head of AI     │ Nyx      │ ?guessed │…││
│           │  │ … more rows …                                                 ││
│           │  └──────────────────────────────────────────────────────────────┘│
│           │  Showing 1–50 of 2,431        [25|50|100]  ‹  1  ›                │
└───────────┴────────────────────────────────────────────────────────────────┘
```
Columns (default): checkbox · Name (avatar+name+email 2-line) · Title/Role (title + role-category badge) · Company (rounded-sq avatar + name, links to company) · Email status badge · Engagement status (dot-badge) · Sequence stage · Location · ⋯. Row click → opens Person detail **drawer**; name click / ⌘-click → full page.

### (b) Companies list

```
│  Companies                                            [ Import ] [+ Add]     │
│  318 companies                                                               │
│  [🔎 Search] [+ Filter] Tier:A×  Signal:Funding×  ICP≥80×    [Columns ▾]     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │☐│ Company            │ ICP        │ Tier │ Signal        │ Contacts │ … │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │☐│(sq) Acme Robotics  │ 92 ▓▓▓▓▓░  │  A   │ 💰 Funding    │ (av av+3)│ … │ │
│  │  │     acme.com       │            │      │ 4d ago        │          │   │ │
│  │☐│(sq) Nyx Labs       │ 74 ▓▓▓▓░░  │  B   │ 👥 Hiring     │ (av av)  │ … │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
```
ICP column = number + thin meter (§6.13). Tier plain badge. Signal = icon-badge + freshness caption. Contacts = avatar group. Row → Company detail drawer.

### (c) Person detail (drawer or full page — same content, wider gutters when full)

```
┌ DRAWER 480px ───────────────────────────────────────────┐
│ (56 av) Jane Doe                              ⤢  ⋯   ✕   │  header
│         CEO · Founder @ Acme Robotics                    │
│         ● in_conversation                                │
│ ───────────────────────────────────────────────────────  │
│ [ Add to sequence ]  [ Edit ]   ✉  in  ⧉                 │  action row
│ ───────────────────────────────────────────────────────  │
│ Overview | Activity | Emails | Notes                     │  tabs
│ ───────────────────────────────────────────────────────  │
│ CONTACT                                                  │
│   Email      jane@acme.com   ✓ verified   ⧉              │  key-value rows
│   LinkedIn   /in/janedoe                    ↗            │
│   Location   San Francisco, US                           │
│ COMPANY                                                  │
│   Acme Robotics (sq)  ·  ICP 92 · Tier A     ↗           │
│   Signal   💰 Funding · Series B · 4d ago                │
│ SEQUENCE                                                 │
│   Pulse · "Founders Q3"  — Step 2 of 5                   │
│   Next: Email in 1 day                                   │
│ ───────────────────────────────────────────────────────  │
│ RECENT ACTIVITY (timeline)                               │
│   ● Replied to Step 1 · 2h ago                           │
│   ● Email opened · 5h ago                                │
│                                        ‹ Prev  Next ›     │  footer
└──────────────────────────────────────────────────────────┘
```

### (d) Company detail

```
│ (56 sq) Acme Robotics                          ⤢  ⋯  ✕  │
│         acme.com  ·  ICP 92 ▓▓▓▓▓░  ·  Tier A            │
│         💰 Funding · Series B · 4 days ago               │
│ [ Find contacts ] [ Add to list ]   ↗ site  in  ⧉       │
│ Overview | Signals | People | Notes                     │
│ ─────────────────────────────────────────────────────    │
│ FIRMOGRAPHICS                                            │
│   Website / HQ / Employees / Industry / Founded          │
│ BUYING SIGNALS (timeline)                                │
│   ● Series B raised $40M ......... 4d ago                │
│   ● 12 eng roles opened .......... 2w ago                │
│ DECISION MAKERS                                          │
│   (av) Jane Doe — CEO · Founder      [Add to seq]        │  mini person rows
│   (av) Sam Ford — Head of AI         [Add to seq]        │
```

### (e) Sequence detail / builder (Pulse) — 560px drawer or full page

```
│  ‹ Sequences   Founders Q3            ● Active   [ Edit ] [ ▸ Enroll ] ⋯     │
│  Multi-channel · 5 steps · 1,204 enrolled                                    │
│  Overview | Steps | Enrolled | Analytics | Settings                          │  tabs
│ ────────────────────────────────────────────────────────────────────────    │
│  STEPS (builder canvas, vertical)                                            │
│                                                                              │
│    ┌ (1) ✉ Email · Step 1   [Angle: Pain-point]           edit ⋯ ⋮ ┐        │
│    │     [Variant A ●live][Variant B ●live][+]                       │        │
│    │     Subject: "Cutting {{company}}'s ramp time…"                 │        │
│    │     ┌ body preview (sunken) ──────────────────────────────┐    │        │
│    │     └───────────────────────────────────────────────────────┘    │      │
│    │     Reply 8.4% · Open 61% · Sent 1,204                          │        │
│    └──────────────────────────────────────────────────────────────────┘      │
│              │   ⏱ Wait 2 days                                                │
│    ┌ (2) in LinkedIn · Connection Invite                    edit ⋯ ┐         │
│    │     Invite ─▸ Accept ─▸ Message                                 │        │
│    │     Message: "Hi {{first_name}}, saw {{company}}'s…"            │        │
│    │     Acceptance 42% · Reply 12%                                  │        │
│    └──────────────────────────────────────────────────────────────────┘      │
│              │   ⏱ Wait 3 days                                                │
│    ┌ (3) ✉ Email · Step 3 …                                          ┐        │
│    └──────────────────────────────────────────────────────────────────┘      │
│              [ + Add step ▾ ]   (Email · LinkedIn · Wait · Condition)         │
```
Right rail (full-page mode, 320px) shows live sequence stats: enrolled, active, replied, meetings booked, per-step funnel bars. Editing a step opens an inline expand or a secondary right panel with Subject/Body editor + variant management (§6.16–6.17).

### (f) Analytics dashboard

```
│  Analytics                              [ Last 30 days ▾ ]  [ Export ]        │
│  ┌── KPI ──┐ ┌── KPI ──┐ ┌── KPI ──┐ ┌── KPI ──┐                             │
│  │ Contacted│ │ Replies │ │ Meetings│ │ Reply % │   (4 stat tiles, sparkline)│
│  │  12,480  │ │  1,043  │ │   214   │ │  8.4%   │                             │
│  │ ▲ 12%    │ │ ▲ 5%    │ │ ▲ 9%    │ │ ▲ 0.6pp │                             │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘                          │
│  ┌─ Funnel ─────────────────────────┐ ┌─ Campaign performance ─────────────┐ │
│  │ Enrolled ████████████████ 12,480 │ │ table: Sequence | Sent | Reply% |… │ │
│  │ Opened   ██████████ 7,610         │ │ Founders Q3 | 1,204 | 8.4% | …     │ │
│  │ Replied  ███ 1,043                │ │ CTO Outbound| 980   | 6.1% | …     │ │
│  │ Meeting  █ 214                    │ │ …                                  │ │
│  └───────────────────────────────────┘ └────────────────────────────────────┘│
│  ┌─ Reply rate over time (line) ─────────────────────────────────────────────┐│
│  │  single brand-600 line, gray-200 gridlines, tabular axis                   ││
│  └────────────────────────────────────────────────────────────────────────────┘│
```
Charts: single-series use `brand-600`; multi-series use the muted categorical set from §8. Gridlines `gray-200`, axis text `gray-500` 11px, no chart borders/shadows. Bars use solid semantic/brand fills at full opacity (no gradient), 4px radius on bar tops only.

---

## 8. Iconography

**Library: `lucide-react`.** 1.5px stroke, 16px default in UI (20px in empty-state, 14px in badges/inline). Icon color inherits `currentColor`; default `gray-500`, active/interactive `gray-700`→`gray-900`, brand contexts `brand-600`.

**Navigation**

| Item | Icon |
|---|---|
| Dashboard | `layout-dashboard` |
| Analytics | `bar-chart-3` |
| People | `users` |
| Companies | `building-2` |
| Lists | `bookmark` |
| Sequences | `git-branch` |
| Inbox | `inbox` |
| Signals | `radar` |
| Settings | `settings` |
| Help | `life-buoy` |

**Actions / UI**

| Action | Icon |
|---|---|
| Search | `search` |
| Add / New | `plus` |
| Filter | `list-filter` |
| Sort | `arrow-up` / `arrow-down` / `chevrons-up-down` |
| Columns | `sliders-horizontal` |
| More / overflow | `ellipsis` (⋯) |
| Edit | `pencil` |
| Duplicate | `copy` |
| Delete | `trash-2` |
| Copy value | `copy` |
| External link | `arrow-up-right` / `external-link` |
| Email | `mail` (open: `mail-open`) |
| LinkedIn | `linkedin` |
| Expand to full page | `maximize-2` |
| Close | `x` |
| Drag handle | `grip-vertical` |
| Wait step | `clock` |
| Enroll / play | `play` |
| Pause | `pause` |
| Import | `upload` / `download` for export |
| Notifications | `bell` |
| Success | `check-circle-2` |
| Warning | `alert-triangle` |
| Danger/bounce | `alert-octagon` |
| Info | `info` |
| Verified email | `badge-check` |
| Guessed email | `help-circle` |
| Unverified email | `circle-dashed` |
| Meeting booked | `calendar-check` |
| Reply | `reply` |

**Signal icons** — see §2.5 (`banknote`, `users`, `trending-up`, `rocket`, `user-plus`, `cpu`, `newspaper`).

> Never use emoji as icons in the shipped product (the emoji in these wireframes are placeholders for the lucide glyphs). No custom multicolor icons — monochrome lucide only.

---

## 9. Interaction & Microcopy Notes

**Voice/tone:** Precise, confident, operator-to-operator. Short. No exclamation points, no emoji, no "Oops!" or cutesy filler. Say what happened and what to do next. Sentence case for all UI text except the uppercase `label` token.

**Buttons/labels:** Verb-first, specific — "Add to sequence", "Find contacts", "Enroll 1,204 people", not "Submit"/"OK". Destructive confirmations name the object and count: "Delete 12 contacts? This can't be undone."

**Search:**
- Global (`⌘K`) searches across People, Companies, Sequences, and Actions; results grouped with type labels; recent + suggested when empty. Debounce 150ms. Highlight matched substring in `brand-700`.
- List search filters the current dataset live (debounce 200ms), scoped to visible columns, and combines with active filters (AND). Shows "N results" and a "Clear search" affordance.

**Filters:**
- Additive chips, ANDed by default; multiple values within one field are ORed (e.g., Role: Founder OR CEO). Show operator when relevant (is / is not / contains / is empty / ≥).
- Applied filters persist in the URL (shareable views) and can be "Saved as view". A "Clear all" ghost link appears when ≥1 filter is active.
- Empty result under filters → empty state with the exact filters echoed and a "Clear filters" primary action.

**Loading:** Tables use skeleton rows (shimmer `gray-100`), not spinners. Buttons show inline 14px spinner + disabled during async, label unchanged. Optimistic updates for status changes with toast + undo.

**Toasts:** Bottom-center or bottom-right, `#FFFFFF`, `shadow-md`, `radius-md`, 1px `gray-200`, leading semantic icon, 13px text, optional "Undo" ghost action, auto-dismiss 5s (errors persist until dismissed). Never stack more than 3.

**Empty states copy examples:**
- People (no data): "No contacts yet — import a CSV or let Pulse source decision-makers for your ICP." → [Import CSV] [Source with Pulse]
- People (no results): "No contacts match these filters." → [Clear filters]
- Sequences (no data): "No sequences yet. Build a multi-channel play in Pulse." → [New sequence]
- Error: "Couldn't load contacts. Check your connection and try again." → [Retry]

**Keyboard:** `⌘K` search, `/` focus list search, `j`/`k` row nav, `x` select row, `↵` open drawer, `Esc` close drawer/menu, `⌘↵` submit forms. Document shortcuts in a `?` help sheet.

**Accessibility:** All text ≥ WCAG AA (4.5:1) against its background — the tint/text badge pairs in §2 are chosen to pass. Focus rings always visible on keyboard nav. Status is never conveyed by color alone — always paired with a label, icon, or dot+text. Hit targets ≥ 28px. Respect `prefers-reduced-motion` (disable slide/shimmer, keep instant state changes).

**Motion:** Purposeful and fast. Drawer/panel slide 180ms ease-out; menus/popovers fade+scale(0.98→1) 120ms; hover transitions 100ms; row selection instant. Nothing bounces. No looping/ambient animation.

---

## 10. Token quick-reference (for implementation)

```css
:root {
  /* neutrals */
  --gray-50:#F8FAFC; --gray-100:#F1F5F9; --gray-200:#E5E9F0; --gray-300:#D3DAE6;
  --gray-400:#A6B0C0; --gray-500:#6B7688; --gray-600:#4B5563; --gray-700:#374151;
  --gray-800:#1F2733; --gray-900:#0F1420;
  /* brand */
  --brand-50:#EEF1FB; --brand-100:#DDE3F7; --brand-200:#BCC7EF; --brand-400:#5B6ED0;
  --brand-500:#3E4FB8; --brand-600:#33409B; --brand-700:#2A3580; --brand-800:#212A66;
  /* semantic */
  --success-bg:#E7F6EE; --success:#1F9D57; --success-text:#116335;
  --warning-bg:#FBF3E2; --warning:#C9871B; --warning-text:#8A5A0B;
  --danger-bg:#FBEAEA;  --danger:#D24141;  --danger-text:#8E2727;
  --info-bg:#E9F0FB;    --info:#2F6FD0;    --info-text:#1E4A8F;
  /* roles */
  --background:var(--gray-50); --surface:#FFFFFF; --surface-sunken:var(--gray-100);
  --border:var(--gray-200); --border-strong:var(--gray-300);
  --text-primary:var(--gray-800); --text-secondary:var(--gray-600); --text-muted:var(--gray-500);
  --text-link:var(--brand-600); --focus-ring:rgba(62,79,184,0.35); --selection-bg:var(--brand-50);
  /* radius */
  --radius-xs:4px; --radius-sm:6px; --radius-md:8px; --radius-full:9999px;
  /* shadow */
  --shadow-xs:0 1px 2px rgba(15,20,32,.04);
  --shadow-sm:0 2px 6px rgba(15,20,32,.06);
  --shadow-md:0 8px 24px rgba(15,20,32,.10);
  --shadow-lg:0 16px 48px rgba(15,20,32,.14);
  /* type */
  --font-sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
}
```

**Categorical chart palette** (multi-series analytics, muted, no gradients):
`#33409B` (brand), `#1F9D57`, `#C9871B`, `#2F6FD0`, `#5B3F9E`, `#0E5C5C`, `#6B7688`, `#D24141`.

---

*End of spec. Implement tokens first, then primitives (button/input/badge/avatar), then the data table, then compose pages. When a decision isn't covered here, default to the most restrained option consistent with §1.*
