#!/usr/bin/env python3
"""Derive the complete predeclared perturbation family from atomic-target results.

All 1,000 targets are validated. Headline hypothesis tests use substantive targets;
Articles 34 and 38 are retained and described separately as procedural targets.
"""

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
from input_gate import verify_cases, verify_summaries
from run_protocol import SCORING, SUMMARY_PROTOCOL
from scoring import majority_vote, mean_rating
from stats import balanced_accuracy, benjamini_hochberg, flip_direction, mcnemar_exact
from targets import target_key, target_stratum


DEFAULT_FAMILY = ROOT / "configs/perturbation_analysis.json"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def key(row):
    return target_key(row)


def expected_input_identity(manifest, cases):
    keys = sorted(target_key(row) for row in cases)
    summaries = manifest["summaries"]
    return {
        "dataset_id": manifest["dataset_id"],
        "targets": len(cases),
        "judgments": len({row["item_id"] for row in cases}),
        "target_unit": manifest["dataset"]["target_contract"]["unit"],
        "target_keys": [list(value) for value in keys],
        "summaries": {
            "dataset_id": manifest["dataset_id"],
            "summarizer": summaries["summarizer"],
            "mode": "abstractive",
            "versions": 1,
            "judgments": summaries["represented_judgments"],
        },
    }


def validate_summary_results(rows):
    keys = [key(row) for row in rows]
    if len(keys) != len(set(keys)) or any(row.get("summary_version", 0) != 0 for row in rows):
        raise ValueError(
            "RQ1 expects one summary result per atomic target; historical multi-version results cannot be pooled"
        )


def validate_rows(rows, expected, label):
    keys = [key(row) for row in rows]
    if len(keys) != len(set(keys)) or set(keys) != set(expected):
        raise ValueError(f"{label}: incomplete, duplicated, or different atomic-target cohort")
    for row in rows:
        if row.get("violation_label") != expected[key(row)]:
            raise ValueError(f"{label}: reference label mismatch")


def prediction(row, samples, field="ratings"):
    values = row.get(field)
    if (
        not isinstance(values, list)
        or len(values) != samples
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 100
            for value in values
        )
    ):
        raise ValueError(f"Incomplete or malformed samples: {row.get('target_id')}/{field}")
    return majority_vote(values)[0]


def describe(rows):
    if not rows:
        return {
            "n_instances": 0,
            "accuracy": None,
            "balanced_accuracy": None,
            "alignment_rate": None,
            "abstention_rate": None,
            "mean_violation_likelihood": None,
            "flip_rate": None,
            "flips_to_violation": 0,
            "flips_to_no_violation": 0,
            "flips_to_abstention": 0,
            "flips_out_of_abstention": 0,
            "n_unparsed": 0,
        }
    n = len(rows)
    directions = Counter(row["flip_direction"] for row in rows if row.get("flip_direction"))
    return {
        "n_instances": n,
        "accuracy": sum(row["accurate"] for row in rows) / n,
        "balanced_accuracy": balanced_accuracy(rows),
        "alignment_rate": (
            sum(row["aligned"] for row in rows) / n if "aligned" in rows[0] else None
        ),
        "abstention_rate": sum(row["prediction"] == "abstention" for row in rows) / n,
        "mean_violation_likelihood": sum(row["avg_rating"] for row in rows) / n,
        "flip_rate": sum(directions.values()) / n if "aligned" in rows[0] else None,
        "flips_to_violation": directions.get("no_violation->violation", 0),
        "flips_to_no_violation": directions.get("violation->no_violation", 0),
        "flips_to_abstention": sum(
            value for direction, value in directions.items() if direction.endswith("->abstention")
        ),
        "flips_out_of_abstention": sum(
            value for direction, value in directions.items() if direction.startswith("abstention->")
        ),
        "n_unparsed": 0,
    }


def procedural_description(rows):
    metrics = describe(rows)
    return {
        "procedural_n": metrics["n_instances"],
        "procedural_accuracy": metrics["accuracy"],
        "procedural_balanced_accuracy": metrics["balanced_accuracy"],
        "procedural_abstention_rate": metrics["abstention_rate"],
        "procedural_mean_violation_likelihood": metrics["mean_violation_likelihood"],
    }


