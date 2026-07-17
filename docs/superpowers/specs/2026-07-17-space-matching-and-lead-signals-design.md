# Design: Auto Space-Matching Engine + "Why this lead, why now" Signal Tags

**Date:** 2026-07-17
**Branch:** `stylework-migration`
**Purpose:** Two features that sharpen the "lead management that mostly runs itself"
story for the Stylework B2B Sales pitch. Feature A (space matching) is the headline;
Feature C (signal tags) is a lightweight synthesis layer; Feature B (AI next-best-action)
is email-text-only, not built.

Scope guard: no schema changes, no migrations, no new AI calls, no new dependencies.
Everything below composes existing data (`spaces`, `leads`, `interactions`-derived
fields) through the existing async patterns.

---

## Feature A — Auto Space-Matching Engine

### Story

A rep forwards a WhatsApp message: "Acme wants 50 seats in Koramangala, budget around
₹8k/seat." The bot extracts the lead, saves it — and *immediately replies with the 2
best-fit spaces from inventory*, unprompted. The dashboard shows the same matches on
the lead's detail page. Nobody searched anything. That is the demo moment.

### Architecture

Three layers, all reusing existing seams:

```
db.py        — pure scoring functions + one async query wrapper (get_matches_for_lead)
main.py      — GET /api/leads/{lead_id}/matches  (require_user + _load_lead_or_403)
flows.py     — _save_capture() tail: follow-up Telegram message with top matches
dashboard    — "Suggested Matches" card on the contact-detail page (openContactDetail)
```

The scoring logic lives in `bot/db.py` as pure functions next to
`calculate_heat_score()` — same precedent: computed at read time, never stored. No new
module; the whole engine is ~80 lines. The `spaces` table has 10 rows and will stay
tiny for the demo, so **matching is done in Python after a single
`get_all_spaces(city)` fetch — no SQL scoring, no index changes** (explicit decision:
at this inventory size, SQL ranking is complexity with zero payoff).

`available_seats` is **never decremented** by matching — this is a read-only
suggestion engine. Inventory mutation is out of scope.

### Matching rules

**Hard filters (disqualify — space is not returned at all):**
1. `lower(space.city) != lower(lead.city)` — cross-city suggestions are noise in this
   domain; a Pune space is useless to a Bangalore lead.
2. `space.available_seats < lead.seat_count` — a space that physically can't hold the
   team is not a "lower-ranked option", it's a non-option.

Everything else only lowers rank. Rationale: with 10 inventory rows, over-filtering
produces empty results; the demo should almost always show *something* ranked.

**Score (0–100), three weighted components:**

| Component | Max | Formula |
|---|---|---|
| Budget fit | 45 | Both values present: `over = max(0, price/budget − 1)`; `points = 45 × max(0, 1 − over/0.3)`. At/under budget = 45 (cheaper is never penalized); 15% over ≈ 22; ≥30% over = 0 (still listed, just ranked down). Either value missing/null → neutral 22. |
| Space type | 30 | Exact match with `lead.space_type` = 30; lead has no `space_type` = 15 (neutral); mismatch = 0. Preferred, never required — a Managed Office lead should still see a great Private Cabin deal. |
| Capacity fit | 25 | `25 × (seat_count / available_seats)`. Right-sizing: 50 seats into 60 available (≈21 pts) beats 50 into 500 (≈2.5 pts). Hard filter guarantees the ratio ≤ 1, no clamp needed. |

`score = round(budget + type + capacity)`. **No minimum-score cutoff** — hard filters
do all disqualifying; a low score is information, not exclusion.

**Tie-breaks (applied in order after score desc):**
1. Lower `price_per_seat` (nulls sort last)
2. Higher capacity utilization (`seat_count / available_seats`)
3. Lower `id` (stable, deterministic)

**Result size:** API returns top **3**; bot message shows top **2** (chat real estate).

### Components

#### 1. `bot/db.py` — scoring + query (new, ~80 lines, after the SPACE FUNCTIONS section)

