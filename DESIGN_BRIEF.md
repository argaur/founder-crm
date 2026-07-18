# DESIGN_BRIEF.md — SitelineCRM visual language (single source of truth)

**Supersedes the dark-amber system entirely (2026-07-16).** The previous brief
(dark `#080706` ground, amber `#E8920A` accent, Cormorant/DM Mono/Outfit
three-font stack) is dead. No file may reference it. If any page still carries
those values, that is a bug — fix the page, not this brief.

**Why the change:** the demo is reviewed by Stylework's Product Head. The
visual system now replicates Stylework's own brand sensibility — minimalist
black-on-white, corporate-meets-accessible premium, sophistication through
restraint — so the product reads as native to their design language, not as a
third-party pitch deck.

Covers the whole product: `landing/index.html` (done, reference
implementation) and `landing/dashboard/index.html` (next phase — restyle to
match this brief). Any new page, section, or component draws from here. If a
value here conflicts with code, fix the code.

**Product name:** SitelineCRM (wordmark: `SITELINECRM`, Manrope 800,
letter-spacing 0.14em). The "Siteline" root reads two ways on purpose: *site
visits* (the coworking sales step) and *sightline* (the manager's view of the
pipeline). Renamed from "Siteline" on 2026-07-18 so the product name, the
Telegram handle (`@SitelineCRMbot`), and the repo (`argaur/siteline-crm`) all
carry one string.

**Positioning line:** "Coworking lead management that runs itself."

---

## 1. Color — exact values

**Light-only. There is no dark mode anywhere in the product.**
`prefers-color-scheme` is deliberately ignored. Reasons: (a) Stylework's own
site is light-only — matching their sensibility is the whole point;
(b) white-ground/near-black-ink IS the brand, inverting it produces a
different brand; (c) the reviewer sees the demo once, in one view — a second
theme doubles QA surface for zero demo value. Do not add dark mode per-page.

### Core tokens (`:root` — identical across landing and dashboard)

| Token | Value | Use |
|---|---|---|
| `--bg` | `#FFFFFF` | Page background |
| `--surface` | `#FAFAF9` | Cards on hover, nav/chrome fills, code blocks, sidebar |
| `--surface-2` | `#F3F3F1` | Nested surfaces: inner chips, url pills, ghost numerals, avatars |
| `--border` | `#EBEBE8` | Default 1px rules, card borders, section dividers |
| `--border-2` | `#DDDDD9` | Stronger border: input fields, icon boxes, hover edges, chrome dots |
| `--ink` | `#0A0A0A` | THE color. Primary buttons, wordmark, active states, emphasis, icons |
| `--text` | `#0A0A0A` | Primary text (same as ink — one black, no forks) |
| `--text-2` | `#5C5C58` | Secondary text: body prose, sublines |
| `--text-3` | `#9A9A96` | Tertiary: labels, captions, muted `em` emphasis, placeholders |

Ink hover state: `#2A2A28` (filled buttons only).
Overlay scrim: `rgba(10,10,10,0.4)` + `backdrop-filter: blur(8px)` (modal).
Nav fill: `rgba(255,255,255,0.92)` + `backdrop-filter: blur(12px)`.

**There is no accent color.** Emphasis is achieved with weight (800), scale,
and ink-vs-grey contrast — never hue. Do not introduce one.

### Semantic colors (functional states only, muted — never decorative)

| Meaning | Text | Fill | Border |
|---|---|---|---|
| Success / won | `#15803D` | `#F5F9F5` | `#DCE8DC` |
| Error / lost | `#B91C1C` | `#FDF3F2` | `#F3DBD8` |

These appear only where state genuinely demands color (form errors, success
confirmations, Closed-Won / Closed-Lost). Everything else stays monochrome.

### Heat / priority badges (monochrome density scale)

| Level | Pattern |
|---|---|
| Hot | `background: var(--ink); color: #FFFFFF` |
| Warm | `background: var(--border-2); color: var(--text-2)` |
| Cold | `background: var(--surface-2); color: var(--text-3)` |

### Stage colors (dashboard phase — read this)

The old 7-hue stage palette (violet/teal/blue/amber…) is superseded. Stages
are identified by their **text label**, not by hue. Stage badges use the
soft-chip pattern: `background: var(--surface-2); border: 1px solid
var(--border-2); color: var(--text-2)` — with two exceptions:
`Closed-Won` uses the success trio and `Closed-Lost` the error trio above.
The current/active stage in any single-lead view may use the ink-filled
badge (`--ink` bg, white text). One palette for the whole product — never
fork it.

---

## 2. Typography — one font, weight does the work

Google Fonts, single `<link>` (same URL in both files):

```
https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap
```

**Manrope** everywhere. Fallback stack: `'Manrope', system-ui, sans-serif`
(token `--sans`). No serif, no mono — hierarchy comes from weight and scale:

| Role | Spec |
|---|---|
| Display / hero h1 | 800, `clamp(46px, 5.2vw, 76px)`, line-height 1.04, letter-spacing −0.035em |
| Section h2 | 800, `clamp(28px, 3vw, 40–48px)`, letter-spacing −0.03em |
| Card / step titles | 700, 1.1–1.2rem, letter-spacing −0.01em |
| Body prose | 400, 0.855–0.9375rem, line-height 1.65–1.78, color `--text-2` |
| Labels / eyebrows | 600–700, 0.675rem, UPPERCASE, letter-spacing 0.14em, color `--text-3` (or `--ink` for strong) |
| Buttons | 700, 0.72–0.82rem, UPPERCASE, letter-spacing 0.1em |
| Data values / numerals | 600–800 with `font-variant-numeric: tabular-nums` |
| Wordmark | 800, 0.85rem, letter-spacing 0.14em, UPPERCASE |

