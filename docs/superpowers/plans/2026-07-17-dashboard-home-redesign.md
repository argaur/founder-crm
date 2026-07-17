# Dashboard Home Redesign (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the dashboard home page (`landing/dashboard/index.html` → `#page-home`) into a role-scoped platform overview fed by one new endpoint (`GET /api/overview`), replacing the fake-demo empty state with the real business picture: money in motion, heat, site-visit weather, inventory pressure, exceptions, and live activity.

**Architecture:** One new authenticated FastAPI endpoint (`GET /api/overview`) composes almost entirely from existing `db.py` calls plus one new query (`db.get_recent_interactions`), aggregating in Python exactly like `/api/team/funnel` (reuse `value_of`, the month-start `last_activity_at` proxy, and `ACTIVE_STAGES`). The dashboard fetches it alongside `/api/leads` in `loadData()`, stores it in a new `overviewData` global, and a rewritten `renderHome()` state machine renders nine hand-rolled-SVG / plain-div panels (no charting library, no bundler, no new dependency). Weather is a deliberately client-side Open-Meteo fetch (keyless, CORS-enabled) — the API stays weather-free.

**Tech Stack:** Python 3.11 / asyncpg / FastAPI / python-telegram-bot v21 (all async) on the bot side; vanilla HTML/CSS/JS (no framework, no bundler) on the dashboard side. Neon Postgres (project `winter-haze-14475661`). Open-Meteo forecast API (client-side, free/non-commercial tier — accepted for this demo).

## Global Constraints

- **Visual system is `DESIGN_BRIEF.md` — light-only, Manrope, NO accent hue.** Emphasis is weight (800) + scale + ink-vs-grey contrast only. The only earned colors are the two semantic states: success/won text `#15803D`, error/lost text `#B91C1C` — used only where state genuinely demands it (Closed-Won value, stalled count > 0, capacity overflow). Everything else is monochrome. Charts stay fully monochrome — **no palette exception** (resolved §8 Q3).
- **Monochrome chart language = the badge density scale:** Hot `var(--ink)`, Warm `var(--border-2)`, Cold `var(--surface-2)` — the exact three fills as the `badge bh/bw/bc` heat badges, so charts need no legend. Opacity, width, weight, and scale carry signal, never hue.
- **Charts are hand-rolled inline SVG** built as JS template-literal strings, `viewBox`-based, width 100%, fixed heights. All text lives in HTML beside/under the SVG (not `<text>` elements) so typography stays in the token system. No axes, no gridlines, no tooltips, no legends in P1.
- **Every numeric value renders through the existing `formatINR(n)` helper; every string through the existing `esc(str)` helper.** Never render a raw integer as money; never interpolate an unescaped string into `innerHTML`.
- **No new dependency, no bundler, no CDN `<script>`, no schema change, no new AI call.** `/api/overview` adds exactly one new `db.py` query (`get_recent_interactions`).
- **Funnel bar metric is deal VALUE (₹, sum of `est_deal_value` per stage), not lead count** — LOCKED by Gaurav (resolved, not open).
- **Rep activity feed panel reads platform-wide** (not own-leads-only), because interaction summaries aren't sensitive between colleagues and it keeps a new rep's home alive (resolved §8 Q2).
- **`signal_tag` is pass-through and null-safe.** `db._lead_with_heat` already injects `lead["signal_tag"]` (Feature C, already landed). Panel D renders it when present; if absent/null in the payload, degrade to `contact · seats · city`. Build nothing that *requires* it.
- Every `db.*` call must be `await`ed (`db.py` is fully async). Every `/api/*` fetch on the dashboard goes through `apiFetch(path)` (attaches the Bearer token, handles 401 by rendering sign-in and returning `undefined`).
- No silent `except` — bot-side failures log via `logger.exception`; client-side non-fatal failures (weather) do exactly one `console.warn`, never an error banner.
- **Verification style:** this project has NO automated test suite (documented in `bot/CLAUDE.md`). Verification is real round-trips: `curl` against a locally-running `bot/main.py` for API tasks, and a manual browser click-through (or a static HTML/JS review if browser automation is unavailable) for dashboard tasks. Throwaway verify scripts live under `bot/scripts/` and are **never** `git add`-ed (add specific files by name, never the directory).
- Run all Python from `bot/` (`cd bot && python ...`) so `load_dotenv()` reads `bot/.env` (`DATABASE_URL` and `DASHBOARD_TOKEN_SECRET` are set; `TELEGRAM_BOT_TOKEN`/`OPENAI_API_KEY` are deliberately blank — API-only mode, which is all these tasks need).
- Commit after every task. No `--force`, no `--no-verify`.
- **Same-file sequencing:** Tasks 2–11 all modify `landing/dashboard/index.html` and MUST be executed in order — each appends a `renderX()` function and adds a call inside `renderHome()` established by Task 2. Task 1 (backend) is the only one that touches a different file set and could run in parallel, but everything else consumes its payload, so build it first.

## Reference: fixed data this plan asserts against

Seeded by `bot/scripts/apply_schema.py` (`spaces`, 10 rows) and `bot/seed.py --seed` (1 manager + 2 reps + 13 leads across all 7 stages, several cities). Seed users (fixed negative `telegram_id`s): manager `-900001`, reps `-900002` / `-900003`. Space columns: `id, name, city, locality, total_seats, available_seats, price_per_seat (NUMERIC), space_type`. Cities present in seeded spaces: Bangalore, Delhi, Gurgaon, Hyderabad, Mumbai, Pune.

## Cut order (if the ~5–6h budget slips)

Per the vision doc, if a reviewer or implementer must triage, cut in this order and **never** the charts or the weather radar: **Task 10 (city strip) → Task 8's merge logic (drop to stalled-only) → Task 3's pulse line.**

---

### Task 1: `GET /api/overview` endpoint + `db.get_recent_interactions`

**Files:**
- Modify: `bot/db.py` — append `get_recent_interactions` after `get_interactions` (ends line 429)
- Modify: `bot/main.py` — insert `api_overview` after `api_lead_interactions` (ends line 543), before `api_team_funnel`
- Verify: `curl` round-trips (no code test file)

**Interfaces:**
- Consumes: `db.get_all_leads(assigned_to=scope)`, `db.get_stale_leads(days, assigned_to=scope)`, `db.get_all_spaces()`, `db.get_all_users()`, `_company_names(leads)`, `require_user`, `_public_user(user)`, `ACTIVE_STAGES`, `db.STAGES`, `NUDGE_STALE_DAYS` — all already defined.
- Produces:
  - `db.get_recent_interactions(limit: int = 10) -> List[Dict[str, Any]]` — rows with keys `id, lead_id, type, ai_summary, logged_at, company, user_name`.
  - `GET /api/overview` → the JSON documented in vision §5. Every dashboard task (2–11) consumes a slice of this exact shape. Key contract:
    - `user` — `_public_user` shape (`id, first_name, email, company, role`)
    - `totals` — `{pipeline_value, active_leads, closed_won_count, closed_won_value, stalled_count, companies, contacts, seats_demanded, seats_available}`
    - `funnel` — 7 items `{stage, count, value}` in `db.STAGES` order
    - `heat` — `{hot, warm, cold}` (active leads only)
    - `by_city` — `[{city, active_count, pipeline_value}]` desc by value
    - `hottest` — ≤4 lead cards (shape below), active, desc by heat score
    - `site_visits` — lead cards for every `Site Visit`-stage lead, desc by heat score
    - `attention` — ≤5 `{lead_id, company, contact_name, stage, est_deal_value, days_stalled, move_in_date, assigned_to}` (assigned_to = `{user_id, name}` or null)
    - `inventory` — `[{city, space_count, total_seats, available_seats, min_price_per_seat, demand_seats}]` asc by city
    - `activity` — ≤10 `{id, lead_id, company, type, ai_summary, user_name, logged_at}`
  - Lead-card shape (used by `hottest` + `site_visits`): `{id, company, contact_name, city, seat_count, space_type, stage, est_deal_value, heat_score, move_in_date, signal_tag}`.

- [ ] **Step 1: Add `get_recent_interactions` to `bot/db.py`**

Append directly after `get_interactions` (line 429):

```python
async def get_recent_interactions(limit: int = 10) -> List[Dict[str, Any]]:
    """Most-recent interactions platform-wide, joined lead → company → user,
    for the home activity feed. Mirrors get_interactions' style but cross-lead.
    Always platform-wide (activity summaries aren't sensitive between reps and
    a scoped read would blank a new rep's home)."""
    rows = await _get_pool().fetch(
        """
        SELECT i.id, i.lead_id, i.type, i.ai_summary, i.logged_at,
               c.name        AS company,
               u.first_name  AS user_name
        FROM interactions i
        JOIN leads l      ON l.id = i.lead_id
        LEFT JOIN companies c ON c.id = l.company_id
        LEFT JOIN users u     ON u.id = i.user_id
        ORDER BY i.logged_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]
```

- [ ] **Step 2: Add the `api_overview` endpoint to `bot/main.py`**

Insert after `api_lead_interactions` (ends line 543), before `api_team_funnel` (line 546):

