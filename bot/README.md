# SitelineCRM — Coworking Lead Management That Runs Itself

> A Telegram bot + manager dashboard that turns forwarded WhatsApp conversations into a live coworking sales pipeline — built for Stylework's B2B Sales vertical (50-seat teams to 10,000-seat managed offices).

**Stage:** Working prototype, live-verified end to end &nbsp;|&nbsp; **Stack:** Python · Telegram Bot API · OpenAI API · Neon Postgres (asyncpg) · FastAPI · vanilla JS dashboard

---

## The Problem

Stylework's B2B sales team currently runs lead management the way most coworking sales teams do: reps chase conversations across WhatsApp, calls, and site visits, and none of it becomes structured pipeline data until someone manually types it into a spreadsheet or CRM — usually after the fact, if at all. Deals stall silently. Managers have no live view of team-wide pipeline value or which leads have gone quiet.

## What I Built

A Telegram bot that acts as the entire capture interface — reps forward a WhatsApp chat, send a voice note, or share a screenshot, and the model extracts the structured deal (contact, company, seat count, city, space type, budget, move-in date, pipeline stage) without the rep ever filling out a form. A FastAPI backend persists this to Postgres and exposes it through a manager dashboard showing team-wide funnel value, a rep leaderboard, and a stalled-deal list — with the bot automatically nudging the assigned rep by DM when a lead has gone quiet past its stage threshold, so the pipeline manages itself instead of needing a manager to chase it.

Key design decisions:
- **No new UI to learn** — the capture interface is a Telegram conversation reps already have open all day
- **AI does the structuring** — reps forward natural-language conversation (including Hinglish); the model normalises it into seat count, city, space type, budget, and pipeline stage
- **Automated nudges, not another dashboard to check** — a background job DMs the rep directly when a deal stalls, rather than relying on a manager to notice
- **Manager and rep views are separated by design** — the rep pipeline board answers "what do I move today," the manager funnel answers "where is the team's revenue and who's sitting on it" — kept as two screens with two auth scopes, not one overloaded view

## Architecture

Started as a single-user Airtable prototype (`founder-crm-bot` + `founder-crm-landing`), then migrated wholesale to a real multi-user backend once the Stylework B2B vertical was chosen: Postgres via `asyncpg` replaced Airtable end to end, every handler became async, and the dashboard was rewired from direct client-side Airtable calls (a real credential-exposure bug in the earlier prototype) to authenticated FastAPI endpoints with signed per-user tokens and server-verified roles.

## Tech Stack

| Layer | Choice |
|-------|--------|
| Bot interface | Telegram Bot API (python-telegram-bot v21, async) |
| AI / NLP | OpenAI `gpt-4o-mini` for extraction/reasoning (incl. vision) + Whisper for voice notes |
| Database | Neon (serverless Postgres) via `asyncpg` |
| Backend API | FastAPI, signed HMAC dashboard tokens, role-scoped endpoints |
| Dashboard | Vanilla HTML/CSS/JS, no framework — Manrope/monochrome design system matched to Stylework's own brand |
| Hosting | Railway (bot + API), GitHub Pages (landing + dashboard) |

## Links

- **Landing page:** https://argaur.github.io/siteline-crm/
- **Portfolio:** https://gauravg-portfolio.vercel.app

---

> Built by [Gaurav Gupta](https://linkedin.com/in/ar-gaurav) — Senior PM & AI Strategist
