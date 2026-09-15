#!/usr/bin/env python3
"""Read-only verdict-leakage triage of the frozen summaries and their inputs.

Lexical candidates are not a verified contamination rate. Court outcomes from
domestic proceedings and earlier ECtHR judgments require contextual review.
This scan does not test pretraining-data overlap and never edits the dataset.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
# Freeze the old screen here to keep the before-repair audit reproducible after
# the production detector is corrected. These are candidates, not gold labels.
_STATES_OUTCOME = re.compile(
    r"(the Court (found|held|concluded|ruled)[^.]{0,60}(violation|no violation)"
    r"|there (has|had) been (a|no) violation"
    r"|(was|were) found to (have )?violat)", re.I)
_SOURCE_DISCUSSES_OUTCOME = re.compile(
    r"(found|held|concluded|ruled)[^.]{0,80}(violation|no violation)"
    r"|there (has|had) been (a|no) violation", re.I)


def asserts_outcome(summary, source_text):
    return bool(summary and _STATES_OUTCOME.search(summary)
                and not _SOURCE_DISCUSSES_OUTCOME.search(source_text or ""))
from scoring import MAX_CASE_CHARS
sys.path.insert(0, str(ROOT / "scripts" / "leak_audit"))
from leakdef import leaking


def digest(raw):
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def snippets(pattern, text, maximum=5):
    return [{"start": m.start(), "end": m.end(),
             "context": text[max(0, m.start()-120):min(len(text), m.end()+240)]}
            for m in list(pattern.finditer(text))[:maximum]]


def audit():
    data_raw = (ROOT / "data/processed/echr_unified.json").read_bytes()
    summary_raw = (ROOT / "data/processed/summaries_dsv41flash.json").read_bytes()
    rows = json.loads(data_raw)
    mapping = json.loads(summary_raw)["summaries"]
    judgments = {}
    for row in rows:
        judgments.setdefault(row["item_id"], row)
    source_patterns = {
        "law_heading_without_line_start_requirement": re.compile(r"\bTHE LAW\b"),
        "court_assessment_heading": re.compile(r"The Court['’]s (?:assessment|evaluation)", re.I),
    }
    candidates, source_candidates, legacy_flags = [], [], []
    for item_id, row in judgments.items():
        source = (row.get("full_case_text_no_verdict") or row.get("verdict_free_text") or "")[:MAX_CASE_CHARS]
        source_hits = {key: snippets(pattern, source) for key, pattern in source_patterns.items()}
        if any(source_hits.values()):
            source_candidates.append({"item_id": item_id, "case_name": row["case_name"],
                "status": "REVIEW_REQUIRED_NOT_CONFIRMED_LEAK", "source_characters": len(source),
                "legacy_structural_flag": leaking(source), "hits": source_hits})
        for version, summary in enumerate(mapping[item_id]):
            old_flag = asserts_outcome(summary, source)
            if old_flag:
                legacy_flags.append([item_id, version])
            hits = snippets(_STATES_OUTCOME, summary)
            if hits:
                candidates.append({"item_id": item_id, "case_name": row["case_name"],
                    "version_zero_based": version, "status": "REVIEW_REQUIRED_NOT_CONFIRMED_LEAK",
                    "legacy_summary_flag": old_flag, "summary_matches": hits,
                    "source_wide_bypass_match": snippets(_SOURCE_DISCUSSES_OUTCOME, source, 1)})
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Prompt-level verdict leakage; not pretraining contamination",
        "dataset_sha256_lf": digest(data_raw), "summaries_sha256_lf": digest(summary_raw),
        "instances": len(rows), "judgments": len(judgments),
        "summaries_scanned": sum(len(v) for v in mapping.values()),
        "counts": {"legacy_summary_flags": len(legacy_flags),
            "explicit_outcome_wording_candidates": len(candidates),
            "source_wide_bypass_candidates": sum(not x["legacy_summary_flag"] for x in candidates),
            **{key: sum(bool(x["hits"][key]) for x in source_candidates) for key in source_patterns}},
        "legacy_summary_flags": legacy_flags,
        "interpretation": "Candidate counts are not leak rates; distinguish current ECtHR findings from domestic and prior judgments.",
        "manually_verified_examples": [
            {"item_id": "001-243363", "versions_zero_based": [0, 2],
             "kind": "SUMMARY_CURRENT_CASE_VERDICT_ASSERTION",
             "evidence": "The Court found a violation of Article 1 of Protocol No. 1",
             "legacy_bypass": "Source mentions a Constitutional Court finding about reasonable time, which wrongly exempts the whole summary."},
            {"item_id": "001-126349", "kind": "SOURCE_CURRENT_CASE_CONCLUSION",
             "evidence": "There has, accordingly, been a separate violation of Article 1 of Protocol No. 1."},
            {"item_id": "001-245460", "kind": "SOURCE_CURRENT_CASE_MERITS_ASSESSMENT",
             "evidence": "the authorities did not deploy all necessary efforts to enforce fully and in due time judgment no. 4917/2012",
             "failure_mode": "THE LAW follows preceding text on the same line; short merits remainder also defeats the legacy length threshold."},
            {"item_id": "001-238515", "kind": "TABLE_OF_CONTENTS_FALSE_POSITIVE_IN_FIRST_50000_CHARACTERS",
             "evidence": "The retained THE LAW and assessment headings in the evaluated prefix belong to the table of contents, followed by factual background."},
        ],
        "summary_candidates": candidates, "source_candidates": source_candidates,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                     ("instances", "judgments", "summaries_scanned", "counts")}, indent=2))


if __name__ == "__main__":
    main()
