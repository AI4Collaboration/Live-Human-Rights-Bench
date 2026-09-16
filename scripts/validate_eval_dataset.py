#!/usr/bin/env python3
"""Validate the active cohort, atomic targets and paired summaries."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys


REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "configs" / "evaluation_dataset.json"
sys.path.insert(0, str(REPO / "experiments"))
from input_gate import verify_case
from targets import target_key


OUTCOME_CUE = re.compile(
    r"\b(?:no[- ]violation|non[- ]violation|violation found|finding of a violation|"
    r"pecuniary damage|non-pecuniary damage|just satisfaction)\b",
    re.IGNORECASE,
)


def validate(manifest=None, require_complete=False):
    config = json.loads(MANIFEST.read_text(encoding="utf-8")) if manifest is None else manifest
    ds, ss = config["dataset"], config["summaries"]

    def check(condition, message):
        if not condition:
            raise ValueError(message)

    rows = json.loads((REPO / ds["path"]).read_text(encoding="utf-8"))
    payload = json.loads((REPO / ss["path"]).read_text(encoding="utf-8"))
    check(isinstance(rows, list) and bool(rows), "Dataset must be a nonempty list")
    for row in rows:
        verify_case(row, compare_canonical=False)
        check(not OUTCOME_CUE.search(row["target_issue"]), "Target issue contains an outcome cue")
    keys = [target_key(row) for row in rows]
    check(len(keys) == len(set(keys)), "Duplicate atomic targets")
    ids = {row["item_id"] for row in rows}
    years = dict(sorted(Counter(row["decision_date"][:4] for row in rows).items()))
    labels = dict(Counter(row["violation_label"] for row in rows))
    check(len(rows) == ds["instances"] and len(ids) == ds["judgments"], "Dataset counts mismatch")
    check(years == ds["annual_counts"], "Annual distribution mismatch")
    check(labels == ds["labels"], "Label distribution mismatch")
    check(
        min(row["decision_date"] for row in rows) == ds["date_min"]
        and max(row["decision_date"] for row in rows) == ds["date_max"],
        "Date range mismatch",
    )
    check(payload["dataset_id"] == config["dataset_id"], "Summary dataset ID mismatch")
    check(payload["summarizer"] == ss["summarizer"], "Summarizer mismatch")
    check(payload["versions"] == ss["versions"] == 1, "Exactly one summary is required")
    summaries = payload["summaries"]
    check(set(summaries) == ids, "Summary coverage must exactly match target judgments")

    def usable(item_id):
        values = summaries.get(item_id)
        return (
            isinstance(values, list)
            and len(values) == 1
            and isinstance(values[0], str)
            and bool(values[0].strip())
            and not values[0].strip().startswith("ERROR:")
        )

    missing = [[item_id, 0] for item_id in sorted(ids) if not usable(item_id)]
    complete = len(ids) - len(missing)
    check(len(summaries) == ss["represented_judgments"], "Summary representation mismatch")
    check(complete == ss["complete_judgments"] == ss["usable_summaries"], "Summary completeness mismatch")
    check(payload["n_judgments"] == len(ids) and payload["n_complete"] == complete,
          "Summary metadata mismatch")
    check(missing == ss["missing_slots_zero_based"], "Missing summary slots mismatch")
    if require_complete:
        check(not missing, "Full-coverage run requires every judgment summary")
    audit_path = REPO / ds["target_contract"]["audit"]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    check(audit.get("status") == "PASSED", "Target-scope audit did not pass")
    check(len(audit.get("rows", [])) == len(rows), "Target-scope audit coverage mismatch")
    return {
        "status": "PASSED",
        "dataset_id": config["dataset_id"],
        "instances": len(rows),
        "judgments": len(ids),
        "unique_atomic_targets": len(set(keys)),
        "annual_counts": years,
        "labels": labels,
        "summarizer": payload["summarizer"],
        "versions": 1,
        "usable_summaries": complete,
        "missing_slots_zero_based": missing,
        "warnings": [] if not missing else [f"{len(missing)} summary slots are missing"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        print(json.dumps(validate(manifest, args.require_complete), indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
