"""Audit the UK State Swap release and compare its evidence with the Türkiye run.

All inputs are read from pinned Git objects. This script makes no model calls.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
REVISION = "05b96bf53698e503f18f25bd44c3a66f47b67d20"
spec = importlib.util.spec_from_file_location(
    "stateswap_offline_helpers", OUT.parent / "stateswap_turkey" / "analyze.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
h.REVISION = REVISION
h.OUT = OUT
MODELS = h.MODELS
ARMS = ["UK", "Russia", "Ukraine"]


def definitions(source):
    namespace = {"re": re}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                        "SYSTEM", "PREDICTIVE", "COUNTRIES", "TARGET_SETS"}:
                    namespace[target.id] = ast.literal_eval(node.value)
        elif isinstance(node, ast.FunctionDef) and node.name == "swap":
            exec(compile(ast.Module(body=[node], type_ignores=[]), "pure_swap", "exec"), namespace)
    namespace["TARGETS"] = namespace["TARGET_SETS"]["uk"]
    return namespace


def interval_rows(keys, values, labels, family_size):
    samples = h.bootstrap(keys, np.asarray(values, float), 20000)
    pointwise = np.quantile(samples[:2000], [.025, .975], axis=0)
    adjusted = np.quantile(samples, [.05/(2*family_size), 1-.05/(2*family_size)], axis=0)
    estimates = np.mean(values, axis=0)
    return [dict(**label, n=len(keys), judgments=len({key[0] for key in keys}),
                 estimate=estimates[i], lo=pointwise[0,i], hi=pointwise[1,i],
                 family_size=family_size, adjusted_lo=adjusted[0,i], adjusted_hi=adjusted[1,i])
            for i, label in enumerate(labels)]


def main():
    cases_path = "data/processed/echr_unified.json"
    summaries_path = "data/processed/summaries_dsv41flash.json"
    cases = json.loads(h.read(cases_path))
    summaries = json.loads(h.read(summaries_path))["summaries"]
    case_map = {(case["item_id"], case["article_full"]): case for case in cases}
    assert len(case_map) == len(cases) == 1000
    assert len(summaries) == len({key[0] for key in case_map}) == 947
    ns = definitions(h.read("experiments/stateswap_summary_run.py"))
    parser = {}
    exec(compile(h.read("experiments/scoring.py"), "offline_scoring", "exec"), parser)
    parse = parser["parse_rating"]
    changed, substituted = {}, {}
    for key, case in case_map.items():
        original = summaries[key[0]][0]
        for arm in ARMS:
            changed[key, arm] = ns["swap"](original, case["target_respondent"], arm) != original
            different = ns["COUNTRIES"][case["target_respondent"]][1] != ns["TARGETS"][arm][1]
            substituted[key, arm] = changed[key, arm] and different

    records, checks = {}, []
    for model in MODELS:
        directory = "data/experiments/stateswap_summary_uk/" + model.replace("/", "_")
        config = json.loads(h.read(directory + "/run_config.json"))
        assert config["model"] == model and config["samples"] == 10
        assert config["limit"] == 0 and config["temperature"] == 1.0 and config["max_tokens"] == 2000
        assert config["rating_parser"] == "anchored-percentage-v1"
        assert config["targets"] == json.loads(json.dumps(ns["TARGETS"]))
        assert config["country_aliases_and_demonyms"] == json.loads(json.dumps(ns["COUNTRIES"]))
        assert config["cases_sha256"] == h.INPUTS[cases_path]["sha256_lf"]
        assert config["summaries_sha256"] == h.INPUTS[summaries_path]["sha256_lf"]
        assert config["prompt_sha256"] == hashlib.sha256((ns["SYSTEM"] + ns["PREDICTIVE"]).encode()).hexdigest()
        rows = [json.loads(line) for line in h.read(directory + "/stateswap_summary_results.jsonl").splitlines() if line]
        assert len(rows) == 4000
        for row in rows:
            key, arm = (row["item_id"], row["article"]), row["arm"]
            assert key in case_map and arm in ["original"] + ARMS
            assert (model, key, arm) not in records
            assert row["key"] == "|".join([*key, arm])
            assert row["respondent"] == case_map[key]["target_respondent"]
            assert row["violation_label"] == case_map[key]["violation_label"]
            assert row["text_changed"] == (arm != "original" and changed[key, arm])
            ratings, responses, histories = row["ratings"], row["responses"], row["response_attempts"]
            assert len(ratings) == len(responses) == len(histories) == 10
            assert [parse(response) for response in responses] == ratings
            assert all(history and history[-1] == response for history, response in zip(histories, responses))
            assert all(parse(response) is None for history in histories for response in history[:-1])
            assert row["parse_retry_count"] == sum(len(history)-1 for history in histories)
            assert row["n_unparsed"] == sum(value is None for value in ratings) == 0
            mean = sum(ratings)/10
            assert mean == row["avg_rating"]
            expected = {-1:"no_violation", 0:"abstention", 1:"violation"}[h.category(mean)]
            assert row["prediction"] == expected
            assert row["accurate"] == (expected == row["violation_label"])
            records[model, key, arm] = row
        assert all((model,key,arm) in records for key in case_map for arm in ["original"]+ARMS)
        checks.append(dict(model=model, rows=len(rows), parsed_ratings=10*len(rows),
                           parse_retries=sum(row["parse_retry_count"] for row in rows),
                           raw_responses_reparsed=True, stored_means_verified=True,
                           transformation_flags_verified=True))

    common = sorted(key for key in case_map if all(substituted[key,arm] for arm in ARMS))
    comparisons = [(model,arm) for model in MODELS for arm in ARMS]
    shifts = np.array([[records[model,key,arm]["avg_rating"]-records[model,key,"original"]["avg_rating"]
                        for model,arm in comparisons] for key in common])
    effects = interval_rows(common, shifts, [dict(model=m,arm=a) for m,a in comparisons], 9)
    source = []
    for index, (model,arm) in enumerate(comparisons):
        for scope, keys in [("common", common), ("substituted", sorted(key for key in case_map if substituted[key,arm]))]:
            values = []
            for key in keys:
                before, after = (records[model,key,a]["avg_rating"] for a in ["original",arm])
                p,q = h.category(before),h.category(after)
                values.append([after-before, abs(after-before), 100*(p!=q), 100*(p*q==-1),
                               100*(p!=0 and q==0), 100*(p==0 and q!=0)])
            values = np.array(values, float)
            limits = np.quantile(h.bootstrap(keys, values), [.025,.975], axis=0)
            row = dict(model=model, arm=arm, scope=scope, n=len(keys), judgments=len({k[0] for k in keys}))
            for j,metric in enumerate(h.METRICS):
                row.update({metric:values[:,j].mean(), metric+"_lo":limits[0,j], metric+"_hi":limits[1,j]})
            if scope == "common":
                row.update(likelihood_shift_family9_lo=effects[index]["adjusted_lo"],
                           likelihood_shift_family9_hi=effects[index]["adjusted_hi"])
            else:
                row.update(likelihood_shift_family9_lo="", likelihood_shift_family9_hi="")
            source.append(row)
    pairs = [(m,a) for m in MODELS for a in ["Russia","Ukraine"]]
    direct = np.array([[records[m,k,"UK"]["avg_rating"]-records[m,k,a]["avg_rating"]
                        for m,a in pairs] for k in common])
    contrasts = interval_rows(common, direct, [dict(model=m,comparison="UK minus "+a) for m,a in pairs], 6)
    model_pairs = [(m,a) for m in MODELS[:2] for a in ARMS]
    between_models = np.column_stack([shifts[:,comparisons.index((MODELS[2],a))]-shifts[:,comparisons.index((m,a))]
                                      for m,a in model_pairs])
    model_contrasts = interval_rows(common, between_models,
        [dict(model=MODELS[2],reference_model=m,arm=a) for m,a in model_pairs], 6)
    core = [key for key in common if not key[1].upper().startswith("P")]
    core_values = np.array([[records[m,k,a]["avg_rating"]-records[m,k,"original"]["avg_rating"]
                            for m,a in comparisons] for k in core])
    core_effects = interval_rows(core,core_values,[dict(model=m,arm=a) for m,a in comparisons],9)
    h.write_csv("source_data.csv",source)
    h.write_csv("destination_contrasts.csv",contrasts)
    h.write_csv("model_contrasts.csv",model_contrasts)
    h.write_csv("response_checks.csv",checks)
    h.write_csv("convention_articles_sensitivity.csv",core_effects)
    h.write_csv("cohort.csv",[dict(item_id=k[0],article=k[1],respondent=case_map[k]["target_respondent"],
        **{f"substituted_{a}":substituted[k,a] for a in ARMS},common=k in common) for k in sorted(case_map)])
    manifest = dict(source_revision=REVISION,new_model_calls=0,models=MODELS,arms=ARMS,
        targets=1000,judgments=947,records=12000,parsed_ratings=120000,
        common_targets=len(common),common_judgments=len({k[0] for k in common}),
        convention_articles_targets=len(core),convention_articles_judgments=len({k[0] for k in core}),
        destination_substitution_counts={a:sum(substituted[k,a] for k in case_map) for a in ARMS},
        changed_text_counts={a:sum(changed[k,a] for k in case_map) for a in ARMS},
        bootstrap=dict(seed=731,pointwise_draws=2000,family_draws=20000,cluster="judgment",estimand="target-weighted mean"),
        inputs=h.INPUTS)
    report = ["# UK State Swap analysis", "",
        f"Source revision: `{REVISION}`. All analysis is offline; no new model calls.", "",
        "## Finding", "",
        "Replacing the respondent with the United Kingdom lowers mean violation likelihood in all three GPT models. Each UK effect remains negative after correction across nine model-by-destination effects. Russia and Ukraine raise scores for both mini models. GPT-5.6-sol has a negative Ukraine effect; its Russia estimate has a pointwise interval crossing zero.", "",
        "## Comparison", "",
        f"All nine comparisons use the same {len(common)} targets from {manifest['common_judgments']} judgments. Every retained target has a different original respondent and changed summary text in all three destination arms. Each model is compared with the original arm collected in this UK run. Effects are score changes on a 0-100 scale, expressed in percentage points.", "",
        "| Model | Destination | Likelihood shift [95% CI] | Judgment change (%) | Strict reversal (%) |",
        "| --- | --- | ---: | ---: | ---: |"]
    for r in source:
        if r["scope"] == "common":
            report.append(f"| {r['model'].split('/')[1]} | {r['arm']} | {r['likelihood_shift']:+.2f} [{r['likelihood_shift_lo']:+.2f}, {r['likelihood_shift_hi']:+.2f}] | {r['judgment_change_pct']:.2f} | {r['reversal_pct']:.2f} |")
    report += ["", "The UK condition changes 4.5%, 11.7% and 9.1% of categorical judgments for GPT-4o mini, GPT-4.1 mini and GPT-5.6-sol. Most changes enter or leave abstention. The respective strict reversal rates are 0.0%, 1.8% and 2.4%.", "",
        "## Additional analysis", "",
        "Restricting the comparison to Convention articles removes Protocol targets and leaves 675 targets from 641 judgments. The UK effects remain negative after correction across nine effects: -1.22 for GPT-4o mini, -2.94 for GPT-4.1 mini and -1.84 for GPT-5.6-sol. This subset is reported in `convention_articles_sensitivity.csv`.", "",
        "`destination_contrasts.csv` compares UK directly with Russia and Ukraine on the same targets. Five of the six differences remain below zero after correction; the adjusted interval for Sol's UK-minus-Ukraine contrast crosses zero. `model_contrasts.csv` tests differences between Sol and the earlier models directly.", "",
        "## Validation and reproducibility", "",
        "All 12,000 records and 120,000 final ratings were checked against the canonical targets and saved raw responses. The audit reproduces means and predictions and checks all response histories. There are 57 retained parse retries. Configurations match the v1.0 input hashes and the released prompt and country-replacement code.", "",
        "The UK destination changes the respondent and summary text for 981 targets. The corresponding counts are 966 for Russia and 832 for Ukraine. Their intersection yields the 783-target common comparison. The other 217 targets are excluded by this comparison definition rather than by missing scores.", "",
        "Pointwise intervals use 2,000 judgment-cluster bootstrap draws with seed 731. Family intervals use 20,000 draws and Bonferroni quantiles. Each resample retains all targets from a judgment and preserves the target-weighted estimand. Effects are analyzed within this run; the Türkiye run keeps its own original arms and cohort.", "",
        "Reproduce with `python analysis/stateswap_uk/analyze.py`.", ""]
    (OUT/"REPORT.md").write_text("\n".join(report),encoding="utf-8")
    names=["source_data.csv","destination_contrasts.csv","model_contrasts.csv","response_checks.csv",
           "convention_articles_sensitivity.csv","cohort.csv","REPORT.md"]
    manifest["output_sha256_lf"]={name:hashlib.sha256((OUT/name).read_bytes().replace(b"\r\n",b"\n")).hexdigest() for name in names}
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(common_targets=len(common),common_judgments=manifest["common_judgments"],
        substitution_counts=manifest["destination_substitution_counts"],checks=checks,
        effects=effects,destination_contrasts=contrasts),indent=2))


if __name__ == "__main__":
    main()
