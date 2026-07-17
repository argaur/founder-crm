# Dashboard Home Redesign — Vision Document

**Date:** 2026-07-17
**Status:** VISION / BRAINSTORM — not an approved spec. Gaurav reviews and cuts before anything becomes an implementation plan.
**Surface:** `landing/dashboard/index.html` → `#page-home` (currently lines ~1657–1761)
**Design authority:** `DESIGN_BRIEF.md` (light-only, Manrope, no accent color — every visual in this doc obeys it)

**Phase tags — every idea carries exactly one:**
- **[P1]** — shippable today, a few hours total for a single implementer working vanilla JS with no bundler
- **[P2]** — later, needs either more time, a schema change, or data we don't collect yet

---

## 0. What this page must prove (purpose before aesthetics)

The home page is the first thing a Stylework reviewer sees after self-signup. Today it shows them a bot explainer and **three rows of fake companies** — the one thing the design brief's voice rules explicitly forbid ("no fabricated testimonials or invented metrics"), rendered as product UI on the most important screen. The root cause: the empty-state check keys on *personal* lead assignment, but self-signups are now managers who own nothing personally while the platform is full of seeded data.

So the page has one job: **make the "pipeline that runs itself" claim visible in ten seconds.** A manager opens home and sees the whole business — money in motion, where it's stuck, what's hot, what the inventory can absorb, and what needs a human today. Every element below either advances that or doesn't ship.

The single structural decision everything else hangs on:

> **[P1] Home becomes a role-scoped platform overview, fed by one new endpoint (`GET /api/overview`). Managers always see platform-wide data — the fake-demo empty state becomes unreachable for them by construction, not by patching the condition.**

---

## 1. The full picture — page anatomy

Top to bottom, a manager's home. (Rep differences in §6.)

```
┌─────────────────────────────────────────────────────────────┐
│ A. Command header — greeting, date, one-line platform pulse │
├─────────────────────────────────────────────────────────────┤
│ B. Stat band — 5 oversized numerals (the Stylework motif)   │
├──────────────────────────────┬──────────────────────────────┤
│ C. Pipeline funnel (chart 1) │ D. Heat & momentum (chart 3) │
├──────────────────────────────┼──────────────────────────────┤
│ E. Site Visit Radar          │ F. Inventory pressure        │
│    (weather lives HERE)      │    (chart 2)                 │
├──────────────────────────────┼──────────────────────────────┤
│ G. Needs a human today       │ H. Live activity feed        │
├──────────────────────────────┴──────────────────────────────┤
│ I. City footprint strip                                     │
└─────────────────────────────────────────────────────────────┘
```

### A. Command header **[P1]**
Replaces the bare "Dashboard" topbar title area inside `#page-home`. Left: `Thursday, 17 July` (eyebrow style, uppercase, `--text-3`) over a Manrope-800 greeting: **"Good afternoon, Gaurav."** Right-aligned subline, declarative voice: *"₹4.2 Cr in play across 11 active deals. 3 need attention."* — numbers pulled from the overview payload, sentence assembled from three fixed templates (healthy / stalled-heavy / empty). This is the cheapest "amazing" on the whole page: it proves the system already knows the state of the business before the user clicks anything.
- **[P2]** The pulse line becomes AI-generated (one gpt-4o-mini call server-side, cached hourly): a genuinely synthesized daily brief ("Negotiation-stage value doubled this week; BrightHire has gone quiet 6 days before their move-in").

### B. Stat band **[P1]**
Five stat cards (current grid has four thin ones). Big-number treatment per brief §2: value 1.6rem+/800 tabular-nums ink, uppercase label beneath in `--text-3`.
1. **Pipeline value** — `₹4.2 Cr` (active stages, est_deal_value sum). The loudest number on the page.
2. **Active deals** — count.
3. **Won this month** — count + value subline, the one place `#15803D` text appears in the band.
4. **Stalled** — count, `#B91C1C` text only when > 0 (functional state, not decoration).
5. **Seats in demand vs. available** — `247 / 410` — total seat_count across active leads vs. total available_seats in `spaces`. This is the number no generic CRM could show: demand vs. supply in one glance. It's the aggregator's own mental model rendered as a stat.
- **[P2]** Each stat gets a 14-day sparkline ghost under the numeral (needs daily snapshots — schema addition, see §7).

