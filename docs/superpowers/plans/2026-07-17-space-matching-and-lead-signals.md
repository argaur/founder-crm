# Space Matching + Lead Signal Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Feature A (auto space-matching engine: bot follow-up message, API endpoint, dashboard card) and Feature C (deterministic "why this lead, why now" signal tag on every lead) from the approved design spec, plus a `/dashboard` bot command (Tasks 9-10) so returning users can get back into the dashboard without re-registering through the web signup form.

**Architecture:** Pure scoring/synthesis functions live in `bot/db.py` next to `calculate_heat_score()` (computed at read time, never stored). One new authenticated endpoint in `bot/main.py`. A follow-up Telegram message appended to `_save_capture()` in `bot/flows.py`. Dashboard renders a "Suggested Matches" card on contact detail and signal-tag sublines on three list views. Matching is done in Python after one `get_all_spaces(city)` fetch — the `spaces` table has 10 rows; SQL ranking is a deliberate non-goal.

**Tech Stack:** Python 3.11 / asyncpg / FastAPI / python-telegram-bot v21 (all async) on the bot side; vanilla HTML/JS (no framework, no bundler) on the dashboard side. Neon Postgres (project `winter-haze-14475661`).

**Spec:** `docs/superpowers/specs/2026-07-17-space-matching-and-lead-signals-design.md` — formulas, statuses, and copy in this plan are copied from it verbatim. If they ever disagree, the spec wins.

## Global Constraints

- **No schema changes, no migrations, no new AI calls, no new dependencies.** Everything composes existing data through existing async patterns.
- **`available_seats` is never decremented** — matching is a read-only suggestion engine.
- **No minimum-score cutoff** — hard filters do all disqualifying; a low score is information, not exclusion.
- **Feature B (AI next-best-action) is NOT built.** Do not create any code for it.
- **No bot-side rendering of signal tags** — dashboard-only for Feature C.
- Every `db.*` call must be `await`ed (`db.py` is fully async).
- No silent `except` — failures log via `logger.exception`, loudly.
- Dashboard styling: DESIGN_BRIEF light/monochrome only — reuse existing `badge bh/bw/bc`, `stage-chip`, muted text classes; **no new colors**.
- Telegram callback data separator stays `:` (not that these features add callbacks — no inline buttons on match messages in v1).
- **Verification style:** this project has NO test framework (documented in `bot/CLAUDE.md`). "Failing test" = a standalone verify script under `bot/scripts/verify_*.py` (pure functions) or a real `curl` round-trip / manual walkthrough (API/bot/dashboard). Verify scripts are throwaway: **never `git add` them** (note: `bot/scripts/` is currently untracked wholesale — always `git add` specific files by name, never the directory); Task 8 deletes them.
- Run all Python from `bot/` (`cd bot && python ...`) so `load_dotenv()` picks up `bot/.env` (`DATABASE_URL` and `DASHBOARD_TOKEN_SECRET` are set; `TELEGRAM_BOT_TOKEN`/`OPENAI_API_KEY` are deliberately blank — server runs in API-only mode, which is all Tasks 1–5, 7, 8 need).
- Commit after every task. No `--force`, no `--no-verify`.

## Reference: fixed data this plan asserts against

Seeded by `bot/scripts/apply_schema.py` (spaces, 10 rows) and `bot/seed.py --seed` (users/leads). Space columns: `id, name, city, locality, total_seats, available_seats, price_per_seat (NUMERIC), space_type`.

| Space | City | Available | Price | Type |
|---|---|---|---|---|
| WorkHub Cyber City | Gurgaon | 120 | 8000 | Dedicated Desk |
| WorkHub DLF Phase 3 | Gurgaon | 340 | 7500 | Managed Office |
| Stylework Nehru Place | Delhi | 60 | 9000 | Private Cabin |
| Stylework Connaught Place | Delhi | 40 | 12000 | Private Cabin |
| WorkHub Koramangala | Bangalore | 180 | 8500 | Dedicated Desk |
| Stylework Whitefield | Bangalore | 410 | 7000 | Managed Office |
| WorkHub Andheri East | Mumbai | 90 | 10000 | Dedicated Desk |
| Stylework BKC | Mumbai | 20 | 15000 | Private Cabin |
| WorkHub Hitech City | Hyderabad | 200 | 6500 | Managed Office |
| Stylework Baner | Pune | 100 | 6000 | Dedicated Desk |

Seed users (fixed negative `telegram_id`s): manager Himanshu Rao `-900001`; reps Priya Nair `-900002`, Arjun Dev `-900003`. Useful seeded leads: Anita Rao (Razorpay, Bangalore, 40 seats, Private Cabin, ₹9000/seat, assigned Priya, 1 day quiet); Karan Mehta (Cred, Mumbai, assigned **Arjun** — use for 403 tests); Rahul Gupta (Swiggy, Hyderabad, 300 seats — undersized vs. max 200); Divya Shah (Meesho, Bangalore, 20 days quiet — stalled).

---

### Task 1: Pure scoring functions in `bot/db.py`

**Files:**
- Modify: `bot/db.py` (append a new `# --- SPACE MATCHING ---` section at end of file, after `get_all_spaces`, line 389)
- Verify script (throwaway, never committed): `bot/scripts/verify_scoring.py`

**Interfaces:**
- Consumes: nothing new (stdlib `math`, `datetime` already imported in `db.py`).
- Produces:
  - `MATCH_REQUIRED_FIELDS: tuple` — documentation constant `("city", "seat_count")`
  - `is_matchable(lead: Dict[str, Any]) -> bool`
  - `score_space_for_lead(lead: Dict[str, Any], space: Dict[str, Any]) -> Dict[str, Any]` returning `{"score": int, "reasons": List[str]}`
  - Task 2 (`get_matches_for_lead`), Task 6 (bot), Task 4 (API) all build on these exact names/shapes.

- [ ] **Step 1: Write the failing verify script**

Create `bot/scripts/verify_scoring.py`:

```python
"""Throwaway verification for db.is_matchable / db.score_space_for_lead.

Pure functions only — no DB, no network. Run from bot/:
    python scripts/verify_scoring.py
Exits 0 with 'ALL PASS' or raises AssertionError.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decimal import Decimal

import db

# ── is_matchable ──────────────────────────────────────────────
assert db.is_matchable({}) is False
assert db.is_matchable({"city": "Bangalore"}) is False
assert db.is_matchable({"city": "Bangalore", "seat_count": 0}) is False
assert db.is_matchable({"city": "Bangalore", "seat_count": None}) is False
assert db.is_matchable({"city": "Bangalore", "seat_count": 50}) is True
print("is_matchable: PASS")

# ── Case A: exact type, under budget, tight capacity → >= 90 ──
lead = {"city": "Bangalore", "seat_count": 50, "space_type": "Dedicated Desk",
        "budget_per_seat": 8000}
space = {"id": 1, "name": "Test", "city": "Bangalore", "available_seats": 55,
         "price_per_seat": 7500, "space_type": "Dedicated Desk"}
r = db.score_space_for_lead(lead, space)
# budget 45 (under budget) + type 30 + capacity 25*50/55=22.727 → round(97.727)=98
assert r["score"] == 98, r
assert r["score"] >= 90
assert "Exact space type" in r["reasons"], r["reasons"]
assert "₹7,500/seat vs ₹8,000 budget (6% under)" in r["reasons"], r["reasons"]
assert "55 seats free for 50" in r["reasons"], r["reasons"]
print("case A (exact/at-budget/tight): PASS")

# ── Case A2: Decimal boundary (asyncpg NUMERIC) — same result ─
lead_d = dict(lead, budget_per_seat=Decimal("8000"))
space_d = dict(space, price_per_seat=Decimal("7500"))
assert db.score_space_for_lead(lead_d, space_d)["score"] == 98
print("case A2 (Decimal boundary): PASS")

# ── Case B: 15% over budget → budget component ≈ 22 ───────────
# type mismatch (0) + huge capacity (25*50/5000=0.25) isolate the budget term:
# 45 * (1 - 0.15/0.3) = 22.5 → round(22.5 + 0 + 0.25) = 23
lead_b = {"city": "X", "seat_count": 50, "space_type": "Dedicated Desk",
          "budget_per_seat": 8000}
space_b = {"id": 2, "name": "T", "city": "X", "available_seats": 5000,
           "price_per_seat": 9200, "space_type": "Private Cabin"}
r = db.score_space_for_lead(lead_b, space_b)
assert r["score"] == 23, r
print("case B (15% over ≈ 22): PASS")

# ── Case C: 35% over budget → budget component 0 (still scored) ─
r = db.score_space_for_lead(lead_b, dict(space_b, price_per_seat=10800))
assert r["score"] == 0, r  # 0 + 0 + 0.25 → 0; a dict is still returned
print("case C (>=30% over → 0): PASS")

# ── Case D: lead has no budget → neutral 22 ───────────────────
lead_nb = {"city": "X", "seat_count": 50, "space_type": "Dedicated Desk",
           "budget_per_seat": None}
space_nb = {"id": 3, "name": "T", "city": "X", "available_seats": 125,
            "price_per_seat": 7500, "space_type": "Dedicated Desk"}
r = db.score_space_for_lead(lead_nb, space_nb)
assert r["score"] == 62, r  # 22 + 30 + 25*50/125=10 → 62
print("case D (no budget → neutral 22): PASS")

# ── Case E: space has no price → neutral 22, not zero ─────────
lead_e = {"city": "X", "seat_count": 50, "space_type": "Managed Office",
          "budget_per_seat": 8000}
space_e = {"id": 4, "name": "T", "city": "X", "available_seats": 125,
           "price_per_seat": None, "space_type": "Dedicated Desk"}
r = db.score_space_for_lead(lead_e, space_e)
assert r["score"] == 32, r  # 22 + 0 (mismatch) + 10 → 32
print("case E (null price → neutral): PASS")

# ── Case F: lead has no space_type → type neutral 15 ──────────
lead_f = {"city": "X", "seat_count": 50, "space_type": None, "budget_per_seat": None}
r = db.score_space_for_lead(lead_f, space_nb)
assert r["score"] == 47, r  # 22 + 15 + 10 → 47
print("case F (no space_type → neutral 15): PASS")

print("ALL PASS")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd bot && python scripts/verify_scoring.py`
Expected: `AttributeError: module 'db' has no attribute 'is_matchable'`