```python
@app.get("/api/overview")
async def api_overview(user: Dict[str, Any] = Depends(require_user)):
    """Role-scoped home overview (vision §5). Manager → platform-wide; rep →
    own leads for leads-derived sections. Inventory (org-level) and activity
    (platform-wide read) stay unscoped so a new rep's home is never blank.
    Aggregation mirrors /api/team/funnel exactly (value_of, month-start proxy,
    ACTIVE_STAGES)."""
    scope = None if user["role"] == "manager" else user["id"]

    pipeline = await db.get_all_leads(assigned_to=scope)
    stale = await db.get_stale_leads(days=NUDGE_STALE_DAYS, assigned_to=scope)
    spaces = await db.get_all_spaces()
    recent = await db.get_recent_interactions(limit=10)
    users = await db.get_all_users()
    users_by_id = {u["id"]: u for u in users}

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def value_of(lead: Dict[str, Any]) -> float:
        return float(lead.get("est_deal_value") or 0)

    def won_this_month(lead: Dict[str, Any]) -> bool:
        return lead["last_activity_at"] >= month_start

    def heat_score(lead: Dict[str, Any]) -> int:
        return (lead.get("heat_score") or {}).get("score", 0)

    all_leads = [l for leads in pipeline.values() for l in leads]
    company_names = await _company_names(all_leads)
    for lead in all_leads:
        lead["company"] = company_names.get(lead.get("company_id"))
    stale_names = await _company_names(stale)
    for lead in stale:
        lead["company"] = stale_names.get(lead.get("company_id"))

    active_leads = [l for s in ACTIVE_STAGES for l in pipeline[s]]
    won_leads = [l for l in pipeline["Closed-Won"] if won_this_month(l)]

    def move_in_iso(lead: Dict[str, Any]) -> Optional[str]:
        mid = lead.get("move_in_date")
        return mid.isoformat() if mid else None

    def lead_card(lead: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": lead["id"],
            "company": lead.get("company"),
            "contact_name": lead.get("contact_name"),
            "city": lead.get("city"),
            "seat_count": lead.get("seat_count"),
            "space_type": lead.get("space_type"),
            "stage": lead.get("stage"),
            "est_deal_value": value_of(lead),
            "heat_score": lead.get("heat_score"),
            "move_in_date": move_in_iso(lead),
            "signal_tag": lead.get("signal_tag"),
        }

    funnel = [
        {"stage": s, "count": len(pipeline[s]),
         "value": sum(value_of(l) for l in pipeline[s])}
        for s in db.STAGES
    ]

    heat = {"hot": 0, "warm": 0, "cold": 0}
    for lead in active_leads:
        label = (lead.get("heat_score") or {}).get("label", "Cold").lower()
        if label in heat:
            heat[label] += 1

    city_agg: Dict[str, Dict[str, Any]] = {}
    for lead in active_leads:
        city = lead.get("city")
        if not city:
            continue
        row = city_agg.setdefault(city, {"city": city, "active_count": 0, "pipeline_value": 0.0})
        row["active_count"] += 1
        row["pipeline_value"] += value_of(lead)
    by_city = sorted(city_agg.values(), key=lambda c: c["pipeline_value"], reverse=True)

    hottest = [lead_card(l) for l in sorted(active_leads, key=heat_score, reverse=True)[:4]]
    site_visits = [lead_card(l) for l in sorted(pipeline["Site Visit"], key=heat_score, reverse=True)]

    # attention = stalled ∪ (Hot with move-in ≤14d) ∪ (Negotiation quiet ≥3d), ≤5
    attention_leads: Dict[int, Dict[str, Any]] = {l["id"]: l for l in stale}
    for lead in active_leads:
        label = (lead.get("heat_score") or {}).get("label")
        mid = lead.get("move_in_date")
        if label == "Hot" and mid and 0 <= (mid - now.date()).days <= 14:
            attention_leads[lead["id"]] = lead
    for lead in pipeline["Negotiation"]:
        if max(0, (now - lead["last_activity_at"]).days) >= NUDGE_STALE_DAYS:
            attention_leads[lead["id"]] = lead

    def attention_item(lead: Dict[str, Any]) -> Dict[str, Any]:
        rep = users_by_id.get(lead.get("assigned_to"))
        return {
            "lead_id": lead["id"],
            "company": lead.get("company"),
            "contact_name": lead.get("contact_name"),
            "stage": lead.get("stage"),
            "est_deal_value": value_of(lead),
            "days_stalled": max(0, (now - lead["last_activity_at"]).days),
            "move_in_date": move_in_iso(lead),
            "assigned_to": {"user_id": rep["id"], "name": rep["first_name"]} if rep else None,
        }

    attention = sorted(
        (attention_item(l) for l in attention_leads.values()),
        key=lambda a: a["days_stalled"], reverse=True,
    )[:5]

    demand_by_city: Dict[str, int] = {}
    for lead in active_leads:
        city = lead.get("city")
        seats = lead.get("seat_count")
        if city and seats:
            demand_by_city[city] = demand_by_city.get(city, 0) + int(seats)

    inv_agg: Dict[str, Dict[str, Any]] = {}
    for space in spaces:
        city = space["city"]
        agg = inv_agg.setdefault(city, {
            "city": city, "space_count": 0, "total_seats": 0,
            "available_seats": 0, "min_price_per_seat": None, "demand_seats": 0,
        })
        agg["space_count"] += 1
        agg["total_seats"] += int(space.get("total_seats") or 0)
        agg["available_seats"] += int(space.get("available_seats") or 0)
        price = float(space["price_per_seat"]) if space.get("price_per_seat") is not None else None
        if price is not None:
            agg["min_price_per_seat"] = (
                price if agg["min_price_per_seat"] is None
                else min(agg["min_price_per_seat"], price)
            )
    for city, agg in inv_agg.items():
        agg["demand_seats"] = demand_by_city.get(city, 0)
    inventory = sorted(inv_agg.values(), key=lambda c: c["city"])

    # companies/contacts computed from the already-fetched (scope-respecting)
    # leads — avoids two unscoped COUNT(*) queries that would leak platform
    # totals to a rep. Not shown in the 5-stat band; carried for completeness.
    totals = {
        "pipeline_value": sum(value_of(l) for l in active_leads),
        "active_leads": len(active_leads),
        "closed_won_count": len(won_leads),
        "closed_won_value": sum(value_of(l) for l in won_leads),
        "stalled_count": len(stale),
        "companies": len({l["company_id"] for l in all_leads if l.get("company_id")}),
        "contacts": len(all_leads),
        "seats_demanded": sum(int(l["seat_count"]) for l in active_leads if l.get("seat_count")),
        "seats_available": sum(int(s.get("available_seats") or 0) for s in spaces),
    }

    activity = [
        {
            "id": r["id"], "lead_id": r["lead_id"], "company": r["company"],
            "type": r["type"], "ai_summary": r["ai_summary"], "user_name": r["user_name"],
            "logged_at": r["logged_at"].isoformat() if r["logged_at"] else None,
        }
        for r in recent
    ]

    return {
        "user": _public_user(user),
        "totals": totals,
        "funnel": funnel,
        "heat": heat,
        "by_city": by_city,
        "hottest": hottest,
        "site_visits": site_visits,
        "attention": attention,
        "inventory": inventory,
        "activity": activity,
    }
```

- [ ] **Step 3: Start the server (API-only mode) and mint a manager token**

Terminal 1: `cd bot && python main.py` (blank `TELEGRAM_BOT_TOKEN` → API-only mode is expected).

Terminal 2:

```bash
curl -s -X POST http://localhost:8000/dashboard-link -H "Content-Type: application/json" -d '{"telegram_id": -900001}'
# → {"user_id":..,"first_name":"<manager>","role":"manager","token":"<MGR_TOKEN>"}
curl -s -X POST http://localhost:8000/dashboard-link -H "Content-Type: application/json" -d '{"telegram_id": -900002}'
# → {"user_id":..,"first_name":"<rep>","role":"rep","token":"<REP_TOKEN>"}
```

- [ ] **Step 4: Verify the manager payload shape**

```bash
curl -s http://localhost:8000/api/overview -H "Authorization: Bearer <MGR_TOKEN>" | python -m json.tool
```

Expected: HTTP 200 with all ten top-level keys (`user, totals, funnel, heat, by_city, hottest, site_visits, attention, inventory, activity`). Assert against seeded data:
- `totals.active_leads` ≥ 1, `totals.pipeline_value` > 0 (a plain number, not a string).
- `funnel` has exactly 7 items in `Inquiry … Closed-Lost` order; each `value` is numeric.
- `heat.hot + heat.warm + heat.cold == totals.active_leads`.
- `hottest` has ≤4 items, each with `heat_score.score` in descending order and a `signal_tag` string.
- `inventory` has one row per seeded city (Bangalore, Delhi, Gurgaon, Hyderabad, Mumbai, Pune), each with numeric `min_price_per_seat` and integer `demand_seats`.
- `activity` has ≤10 items, newest `logged_at` first.
- `attention` has ≤5 items sorted by `days_stalled` desc.

