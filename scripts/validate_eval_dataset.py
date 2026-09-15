#!/usr/bin/env python3
"""Verify the frozen evaluation cohort and paired summaries without model calls."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "configs" / "evaluation_dataset.json"


def sha256_lf(raw):
    """Keep artifact identity stable across Git's LF/CRLF checkout conversion."""
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def validate(manifest=None, require_complete=False):
    config = json.loads(MANIFEST.read_text(encoding="utf-8")) if manifest is None else manifest
    ds, ss = config["dataset"], config["summaries"]

    def check(condition, message):
        if not condition:
            raise ValueError(message)

    def read(spec, name):
        raw = (REPO / spec["path"]).read_bytes()
        check(sha256_lf(raw) == spec["sha256_lf"], f"{name} SHA256 mismatch (LF-normalized)")
        return json.loads(raw)

    rows, payload = read(ds, "Dataset"), read(ss, "Summaries")
    check(isinstance(rows, list) and bool(rows), "Dataset must be a nonempty list")
    keys = [tuple(row[field] for field in ds["instance_key"]) for row in rows]
    check(len(keys) == len(set(keys)), "Duplicate compound instance keys")
    ids = {row["item_id"] for row in rows}
    years = dict(sorted(Counter(row["decision_date"][:4] for row in rows).items()))
    labels = dict(Counter(row["violation_label"] for row in rows))
    check(len(rows) == ds["instances"] and len(ids) == ds["judgments"], "Dataset counts mismatch")
    check(years == ds["annual_counts"], "Annual distribution mismatch")
    check(labels == ds["labels"], "Label distribution mismatch")
    check(min(row["decision_date"] for row in rows) == ds["date_min"] and
          max(row["decision_date"] for row in rows) == ds["date_max"], "Date range mismatch")
    check(payload["summarizer"] == ss["summarizer"], "Summarizer mismatch")
    check(payload["versions"] == ss["versions"], "Summary version count mismatch")
    summaries, versions = payload["summaries"], ss["versions"]
    check(versions == 1, "Only one summary per judgment is supported")
    check(set(summaries) <= ids, "Summaries contain judgments outside the dataset")
    check(all(isinstance(v, list) and len(v) == versions for v in summaries.values()),
          f"Each represented judgment must have exactly {versions} summary slots")

    def usable(item_id, version):
        value = summaries.get(item_id, [None] * versions)[version]
        return isinstance(value, str) and bool(value.strip()) and not value.strip().startswith("ERROR:")

    missing = [[item_id, version] for item_id in sorted(ids) for version in range(versions)
               if not usable(item_id, version)]
    complete = sum(all(usable(item_id, v) for v in range(versions)) for item_id in ids)
    usable_count = len(ids) * versions - len(missing)
    check(len(summaries) == ss["represented_judgments"] and complete == ss["complete_judgments"]
          and usable_count == ss["usable_summaries"], "Summary coverage mismatch")
    check(payload["n_judgments"] == len(ids) and payload["n_complete"] == complete,
          "Summary coverage metadata mismatch")
    check(missing == ss["missing_slots_zero_based"], "Missing summary slots differ from manifest")
    warnings = []
    if missing:
        warnings.append(f"{len(missing)} missing summary slots; retain the frozen cohort and complete before full-coverage runs.")
        check(not require_complete, warnings[-1])
    reviewed_release = None
    if "input_release" in config:
        spec = json.loads((REPO / config["input_release"]["path"]).read_text(encoding="utf-8"))
        check(spec.get("status") == "APPROVED", "Input release is not approved")
        check(spec["release_id"] == config["input_release"]["release_id"], "Input release ID mismatch")
        check(spec["dataset_sha256_lf"] == ds["sha256_lf"] and spec["summaries_sha256_lf"] == ss["sha256_lf"],
              "Input release file hashes mismatch")
        text_hash = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
        source_hashes = {r["item_id"]:text_hash(r["full_case_text_no_verdict"][:50000]) for r in rows}
        summary_hashes = {k:[text_hash(value) for value in values] for k,values in summaries.items()}
        check(source_hashes == spec["source_inputs"], "Unreviewed source inputs")
        check(summary_hashes == spec["summary_inputs"], "Unreviewed summary inputs")
        check(versions == spec["versions"], "Input release version count mismatch")
        reviewed_release = spec["release_id"]
    return {
        "dataset_id": config["dataset_id"], "instances": len(rows), "judgments": len(ids),
        "annual_counts": years, "labels": labels, "date_range": [ds["date_min"], ds["date_max"]],
        "dataset_sha256_lf": ds["sha256_lf"], "summaries_sha256_lf": ss["sha256_lf"],
        "summarizer": payload["summarizer"], "versions": versions,
        "usable_summaries": usable_count, "complete_judgments": complete,
        "missing_judgments": sorted(ids - set(summaries)), "missing_slots_zero_based": missing,
        "instance_coverage_by_version": [sum(usable(row["item_id"], v) for row in rows)
                                         for v in range(versions)],
        "warnings": warnings,
        "reviewed_input_release": reviewed_release,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--require-complete", action="store_true",
                        help="fail if any judgment summary is missing")
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