```python
MATCH_REQUIRED_FIELDS = ("city", "seat_count")  # budget/space_type optional

def is_matchable(lead: Dict[str, Any]) -> bool:
    """True if the lead has city and a positive seat_count."""

def score_space_for_lead(lead: Dict[str, Any], space: Dict[str, Any]) -> Dict[str, Any]:
    """Pure. Returns {"score": int, "reasons": List[str]} per the weights table.
    reasons are short human strings, e.g. "Exact space type",
    "₹7,500/seat vs ₹8,000 budget (6% under)", "62 seats free for 50"."""

async def get_matches_for_lead(lead: Dict[str, Any], limit: int = 3) -> Dict[str, Any]:
    """One get_all_spaces(city) fetch, then pure filtering/scoring/sorting.
    Returns {"status": str, "matches": List[dict], "largest_available": Optional[int]}
    where each match is the space dict + "score" + "reasons"."""
```

`status` is a four-value string enum — the single source of truth for every surface's
empty-state copy:

| status | Condition | matches |
|---|---|---|
| `ok` | ≥1 space passed hard filters | top-N scored spaces |
| `not_enough_info` | lead missing `city` or `seat_count` | `[]` |
| `no_city_inventory` | zero `spaces` rows in the lead's city | `[]` |
| `undersized_inventory` | rows exist in city, but every `available_seats < seat_count` | `[]`, plus `largest_available` = max available_seats in that city (so surfaces can say "largest has 120 of the 200 needed") |

`budget_per_seat`/`price_per_seat` arrive as `Decimal` from asyncpg (NUMERIC columns)
— `score_space_for_lead` converts via `float()` at its boundary, same as
`calculate_heat_score` does with `est_deal_value`.

#### 2. `bot/main.py` — endpoint (after `api_lead_interactions`)

```python
@app.get("/api/leads/{lead_id}/matches")
async def api_lead_matches(lead_id: int, user: Dict[str, Any] = Depends(require_user)):
    lead = await _load_lead_or_403(lead_id, user)   # 404 / 403 exactly like notes/interactions
    result = await db.get_matches_for_lead(lead)
    return {"lead_id": lead_id, **result}
```

Auth semantics inherited from `_load_lead_or_403`: reps see matches only for their own
leads, managers for any. FastAPI serializes the Decimal price fields — matches pass
through `float()` conversion inside `get_matches_for_lead` so the JSON is plain numbers
(mirrors what `api_team_funnel` does for `est_deal_value`).

#### 3. `bot/flows.py` — bot surface (tail of `_save_capture`)

`_save_capture` already knows whether this capture changed matching inputs:
- **create branch** → inputs are fresh by definition
- **update branch** → the `updates` dict tells us if any of `city` / `seat_count` /
  `space_type` / `budget_per_seat` was just filled in

Track `matching_inputs_changed: bool` across both branches. After the existing
confirmation card is sent, append:

```python
if matching_inputs_changed:
    try:
        result = await db.get_matches_for_lead(updated)
        text = _format_matches_message(updated, result)   # None → stay silent
        if text:
            await update.message.reply_text(text, parse_mode="MarkdownV2")
    except Exception:
        logger.exception(f"[match] suggestion failed for lead {lead_id}")
        # capture already succeeded and was confirmed — never surface this to the rep
```

The changed-inputs gate is the anti-spam mechanism: recapturing a note against an
already-complete lead ("spoke to Arjun again, he'll confirm Friday") does **not**
re-send the same match list. The exception handler logs loudly (project rule: no
silent except) but never breaks the capture flow — the match message is a bonus, the
saved lead is the product.

`_format_matches_message(lead, result)` (new helper in `flows.py`, uses existing
`md()` + `fmt_inr()`):