- [ ] **Step 5: Verify rep scoping + auth**

```bash
# Rep sees only their own leads-derived sections, but activity/inventory stay populated:
curl -s http://localhost:8000/api/overview -H "Authorization: Bearer <REP_TOKEN>" | python -m json.tool
# Missing token → 401:
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/overview
```

Expected: rep payload's `totals.active_leads` ≤ manager's (scoped down), but `activity` and `inventory` non-empty; missing-token call prints `401`.

- [ ] **Step 6: Commit**

```bash
git add bot/db.py bot/main.py
git commit -m "feat(api): GET /api/overview role-scoped home aggregate + get_recent_interactions"
```

---

### Task 2: Delete fake demo data, rewire home onto `/api/overview`, empty-state rekey + panel skeleton

**Files:**
- Modify: `landing/dashboard/index.html` — HTML `#page-home` block (lines 1657–1761), `loadData()` (line 2212), `renderHome()` (lines 2259–2326), globals (near line 2057), CSS `<style>` block (add `.home-grid` / `.stat-grid-5` near `.stat-grid` ~line 218).
- **Sequential:** first of the same-file tasks; Tasks 3–11 build on the `renderHome()` state machine and the panel container ids established here.

**Interfaces:**
- Consumes: `apiFetch('/api/overview')` (Task 1), existing `currentUser`, `allLeads`, `revealManagerNav()`, `esc`, `formatINR`.
- Produces:
  - Global `let overviewData = null;`
  - `renderHome()` rewritten as a 3-state machine keyed on `overviewData` + role, calling per-panel `renderX()` functions (added by Tasks 3–11).
  - New empty container ids inside `#home-data`: `#home-header`, `#home-stats`, `#home-funnel`, `#home-heat`, `#home-radar`, `#home-inventory`, `#home-attention`, `#home-activity`, `#home-cities`.
  - The fake `demo-box` (TechCorp/Razorpay/Groww) is deleted.

- [ ] **Step 1: Delete the fake demo rows from `#home-empty`**

In the `#home-empty` block, delete the entire `<div class="demo-box"> … </div>` (lines 1702–1719 — the "Example Pipeline" box with the three hardcoded companies). Keep `welcome-box` and `welcome-steps` exactly as they are (the 3-step bot explainer is good). The empty state now ends after the `</div>` that closes `welcome-steps`.

- [ ] **Step 2: Replace the `#home-data` inner markup with the panel skeleton**

Replace the entire contents of `<div id="home-data" class="hidden"> … </div>` (lines 1723–1760) with:

```html
        <!-- Data state -->
        <div id="home-data" class="hidden">
          <div id="home-header" class="home-header"></div>
          <div id="home-stats" class="stat-grid stat-grid-5"></div>
          <div class="home-grid">
            <div class="panel">
              <div class="panel-hd"><span class="panel-title">Pipeline</span></div>
              <div id="home-funnel"></div>
            </div>
            <div class="panel">
              <div class="panel-hd"><span class="panel-title">Heat &amp; Momentum</span></div>
              <div id="home-heat"></div>
            </div>
          </div>
          <div class="home-grid">
            <div class="panel">
              <div class="panel-hd"><span class="panel-title">Site Visit Radar</span></div>
              <div id="home-radar"></div>
            </div>
            <div class="panel">
              <div class="panel-hd"><span class="panel-title">Inventory Pressure</span></div>
              <div id="home-inventory"></div>
            </div>
          </div>
          <div class="home-grid">
            <div class="panel">
              <div class="panel-hd"><span class="panel-title">Needs a Human Today</span></div>
              <div id="home-attention"></div>
            </div>
            <div class="panel">
              <div class="panel-hd"><span class="panel-title">Live Activity</span></div>
              <div id="home-activity"></div>
            </div>
          </div>
          <div class="panel">
            <div class="panel-hd"><span class="panel-title">City Footprint</span></div>
            <div id="home-cities"></div>
          </div>
        </div>
```

- [ ] **Step 3: Add layout CSS**

In the `<style>` block, directly after the `.stat-card { … }` rule (line 218), add:

```css
    .stat-grid-5 { grid-template-columns: repeat(5, 1fr); }
    .home-header { margin-bottom: 20px; }
    .home-eyebrow {
      font-family: var(--sans); font-weight: 700; font-size: 0.675rem;
      text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-3);
    }
    .home-greeting {
      font-family: var(--sans); font-weight: 800; font-size: 1.5rem;
      letter-spacing: -0.02em; color: var(--ink); margin-top: 4px;
    }
    .home-pulse {
      font-family: var(--sans); font-weight: 400; font-size: 0.8125rem;
      color: var(--text-2); margin-top: 6px; line-height: 1.55;
    }
    .home-grid {
      display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px;
    }
    #home-data { display: flex; flex-direction: column; }
    #home-stats { margin-top: 4px; }
    @media (max-width: 860px) {
      .stat-grid-5 { grid-template-columns: repeat(2, 1fr); }
      .home-grid { grid-template-columns: 1fr; }
    }
```

- [ ] **Step 4: Add the `overviewData` global**

Near the other data globals (after `let pipelineData = {};`, line 2058), add:

```js
    let overviewData = null;   // parsed GET /api/overview payload (drives #page-home)
```

- [ ] **Step 5: Fetch `/api/overview` in `loadData()`**

In `loadData()`, replace the single fetch line (line 2225):

```js
        const data = await apiFetch('/api/leads');
        if (!data) return;   // 401 → apiFetch already rendered the sign-in state
```

with a parallel fetch of both endpoints:

```js
        const [data, overview] = await Promise.all([
          apiFetch('/api/leads'),
          apiFetch('/api/overview'),
        ]);
        if (!data || !overview) return;   // 401 → apiFetch already rendered sign-in
        overviewData = overview;
```

(The rest of the `try` block — `pipelineData`, `allLeads`, `revealManagerNav()`, the `renderHome(); renderPipeline(); …` line — is unchanged.)

- [ ] **Step 6: Rewrite `renderHome()` as the 3-state machine**

Replace the entire `renderHome()` function (lines 2259–2326) with:

```js
    // ── Render Home (overview-driven, vision §1) ──────────────────
    // States:
    //   full     — this scope has leads (or the user is a manager): render all panels
    //   rep-empty— rep with zero own leads but the platform is alive: explainer
    //              + real activity feed (wired in Task 9), never fake rows
    //   cold     — zero leads AND zero platform activity: explainer + zeroed stats
    function renderHome() {
      document.getElementById('home-loading').style.display = 'none';
      const dataEl  = document.getElementById('home-data');
      const emptyEl = document.getElementById('home-empty');
      const o = overviewData;
      if (!o) return;

      const role       = (currentUser && currentUser.role) || 'rep';
      const scopeHasLeads = o.totals.active_leads > 0 || o.totals.closed_won_count > 0;
      const platformAlive = (o.activity || []).length > 0;

      if (!scopeHasLeads && role !== 'manager') {
        // rep-empty OR cold-start — both show the explainer.
        dataEl.classList.add('hidden');
        emptyEl.classList.remove('hidden');
        // Task 9 replaces the deleted demo-box with the real activity feed here.
        return;
      }

      emptyEl.classList.add('hidden');
      dataEl.classList.remove('hidden');

      // Per-panel renderers are added by Tasks 3–11. Each is null-safe on its
      // slice of the payload, so partial builds render cleanly.
      renderHomeHeader(o);      // Task 3
      renderHomeStats(o);       // Task 3
      renderFunnel(o);          // Task 4
      renderHeatPanel(o);       // Task 5
      renderRadar(o);           // Task 6
      renderInventory(o);       // Task 7
      renderAttention(o);       // Task 8
      renderActivity(o);        // Task 9
      renderCities(o);          // Task 10
      applyRepLayout(role);     // Task 11

      // Nav follow-up badge (kept — sourced from the overview stalled count).
      const badge = document.getElementById('followup-badge');
      if (o.totals.stalled_count > 0) {
        badge.textContent = o.totals.stalled_count;
        badge.classList.remove('hidden');
      } else {
        badge.classList.add('hidden');
      }
    }
```

- [ ] **Step 7: Add temporary no-op stubs so the page renders between tasks**

So the page doesn't throw `ReferenceError` before Tasks 3–11 land, add these no-op stubs immediately after `renderHome()`. **Each subsequent task deletes its stub and replaces it with the real function.**

```js
    // Temporary stubs — each is replaced by its owning task (3–11). Delete the
    // matching stub when you implement the real renderer.
    function renderHomeHeader(o) {}
    function renderHomeStats(o) {}
    function renderFunnel(o) {}
    function renderHeatPanel(o) {}
    function renderRadar(o) {}
    function renderInventory(o) {}
    function renderAttention(o) {}
    function renderActivity(o) {}
    function renderCities(o) {}
    function applyRepLayout(role) {}
```

- [ ] **Step 8: Verify in the browser (or static review)**

Serve the dashboard on an allowed origin and load it with a manager token:

```bash
# Terminal A: cd bot && python main.py
# Terminal B: cd landing && python -m http.server 8080
# Browser: http://localhost:8080/dashboard/?token=<MGR_TOKEN>
```