- [ ] **Step 3: Implement in `bot/db.py`**

Append at end of file (after `get_all_spaces`, which ends at line 388):

```python
# --- SPACE MATCHING (Feature A) ---
# Pure functions + one async wrapper (Task 2). Same precedent as
# calculate_heat_score: computed at read time, never stored. Matching is done
# in Python after a single get_all_spaces(city) fetch — the spaces table has
# ~10 rows; SQL ranking is deliberate non-scope (see design doc 2026-07-17).
# available_seats is NEVER decremented here — read-only suggestion engine.

MATCH_REQUIRED_FIELDS = ("city", "seat_count")  # budget/space_type optional


def is_matchable(lead: Dict[str, Any]) -> bool:
    """True if the lead has a city and a positive seat_count."""
    if not lead.get("city"):
        return False
    try:
        return int(lead.get("seat_count") or 0) > 0
    except (TypeError, ValueError):
        return False


def score_space_for_lead(lead: Dict[str, Any], space: Dict[str, Any]) -> Dict[str, Any]:
    """Pure 0-100 match score. Assumes hard filters already passed
    (same city, available_seats >= seat_count).

    Weights: budget fit 45, space type 30, capacity fit 25.
    Returns {"score": int, "reasons": List[str]} — reasons are short human
    strings, ordered [type?, budget?, capacity].
    """
    seat_count = int(lead["seat_count"])
    available = int(space["available_seats"])
    reasons: List[str] = []

    # Budget fit (max 45). NUMERIC columns arrive as Decimal from asyncpg —
    # float() at the boundary, same as calculate_heat_score does.
    budget = float(lead["budget_per_seat"]) if lead.get("budget_per_seat") else None
    price = float(space["price_per_seat"]) if space.get("price_per_seat") else None
    if budget and price:
        over = max(0.0, price / budget - 1)
        budget_points = 45.0 * max(0.0, 1 - over / 0.3)
        if price <= budget:
            pct_under = round((1 - price / budget) * 100)
            if pct_under > 0:
                reasons.append(
                    f"₹{price:,.0f}/seat vs ₹{budget:,.0f} budget ({pct_under}% under)"
                )
            else:
                reasons.append(f"₹{price:,.0f}/seat at budget")
        else:
            reasons.append(f"₹{price:,.0f}/seat ({round(over * 100)}% over budget)")
    else:
        budget_points = 22.0  # either value missing/null → neutral
        if price:
            reasons.append(f"₹{price:,.0f}/seat")

    # Space type (max 30) — preferred, never required. A Managed Office lead
    # should still see a great Private Cabin deal, just ranked lower.
    lead_type = lead.get("space_type")
    if lead_type and space.get("space_type") == lead_type:
        type_points = 30.0
        reasons.insert(0, "Exact space type")
    elif not lead_type:
        type_points = 15.0  # lead has no preference → neutral
    else:
        type_points = 0.0

    # Capacity fit (max 25) — right-sizing: 50 into 60 beats 50 into 500.
    # Hard filter guarantees ratio <= 1, no clamp needed.
    capacity_points = 25.0 * (seat_count / available) if available else 0.0
    reasons.append(f"{available} seats free for {seat_count}")

    return {
        "score": int(round(budget_points + type_points + capacity_points)),
        "reasons": reasons,
    }
```

- [ ] **Step 4: Run the verify script — all cases pass**

Run: `cd bot && python scripts/verify_scoring.py`
Expected: 8 `PASS` lines, ending `ALL PASS`, exit 0.

- [ ] **Step 5: Commit (db.py only — never the verify script)**

```bash
git add bot/db.py
git commit -m "feat(db): pure space-match scoring (is_matchable, score_space_for_lead)"
```

---

### Task 2: `get_matches_for_lead` status engine in `bot/db.py`

**Files:**
- Modify: `bot/db.py` (append to the `# --- SPACE MATCHING ---` section from Task 1)
- Verify script (throwaway, never committed): `bot/scripts/verify_matching.py`

**Interfaces:**
- Consumes: `is_matchable`, `score_space_for_lead` (Task 1), existing `get_all_spaces(city)` (already case-insensitive on city in SQL — this IS the cross-city hard filter).
- Produces: `async get_matches_for_lead(lead: Dict[str, Any], limit: int = 3) -> Dict[str, Any]` returning `{"status": str, "matches": List[dict], "largest_available": Optional[int]}`. `status` is one of `"ok" | "not_enough_info" | "no_city_inventory" | "undersized_inventory"` — the single source of truth for every surface's empty-state copy (Tasks 4, 6, 7 switch on these exact strings). Each match = full space dict + `"score"` + `"reasons"`, with `price_per_seat` converted to plain `float` (JSON-ready).

- [ ] **Step 1: Write the failing verify script**

Create `bot/scripts/verify_matching.py`:

