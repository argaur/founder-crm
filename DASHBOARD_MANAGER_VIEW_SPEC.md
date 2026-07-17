# Manager View Spec — `landing/dashboard/index.html`

**Scope:** the new manager view only (IMPLEMENTATION_PLAN.md Phase 6, "the screen
Himanshu would actually look at"). This spec is additive — it does not touch the
rep-facing pipeline/contacts/follow-ups pages beyond the nav insertion and the
shared stage-rename work already planned in Phase 6.

**Ground truth correction, read first:** the dashboard does **not** use Tailwind.
It is bespoke CSS built on tokens in `:root` (`--bg`, `--surface`, `--border`,
`--accent: #E8920A`, `--text/-2/-3`) with three fonts (DM Mono for UI chrome,
Cormorant Garamond for large numerals, Outfit for prose) and a signature
"1px-gap grid" card pattern (`gap:1px; background:var(--border)` with
`var(--surface)` cells). Only `landing/index.html` (the marketing page) uses
Tailwind CDN. All class specs below follow the dashboard's actual idiom.
`DESIGN_BRIEF.md` did not exist when this was written — **the implementing agent
must read `DESIGN_BRIEF.md` if it now exists and reconcile token/color choices
with it before building** (this spec's stage colors are derived from the
dashboard's existing badge palette and should survive that reconciliation).

**Canonical stage names** (must match `bot/` copy and the DB enum exactly,
including hyphenation):
`Inquiry`, `Qualified`, `Site Visit`, `Proposal`, `Negotiation`, `Closed-Won`, `Closed-Lost`.
Active stages = the first five. Closed stages = the last two.

---

## 1. Layout

### 1.1 Placement: new `page-manager`, own nav item

**Decision: a new top-level page (`page-manager`), not a toggle inside
`page-pipeline`.** Justification:

- It is a different audience with different auth: `GET /api/team/funnel` is
  manager-only (Phase 5). A toggle inside the rep pipeline would mean the rep
  view has a control that 403s for most users — a dead switch is worse than no
  switch.
- It answers a different question. The rep pipeline is "what do *I* move
  today"; the manager view is "where is the *team's* revenue and who is
  sitting on it". Mixing them dilutes both.
- The `showPage()` architecture makes a new page nearly free: one `<div
  id="page-manager" class="page pg">`, one nav button, one `PAGE_TITLES`
  entry. No `PAGE_PARENT_NAV` entry needed (it has its own nav element).

**Nav:** insert a button between **Pipeline** and **Contacts**:

- `id="nav-manager"`, label **`Team`**, `onclick="showPage('manager')"`.
- Icon: a simple bar-chart SVG (three ascending bars), 13x13, same
  `stroke="currentColor" stroke-width="2"` style as existing icons.
- `PAGE_TITLES` addition: `manager: 'Team Pipeline'` (topbar title).
- **Role gating:** the nav item ships with class `hidden` and is revealed only
  when the authenticated user's role is `manager` (role comes with the signed
  dashboard token / `GET /api/me`-equivalent — however Phase 5/6 wires
  identity). The demo seed user is a manager, so the demo always shows it. If
  a non-manager somehow opens `page-manager`, render the error banner state
  (Section 2.6) with the 403 copy — never a blank page.

### 1.2 Section order (top to bottom, single column)

1. **Stat row** — four tiles (existing `.stat-grid` pattern).
2. **Team funnel** — horizontal stage bars, Inquiry → Negotiation, with a
   closed-stages summary strip beneath.
3. **Rep leaderboard** — table, one row per rep.
4. **Stalled leads** — list rows, one per stalled lead, with actions.

Sections 3 and 4 sit side by side at desktop width inside the existing
`.home-panels` two-column pattern **only if both fit without truncating the
leaderboard columns — they will not** (the leaderboard needs 6 columns), so:
funnel full-width, leaderboard full-width, stalled list full-width, stacked
with 20px vertical rhythm (matching `margin-bottom: 20px` used on
`.stat-grid`). Keep it a boring single column; the content is the design.

Loading state: each section gets a skeleton block (`.skeleton .sk-stat` x4 for
the stat row, `.sk-panel` for funnel, `.sk-row` x4 for leaderboard and stalled
list), same shimmer pattern as `page-home`. Data fetch is a single call to
`GET /api/team/funnel` on first navigation to the page, re-fetched by the
existing topbar Refresh button and the 5-minute auto-refresh cycle.

---

## 2. Content per section

### 2.1 Stat row — exactly four tiles

Reuse `.stat-grid` / `.stat-card` / `.stat-lbl` / `.stat-num` verbatim.

| # | Label (`.stat-lbl`) | Value (`.stat-num`) | Color class | Source |
|---|---|---|---|---|
| 1 | `TOTAL PIPELINE` | `formatINR(totals.pipeline_value)` e.g. `₹4.2 Cr` | default (cream) | sum of `est_deal_value` across the five active stages |
| 2 | `ACTIVE LEADS` | integer, e.g. `23` | `b` (blue) | count of leads in active stages |
| 3 | `CLOSED-WON · THIS MONTH` | `formatINR(...)` with count beneath — see note | `g` (green) | Closed-Won leads with close date in current calendar month |
| 4 | `STALLED LEADS` | integer, e.g. `4` | `a` (accent amber) — turns default cream when `0` | count of stalled list |

Tile 3 note: primary numeral is the won *value*; add a sub-line under the
numeral in `.stat-lbl` styling (mono, `--text-3`): `3 deals` (singular `1 deal`).
This is the only tile with a sub-line.

**`formatINR(n)` helper (new JS, used everywhere money appears):**
`n >= 1e7` → `₹X.X Cr` · `n >= 1e5` → `₹XX L` · else → `₹XX,XXX`
(`toLocaleString('en-IN')`). Never render raw paise/rupee integers.

### 2.2 Team funnel — horizontal bars, five active stages

Not a chart library — pure CSS bars (consistent with the no-framework,
no-bundler constraint). One row per active stage, in pipeline order:

```
INQUIRY       ████████████████████░░░░░░░░  8 leads   ₹62 L
QUALIFIED     ██████████████░░░░░░░░░░░░░░  6 leads   ₹1.1 Cr
SITE VISIT    █████████░░░░░░░░░░░░░░░░░░░  4 leads   ₹88 L
PROPOSAL      ██████░░░░░░░░░░░░░░░░░░░░░░  3 leads   ₹1.6 Cr
NEGOTIATION   ███░░░░░░░░░░░░░░░░░░░░░░░░░  2 leads   ₹75 L
```

Per row: stage label (left, fixed 110px, mono uppercase in that stage's color
— reuse the `.col-title ct-*` treatment), bar (flex-fill), then two
right-aligned figures: **lead count** and **pipeline value** (`formatINR`).

- **Bar width is proportional to lead count** relative to the largest active
  stage (max bar = 100%). Count drives width because a funnel reads as
  volume-narrowing; value is the label so a 2-lead ₹1.6 Cr Proposal stage is
  still legible as the money stage. Minimum rendered width for a non-zero
  stage: 4px. Zero-count stage: no bar, count column shows `0 leads`, value
  `—`, row at 45% opacity.
- Bar fill: the stage's badge background color at full opacity of its `rgba`
  tint is too faint — use the stage color at 0.35 alpha with a 1px left border
  in the solid stage color. Bar track: `var(--surface-2)`.
- Bar height 18px, 7px vertical gap between rows.
- **Closed strip** below the bars, separated by a `--border` top rule: one
  line, mono, small:
  `Closed-Won 5 · ₹2.1 Cr` (in `#4ADE80`) `   ` `Closed-Lost 3 · ₹94 L` (in `#EF4444`),
  both all-time-for-demo (whatever window the API returns — see Section 5).
- No conversion-rate percentages between stages in v1. (Requires cohort
  logic the endpoint won't have on day one; do not fake it from snapshot
  counts.)
- Row click: navigates to `page-pipeline` (the rep board already filters by
  stage columns; deep-filtering the board by stage is out of scope).

Panel header uses the existing `.panel-hd` / `.panel-title` pattern:
title `TEAM FUNNEL`, right side a static mono caption (not a button):
`All reps · live`.

### 2.3 Rep leaderboard — table

Header (existing `.sec-lbl` treatment): `REP LEADERBOARD`.

Table styled like `.cmd-table` (1px `--border`, collapsed, row bottom rules)
plus a header row (mono, 0.56rem, uppercase, `--text-3`, letter-spaced).
Columns, in order:

| Column | Content | Notes |
|---|---|---|
| `#` | rank 1..n | rank by pipeline value desc |
| `REP` | rep first name + 26px initial avatar (reuse `.c-av`) | |
| `ACTIVE LEADS` | integer | active stages only |
| `PIPELINE` | `formatINR` | sum of `est_deal_value`, active stages |
| `CLOSED-WON` | `2 · ₹80 L` (count · value, current month) | `0 · —` when none |
| `STALLED` | integer | amber (`--accent`) when > 0, `--text-3` when 0 |
| `LAST ACTIVITY` | `timeAgo()` of rep's most recent logged interaction | reuse existing `timeAgo` helper |

- **On "avg response time":** deliberately excluded. The `interactions` schema
  (Phase 0) logs capture events with `logged_at` but has no inbound-vs-outbound
  direction, so response time is not derivable without inventing data.
  `LAST ACTIVITY` is the honest proxy. Do not add a response-time column until
  the schema can support it.
- Sort: pipeline value descending, fixed (no interactive column sorting in v1).
- Rank 1 row: left border 2px `var(--accent)` (same affordance as `.fu-item`)
  — one highlight, nothing else.
- Numeric columns right-aligned; `REP` left-aligned.
- Rows are not clickable in v1 (no per-rep drill-down page exists; do not fake
  one).

### 2.4 Stalled leads — action list

Header: `STALLED LEADS` with a mono caption to its right:
`Quiet past their stage threshold · nudges go out automatically`.
(The caption ties the screen to the Phase 4 auto-nudge feature — the pitch is
that the system already acted; this list is oversight, not a to-do inbox.)

Row pattern: reuse `.fu-item` (bordered row, 2px accent left border, hover
lift) with this content layout:

```
Zomato — Rohan Verma                    [Proposal] 5d quiet   Priya
200 seats · Gurgaon · ₹1.4 Cr                    [View] [Nudge rep]
```

Per row, precisely:
- Line 1 left: **company** (mono, `--text`, 0.7rem) ` — ` contact name (mono,
  `--text-3`).
- Line 1 right: stage badge (Section 3 colors) · `Nd quiet` (mono, `--text-3`)
  · assigned rep first name (mono, `--text-2`).
- Line 2 left: `` `${seat_count} seats · ${city} · ${formatINR(est_deal_value)}` ``
  — seat count uses coworking phrasing: if `space_type` is `managed_office`,
  render `200 seats · managed office · Gurgaon · ₹1.4 Cr`; if seat_count is
  null render `seats TBC`.
- Line 2 right: two actions (`.note-btn` styling):
  - **`View`** — opens the lead's detail page (`openContactDetail`-equivalent
    for the lead). Primary, always present.
  - **`Nudge rep`** — sends the assigned rep the same Telegram nudge Phase 4
    sends automatically, now. **Dependency:** needs a
    `POST /api/leads/{id}/nudge` endpoint that is *not* in the Phase 5 list —
    the implementing agent must either get it added to Phase 5 scope or ship
    the button in a disabled state with tooltip text (Section 4). Do not fake
    a success toast without a real call. On success: button text flips to
    `Nudged` (mono, green `#4ADE80`), disabled, for the remainder of the page
    session.