Expected: the home page shows the empty stat/panel skeleton (containers present, no fake TechCorp/Razorpay/Groww rows anywhere), the browser console has no `ReferenceError`, and the Network tab shows a `200` on `/api/overview`. If browser automation is unavailable, statically confirm: (a) no `demo-box`/`TechCorp`/`Razorpay`/`Groww` strings remain in the file, (b) all ten stub functions exist, (c) `renderHome` references only ids that exist in the new skeleton. Load with `?token=<REP_TOKEN>` for a rep with zero leads → the explainer (welcome-box + steps) shows with **no** demo box.

- [ ] **Step 9: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): rewire home onto /api/overview, delete fake demo rows, add panel skeleton"
```

---

### Task 3: Command header (A) + 5-stat band (B)

**Files:**
- Modify: `landing/dashboard/index.html` — replace the `renderHomeHeader` and `renderHomeStats` stubs (from Task 2 Step 7); add stat CSS near `.stat-num` (~line 228).
- **Sequential** (same file; after Task 2).

**Interfaces:**
- Consumes: `overviewData.totals`, `overviewData.user`, `formatINR`, `esc`.
- Produces: real `renderHomeHeader(o)` and `renderHomeStats(o)` rendering into `#home-header` / `#home-stats`.

- [ ] **Step 1: Add stat-band CSS**

After the `.stat-num.b { color: var(--ink); }` rule (line 239), add:

```css
    .stat-num.won-line { font-size: 0.7rem; font-weight: 700; color: #15803D;
      margin-top: 2px; letter-spacing: 0; }
    .stat-num.red { color: #B91C1C; }
    .stat-sub { font-family: var(--sans); font-size: 0.62rem; color: var(--text-3);
      margin-top: 3px; font-variant-numeric: tabular-nums; }
```

- [ ] **Step 2: Replace the `renderHomeHeader` stub**

```js
    function renderHomeHeader(o) {
      const el = document.getElementById('home-header');
      const now = new Date();
      const dateStr = now.toLocaleDateString('en-IN',
        { weekday: 'long', day: 'numeric', month: 'long' });
      const hr = now.getHours();
      const part = hr < 12 ? 'morning' : hr < 17 ? 'afternoon' : 'evening';
      const name = (o.user && o.user.first_name) ? o.user.first_name : 'there';
      const t = o.totals;
      let pulse;
      if (t.active_leads === 0) {
        pulse = 'No active deals yet — forward a conversation to the bot to begin.';
      } else if (t.stalled_count > 0) {
        pulse = `${formatINR(t.pipeline_value)} in play across ${t.active_leads} active ` +
          `deals. ${t.stalled_count} need attention.`;
      } else {
        pulse = `${formatINR(t.pipeline_value)} in play across ${t.active_leads} active ` +
          `deals. Pipeline is moving.`;
      }
      el.innerHTML =
        `<div class="home-eyebrow">${esc(dateStr)}</div>` +
        `<div class="home-greeting">Good ${part}, ${esc(name)}.</div>` +
        `<div class="home-pulse">${esc(pulse)}</div>`;
    }
```

- [ ] **Step 3: Replace the `renderHomeStats` stub**

```js
    function renderHomeStats(o) {
      const t = o.totals;
      const stalledCls = t.stalled_count > 0 ? 'stat-num red' : 'stat-num';
      const wonSub = t.closed_won_value > 0
        ? `<div class="stat-num won-line">${formatINR(t.closed_won_value)}</div>` : '';
      document.getElementById('home-stats').innerHTML =
        card('Pipeline Value', formatINR(t.pipeline_value), 'stat-num') +
        card('Active Deals', t.active_leads, 'stat-num') +
        card('Won This Month', t.closed_won_count, 'stat-num g', wonSub) +
        card('Stalled', t.stalled_count, stalledCls) +
        card('Seats: Demand / Avail',
             `${t.seats_demanded} / ${t.seats_available}`, 'stat-num');

      function card(label, value, cls, extra) {
        return `<div class="stat-card">
          <div class="stat-lbl">${esc(label)}</div>
          <div class="${cls}">${esc(String(value))}</div>
          ${extra || ''}
        </div>`;
      }
    }
```

- [ ] **Step 4: Verify**

Reload `http://localhost:8080/dashboard/?token=<MGR_TOKEN>`. Expected: header shows the weekday/date eyebrow, "Good {morning/afternoon/evening}, {name}." in Manrope 800, and a pulse line matching the template — e.g. `₹X.X Cr in play across N active deals. M need attention.` (the ₹ figure via `formatINR`). The stat band shows five cards; "Won This Month" shows a green (`#15803D`) value figure beneath the count; "Stalled" is red (`#B91C1C`) only when > 0; the fifth reads `demand / available` seats. Static-review fallback: confirm both functions replaced their stubs and reference only `overviewData.totals`/`.user` keys defined in Task 1.

- [ ] **Step 5: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): home command header + 5-stat band"
```

---

### Task 4: Pipeline funnel chart (C)

**Files:**
- Modify: `landing/dashboard/index.html` — replace the `renderFunnel` stub; add funnel CSS near `.panel` (~line 251).
- **Sequential** (same file; after Task 3). Introduces the shared `.bar-row` markup pattern reused (by copy) in Tasks 5 and 7.

**Interfaces:**
- Consumes: `overviewData.funnel` (7 `{stage, count, value}`), `formatINR`, `esc`, `showPage`.
- Produces: real `renderFunnel(o)` rendering seven opacity-graded value bars into `#home-funnel`.

- [ ] **Step 1: Add funnel CSS**

After the `.panel { … }` rule (line 251), add:

```css
    .funnel-row { display: grid; grid-template-columns: 110px 1fr auto;
      align-items: center; gap: 10px; padding: 5px 0; cursor: pointer; }
    .funnel-row:hover .funnel-track { background: var(--border); }
    .funnel-stage { font-size: 0.72rem; font-weight: 600; color: var(--text-2); }
    .funnel-stage.lost { color: #B91C1C; }
    .funnel-track { position: relative; height: 22px; border-radius: 5px;
      background: var(--surface-2); overflow: hidden; }
    .funnel-fill { position: absolute; inset: 0 auto 0 0; height: 22px;
      border-radius: 5px; background: var(--ink); }
    .funnel-val { font-size: 0.72rem; font-weight: 600; color: var(--ink);
      font-variant-numeric: tabular-nums; white-space: nowrap; }
    .funnel-val.won { color: #15803D; }
```

- [ ] **Step 2: Replace the `renderFunnel` stub**

```js
    // Stepped opacity by funnel progress — darker = closer to money (vision §3).
    const FUNNEL_OPACITY = {
      'Inquiry': 0.18, 'Qualified': 0.32, 'Site Visit': 0.46, 'Proposal': 0.62,
      'Negotiation': 0.80, 'Closed-Won': 1.00, 'Closed-Lost': 0.12,
    };
    function renderFunnel(o) {
      const rows = o.funnel || [];
      const maxVal = Math.max(1, ...rows.map(r => r.value || 0));
      document.getElementById('home-funnel').innerHTML = rows.map(r => {
        const isLost = r.stage === 'Closed-Lost';
        const isWon  = r.stage === 'Closed-Won';
        // Zero-value stage → a 2px ink tick, not nothing (absence is information).
        const pct = r.value > 0 ? Math.max(2, Math.round((r.value / maxVal) * 100)) : 0;
        const widthCss = r.value > 0 ? pct + '%' : '2px';
        const opacity = FUNNEL_OPACITY[r.stage] ?? 0.5;
        return `<div class="funnel-row" onclick="showPage('pipeline')">
          <span class="funnel-stage${isLost ? ' lost' : ''}">${esc(r.stage)}</span>
          <div class="funnel-track">
            <div class="funnel-fill" style="width:${widthCss};opacity:${opacity}"></div>
          </div>
          <span class="funnel-val${isWon ? ' won' : ''}">${r.count} · ${formatINR(r.value)}</span>
        </div>`;
      }).join('');
    }
```

- [ ] **Step 3: Verify**

Reload with `<MGR_TOKEN>`. Expected: seven rows in `Inquiry … Closed-Lost` order; bar widths proportional to summed ₹ value (Negotiation/high-value stages widest); fills visibly darker down the funnel (Inquiry faint → Closed-Won solid ink); Closed-Lost label in red; each right value reads `count · ₹value` with Closed-Won's value green; a zero-value stage shows a thin 2px tick. Clicking a row navigates to the Pipeline page. Static fallback: confirm the opacity map covers all 7 exact stage strings from `db.STAGES`.

- [ ] **Step 4: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): pipeline funnel chart (value-weighted, opacity-graded)"
```

---

### Task 5: Heat strip + hottest deals (D)

**Files:**
- Modify: `landing/dashboard/index.html` — replace the `renderHeatPanel` stub; add heat-strip + hottest-row CSS near `.badge` (~line 323).
- **Sequential** (same file; after Task 4).

**Interfaces:**
- Consumes: `overviewData.heat` (`{hot, warm, cold}`), `overviewData.hottest` (≤4 lead cards), `formatINR`, `esc`, `heatOf`, `openContactDetail`.
- Produces: real `renderHeatPanel(o)` — a stacked heat strip + a top-4 hottest-deals list into `#home-heat`.

