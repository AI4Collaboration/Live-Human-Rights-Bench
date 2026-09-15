#!/usr/bin/env python3
"""Rescore-derived metrics with one complete, predeclared global BH family.

Never pool summary draws, reuse stale q-values, or correct a partial roster.
The current family contains 6 summary, 18 framing and 6 reconsideration tests.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
from stats import balanced_accuracy, benjamini_hochberg, flip_direction, mcnemar_exact
from scoring import majority_vote, mean_rating
from run_protocol import SCORING, SUMMARY_PROTOCOL

DEFAULT_FAMILY = ROOT / "configs/perturbation_analysis.json"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def key(row):
    return row["item_id"], row["article"]


def validate_summary_results(rows):
    keys = [key(r) for r in rows]
    if len(keys) != len(set(keys)) or any(r.get("summary_version", 0) != 0 for r in rows):
        raise ValueError("RQ1 expects one summary result per case-article instance; historical multi-version results cannot be pooled")


def validate_rows(rows, expected, label):
    keys = [key(r) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != set(expected):
        raise ValueError(f"{label}: incomplete, duplicated or different case-article cohort")
    for r in rows:
        if r.get("violation_label") != expected[key(r)]:
            raise ValueError(f"{label}: reference label mismatch")


def prediction(row, samples, field="ratings"):
    values = row.get(field)
    if (not isinstance(values, list) or len(values) != samples
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 100 for v in values)):
        raise ValueError(f"Incomplete or malformed samples: {row.get('item_id')}/{field}")
    return majority_vote(values)[0]


def describe(rows):
    n = len(rows)
    directions = Counter(r["flip_direction"] for r in rows if r.get("flip_direction"))
    return {
        "n_instances": n,
        "accuracy": sum(r["accurate"] for r in rows) / n,
        "balanced_accuracy": balanced_accuracy(rows),
        "alignment_rate": sum(r["aligned"] for r in rows) / n if "aligned" in rows[0] else None,
        "abstention_rate": sum(r["prediction"] == "abstention" for r in rows) / n,
        "mean_violation_likelihood": sum(r["avg_rating"] for r in rows) / n,
        "flip_rate": sum(directions.values()) / n if "aligned" in rows[0] else None,
        "flips_to_violation": directions.get("no_violation->violation", 0),
        "flips_to_no_violation": directions.get("violation->no_violation", 0),
        "flips_to_abstention": sum(v for k,v in directions.items() if k.endswith("->abstention")),
        "flips_out_of_abstention": sum(v for k,v in directions.items() if k.startswith("abstention->")),
        "n_unparsed": 0,
    }


def apply_global_bh(comparisons, expected_count, alpha=0.05):
    tested = [r for r in comparisons if r["arm"] != "baseline"]
    if len(tested) != expected_count:
        raise ValueError("Incomplete BH family; refusing partial-family q-values")
    identities = [(r["model"], r["arm"], r["variant"]) for r in tested]
    if len(set(identities)) != expected_count:
        raise ValueError("Duplicated hypothesis in BH family")
    if any(not isinstance(r.get("mcnemar_p"), (float, int)) or not math.isfinite(r["mcnemar_p"])
           or not 0 <= r["mcnemar_p"] <= 1 for r in tested):
        raise ValueError("Invalid p-value in BH family")
    for row, q in zip(tested, benjamini_hochberg([r["mcnemar_p"] for r in tested])):
        row.update(mcnemar_q=q, significant_bh=q < alpha, bh_family_size=expected_count)
    for row in comparisons:
        if row["arm"] == "baseline":
            row.update(mcnemar_q=None, significant_bh=None, bh_family_size=expected_count)
    return comparisons


def analyze_family(run_dir, family, cases, release):
    if release.get("status") != "APPROVED" or release.get("versions") != 1:
        raise ValueError("A reviewed single-summary release is required")
    expected = {key(r): r["violation_label"] for r in cases}
    if len(expected) != len(cases):
        raise ValueError("Ambiguous legacy article keys in the current cohort")
    models = family["models"]
    if len(models) != len(set(models)) or not models:
        raise ValueError("Family model roster must be nonempty and unique")
    variants_by_arm = {"rq1": ["single_summary"], "rq2": ["predictive", "normative", "factual"], "rq3": ["reconsideration"]}
    if family["comparisons"] != variants_by_arm or family["expected_comparisons"] != len(models) * 5:
        raise ValueError("Family must declare one summary, three framing and one reconsideration comparison per model")
    if family["references"] != {"rq1": "baseline", "rq2": "baseline", "rq3": "same_trajectory_initial_response"}:
        raise ValueError("Comparison references differ from this protocol")
    comparisons, provenance, sample_counts, protocols = [], {}, set(), set()
    for model in models:
        directory = Path(run_dir) / model.replace("/", "_").replace(".", "_")
        identity = read(directory / "input_identity.json")
        if any(identity.get(k) != release[k] for k in ("release_id", "summaries_sha256_lf")) or identity.get("cases_sha256_lf") != release["dataset_sha256_lf"]:
            raise ValueError(f"{model}: results are not a rescore of the approved inputs")
        settings = read(directory / "run_config.json")
        if (settings.get("model") != model or settings.get("summary_protocol") != SUMMARY_PROTOCOL
                or settings.get("scoring") != SCORING or not settings.get("prompts_sha256")):
            raise ValueError(f"{model}: missing single-summary run provenance")
        protocols.add(json.dumps({k:v for k,v in settings.items() if k not in {"model", "base_url", "samples"}}, sort_keys=True))
        samples = settings.get("samples")
        if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
            raise ValueError("Missing target sample count")
        sample_counts.add(samples)
        results = {arm: read(directory / f"{arm}_results.json") for arm in ("baseline", "rq1", "rq2", "rq3")}
        validate_rows(results["baseline"], expected, f"{model}/baseline")
        baseline = {}
        for r in results["baseline"]:
            pred = prediction(r, samples)
            baseline[key(r)] = {**r, "prediction": pred, "accurate": pred == expected[key(r)], "avg_rating": mean_rating(r["ratings"])}
        comparisons.append({"model": model, "arm": "baseline", "variant": "", **describe(list(baseline.values())),
                            "accuracy_delta": None, "mcnemar_p": None, "mcnemar_n": None})
        validate_summary_results(results["rq1"])
        for arm, variants in variants_by_arm.items():
            if arm == "rq2" and {r.get("framing") for r in results[arm]} != set(variants):
                raise ValueError(f"{model}/rq2: framing set differs from declared family")
            for variant in variants:
                subset = [r for r in results[arm] if arm != "rq2" or r["framing"] == variant]
                validate_rows(subset, expected, f"{model}/{arm}/{variant}")
                normalized, n01, n10, ref_correct = [], 0, 0, 0
                for r in subset:
                    gold = expected[key(r)]
                    if arm == "rq3":
                        reference = prediction(r, samples, "original_ratings")
                        pred = prediction(r, samples, "challenged_ratings")
                        values = r["challenged_ratings"]
                    else:
                        reference = baseline[key(r)]["prediction"]
                        pred = prediction(r, samples)
                        values = r["ratings"]
                    a, b = reference == gold, pred == gold
                    n01 += not a and b
                    n10 += a and not b
                    ref_correct += a
                    normalized.append({**r, "prediction": pred, "accurate": b, "aligned": pred == reference,
                        "avg_rating": mean_rating(values), "flip_direction": flip_direction(reference, pred)})
                discordant, pval = mcnemar_exact(n01, n10)
                metrics = describe(normalized)
                comparisons.append({"model": model, "arm": arm, "variant": variant, **metrics,
                    "accuracy_delta": metrics["accuracy"] - ref_correct / len(subset),
                    "mcnemar_n": discordant, "mcnemar_p": pval,
                    "better_than_reference": n01, "worse_than_reference": n10})
        provenance[model] = {name: digest(directory / name) for name in
            ["input_identity.json", "run_config.json", "baseline_results.json", "rq1_results.json", "rq2_results.json", "rq3_results.json"]}
    if len(sample_counts) != 1:
        raise ValueError("Target sample counts differ across models")
    if len(protocols) != 1:
        raise ValueError("Prompts or scoring settings differ across models")
    apply_global_bh(comparisons, family["expected_comparisons"], family.get("alpha", .05))
    return comparisons, {"status": "COMPLETE", "family_id": family["family_id"], "release_id": release["release_id"],
        "models": len(models), "instances_per_comparison": len(cases), "samples_per_instance": next(iter(sample_counts)),
        "comparisons_by_arm": {arm: len(models)*len(v) for arm,v in variants_by_arm.items()},
        "bh_family_size": family["expected_comparisons"], "input_provenance": provenance}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--family", type=Path, default=DEFAULT_FAMILY)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    output = args.out or Path(args.run_dir) / "single_summary_statistics.csv"
    try:
        family = read(args.family)
        manifest = read(ROOT / family["input_manifest"])
        release = read(ROOT / manifest["input_release"]["path"])
        case_path = ROOT / manifest["dataset"]["path"]
        summary_path = ROOT / manifest["summaries"]["path"]
        if digest(case_path) != release["dataset_sha256_lf"] or digest(summary_path) != release["summaries_sha256_lf"]:
            raise ValueError("Current data files differ from the approved release")
        cases = read(case_path)
        rows, report = analyze_family(args.run_dir, family, cases, release)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"No q-values produced: {error}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report.update(family_config_sha256=digest(args.family), statistics_sha256=digest(output))
    output.with_suffix(".provenance.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "input_provenance"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