**Emphasis move:** `em` inside headlines is NOT italic — it is
`font-style: normal; color: var(--text-3)`. The muted-grey word against
near-black is the one rhetorical flourish. Use it once per headline, max.

**Big-number treatment** (Stylework's stat-callout motif): oversized ghost
numerals — step numbers at 88px/800 in `--surface-2` (darkening to
`--border-2` on hover); stat values 1.6rem+/800 in `--ink`, tabular-nums,
with a small uppercase label beneath. Numbers are the loudest thing on any
card.

---

## 3. Shape, spacing, elevation, motion

- **Radius scale:** 12px cards/mockup frames · 8px buttons/inputs/inner
  panels/icon boxes · 6px chips/url pills/nav items · 5px tiny badges ·
  14px modal. No pills, no sharp squares — soft-rectangle throughout.
- **Borders do the layout work:** `1px solid var(--border)` separates
  sections (`.sec { border-top }`) and structures compound components
  (compare table, steps row) — internal 1px rules, not gaps.
- **Elevation (allowed shadows, nothing else):**
  - hero mockup: `0 16px 44px rgba(10,10,10,0.06)`
  - dashboard mockup: `0 28px 64px rgba(10,10,10,0.07)`
  - feature-card hover: `0 12px 32px rgba(10,10,10,0.05)`
  - modal: `0 32px 80px rgba(10,10,10,0.14)`
  No decorative gradients. No glows (the amber glows are gone with the amber).
- **Spacing scale (landing):** section padding 112px/48px desktop →
  72px/24px mobile; hero 148px top / 104px bottom; CTA section 136px;
  content max-width 1280px; grid gaps 24–80px. Whitespace-heavy —
  when in doubt, add space, not a border.
- **Buttons:** primary = ink fill, white text, 8px radius, uppercase
  letter-spaced label ending in `→` (e.g. `GET THE BOT →`), hover
  `#2A2A28` + `translateY(-1px)`. Ghost = plain text link, lowercase,
  1px bottom border `--border-2` → `--ink` on hover. Two button types
  total; no outlined third variant.
- **Cards:** `--bg` fill, 1px `--border`, 12px radius, 40px padding;
  hover = border → `--border-2` + soft shadow. Icon boxes: 36px square,
  1px `--border-2`, 8px radius, single-color ink SVG (stroke 1.5) inside;
  border → `--ink` on card hover.
- **Left-rule accent pattern:** quoted/code snippets and "out" chat bubbles
  carry `border-left: 2px solid var(--ink)` — the monochrome replacement
  for what accent color used to do.
- **Motion:** restrained — fade/translate-up reveals (0.65s ease, staggered
  0.08–0.56s), marquee loop 30s linear, hover transitions 0.18–0.28s.
  Nothing bounces. One blinking 6px ink dot (hero tag) is the only looping
  attention cue besides the marquee.
- **Focus states:** `outline: 2px solid var(--ink); outline-offset: 3px`.
- **Cursors:** standard (`pointer` on interactive). No gimmicks.

---

## 4. Voice of the copy (unchanged — visual system changed, voice did not)

Three adjectives, each load-bearing:

1. **Declarative** — short sentences that state what happens, not what's
   possible. "Forward the message — the lead stages itself." The product's
   pitch is automation; hedging ("can", "helps you") undercuts it.
2. **Domain-literal** — coworking vocabulary everywhere a generic SaaS word
   could sit: *seats, cabins, managed office, site visit, move-in,
   per-seat pricing, lock-in*. Money in Indian units (₹ L / ₹ Cr), cities
   real (Gurgaon, Pune, Mumbai). This is how the reader knows the product
   was built for them and not re-skinned.
3. **Unembellished** — no exclamation marks, no "supercharge/unlock/
   revolutionize", no fabricated testimonials or invented metrics. Where
   social proof would normally go, the landing page shows persona cards
   (rep / sales head / the pipeline itself) instead — honest and more
   informative. Numbers shown in mocks are plausible demo data, presented
   as product UI, not as claims.

Recurring rhetorical device: the "runs itself" construction (echoes the
Stylework brief's own phrasing: "Imagine if it mostly ran itself"). Use it
sparingly — hero, step 03, footer — so it stays a spine, not a tic.

---

## 5. Per-surface notes

- **Landing (`landing/index.html`):** DONE — the reference implementation
  of this brief. Marketing register: reveals and marquee allowed, biggest
  type sizes, mockup shadows. No Tailwind (the note in `landing/CLAUDE.md`
  claiming Tailwind CDN is stale; the page is bespoke CSS on the tokens
  above).
- **Dashboard (`landing/dashboard/index.html`):** NEXT PHASE — currently
  still on the old dark-amber system; restyle it to this brief. Utilitarian
  register: no marquee, no reveal animations, no mockup shadows; same
  tokens, same Manrope link, denser spacing (12–20px rhythm), stat numerals
  and monochrome badges per §1–§2. The landing page's embedded dashboard
  mock (`.db-*` classes) is the visual target.
- **Bot copy (Telegram):** voice rules (§4) apply; no visual tokens, but
  stage names and money formatting (`₹X.X Cr` / `₹XX L`) must match §6.

---

## 6. Canonical strings

- Stages (exact, hyphenation matters): `Inquiry`, `Qualified`, `Site Visit`,
  `Proposal`, `Negotiation`, `Closed-Won`, `Closed-Lost`.
- Money: `₹4.2 Cr`, `₹62 L`, `₹45,000` — never raw integers, never "INR".
- Tagline: "Coworking lead management that runs itself."