- [ ] **Step 1: Add CSS**

After the `.bc { … }` heat-badge rule (line 334), add:

```css
    .heat-strip { display: flex; height: 12px; border-radius: 6px; overflow: hidden;
      gap: 1px; margin: 4px 0 8px; }
    .heat-seg { height: 12px; }
    .heat-seg.hot  { background: var(--ink); }
    .heat-seg.warm { background: var(--border-2); }
    .heat-seg.cold { background: var(--surface-2); }
    .heat-legend { display: flex; gap: 14px; font-size: 0.68rem; color: var(--text-2);
      font-variant-numeric: tabular-nums; margin-bottom: 10px; }
    .heat-legend .dot { display: inline-block; width: 6px; height: 6px; border-radius: 2px;
      margin-right: 5px; vertical-align: middle; }
    .heat-legend .muted { color: var(--text-3); }
    .hot-row { display: grid; grid-template-columns: 1fr auto; gap: 8px;
      align-items: start; padding: 7px 0; border-top: 1px solid var(--border); cursor: pointer; }
    .hot-row:first-child { border-top: none; }
    .hot-co { font-weight: 700; font-size: 0.8rem; color: var(--ink); }
    .hot-meta { font-size: 0.68rem; color: var(--text-2); margin-top: 1px; }
    .hot-signal { font-size: 0.62rem; color: var(--text-3); margin-top: 2px; }
    .hot-right { text-align: right; white-space: nowrap; }
    .hot-val { font-size: 0.72rem; font-weight: 600; color: var(--ink);
      font-variant-numeric: tabular-nums; margin-top: 3px; }
```

- [ ] **Step 2: Replace the `renderHeatPanel` stub**

```js
    function renderHeatPanel(o) {
      const h = o.heat || { hot: 0, warm: 0, cold: 0 };
      const total = Math.max(1, h.hot + h.warm + h.cold);
      const seg = (n, cls) => n > 0
        ? `<div class="heat-seg ${cls}" style="flex:${n}"></div>` : '';
      const lbl = (n, cls, name) => `<span${n === 0 ? ' class="muted"' : ''}>` +
        `<span class="dot" style="background:${cls}"></span>${name} ${n}</span>`;
      const strip = `<div class="heat-strip">${seg(h.hot,'hot')}${seg(h.warm,'warm')}${seg(h.cold,'cold')}</div>` +
        `<div class="heat-legend">` +
        lbl(h.hot,  'var(--ink)',       'Hot')  +
        lbl(h.warm, 'var(--border-2)',  'Warm') +
        lbl(h.cold, 'var(--surface-2)', 'Cold') + `</div>`;

      const hottest = o.hottest || [];
      const rows = hottest.map(l => {
        const hb = heatOf(l);   // maps l.heat_score.label → badge bh/bw/bc
        // signal_tag pass-through; degrade to contact · seats · city if absent.
        const fallback = [l.contact_name, l.seat_count != null ? `${l.seat_count} seats` : null, l.city]
          .filter(Boolean).map(esc).join(' · ');
        const second = l.signal_tag ? esc(l.signal_tag) : fallback;
        return `<div class="hot-row" onclick="openContactDetail('${l.id}')">
          <div>
            <div class="hot-co">${esc(l.company || l.contact_name || '—')}</div>
            <div class="hot-meta">${fallback}</div>
            <div class="hot-signal">${second}</div>
          </div>
          <div class="hot-right">
            <span class="${hb.cls}">${hb.label} · ${hb.score}</span>
            <div class="hot-val">${formatINR(l.est_deal_value)}</div>
          </div>
        </div>`;
      }).join('');

      document.getElementById('home-heat').innerHTML = strip +
        (rows || '<div class="panel-empty">No active deals yet.</div>');
    }
```

- [ ] **Step 3: Verify**

Reload with `<MGR_TOKEN>`. Expected: a 12px stacked strip with three ink/grey/light segments sized by active-lead counts (1px white gaps), a legend `● Hot N · Warm N · Cold N` with swatch dots matching the segment fills, and beneath it up to 4 hottest deals sorted by heat score — each with company (700), a meta line, a signal-tag line (the `signal_tag` string, or `contact · seats · city` if null), a heat badge, and a right-aligned ₹ value. Rows click through to contact detail. Static fallback: confirm segment fills equal the badge fills (`var(--ink)`/`var(--border-2)`/`var(--surface-2)`).

- [ ] **Step 4: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): heat strip + hottest deals panel"
```

---

### Task 6: Site Visit Radar + Open-Meteo weather (E)

**Files:**
- Modify: `landing/dashboard/index.html` — replace the `renderRadar` stub; add a weather module (coords, fetch, WMO icons, chip builder) just above `renderRadar`; add radar CSS near `.panel` (~line 251).
- **Sequential** (same file; after Task 5).

**Interfaces:**
- Consumes: `overviewData.site_visits` (lead cards at stage `Site Visit`), `esc`, `showPage`, `openContactDetail`.
- Produces: real `renderRadar(o)`, plus module-scoped helpers `CITY_COORDS`, `fetchWeather(cities)`, `wmoIconKey(code)`, `WX_ICONS`, `weekdayShort(iso)`, `weatherChipHTML(city, daily)`. Weather is best-effort: on any failure, chips are hidden and the radar still renders (one `console.warn`, no error banner).

- [ ] **Step 1: Add radar CSS**

After the `.panel { … }` rule (line 251), add:

```css
    .radar-row { padding: 8px 0; border-top: 1px solid var(--border); }
    .radar-row:first-child { border-top: none; }
    .radar-line1 { font-size: 0.8rem; color: var(--ink); }
    .radar-co { font-weight: 700; }
    .radar-line1 .muted { color: var(--text-2); font-weight: 400; }
    .radar-typechip { display: inline-block; font-size: 0.6rem; padding: 1px 6px;
      border-radius: 5px; background: var(--surface-2); border: 1px solid var(--border-2);
      color: var(--text-2); margin-left: 4px; }
    .wx-chip { display: flex; align-items: center; gap: 6px; font-size: 0.72rem;
      color: var(--text-2); margin-top: 4px; font-variant-numeric: tabular-nums; }
    .wx-chip svg { flex: none; }
    .wx-cue { font-size: 0.68rem; color: var(--text-3); margin-top: 2px; }
    .movein-chip { display: inline-block; font-size: 0.6rem; padding: 1px 6px;
      border-radius: 5px; background: var(--surface-2); color: var(--text-2); margin-top: 4px; }
    .radar-link { display: inline-block; margin-top: 5px; font-size: 0.68rem;
      color: var(--ink); border-bottom: 1px solid var(--border-2); cursor: pointer; }
    .radar-link:hover { border-color: var(--ink); }