```python
"""Throwaway verification for db.get_matches_for_lead.

Part 1 monkeypatches db.get_all_spaces (deterministic tie-break/null cases,
no DB). Part 2 hits the real Neon spaces table (10 seeded rows — see
scripts/apply_schema.py). Run from bot/:
    python scripts/verify_matching.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio

import db

FAKE_SPACES = [
    {"id": 1, "name": "Alpha", "city": "Testville", "locality": None,
     "total_seats": 200, "available_seats": 125, "price_per_seat": 9000,
     "space_type": "Dedicated Desk"},
    {"id": 2, "name": "Bravo", "city": "Testville", "locality": None,
     "total_seats": 200, "available_seats": 125, "price_per_seat": 7000,
     "space_type": "Dedicated Desk"},
    {"id": 3, "name": "Delta", "city": "Testville", "locality": None,
     "total_seats": 200, "available_seats": 125, "price_per_seat": None,
     "space_type": "Dedicated Desk"},
    {"id": 4, "name": "Tiny", "city": "Testville", "locality": None,
     "total_seats": 30, "available_seats": 20, "price_per_seat": 5000,
     "space_type": "Day Pass"},
]

async def fake_get_all_spaces(city=None):
    return [s for s in FAKE_SPACES if s["city"].lower() == (city or "").lower()]

async def part1_monkeypatched():
    real = db.get_all_spaces
    db.get_all_spaces = fake_get_all_spaces
    try:
        # Tie-break: no budget on lead → Alpha/Bravo/Delta all score
        # 22 + 30 + 25*50/125 = 62. Cheaper price first, nulls last.
        lead = {"city": "Testville", "seat_count": 50,
                "space_type": "Dedicated Desk", "budget_per_seat": None}
        r = await db.get_matches_for_lead(lead)
        assert r["status"] == "ok", r
        names = [m["name"] for m in r["matches"]]
        assert names == ["Bravo", "Alpha", "Delta"], names  # 7000 < 9000 < null
        assert all(m["score"] == 62 for m in r["matches"]), r["matches"]
        assert r["largest_available"] is None
        print("part1 tie-break (cheaper first, nulls last): PASS")

        # limit respected; low scores still listed (no cutoff)
        r = await db.get_matches_for_lead(lead, limit=2)
        assert len(r["matches"]) == 2
        print("part1 limit: PASS")

        # Deep over-budget + type-mismatch spaces score low but ARE listed
        # (no minimum-score cutoff). Alpha/Bravo are 80%/40% over a 5000
        # budget → budget 0, type 0, capacity 10 → score 10. Delta has no
        # price → neutral 22 + 0 + 10 = 32. Tiny (20 seats < 50) is the only
        # one hard-filtered.
        lead2 = {"city": "Testville", "seat_count": 50,
                 "space_type": "Managed Office", "budget_per_seat": 5000}
        r = await db.get_matches_for_lead(lead2)
        assert r["status"] == "ok"
        scores = {m["name"]: m["score"] for m in r["matches"]}
        assert scores == {"Delta": 32, "Bravo": 10, "Alpha": 10}, scores
        assert [m["name"] for m in r["matches"]][0] == "Delta"  # 32 ranks first
        assert "Tiny" not in scores                             # hard filter only
        print("part1 low scores still listed (no cutoff): PASS")

        # undersized: every available_seats < seat_count
        r = await db.get_matches_for_lead({"city": "Testville", "seat_count": 900})
        assert r["status"] == "undersized_inventory", r
        assert r["matches"] == []
        assert r["largest_available"] == 125, r
        print("part1 undersized_inventory: PASS")

        # not_enough_info: guard fires before any query
        for bad in ({}, {"city": "Testville"}, {"seat_count": 50},
                    {"city": "Testville", "seat_count": 0}):
            r = await db.get_matches_for_lead(bad)
            assert r["status"] == "not_enough_info", (bad, r)
            assert r["matches"] == []
        print("part1 not_enough_info: PASS")
    finally:
        db.get_all_spaces = real

async def part2_real_db():
    await db.init_pool()
    try:
        # Bangalore, 50 seats, Dedicated Desk, budget 8000:
        # Koramangala: 45*(1-0.0625/0.3)=35.625 + 30 + 25*50/180=6.944 → 73
        # Whitefield:  45 + 0 + 25*50/410=3.049 → 48
        lead = {"city": "Bangalore", "seat_count": 50,
                "space_type": "Dedicated Desk", "budget_per_seat": 8000}
        r = await db.get_matches_for_lead(lead)
        assert r["status"] == "ok", r
        got = [(m["name"], m["score"]) for m in r["matches"]]
        assert got == [("WorkHub Koramangala", 73), ("Stylework Whitefield", 48)], got
        assert isinstance(r["matches"][0]["price_per_seat"], float)  # JSON-ready
        print("part2 Bangalore ok + ordering: PASS")

        # City comparison is case-insensitive on both sides
        r2 = await db.get_matches_for_lead(dict(lead, city="bangalore"))
        assert r2["status"] == "ok" and len(r2["matches"]) == 2
        print("part2 lowercase city: PASS")

        # No spaces rows in the lead's city
        r = await db.get_matches_for_lead({"city": "Atlantis", "seat_count": 10})
        assert r["status"] == "no_city_inventory", r
        print("part2 no_city_inventory: PASS")

        # Undersized against real inventory: Bangalore max available is 410
        r = await db.get_matches_for_lead({"city": "Bangalore", "seat_count": 100000})
        assert r["status"] == "undersized_inventory", r
        assert r["largest_available"] == 410, r
        print("part2 undersized largest_available=410: PASS")
    finally:
        await db.close_pool()

asyncio.run(part1_monkeypatched())
asyncio.run(part2_real_db())
print("ALL PASS")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd bot && python scripts/verify_matching.py`
Expected: `AttributeError: module 'db' has no attribute 'get_matches_for_lead'`

- [ ] **Step 3: Implement in `bot/db.py`**

Append to the `# --- SPACE MATCHING ---` section, directly after `score_space_for_lead`:

```python
async def get_matches_for_lead(lead: Dict[str, Any], limit: int = 3) -> Dict[str, Any]:
    """Top-N space suggestions for a lead. One get_all_spaces(city) fetch,
    then pure filtering/scoring/sorting in Python.

    Returns {"status": str, "matches": List[dict], "largest_available": Optional[int]}:
      ok                   — >=1 space passed hard filters; matches = top-N scored
      not_enough_info      — lead missing city or positive seat_count (normal
                             state for early leads, never an exception)
      no_city_inventory    — zero spaces rows in the lead's city
      undersized_inventory — city rows exist but every available_seats <
                             seat_count; largest_available = max in that city

    Hard filters (disqualify entirely): wrong city (enforced by the
    case-insensitive SQL filter in get_all_spaces) and available_seats <
    seat_count. Everything else only lowers rank — no minimum-score cutoff.
    """
    if not is_matchable(lead):
        return {"status": "not_enough_info", "matches": [], "largest_available": None}

    spaces = await get_all_spaces(lead["city"])
    if not spaces:
        return {"status": "no_city_inventory", "matches": [], "largest_available": None}

    seat_count = int(lead["seat_count"])
    fitting = [s for s in spaces if int(s["available_seats"]) >= seat_count]
    if not fitting:
        return {
            "status": "undersized_inventory",
            "matches": [],
            "largest_available": max(int(s["available_seats"]) for s in spaces),
        }

    scored = []
    for space in fitting:
        match = dict(space)
        # Plain floats so FastAPI/json emit numbers, mirroring what
        # api_team_funnel does for est_deal_value.
        if match.get("price_per_seat") is not None:
            match["price_per_seat"] = float(match["price_per_seat"])
        match.update(score_space_for_lead(lead, space))
        scored.append(match)

    # Sort: score desc, then price asc (nulls last), then higher capacity
    # utilization (tighter fit), then id asc (stable, deterministic).
    scored.sort(key=lambda m: (
        -m["score"],
        m["price_per_seat"] if m.get("price_per_seat") is not None else float("inf"),
        -(seat_count / int(m["available_seats"])),
        m["id"],
    ))
    return {"status": "ok", "matches": scored[:limit], "largest_available": None}
```

- [ ] **Step 4: Run the verify script — all cases pass**

Run: `cd bot && python scripts/verify_matching.py`
Expected: 9 `PASS` lines, ending `ALL PASS`. (Part 2 requires `DATABASE_URL` in `bot/.env` — it is set.)

- [ ] **Step 5: Re-run Task 1's script (regression)**

Run: `cd bot && python scripts/verify_scoring.py`
Expected: `ALL PASS`

- [ ] **Step 6: Commit**

```bash
git add bot/db.py
git commit -m "feat(db): get_matches_for_lead status engine (ok/not_enough_info/no_city_inventory/undersized_inventory)"
```

---

### Task 3: `lead_signal_tag` (Feature C core) in `bot/db.py`

**Files:**
- Modify: `bot/db.py` — insert new functions directly below `calculate_heat_score()` (which ends at line 100) and add one line inside `_lead_with_heat()` (line 103)
- Verify script (throwaway, never committed): `bot/scripts/verify_signal_tag.py`

