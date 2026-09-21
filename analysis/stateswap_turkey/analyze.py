"""Audit and analyze the saved Türkiye State Swap release, without model calls.

Run from any directory: python analysis/stateswap_turkey/analyze.py
Only pinned Git objects are read. No API runner is imported or executed.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REVISION = "b35f6ca1b97017175fab7d9862d29a057529ec2f"
MODELS = ["openai/gpt-4o-mini", "openai/gpt-4.1-mini", "openai/gpt-5.6-sol"]
ARMS = ["Turkey", "Russia", "Ukraine"]
METRICS = ["likelihood_shift", "absolute_shift", "judgment_change_pct",
           "reversal_pct", "to_abstention_pct", "from_abstention_pct"]
INPUTS = {}


def read(path):
    raw = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{REVISION}:{path}"])
    INPUTS[path] = dict(sha256_git_bytes=hashlib.sha256(raw).hexdigest(),
                        sha256_lf=hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
                        bytes=len(raw))
    return raw.decode("utf-8").replace("\r\n", "\n")


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def category(value):
    return None if value is None else 1 if value > 60 else -1 if value < 40 else 0


def bootstrap(keys, values, draws=2000):
    """Resample judgments together; keep the target-weighted estimand."""
    unique, inverse = np.unique([key[0] for key in keys], return_inverse=True)
    sums = np.zeros((len(unique), values.shape[1]))
    np.add.at(sums, inverse, values)
    counts = np.bincount(inverse)
    rng = np.random.default_rng(731)
    samples = []
    for start in range(0, draws, 256):
        indices = rng.integers(0, len(unique), (min(256, draws-start), len(unique)))
        samples.append(sums[indices].sum(axis=1) / counts[indices].sum(axis=1)[:, None])
    return np.concatenate(samples)


def main():
    cases_path = "data/processed/echr_unified.json"
    summary_path = "data/processed/summaries_dsv41flash.json"
    cases = json.loads(read(cases_path))
    payload = json.loads(read(summary_path))
    summaries = payload["summaries"]
    case_map = {(case["item_id"], case["article_full"]): case for case in cases}
    assert len(case_map) == len(cases) == 1000
    assert len(summaries) == len({key[0] for key in case_map}) == 947
    identity_keys = sorted([case["item_id"], case["target_respondent_code"],
                            case["article_full"], case["target_issue"].casefold()] for case in cases)

    # Extract only literal definitions and the pure string replacement function.
    runner = read("experiments/stateswap_summary_run.py")
    namespace = {"re": re}
    tree = ast.parse(runner)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if any(name in {"SYSTEM", "PREDICTIVE", "COUNTRIES", "TARGET_SETS"} for name in names):
                value = ast.literal_eval(node.value)
                for name in names:
                    namespace[name] = value
        elif isinstance(node, ast.FunctionDef) and node.name == "swap":
            exec(compile(ast.Module(body=[node], type_ignores=[]), "pure_swap", "exec"), namespace)
    namespace["TARGETS"] = namespace["TARGET_SETS"]["turkey"]
    # scoring.py contains only standard-library parsing and aggregation helpers.
    scoring = {}
    exec(compile(read("experiments/scoring.py"), "offline_scoring", "exec"), scoring)
    parse = scoring["parse_rating"]
    countries, targets = namespace["COUNTRIES"], namespace["TARGETS"]
    respondent = {key: case["target_respondent"] for key, case in case_map.items()}
    changed, different = {}, {}
    for key in case_map:
        original = summaries[key[0]][0]
        for arm in ARMS:
            changed[key, arm] = namespace["swap"](original, respondent[key], arm) != original
            different[key, arm] = countries[respondent[key]][1] != targets[arm][1]
    substituted = {(key, arm): changed[key, arm] and different[key, arm]
                   for key in case_map for arm in ARMS}
    records, checks = {}, []
    identities, configs = [], []
    for model in MODELS:
        directory = "data/experiments/stateswap_summary_turkey/" + model.replace("/", "_")
        config = json.loads(read(directory + "/run_config.json"))
        identity = json.loads(read(directory + "/input_identity.json"))
        assert identity["target_keys"] == identity_keys
        assert identity["targets"] == 1000 and identity["judgments"] == 947
        assert identity["dataset_id"] == payload["dataset_id"] == "echr-unified-atomic-targets-20260916"
        assert identity["summaries"] == {"dataset_id": payload["dataset_id"],
            "summarizer": payload["summarizer"], "mode": payload.get("mode", "abstractive"),
            "versions": payload.get("versions", 1), "judgments": 947}
        assert config["model"] == model and config["samples"] == 10
        assert config["limit"] == 0 and config["temperature"] == 1.0 and config["max_tokens"] == 2000
        assert config["rating_parser"] == "anchored-percentage-v1"
        assert config["targets"] == {key: list(value) for key, value in targets.items()}
        assert config["country_aliases_and_demonyms"] == json.loads(json.dumps(countries))
        assert config["cases_sha256"] == INPUTS[cases_path]["sha256_lf"]
        assert config["summaries_sha256"] == INPUTS[summary_path]["sha256_lf"]
        assert config["prompt_sha256"] == hashlib.sha256((namespace["SYSTEM"] + namespace["PREDICTIVE"]).encode()).hexdigest()
        identities.append(identity)
        configs.append({key: value for key, value in config.items() if key != "model"})
        rows = [json.loads(line) for line in read(directory + "/stateswap_summary_results.jsonl").splitlines() if line.strip()]
        assert len(rows) == 4000
        for row in rows:
            key, arm = (row["item_id"], row["article"]), row["arm"]
            assert key in case_map and arm in ["original"] + ARMS
            assert (model, key, arm) not in records
            assert row["key"] == "|".join([*key, arm])
            assert row["respondent"] == respondent[key]
            assert row["violation_label"] == case_map[key]["violation_label"]
            assert row["text_changed"] == (arm != "original" and changed[key, arm])
            ratings, responses, attempts = row["ratings"], row["responses"], row["response_attempts"]
            assert len(ratings) == len(responses) == len(attempts) == 10
            assert [parse(response) for response in responses] == ratings
            assert all(history and history[-1] == response for history, response in zip(attempts, responses))
            assert all(parse(response) is None for history in attempts for response in history[:-1])
            assert row["parse_retry_count"] == sum(len(history)-1 for history in attempts)
            valid = [value for value in ratings if value is not None]
            assert row["n_unparsed"] == len(ratings)-len(valid)
            mean = sum(valid)/len(valid) if valid else None
            assert mean == row["avg_rating"]
            expected = {None: None, -1: "no_violation", 0: "abstention", 1: "violation"}[category(mean)]
            assert row["prediction"] == expected
            assert row["accurate"] == (expected == row["violation_label"])
            records[model, key, arm] = row
        assert all((model, key, arm) in records for key in case_map for arm in ["original"] + ARMS)
        checks.append(dict(model=model, rows=len(rows), requested_ratings=10*len(rows),
            parsed_ratings=sum(10-row["n_unparsed"] for row in rows),
            no_valid_mean=sum(row["avg_rating"] is None for row in rows),
            parse_retries=sum(row["parse_retry_count"] for row in rows),
            raw_responses_reparsed=True, stored_means_verified=True, transformation_flags_verified=True))
    assert all(identity == identities[0] for identity in identities)
    assert all(config == configs[0] for config in configs)
    common = sorted(key for key in case_map if all(substituted[key, arm] for arm in ARMS)
        and all(records[model, key, arm]["avg_rating"] is not None for model in MODELS for arm in ["original"] + ARMS))
    assert len(common) == 785 and len({key[0] for key in common}) == 742
    comparisons = [(model, arm) for model in MODELS for arm in ARMS]
    shifts = np.array([[records[model, key, arm]["avg_rating"] - records[model, key, "original"]["avg_rating"]
                        for model, arm in comparisons] for key in common])
    adjusted = np.quantile(bootstrap(common, shifts, 20000), [.05/18, 1-.05/18], axis=0)
    source_rows = []
    for model, arm in comparisons:
        valid = {key for key in case_map if all(records[model, key, group]["avg_rating"] is not None for group in ["original", arm])}
        eligible = {key for key in valid if substituted[key, arm]}
        scopes = {"common": common, "substituted": sorted(eligible), "all_valid": sorted(valid),
                  "no_substitution": sorted(valid-eligible)}
        for scope, keys in scopes.items():
            values = []
            for key in keys:
                before, after = (records[model, key, group]["avg_rating"] for group in ["original", arm])
                p, q = category(before), category(after)
                values.append([after-before, abs(after-before), 100*(p != q), 100*(p*q == -1),
                               100*(p != 0 and q == 0), 100*(p == 0 and q != 0)])
            values = np.array(values, float)
            means, intervals = values.mean(axis=0), np.quantile(bootstrap(keys, values), [.025, .975], axis=0)
            row = dict(model=model, arm=arm, scope=scope, n=len(keys), judgments=len({key[0] for key in keys}))
            for j, metric in enumerate(METRICS):
                row.update({metric: means[j], metric+"_lo": intervals[0,j], metric+"_hi": intervals[1,j]})
            index = comparisons.index((model, arm))
            row["likelihood_shift_family9_lo"] = adjusted[0,index] if scope == "common" else ""
            row["likelihood_shift_family9_hi"] = adjusted[1,index] if scope == "common" else ""
            source_rows.append(row)
    contrasts = []
    for earlier in MODELS[:2]:
        for arm in ARMS:
            values = shifts[:, comparisons.index((MODELS[2], arm))] - shifts[:, comparisons.index((earlier, arm))]
            sampled = bootstrap(common, values[:,None], 20000)[:,0]
            lo, hi = np.quantile(sampled[:2000], [.025, .975])
            family_lo, family_hi = np.quantile(sampled, [.05/12, 1-.05/12])
            contrasts.append(dict(model="openai/gpt-5.6-sol", reference_model=earlier, arm=arm,
                n=len(common), judgments=742, estimate=values.mean(), lo=lo, hi=hi,
                family6_lo=family_lo, family6_hi=family_hi))
    write_csv("source_data.csv", source_rows)
    write_csv("model_contrasts.csv", contrasts)
    write_csv("response_checks.csv", checks)
    write_csv("cohort.csv", [dict(item_id=key[0], article=key[1], respondent=respondent[key],
        **{f"substituted_{arm}": substituted[key, arm] for arm in ARMS}, common=key in common) for key in sorted(case_map)])
    primary = [row for row in source_rows if row["scope"] == "common"]
    report = ["# Türkiye State Swap follow-up", "", f"Source release: `{REVISION}`. All analysis is offline; no new model calls.", "",
        "## Main finding", "", "Russia and Ukraine substitutions raise mean violation likelihood for GPT-4o mini and GPT-4.1 mini, but lower it for GPT-5.6-sol. All six directions remain after correction across the nine model-by-destination shifts. GPT-5.6-sol also has a negative Türkiye shift. These are model-specific responses to the same country edits, not estimates of a training-cutoff effect.", "",
        "## Inputs and scoring", "", "The three models use the same frozen v1.0 inputs (1,000 targets from 947 judgments) and the same summaries, prompts and scoring settings. Every target has an original arm and Türkiye, Russia and Ukraine arms, each with ten requested ratings at temperature 1.0. All 120,000 final ratings parse. The 44 additional parse attempts are retained and checked. Stored means, labels, response histories and text-change flags were verified against the saved responses and deterministic replacement code.", "",
        "The common comparison includes 785 targets from 742 judgments whose respondent differs from all three destinations, whose summary changes under every substitution, and whose means are valid in all twelve model-arm combinations. Destination-specific substitution counts are 983 for Türkiye, 966 for Russia and 832 for Ukraine. Original Türkiye cases account for the 15-target difference from the original US experiment's 800-target comparison; these are cohort exclusions, not missing model responses.", "",
        "## Common-cohort results", "", "Likelihood shifts are percentage points relative to the original arm of this follow-up run. Judgment changes and strict reversals use all 785 targets; changes involving abstention are counted separately.", "",
        "| Model | Destination | Likelihood shift [95% CI] | Judgment change (%) | Strict reversal (%) |", "| --- | --- | ---: | ---: | ---: |"]
    for row in primary:
        report.append(f"| {row['model'].split('/')[1]} | {'Türkiye' if row['arm']=='Turkey' else row['arm']} | {row['likelihood_shift']:+.2f} [{row['likelihood_shift_lo']:+.2f}, {row['likelihood_shift_hi']:+.2f}] | {row['judgment_change_pct']:.2f} | {row['reversal_pct']:.2f} |")
    report += ["", "## Interpretation and reproducibility", "",
        "The follow-up tests an additional destination without the US arm. It does not implement the separately planned UK/France comparison with an explicitly fixed Convention framework. Country effects are evaluated as likelihood shifts and judgment transitions, not as accuracy under a transplanted reference verdict. The original six-model US run remains a separate comparison with its own original arms and cohort.", "",
        "Pointwise intervals use 2,000 judgment-cluster bootstrap draws with seed 731. Family-adjusted bounds use 20,000 draws and Bonferroni quantiles across nine likelihood shifts or six model contrasts. Each draw keeps all targets of a sampled judgment together and retains target weighting. `source_data.csv` includes the common cohort, destination-specific substitutions, all valid pairs and no-substitution diagnostics. The latter are separately sampled inputs, not paired random-seed controls.", "",
        "Run `python analysis/stateswap_turkey/analyze.py` to reproduce the audit and tables from the pinned Git objects.", ""]
    (OUT/"REPORT.md").write_text("\n".join(report), encoding="utf-8")
    manifest = dict(source_revision=REVISION, new_model_calls=0, models=MODELS, arms=ARMS,
        targets=1000, judgments=947, records=12000, requested_ratings=120000,
        parsed_ratings=sum(row["parsed_ratings"] for row in checks),
        common_targets=len(common), common_judgments=742,
        destination_substitution_counts={arm: sum(substituted[key,arm] for key in case_map) for arm in ARMS},
        changed_text_counts={arm: sum(changed[key,arm] for key in case_map) for arm in ARMS},
        identity=identities[0] | {"target_keys": "Verified against every canonical v1.0 target; see cohort.csv."},
        bootstrap=dict(seed=731, pointwise_draws=2000, family_draws=20000, cluster="judgment", estimand="target-weighted mean"),
        inputs=INPUTS, output_sha256_lf={name: hashlib.sha256((OUT/name).read_bytes().replace(b"\r\n",b"\n")).hexdigest()
            for name in ["source_data.csv", "model_contrasts.csv", "response_checks.csv", "cohort.csv", "REPORT.md"]})
    (OUT/"manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({"records_verified": 12000, "parsed_ratings": manifest["parsed_ratings"],
        "common_targets": len(common), "common_judgments": 742,
        "likelihood_shifts": [{key: row[key] for key in ["model","arm","likelihood_shift","likelihood_shift_family9_lo","likelihood_shift_family9_hi"]} for row in primary]}, indent=2))


if __name__ == "__main__":
    main()