```

- [ ] **Step 2: Add the weather module + `renderRadar` (replacing the stub)**

Replace the `renderRadar` stub with the module below (the four icons are 16px, stroke-1.5, ink — no emoji, per repo rules):

```js
    // ── Site Visit Radar weather (Open-Meteo, client-side, keyless) ──
    // Coords for the six seeded cities only; unknown city → no chip, no error.
    const CITY_COORDS = {
      Bangalore: [12.97, 77.59], Delhi: [28.61, 77.21], Gurgaon: [28.46, 77.03],
      Hyderabad: [17.39, 78.49], Mumbai: [19.08, 72.88], Pune: [18.52, 73.86],
    };
    const WX_ICONS = {
      sun:  '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0A0A0A" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/></svg>',
      cloud:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0A0A0A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 18h11a4 4 0 0 0 .5-7.97A6 6 0 0 0 6 11a4 4 0 0 0 0 7Z"/></svg>',
      rain: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0A0A0A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 15h10a4 4 0 0 0 .5-7.97A6 6 0 0 0 6 8"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/></svg>',
      haze: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0A0A0A" stroke-width="1.5" stroke-linecap="round"><path d="M3 8h18M5 12h14M4 16h16"/></svg>',
    };
    function wmoIconKey(code) {
      if (code == null) return 'cloud';
      if (code === 0 || code === 1) return 'sun';
      if (code === 45 || code === 48) return 'haze';
      if (code >= 51) return 'rain';   // drizzle/rain/snow/thunder
      return 'cloud';                  // 2, 3
    }
    function weekdayShort(iso) {
      return new Date(iso + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'short' });
    }
    // Returns {} on any failure (chips simply won't render). 30-min sessionStorage cache.
    async function fetchWeather(cities) {
      const uniq = [...new Set(cities.filter(c => CITY_COORDS[c]))].sort();
      if (!uniq.length) return {};
      const cacheKey = 'siteline_wx_' + uniq.join(',');
      try {
        const cached = JSON.parse(sessionStorage.getItem(cacheKey) || 'null');
        if (cached && Date.now() - cached.t < 30 * 60 * 1000) return cached.data;
      } catch (e) { /* ignore corrupt cache */ }
      const lats = uniq.map(c => CITY_COORDS[c][0]).join(',');
      const lons = uniq.map(c => CITY_COORDS[c][1]).join(',');
      const url = 'https://api.open-meteo.com/v1/forecast?latitude=' + lats +
        '&longitude=' + lons +
        '&daily=weather_code,temperature_2m_max,precipitation_probability_max' +
        '&forecast_days=4&timezone=Asia%2FKolkata';
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('weather ' + res.status);
        const json = await res.json();
        const arr = Array.isArray(json) ? json : [json];  // multi- vs single-city
        const data = {};
        uniq.forEach((c, i) => { data[c] = (arr[i] && arr[i].daily) ? arr[i].daily : null; });
        sessionStorage.setItem(cacheKey, JSON.stringify({ t: Date.now(), data }));
        return data;
      } catch (e) {
        console.warn('[weather] fetch failed — rendering radar without chips', e);
        return {};
      }
    }
    function weatherChipHTML(city, daily) {
      if (!daily || !daily.temperature_2m_max) return '';
      const temps = daily.temperature_2m_max;
      const precip = daily.precipitation_probability_max || [];
      const codes = daily.weather_code || [];
      const dates = daily.time || [];
      const todayTemp = Math.round(temps[0]);
      const icon = WX_ICONS[wmoIconKey(codes[0])];
      let line = `${esc(city)} · ${todayTemp}° today`;
      // Wettest of the next 3 days (idx 1..3) for the warning half of the chip.
      let warnIdx = -1, warnMax = -1;
      for (let i = 1; i <= 3 && i < precip.length; i++) {
        if (precip[i] > warnMax) { warnMax = precip[i]; warnIdx = i; }
      }
      if (warnIdx > 0 && warnMax >= 60) {
        line += ` · Rain ${Math.round(warnMax)}% ${weekdayShort(dates[warnIdx])}`;
      }
      let cue = '';
      if (warnMax >= 60) {                          // driest day across the forecast
        let dryIdx = 0, dryMin = Infinity;
        for (let i = 0; i < precip.length; i++) {
          if (precip[i] < dryMin) { dryMin = precip[i]; dryIdx = i; }
        }
        cue = `<div class="wx-cue">${weekdayShort(dates[dryIdx])} is the dry window.</div>`;
      }
      return `<div class="wx-chip">${icon}<span>${line}</span></div>${cue}`;
    }

    function renderRadar(o) {
      const visits = o.site_visits || [];
      const el = document.getElementById('home-radar');
      if (!visits.length) {
        el.innerHTML = '<div class="panel-empty">No site visits scheduled.</div>';
        return;
      }
      const now = Date.now();
      // Render rows first (weather is enrichment, injected async into placeholders).
      el.innerHTML = visits.map(l => {
        const seats = l.seat_count != null ? `${l.seat_count} seats` : 'seats TBC';
        const type = l.space_type ? `<span class="radar-typechip">${esc(l.space_type)}</span>` : '';
        let movein = '';
        if (l.move_in_date) {
          const days = Math.round((new Date(l.move_in_date + 'T00:00:00').getTime() - now) / 86400000);
          if (days >= 0 && days <= 21) {
            const d = new Date(l.move_in_date + 'T00:00:00')
              .toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
            movein = `<div class="movein-chip">Move-in ${esc(d)}</div>`;
          }
        }
        const cityAttr = l.city ? esc(l.city) : '';
        return `<div class="radar-row">
          <div class="radar-line1" onclick="openContactDetail('${l.id}')" style="cursor:pointer">
            <span class="radar-co">${esc(l.company || l.contact_name || '—')}</span>
            <span class="muted"> · ${esc(l.contact_name || '')} · ${esc(seats)}</span>${type}
          </div>
          <div class="wx-slot" data-city="${cityAttr}"></div>
          ${movein}
          <span class="radar-link" onclick="showPage('home');document.getElementById('home-inventory').scrollIntoView({behavior:'smooth'})">Spaces in ${cityAttr || 'city'} &rarr;</span>
        </div>`;
      }).join('');

      // Enrich with weather (best-effort). Failure leaves the rows as-is.
      const cities = visits.map(l => l.city).filter(Boolean);
      fetchWeather(cities).then(wx => {
        el.querySelectorAll('.wx-slot').forEach(slot => {
          const city = slot.getAttribute('data-city');
          const daily = wx[city];
          if (daily) slot.innerHTML = weatherChipHTML(city, daily);
        });
      });
    }
```

- [ ] **Step 3: Verify (with network)**

Reload with `<MGR_TOKEN>` on a machine with internet. Expected: one row per `Site Visit`-stage lead (company/contact/seats + space-type chip), a weather chip line resolving shortly after load (ink SVG icon + `City · NN° today` and, when a coming day is wet, `· Rain NN% <Day>`), a "dry window" cue when any next-3-days precip ≥ 60%, a `Move-in DD Mmm` chip when the move-in is within 21 days, and a "Spaces in {city} →" link that scrolls to the inventory panel. Then **disable network / block `api.open-meteo.com`** and reload: the radar rows still render, chips are simply absent, exactly one `[weather] fetch failed` `console.warn`, and no error banner. Static fallback: confirm `fetchWeather` returns `{}` on every failure path and no code path throws out of it.

- [ ] **Step 4: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): site visit radar with Open-Meteo weather chips + dry-window cue"
```

---

### Task 7: Inventory pressure bars + demand tick (F)

**Files:**
- Modify: `landing/dashboard/index.html` — replace the `renderInventory` stub; add inventory CSS near `.panel` (~line 251).
- **Sequential** (same file; after Task 6).

**Interfaces:**
- Consumes: `overviewData.inventory` (`[{city, space_count, total_seats, available_seats, min_price_per_seat, demand_seats}]`), `formatINR`, `esc`.
- Produces: real `renderInventory(o)` rendering occupancy bars with an overlaid demand tick into `#home-inventory`.

- [ ] **Step 1: Add inventory CSS**

After the `.panel { … }` rule (line 251), add:

```css
    .inv-row { padding: 7px 0; border-top: 1px solid var(--border); }
    .inv-row:first-child { border-top: none; }
    .inv-head { display: flex; justify-content: space-between; align-items: baseline; }
    .inv-city { font-weight: 700; font-size: 0.78rem; color: var(--ink); }
    .inv-seats { font-size: 0.7rem; color: var(--text-2); font-variant-numeric: tabular-nums; }
    .inv-seats .over { color: #B91C1C; font-weight: 700; }
    .inv-track { position: relative; height: 12px; border-radius: 6px;
      background: var(--surface-2); overflow: hidden; margin: 5px 0 3px; }
    .inv-fill { position: absolute; inset: 0 auto 0 0; height: 12px; background: var(--ink);
      border-radius: 6px; }
    .inv-tick { position: absolute; top: 0; width: 2px; height: 12px; background: var(--ink); }
    .inv-sub { font-size: 0.66rem; color: var(--text-3); font-variant-numeric: tabular-nums; }
```

- [ ] **Step 2: Replace the `renderInventory` stub**

```js
    function renderInventory(o) {
      const rows = o.inventory || [];
      const el = document.getElementById('home-inventory');
      if (!rows.length) {
        el.innerHTML = '<div class="panel-empty">No inventory loaded.</div>';
        return;
      }
      el.innerHTML = rows.map(r => {
        const total = Math.max(1, r.total_seats);
        const occupied = Math.max(0, r.total_seats - r.available_seats);
        const occPct = Math.min(100, Math.round((occupied / total) * 100));
        // Where occupancy lands if the current pipeline closes.
        const projected = occupied + (r.demand_seats || 0);
        const tickPct = Math.min(100, Math.round((projected / total) * 100));
        const over = projected - total;
        const overTxt = over > 0 ? ` <span class="over">+${over} over</span>` : '';
        const price = r.min_price_per_seat != null
          ? ` · from ${formatINR(r.min_price_per_seat)}/seat` : '';
        return `<div class="inv-row">
          <div class="inv-head">
            <span class="inv-city">${esc(r.city)}</span>
            <span class="inv-seats">${occupied}/${r.total_seats} seats${overTxt}</span>
          </div>
          <div class="inv-track">
            <div class="inv-fill" style="width:${occPct}%"></div>
            <div class="inv-tick" style="left:calc(${tickPct}% - 1px)"></div>
          </div>
          <div class="inv-sub">${r.space_count} space${r.space_count === 1 ? '' : 's'}${price}</div>
        </div>`;
      }).join('');
    }
```

- [ ] **Step 3: Verify**

Reload with `<MGR_TOKEN>`. Expected: one row per inventory city (asc by city name), each with an ink occupancy fill on a light track, a 2px vertical ink demand tick further right (at `(occupied + pipeline seat demand) / total`), the `occupied/total seats` figure, and a subline `N spaces · from ₹X/seat` (min price via `formatINR`). Where projected demand exceeds capacity, the tick pins at 100% and the seats figure gains a red `+N over`. Static fallback: confirm the tick `left` never exceeds 100% and `over` only shows when positive.