- No reassign action in v1 — reassignment is a Phase 3 *stretch* bot feature;
  the dashboard must not offer a control the backend may not have. Leave it
  out entirely rather than disabled.
- Sort: `days_stalled` descending (worst first). Cap display at 10 rows with a
  mono footer link `Show all N stalled leads` that expands in place (same
  toggle pattern as `toggleClosed()`).

### 2.5 Empty states (per section, all must exist)

Reuse `.panel-empty` (inline, mono, centered) unless noted:

| Section | Condition | Copy |
|---|---|---|
| Whole page | API returns zero leads team-wide | Full `.empty-state` block — title (serif): `Nothing in the pipeline yet.` · sub: `Team leads will appear here as reps forward conversations to the bot.` |
| Funnel | all active stages zero but closed deals exist | bars render at zero-state opacity; closed strip still shows |
| Leaderboard | no reps registered | `No reps on the team yet. Reps appear after their first /start.` |
| Stalled list | zero stalled | `.empty-state` with the check icon (reuse follow-ups page icon) — title: `Nothing stalled.` · sub: `Every active lead has been touched inside its stage threshold. The bot will nudge reps if that changes.` |

### 2.6 Error states

- Fetch failure: reuse `.err-banner` at top of `page-manager`:
  `Could not load team data: {message}` — all section skeletons hidden.
