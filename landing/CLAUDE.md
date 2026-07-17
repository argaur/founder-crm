# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# No build step — pure static HTML/CSS/JS, no framework, no bundler
python -m http.server 8080    # then open http://localhost:8080

# Deploy: push to GitHub — auto-deploys to GitHub Pages
# Live URL: https://argaur.github.io/founder-crm/
```

## Architecture

Three surfaces, no framework, no bundler.

```
index.html     — Landing page (marketing) + signup form. Bespoke CSS (no Tailwind — a stale claim
                 to the contrary used to live here; the page has always been hand-styled), light/
                 monochrome/Manrope system per DESIGN_BRIEF.md, the reference implementation of it.
dashboard/     — Dashboard SPA: rep pipeline view + role-gated manager ("Team") view.
                 config.js is gitignored — copy config.example.js and fill in your values.
style.css      — Shared styles (minimal — most styling is inline per-page).
assets/        — Static assets.
```

`DESIGN_BRIEF.md` (repo root) is the single source of truth for the visual system across both
`index.html` and `dashboard/index.html` — light-only, Manrope, no accent hue, stages identified by text
label not color. If a value here conflicts with the code, fix the code, not this file.

## Signup Flow

Landing page form → `POST {API_BASE_URL}/register` → returns `{user_id, deep_link, dashboard_token}` →
redirects to `dashboard/?uid=<user_id>` (or `?token=<dashboard_token>` directly). The Railway API URL is
configured wherever the signup form's fetch call lives in `index.html` — check there if it changes.

## Dashboard Architecture

`dashboard/index.html` is a single-page app using `showPage(name)` to switch between `home`, `pipeline`,
`contacts`, `contact-detail`, `followups`, `bot`, `settings`, and `manager` (role-gated, see below).
Pages without their own nav element (currently only `contact-detail`) must be listed in
`PAGE_PARENT_NAV` — a missing entry crashes `showPage()`.

**Auth**: the dashboard talks to the real FastAPI backend (`bot/main.py`) via signed per-user tokens, not
directly to any database. On load, `initAuth()` resolves a token in this order: `?token=` in the URL →
`?uid=` in the URL (mints one via `POST /dashboard-link`) → `localStorage.getItem('dashboardToken')`. The
resolved token is persisted to `localStorage` and stripped from the URL. No token found → a full-page
sign-in state (link to the Telegram bot), never a blank/broken dashboard. Every `/api/*` call goes
through `apiFetch(path, opts)`, which attaches `Authorization: Bearer <token>` and clears the stored
token + re-renders sign-in on a 401.

**Rep vs. manager views**: `GET /api/me` at bootstrap returns the authenticated user's role. Reps see the
`pipeline`/`contacts`/`followups` pages scoped to their own leads. The `Team` nav item (routes to
`page-manager`) ships hidden and is revealed only for `role === 'manager'` — it renders live data from
`GET /api/team/funnel` (manager-only, 403 for reps): team funnel by stage, a rep leaderboard, and a
stalled-leads list. These are two separate pages with two separate auth scopes by design, not a toggle —
see `DASHBOARD_MANAGER_VIEW_SPEC.md` for the full layout/copy rationale.

Money renders via a shared `formatINR(n)` helper (`>=1e7 → ₹X.X Cr`, `>=1e5 → ₹XX L`, else
`toLocaleString('en-IN')` rupees) — never render a raw integer.

Two visitor types on load: direct visitors land on the home page; signup-redirect visitors (`?uid=`)
land on the `bot` page with their Telegram deep link, same as before the auth rework — that navigation
behavior is preserved, only the token handling around it changed.

## API Dependency

The dashboard fetches all data from `bot/main.py`'s FastAPI backend (`API_BASE_URL` in `config.js` —
Railway URL in production, `http://localhost:8000` for local dev). CORS on the backend only allows
`https://argaur.github.io` and `localhost`/`127.0.0.1` (with or without `:8080`) — serve this directory
on one of those origins when testing locally, or every fetch will fail with a CORS error, not a useful
one. If the backend is sleeping or down, `apiFetch` throws and the calling page shows `.err-banner`
rather than a blank/broken view.

There is no local mock — test against a real running `bot/main.py` (see `bot/CLAUDE.md`), ideally seeded
via `python seed.py --seed` so the pipeline/manager views have real data to render.

## Status
- **State:** Fully rewired off Airtable (the dashboard used to call `api.airtable.com` directly from the
  browser with a client-side PAT — a real credential-exposure bug, now closed) onto the authenticated
  `/api/*` backend. Restyled to `DESIGN_BRIEF.md`'s light/monochrome system. Manager view built and
  live-verified. Both live-verified via real `curl`/API round-trips against Neon this session; no browser
  automation was available to confirm the rendered pixels, so a manual click-through is still worth doing
  before the final demo.
- **Current task:** none pending on this surface — next relevant step is the Phase 9 end-to-end
  walkthrough once `bot/.env`'s remaining API keys are filled in.
- **Blocker:** none directly (this surface doesn't need the missing API keys) — but a real demo walk-
  through needs the bot running with `TELEGRAM_BOT_TOKEN` set, since the `bot` page's deep link and the
  signup→Telegram handoff only make sense with a real bot.
- **Last updated:** 2026-07-17