- [ ] **Step 4: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): inventory pressure bars with demand tick"
```

---

### Task 8: Needs-a-human list + Nudge (G)

**Files:**
- Modify: `landing/dashboard/index.html` — replace the `renderAttention` stub; add `nudgeLead(leadId, btn)` helper; add attention CSS near `.panel` (~line 251).
- **Sequential** (same file; after Task 7).

**Interfaces:**
- Consumes: `overviewData.attention` (≤5 items), `currentUser.role`, `apiFetch` (for `POST /api/leads/{id}/nudge`, existing manager-only endpoint returning 204), `formatINR`, `esc`, `openContactDetail`.
- Produces: real `renderAttention(o)` + `async nudgeLead(leadId, btn)`. Reasons are template strings computed client-side (no AI). The **Nudge** button renders only for managers.

- [ ] **Step 1: Add attention CSS**

After the `.panel { … }` rule (line 251), add:

```css
    .att-row { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: center;
      padding: 8px 0; border-top: 1px solid var(--border); }
    .att-row:first-child { border-top: none; }
    .att-co { font-weight: 700; font-size: 0.8rem; color: var(--ink); cursor: pointer; }
    .att-reason { font-size: 0.68rem; color: var(--text-2); margin-top: 1px; }
    .att-right { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
    .att-days { font-size: 0.62rem; padding: 2px 7px; border-radius: 5px;
      background: var(--surface-2); color: var(--text-3); font-variant-numeric: tabular-nums; }
    .att-nudge { font-family: var(--sans); font-size: 0.62rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.08em; color: var(--ink); cursor: pointer;
      background: none; border: none; border-bottom: 1px solid var(--border-2); padding: 0 0 1px; }
    .att-nudge:hover { border-color: var(--ink); }
    .att-nudge:disabled { color: var(--text-3); cursor: default; border-color: transparent; }
```

- [ ] **Step 2: Replace the `renderAttention` stub + add `nudgeLead`**

```js
    // Reason line from fields already in the payload — template strings, no AI.
    function attentionReason(a) {
      const now = Date.now();
      if (a.move_in_date) {
        const days = Math.round((new Date(a.move_in_date + 'T00:00:00').getTime() - now) / 86400000);
        if (days >= 0 && days <= 14) return `Move-in in ${days} day${days === 1 ? '' : 's'}, needs a push`;
      }
      if (a.stage === 'Negotiation' && a.days_stalled >= 3) {
        return `In Negotiation, no activity for ${a.days_stalled} days`;
      }
      return `${a.days_stalled} day${a.days_stalled === 1 ? '' : 's'} quiet in ${a.stage}`;
    }
    function renderAttention(o) {
      const rows = o.attention || [];
      const el = document.getElementById('home-attention');
      if (!rows.length) {
        el.innerHTML = '<div class="panel-empty">Nothing needs a human right now.</div>';
        return;
      }
      const isManager = currentUser && currentUser.role === 'manager';
      el.innerHTML = rows.map(a => {
        const nudge = isManager
          ? `<button class="att-nudge" onclick="nudgeLead('${a.lead_id}', this)">Nudge</button>` : '';
        return `<div class="att-row">
          <div>
            <div class="att-co" onclick="openContactDetail('${a.lead_id}')">${esc(a.company || a.contact_name || '—')}</div>
            <div class="att-reason">${esc(attentionReason(a))}</div>
          </div>
          <div class="att-right">
            <span class="att-days">${a.days_stalled}d</span>
            ${nudge}
          </div>
        </div>`;
      }).join('');
    }
    async function nudgeLead(leadId, btn) {
      btn.disabled = true;
      const original = btn.textContent;
      try {
        await apiFetch('/api/leads/' + leadId + '/nudge', { method: 'POST' });
        btn.textContent = 'Nudged';
      } catch (e) {
        btn.textContent = 'Failed';
        btn.disabled = false;
        console.warn('[nudge] failed for lead ' + leadId, e);
        setTimeout(() => { btn.textContent = original; }, 2500);
      }
    }
```

- [ ] **Step 3: Verify**

Reload with `<MGR_TOKEN>`. Expected: up to 5 rows (stalled ∪ hot-with-imminent-move-in ∪ quiet-Negotiation), sorted by days-stalled desc, each with company (700), a template reason line ("9 days quiet in Proposal" / "In Negotiation, no activity for N days" / "Move-in in N days, needs a push"), a monochrome `Nd` chip, and a **Nudge** ghost button. Clicking Nudge calls `POST /api/leads/{id}/nudge`: because the bot isn't polling (`TELEGRAM_BOT_TOKEN` blank), expect the endpoint's `503`/`409` path → the button shows "Failed" then resets (this is correct behavior; the 204 success path is exercised in the Phase 9 demo with a live bot). Reload with `<REP_TOKEN>` (a rep who owns a stalled lead) → rows render **without** any Nudge button. Static fallback: confirm the Nudge button is gated on `currentUser.role === 'manager'`.

- [ ] **Step 4: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): needs-a-human panel with manager nudge action"
```

---

### Task 9: Live activity feed (H) + rep-empty wiring

**Files:**
- Modify: `landing/dashboard/index.html` — replace the `renderActivity` stub; wire the feed into the rep-empty branch of `renderHome()` (from Task 2 Step 6); add activity CSS + type icons near `.panel` (~line 251).
- **Sequential** (same file; after Task 8).

**Interfaces:**
- Consumes: `overviewData.activity` (≤10 items, platform-wide), `esc`, `timeAgo` (existing), `openContactDetail`.
- Produces: real `renderActivity(o)` rendering into `#home-activity`; the same feed is also injected below the explainer in the rep-empty state.

- [ ] **Step 1: Add activity CSS + type-icon map**

After the `.panel { … }` rule (line 251), add:

```css
    .act-row { display: grid; grid-template-columns: 20px 1fr auto; gap: 8px; align-items: start;
      padding: 7px 0; border-top: 1px solid var(--border); }
    .act-row:first-child { border-top: none; }
    .act-row.newest { border-left: 2px solid var(--ink); padding-left: 8px; margin-left: -10px; }
    .act-icon svg { display: block; margin-top: 2px; }
    .act-summary { font-size: 0.75rem; color: var(--ink); line-height: 1.4;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .act-co { font-size: 0.64rem; color: var(--text-3); margin-top: 1px; }
    .act-time { font-size: 0.64rem; color: var(--text-3); font-variant-numeric: tabular-nums;
      white-space: nowrap; }
    .act-empty-feed { margin-top: 20px; }
```

- [ ] **Step 2: Replace the `renderActivity` stub**

```js
    // 16px ink icons (stroke 1.5) per interaction type — chat/mic/camera/pencil.
    const ACT_ICONS = {
      whatsapp_forward: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0A0A0A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.5 8.5 0 0 1-12.5 7.5L3 21l2-5.5A8.5 8.5 0 1 1 21 11.5Z"/></svg>',
      voice_note: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0A0A0A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M6 11a6 6 0 0 0 12 0M12 17v4"/></svg>',
      screenshot: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0A0A0A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="18" height="14" rx="2"/><circle cx="12" cy="13" r="3.5"/><path d="M8 6l1.5-2h5L16 6"/></svg>',
      addnote_command: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0A0A0A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
    };
    function activityRowsHTML(items) {
      return items.map((a, i) => {
        const icon = ACT_ICONS[a.type] || ACT_ICONS.addnote_command;
        return `<div class="act-row${i === 0 ? ' newest' : ''}" ${a.lead_id ? `onclick="openContactDetail('${a.lead_id}')" style="cursor:pointer"` : ''}>
          <span class="act-icon">${icon}</span>
          <div>
            <div class="act-summary">${esc(a.ai_summary || '—')}</div>
            <div class="act-co">${esc(a.company || '')}${a.user_name ? ' · ' + esc(a.user_name) : ''}</div>
          </div>
          <span class="act-time">${esc(timeAgo(a.logged_at))}</span>
        </div>`;
      }).join('');
    }
    function renderActivity(o) {
      const items = o.activity || [];
      const el = document.getElementById('home-activity');
      el.innerHTML = items.length
        ? activityRowsHTML(items)
        : '<div class="panel-empty">No activity yet.</div>';
    }
```

- [ ] **Step 3: Wire the feed into the rep-empty branch of `renderHome()`**

In `renderHome()` (Task 2), replace the rep-empty branch body:

```js
      if (!scopeHasLeads && role !== 'manager') {
        dataEl.classList.add('hidden');
        emptyEl.classList.remove('hidden');
        // Task 9 replaces the deleted demo-box with the real activity feed here.
        return;
      }
```

with:

```js
      if (!scopeHasLeads && role !== 'manager') {
        dataEl.classList.add('hidden');
        emptyEl.classList.remove('hidden');
        // Replace the deleted demo-box with the REAL platform activity feed
        // (read-scoped) — the "yours will appear here" promise, shown with true
        // data instead of fabricated rows. Cold-start (no activity) shows nothing.
        let feed = document.getElementById('empty-activity-feed');
        if (!feed) {
          feed = document.createElement('div');
          feed.id = 'empty-activity-feed';
          feed.className = 'panel act-empty-feed';
          emptyEl.appendChild(feed);
        }
        const items = (overviewData.activity || []);
        feed.innerHTML = items.length
          ? '<div class="panel-hd"><span class="panel-title">Live Activity</span></div>' +
            activityRowsHTML(items)
          : '';
        return;
      }
```

- [ ] **Step 4: Verify**

Reload with `<MGR_TOKEN>`. Expected: the Live Activity panel shows ≤10 reverse-chron interactions — each a 16px ink type icon (chat/mic/camera/pencil by `type`), the `ai_summary` truncated to one line, a `company · user` subline, and a relative time (`2 days ago`) right-aligned; only the newest row carries the `border-left: 2px solid var(--ink)` accent. Rows click through to contact detail. Reload with a zero-lead `<REP_TOKEN>` → the explainer shows, and below it the same real activity feed appears (no fake rows). Static fallback: confirm `ACT_ICONS` covers all four `interaction_type` enum values.

- [ ] **Step 5: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): live activity feed + real feed in rep empty state"
```

---

### Task 10: City footprint strip (I)

**Files:**
- Modify: `landing/dashboard/index.html` — replace the `renderCities` stub; add city CSS near `.panel` (~line 251).
- **Sequential** (same file; after Task 9). *(First cut candidate if budget slips — see cut order.)*

**Interfaces:**
- Consumes: `overviewData.by_city` (`[{city, active_count, pipeline_value}]` desc by value), `formatINR`, `esc`.
- Produces: real `renderCities(o)` rendering a horizontal row of city cards (max 6) into `#home-cities`, each with a share-of-pipeline underline bar.

