# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Local dev
pip install -r requirements.txt
python main.py                          # starts bot (polling, if TELEGRAM_BOT_TOKEN set) + FastAPI on port 8000
                                          # if TELEGRAM_BOT_TOKEN is blank, starts in API-only mode (no bot, no nudges)

# Railway (production)
uvicorn main:app --host 0.0.0.0 --port $PORT   # Railway Procfile command

# Apply schema + seed spaces inventory (once, against a fresh DATABASE_URL)
python scripts/apply_schema.py

# Seed demo data — 1 manager + 2 reps + 13 leads across all 7 stages
python seed.py --seed
python seed.py --clear                   # removes only the rows seed.py created

# Extraction accuracy eval (eval/)
python eval/score_extraction.py                      # print field-level accuracy on ai.extract_from_voice()
python eval/score_extraction.py --verbose             # + per-example pass/fail
python eval/score_extraction.py --min-accuracy 0.8    # exit 1 if below threshold
```

No end-to-end test suite exists — verify bot changes by running locally and testing against Telegram,
and verify dashboard/API changes with real `curl` round-trips against a locally-running `main.py` plus
a statically-served `landing/` (see `landing/CLAUDE.md`). `eval/` is a narrower thing: a scalar accuracy
metric for the extraction prompt specifically, not a general test suite. See `eval/README.md` for the
metric definition and the read-only trust boundary rule (never edit `eval/dataset.jsonl` or
`eval/score_extraction.py` to make the score pass — only the prompt in `ai.py`). Requires
`OPENAI_API_KEY` — makes real API calls (gpt-4o-mini, ~20-25 short calls).

## Architecture

Five source files, all fully async on a single asyncio event loop (python-telegram-bot v21 + FastAPI
share the loop via `main.py`'s lifespan handler).

```
main.py      — FastAPI lifespan wires everything: bot polling (if configured) + nudge JobQueue on startup,
               all /api/* dashboard endpoints, /register + /dashboard-link signup/auth
db.py        — asyncpg queries against Neon Postgres — ASYNC (always await these calls)
ai.py        — OpenAI only (gpt-4o-mini for extraction/reasoning, Whisper for transcription) — ASYNC
commands.py  — All slash command handlers (/pipeline, /context, /won, /lost, /ask, /addcontact)
flows.py     — All message capture handlers (forwarded text, voice, image, /addnote, /note)
```

## Critical Constraints

**Sync/async:** `db.py` and `ai.py` are fully async — `asyncpg` and `AsyncOpenAI` both support it
natively. Every `db.*`/`ai.*` call must be `await`ed. (This inverts an earlier, now-stale constraint from
the original Airtable/sync-pyairtable prototype — if you see "never await db.*" anywhere, it's describing
the pre-migration architecture, not this one.)

**Single AI provider (OpenAI):** originally split across Anthropic (Claude Haiku, for extraction/
reasoning) and OpenAI (Whisper, for transcription only) — consolidated onto OpenAI alone on 2026-07-17
("less accounts to manage and top-up"). `ai.py` now uses `gpt-4o-mini` (cheap, supports vision + JSON
mode) for every extraction/reasoning task and Whisper for transcription, both through one
`AsyncOpenAI` client. Claude has no audio-input endpoint at all, so full single-provider consolidation
meant picking the provider that covers both jobs — OpenAI, not Anthropic. If cost/quality becomes a
concern later, a clean single-provider swap to something like OpenRouter or openmodels.market (both
OpenAI-SDK-compatible — just a `base_url`/key change) is the natural next step, not a same-day one.

**Handler registration order in `main.py`:**
1. `commands.get_handlers()` — all slash commands + ConversationHandler for `/addcontact`
2. `flows.get_handlers()` — ConversationHandler for `/addnote` must come before the generic
   `MessageHandler(filters.TEXT)`, which is the catch-all for forwarded messages

If the order is swapped, text replies during ConversationHandler flows get intercepted by the
forward/text capture handler.

**Lead record structure** (`db.py` returns flat dicts, not nested — no Airtable-style `fields` wrapper):
- `lead["id"]` → Postgres bigserial id (int, not a string record id)
- `lead["contact_name"]`, `lead["company"]` (name injected by callers via `_company_names`/joins — not
  a raw column on `leads`, which only stores `company_id`), `lead["stage"]`, `lead["seat_count"]`,
  `lead["city"]`, `lead["space_type"]`, `lead["est_deal_value"]`, `lead["budget_per_seat"]`,
  `lead["assigned_to"]` (user id or null)
- `lead["heat_score"]` → `{"score": int, "label": "Hot"|"Warm"|"Cold"}` injected by
  `db._lead_with_heat()`/`db.calculate_heat_score()`, NOT stored — recomputed on every read from
  recency + interaction count + deal size (see `db.py`'s docstring on `calculate_heat_score` for the
  exact formula; it deliberately treats a never-touched lead as Cold, not Hot)
- `lead["interaction_count"]` → derived at read time via a subquery, no stored counter to drift

**Stage list is one source of truth:** `db.STAGES` (also mirrored as `ai.STAGES` for the extraction
prompt) — `Inquiry, Qualified, Site Visit, Proposal, Negotiation, Closed-Won, Closed-Lost`, exact
strings including hyphenation. `db.CLOSED_STAGES` = the last two. `ai.py`'s extraction may return
`"unknown"` as a fallback when the stage genuinely can't be inferred — that value is extraction-only and
must never be persisted; `db._validate_stage()` enforces this by rejecting anything not in `db.STAGES`.

**Dashboard auth:** signed, non-expiring HMAC tokens (`DASHBOARD_TOKEN_SECRET`), minted by `/register`
(new signup) or `/dashboard-link` (existing user, by `telegram_id` or `user_id`), verified per-request by
`require_user`/`require_manager` in `main.py`. Role is re-read from the DB on every request, never
trusted from the token payload, so a demoted manager can't keep manager-only access via a stale token.
This is a deliberate 1-day-demo simplification — no OAuth, no expiry, no revocation.

## Data Flow: Capture Path

Forwarded text → `forward_or_text_handler` → `ai.extract_from_text()` → `ai.evaluate_note_quality()` →
`_save_capture()`

Voice note → `voice_handler` → Whisper transcription → `ai.classify_intent()` → if "recall": generate
brief; if "capture": `ai.extract_from_voice()` → `_save_capture()` (no quality gate for voice)

Image/screenshot → `image_handler` → `ai.extract_from_image()` (Claude Vision) → `_save_capture()`

`_save_capture()` in `flows.py` is the shared write path: find-or-create company + lead,
`db.log_interaction()` (transactionally bumps `last_activity_at`), then sends a confirmation card with
"Looks good / Edit stage" inline keyboard. It never auto-regresses a lead's stage backwards from a vague
recapture — if the extracted stage is earlier than the lead's current stage, the current stage is kept
and flagged for manual confirmation instead.

## Postgres Schema (`schema.sql`)

Five tables: `users`, `companies`, `leads`, `interactions`, `spaces`.

- `leads.stage` — `lead_stage` enum, the 7 canonical stages above
- `leads.space_type` — `space_type` enum: `Dedicated Desk`, `Private Cabin`, `Managed Office`, `Day Pass`
- `leads.heat_score` is NOT a column — computed dynamically by `db.calculate_heat_score()`
- `interactions.type` — `interaction_type` enum: `whatsapp_forward`, `voice_note`, `screenshot`,
  `addnote_command` (dashboard-created notes map onto `addnote_command` — there is no separate
  `dashboard_note`/`manual_note` value)
- `spaces` — inventory rows (name, city, locality, seat counts, price, space_type), seeded once by
  `scripts/apply_schema.py`, used by the (stretch, not built) inventory-matching feature
- Demo data (1 manager + 2 reps + 13 leads spanning all 7 stages/several cities) lives under fixed
  negative `telegram_id`s seeded by `seed.py` — real Telegram users always have positive ids, so there's
  no collision, and `seed.py --clear` can find and remove exactly the rows it created

## Environment Variables

```
TELEGRAM_BOT_TOKEN      # blank → bot starts in API-only mode (dashboard/API still work, no bot/nudges)
BOT_NAME                # Telegram bot username without @ — used for deep links
DATABASE_URL            # Neon pooled connection string
OPENAI_API_KEY          # required for all AI: extraction/reasoning (gpt-4o-mini) + transcription (Whisper)
APP_BASE_URL            # Railway URL — used in /start deep link and signup redirect
DASHBOARD_TOKEN_SECRET  # HMAC signing key for dashboard tokens
```

## Deployment
- Railway (`Procfile`, `railway.json`), FastAPI served via `uvicorn main:app`
- Landing + dashboard deploy separately to GitHub Pages — see `landing/CLAUDE.md`

**Deploy target:** Railway project `founder-crm` (id `e244123a-3939-47be-a654-18c001ec949a`),
service `founder-crm-bot` (id `a517b096-668c-4209-8ea6-a40d36d73ada`), workspace
`Gaurav Gupta's Projects` (id `e7c14b80-ab32-4a76-9d10-b64df2d0c455`), Hobby plan, runtime Python via
Nixpacks, deployed via `railway up` from `bot/`. Confirmed by Gaurav 2026-07-17.

## Status
- **State:** Postgres/FastAPI migration complete, dashboard rework complete, all live-verified against
  real Neon data (round-trips for rep pipeline, notes, stage changes, and the manager funnel/leaderboard/
  stalled-leads views, including 403 enforcement for non-manager roles). AI provider consolidated from
  Anthropic+OpenAI onto OpenAI alone (`gpt-4o-mini` + Whisper, one key). A follow-up plan added the
  auto space-matching engine (`flows.py`'s post-capture follow-up message + `GET /api/leads/{id}/matches`,
  scored in `db.py`'s `score_space_for_lead`), dashboard-only lead signal tags (e.g. "Stalled — no
  contact in N days", driven by `db.STALE_TAG_DAYS`, which now reads the same `NUDGE_STALE_DAYS` env var
  as `main.py`'s nudge job), and a `/dashboard` command for returning users to get a fresh sign-in link.
- **Current task:** `eval/score_extraction.py` has been ported to the new coworking-domain dataset and
  the new OpenAI extraction call, but has not been run yet — blocked on `OPENAI_API_KEY` being filled
  into `.env` (deliberately deferred to the end of the build, alongside `TELEGRAM_BOT_TOKEN`, per
  Gaurav's call). Remaining work: fill in both keys, run the eval, then a full end-to-end demo-spine
  walkthrough with the bot actually polling Telegram.
- **Blocker:** `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` still blank in `bot/.env` — the app runs fine
  without them (API-only mode), but the bot itself, AI extraction, and the eval script all need them.
- **Last updated:** 2026-07-17
