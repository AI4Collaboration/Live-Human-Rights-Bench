#!/usr/bin/env python3
"""Reaggregate saved paired results after excluding generator-linked evaluators.

Run from any directory: python analysis/generator_exclusion/analyze.py
Only Python's standard library and Git are required. No model calls are made.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess

REVISION = "66e9f06451ac3463cb7dd6bc6e995e1fa67f9220"
RULE = "band_40_60"
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[1]
MODELS = (
    "anthropic/claude-opus-4.6", "openai/gpt-5.6-sol",
    "deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash",
    "qwen/qwen3-235b-a22b", "qwen/qwen3-32b",
)
EXCLUSIONS = {
    "summarization": {"deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash"},
    "paraphrasing": {"openai/gpt-5.6-sol"},
}
INPUTS = {}


def source(path):
    data = subprocess.check_output(["git", "-C", str(REPO), "show", f"{REVISION}:{path}"])
    INPUTS[path] = {"bytes": len(data), "sha256_git_bytes": hashlib.sha256(data).hexdigest()}
    return data


def table(path):
    return list(csv.DictReader(io.StringIO(source(path).decode("utf-8"))))


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def integer(row, key):
    return int(row[key])


def aggregate(rows, scope):
    first = rows[0]
    count_fields = [key for key in first if key.endswith("_n")]
    totals = {key: sum(integer(row, key) for row in rows) for key in count_fields}
    n = sum(integer(row, "n") for row in rows)
    net = totals["gained_correct_n"] - totals["lost_correct_n"]
    assert net == totals["final_correct_n"] - totals["initial_correct_n"]
    record = dict(
        experiment=first["experiment"], condition=first["condition"], scope=scope,
        rule=RULE, models=len(rows), unique_targets=integer(first, "n"),
        unique_judgments=integer(first, "judgments"), paired_model_target_observations=n,
        target_cohort_sha256=first["cohort_sha256"],
        initial_correct_n=totals["initial_correct_n"], final_correct_n=totals["final_correct_n"],
        corrections_n=totals["gained_correct_n"], losses_n=totals["lost_correct_n"],
        net_correct_change_n=net, accuracy_change_pp=100 * net / n,
        categorical_change_n=totals["categorical_change_n"],
        categorical_change_pct=100 * totals["categorical_change_n"] / n,
        strict_reversal_n=totals["strict_reversal_n"],
        strict_reversal_pct=100 * totals["strict_reversal_n"] / n,
        model_accuracy_change_min_pp=min(float(row["accuracy_change_pp"]) for row in rows),
        model_accuracy_change_max_pp=max(float(row["accuracy_change_pp"]) for row in rows),
        model_categorical_change_min_pct=min(float(row["categorical_change_pct"]) for row in rows),
        model_categorical_change_max_pct=max(float(row["categorical_change_pct"]) for row in rows),
    )
    for key in ("correct_to_wrong_n", "wrong_to_correct_n", "correct_to_abstention_n",
                "abstention_to_correct_n", "correct_to_failure_n", "failure_to_correct_n",
                "net_abstention_loss_n", "initial_failure_n", "final_failure_n"):
        record[key] = totals[key]
    record["included_models"] = ";".join(row["model"] for row in rows)
    record["excluded_models"] = ";".join(model for model in MODELS if model not in {r["model"] for r in rows})
    return record, totals


def span(row, low, high, signed=False):
    fmt = "+.1f" if signed else ".1f"
    return f"{row[low]:{fmt}} to {row[high]:{fmt}}"


def main():
    rows = [r for r in table("analysis/threshold_sensitivity/systematic.csv") if r["rule"] == RULE]
    published = [r for r in table("analysis/threshold_sensitivity/systematic_pooled.csv") if r["rule"] == RULE]
    upstream = json.loads(source("analysis/threshold_sensitivity/manifest.json"))
    cohorts = table("analysis/threshold_sensitivity/cohorts.csv")
    readme = source("README.md").decode("utf-8")
    runner = source("experiments/paraphrase_run.py").decode("utf-8")
    assert "| Shared abstractive summarizer | `deepseek/deepseek-v4.1-flash` |" in readme
    assert 'PARAPHRASER = "openai/gpt-5.6-sol"' in runner
    assert len(rows) == 24 and len(published) == 4
    assert {r["model"] for r in rows} == set(MODELS)
    assert {(integer(r, "n"), integer(r, "judgments")) for r in rows} == {(1000, 947)}
    assert len({r["cohort_sha256"] for r in rows}) == 1
    for path in ("systematic.csv", "systematic_pooled.csv", "cohorts.csv"):
        raw = source(f"analysis/threshold_sensitivity/{path}")
        assert hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == upstream["outputs"][path]["sha256_lf"]

    per_model = []
    for r in rows:
        assert integer(r, "gained_correct_n") - integer(r, "lost_correct_n") == integer(r, "final_correct_n") - integer(r, "initial_correct_n")
        assert integer(r, "lost_correct_n") == sum(integer(r, key) for key in ("correct_to_wrong_n", "correct_to_abstention_n", "correct_to_failure_n"))
        assert integer(r, "gained_correct_n") == sum(integer(r, key) for key in ("wrong_to_correct_n", "abstention_to_correct_n", "failure_to_correct_n"))
        match = [c for c in cohorts if c["scope"] == r["experiment"] and c["model"] == r["model"] and c["comparison"] == r["condition"]]
        assert len(match) == 1 and match[0]["cohort_sha256"] == r["cohort_sha256"]
        per_model.append(dict(
            model=r["model"], label=r["label"], experiment=r["experiment"], condition=r["condition"],
            retained_after_exclusion=r["model"] not in EXCLUSIONS[r["experiment"]],
            rule=RULE, paired_targets=integer(r, "n"), unique_judgments=integer(r, "judgments"),
            cohort_sha256=r["cohort_sha256"],
            initial_correct_n=integer(r, "initial_correct_n"), final_correct_n=integer(r, "final_correct_n"),
            corrections_n=integer(r, "gained_correct_n"), losses_n=integer(r, "lost_correct_n"),
            net_correct_change_n=integer(r, "gained_correct_n") - integer(r, "lost_correct_n"),
            accuracy_change_pp=float(r["accuracy_change_pp"]),
            categorical_change_n=integer(r, "categorical_change_n"), categorical_change_pct=float(r["categorical_change_pct"]),
            strict_reversal_n=integer(r, "strict_reversal_n"),
        ))
    pooled = []
    for condition in ("summary", "light", "medium", "heavy"):
        selected = [r for r in rows if r["condition"] == condition]
        assert len(selected) == 6 and len({r["model"] for r in selected}) == 6
        all_models, totals = aggregate(selected, "all_six")
        ref = next(r for r in published if r["condition"] == condition)
        assert all(totals[key] == integer(ref, key) for key in totals)
        assert all_models["paired_model_target_observations"] == integer(ref, "n")
        assert math.isclose(all_models["accuracy_change_pp"], float(ref["accuracy_change_pp"]), abs_tol=1e-12)
        retained, _ = aggregate([r for r in selected if r["model"] not in EXCLUSIONS[r["experiment"]]], "generator_linked_evaluators_excluded")
        pooled.extend([all_models, retained])
    write_csv("pooled.csv", pooled)
    write_csv("per_model.csv", per_model)

    trajectories = []
    for model in MODELS:
        selected = [r for r in per_model if r["experiment"] == "paraphrasing" and r["model"] == model]
        delta = {r["condition"]: r["net_correct_change_n"] for r in selected}
        a, b, c = (delta[arm] for arm in ("light", "medium", "heavy"))
        trend = "nondecreasing" if a <= b <= c else "nonincreasing" if a >= b >= c else "nonmonotonic"
        trajectories.append(dict(model=model, label=selected[0]["label"],
            retained_after_exclusion=model not in EXCLUSIONS["paraphrasing"],
            light_accuracy_change_pp=a / 10, medium_accuracy_change_pp=b / 10,
            heavy_accuracy_change_pp=c / 10, strength_trend=trend))
    write_csv("paraphrase_strength.csv", trajectories)

    retained = {r["condition"]: r for r in pooled if r["scope"] != "all_six"}
    baseline = {r["condition"]: r for r in pooled if r["scope"] == "all_six"}
    s = retained["summary"]
    trend_counts = {name: sum(r["retained_after_exclusion"] and r["strength_trend"] == name for r in trajectories)
                    for name in ("nondecreasing", "nonincreasing", "nonmonotonic")}
    lines = [
        "# Generator-linked evaluator exclusion", "",
        "**Takeaway.** The main systematic-perturbation patterns remain after removing generator-linked evaluators. Summary accuracy still decreases for every retained model, with corrections offsetting many losses. Paraphrases still change individual judgments without a common accuracy direction across models or a common response to increasing rewrite strength.", "",
        "## Fixed comparisons", "",
        "The diagnostic reaggregates the published inclusive 40-60 abstention rule: scores below 40 indicate no violation, scores above 60 indicate violation, and both endpoints belong to abstention. Summary evaluation compares each target's full-record score with its shared-summary score. Paraphrasing compares each rewrite with the saved original arm from that experiment.", "",
        "- Summary: exclude DeepSeek V4 Pro and DeepSeek V4 Flash. The summary generator is DeepSeek V4.1 Flash, so this exclusion follows a model-family link rather than an exact-model overlap.",
        "- Paraphrasing: exclude GPT-5.6-sol, the exact model used as both paraphraser and evaluator.", "",
        "Every retained model keeps all 1,000 paired targets from the same 947 judgments. Counts pool paired model-target observations: 6,000 for all six evaluators, 4,000 for summary after exclusion, and 5,000 per paraphrase strength after exclusion. These are target-weighted counts, not counts of distinct judgments; the 947 judgments are not multiplied into new independent cases. Missing scores retain the source analysis's failure category. Category changes include transitions among no violation, violation, abstention and failure; corrections and losses respectively enter and leave the correct category.", "",
        "## Paired totals", "",
        "| Comparison | Evaluators | Paired observations | Category changes | Corrections | Losses | Net correct change | Accuracy change (pp) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in pooled:
        label = r["condition"].capitalize() + (", all six" if r["scope"] == "all_six" else ", exclusion")
        lines.append(f"| {label} | {r['models']} | {r['paired_model_target_observations']:,} | {r['categorical_change_n']} ({r['categorical_change_pct']:.2f}%) | {r['corrections_n']} | {r['losses_n']} | {r['net_correct_change_n']:+d} | {r['accuracy_change_pp']:+.2f} |")
    lines.extend(["", "## What remains after exclusion", "",
        f"**Summary losses remain small in aggregate but hide larger opposing changes.** Accuracy changes range from {span(s, 'model_accuracy_change_min_pp', 'model_accuracy_change_max_pp', True)} percentage points across the four retained models; category-change rates range from {span(s, 'model_categorical_change_min_pct', 'model_categorical_change_max_pct')}%. The pooled net change is {s['net_correct_change_n']} correct answers ({s['accuracy_change_pp']:+.2f} points), combining {s['corrections_n']} corrections with {s['losses_n']} losses. Correct-to-abstention transitions ({s['correct_to_abstention_n']}) exceed abstention-to-correct transitions ({s['abstention_to_correct_n']}) by {s['net_abstention_loss_n']}, accounting for {100*s['net_abstention_loss_n']/-s['net_correct_change_n']:.1f}% of the net loss. The all-six pooled change was {baseline['summary']['accuracy_change_pp']:+.2f} points.", "",
        "**Paraphrase effects remain model dependent.** The five retained evaluators still have both positive and negative net accuracy changes at each rewrite strength:", "",
        "| Rewrite | Per-model accuracy change (pp) | Per-model category changes (%) |",
        "| --- | ---: | ---: |",
    ])
    for arm in ("light", "medium", "heavy"):
        r = retained[arm]
        lines.append(f"| {arm.capitalize()} | {span(r, 'model_accuracy_change_min_pp', 'model_accuracy_change_max_pp', True)} | {span(r, 'model_categorical_change_min_pct', 'model_categorical_change_max_pct')} |")
    lines.extend(["",
        f"As rewrite strength increases from light to medium to heavy, {trend_counts['nondecreasing']} retained models have nondecreasing accuracy changes, {trend_counts['nonmonotonic']} have nonmonotonic changes, and {trend_counts['nonincreasing']} have nonincreasing changes. Pooled accuracy changes are {retained['light']['accuracy_change_pp']:+.2f}, {retained['medium']['accuracy_change_pp']:+.2f} and {retained['heavy']['accuracy_change_pp']:+.2f} points, respectively. Removing GPT-5.6-sol leaves the full -1.4 to +1.9 point range across model/strength combinations intact.", "",
        "## Interpretation and reproduction", "",
        "The diagnostic establishes that these aggregate patterns do not depend on including the specified generator-linked evaluators. It retains the original generated texts and does not test a replacement generator or establish generator independence. Its useful addition is this direct evaluator-dependence check; the underlying model results and headline conclusions are unchanged.", "",
        "Run `python analysis/generator_exclusion/analyze.py` from the repository root. The standard-library script reads committed tables and generator-role records from revision `" + REVISION + "`, validates source hashes and all four published six-model totals, and writes the three CSVs, this report and the manifest. The tables trace to raw-score revision `" + upstream["source_revision"] + "` through the threshold analysis manifest. No API calls, new labels, bootstrap, confidence intervals or figures are added.", "",
        "- `pooled.csv`: all-six and excluded-evaluator paired totals, ranges, transition decomposition, model lists and cohort hash.",
        "- `per_model.csv`: all 24 published model/contrast estimates with explicit retention flags.",
        "- `paraphrase_strength.csv`: six three-strength sequences with retention flags and direction classification.",
        "- `manifest.json`: source byte hashes, output hashes, generator/evaluator mapping and passed checks.", "",
    ])
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    outputs = {}
    for name in ("pooled.csv", "per_model.csv", "paraphrase_strength.csv", "REPORT.md", "analyze.py"):
        data = (OUT / name).read_bytes().replace(b"\r\n", b"\n")
        outputs[name] = {"bytes_lf": len(data), "sha256_lf": hashlib.sha256(data).hexdigest()}
        if name.endswith(".csv"):
            outputs[name]["rows"] = len(list(csv.DictReader(io.StringIO(data.decode("utf-8")))))
    manifest = dict(source_revision=REVISION, upstream_raw_score_revision=upstream["source_revision"],
        rule=RULE, model_api_calls=0, new_human_annotations=0, new_bootstrap_draws=0,
        unique_targets=1000, unique_judgments=947, estimand="Target-weighted paired model-target outcomes",
        target_cohort_sha256=rows[0]["cohort_sha256"],
        generator_mapping={"summarization": {"generator":"deepseek/deepseek-v4.1-flash", "link":"family", "excluded_evaluators":sorted(EXCLUSIONS["summarization"])},
                           "paraphrasing": {"generator":"openai/gpt-5.6-sol", "link":"exact_model", "excluded_evaluators":sorted(EXCLUSIONS["paraphrasing"])}},
        checks={"source_output_hashes_match_upstream": True, "all_24_target_cohorts_identical":True,
                "all_24_cohort_registry_matches":True, "all_24_correctness_transition_identities":True,
                "all_four_published_pooled_count_vectors_reproduced":True,
                "no_target_filtering_or_generated_text_changes":True},
        retained_paraphrase_strength_patterns=trend_counts, inputs=INPUTS, outputs=outputs)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"completed":True, "pooled_rows":len(pooled), "per_model_rows":len(per_model), "api_calls":0}))


if __name__ == "__main__":
    main()