### C. Pipeline funnel — signature chart 1 **[P1]** — full spec in §3.

### D. Heat & momentum **[P1 / P2 split]**
- **[P1]** Heat distribution strip (signature chart 3, §3) + "Hottest deals" list, top 4 by heat score: company (700 weight), contact · seats · city in `--text-2`, heat badge, `est_deal_value` right-aligned tabular. Row click → pipeline page. If the in-flight `signal_tag` field has landed, render it as the row's second line in `--text-3` italic-free ("why this lead, why now" — it was built for exactly this slot); if absent from the payload, degrade to contact/seats/city. Do not build anything that *requires* it.
- **[P2]** 14-day capture-activity sparkline (interactions/day, SVG columns) once the overview endpoint aggregates `interactions.logged_at` by day — cheap query, but cut from P1 to protect the few-hours budget.

### E. Site Visit Radar — the weather feature **[P1]** — full spec in §4.

### F. Inventory pressure — signature chart 2 **[P1]** — full spec in §3. Built on the existing `db.get_all_spaces()`; does not touch the in-flight per-lead matching engine.
- **[P2]** "Match digest" line per city — "3 hot leads in Gurgaon match Awfis Cyber City" — composed client-side from the in-flight `GET /api/leads/{id}/matches` once it ships. Leverage, don't rebuild.

### G. Needs a human today **[P1]**
The automation story's honest counterpart: the system runs itself *and tells you the exceptions.* A ranked list (max 5) merging: stalled leads (days-stalled desc, from overview payload), hot leads with `move_in_date` within 14 days, and Negotiation-stage leads with no activity in 3+ days. Each row: company, one-line reason in `--text-2` ("Site visit 9 days ago, no follow-up"), days-badge (monochrome chip), and for managers a **Nudge** ghost button wired to the existing `POST /api/leads/{id}/nudge`. Reasons are template strings computed client-side from fields already in the payload — no AI call.
- **[P2]** Reasons become AI-written per-lead (or reuse `signal_tag` directly once confirmed shipped).

### H. Live activity feed **[P1]**
Reverse-chron last 10 interactions platform-wide: relative time (`2h ago`, `--text-3` tabular), type icon (16px ink SVG stroke-1.5 per `interaction_type` — chat/mic/camera/pencil), `ai_summary` truncated to one line, company chip. The left edge carries the brief's `border-left: 2px solid var(--ink)` rule on the newest item only — "live" expressed monochromatically. This panel *is* the product demo: WhatsApp chaos becoming structured rows, visibly, timestamped.
- **[P2]** Poll every 60s and prepend with a fade-in; **[P2]** filter chips by type/rep.

### I. City footprint strip **[P1]**
One horizontal row of city cards (6 cities max — Bangalore, Delhi, Gurgaon, Hyderabad, Mumbai, Pune): city name 700-weight, active-deal count + pipeline value tabular, and a 3px-tall ink bar under each whose width ∝ that city's share of pipeline value (a bar chart disguised as an underline). Click → **[P2]** city-filtered pipeline view.
- **[P2]** Replace with a hand-drawn SVG India outline, cities as ink dots sized by pipeline value, labels on hover. Genuinely striking in monochrome, genuinely not a few-hours item.

### Deliberately excluded (evaluated, rejected as dashboard bloat)
Decorative clocks/quotes; generic "conversion rate" gauges (7 stages × 13 seeded leads = statistically meaningless rates that would read as fake); anything requiring a paid API; dark-mode variants (brief forbids); any second font or accent hue.