- 403 (non-manager token): `.err-banner`:
  `This view is for managers. Ask your admin for a manager dashboard link.`

---

## 3. Visual language

Follow the dashboard's existing idiom (see correction at top — CSS tokens, not
Tailwind). Concretely:

### 3.1 Stat tiles
Reuse existing classes unchanged: `.stat-grid` (4-up, 1px-gap grid),
`.stat-card`, `.stat-lbl` (mono 0.58rem uppercase `--text-3`), `.stat-num`
(serif 2.4rem) with existing color modifiers `.g` `#4ADE80`, `.a`
`var(--accent)`, `.b` `#60A5FA`. Nothing new required.

### 3.2 Stage badge colors — all 7 new stages
Extend the existing `.badge` base (mono 0.58rem, 2px/6px padding, 1px border,
10%-alpha background, 20%-alpha border). New classes, replacing `bs-lead`/
`bs-eval`/`bs-prop`/`bs-neg`/`bs-won`/`bs-lost` app-wide as part of the Phase 6
stage rename:

| Stage | Class | Color | Rationale |
|---|---|---|---|
| Inquiry | `.bs-inq` | `#9CA3AF` gray | entry noise, lowest signal (was Lead's color) |
| Qualified | `.bs-qual` | `#A78BFA` violet | (was Evaluating's color) |
| Site Visit | `.bs-visit` | `#2DD4BF` teal | **new color** — the physically-distinct step; teal is unused elsewhere in the palette and reads "in the world, not in a doc" |
| Proposal | `.bs-prop` | `#60A5FA` blue | paper stage (keeps Proposal Sent's color) |
| Negotiation | `.bs-neg` | `var(--accent)` `#E8920A` amber | heat, matches accent (was Negotiating's) |
| Closed-Won | `.bs-won` | `#4ADE80` green | unchanged |
| Closed-Lost | `.bs-lost` | `#EF4444` red | unchanged |

Pattern for each: `color: <hex>; background: rgba(<rgb>,0.10);
border-color: rgba(<rgb>,0.20);`. Matching funnel-label classes `ct-inq` …
`ct-lost` (solid color, no background) mirror the existing `.ct-*` set.
These seven mappings are the single source of stage color for the whole
dashboard — the rep pipeline board picks up the same classes during its
rename; do not maintain two palettes.

### 3.3 Funnel bars (new CSS, ~20 lines)
`.funnel-row` flex, 7px bottom margin. `.funnel-lbl` = `.col-title` treatment,
110px fixed. `.funnel-track` flex-1, height 18px, `background:
var(--surface-2); border: 1px solid var(--border)`. `.funnel-fill` height
100%, `background: rgba(<stage rgb>, 0.35); border-left: 2px solid <stage
hex>; transition: width 0.4s`. Counts/value: mono 0.6rem, `--text-2` and
`--text-3`, right-aligned, fixed-width columns (70px / 80px) so figures align
vertically across rows.

### 3.4 Leaderboard table
`.lb-table`: `width:100%; border:1px solid var(--border); border-collapse:
collapse;` — `td/th padding: 10px 13px; border-bottom: 1px solid
var(--border)` (i.e. `.cmd-table` plus a header). Header `th`: mono 0.56rem
uppercase `--text-3` letter-spacing 0.1em, `background: var(--surface)`.
Body: mono 0.66rem `--text`; money and counts `--text-2`. Rank-1 `tr`:
`border-left: 2px solid var(--accent)`. Wrap the table in a
`overflow-x:auto` container; at `max-width: 900px` drop the `LAST ACTIVITY`
column, at `580px` also drop `STALLED` (mobile shows rank, rep, leads,
pipeline, closed-won).

### 3.5 Section spacing
Every section: `margin-bottom: 20px`. Panel-style sections (funnel) use
`.panel` inside a 1px `--border` wrapper, consistent with `page-home` panels.
No new fonts, no new spacing scale, no shadows, no rounded corners — the
dashboard is deliberately square-cornered; keep it that way.

---

## 4. Copy — every string on the page

Coworking vocabulary throughout: *seats, cabins, managed office, site visit,
lock-in, move-in*. Never "deals pipeline" generic-SaaS phrasing where a
coworking term exists. Exact strings:

| Location | String |
|---|---|
| Nav item | `Team` |
| Topbar title (`PAGE_TITLES.manager`) | `Team Pipeline` |
| Stat 1 label | `TOTAL PIPELINE` |
| Stat 2 label | `ACTIVE LEADS` |
| Stat 3 label | `CLOSED-WON · THIS MONTH` |
| Stat 3 sub-line | `{n} deals` / `1 deal` |
| Stat 4 label | `STALLED LEADS` |
| Funnel panel title | `TEAM FUNNEL` |
| Funnel panel caption | `All reps · live` |
| Funnel row figures | `{n} leads` (`1 lead`), `{formatINR}` |
| Closed strip | `Closed-Won {n} · {value}` `Closed-Lost {n} · {value}` |
| Leaderboard header | `REP LEADERBOARD` |
| Leaderboard columns | `#` · `REP` · `ACTIVE LEADS` · `PIPELINE` · `CLOSED-WON` · `STALLED` · `LAST ACTIVITY` |
| Stalled header | `STALLED LEADS` |
| Stalled caption | `Quiet past their stage threshold · nudges go out automatically` |
| Stalled row line 2 | `{seat_count} seats · {space_type?} · {city} · {value}` — `seats TBC` when null |
| Stalled row quiet label | `{n}d quiet` |
| Action buttons | `View` · `Nudge rep` |
| Nudge success state | `Nudged` |
| Nudge disabled tooltip (`title` attr, only if endpoint unbuilt) | `Manual nudge coming soon — automatic nudges are already active` |
| Expand link | `Show all {n} stalled leads` |
| Empty — whole page title / sub | `Nothing in the pipeline yet.` / `Team leads will appear here as reps forward conversations to the bot.` |
| Empty — leaderboard | `No reps on the team yet. Reps appear after their first /start.` |
| Empty — stalled title / sub | `Nothing stalled.` / `Every active lead has been touched inside its stage threshold. The bot will nudge reps if that changes.` |
| Error — fetch | `Could not load team data: {message}` |
| Error — 403 | `This view is for managers. Ask your admin for a manager dashboard link.` |

Tooltips beyond the one above: none. The screen must be self-explanatory; if a
label needs a tooltip, the label is wrong.

---

## 5. Data contract assumption — `GET /api/team/funnel`

**This is an assumption to reconcile with the Phase 5 implementer, not a
locked contract.** Whichever side builds first, the other adapts; if the
endpoint diverges, update this section rather than silently mapping around it.

Auth: `Authorization: Bearer <signed dashboard token>`; 403 for non-manager
role. Single response, no pagination (team scale for the demo is ~15 leads).

```json
{
  "period": { "month": "2026-07" },
  "totals": {
    "pipeline_value": 42000000,
    "active_leads": 23,
    "closed_won_count": 3,
    "closed_won_value": 21000000,
    "stalled_count": 4
  },
  "funnel": [
    { "stage": "Inquiry",     "count": 8, "value": 6200000 },
    { "stage": "Qualified",   "count": 6, "value": 11000000 },
    { "stage": "Site Visit",  "count": 4, "value": 8800000 },
    { "stage": "Proposal",    "count": 3, "value": 16000000 },
    { "stage": "Negotiation", "count": 2, "value": 7500000 },
    { "stage": "Closed-Won",  "count": 5, "value": 21000000 },
    { "stage": "Closed-Lost", "count": 3, "value": 9400000 }
  ],
  "reps": [
    {
      "user_id": 2,
      "name": "Priya",
      "active_leads": 9,
      "pipeline_value": 18000000,
      "closed_won_count": 2,
      "closed_won_value": 8000000,
      "stalled_count": 1,
      "last_activity_at": "2026-07-16T09:12:00Z"
    }
  ],
  "stalled": [
    {
      "lead_id": 12,
      "company": "Zomato",
      "contact_name": "Rohan Verma",
      "seat_count": 200,
      "space_type": "managed_office",
      "city": "Gurgaon",
      "stage": "Proposal",
      "est_deal_value": 14000000,
      "days_stalled": 5,
      "assigned_to": { "user_id": 2, "name": "Priya" }
    }
  ]
}
```

Assumptions embedded above, called out explicitly:

1. **Money is integer rupees** (not paise, not lakh-units). `formatINR`
   assumes this.
2. **`funnel` includes all 7 stages** (closed included, for the closed strip
   and won-this-month cross-check) in canonical order; UI does not re-sort.
3. **Stage strings are the canonical names verbatim** — `Site Visit` with a
   space, `Closed-Won`/`Closed-Lost` hyphenated. Badge class lookup is an
   exact-match map; a mismatch renders the fallback `.bs-inq` gray and will be
   visibly wrong on the demo — treat naming drift as a bug on whichever side
   drifted.
4. **Stalled-ness is computed server-side** (per-stage inactivity thresholds
   live next to the Phase 4 nudge logic — one definition, two consumers). The
   UI only displays `days_stalled`, never derives it.
5. **`closed_won_*` totals are current-calendar-month**, matching the stat
   tile label; `funnel`'s Closed-Won row may be a wider window (demo:
   all-time) — the funnel strip and stat tile are therefore allowed to differ.
6. **`reps` is pre-sorted by `pipeline_value` desc**; UI assigns ranks by
   array order.
7. `Nudge rep` needs **`POST /api/leads/{id}/nudge`** (manager-only, triggers
   the Phase 4 nudge DM for that lead immediately, 204 on success). Not in
   the Phase 5 endpoint list as of this writing — reconcile scope before
   building the button live; otherwise ship it disabled with the tooltip in
   Section 4.

---

## 6. Implementation notes for the executing agent

- Additions to existing JS plumbing: `PAGE_TITLES.manager = 'Team Pipeline'`;
  no `PAGE_PARENT_NAV` entry; new `nav-manager` button; a `loadTeamData()`
  fetch wired into the same refresh cycle as `loadData()` but only executed
  when the manager nav is visible (don't 403-spam for reps).
- `formatINR` and the 7-stage badge map are shared with the reworked rep view
  — define once at the top of the script block next to `ALL_STAGES` (which
  itself gets the new stage names in Phase 6; keep one constant, not two).
- Everything renders from the single `/api/team/funnel` payload — no N+1
  fetches, no client-side joins against the rep-view lead list.
- All dynamic strings pass through the existing `esc()` helper (company names,
  rep names, cities come from AI extraction of forwarded messages — hostile
  input surface).
