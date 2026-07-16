# Stylework Context — Founder CRM as base for proposed solution

## Referral situation
- Contact: Harshit — referring Gaurav for a role at Stylework.
- Ask: build a "proposed solution" alongside the application; Harshit's rationale is
  that a working build gives Gaurav an edge over other candidates.

## Problem Statement (source: LinkedIn post, Himanshu Agarwal, Product Head @Stylework)

> Hiring AI Product Builders to build the future of work
>
> This is not conventional hiring with a specific JD, because I don't want to limit
> our imagination.
>
> Quick context: Stylework is India's largest coworking space aggregator, where we
> help people book coworking passes, desks, and offices, and help companies manage
> workspace at scale, across 125+ cities. We've raised over $7M so far, including a
> fresh $3.4M round this year. We're profitable and growing fast.
>
> Now, coming to the point, here are 4 business verticals we have to crack.
>
> 1. B2C E-commerce: People book a pass, a desk, a cabin, a day office, like booking
>    a flight. They search, compare, pay, park their vehicle, walk in, work, eat,
>    work, and leave. This requires an Airbnb-inspired 11-star experience, and
>    that's yours to build.
>
> 2. B2B Sales: Some companies want 50 seats in a coworking space, some want a
>    10,000-seat managed office. Today, this runs on people chasing people via lead
>    management. Imagine if it mostly ran itself.
>
> 3. Office Management SaaS: Large enterprise clients have thousands of offices
>    managed by admins buried under Excel sheets, with no insights. This is not
>    even a category which exists today.
>
> 4. Operator management SaaS: Space operators run their own inventory, invoicing,
>    and bookings, everything with Excel sheets. We want to hand them software so
>    good that running and growing their whole business feels effortless, while
>    also giving customers real-time info.
>
> That's it.
> Pick any in depth problem from these 4 areas and write an email to me on how
> you'll solve it with all the details leveraging your past experience.
>
> Also mention if you have build any revenue generating product just by yourself,
> your compensation details, expectation and don't forget to attach resume.
>
> This isn't formal hiring. It's a real shot to act like a founder and build the
> thing you actually want to build. If this gets you excited, send an email to
> himanshu@stylework.city.
>
> Repost for good karma, and refer folks in the comments if you know any.

**Ask, distilled:** pick ONE of the 4 verticals in depth, email a detailed solution
leveraging past experience, optionally backed by a self-built revenue-generating
product, plus compensation details/expectations and resume, to
himanshu@stylework.city.

## Why Founder CRM is the starting point
Existing working, deployed system Gaurav can extend/repurpose quickly once a
vertical is chosen, rather than starting from zero.

## Current state of the Founder CRM codebase
### What it does
Telegram bot for founders to log investor/customer contacts, notes, and
interactions via forwarded messages, voice notes, or manual commands; AI extracts
structured fields (stage, next action, sentiment) into Airtable.

### Stack
- Python/FastAPI backend (`bot/main.py`, `ai.py`, `commands.py`, `flows.py`, `db.py`)
- Airtable as data store (pyairtable — synchronous client, never `await`)
- Anthropic Claude Haiku for extraction, OpenAI Whisper for transcription
- python-telegram-bot v21
- Static dashboard (`landing/dashboard/`) — HTML/Tailwind CDN/vanilla JS, reads
  Airtable directly client-side

### Deployment
- Bot + API: Railway (`bot/Procfile`, `bot/railway.json`)
- Landing + dashboard: GitHub Pages (pre-merge; redeploy target TBD post-merge)

### What's reusable
- AI extraction pipeline pattern (`bot/ai.py`) — voice/text → structured data via
  Claude Haiku
- Telegram bot scaffolding (command + conversation handler patterns)
- Dashboard shell (pipeline/contact views) as a UI starting point
- Airtable-as-backend pattern, if a lightweight no-custom-DB approach fits the
  chosen vertical

### Known limitations / debt inherited
- Dashboard hardcoded to a single demo user, not multi-tenant
- No end-to-end test suite; only a narrow extraction-accuracy eval harness
  (`bot/eval/`)
- (Historical) the landing repo's dashboard variant had a hardcoded, now-rotated
  Airtable PAT committed to a public repo — pattern to avoid repeating; config now
  lives in a gitignored `config.js` (see `landing/dashboard/config.example.js`)

## Next step
Pick one of the 4 verticals above with Gaurav, then run intake (`/rubric`,
`/prd-create` or `/phase-0-intake`) on that specific direction before any build
work starts — same as any other new project. This file is the jumping-off point;
it doesn't pre-select a vertical.