**Interfaces:**
- Consumes: `calculate_heat_score(lead)` (existing — returns `{"score": int, "label": "Hot"|"Warm"|"Cold"}`; thresholds: >=70 Hot, >=40 Warm, else Cold; recency max 60, engagement `min(15, count*3)`, value `min(25, (log10(v)-3)*5)`).
- Produces:
  - `STALE_TAG_DAYS = 3` (module constant, aligned with `main.py`'s `NUDGE_STALE_DAYS` default)
  - `_fmt_inr(value) -> str` (db-private; deliberate 6-line mirror of `flows.fmt_inr` — importing flows from db would invert the dependency direction)
  - `lead_signal_tag(lead: Dict[str, Any]) -> str` — pure, never raises
  - `lead["signal_tag"]` present on every lead returned through `_lead_with_heat` — i.e. `/api/leads` pipeline, `find_leads`, `get_stale_leads`, `get_lead_by_id` all carry it for free. Tasks 5 and 8 rely on the key name `signal_tag`.

- [ ] **Step 1: Write the failing verify script**

Create `bot/scripts/verify_signal_tag.py`:

```python
"""Throwaway verification for db.lead_signal_tag + _lead_with_heat wiring.

Pure — no DB. Run from bot/:  python scripts/verify_signal_tag.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta, timezone

import db

now = datetime.now(timezone.utc)

# Rule 1: zero interactions
assert db.lead_signal_tag({"interaction_count": 0}) == "New — no touches logged yet"
assert db.lead_signal_tag({}) == "New — no touches logged yet"  # tolerant of missing keys
print("rule 1 (new lead): PASS")

# Rule 3: active Hot with deal value
# recency 60 + engagement 15 + value (log10(2e6)-3)*5=16.505 → 92 Hot
lead = {"interaction_count": 5, "last_activity_at": now, "est_deal_value": 2_000_000}
lead["heat_score"] = db.calculate_heat_score(lead)
assert db.lead_signal_tag(lead) == "Hot — 5 touches, last 0d ago, ₹20.0L deal", db.lead_signal_tag(lead)
print("rule 3 (active Hot + deal): PASS")

# Rule 3: singular "touch", no deal value
# recency 54 + engagement 3 = 57 Warm
lead = {"interaction_count": 1, "last_activity_at": now - timedelta(days=1),
        "est_deal_value": None}
lead["heat_score"] = db.calculate_heat_score(lead)
assert db.lead_signal_tag(lead) == "Warm — 1 touch, last 1d ago", db.lead_signal_tag(lead)
print("rule 3 (singular touch): PASS")

# Rule 2: stalled, was Warm
# current: recency 60-30=30 + engagement 6 = 36 → Cold
# potential (recency forced to 60): 60 + 6 = 66 → Warm ≠ Cold → suffix
lead = {"interaction_count": 2, "last_activity_at": now - timedelta(days=5),
        "est_deal_value": None}
lead["heat_score"] = db.calculate_heat_score(lead)
assert db.lead_signal_tag(lead) == "Stalled — no contact in 5 days, was Warm", db.lead_signal_tag(lead)
print("rule 2 (stalled, was Warm): PASS")

# Rule 2: stalled, same label → NO suffix
# current: 60-24=36 + 15 + (log10(1e7)-3)*5=20 → 71 Hot; potential 95 Hot → same
lead = {"interaction_count": 5, "last_activity_at": now - timedelta(days=4),
        "est_deal_value": 10_000_000}
lead["heat_score"] = db.calculate_heat_score(lead)
assert db.lead_signal_tag(lead) == "Stalled — no contact in 4 days", db.lead_signal_tag(lead)
print("rule 2 (stalled, same label, no suffix): PASS")

# Never raises: missing heat_score computed internally; None last_activity tolerated
t = db.lead_signal_tag({"interaction_count": 3, "last_activity_at": None})
assert isinstance(t, str) and t == "Cold — 3 touches, last 0d ago", t
print("tolerance (no heat_score / no timestamp): PASS")

# _lead_with_heat wiring: dict(row) works on a plain dict too
row = {"interaction_count": 0, "last_activity_at": None, "est_deal_value": None}
enriched = db._lead_with_heat(row)
assert enriched["heat_score"]["label"] == "Cold"
assert enriched["signal_tag"] == "New — no touches logged yet"
print("_lead_with_heat injection: PASS")

# _fmt_inr mirrors flows.fmt_inr
assert db._fmt_inr(2_000_000) == "₹20.0L"
assert db._fmt_inr(15_000_000) == "₹1.5Cr"
assert db._fmt_inr(90_000) == "₹90,000"
print("_fmt_inr: PASS")

print("ALL PASS")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd bot && python scripts/verify_signal_tag.py`
Expected: `AttributeError: module 'db' has no attribute 'lead_signal_tag'`

- [ ] **Step 3: Implement in `bot/db.py`**

Insert directly after `calculate_heat_score()` (after line 100, before the current `def _lead_with_heat`):

```python
# --- SIGNAL TAG (Feature C) ---

STALE_TAG_DAYS = 3   # aligned with main.py's NUDGE_STALE_DAYS default


def _fmt_inr(value) -> str:
    """Compact INR (mirrors flows.fmt_inr — accepted micro-duplication:
    importing flows from db would invert the dependency direction)."""
    v = float(value)
    if v >= 1e7:
        return f"₹{v / 1e7:.1f}Cr"
    if v >= 1e5:
        return f"₹{v / 1e5:.1f}L"
    return f"₹{v:,.0f}"


def lead_signal_tag(lead: Dict[str, Any]) -> str:
    """Pure. One-line 'why this lead, why now' synthesis. Never raises —
    None/missing fields coerce like calculate_heat_score does.

    Deliberate phrasing: "N touches, last Dd ago" (not "N in D days") — a
    first-interaction timestamp would cost a per-lead query; not worth it.
    """
    interaction_count = lead.get("interaction_count") or 0
    if interaction_count == 0:
        return "New — no touches logged yet"

    last_activity = lead.get("last_activity_at")
    days = (datetime.now(timezone.utc) - last_activity).days if last_activity else 0
    heat = lead.get("heat_score") or calculate_heat_score(lead)

    if days >= STALE_TAG_DAYS:
        tag = f"Stalled — no contact in {days} days"
        # What the lead read as when last touched: recency forced to its
        # 60-point max, engagement + deal size unchanged (same formulas as
        # calculate_heat_score). Suffix only when the label actually differs
        # — "Stalled — ..., was Cold" would add nothing.
        engagement = min(15, interaction_count * 3)
        value = float(lead.get("est_deal_value") or 0)
        value_points = (
            min(25.0, max(0.0, (math.log10(value) - 3) * 5)) if value > 0 else 0.0
        )
        potential = int(round(min(100, 60 + engagement + value_points)))
        potential_label = "Hot" if potential >= 70 else "Warm" if potential >= 40 else "Cold"
        if potential_label != heat["label"]:
            tag += f", was {potential_label}"
        return tag

    touches = f"{interaction_count} touch" + ("" if interaction_count == 1 else "es")
    tag = f"{heat['label']} — {touches}, last {days}d ago"
    if lead.get("est_deal_value"):
        tag += f", {_fmt_inr(lead['est_deal_value'])} deal"
    return tag
```

Then modify `_lead_with_heat` (one added line — order matters, heat first):

```python
def _lead_with_heat(row: asyncpg.Record) -> Dict[str, Any]:
    lead = dict(row)
    lead["heat_score"] = calculate_heat_score(lead)
    lead["signal_tag"] = lead_signal_tag(lead)
    return lead
```

- [ ] **Step 4: Run the verify script — all cases pass**

Run: `cd bot && python scripts/verify_signal_tag.py`
Expected: 8 `PASS` lines, ending `ALL PASS`.

- [ ] **Step 5: Regression — Tasks 1–2 scripts still pass**

Run: `cd bot && python scripts/verify_scoring.py && python scripts/verify_matching.py`
Expected: both end `ALL PASS`.

- [ ] **Step 6: Commit**

```bash
git add bot/db.py
git commit -m "feat(db): lead_signal_tag synthesis line on every heat-bearing read"
```

---

### Task 4: `GET /api/leads/{lead_id}/matches` endpoint in `bot/main.py`

**Files:**
- Modify: `bot/main.py` — insert after `api_lead_interactions` (ends line 543), before `api_team_funnel`

**Interfaces:**
- Consumes: `db.get_matches_for_lead(lead)` (Task 2), existing `require_user` dependency and `_load_lead_or_403(lead_id, user)` (404 on unknown id, 403 when a rep touches another rep's lead — managers pass for any lead).
- Produces: `GET /api/leads/{lead_id}/matches` → `{"lead_id": int, "status": str, "matches": [...], "largest_available": int|null}`. Task 7's dashboard card consumes this exact shape.

- [ ] **Step 1: Implement the endpoint**

Insert into `bot/main.py` after `api_lead_interactions`:

```python
@app.get("/api/leads/{lead_id}/matches")
async def api_lead_matches(
    lead_id: int,
    user: Dict[str, Any] = Depends(require_user),
):
    """Suggested spaces for a lead (Feature A). Read-only — never touches
    available_seats. Auth semantics inherited from _load_lead_or_403: reps
    see matches only for their own leads, managers for any. An unexpected DB
    error surfaces as FastAPI's standard 500, same as every other endpoint."""
    lead = await _load_lead_or_403(lead_id, user)
    result = await db.get_matches_for_lead(lead)
    return {"lead_id": lead_id, **result}
```

- [ ] **Step 2: Start the server (API-only mode) and mint tokens**

Terminal 1: `cd bot && python main.py` (blank `TELEGRAM_BOT_TOKEN` → API-only mode is expected and fine).

Terminal 2:

```bash
curl -s -X POST http://localhost:8000/dashboard-link -H "Content-Type: application/json" -d '{"telegram_id": -900001}'
# → {"user_id":..,"first_name":"Himanshu Rao","role":"manager","token":"<MGR_TOKEN>"}
curl -s -X POST http://localhost:8000/dashboard-link -H "Content-Type: application/json" -d '{"telegram_id": -900002}'
# → {"user_id":..,"first_name":"Priya Nair","role":"rep","token":"<PRIYA_TOKEN>"}
```

Get lead ids (note the ids for Anita Rao / Karan Mehta / Rahul Gupta):

```bash
curl -s http://localhost:8000/api/leads -H "Authorization: Bearer <MGR_TOKEN>" | python -m json.tool
```

- [ ] **Step 3: Verify the happy path (`ok`)**

```bash
curl -s http://localhost:8000/api/leads/<ANITA_ID>/matches -H "Authorization: Bearer <MGR_TOKEN>" | python -m json.tool
```

Expected: `"status": "ok"`, `matches` = 2 Bangalore spaces in score-desc order, each with `score`, `reasons` (list of strings), and numeric (not string) `price_per_seat`. Anita is 40 seats / Private Cabin / budget 9000, so: Whitefield (45 + 0 + 25·40/410=2.44 → 47) vs Koramangala (price 8500 under budget → 45, type 0, 25·40/180=5.56 → 51) — **Koramangala first with 51, Whitefield 47**.

- [ ] **Step 4: Verify `undersized_inventory`**

```bash
curl -s http://localhost:8000/api/leads/<RAHUL_ID>/matches -H "Authorization: Bearer <MGR_TOKEN>" | python -m json.tool
```

Expected: Rahul Gupta (Swiggy, Hyderabad, 300 seats; Hyderabad max available = 200) → `"status": "undersized_inventory"`, `"matches": []`, `"largest_available": 200`.

- [ ] **Step 5: Verify `no_city_inventory` via a temporary city tweak (then revert)**

```bash
cd bot && python - <<'EOF'
import asyncio, db
async def main():
    await db.init_pool()
    leads = await db.find_leads("Anita")
    print("lead", leads[0]["id"], "city:", leads[0]["city"])
    await db.update_lead(leads[0]["id"], city="Jaipur")
    await db.close_pool()
asyncio.run(main())
EOF
```

```bash
curl -s http://localhost:8000/api/leads/<ANITA_ID>/matches -H "Authorization: Bearer <MGR_TOKEN>"
```

Expected: `"status": "no_city_inventory"`, `"matches": []`. **Then revert immediately** (same heredoc with `city="Bangalore"`), and re-run Step 3's curl to confirm `ok` is back.

- [ ] **Step 6: Verify auth: 403, 401, 404**

```bash
# Karan Mehta (Cred) is assigned to Arjun — Priya's rep token must 403:
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/leads/<KARAN_ID>/matches -H "Authorization: Bearer <PRIYA_TOKEN>"   # → 403
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/leads/<ANITA_ID>/matches                                            # → 401
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/leads/999999/matches -H "Authorization: Bearer <MGR_TOKEN>"         # → 404
```

Expected: exactly `403`, `401`, `404`.

- [ ] **Step 7: Commit**

```bash
git add bot/main.py
git commit -m "feat(api): GET /api/leads/{lead_id}/matches"
```

---

### Task 5: `signal_tag` on the team funnel's stalled items (`bot/main.py`)

**Files:**
- Modify: `bot/main.py` — the hand-built `stalled` item dict inside `api_team_funnel` (lines 619–632)

**Interfaces:**
- Consumes: `lead["signal_tag"]` — already present on every stale lead because `get_stale_leads` flows through `_lead_with_heat` (Task 3).
- Produces: each item in `/api/team/funnel`'s `stalled` array carries `"signal_tag": str`. Task 8's `renderStalled` reads `s.signal_tag`.

- [ ] **Step 1: Add the field**

In `api_team_funnel`, the `stalled.append({...})` dict currently ends with:

```python
            "days_stalled": max(0, (now - lead["last_activity_at"]).days),
            "assigned_to": {"user_id": rep["id"], "name": rep["first_name"]} if rep else None,
        })
```

Add one line so it reads:

```python
            "days_stalled": max(0, (now - lead["last_activity_at"]).days),
            "signal_tag": lead["signal_tag"],
            "assigned_to": {"user_id": rep["id"], "name": rep["first_name"]} if rep else None,
        })
```

- [ ] **Step 2: Verify `signal_tag` through HTTP (both surfaces)**

With the server running (restart it to pick up the change) and `<MGR_TOKEN>` from Task 4:

```bash
curl -s http://localhost:8000/api/leads -H "Authorization: Bearer <MGR_TOKEN>" | grep -o '"signal_tag"' | wc -l
```

Expected: `13` (every seeded lead carries the tag; ≥13 if extra leads exist).

```bash
curl -s http://localhost:8000/api/team/funnel -H "Authorization: Bearer <MGR_TOKEN>" | python -m json.tool | grep -A1 '"signal_tag"' | head -20
```

Expected: every `stalled` item has a `signal_tag` starting with `"Stalled — no contact in "` (seed backdates several leads past 3 days — e.g. Divya Shah/Meesho at 20 days shows `"Stalled — no contact in 20 days, was Hot"`; day counts drift upward if the seed is older than today).

- [ ] **Step 3: Commit**

```bash
git add bot/main.py
git commit -m "feat(api): signal_tag on team funnel stalled items"
```

---

### Task 6: Bot follow-up message after capture (`bot/flows.py`)

**Files:**
- Modify: `bot/flows.py` — new helper `_format_matches_message` (place after `_lead_details`, line 86) and edits inside `_save_capture` (lines 97–221)
- Verify script (throwaway, never committed): `bot/scripts/verify_match_message.py`

**Interfaces:**
- Consumes: `db.get_matches_for_lead(updated)` (Task 2 — `updated` is the fresh lead dict `_save_capture` already fetches at line 198), existing `md()` (MarkdownV2 escape) and `logger`.
- Produces: `_format_matches_message(lead: dict, result: dict, company_name: str = "") -> Optional[str]` — returns a fully MarkdownV2-escaped string ready for `reply_text(..., parse_mode="MarkdownV2")`, or `None` for "send nothing". (The `company_name` param is a deliberate 1-arg extension over the spec's sketch: the lead row has no company name, and `_save_capture` already has it in scope — this keeps the helper sync.) No inline buttons — "Book a visit" actions are Feature B territory, not built.

- [ ] **Step 1: Write the failing verify script**

Create `bot/scripts/verify_match_message.py`:

```python
"""Throwaway verification for flows._format_matches_message (pure).

Run from bot/:  python scripts/verify_match_message.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flows

LEAD = {"contact_name": "Arjun", "city": "Bangalore", "seat_count": 50,
        "budget_per_seat": 8000}

OK = {"status": "ok", "largest_available": None, "matches": [
    {"name": "WorkHub Koramangala", "space_type": "Dedicated Desk",
     "available_seats": 180, "price_per_seat": 8500.0, "score": 73,
     "reasons": ["Exact space type"]},
    {"name": "Stylework Whitefield", "space_type": "Managed Office",
     "available_seats": 410, "price_per_seat": 7000.0, "score": 48,
     "reasons": []},
    {"name": "Third Space", "space_type": "Day Pass",
     "available_seats": 100, "price_per_seat": None, "score": 40,
     "reasons": []},
]}

text = flows._format_matches_message(LEAD, OK, company_name="Acme")
assert text is not None
assert "Acme" in text and "50 seats" in text and "Bangalore" in text
assert "WorkHub Koramangala" in text and "Stylework Whitefield" in text
assert "Third Space" not in text                      # bot shows top 2 only
assert text.count("match ") == 2
assert "6% over budget" in text                        # 8500 vs 8000 → over line
assert "₹7,000/seat vs ₹8,000 budget" in text          # under budget → vs line
assert "\\." in text                                   # MarkdownV2-escaped
print("ok status: PASS")

assert flows._format_matches_message(LEAD, {"status": "not_enough_info",
    "matches": [], "largest_available": None}) is None  # silent by design
print("not_enough_info → None: PASS")

t = flows._format_matches_message(dict(LEAD, city="Jaipur"),
    {"status": "no_city_inventory", "matches": [], "largest_available": None})
assert "No partner spaces in Jaipur in inventory yet" in t
print("no_city_inventory: PASS")

t = flows._format_matches_message(dict(LEAD, seat_count=300, city="Hyderabad"),
    {"status": "undersized_inventory", "matches": [], "largest_available": 200})
assert "No single space fits 300 seats in Hyderabad" in t
assert "largest available has 200" in t
print("undersized_inventory: PASS")

print("ALL PASS")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd bot && python scripts/verify_match_message.py`
Expected: `AttributeError: module 'flows' has no attribute '_format_matches_message'`

- [ ] **Step 3: Implement `_format_matches_message` in `bot/flows.py`**

Insert after `_lead_details` (line 86), before `_not_registered`:

```python
def _format_matches_message(lead: dict, result: dict, company_name: str = ""):
    """Builds the follow-up suggested-spaces message after a capture (Feature A).

    Returns a MarkdownV2-escaped string ready for parse_mode="MarkdownV2",
    or None when nothing should be sent (status == "not_enough_info": the
    next capture may enrich the lead — nagging for city/seats here would
    fight the evaluate_note_quality follow-up flow, which owns that job).
    Plain numbered text, no inline buttons — actions are Feature B, not built.
    """
    status = result.get("status")
    if status == "not_enough_info":
        return None

    if status == "no_city_inventory":
        return md(f"No partner spaces in {lead.get('city')} in inventory yet.")

    if status == "undersized_inventory":
        return md(
            f"No single space fits {lead.get('seat_count')} seats in "
            f"{lead.get('city')} — largest available has "
            f"{result.get('largest_available')}."
        )

    matches = result.get("matches") or []
    if not matches:  # defensive — "ok" always carries >=1 match
        return None

    display_name = company_name or lead.get("contact_name") or "this lead"
    lines = [
        f"Suggested spaces for {display_name} "
        f"({lead.get('seat_count')} seats, {lead.get('city')}):",
        "",
    ]
    budget = float(lead["budget_per_seat"]) if lead.get("budget_per_seat") else None

    for i, m in enumerate(matches[:2], start=1):  # top 2 — chat real estate
        bits = [f"{m['available_seats']} seats free"]
        price = m.get("price_per_seat")
        if price is not None and budget:
            if price <= budget:
                bits.append(f"₹{price:,.0f}/seat vs ₹{budget:,.0f} budget")
            else:
                bits.append(
                    f"₹{price:,.0f}/seat ({round((price / budget - 1) * 100)}% over budget)"
                )
        elif price is not None:
            bits.append(f"₹{price:,.0f}/seat")
        bits.append(f"match {m['score']}")
        lines.append(f"{i}. {m['name']} — {m['space_type']}")
        lines.append(f"   {' · '.join(bits)}")

    return md("\n".join(lines))
```

- [ ] **Step 4: Run the verify script — all cases pass**

Run: `cd bot && python scripts/verify_match_message.py`
Expected: 4 `PASS` lines, ending `ALL PASS`.

- [ ] **Step 5: Wire the `_save_capture` tail (changed-inputs gate + send)**

Three edits inside `_save_capture`:

**(a)** In the create branch — after `lead_id = lead["id"]` (line 151), add:

```python
        # Fresh lead → matching inputs are fresh by definition.
        matching_inputs_changed = True
```

**(b)** In the update branch — after the `if updates: await db.update_lead(lead_id, **updates)` block (line 184–185), add:

```python
        # Anti-spam gate: only re-suggest when this capture actually filled in
        # a matching input. Recapturing a vague note against a complete lead
        # must NOT re-send the same match list.
        matching_inputs_changed = any(
            k in updates for k in ("city", "seat_count", "space_type", "budget_per_seat")
        )
```

**(c)** At the very end of `_save_capture` — after the existing confirmation-card `await update.message.reply_text(card, reply_markup=keyboard, parse_mode="MarkdownV2")` (line 221), add:

```python
    if matching_inputs_changed:
        try:
            result = await db.get_matches_for_lead(updated)
            text = _format_matches_message(updated, result, company_name)
            if text:
                await update.message.reply_text(text, parse_mode="MarkdownV2")
        except Exception:
            # Capture already succeeded and was confirmed — the match message
            # is a bonus, the saved lead is the product. Log loudly (project
            # rule: no silent except), never surface this to the rep.
            logger.exception(f"[match] suggestion failed for lead {lead_id}")
```

(`updated` and `company_name` are already in scope from lines 198–200; `updated` includes Decimal `budget_per_seat`, which `get_matches_for_lead`/`_format_matches_message` both convert via `float()` at their boundaries.)

- [ ] **Step 6: Static + import sanity check**

Run: `cd bot && python -c "import flows; print('flows imports clean')"` — expected: `flows imports clean`.
Then confirm the server still boots: `cd bot && python main.py` starts without traceback (API-only mode), Ctrl-C to stop.

Live Telegram walkthrough (forward with city+seats+budget → card **then** match message; vague recapture → no repeat; no-city capture → card only, silence) is **deferred to the Phase 9 demo-spine walkthrough** — `TELEGRAM_BOT_TOKEN` is deliberately blank until the end of the build (documented blocker in root `CLAUDE.md`). Note this in the commit body.

- [ ] **Step 7: Commit**

```bash
git add bot/flows.py
git commit -m "feat(bot): suggested-space follow-up message after capture

Live Telegram walkthrough deferred to Phase 9 (TELEGRAM_BOT_TOKEN blank by
design); formatter verified via standalone assertions, wiring via static review."
```

---

### Task 7: Dashboard "Suggested Matches" card (`landing/dashboard/index.html`)

**Files:**
- Modify: `landing/dashboard/index.html` — three spots: contact-detail page HTML (line 1853), CSS (after the heat-badge block, line 334), JS (inside/next to `openContactDetail`, line 2724)

**Interfaces:**
- Consumes: `GET /api/leads/{id}/matches` (Task 4 shape), existing `apiFetch(path)` (returns parsed JSON, `undefined` on 401 after rendering sign-in), `esc(str)`, `formatINR(n)`, badge classes `badge bh|bw|bc`, chip class `stage-chip`, muted classes `empty-sub`/`list-*`/`c-meta`, skeleton class `skeleton sk-row`.
- Produces: `#cd-matches` container + `loadMatches(lead)` + `matchBadgeCls(score)`; `.signal-tag` CSS class (also used by Task 8).

- [ ] **Step 1: Add the HTML section**

At line 1853, change:

```html
        <div id="cd-header" class="cd-box"></div>
        <div>
          <div class="int-lbl">Interaction History</div>
```

to (matches card sits below lead facts, above the interactions timeline):

```html
        <div id="cd-header" class="cd-box"></div>
        <div style="margin-bottom:18px">
          <div class="int-lbl">Suggested Matches</div>
          <div id="cd-matches"></div>
        </div>
        <div>
          <div class="int-lbl">Interaction History</div>
```

- [ ] **Step 2: Add the `.signal-tag` CSS**

Directly after the heat-badge block (after line 334, `.bc  { background: var(--surface-2); color: var(--text-3); }`), add:

```css
    /* ── SIGNAL TAG (muted one-line synthesis, Feature C + match reasons) ── */
    .signal-tag {
      font-family: var(--sans);
      font-size: 0.58rem;
      color: var(--text-3);
      margin-top: 3px;
      line-height: 1.4;
    }
```

(Task 8 reuses this exact class — if it already exists when you get there, do not duplicate it.)

- [ ] **Step 3: Add `matchBadgeCls` + `loadMatches` and call it from `openContactDetail`**

Insert both functions immediately before `async function openContactDetail(leadId)` (line 2724):

```js
    // Score → monochrome density badge, same scale as the heat badges.
    function matchBadgeCls(score) {
      return score >= 70 ? 'badge bh' : score >= 40 ? 'badge bw' : 'badge bc';
    }

    // Non-blocking, card-local: mirrors the interactions fetch pattern —
    // a failure here never blocks the detail page.
    async function loadMatches(lead) {
      const el = document.getElementById('cd-matches');
      el.innerHTML = '<div class="skeleton sk-row"></div>';
      let data;
      try {
        data = await apiFetch(`/api/leads/${lead.id}/matches`);
        if (!data) return;   // 401 → sign-in already rendered
      } catch (err) {
        el.innerHTML = '<div class="empty-sub">Couldn\'t load matches.</div>';
        return;
      }
      if (data.status === 'not_enough_info') {
        // Passive view — unlike the bot, the dashboard SHOULD say this.
        el.innerHTML = '<div class="empty-sub">Add city and seat count to see suggested spaces.</div>';
        return;
      }
      if (data.status === 'no_city_inventory') {
        el.innerHTML = `<div class="empty-sub">No partner spaces in ${esc(lead.city)} yet.</div>`;
        return;
      }
      if (data.status === 'undersized_inventory') {
        el.innerHTML = `<div class="empty-sub">No single space fits ${esc(lead.seat_count)} seats — largest in ${esc(lead.city)} has ${esc(data.largest_available)}.</div>`;
        return;
      }
      el.innerHTML = (data.matches || []).map(m => {
        const priceBit = m.price_per_seat != null
          ? `${formatINR(m.price_per_seat)}/seat${lead.budget_per_seat ? ' vs ' + formatINR(lead.budget_per_seat) + ' budget' : ''}`
          : '';
        const meta = [`${m.available_seats} seats free`, priceBit].filter(Boolean).map(esc).join(' · ');
        const reason = (m.reasons && m.reasons[0])
          ? `<div class="signal-tag">${esc(m.reasons[0])}</div>` : '';
        return `<div class="list-row" style="cursor:default">
          <div>
            <span class="list-name">${esc(m.name)}</span><span class="list-co">${esc(m.locality || '')}</span>
            <div class="c-meta">${meta}</div>
            ${reason}
          </div>
          <div class="list-right">
            <span class="stage-chip">${esc(m.space_type)}</span>
            <span class="${matchBadgeCls(m.score)}">match ${m.score}</span>
          </div>
        </div>`;
      }).join('');
    }
```

Then inside `openContactDetail`, right after the `document.getElementById('cd-header').innerHTML = \`...\`;` assignment ends (line 2761) and before the interactions loading block, add:

```js
      loadMatches(lead);   // fire-and-forget — loads in parallel with interactions
```

- [ ] **Step 4: Manual verification (real server + real seeded data)**

Terminal 1: `cd bot && python main.py`. Terminal 2: `cd landing && python -m http.server 8080`. Ensure `landing/dashboard/config.js` exists with `API_BASE_URL: 'http://localhost:8000'` (copy `config.example.js` if missing). Open `http://localhost:8080/dashboard/?token=<MGR_TOKEN>` (token from Task 4).

Check each state against seeded leads:
1. Contacts → **Anita Rao** → detail shows "Suggested Matches" between the header box and Interaction History: 2 rows (WorkHub Koramangala `match 51` first, Stylework Whitefield `match 47`), each with locality, `N seats free · ₹X/seat vs ₹9,000 budget`, a `stage-chip` type chip, a monochrome badge, and a muted first-reason subline. No new colors anywhere.
2. **Rahul Gupta** (Swiggy) → "No single space fits 300 seats — largest in Hyderabad has 200."
3. `not_enough_info` / `no_city_inventory`: reuse Task 4 Step 5's heredoc to temporarily set Anita's `city='Jaipur'` (→ "No partner spaces in Jaipur yet."), then `seat_count=None` with `city='Bangalore'` (→ "Add city and seat count to see suggested spaces."), reload the detail page between tweaks, and **revert both** (`city='Bangalore'`, `seat_count=40`) when done.
4. Error state: with the detail page open, stop the bot server and re-open the same contact from the cached list → card shows "Couldn't load matches." while the rest of the page still renders. Restart the server after.

- [ ] **Step 5: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): Suggested Matches card on contact detail"
```

---

### Task 8: Dashboard signal tags on three list views + cleanup

**Files:**
- Modify: `landing/dashboard/index.html` — `renderCard` (line 2372), `renderFollowups` (line 2459), `renderStalled` (line 2659)
- Delete: `bot/scripts/verify_scoring.py`, `bot/scripts/verify_matching.py`, `bot/scripts/verify_signal_tag.py`, `bot/scripts/verify_match_message.py` (throwaway — every one is reproducible from this plan)

**Interfaces:**
- Consumes: `lead.signal_tag` on every `/api/leads` lead (Task 3), `s.signal_tag` on funnel stalled items (Task 5), `.signal-tag` CSS class (Task 7 — already present; do not re-add), `esc()`.
- Produces: nothing downstream — this is the last task.

- [ ] **Step 1: `renderCard` (rep pipeline deal cards)**

In `renderCard`, change:

```js
        <div class="deal-meta">
          <span class="deal-val">${formatINR(lead.est_deal_value)}</span>
          <span class="deal-specs">${specLine(lead)}</span>
        </div>
```

to:

```js
        <div class="deal-meta">
          <span class="deal-val">${formatINR(lead.est_deal_value)}</span>
          <span class="deal-specs">${specLine(lead)}</span>
        </div>
        ${lead.signal_tag ? `<div class="signal-tag" style="margin-top:0;margin-bottom:7px">${esc(lead.signal_tag)}</div>` : ''}
```

- [ ] **Step 2: `renderFollowups` (rep follow-ups list)**

In `renderFollowups`, change:

```js
              <div class="fu-action">Stale in ${esc(l.stage||'pipeline')} — needs a nudge.</div>
```

to:

```js
              <div class="fu-action">Stale in ${esc(l.stage||'pipeline')} — needs a nudge.</div>
              ${l.signal_tag ? `<div class="signal-tag">${esc(l.signal_tag)}</div>` : ''}
```

- [ ] **Step 3: `renderStalled` (manager stalled view, funnel payload)**

In `renderStalled`, change:

```js
            <div class="fu-action">${specParts}</div>
```

to:

```js
            <div>
              <div class="fu-action">${specParts}</div>
              ${s.signal_tag ? `<div class="signal-tag">${esc(s.signal_tag)}</div>` : ''}
            </div>
```

(No bot-side rendering — `/pipeline`'s chat cards already show heat; dashboard-only per scope.)

- [ ] **Step 4: Manual verification**

Same setup as Task 7 Step 4 (bot server + `http.server 8080`, manager token). Values below assume a fresh `seed.py --seed`; if seeded days ago, day counts shift up accordingly:
1. **Pipeline** page: every deal card shows a muted one-liner under the value/specs row — e.g. Anita Rao: `Hot — 2 touches, last 1d ago, ₹3.6L deal`.
2. **Follow-ups** page: stale items carry `Stalled — no contact in N days[, was X]` lines — e.g. Divya Shah (Meesho): `Stalled — no contact in 20 days, was Hot`.
3. **Team → Stalled Leads** (manager view): each stalled row shows its signal tag under the spec line; confirm the tags match the follow-ups page for the same leads.
4. Confirm tags are muted (`--text-3`), one line, no new colors, and XSS-escaped (they render via `esc()` like every server string).

- [ ] **Step 5: Delete the throwaway verify scripts**

```bash
rm bot/scripts/verify_scoring.py bot/scripts/verify_matching.py bot/scripts/verify_signal_tag.py bot/scripts/verify_match_message.py
```

(They were never committed; this just cleans the working tree.)

- [ ] **Step 6: Commit**

```bash
git add landing/dashboard/index.html
git commit -m "feat(dashboard): signal tags on pipeline, follow-ups, stalled views"
```

---

### Task 9: Move dashboard-token functions from `bot/main.py` into `bot/db.py`

**Why:** returning users currently have no way back into the dashboard except re-registering as a brand-new user via the web signup form — losing `localStorage` (new device, cleared storage) is a dead end. The dashboard's own sign-in fallback (`landing/dashboard/index.html`'s `renderSignedOut()`) already claims *"Open your dashboard from the Telegram bot — your secure link signs you in automatically,"* but no bot command does that. Task 10 adds a `/dashboard` command to close that loop — but `bot/commands.py` cannot import the token-signing functions from `bot/main.py` (main.py imports commands.py via `commands.get_handlers()`, so the reverse import would be circular). `bot/db.py` has no dependency on either module and `commands.py` already imports it, so the functions move there.

**Files:**
- Modify: `bot/db.py` — add near the top (new imports) and anywhere after the existing imports (new functions)
- Modify: `bot/main.py` — delete the three functions, update both call sites

**Interfaces:**
- Consumes: nothing new — `DASHBOARD_TOKEN_SECRET` env var (already required, already set in `bot/.env`).
- Produces: `db.make_dashboard_token(user_id: int, role: str) -> str` and `db.verify_dashboard_token(token: str) -> Optional[Dict[str, Any]]` (returns `{"uid": int, "role": str}` or `None`). Task 10's `/dashboard` command consumes `db.make_dashboard_token`.

- [ ] **Step 1: Add the functions to `bot/db.py`**

Add to `db.py`'s imports (top of file, alongside the existing `import os`):

```python
import base64
import hashlib
import hmac
import json
```

Add the functions anywhere after the imports (e.g. near `calculate_heat_score`) — moved verbatim from `bot/main.py`, unchanged behavior:

```python
# ─── Signed dashboard tokens (stdlib HMAC, no new dependency) ──
# Deliberate 1-day-demo simplification: a signed, non-expiring token embedded
# in each user's dashboard link, verified per-request. Not OAuth, no
# revocation, no expiry. Lives here (not main.py) so commands.py can mint
# tokens too, without a circular import.

def _signing_key() -> bytes:
    return os.environ["DASHBOARD_TOKEN_SECRET"].encode()


def make_dashboard_token(user_id: int, role: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"uid": int(user_id), "role": role}, separators=(",", ":")).encode()
    ).rstrip(b"=")
    signature = hmac.new(_signing_key(), payload, hashlib.sha256).hexdigest()
    return f"{payload.decode()}.{signature}"


