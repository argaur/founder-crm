# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Local dev
pip install -r requirements.txt
python main.py                          # starts bot (polling) + FastAPI on port 8000

# Railway (production)
uvicorn main:app --host 0.0.0.0 --port $PORT   # Railway Procfile command

# Seed demo data
python seed.py                          # populates demo-gaurav-001 with 8 contacts

# Extraction accuracy eval (eval/, added 2026-07-13)
python eval/score_extraction.py                      # print field-level accuracy on ai.extract_from_voice()
python eval/score_extraction.py --verbose             # + per-example pass/fail
python eval/score_extraction.py --min-accuracy 0.8    # exit 1 if below threshold (Ralph-loop stop-condition)
```

No end-to-end test suite exists — verify bot changes by running locally and testing against Telegram.
`eval/` is a narrower thing: a scalar accuracy metric for the extraction prompt specifically, not a
general test suite. See `eval/README.md` for the metric definition and the read-only trust boundary
rule (never edit `eval/dataset.jsonl` or `eval/score_extraction.py` to make the score pass — only the
prompt in `ai.py`). Requires `ANTHROPIC_API_KEY` — makes real API calls (Haiku, ~20-30 short calls).

## Architecture

Five source files. All run in a single process on a single asyncio event loop.

```
main.py      — FastAPI lifespan wires everything: bot polling on startup
db.py        — Airtable via pyairtable (SYNCHRONOUS — never await these calls)
ai.py        — Claude Haiku + OpenAI Whisper (SYNCHRONOUS — never await these calls)
commands.py  — All slash command handlers (/pipeline, /context, /won, /lost, /ask, /addcontact)
flows.py     — All message capture handlers (forwarded text, voice, image, /addnote, /note)
```

## Critical Constraints

**Sync/async split:** `db.py` and `ai.py` are fully synchronous — pyairtable and anthropic SDK do not support async. All handlers in `commands.py` and `flows.py` are async (python-telegram-bot v21). Never add `await` to any `db.*` or `ai.*` call.

**Handler registration order in main.py:**
1. `commands.get_handlers()` — all slash commands + ConversationHandler for `/addcontact`
2. `flows.get_handlers()` — ConversationHandler for `/addnote` must come before the generic `MessageHandler(filters.TEXT)`, which is the catch-all for forwarded messages

If the order is swapped, text replies during ConversationHandler flows get intercepted by the forward/text capture handler.

**Airtable record structure:**
- `rec["id"]` → Airtable record ID (e.g. `rec8uEn16M5rbB9Th`)
- `rec["fields"]["name"]` → contact name (never access fields at the top level)
- `rec["heat_score"]` → `{"score": int, "label": str}` injected by `get_all_contacts()`, NOT stored in Airtable

**pyairtable sort syntax:** Strings only — `sort=["-logged_on"]` for desc, `sort=["logged_on"]` for asc. Never pass dicts `{"field": ..., "direction": ...}` — this crashes with `AttributeError: 'dict' object has no attribute 'startswith'`.

**Callback data separator:** Uses `:` (colon) throughout, not `_` (underscore). Airtable record IDs contain underscores — splitting on `_` would corrupt them. Always `split(":", 1)` or `split(":", 2)` to preserve the record ID intact.

## Data Flow: Capture Path

Forwarded text → `forward_or_text_handler` → `ai.extract_from_text()` → `ai.evaluate_note_quality()` → `_save_capture()`

Voice note → `voice_handler` → Whisper transcription → `ai.classify_intent()` → if "recall": generate brief; if "capture": `ai.extract_from_voice()` → `_save_capture()` (no quality gate for voice)

Image/screenshot → `image_handler` → `ai.extract_from_image()` (Claude Vision) → `_save_capture()`

`_save_capture()` in `flows.py` is the shared write path: find-or-create contact, `db.log_interaction()` (which also calls `db.increment_interaction_count()`), then sends confirmation card with "Looks good / Edit stage" inline keyboard.

## Airtable Tables

Three tables: `users`, `contacts`, `interactions`.

- `contacts.stage` valid values: `Lead`, `Evaluating`, `Proposal Sent`, `Negotiating`, `Won`, `Lost`
- `contacts.heat_score` is computed dynamically: `100 - (days_since_last_update * 5) + (interaction_count * 3)`, clamped 0–100
- `interactions.source` values: `whatsapp_forward`, `voice_note`, `screenshot`, `addnote_command`
- Demo data lives under `user_id="demo-gaurav-001"` — not visible in the bot (bot uses real Telegram-linked user_id)

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

---

## AI Session Protocol — Read This First

> Instructions for Claude. Follow these steps at the start of every session.

### Step 1: Orient (before touching any code)
- Read this file fully
- Run `git log --oneline -10` to see recent history
- Check "Status" section below → tell Gaurav: current state, what was last done, what's next

### Step 2: Explore → Gemini (not Claude tokens)
- Large file reads, understanding a module, reading logs → Gemini terminal tab
- Gemini has 1M context and is free — don't burn Claude tokens on reads
- Paste Gemini's summary into the Claude session as context

### Step 3: Plan → Claude Plan Mode
- Any task with 3+ steps → enter Plan Mode before writing code
- Challenge the ask: right problem? right scope? right time?
- Only build what was asked. Scope Hold.

### Step 4: Build → Split by task type

| Task | Tool |
|---|---|
| Boilerplate, tests, repetitive handlers, bulk codegen | Codex background mode |
| Integration logic, Telegram flows, Airtable edge cases | Claude |
| Inline completions, simple edits | Copilot |

Codex background: `codex exec --prompt "<task>" --full-auto --model gpt-4o-mini > .codex-review.md 2>&1 &`

### Step 5: End of Session (do not skip)
1. Update "Status" section below (current task, blocker, date)
2. Run `/compact` in Claude
3. Update Obsidian project page

---

## Status
- **State:** completed
- **Current task:** none — all 9 sessions done, deployed on Railway
- **Blocker:** none
- **Last updated:** 2026-04-14