### The empty-state fix **[P1]**
- Manager (every self-signup): never sees the empty state — overview payload always has platform data. Section A–I render.
- Rep with zero assigned leads: keep the existing 3-step bot explainer (it's good), **delete the fake TechCorp/Razorpay/Groww demo rows entirely** — replace the demo-box with the real platform activity feed (H), read-scoped, so the "yours will appear here" promise is demonstrated with true data instead of fabricated data.
- True cold-start platform (zero leads anywhere): explainer + zeroed stat band. Zeros are honest; fake rows are not.

---

## 2. Charting approach — hand-rolled SVG, and why

**Decision [P1]: no charting library.** Hand-rolled inline SVG (bars, strips, sparklines) + plain divs where a div suffices.
- Every chart in P1 is bars-and-labels — a library's value (scales, axes, tooltips, animation) is exactly what the brief strips away (no axes, no gridlines, restrained motion).
- No bundler means a library = a CDN `<script>` — new external dependency, new failure mode, ~70–200KB for four bar charts.
- Libraries ship opinionated default palettes and hover chrome that would each need fighting to reach monochrome compliance. Hand-rolled starts compliant.
- Precedent already in-repo: the landing page's `.db-*` dashboard mock is hand-built markup on the same tokens; these charts are its live siblings.

Rendering rule: build SVG strings in JS template literals, `viewBox`-based so they scale, width 100%, heights fixed (funnel rows 28px, strips 10–12px). All text as HTML beside/under the SVG, not `<text>` elements — keeps typography in the token system. **All numeric values escape through the existing `formatINR(n)` helper; all strings through the dashboard's existing escaping pattern.**

**[P2]** If analytics ever grow real time-series (velocity, forecasts), reconsider a micro-library (uPlot, ~40KB) — but not before the data exists.

---

## 3. The monochrome resolution — three signature charts, specced to the pixel

The tension: "amazing charts" vs. "there is no accent color." Resolution: **hue is not the only channel — the brief already defines a density scale (ink-filled / border-grey / surface-grey for Hot/Warm/Cold). The charts extend that exact scale, so data-viz and badge language become one system.** Opacity, width, weight, and scale carry signal. Precedent: Stripe's early dashboards and Linear's graphs read as premium *because* of restraint. A monochrome chart on this page isn't a limitation being worked around; it's the same statement the whole brief makes — sophistication through restraint — applied to data.

### Chart 1 — Pipeline funnel (panel C) **[P1]**
Seven horizontal rows, one per stage in `db.STAGES` order. Each row: stage label left (0.72rem, 600, `--text-2`, fixed 110px column), bar middle, `count · ₹value` right (tabular-nums, 600, `--ink`).
- Bar: height 22px, radius 5px, width ∝ **sum of est_deal_value** in that stage (max stage = 100% of track; zero-value stage renders a 2px ink tick, not nothing — brief says numbers are the loudest thing, and absence is information).
- Fill: `var(--ink)` at stepped opacity by funnel progress — Inquiry 0.18, Qualified 0.32, Site Visit 0.46, Proposal 0.62, Negotiation 0.80, Closed-Won 1.00, Closed-Lost 0.12 with the row's *label* in `#B91C1C`. Reading: **darker = closer to money.** The funnel narrative is visible without a single hue.
- Closed-Won's right-hand value text in `#15803D` (functional state — the one earned use).
- Track behind each bar: `var(--surface-2)`, full width, so relative widths read instantly.
- No axis, no gridlines, no legend, no tooltips in P1. Row hover: track → `var(--border)`, cursor pointer, click → pipeline page. **[P2]** click filters pipeline to that stage.

### Chart 2 — Inventory pressure (panel F) **[P1]**
Per city with spaces (6 rows): city label left (700, `--ink`), occupancy bar, `occupied/total seats` right (tabular).
- Bar: 12px tall track in `var(--surface-2)`, radius 6px; ink fill for occupied fraction (`(total_seats − available_seats) / total_seats`).
- Overlaid **demand tick**: a 2px vertical `var(--ink)` line at the position of `(occupied + active-lead seat demand in that city) / total`, capped at 100% — showing where occupancy lands *if the current pipeline closes*. One bar answers "can this city absorb its own pipeline?" — the single smartest monochrome move on the page. If demand overflows the track, the tick sits at 100% and the right-hand text gains `+N over` in `#B91C1C` (functional: a real capacity problem).
- Subline per row (0.675rem, `--text-3`): `4 spaces · from ₹7,500/seat` (min price_per_seat).
- No hue anywhere; the demand tick is the drama.

### Chart 3 — Heat strip (panel D) **[P1]**
A single 100%-width stacked horizontal bar, 12px tall, radius 6px, three segments sized by count of active leads: Hot = `var(--ink)`, Warm = `var(--border-2)`, Cold = `var(--surface-2)` — **the exact same three fills as the heat badges**, so the chart needs no legend for anyone who has seen a badge. 1px white gaps between segments. Beneath: three inline labels `● Hot 4 · Warm 5 · Cold 2` (dot = 6px swatch of the segment fill, counts tabular 600). Zero-count segment: omit segment, render label at `--text-3`.

---

## 4. Site Visit Radar — weather that earns its place **[P1]**

**Not an ambient widget.** Site visits are the physical, revenue-critical step in this pipeline — and in Indian metros, monsoon rain, 44° heat, and (Delhi) toxic air genuinely reschedule them. The feature answers one rep question: *"I need to get this prospect to a space this week — which day?"*

**Data source: Open-Meteo** (`api.open-meteo.com/v1/forecast`). Free for non-commercial use, **no API key, no signup, CORS-enabled** — callable straight from the static GitHub-Pages dashboard, nothing for Gaurav to provision, no secret to leak (the exact failure class the old Airtable PAT bug taught this repo about). One batched call covers all cities: comma-separated `latitude`/`longitude` lists return one forecast per city pair. City coordinates are a hardcoded six-entry map in the dashboard JS (Bangalore 12.97,77.59 · Delhi 28.61,77.21 · Gurgaon 28.46,77.03 · Hyderabad 17.39,78.49 · Mumbai 19.08,72.88 · Pune 18.52,73.86) — the `spaces` seed and demo leads only span these; unknown city → no chip, no error.

Request: `daily=weather_code,temperature_2m_max,precipitation_probability_max&forecast_days=4&timezone=Asia/Kolkata`. Cache the parsed response in `sessionStorage` for 30 minutes. **Failure mode: hide weather chips entirely and render the radar without them — weather is enrichment, never a blocker; no error banner, one `console.warn`.**

**Panel content:** every active lead at stage `Site Visit` (plus **[P2]** Qualified-stage hot leads as "visit candidates"), sorted by heat. Each row:
- Line 1: company (700) · contact · `NN seats` · space_type chip.
- Line 2 — the weather chip: 16px monochrome ink SVG icon (sun/cloud/rain/haze, stroke 1.5 — mapped from WMO `weather_code`; no emoji, per repo rules) + `Gurgaon · 34° today · Rain 80% Thu` (0.72rem, `--text-2`, temps tabular). When any of the next 3 days has precipitation probability ≥ 60%, append a declarative planning cue in `--text-3`: *"Wed is the dry window."* — computed by trivially picking the lowest-precip day. That one sentence converts weather data into a sales decision, which is the entire justification for the feature.
- If `move_in_date` is within 21 days: a `Move-in DD Mmm` chip (`--surface-2` ground) — urgency context beside weather context.
- Row action: **Spaces in {city} →** ghost link. **[P1]** scrolls to the inventory panel; **[P2]** opens the lead's actual match list from the in-flight `GET /api/leads/{id}/matches`.

**[P2] extensions:** Open-Meteo's air-quality endpoint (also keyless) → AQI chip for Delhi/Gurgaon visits ("AQI 240 — book the afternoon slot"); a "best visit day" badge combining precip + AQI + move-in urgency; **[P2]** travel-time estimates (needs Google/Mapbox key — paid, explicitly out unless Gaurav provisions one).

---

## 5. New endpoint for Phase 1 — `GET /api/overview`

One endpoint, not five (fewer powerful tools > many narrow ones). Auth `Depends(require_user)`, **role-scoped exactly like `/api/leads`**: manager → platform-wide; rep → `assigned_to=user["id"]` scope for leads-derived sections, while `inventory` (org-level, non-sensitive) and `activity` (platform-wide read keeps a new rep's page alive) stay unscoped. Weather is deliberately client-side (§4) — the API stays weather-free.

```jsonc
// GET /api/overview   → 200
{
  "user": { /* _public_user shape */ },
  "totals": {
    "pipeline_value": 42000000.0,      // active stages only (reuse ACTIVE_STAGES)
    "active_leads": 11,
    "closed_won_count": 2,             // this month, last_activity_at proxy — same rule as /api/team/funnel
    "closed_won_value": 8400000.0,
    "stalled_count": 3,                // db.get_stale_leads(days=NUDGE_STALE_DAYS)
    "companies": 12,                   // COUNT(*) companies
    "contacts": 13,                    // COUNT(*) leads (contact per lead in this model)
    "seats_demanded": 247,             // SUM(seat_count) active leads
    "seats_available": 410             // SUM(available_seats) spaces
  },
  "funnel":  [ { "stage": "Inquiry", "count": 3, "value": 4500000.0 }, /* ×7, db.STAGES order */ ],
  "heat":    { "hot": 4, "warm": 5, "cold": 2 },              // active leads only
  "by_city": [ { "city": "Gurgaon", "active_count": 4, "pipeline_value": 18000000.0 } ],
  "hottest": [ /* ≤4 lead dicts: id, company (name), contact_name, city, seat_count,
                  space_type, stage, est_deal_value, heat_score, move_in_date,
                  signal_tag (whatever _lead_with_heat injects — pass through, null-safe) */ ],
  "site_visits": [ /* leads at stage "Site Visit", same lead shape */ ],
  "attention": [ { "lead_id": 7, "company": "BrightHire", "contact_name": "…",
                   "stage": "Negotiation", "est_deal_value": 6200000.0,
                   "days_stalled": 6, "move_in_date": "2026-08-01",
                   "assigned_to": { "user_id": 2, "name": "Priya" } } ],   // ≤5, stalled ∪ urgent
  "inventory": [ { "city": "Gurgaon", "space_count": 2, "total_seats": 120,
                   "available_seats": 38, "min_price_per_seat": 7500.0,
                   "demand_seats": 85 } ],                    // demand = active-lead seats in city
  "activity":  [ { "id": 41, "lead_id": 7, "company": "BrightHire", "type": "voice_note",
                   "ai_summary": "…", "user_name": "Priya", "logged_at": "2026-07-17T09:40:00Z" } ]  // ≤10
}
```

**Implementation notes (P1-honest):** composes almost entirely from existing `db.py` calls — `get_all_leads(assigned_to=scope)`, `get_stale_leads`, `get_all_spaces()`, `_company_names`, plus **one** new query, `db.get_recent_interactions(limit=10)` (interactions ⋈ leads ⋈ companies ⋈ users, `ORDER BY logged_at DESC` — mirror `get_interactions`' style) and two scalar counts. Aggregation happens in Python exactly like `/api/team/funnel` already does — copy its patterns (`value_of`, month-start proxy, `ACTIVE_STAGES`) rather than inventing parallel ones. Est. 60–90 min including curl verification against seeded Neon data.

**[P2] endpoints (named now, built later):**
- `GET /api/spaces` — full inventory listing for a future Spaces page (role: any; the home panel's aggregate ships inside `/api/overview` and does not wait for this).
- `GET /api/overview/brief` — the AI-written daily pulse (server-side gpt-4o-mini, 1h cache).
- `GET /api/analytics/velocity` — time-in-stage / conversion analytics. **Blocked on schema:** requires a `stage_history` table (or `stage_changed_at` audit rows); today only `last_activity_at` exists, and honest velocity math is impossible without it. Do not fake it from proxies.
- Daily `pipeline_snapshots` table + cron for stat-band sparklines **[P2]**.

---

## 6. Rep-scoped home (secondary, but specified)

Same layout, scoped payload, three differences: (1) stat band reads *my* pipeline; seats-demand stat compares **my** demand vs. platform availability — still useful, differently framed. (2) Panel G drops the Nudge button (manager-only endpoint) — reason lines remain. (3) Site Visit Radar becomes the rep's **primary** panel (it's their literal to-do list) — visually identical, just ordered above the funnel. Cheap conditional reorder, not a fork. **[P1]** — falls out of the role-scoped endpoint nearly free; budget 20 minutes for the conditionals.

---

## 7. Phase summary table

| # | Item | Phase | Depends on |
|---|------|-------|-----------|
| A | Command header, templated pulse line | **P1** | `/api/overview` |
| A+ | AI-written daily brief | P2 | new endpoint, cache |
| B | 5-stat band incl. seats demand/supply | **P1** | `/api/overview` |
| B+ | Stat sparklines | P2 | snapshots table |
| C | Funnel chart (opacity-graded bars) | **P1** | `/api/overview` |
| D | Heat strip + hottest deals (+ signal_tag pass-through) | **P1** | `/api/overview` |
| D+ | Activity sparkline | P2 | daily-counts query |
| E | Site Visit Radar + Open-Meteo chips + dry-window cue | **P1** | `/api/overview` + client fetch |
| E+ | AQI, best-day badge, per-lead space matches | P2 | in-flight matches API |
| F | Inventory pressure bars + demand tick | **P1** | `/api/overview` |
| F+ | Match digest lines | P2 | in-flight matches API |
| G | Needs-a-human list + Nudge | **P1** | `/api/overview`, existing nudge API |
| H | Activity feed | **P1** | `/api/overview` |
| H+ | 60s polling, filters | P2 | — |
| I | City strip with share-bars | **P1** | `/api/overview` |
| I+ | SVG India map | P2 | — |
| — | Fake-demo-data deletion + empty-state rekey | **P1** | none (do this regardless) |
| — | `GET /api/overview` | **P1** | 1 new db query |
| — | Rep-scoped variant | **P1** | same endpoint |
| — | Velocity/conversion analytics | P2 | `stage_history` schema |
| — | Spaces page + `GET /api/spaces` | P2 | — |

**P1 budget check (single implementer, few hours):** endpoint 1–1.5h · charts C/D/F/H/I ~2h (they share one bar-row rendering helper) · radar + weather ~1h · header/stats/empty-state ~1h. Tight but honest at ~5–6h; if it slips, the cut order is **I → G's merge logic (stalled-only) → A's pulse line**, never the charts or the radar (they are the demo).

---

## 8. Open questions for Gaurav

1. **Funnel bar metric:** width by ₹ value (proposed — it's a sales pitch) or by count? Value makes Negotiation dominate; count flatters the top of funnel.
2. **Activity feed scope for reps:** platform-wide read (proposed, keeps new-rep home alive; summaries aren't sensitive between colleagues) or own-leads only?
3. **One palette exception to consider — recommendation: no.** Charts stay fully monochrome per brief. If any future chart genuinely needs a second categorical channel (e.g. rep-comparison overlays), the brief-compatible answer is pattern (hairline diagonal stripes at ink-10%), not hue. Flagged only so nobody "helpfully" adds colors later.
4. **Open-Meteo licence:** free tier is non-commercial. For a job-referral demo this is fine; if Siteline ever became a real commercial product, weather needs a paid tier (~€29/mo) or a swap. Accept for the demo?
