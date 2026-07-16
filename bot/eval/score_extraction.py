#!/usr/bin/env python3
"""score_extraction.py — the scalar metric for the founder-crm-bot autoresearch loop
(PRACTITIONER_SETUPS.md #3). Runs ai.extract_from_voice() against eval/dataset.jsonl
and scores field-level accuracy on the deterministic/categorical fields only.

Usage:   python eval/score_extraction.py [--min-accuracy 0.8] [--verbose]
Example: python eval/score_extraction.py --min-accuracy 0.8

Requires ANTHROPIC_API_KEY set (real API calls — small but non-zero cost, Haiku model,
one call per dataset row). Never edit this file or dataset.jsonl to make the score pass —
see README.md's read-only trust boundary rule.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATASET_PATH = Path(__file__).resolve().parent / "dataset.jsonl"

# Fields scored by exact/presence match — free-text fields (summary, next_action) are
# excluded from the scalar metric; grading prose needs a human or a second LLM-as-judge,
# which reintroduces the non-determinism this metric is designed to avoid. See README.md.
SCORED_FIELDS = ["stage", "contact_name_present", "company_present", "budget_signal_present"]


def load_dataset():
    if not DATASET_PATH.exists():
        print(f"ERROR: dataset not found at {DATASET_PATH}", file=sys.stderr)
        sys.exit(1)
    rows = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"ERROR: dataset.jsonl line {line_num} is not valid JSON: {e}", file=sys.stderr)
                sys.exit(1)
    if not rows:
        print("ERROR: dataset.jsonl is empty", file=sys.stderr)
        sys.exit(1)
    return rows


def score_one(actual: dict, expected: dict) -> dict:
    """Returns {field: bool_correct} for each scored field."""
    result = {}

    result["stage"] = actual.get("stage") == expected.get("stage")

    for presence_field, actual_key in [
        ("contact_name_present", "contact_name"),
        ("company_present", "company"),
        ("budget_signal_present", "budget_signal"),
    ]:
        expected_present = expected.get(presence_field, False)
        actual_present = actual.get(actual_key) not in (None, "", "null")
        result[presence_field] = expected_present == actual_present

    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-accuracy", type=float, default=0.0,
                         help="Exit non-zero if field-level accuracy falls below this threshold (0.0-1.0)")
    parser.add_argument("--verbose", action="store_true", help="Print per-example results")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set — this script calls the real Anthropic API "
              "and cannot run without it.", file=sys.stderr)
        sys.exit(1)

    # Imported after the API-key check so --help works without credentials.
    from ai import extract_from_voice

    rows = load_dataset()
    total_fields = 0
    correct_fields = 0
    failures = []

    for i, row in enumerate(rows, start=1):
        transcript = row["transcript"]
        expected = row["expected"]

        try:
            actual = extract_from_voice(transcript)
        except Exception as e:
            print(f"ERROR: extraction failed on row {i}: {e}", file=sys.stderr)
            actual = {}

        field_results = score_one(actual, expected)
        for field, correct in field_results.items():
            total_fields += 1
            if correct:
                correct_fields += 1
            else:
                failures.append((i, field, expected.get(field), actual))

        if args.verbose:
            status = "OK" if all(field_results.values()) else "MISS"
            print(f"[{status}] row {i}: {field_results}")

    accuracy = correct_fields / total_fields if total_fields else 0.0

    print(f"\nField-level accuracy: {correct_fields}/{total_fields} = {accuracy:.1%}")

    if failures:
        print(f"\n{len(failures)} field mismatch(es):")
        for row_num, field, expected_val, actual_row in failures:
            print(f"  row {row_num} — {field}: expected {expected_val!r}, got {actual_row!r}")

    if accuracy < args.min_accuracy:
        print(f"\nFAIL: accuracy {accuracy:.1%} is below --min-accuracy {args.min_accuracy:.1%}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
