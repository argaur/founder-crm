---
name: Deduplication Signals
description: How to distinguish exact duplicates, near-duplicates, and same-topic-different-angle entries in the Post Ideas DB
type: feedback
---

# Deduplication Logic

## Rule: When in doubt, skip. Duplicates pollute the DB more than missed ideas hurt it.

## Exact Match — Always Skip
Same topic + same angle + same framing. Example: "LinkedIn automation pipeline" already exists → skip any new entry on automating LinkedIn content creation.

## Near-Duplicate — Skip, Note as Variant
Very similar insight, minor reframing. Example:
- Existing: "Incentives Shape Behavior" (concept post)
- Candidate: "How incentive structures drive team decisions" → same insight, different label → skip

## Same Topic, Different Angle — Include
Same subject domain but genuinely distinct lens. Example:
- Existing: Skyrim (platform strategy, modding ecosystem)
- New: "Building an AI-Powered Personal OS" (personal automation as platform design) → references the Skyrim principle but applies it to a completely different context → include

## Key Check: Notion DB Has Two Clusters
1. **Gaming ideas** — each game is a separate entry. New gaming ideas are welcome IF the game isn't already there AND the angle is product-relevant.
2. **Concept ideas** — abstract principles (Incentives, Scope, Activity, Stability, Structure). New concept ideas must have a clearly different principle, not a paraphrase.

## Recency of Existing Entries
Most existing entries were created 2026-02-26 to 2026-03-13. No status filtering needed — even Done/Scheduled entries count as existing for deduplication.

## Deduplication Index Update Rule
After each session, update `notion_post_ideas_db.md` with the new entries added. This becomes the working deduplication index for next session — faster than re-querying Notion every time.

## What Was Skipped This Session (2026-03-15) and Why

| Candidate | Reason Skipped |
|---|---|
| LinkedIn content pipeline automation | Near-duplicate of existing "LinkedIn content pipeline automation with AI" entry |
| Solopreneur in 2026 needs AI as infrastructure | Too generic — no specific data, no Gaurav-owned angle, novelty threshold not met |
| CRM 6-week pattern applies to all productivity tools | Same angle as CRM 6-Week Abandonment Cycle — generalization without new data |
| Unwrap 90%+ feedback auto-categorization | Newsletter source only, no Gaurav POV, too thin |
| PRD structure: start broad, drill to target | Moderate specificity but no hook, no data point — flagged for revisit if Gaurav develops it further |