- [ ] **Step 1: Add city CSS**

After the `.panel { … }` rule (line 251), add:

```css
    .city-strip { display: flex; gap: 20px; flex-wrap: wrap; }
    .city-card { min-width: 120px; }
    .city-name { font-weight: 700; font-size: 0.8rem; color: var(--ink); }
    .city-figs { font-size: 0.68rem; color: var(--text-2); margin-top: 2px;
      font-variant-numeric: tabular-nums; }
    .city-bar { height: 3px; background: var(--ink); border-radius: 2px; margin-top: 6px;
      min-width: 4px; }
```

- [ ] **Step 2: Replace the `renderCities` stub**

```js
    function renderCities(o) {
      const rows = (o.by_city || []).slice(0, 6);
      const el = document.getElementById('home-cities');
      if (!rows.length) {
        el.innerHTML = '<div class="panel-empty">No city activity yet.</div>';
        return;
      }
      const maxVal = Math.max(1, ...rows.map(r => r.pipeline_value || 0));
      el.innerHTML = '<div class="city-strip">' + rows.map(r => {
        const pct = Math.max(4, Math.round((r.pipeline_value / maxVal) * 100));
        return `<div class="city-card">
          <div class="city-name">${esc(r.city)}</div>
          <div class="city-figs">${r.active_count} deal${r.active_count === 1 ? '' : 's'} · ${formatINR(r.pipeline_value)}</div>
          <div class="city-bar" style="width:${pct}%"></div>
        </div>`;
      }).join('') + '</div>';
    }
```

- [ ] **Step 3: Verify**

Reload with `<MGR_TOKEN>`. Expected: a horizontal strip of up to 6 city cards (desc by pipeline value), each with city name (700), `N deals · ₹value`, and a 3px ink underline whose width is proportional to that city's share of the max pipeline value. Static fallback: confirm the widest city bar is the highest-value city and no bar exceeds 100%.

- [ ] **Step 4: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): city footprint strip with share bars"
```

---

### Task 11: Rep-scoped home variant (§6)

**Files:**
- Modify: `landing/dashboard/index.html` — replace the `applyRepLayout` stub (from Task 2 Step 7).
- **Sequential** (same file; last — depends on all panels existing).

**Interfaces:**
- Consumes: `currentUser.role`, the DOM structure built by Tasks 2–10.
- Produces: real `applyRepLayout(role)` — for a rep, reorders the Site Visit Radar row above the funnel row (the radar is the rep's literal to-do list). Nudge already drops out for reps (Task 8); stat framing already scopes via the endpoint (Task 1). No fork — a conditional reorder only.

- [ ] **Step 1: Replace the `applyRepLayout` stub**

```js
    // Rep-scoped home differences (vision §6): the endpoint already scopes the
    // stat band to the rep's pipeline, and the Nudge button already drops out
    // for reps (Task 8). The only visual change is ordering the Site Visit Radar
    // — the rep's actual to-do list — above the funnel. Managers keep funnel-first.
    function applyRepLayout(role) {
      const dataEl = document.getElementById('home-data');
      const grids = dataEl.querySelectorAll('.home-grid');
      if (!grids.length) return;
      const funnelRow = document.getElementById('home-funnel').closest('.home-grid');
      const radarRow  = document.getElementById('home-radar').closest('.home-grid');
      if (!funnelRow || !radarRow) return;
      if (role === 'rep' && radarRow !== funnelRow) {
        // Idempotent: only move if the radar row isn't already first.
        if (dataEl.querySelector('.home-grid') !== radarRow) {
          dataEl.insertBefore(radarRow, funnelRow);
        }
      } else if (role === 'manager') {
        // Restore funnel-first if a prior rep render moved things (shared page object).
        if (dataEl.querySelector('.home-grid') !== funnelRow) {
          dataEl.insertBefore(funnelRow, radarRow);
        }
      }
    }
```

- [ ] **Step 2: Verify both roles**

Reload with `<REP_TOKEN>` (a rep who owns leads). Expected: the Site Visit Radar / Inventory row now sits **above** the Pipeline / Heat row; the stat band reflects only that rep's pipeline (scoped by the endpoint); no Nudge buttons. Reload with `<MGR_TOKEN>` in the same browser session (page object reused) → the funnel row is back on top. Static fallback: confirm `applyRepLayout` is idempotent (re-running for the same role doesn't keep shuffling) and restores manager order.

- [ ] **Step 3: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): rep-scoped home — radar-first layout"
```

---

## Self-Review (run against the vision doc's P1 items)

**1. Spec coverage — every `[P1]` item maps to a task:**

| Vision P1 item (§7 table) | Task |
|---|---|
| `GET /api/overview` | Task 1 |
| Fake-demo deletion + empty-state rekey | Task 2 |
| A — Command header + templated pulse | Task 3 |
| B — 5-stat band incl. seats demand/supply | Task 3 |
| C — Funnel chart (opacity-graded, value-weighted) | Task 4 |
| D — Heat strip + hottest deals (+ signal_tag pass-through) | Task 5 |
| E — Site Visit Radar + Open-Meteo + dry-window cue | Task 6 |
| F — Inventory pressure bars + demand tick | Task 7 |
| G — Needs-a-human list + Nudge | Task 8 |
| H — Activity feed | Task 9 |
| I — City strip with share bars | Task 10 |
| Rep-scoped variant | Task 11 |

12 P1 items → 11 tasks (A+B share Task 3 per the vision's "header/stats" grouping). No P1 item is unassigned. No P2 item is planned (AI pulse/brief, stat sparklines, activity sparkline, 60s polling + filters, AQI/best-day/travel-time, match-digest lines, SVG India map, `GET /api/spaces`, velocity analytics, snapshots table — all deliberately excluded).

**2. Placeholder scan:** No "TBD/TODO/handle edge cases/add validation" left. The Task 2 Step 7 stubs are explicit, named no-ops each deleted by its owning task — a deliberate scaffold, not an unfilled placeholder, and every one is replaced with real code before the plan ends. Every code step contains complete, runnable content.

**3. Type consistency:** Payload keys are defined once in Task 1's Produces block and consumed verbatim downstream — `totals.{pipeline_value,active_leads,closed_won_count,closed_won_value,stalled_count,seats_demanded,seats_available}` (Task 3), `funnel[].{stage,count,value}` (Task 4), `heat.{hot,warm,cold}` + `hottest[]` lead cards with `signal_tag` (Task 5), `site_visits[]` lead cards (Task 6), `inventory[].{city,space_count,total_seats,available_seats,min_price_per_seat,demand_seats}` (Task 7), `attention[].{lead_id,company,contact_name,stage,est_deal_value,days_stalled,move_in_date,assigned_to}` (Task 8), `activity[].{id,lead_id,company,type,ai_summary,user_name,logged_at}` (Task 9), `by_city[].{city,active_count,pipeline_value}` (Task 10). Render function names are consistent between the Task 2 dispatcher, the Task 2 stubs, and each task's replacement: `renderHomeHeader, renderHomeStats, renderFunnel, renderHeatPanel, renderRadar, renderInventory, renderAttention, renderActivity, renderCities, applyRepLayout`. Existing helpers used at their real signatures: `apiFetch(path, opts)`, `formatINR(n)`, `esc(str)`, `heatOf(lead)`, `timeAgo(dateStr)`, `showPage(name)`, `openContactDetail(leadId)`, `_company_names`, `_public_user`, `db.get_all_leads/get_stale_leads/get_all_spaces/get_all_users`, `ACTIVE_STAGES`, `NUDGE_STALE_DAYS`.

Self-review passed clean; no gaps found.
