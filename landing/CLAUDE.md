# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# No build step — pure static HTML
# Local dev: open in browser directly or use any static server
python -m http.server 8080    # then open http://localhost:8080

# Deploy: push to GitHub — auto-deploys to GitHub Pages
# Live URL: https://argaur.github.io/founder-crm-landing/
```

## Architecture

Three files. No framework, no bundler.

```
index.html     — Landing page (marketing) + signup form
dashboard/     — Dashboard SPA (single page, contacts pipeline view)
style.css      — Shared styles (minimal — Tailwind CDN handles most)
assets/        — Static assets
```

Tailwind is loaded via CDN in `<script src="https://cdn.tailwindcss.com">`. Custom design tokens (brand colors, fonts) are configured inline in `tailwind.config` inside a `<script>` block in the HTML head.

## Signup Flow

Landing page form → `POST https://web-production-21776.up.railway.app/register` → returns `{ user_id, deep_link }` → redirects user to `dashboard/?uid=<user_id>` with the Telegram deep link displayed.

The Railway API endpoint is hardcoded in the form's fetch call. If the Railway URL changes, update it there.

## Dashboard Routing

Dashboard (`dashboard/index.html`) is a single-page app using `showPage()` to switch views. Pages that don't have their own nav element (e.g. contact-detail) must be listed in the `PAGE_PARENT_NAV` map — missing entries crash `showPage()`.

Two visitor types handled separately:
- Direct visitors → land on home page
- Signup redirect (`?uid=`) → land on bot page with their Telegram deep link

Dashboard always loads demo data under `user_id="demo-gaurav-001"` — it's a portfolio demo, not a live multi-user dashboard.

## API Dependency

Dashboard fetches live data from the Railway backend (`web-production-21776.up.railway.app`). If Railway is sleeping or down, the dashboard shows empty/error state. No local mock — test against the live Railway deployment.

---

## AI Session Protocol — Read This First

> Instructions for Claude. Follow these steps at the start of every session.

### Step 1: Orient (before touching any code)
- Read this file fully
- Run `git log --oneline -10` to see recent history
- Check "Status" section below → tell Gaurav: current state, what was last done, what's next

### Step 2: Explore → Gemini (not Claude tokens)
- Large file reads, understanding a module → Gemini terminal tab
- Gemini has 1M context and is free — don't burn Claude tokens on reads

### Step 3: Plan → Claude Plan Mode
- Any task with 3+ steps → enter Plan Mode before writing code

### Step 4: Build → Split by task type

| Task | Tool |
|---|---|
| Repetitive HTML/CSS, copy changes | Codex background mode |
| JS logic, routing, API integration | Claude |
| Inline completions, simple edits | Copilot |

### Step 5: End of Session (do not skip)
1. Update "Status" section below
2. Run `/compact` in Claude

---

## Status
- **State:** completed
- **Current task:** none — static portfolio landing, deployed to GitHub Pages
- **Blocker:** none
- **Last updated:** 2026-04-14