- `status == "ok"` — top 2, e.g.:
  ```
  Suggested spaces for Acme (50 seats, Bangalore):

  1. WorkNest Koramangala — Dedicated Desk
     62 seats free · ₹7,500/seat vs ₹8,000 budget · match 92
  2. Innov8 Indiranagar — Private Cabin
     80 seats free · ₹8,400/seat (5% over budget) · match 71
  ```
  (Plain numbered text lines, MarkdownV2-escaped. No inline buttons in v1 — "Book a
  visit" actions are Feature B territory, deliberately not built.)
- `status == "not_enough_info"` — **send nothing.** The lead may get enriched by the
  next capture; nagging for city/seats here would fight the follow-up-question flow
  that `evaluate_note_quality` already owns.
- `status == "no_city_inventory"` — one line: `No partner spaces in {city} in
  inventory yet.` (Signal for the ops side; still useful spoken aloud in a demo.)
- `status == "undersized_inventory"` — one line: `No single space fits {seat_count}
  seats in {city} — largest available has {largest_available}.`

#### 4. Dashboard — "Suggested Matches" card (`landing/dashboard/index.html`)

In `openContactDetail(leadId)`: after the existing detail render, add a
`<div id="cd-matches">` section (below lead facts, above the interactions timeline)
showing a loading state, then `apiFetch('/api/leads/' + leadId + '/matches')` and
render (same non-blocking pattern the interactions fetch already uses):

- `ok` → up to 3 rows: space name + locality, space_type chip, `available_seats` free,
  `price_per_seat` vs budget, score as a small monochrome badge (reuse the heat-badge
  density style — DESIGN_BRIEF light/monochrome, no new colors). First `reasons`
  string as a muted subline.
- `not_enough_info` → muted line: "Add city and seat count to see suggested spaces."
  (The dashboard, unlike the bot, *should* say this — it's a passive view, not an
  interruption.)
- `no_city_inventory` → "No partner spaces in {city} yet."
- `undersized_inventory` → "No single space fits {seat_count} seats — largest in
  {city} has {largest_available}."
- fetch error → "Couldn't load matches." (card-local, never blocks the detail page)

### Data flow

```
capture (text/voice/image)
  → _save_capture: find-or-create lead, log interaction, confirmation card   [existing]
  → matching_inputs_changed?
      → db.get_matches_for_lead(lead)
          → db.get_all_spaces(lead.city)        [1 query]
          → hard filters → score → sort → top N  [pure Python]
      → follow-up Telegram message (or per-status one-liner, or silence)

dashboard contact detail
  → GET /api/leads/{id}/matches (Bearer token)
      → require_user → _load_lead_or_403 → db.get_matches_for_lead → JSON
  → Suggested Matches card
```

### Error handling

- Lead missing required fields → `not_enough_info` status, **never an exception** —
  it's a normal state for early-stage leads.
- Matching failure inside `_save_capture` → `logger.exception`, capture unaffected
  (see code above). The API path needs no special handling — an unexpected DB error
  surfaces as FastAPI's standard 500, consistent with every other endpoint.
- City comparison is case-insensitive on both sides (`get_all_spaces` already lowers;
  extraction may emit "bangalore"). Seat/price values go through `float()`/`int()`
  boundaries; a null `price_per_seat` on a space scores budget-neutral (22), not zero.

---

## Feature C — "Why this lead, why now" signal tag

### What it is

A one-line, deterministic synthesis string on every lead — the answer a manager wants
before asking a rep "what's happening with this one?". No AI call, no new query: a
pure function over fields every lead dict already carries (`interaction_count`,
`last_activity_at`, `est_deal_value`, and the computed heat score).

### Component

One pure function in `bot/db.py`, directly below `calculate_heat_score()`:

```python
STALE_TAG_DAYS = 3   # aligned with NUDGE_STALE_DAYS' default

def lead_signal_tag(lead: Dict[str, Any]) -> str:
    """Pure. One-line 'why this lead, why now' synthesis. Never raises."""
```

Rules, evaluated in order (all thresholds explicit — no judgment calls left to
implementation):

1. `interaction_count == 0` → `"New — no touches logged yet"`
2. `days_since_activity >= STALE_TAG_DAYS` →
   `"Stalled — no contact in {d} days"`, and if the lead *was* better than it reads
   now, append `", was {potential_label}"` — where `potential_label` is the heat label
   recomputed with recency forced to its 60-point maximum (i.e. what the lead scored
   when it was last touched). Append only when `potential_label != current label`;
   `"Stalled — ..., was Cold"` adds nothing.
3. Otherwise (active lead) →
   `"{heat_label} — {n} touch(es), last {d}d ago"`, plus `", {₹X} deal"` when
   `est_deal_value` is set (formatted Cr/L/plain like `flows.fmt_inr`).

Honest-phrasing decision: the brief's example ("3 interactions in 2 days") implies a
first-interaction timestamp we don't have without an extra per-lead query. The tag
therefore says `"3 touches, last 2d ago"` — same signal, zero new queries, no batch
N+1 against `interactions`. Not worth a query per lead in the pipeline view.

INR formatting: `db.py` gets a private `_fmt_inr()` (6 lines, mirrors
`flows.fmt_inr`). Accepted micro-duplication — importing `flows` from `db` would
invert the dependency direction for a formatter.

### Wiring (the whole feature is injection + rendering)

- `db._lead_with_heat()` adds one line: `lead["signal_tag"] = lead_signal_tag(lead)`.
  Every read path that returns heat — `/api/leads` pipeline, `find_leads`,
  `get_stale_leads`, `get_lead_by_id` — now carries the tag for free.
- `main.py api_team_funnel`: the hand-built `stalled` item dict gets
  `"signal_tag": lead["signal_tag"]` (stale leads flow through `_lead_with_heat`, so
  it's already on the lead dict).
- Dashboard (`landing/dashboard/index.html`): render `lead.signal_tag` as a muted
  one-line subtext (`class="signal-tag"`, existing muted text style, no new colors) in:
  - `renderCard()` — rep pipeline deal cards
  - `renderFollowups()` — rep follow-ups list
  - `renderStalled()` — manager stalled-leads view (from the funnel payload)
- Bot: **no bot-side rendering in v1** — `/pipeline`'s card format already shows heat,
  and chat lines are width-constrained. Dashboard-only, per scope.

### Error handling

`lead_signal_tag` mirrors `calculate_heat_score`'s tolerance: `None`/missing fields
coerce to 0/absent, function always returns a string, never raises. Dashboard renders
it with the existing `esc()` helper like every other server string.

---

## Feature B — AI next-best-action + drafted follow-up (email mention only, not built)

After each logged interaction, the AI proposes the next best action for the deal
("send revised proposal for 45 seats", "book the Indiranagar site visit before
Friday") and drafts the actual outreach message — WhatsApp-ready, in the rep's voice,
one tap to copy. Combined with capture, nudges, matching, and signal tags, this closes
the loop the prompt asks for: the system doesn't just *track* the chase, it does the
chasing prep itself. Deliberately not built today: it's a prompt-quality problem, not
an architecture problem, and it deserves eval-driven iteration (the repo already has
an extraction-eval harness to extend). One paragraph in the email as the roadmap
headline; the two features above are its live foundation.

---

## Testing / verification plan

Project norm applies: no e2e suite; verify with real round-trips (per root
`CLAUDE.md`). No new test framework for a few-hours feature.

1. **Pure functions first** (before any wiring): drive `score_space_for_lead`,
   `get_matches_for_lead`'s filter/sort (via a seeded lead), and `lead_signal_tag`
   from a throwaway script against these cases, asserting exact expected values:
   - exact-type, at-budget, tight-capacity space → score ≥ 90, ranked #1
   - 15% over budget → budget component ≈ 22; 35% over → 0 but still listed
   - lead with no `budget_per_seat` → all spaces budget-neutral, type dominates
   - two spaces, equal score → cheaper one first (tie-break)
   - undersized city inventory → `undersized_inventory` + correct `largest_available`
   - missing city → `not_enough_info`, no query beyond the guard
   - signal tag: 0 interactions / active-Hot-with-deal-value / stalled-was-Warm /
     stalled-was-Cold (no ", was" suffix)
2. **API round-trips** against seeded Neon data (`seed.py` leads span cities/stages):
   `curl` `/api/leads/{id}/matches` for (a) a matchable Bangalore lead → `ok` + top 3
   sorted by score, (b) a lead in a city with no spaces → `no_city_inventory`,
   (c) rep token on another rep's lead → 403, (d) missing token → 401. Verify
   `signal_tag` appears in `/api/leads` and in `/api/team/funnel` stalled items.
3. **Bot walkthrough** (once `TELEGRAM_BOT_TOKEN` is filled — currently the known
   blocker): forward a message with city+seats+budget → confirmation card *then* match
   message; recapture a vague note on the same lead → no repeat match message;
   capture with no city → card only, silence.
4. **Dashboard click-through**: contact detail shows the Suggested Matches card in all
   four states (pick seeded leads per state); pipeline cards, follow-ups, and the
   manager stalled view show signal tags; non-manager still 403s off the Team view.

### Explicitly out of scope
- Decrementing/holding `available_seats` (no inventory mutation)
- Cross-city or locality-radius matching
- "Book a visit" inline actions on match messages (Feature B territory)
- Bot-side rendering of signal tags
- Any schema change or new dependency
