# Implementation Plan — Founder CRM → Stylework B2B Sales CRM

**Status:** approved, not started. Pick this up at the top of the next session.
**Owner:** Gaurav Gupta. **Agent policy:** all `Agent` tool dispatches on this
project use `model: "fable"` (Fable 5) only — this is a hard constraint for
this project specifically, not a general default.

## Why / stakes
This is a job-application artifact (Stylework, AI Product Builder role via
Harshit's referral), not a side project — treat it at that quality bar. Once
it demos cleanly it **replaces "Rethink CRM" in Gaurav's portfolio**, so the
landing page, README, and overall polish matter as much as the bot logic.
Target: working end-to-end by tomorrow (2026-07-17), covering every
improvement identified in the Fable 5 analysis (see
`memory/decision-b2b-vertical-and-db-migration.md` for the full findings this
plan is built from) — not a stripped demo with the rest left as email prose.
`/rubric`/Blueprint framework is explicitly skipped for this project (too slow
for the timeline); work directly off this plan.

## What "done" looks like (demo spine)
Forward a WhatsApp-style message mentioning a company + seat count + city →
bot extracts it with the new B2B fields → contact appears correctly staged on
a manager dashboard showing team-wide pipeline value → a stale lead
auto-nudges the assigned rep → `/ask` answers a manager-style pipeline
question. All of it running on Neon Postgres, no Airtable left anywhere.

## Phase 0 — Neon setup + schema
- Create Neon project (serverless Postgres), get a pooled connection string,
  add `DATABASE_URL` to `.env`/Railway env vars, drop `AIRTABLE_PAT`/
  `AIRTABLE_BASE_ID`.
- Create schema (5 tables, per the Fable analysis):
  `users` (id, telegram_id, first_name, email, company, role enum[rep,manager],
  joined_at), `companies` (id, name, industry, city), `leads` (id, company_id,
  contact_name, contact_role, phone, stage enum, seat_count, city, space_type
  enum, budget_per_seat, est_deal_value, move_in_date, assigned_to→users,
  source, last_activity_at, created_at), `interactions` (id, lead_id, user_id,
  type enum, raw_content, ai_summary, logged_at), `spaces` (id, name, city,
  locality, total_seats, available_seats, price_per_seat, space_type) — seed
  ~10 rows, used for the inventory-matching stretch feature if time allows.
- Pick a driver: `asyncpg` + hand-written SQL (fastest to ship in a day) or
  SQLAlchemy async — recommend plain `asyncpg` given the 1-day budget; no ORM
  overhead to learn/debug under time pressure.

## Phase 1 — `bot/db.py` full async rewrite
- Replace every pyairtable call with `asyncpg` queries; every function becomes
  `async def` (inverts the current CLAUDE.md "never await db.*" rule — must be
  rewritten, see Phase 8).
- Fix along the way (both are real bugs, not just migration noise):
  - `calculate_heat_score`/lead score: never-touched leads must not default to
    `days_since=0` → "Hot". Use `est_deal_value` in the score too so a
    10,000-seat deal outranks a 4-desk one.
  - `find_contact`-equivalent: parameterized `ILIKE`, not f-string formula
    interpolation (current version is injection-prone).
- Add `assigned_to` read/write, `companies` CRUD, `spaces` read for matching.
- Centralize stage list as one module-level constant/enum, imported everywhere
  (currently duplicated in 5 places — this is the point where that gets fixed).

## Phase 2 — `bot/ai.py` updates
- Migrate to `AsyncAnthropic` (async is supported now; the "SDK doesn't
  support async" note in the old CLAUDE.md is stale).
- Update extraction JSON schemas/prompts (text, voice, image) to pull
  `seat_count`, `city`, `space_type`, `budget_per_seat`, `move_in_date` where
  mentioned, and to reason in coworking vocabulary (seats, cabins, day passes,
  managed office, lock-in, security deposit, fit-out) instead of
  founder/investor vocabulary. Keep the Hinglish handling.
- Keep `evaluate_note_quality`, `classify_intent` structurally unchanged —
  update wording only.

## Phase 3 — `bot/commands.py` + `bot/flows.py`
- Update all handlers for the new async `db.*` calls (`await` everywhere now).
- Fix `_save_capture()`'s auto-overwrite bug: never move a lead **backwards**
  in stage automatically from an extraction — if the extracted stage is
  earlier than the current one, keep current stage and flag for manual
  confirmation instead.
- Add lead assignment: on creation, assign to the capturing rep by default;
  add a manager-only reassign path if time allows (stretch).
- Update `/pipeline`, `/context`, `/ask` output to show seat_count/city/deal
  value alongside existing fields.
- Update stage names in all user-facing copy/keyboards to the new coworking
  cycle: Inquiry → Qualified → Site Visit → Proposal → Negotiation →
  Closed-Won / Closed-Lost.

## Phase 4 — Automated nudges (the headline "runs itself" feature)
- Wire PTB's `JobQueue` (already available, no new dependency) to run every
  N hours, call the async stale-lead query (ported `get_stale_contacts`
  logic), and DM the assigned rep: "Zomato (200 seats, Gurgaon) — 5 days
  quiet in Proposal. Nudge / Snooze / Mark Lost" via inline keyboard.
- This is the single most pitch-critical item — do not cut it for time.

## Phase 5 — FastAPI backend endpoints (`bot/main.py`)
- Add authenticated endpoints to replace direct-Airtable dashboard reads:
  `GET /api/leads` (scoped to caller), `PATCH /api/leads/{id}/stage`,
  `POST /api/leads/{id}/notes`, `GET /api/team/funnel` (stage counts, total
  pipeline value, per-rep breakdown, stalled-deal list) — manager-only.
- Auth: simplest viable for a 1-day demo — a signed token embedded in each
  user's dashboard link (issued at `/register` or a new `/dashboard-link`
  endpoint), verified per-request. Not full OAuth; call this out as the
  known simplification if it comes up.
- Keep existing `/health` and `/register` endpoints, port `/register` to
  Postgres.

## Phase 6 — Dashboard rework (`landing/dashboard/`)
- Replace every direct Airtable fetch (currently ~10 call sites incl. the
  `PATCH`/`POST` writes at `index.html:2181-2252` that a read-only PAT should
  never have been able to do) with calls to the new `/api/*` endpoints. This
  also permanently closes the exposed-credential pattern noted in
  `memory/project-founder-crm-security-note.md`.
- Add a manager view: team funnel by stage, pipeline value, per-rep
  leaderboard, stalled-deal list — this is the screen Himanshu would actually
  look at.
- Keep the existing rep-facing pipeline view, just re-pointed at the API and
  extended with the new lead fields.

## Phase 7 — Seed data + eval harness port
- Rewrite `bot/seed.py` for the new schema: 2 reps + 1 manager, ~10-15 leads
  across a spread of stages/cities/seat counts (small enough for a fast site
  visit + several 500-2000+ seat "managed office" leads to show range), a
  handful of `spaces` rows.
- Port `bot/eval/dataset.jsonl` examples to coworking-domain transcripts with
  the new fields; keep `score_extraction.py`'s read-only trust-boundary rule
  unchanged (only the prompt in `ai.py` may change to pass the eval).

## Phase 8 — Landing page + docs
- Reframe `landing/index.html` copy for the Stylework B2B pitch (same visual
  system, new positioning — "coworking lead management that runs itself").
- Rewrite both `CLAUDE.md` files: flip the sync/async constraint (now
  `await` everything in `db.*`/`ai.*`), replace the Airtable record-structure
  section with the Postgres schema, update env vars (`DATABASE_URL` instead of
  `AIRTABLE_PAT`/`AIRTABLE_BASE_ID`), update Status section.
- Write/update a short case-study-style README section suitable for slotting
  directly into the portfolio once this replaces Rethink CRM.

## Phase 9 — End-to-end verification
- Seed a Neon demo branch fresh, run the bot locally, walk the full demo
  spine end to end (see "What done looks like" above) before calling this
  finished. No claiming done without actually running it.
- Confirm `eval/score_extraction.py --min-accuracy 0.8` still passes on the
  reworked prompts.

## Explicit stretch / pitch-email-only (do not build unless everything above
lands with time to spare)
Inventory-matching against `spaces` beyond basic seed data, site-visit
scheduling/calendar hooks, auto-proposal generation, e-sign hooks
(Leegality/DocuSign), WhatsApp Business API as a capture channel (Telegram
stays the prototype substrate — say so honestly in the pitch, the capture
pipeline is channel-agnostic by design).

## Files most affected
`bot/db.py` (full rewrite), `bot/ai.py` (async + schema/prompt updates),
`bot/commands.py`, `bot/flows.py`, `bot/main.py` (new endpoints), `bot/seed.py`,
`bot/eval/dataset.jsonl`, `landing/dashboard/index.html` (fetch layer + new
manager view), `landing/index.html` (copy), `CLAUDE.md` (root + `bot/`).

## Known risk called out up front
Multi-tenancy/auth and the dashboard becoming a real backend-served app are
the two biggest time sinks in this plan — if the 1-day budget is tight, cut
scope inside Phase 5/6 (e.g. token-in-URL instead of anything fancier) rather
than dropping Phase 4 (nudges) or the schema migration itself.