def apply_global_bh(comparisons, expected_count, alpha=0.05):
    tested = [row for row in comparisons if row["arm"] != "baseline"]
    if len(tested) != expected_count:
        raise ValueError("Incomplete BH family; refusing partial-family q-values")
    identities = [(row["model"], row["arm"], row["variant"]) for row in tested]
    if len(set(identities)) != expected_count:
        raise ValueError("Duplicated hypothesis in BH family")
    if any(
        not isinstance(row.get("mcnemar_p"), (float, int))
        or not math.isfinite(row["mcnemar_p"])
        or not 0 <= row["mcnemar_p"] <= 1
        for row in tested
    ):
        raise ValueError("Invalid p-value in BH family")
    adjusted = benjamini_hochberg([row["mcnemar_p"] for row in tested])
    for row, q_value in zip(tested, adjusted):
        row.update(
            mcnemar_q=q_value,
            significant_bh=q_value < alpha,
            bh_family_size=expected_count,
        )
    for row in comparisons:
        if row["arm"] == "baseline":
            row.update(mcnemar_q=None, significant_bh=None, bh_family_size=expected_count)
    return comparisons


def analyze_family(run_dir, family, cases, manifest):
    if manifest["summaries"].get("versions") != 1:
        raise ValueError("A reviewed single-summary dataset is required")
    expected = {key(row): row["violation_label"] for row in cases}
    if len(expected) != len(cases):
        raise ValueError("Atomic target keys are not unique")
    substantive = {
        key(row) for row in cases if target_stratum(row["article_full"]) == "substantive"
    }
    procedural = set(expected) - substantive
    if not substantive:
        raise ValueError("No substantive targets are available for headline analysis")

    models = family["models"]
    if len(models) != len(set(models)) or not models:
        raise ValueError("Family model roster must be nonempty and unique")
    variants_by_arm = {
        "rq1": ["single_summary"],
        "rq2": ["predictive", "normative", "factual"],
        "rq3": ["reconsideration"],
    }
    if family["comparisons"] != variants_by_arm or family["expected_comparisons"] != len(models) * 5:
        raise ValueError(
            "Family must declare one summary, three framing, and one reconsideration comparison per model"
        )
    if family["references"] != {
        "rq1": "baseline",
        "rq2": "baseline",
        "rq3": "same_trajectory_initial_response",
    }:
        raise ValueError("Comparison references differ from this protocol")

    expected_identity = expected_input_identity(manifest, cases)
    comparisons, provenance, sample_counts, protocols = [], {}, set(), set()
    for model in models:
        directory = Path(run_dir) / model.replace("/", "_").replace(".", "_")
        identity = read(directory / "input_identity.json")
        if identity != expected_identity:
            raise ValueError(f"{model}: results do not match the active atomic-target inputs")
        settings = read(directory / "run_config.json")
        if (
            settings.get("model") != model
            or settings.get("summary_protocol") != SUMMARY_PROTOCOL
            or settings.get("scoring") != SCORING
            or not settings.get("prompt_version")
        ):
            raise ValueError(f"{model}: missing single-summary run settings")
        protocols.add(
            json.dumps(
                {
                    name: value
                    for name, value in settings.items()
                    if name not in {"model", "base_url", "samples"}
                },
                sort_keys=True,
            )
        )
        samples = settings.get("samples")
        if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
            raise ValueError("Missing target sample count")
        sample_counts.add(samples)

        results = {
            arm: read(directory / f"{arm}_results.json")
            for arm in ("baseline", "rq1", "rq2", "rq3")
        }
        validate_rows(results["baseline"], expected, f"{model}/baseline")
        baseline = {}
        for row in results["baseline"]:
            pred = prediction(row, samples)
            baseline[key(row)] = {
                **row,
                "prediction": pred,
                "accurate": pred == expected[key(row)],
                "avg_rating": mean_rating(row["ratings"]),
            }
        primary_baseline = [baseline[value] for value in substantive]
        procedural_baseline = [baseline[value] for value in procedural]
        comparisons.append(
            {
                "model": model,
                "arm": "baseline",
                "variant": "",
                **describe(primary_baseline),
                **procedural_description(procedural_baseline),
                "validated_targets": len(expected),
                "accuracy_delta": None,
                "mcnemar_p": None,
                "mcnemar_n": None,
            }
        )

        validate_summary_results(results["rq1"])
        for arm, variants in variants_by_arm.items():
            if arm == "rq2" and {row.get("framing") for row in results[arm]} != set(variants):
                raise ValueError(f"{model}/rq2: framing set differs from declared family")
            for variant in variants:
                subset = [
                    row
                    for row in results[arm]
                    if arm != "rq2" or row["framing"] == variant
                ]
                validate_rows(subset, expected, f"{model}/{arm}/{variant}")
                normalized, n01, n10, reference_correct = [], 0, 0, 0
                for row in subset:
                    gold = expected[key(row)]
                    if arm == "rq3":
                        reference = prediction(row, samples, "original_ratings")
                        pred = prediction(row, samples, "challenged_ratings")
                        values = row["challenged_ratings"]
                    else:
                        reference = baseline[key(row)]["prediction"]
                        pred = prediction(row, samples)
                        values = row["ratings"]
                    reference_is_correct, current_is_correct = reference == gold, pred == gold
                    if key(row) in substantive:
                        n01 += not reference_is_correct and current_is_correct
                        n10 += reference_is_correct and not current_is_correct
                        reference_correct += reference_is_correct
                    normalized.append(
                        {
                            **row,
                            "prediction": pred,
                            "accurate": current_is_correct,
                            "aligned": pred == reference,
                            "avg_rating": mean_rating(values),
                            "flip_direction": flip_direction(reference, pred),
                        }
                    )
                primary = [row for row in normalized if key(row) in substantive]
                procedural_rows = [row for row in normalized if key(row) in procedural]
                discordant, p_value = mcnemar_exact(n01, n10)
                metrics = describe(primary)
                comparisons.append(
                    {
                        "model": model,
                        "arm": arm,
                        "variant": variant,
                        **metrics,
                        **procedural_description(procedural_rows),
                        "validated_targets": len(expected),
                        "accuracy_delta": metrics["accuracy"] - reference_correct / len(primary),
                        "mcnemar_n": discordant,
                        "mcnemar_p": p_value,
                        "better_than_reference": n01,
                        "worse_than_reference": n10,
                    }
                )
        provenance[model] = {
            "directory": str(directory),
            "prompt_version": settings["prompt_version"],
            "result_rows": {name: len(rows) for name, rows in results.items()},
        }

    if len(sample_counts) != 1:
        raise ValueError("Target sample counts differ across models")
    if len(protocols) != 1:
        raise ValueError("Prompts or scoring settings differ across models")
    apply_global_bh(comparisons, family["expected_comparisons"], family.get("alpha", 0.05))
    return comparisons, {
        "status": "COMPLETE",
        "family_id": family["family_id"],
        "dataset_id": manifest["dataset_id"],
        "models": len(models),
        "validated_targets_per_comparison": len(expected),
        "substantive_targets_per_headline_comparison": len(substantive),
        "procedural_targets_reported_separately": len(procedural),
        "samples_per_instance": next(iter(sample_counts)),
        "comparisons_by_arm": {
            arm: len(models) * len(variants) for arm, variants in variants_by_arm.items()
        },
        "bh_family_size": family["expected_comparisons"],
        "input_provenance": provenance,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--family", type=Path, default=DEFAULT_FAMILY)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = args.out or Path(args.run_dir) / "single_summary_statistics.csv"
    try:
        family = read(args.family)
        manifest = read(ROOT / family["input_manifest"])
        cases = read(ROOT / manifest["dataset"]["path"])
        summaries = read(ROOT / manifest["summaries"]["path"])
        verify_cases(cases)
        verify_summaries(summaries["summaries"], metadata=summaries)
        rows, report = analyze_family(args.run_dir, family, cases, manifest)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"No q-values produced: {error}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(field for row in rows for field in row))
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report.update(
        family_config=str(args.family),
        statistics_path=str(output),
    )
    output.with_suffix(".provenance.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "input_provenance"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