def verify_dashboard_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload_b64, signature = token.split(".", 1)
        expected = hmac.new(_signing_key(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if not isinstance(payload.get("uid"), int):
            return None
        return payload
    except Exception:
        return None
```

- [ ] **Step 2: Remove the functions from `bot/main.py` and call `db.*` instead**

Delete `_signing_key`, `make_dashboard_token`, `verify_dashboard_token` (the block starting `# ─── Signed dashboard tokens ...` through the end of `verify_dashboard_token`, currently before `async def require_user`).

Update the two call sites:
- In `require_user`, `verify_dashboard_token(token)` → `db.verify_dashboard_token(token)`
- In `register` (the `RegisterResponse(...)` return), `make_dashboard_token(user["id"], user["role"])` → `db.make_dashboard_token(user["id"], user["role"])`
- In `dashboard_link`, `make_dashboard_token(user["id"], user["role"])` → `db.make_dashboard_token(user["id"], user["role"])`

`base64`/`hashlib`/`hmac`/`json` may now be unused in `main.py` — check with a quick grep before removing the imports:

```bash
cd bot && grep -n "base64\.\|hashlib\.\|hmac\.\|json\." main.py
```

If `json.` still has other hits (it does — request/response bodies elsewhere in the file typically don't need the stdlib `json` module directly since FastAPI/Pydantic handle serialization, but confirm from the grep output rather than assuming), keep exactly the imports still referenced and drop only the ones with zero remaining hits.

- [ ] **Step 3: Verify nothing broke — full token round-trip**

Terminal 1: `cd bot && python main.py` (API-only mode).

Terminal 2:

```bash
curl -s -X POST http://localhost:8000/register -H "Content-Type: application/json" \
  -d '{"first_name":"TaskNineCheck","email":"task9-check@example.com","company":"Test Co"}'
```

Expected: `200`, a JSON body with a `dashboard_token` string (still works — proves `db.make_dashboard_token` wired correctly into `register`).

```bash
curl -s -X POST http://localhost:8000/dashboard-link -H "Content-Type: application/json" -d '{"telegram_id": -900001}'
```

Expected: `200`, `{"user_id":...,"first_name":"Himanshu Rao","role":"manager","token":"..."}`.

```bash
curl -s http://localhost:8000/api/me -H "Authorization: Bearer <token from either call above>"
```

Expected: `200`, `{"id":...,"first_name":...,"role":...}` — proves `require_user` still verifies tokens correctly via `db.verify_dashboard_token`. Then try a mangled token:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/me -H "Authorization: Bearer garbage.notavalidtoken"
```

Expected: `401`.

- [ ] **Step 4: Commit**

```bash
git add bot/db.py bot/main.py
git commit -m "refactor: move dashboard-token functions from main.py to db.py"
```

---

### Task 10: `/dashboard` bot command in `bot/commands.py`

**Files:**
- Modify: `bot/commands.py` — add the command function (near `start`, since it's the same "returning user" territory) and register it in `get_handlers()`; add one line to `help_command`'s text.

**Interfaces:**
- Consumes: `db.get_user_by_telegram_id` (existing, via the `_get_user` helper), `db.make_dashboard_token` (Task 9), `_not_registered(update)` (existing helper, already used by other commands for the "not registered yet" case), `md()` (existing MarkdownV2 escaper).
- Produces: `/dashboard` command, registered in `get_handlers()`'s returned list. No other task depends on this one.

- [ ] **Step 1: Add the `DASHBOARD_BASE_URL` constant**

Add near the top of `commands.py`, alongside other module-level constants (check for an existing constants block near the imports — if none exists, add directly after the imports):

```python
DASHBOARD_BASE_URL = "https://argaur.github.io/founder-crm/dashboard/"
```

- [ ] **Step 2: Add the command function**

Add near `start` (e.g. directly after it):

```python
# ─── /dashboard ───────────────────────────────────────────────

async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a returning user a fresh dashboard sign-in link. This is the
    bot-side half of the promise landing/dashboard/index.html's sign-in
    fallback screen already makes ("open your dashboard from the Telegram
    bot") — without this command that promise had no code behind it."""
    telegram_id = update.effective_user.id
    user = await _get_user(telegram_id)
    if not user:
        await _not_registered(update)
        return

    token = db.make_dashboard_token(user["id"], user["role"])
    link = f"{DASHBOARD_BASE_URL}?token={token}"
    await update.message.reply_text(
        f"Here's your dashboard, *{md(user['first_name'])}*\\.\n\n"
        f"[Open Dashboard]({md(link)})",
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
```

Note on `md(link)`: `escape_markdown` with `version=2` inside a markdown link's URL slot needs the *entity-aware* escape (Telegram's `[text](url)` requires only `)` and `\` escaped inside the URL, not the same full escape set as body text) — but this project's `md()` doesn't distinguish contexts, and the URL here is fully bot-generated (base URL constant + hex/base64 token), containing none of MarkdownV2's reserved characters (`_*[]()~\`>#+-=|{}.!`) in practice. Confirm this holds by checking the actual token format from Task 9 (`base64.urlsafe_b64encode` output is `[A-Za-z0-9_-]+`, `.`, then a hex digest — a bare `.` and `-`/`_` are not in MarkdownV2's reserved set requiring escaping inside URLs). If Step 4's verification shows Telegram rejecting the message or rendering it oddly, drop the markdown link and send the raw URL as plain text instead — do not fight `md()`'s escaping rules mid-task.

- [ ] **Step 3: Register the command and add it to `/help`**

In `get_handlers()`, add to the returned list (alongside the other `CommandHandler`s, before `CallbackQueryHandler`s):

```python
CommandHandler("dashboard", dashboard_command),
```

In `help_command`'s text, add a line (after the `/addcontact` line, before `/reassign`):

```python
"/dashboard — Get a fresh link to your dashboard\n"
```

- [ ] **Step 4: Manual verification (requires `TELEGRAM_BOT_TOKEN` filled in)**

This step needs the bot actually polling — same deferred-verification category as Task 6's live Telegram walkthrough (see "Post-plan notes" below). Once `TELEGRAM_BOT_TOKEN` is set and `python main.py` is running:

1. As a registered user (e.g. message the bot from an account that's already run `/start`), send `/dashboard`.
2. Expected: a reply with "Here's your dashboard, `<name>`." and a tappable "Open Dashboard" link.
3. Tap the link (or copy it) — expected: it opens the dashboard directly into that user's pipeline/team view, no sign-in screen.
4. From an account that has never run `/start`, send `/dashboard` — expected: the standard "You're not registered yet. Send /start to set up your account." reply, not an error or crash.

If `TELEGRAM_BOT_TOKEN`/`OPENAI_API_KEY` are still blank when this task is executed, do the code-level checks only (Steps 1-3, plus a Python import sanity check: `cd bot && python -c "import commands"` should succeed with no errors) and flag Step 4 as deferred, same as Task 6.

- [ ] **Step 5: Commit**

```bash
git add bot/commands.py
git commit -m "feat(bot): /dashboard command sends returning users a fresh sign-in link"
```

---

## Post-plan notes for the executor

- **Deferred verification (do not silently skip — hand back to Gaurav):** the live Telegram walkthroughs of Task 6 (capture → match message, recapture → silence) and Task 10 Step 4 (`/dashboard` command round-trip) belong to the Phase 9 demo-spine walkthrough once `TELEGRAM_BOT_TOKEN`/`OPENAI_API_KEY` are filled in — both bots are currently live and polling in production (Railway), so this may already be checkable directly against the deployed bot rather than a fresh local run; check `bot/CLAUDE.md`'s Status section for current blocker state before assuming it's still blocked. Everything else in this plan is fully verifiable today.
- **Out of scope (from the spec — do not build):** decrementing/holding `available_seats`; cross-city or locality-radius matching; "Book a visit" inline actions on match messages; bot-side signal-tag rendering; any schema change or new dependency; all of Feature B.
