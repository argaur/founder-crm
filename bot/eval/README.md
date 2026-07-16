# Eval harness — extraction accuracy

A scalar, machine-computable accuracy metric for `ai.extract_from_voice()`, built for
Karpathy's "Autoresearch loop" pattern (see `docs/reference/PRACTITIONER_SETUPS.md` #3 in the
Claude Optimisation framework repo): an agent tunes one editable asset against one number, in a
time-boxed loop, with git as memory.

## What this measures

`extract_from_voice(transcript)` returns a fixed JSON schema (`contact_name`, `company`, `role`,
`stage`, `summary`, `next_action`, `budget_signal`) from a voice-note transcript. This harness
scores it against `dataset.jsonl`, a labelled set of realistic transcripts (including Hinglish/
informal phrasing, matching real usage).

**Only 4 fields are scored**, all deterministic/categorical:
- `stage` — exact match against the enum
- `contact_name_present`, `company_present`, `budget_signal_present` — presence/absence match

`summary` and `next_action` are **excluded from the score** — they're free text, and grading
prose without a human or a second LLM-as-judge reintroduces the non-determinism this pattern is
designed to avoid. A v2 could add an LLM-judge score for these as a *separate* number, but that's
not built here.

**Metric = field-level accuracy**: correct fields / total scored fields, across all dataset rows.

## Running it

```bash
python eval/score_extraction.py                        # print accuracy
python eval/score_extraction.py --verbose               # + per-row pass/fail
python eval/score_extraction.py --min-accuracy 0.8       # exit 1 if accuracy < 80%
```

Requires `ANTHROPIC_API_KEY` in the environment — this makes real API calls (Haiku model, one
call per dataset row, small but non-zero cost).

## Using it as a Ralph-loop stop condition

The `--min-accuracy` flag makes this script usable directly as `scripts/ralph-loop.sh`'s
`--test-cmd` (from the Claude Optimisation framework repo) once you're ready to run an actual
autoresearch loop tuning `ai.py`'s prompt:

```bash
bash scripts/ralph-loop.sh --test-cmd "python eval/score_extraction.py --min-accuracy 0.8"
```

**This has not been run yet.** This harness was built and verified standalone; running it as a
tuning loop against `ai.py` (which is live, deployed production code) is a deliberate follow-up,
not automatic.

## Read-only trust boundary (do not violate)

If you (or an agent) are tuning the extraction prompt against this metric: **only edit the
system prompt string inside `ai.py`'s `extract_from_voice`**. Never edit `dataset.jsonl` or
`score_extraction.py` to make the score go up — that's reward-hacking the eval, not improving
the extraction. This is the same rule Karpathy's pattern calls a "read-only trust boundary."

## Dataset

`dataset.jsonl` is a **synthetic starter set** (22 examples) — realistic but hand-written, not
pulled from real bot traffic. Expand it over time with real, anonymized transcripts as the bot
accumulates usage; a bigger, more representative set makes the accuracy number more trustworthy.
