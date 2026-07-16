# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

**Framework state:** NOT YET SET — run `/rubric` once a Stylework vertical is chosen
(see `STYLEWORK_CONTEXT.md`). Do not run it against this codebase as-is; the eventual
solution direction may look nothing like the current Founder CRM.

## What this is
Merged from two previously separate repos (`founder-crm-bot`, `founder-crm-landing`)
on 2026-07-16, to serve as the reusable base for a Stylework referral proposed
solution — see `STYLEWORK_CONTEXT.md` for the full brief and problem statement
before starting any build work.

## Layout
```
bot/       — Telegram bot backend (Python/FastAPI), deploys to Railway
landing/   — Landing page + dashboard (static HTML/JS), deploys to GitHub Pages
```

## Commands

```bash
# Bot — local dev
cd bot
pip install -r requirements.txt
python main.py                          # starts bot (polling) + FastAPI on port 8000

# Bot — Railway (production)
uvicorn main:app --host 0.0.0.0 --port $PORT   # Railway Procfile command

# Bot — seed demo data
python seed.py                          # populates demo-gaurav-001 with 8 contacts

# Bot — extraction accuracy eval
python eval/score_extraction.py                      # print field-level accuracy
python eval/score_extraction.py --verbose             # + per-example pass/fail
python eval/score_extraction.py --min-accuracy 0.8    # exit 1 if below threshold

# Landing — local dev (no build step)
cd landing
python -m http.server 8080    # then open http://localhost:8080
```

No end-to-end test suite exists for either side — verify bot changes by running
locally against Telegram; verify the dashboard against the live Railway API.

## Architecture

### bot/ — five source files, single asyncio process
```
main.py      — FastAPI lifespan wires everything: bot polling on startup
db.py        — Airtable via pyairtable (SYNCHRONOUS — never await these calls)
ai.py        — Claude Haiku + OpenAI Whisper (SYNCHRONOUS — never await these calls)
commands.py  — All slash command handlers (/pipeline, /context, /won, /lost, /ask, /addcontact)
flows.py     — All message capture handlers (forwarded text, voice, image, /addnote, /note)
```

### landing/ — static, no framework, no bundler
```
index.html       — Landing page (marketing) + signup form
dashboard/       — Dashboard SPA (contacts pipeline view), config in gitignored config.js
style.css        — Shared styles (Tailwind CDN handles most)
assets/          — Static assets
```

## Critical Constraints

**Sync/async split:** `bot/db.py` and `bot/ai.py` are fully synchronous — pyairtable
and the Anthropic SDK do not support async. All handlers in `commands.py`/`flows.py`
are async (python-telegram-bot v21). Never add `await` to any `db.*` or `ai.*` call.

**Handler registration order in `bot/main.py`:**
1. `commands.get_handlers()` — all slash commands + ConversationHandler for `/addcontact`
2. `flows.get_handlers()` — ConversationHandler for `/addnote` must come before the
   generic `MessageHandler(filters.TEXT)`, the catch-all for forwarded messages

If the order is swapped, text replies during ConversationHandler flows get
intercepted by the forward/text capture handler.

**Airtable record structure:**
- `rec["id"]` → Airtable record ID (e.g. `rec8uEn16M5rbB9Th`)
- `rec["fields"]["name"]` → contact name (never access fields at the top level)
- `rec["heat_score"]` → `{"score": int, "label": str}` injected by `get_all_contacts()`,
  NOT stored in Airtable

**pyairtable sort syntax:** Strings only — `sort=["-logged_on"]` for desc,
`sort=["logged_on"]` for asc. Never pass dicts — crashes with
`AttributeError: 'dict' object has no attribute 'startswith'`.

**Callback data separator:** Uses `:` (colon) throughout, not `_` (underscore).
Airtable record IDs contain underscores — splitting on `_` would corrupt them.
Always `split(":", 1)` or `split(":", 2)`.

**Dashboard config:** `landing/dashboard/config.js` is gitignored — copy
`config.example.js` to `config.js` and fill in a real, rotated Airtable PAT.
Never hardcode credentials directly in `index.html` (a prior version of this
dashboard did exactly that and leaked a PAT into a public repo — see
`STYLEWORK_CONTEXT.md` known-limitations note).

## Data Flow: Capture Path

Forwarded text → `forward_or_text_handler` → `ai.extract_from_text()` →
`ai.evaluate_note_quality()` → `_save_capture()`

Voice note → `voice_handler` → Whisper transcription → `ai.classify_intent()` →
if "recall": generate brief; if "capture": `ai.extract_from_voice()` →
`_save_capture()` (no quality gate for voice)

Image/screenshot → `image_handler` → `ai.extract_from_image()` (Claude Vision) →
`_save_capture()`

`_save_capture()` in `flows.py` is the shared write path: find-or-create contact,
`db.log_interaction()` (also calls `db.increment_interaction_count()`), then sends
confirmation card with "Looks good / Edit stage" inline keyboard.

## Airtable Tables

Three tables: `users`, `contacts`, `interactions`.

- `contacts.stage` valid values: `Lead`, `Evaluating`, `Proposal Sent`,
  `Negotiating`, `Won`, `Lost`
- `contacts.heat_score` computed dynamically:
  `100 - (days_since_last_update * 5) + (interaction_count * 3)`, clamped 0–100
- `interactions.source` values: `whatsapp_forward`, `voice_note`, `screenshot`,
  `addnote_command`
- Demo data lives under `user_id="demo-gaurav-001"`

## Environment Variables

```
TELEGRAM_BOT_TOKEN
AIRTABLE_PAT
AIRTABLE_BASE_ID
ANTHROPIC_API_KEY
OPENAI_API_KEY
APP_BASE_URL          # Railway URL — used in /start deep link and signup redirect
BOT_NAME              # Telegram bot username without @ — used for deep links
```

## Deployment
- `bot/` → Railway (`Procfile`, `railway.json`)
- `landing/` → GitHub Pages (redeploy target/URL TBD post-merge)

## Status
- **State:** merged base, awaiting Stylework vertical decision
- **Current task:** none — see `STYLEWORK_CONTEXT.md` next step
- **Blocker:** Stylework vertical not yet chosen
- **Last updated:** 2026-07-16
