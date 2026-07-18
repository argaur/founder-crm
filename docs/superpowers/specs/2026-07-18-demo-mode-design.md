# Demo Mode — seeded data for every visitor

**Date:** 2026-07-18
**Status:** implemented

## Context

The dashboard is a job-application artifact for Stylework. A reviewer who signs
up sees the dashboard through a brand-new account — which owns no leads. Every
leads-derived panel therefore renders empty, and `renderHome()` short-circuits to
the "Welcome to Siteline" explainer. Eleven panels of built work are invisible to
exactly the audience the artifact exists for.

This was discovered while debugging "recent changes not displaying on the live
dashboard". The deploy, the CDN, and the code were all correct; the signed-in
account (user 14, `Gaurav`, rep, 0 leads) simply hit the empty branch at
`landing/dashboard/index.html:2399`.

**Goal:** any visitor sees a fully populated dashboard, clearly labelled as
sample data, with a way to clear it and reach their own real (empty) state.

## Decision

**Read-fallback, not per-user cloning.** A rep who owns no leads reads the
platform-wide pipeline. Rejected the alternative — copying the 13 seeded leads
per signup — because it needs an `is_demo` column, duplicates companies, and
writes ~30 rows on every registration to buy ownership semantics a demo does not
need.

**Gated behind `DEMO_MODE`, default off.** The fallback widens read scope across
user boundaries. Left unconditional, that reads as a tenant-isolation bug to
anyone reviewing the code. As an env-gated switch it is a visible product
decision, and production-off is the honest default.

**Reads only — never writes.** Demo visitors may view seeded leads but never
mutate them. The demo database is shared: without this, any visitor could edit
the seeded story and degrade it for every later viewer.

## Implementation

### `bot/main.py`

- `DEMO_MODE` env flag, default off.
- `_read_scope(user) -> (assigned_to, demo_mode, pipeline)` — single resolver for
  pipeline read scope. Returns the pipeline alongside the scope because
  resolving the scope requires fetching it; callers reuse it rather than
  re-querying.
- `/api/overview` and `/api/leads` both use it, so Home and
  Pipeline/Contacts/Follow-ups stay consistent. Both emit `demo_mode` in the
  payload.
- `_load_lead_or_403(lead_id, user, write=True)` — `write=False` marks the two
  read-only lead endpoints (`/interactions`, `/matches`) as the only ones that
  may serve a seeded lead to a demo visitor. Mutations are unchanged.

### `landing/dashboard/index.html`

- `#demo-banner` sits outside the page containers, so seeded rows are labelled on
  Pipeline/Contacts/Follow-ups too — not just Home. Monochrome per
  `DESIGN_BRIEF.md`: it informs, so it reads as a surface, not an alarm.
- `demoCleared()` / `clearDemoData()` — a per-browser `localStorage` preference,
  deliberately not a server-side delete (the rows belong to other accounts, and
  the API refuses demo writes). An incognito window resets it, which is the
  escape hatch if it is cleared mid-walkthrough.
- `renderHomeEmpty()` — extracted from the existing empty branch, now shared by
  the rep-empty, cold-start, and sample-data-cleared paths.
- Clearing is honoured in `loadData()`, the single point where leads enter the
  app, so all four views empty together.

## Verification

Live round-trips against Neon via a local API in API-only mode
(`TELEGRAM_BOT_TOKEN=""`, to avoid a second Telegram poller competing with
production).

| Check | `DEMO_MODE=true` | `DEMO_MODE=false` |
|---|---|---|
| `/api/overview` (user 14, 0 leads) | `demo_mode=true`, 9 active, ₹5.93Cr | `demo_mode=false`, 0 active |
| `/api/leads` (user 14) | 13 leads | 0 leads |
| `GET` interactions/matches, cross-user | 200 | 403 |
| `PATCH` stage / `POST` notes, cross-user | **403** | **403** |
| `/api/overview` (user 12, owns 6) | `demo_mode=false`, 6 active | `demo_mode=false`, 6 active |

The write lockout holds in both modes — the security boundary does not depend on
the flag.

**Not verified:** rendered pixels. The Chrome extension was not connected this
session, so the banner, the dismiss flow, and the cleared-state layout have been
verified by API contract and static review only.

## Deployment

Set `DEMO_MODE=true` on the Railway service. With it unset, behaviour is
byte-identical to before this change.
