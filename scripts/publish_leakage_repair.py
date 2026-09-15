"""Validate and publish the reviewed, single-summary evaluation input release.

Dry-run is the default. The original corpus is read from the pinned pre-repair Git
commit, so publication and subsequent offline verification use the same baseline.
No target-model calls or manuscript edits are performed here.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.leak_audit.reviews import accepted_generations, digest, passed, read_reviews
from experiments.summaries import (
    LEAK_SAFE_SUMMARY_TEMPLATE,
    LEAK_SAFE_SUMMARY_TEMPLATE_V2,
    SUMMARY_TEMPLATE,
)
from scripts.validate_eval_dataset import validate as validate_current_release

BASE_COMMIT = "4a1ba1117a047dac7553ca2cfd3100a18171a841"
FIELD = "full_case_text_no_verdict"
MODEL = "deepseek/deepseek-v4.1-flash"
RELEASE_ID = "echr-unified-1000-leakchecked-single-v1-20260916"
AUDIT = ROOT / "data/audits/leakage_20260915"
POSTCUT_AUDIT = ROOT / "data/audits/verdict_spans"
DATA_PATH = "data/processed/echr_unified.json"
SUMMARY_PATH = "data/processed/summaries_dsv41flash.json"
MANIFEST_PATH = "configs/evaluation_dataset.json"


def serialize(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def file_hash(raw):
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def original(path):
    return json.loads(subprocess.check_output(["git", "show", f"{BASE_COMMIT}:{path}"], cwd=ROOT))


def head_blob(path):
    return subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=ROOT)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def assemble(old_rows, new_rows, old_blob, source_reviews, summary_reviews, generations,
             provenance, current_blob=None):
    check(len(new_rows) == len(old_rows), "Instance count changed")
    for before, after in zip(old_rows, new_rows):
        check({k:v for k,v in before.items() if k != FIELD} ==
              {k:v for k,v in after.items() if k != FIELD}, "Non-text instance metadata changed")
    old_by, new_by = {}, {}
    for old, new in zip(old_rows, new_rows):
        key = new["item_id"]
        if key in new_by:
            check(new_by[key][FIELD] == new[FIELD], "Inconsistent text for repeated judgment")
        old_by[key], new_by[key] = old, new
    check(not provenance["unresolved"], "Unresolved structural source repairs")
    check(set(old_blob["summaries"]) == set(new_by), "Summary judgment IDs changed")
    check(old_blob["summarizer"] == MODEL, "Unexpected original summarizer")
    mapping, registry, gaps = {}, {}, []
    source_hashes = {}
    for item_id, case in new_by.items():
        source = case[FIELD][:50000]
        source_sha = digest(source)
        source_hashes[item_id] = source_sha
        if not source or not passed(source_reviews.get((item_id, source_sha))):
            gaps.append({"item_id": item_id, "reason": "source_not_approved"})
            continue
        # Select original index 0 before looking at any evaluator's response.
        key = f"{item_id}:0"
        old_summary = old_blob["summaries"][item_id][0]
        current_summary = (
            current_blob.get("summaries", {}).get(item_id, [old_summary])[0]
            if current_blob else old_summary
        )
        source_changed = source != old_by[item_id][FIELD][:50000]
        old_review = summary_reviews.get((key, digest(old_summary)))
        needed = source_changed or not passed(old_review)
        generated = generations.get((key, source_sha))
        generated_selected = generated is not None and (
            needed
            or generated.get("supersedes_summary_sha256") == digest(current_summary)
            or generated.get("summary_sha256") == digest(current_summary)
        )
        if generated_selected:
            check(generated["version"] == 0 and generated["model"] == MODEL,
                  "Generated summary version or model changed")
            check(generated["temperature"] == 1.0 and generated["max_source_characters"] == 50000,
                  "Generation settings changed")
            check(generated["previous_summary_sha256"] == digest(old_summary), "Original summary mismatch")
            prompt_version = generated.get("generation_prompt_version")
            template = (
                LEAK_SAFE_SUMMARY_TEMPLATE
                if prompt_version == "leak-safe-v3"
                else LEAK_SAFE_SUMMARY_TEMPLATE_V2
                if prompt_version == "leak-safe-v2"
                else SUMMARY_TEMPLATE
            )
            prompt = template.format(case_name=case["case_name"], full_text=source)
            check(generated["generation_prompt_sha256"] == digest(prompt), "Generation prompt mismatch")
            summary = generated["summary"]
            origin = "regenerated_from_reviewed_source"
        elif needed:
            gaps.append({"item_id": item_id, "reason": "summary_regeneration_pending"})
            continue
        else:
            summary = old_summary
            origin = "reviewed_original_version_0"
        check(isinstance(summary, str) and summary.strip() and not summary.startswith("ERROR:"),
              "Unusable summary")
        mapping[item_id] = [summary]
        registry[item_id] = {"source_input_sha256": source_sha,
                             "summary_sha256": digest(summary), "origin": origin,
                             "original_version_index": 0}
    report = {"status": "READY" if not gaps else "PENDING", "release_id": RELEASE_ID,
              "original_commit": BASE_COMMIT, "instances": len(new_rows), "judgments": len(new_by),
              "summary_versions": 1, "selected_original_version_index": 0,
              "source_inputs_approved": sum(passed(source_reviews.get((k,h))) for k,h in source_hashes.items()),
              "summaries_ready": len(mapping), "gaps": gaps,
              "source_text_changes": provenance["source_changes"],
              "source_model_input_changes": provenance["model_inputs_changed"],
              "restored_factual_appendices": sum(bool(r["factual_appendix"]) for r in provenance["changes"]),
              "annual_counts": dict(sorted(Counter(r["decision_date"][:4] for r in new_rows).items())),
              "labels": dict(Counter(r["violation_label"] for r in new_rows)),
              "scope": "Prompt-level current-ECtHR outcome and merits-reasoning leakage; not pretraining overlap",
              "input_registry": registry}
    blob = {"summarizer": MODEL, "versions": 1, "n_judgments": len(new_by),
            "n_complete": len(mapping), "release_id": RELEASE_ID,
            "selected_original_version_index": 0,
            "selection_rule": "Original version 0 fixed before evaluation; no selection using model scores.",
            "historical_usage_metadata": {k:old_blob[k] for k in ("prompt_tokens", "completion_tokens") if k in old_blob},
            "usage_note": "Historical counters are not full-release usage. Repair calls and retries are in the audit checkpoints.",
            "summaries": mapping}
    spec = {"schema_version": 1, "status": "APPROVED" if not gaps else "PENDING",
            "release_id": RELEASE_ID, "dataset_sha256_lf": file_hash(serialize(new_rows)),
            "summaries_sha256_lf": file_hash(serialize(blob)), "max_case_characters": 50000,
            "versions": 1, "source_inputs": source_hashes,
            "summary_inputs": {k:[digest(s[0])] for k,s in mapping.items()},
            "review_evidence": "data/audits/leakage_20260915/repair_release_report.json"}
    return blob, spec, report


def before_review_counts(rows, reviews):
    by = {r["item_id"]:r for r in rows}
    groups = {name:set() for name in ("conclusion", "reasoning", "either")}
    for item_id, row in by.items():
        rec = reviews.get((item_id, digest(row[FIELD][:50000])))
        check(rec is not None, "Missing original-input review")
        for name in ("conclusion", "reasoning"):
            if rec["result"][name]:
                groups[name].add(item_id)
                groups["either"].add(item_id)
    return {name:{"judgments": len(ids), "instances": sum(r["item_id"] in ids for r in rows),
                  "instance_rate_percent": 100*sum(r["item_id"] in ids for r in rows)/len(rows)}
            for name,ids in groups.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=AUDIT / "proposed_sources.json")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    sources_path = args.sources if args.sources.exists() else ROOT / DATA_PATH
    old_rows, old_blob = original(DATA_PATH), original(SUMMARY_PATH)
    new_rows = json.loads(sources_path.read_text(encoding="utf-8"))
    provenance = json.loads((AUDIT / "proposed_sources.provenance.json").read_text(encoding="utf-8"))
    generation_paths = sorted(p for p in AUDIT.glob("summary_regeneration*.jsonl")
                              if not p.name.endswith(".attempts.jsonl"))
    second_pass = AUDIT / "summary_second_pass.jsonl"
    if second_pass.exists():
        generation_paths.append(second_pass)
    current_blob = json.loads((ROOT / SUMMARY_PATH).read_text(encoding="utf-8"))
    source_reviews = read_reviews(AUDIT / "proposed_source_reviews.jsonl")
    source_reviews.update(read_reviews(POSTCUT_AUDIT / "postcut_source_reviews.jsonl"))
    blob, spec, report = assemble(old_rows, new_rows, old_blob,
        source_reviews,
        read_reviews(AUDIT / "original_summary_reviews.jsonl"),
        accepted_generations(generation_paths), provenance, current_blob)
    cuts = json.loads((POSTCUT_AUDIT / "procedural_history_cuts.json").read_text(encoding="utf-8"))
    report["procedural_history_cuts"] = {
        "status": cuts["status"],
        "judgments": cuts["judgments"],
        "instances": cuts["instances"],
        "characters_removed": sum(row["characters_removed"] for row in cuts["cuts"]),
        "verification": "data/audits/verdict_spans/postcut_verification_20260916.json",
    }
    report["original_input_machine_review"] = before_review_counts(old_rows, read_reviews(AUDIT / "original_source_reviews.jsonl"))
    report["rate_interpretation"] = "Evidence-grounded machine-review positive rates, not fully human-adjudicated prevalence. Categories overlap."
    report["dataset_sha256_lf"] = spec["dataset_sha256_lf"]
    report["summaries_sha256_lf"] = spec["summaries_sha256_lf"]
    print(json.dumps({k:v for k,v in report.items() if k not in ("input_registry", "gaps")}, indent=2))
    if report["gaps"]:
        print(json.dumps({"pending": len(report["gaps"]), "first_10": report["gaps"][:10]}, indent=2))
        if args.publish:
            raise SystemExit("Publication refused: every source and summary must pass")
        return
    if not args.publish:
        print("All release checks passed; --publish is required to replace canonical inputs.")
        return
    manifest = original(MANIFEST_PATH)
    manifest["dataset_id"] = RELEASE_ID
    manifest["source_commit"] = BASE_COMMIT
    manifest["dataset"]["sha256_lf"] = spec["dataset_sha256_lf"]
    manifest["summaries"].update(sha256_lf=spec["summaries_sha256_lf"], versions=1,
        represented_judgments=len(blob["summaries"]), complete_judgments=blob["n_complete"],
        usable_summaries=blob["n_complete"], missing_slots_zero_based=[])
    manifest["input_release"] = {"path": "data/processed/input_release.json", "release_id": RELEASE_ID}
    manifest["provenance_notes"].extend([
        "The main experiment now uses original version index 0 only, selected without evaluator scores.",
        "Every selected source and summary is hash-bound to accepted leakage-review evidence.",
        "Adjudicated earlier-instance and excluded-complaint outcomes were cut from 11 judgments and 12 case-article instances before this release.",
        "The original DeepSeek V4.1 Flash summarizer regenerated all 11 summaries whose source changed in the final cut.",
        "Earlier results and the historical three-version summaries are not current-release results."])
    # Refuse to overwrite any unrelated concurrent data edits. Each file must be
    # either the pinned original, the currently approved release, or this script's
    # fully validated output.
    current_release_valid = False
    try:
        validate_current_release(require_complete=True)
        current_release_valid = True
    except ValueError:
        pass
    previous_spec_raw = head_blob("data/processed/input_release.json")
    previous_spec = json.loads(previous_spec_raw)
    previous_manifest = json.loads(head_blob(MANIFEST_PATH))
    previous_release_valid = (
        previous_spec.get("status") == "APPROVED"
        and file_hash(head_blob(DATA_PATH)) == previous_spec.get("dataset_sha256_lf")
        and file_hash(head_blob(SUMMARY_PATH)) == previous_spec.get("summaries_sha256_lf")
        and previous_manifest.get("dataset_id") == previous_spec.get("release_id")
        and previous_manifest.get("input_release", {}).get("release_id") == previous_spec.get("release_id")
    )
    previous_outputs = {
        DATA_PATH: json.loads(head_blob(DATA_PATH)),
        SUMMARY_PATH: json.loads(head_blob(SUMMARY_PATH)),
        MANIFEST_PATH: previous_manifest,
    }
    outputs = {DATA_PATH:new_rows, SUMMARY_PATH:blob, MANIFEST_PATH:manifest}
    for path, value in outputs.items():
        current = json.loads((ROOT / path).read_text(encoding="utf-8"))
        check(current == original(path) or current == value or current_release_valid
              or (previous_release_valid and current == previous_outputs[path]),
              f"Concurrent changes in {path}; publication refused")
    current_spec = json.loads((ROOT / "data/processed/input_release.json").read_text(encoding="utf-8"))
    check(current_spec == previous_spec or current_spec == spec,
          "Concurrent changes in data/processed/input_release.json; publication refused")
    report["status"] = "APPROVED"
    (AUDIT / "repair_release_report.json").write_bytes(serialize(report))
    for path, value in outputs.items():
        (ROOT / path).write_bytes(serialize(value))
    # Approval is written last. An interrupted publication cannot approve a
    # partially assembled set of inputs.
    (ROOT / "data/processed/input_release.json").write_bytes(serialize(spec))
    print("Published reviewed single-summary release. Target-model evaluations were not rerun.")


if __name__ == "__main__":
    main()
