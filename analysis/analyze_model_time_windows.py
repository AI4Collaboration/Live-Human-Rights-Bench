"""Analyze earlier-model cutoff windows, with primary models as references.

Offline only. Reads immutable Git objects and never imports experiment runners.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from analyze_reliability_controls import (
    MODELS, GitSource, bootstrap_totals, category, finite, ground_truth, write_csv,
)

REVISION = "8c876a920864bfa3352927551161b16166572d35"
OLD = [
    ("openai/gpt-4o-mini", "GPT-4o mini", "openai_gpt-4o-mini"),
    ("openai/gpt-4.1-mini", "GPT-4.1 mini", "openai_gpt-4_1-mini"),
]
ALL_MODELS = OLD + MODELS
LABELS = dict((m, label) for m, label, _ in ALL_MODELS)
PRED = {-1: "no_violation", 0: "abstention", 1: "violation", 9: None}


def code(score):
    return int(category(score)) if finite(score) else 9


def ratio(x, y):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 100 * np.asarray(x, dtype=float) / np.asarray(y, dtype=float)


def ci(values):
    good = np.asarray(values)[np.isfinite(values)]
    return tuple(map(float, np.quantile(good, [.025, .975]))) if len(good) else (None, None)


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def load_rows(source, path, canonical, inventory, family, model):
    result, stats = {}, {}
    for row in source.jsonl(path):
        key = row["item_id"], str(row.get("article_full") or row["article"])
        arm = row.get("arm", "default")
        assert key in canonical and (key, arm) not in result
        assert row["violation_label"] == canonical[key]["violation_label"]
        score = row.get("avg_rating")
        pred = code(score)
        counts = stats.setdefault(arm, Counter())
        counts["records"] += 1
        counts["valid_means"] += pred != 9
        counts["missing_means"] += pred == 9
        counts["abstentions"] += pred == 0
        counts["unparsed_ratings"] += row["n_unparsed"]
        counts["complete_ten_ratings"] += row["n_unparsed"] == 0
        if "ratings" in row:
            values = [v for v in row["ratings"] if finite(v)]
            assert len(row["ratings"]) == 10
            assert len(values) == 10 - row["n_unparsed"]
            assert (not values and pred == 9) or np.isclose(np.mean(values), score, atol=1e-9)
        if family in ("full_record", "summary") and pred != 9:
            votes = Counter(PRED[code(v)] for v in values).most_common()
            plurality = "abstention" if len(votes) > 1 and votes[0][1] == votes[1][1] else votes[0][0]
            assert row["prediction"] == plurality
            counts["saved_plurality_differs_from_mean"] += row["prediction"] != PRED[pred]
        else:
            assert row["prediction"] == PRED[pred], (path, key)
        result[key, arm] = row
    for arm, counts in stats.items():
        assert counts["records"] == 1000
        inventory.append(dict(model=model, family=family, arm=arm, path=path,
            **{k:counts[k] for k in ("records", "valid_means", "missing_means", "abstentions",
               "unparsed_ratings", "complete_ten_ratings", "saved_plurality_differs_from_mean")}))
    return result


def time_cohorts(canonical, cutoffs):
    definitions = [("all", "2012-01-10", "2026-05-21"),
        ("before_both_old_cutoffs", "2012-01-10", "2023-10-01"),
        ("between_old_cutoffs", "2023-10-02", "2024-06-01"),
        ("after_both_old_cutoffs", "2024-06-02", "2026-05-21")]
    for row in cutoffs["models"]:
        if row["model"] not in {m for m, _, _ in OLD}:
            continue
        for field in ("knowledge_cutoff",):
            if not row.get(field):
                continue
            cut = row[field]
            stem = row["model"].split("/")[1] + "_" + field
            for side in ("pre", "post"):
                keys = sorted(k for k, r in canonical.items() if
                    (r["decision_date"] <= cut if side == "pre" else r["decision_date"] > cut))
                yield f"{stem}_{side}", keys, row["model"], cut
    for year in range(2012, 2027):
        definitions.append((str(year), f"{year}-01-01", f"{year}-12-31"))
    for start, end in [(2012, 2016), (2017, 2021), (2022, 2026)]:
        definitions.append((f"{start}-{end}", f"{start}-01-01", f"{end}-12-31"))
    for name, start, end in definitions:
        yield name, sorted(k for k, r in canonical.items() if start <= r["decision_date"] <= end), "", ""


def performance(keys, predictions, canonical, draws, seed):
    truth = np.array([ground_truth(canonical[k]["violation_label"]) for k in keys])
    columns = [np.ones(len(keys)), truth == 1, truth == -1]
    for scores in predictions.values():
        p = np.array([code(scores[k]) for k in keys])
        columns.extend([p == truth, (p == truth) & (truth == 1),
                        (p == truth) & (truth == -1), p == 0, p == 9])
    point, boot, judgments = bootstrap_totals(np.column_stack(columns), [k[0] for k in keys], draws, seed)
    out, uncertainty = {}, {}
    for index, name in enumerate(predictions):
        offset = 3 + 5 * index
        metrics, sampled = {}, {}
        for metric, ni, di in [("accuracy", offset, 0), ("violation_recall", offset+1, 1),
                ("no_violation_recall", offset+2, 2), ("abstention", offset+3, 0), ("missing", offset+4, 0)]:
            metrics[metric] = float(ratio(point[ni], point[di]))
            sampled[metric] = ratio(boot[:, ni], boot[:, di])
        metrics["balanced_accuracy"] = (metrics["violation_recall"] + metrics["no_violation_recall"]) / 2
        sampled["balanced_accuracy"] = (sampled["violation_recall"] + sampled["no_violation_recall"]) / 2
        r = dict(targets=len(keys), judgments=judgments, violation=int(point[1]), no_violation=int(point[2]),
                 correct=int(point[offset]), correct_violation=int(point[offset+1]),
                 correct_no_violation=int(point[offset+2]))
        for metric, value in metrics.items():
            lo, hi = ci(sampled[metric])
            r.update({metric+"_pct":value, metric+"_lower_95":lo, metric+"_upper_95":hi})
        out[name], uncertainty[name] = r, sampled
    return out, uncertainty


def paired_changes(keys, before, after, canonical, meta):
    valid = [k for k in keys if finite(before[k]) and finite(after[k])]
    b = np.array([code(before[k]) for k in valid]); a = np.array([code(after[k]) for k in valid])
    truth = np.array([ground_truth(canonical[k]["violation_label"]) for k in valid])
    r = dict(**meta, released_pairs=len(keys), valid_pairs=len(valid),
             judgments=len({k[0] for k in valid}), reference_missing=sum(not finite(before[k]) for k in keys),
             perturbed_missing=sum(not finite(after[k]) for k in keys))
    events = {"changed":a != b, "strict_reversal":(b != 0) & (a == -b),
              "correct_to_wrong":(b == truth) & (a == -truth),
              "wrong_to_correct":(b == -truth) & (a == truth),
              "correct_to_abstention":(b == truth) & (a == 0),
              "abstention_to_correct":(b == 0) & (a == truth)}
    for name, values in events.items():
        r[name+"_n"] = int(values.sum()); r[name+"_pct"] = float(ratio(values.sum(),len(valid)))
    r["accuracy_difference_pp"] = float(ratio((a == truth).sum() - (b == truth).sum(),len(valid)))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--revision", default=REVISION)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=731)
    args = ap.parse_args(); out = args.out or args.repo / "analysis/model_time_windows"
    out.mkdir(parents=True, exist_ok=True)
    source = GitSource(args.repo, args.revision)
    cutoffs_path = args.repo / "configs/model_knowledge_cutoffs.json"
    cutoffs = json.loads(cutoffs_path.read_text(encoding="utf-8"))
    cases = source.json("data/processed/echr_unified.json")
    summary_artifact = source.json("data/processed/summaries_dsv41flash.json")
    assert len(summary_artifact["summaries"]) == 947
    canonical = {(r["item_id"], str(r["article_full"])):r for r in cases}
    assert len(cases) == len(canonical) == 1000 and len({k[0] for k in canonical}) == 947
    keys = sorted(canonical); inventory, predictions, checks, perturbations = [], {}, [], []
    reference_config = source.json("data/experiments/unified_fullcase_latest/openai_gpt-5_6-sol/run_config.json")
    reference_identity = source.json("data/experiments/unified_fullcase_latest/openai_gpt-5_6-sol/input_identity.json")
    for model, label, directory in ALL_MODELS:
        old = model in {m for m, _, _ in OLD}
        family = "unified_fullcase_oldmodels" if old else "unified_fullcase_latest"
        prefix = f"data/experiments/{family}/{directory}"
        cfg = source.json(prefix+"/run_config.json"); identity = source.json(prefix+"/input_identity.json")
        assert identity == reference_identity
        assert {k:v for k,v in cfg.items() if k not in ("model", "prompt_version")} == {
            k:v for k,v in reference_config.items() if k not in ("model", "prompt_version")}
        checks.append(dict(model=model, input_identity_equal=True, run_settings_equal_except_model_and_prompt_tag=True,
                           requested_model=cfg["model"], prompt_version=cfg["prompt_version"]))
        for arm, filename in [("full_record", "baseline"), ("summary", "rq1")]:
            rows = load_rows(source, prefix+f"/{filename}.jsonl", canonical, inventory, arm, model)
            predictions[model, arm] = {k:r["avg_rating"] for (k, _), r in rows.items()}
        for family, filename in [("paraphrase", "paraphrase_results.jsonl"), ("stateswap", "stateswap_summary_results.jsonl")]:
            dirname = (family+"_oldmodels" if old else "stateswap_summary" if family == "stateswap" else family)
            path = f"data/experiments/{dirname}/{model.replace('/', '_')}"
            rows = load_rows(source, path+"/"+filename, canonical, inventory, family, model)
            if old:
                cfg = source.json(path+"/run_config.json")
                if family == "stateswap":
                    assert cfg["cases_sha256"] == source.inputs["data/processed/echr_unified.json"]["sha256_git_bytes"]
                    assert cfg["summaries_sha256"] == source.inputs["data/processed/summaries_dsv41flash.json"]["sha256_git_bytes"]
                checks.append(dict(model=model, family=family, run_config=cfg))
            if family == "paraphrase":
                original = {k:r["avg_rating"] for (k,a),r in rows.items() if a == "original"}
                for arm in ("light", "medium", "heavy"):
                    perturbed = {k:r["avg_rating"] for (k,a),r in rows.items() if a == arm}
                    for cohort, kk in [("all", keys), ("after_both_old_cutoffs", [k for k in keys if canonical[k]["decision_date"] > "2024-06-01"])]:
                        perturbations.append(paired_changes(kk, original, perturbed, canonical,
                            dict(model=model, family=family, arm=arm, cohort=cohort)))
        for cohort, kk in [("all", keys), ("after_both_old_cutoffs", [k for k in keys if canonical[k]["decision_date"] > "2024-06-01"])]:
            perturbations.append(paired_changes(kk, predictions[model,"full_record"], predictions[model,"summary"],
                canonical, dict(model=model, family="summary", arm="summary", cohort=cohort)))

    cohorts, scores, differences = [], [], []
    for name, selected, owner, cutoff in time_cohorts(canonical, cutoffs):
        assert selected
        cohorts.append(dict(cohort=name, cutoff_model=owner, cutoff=cutoff, targets=len(selected),
            judgments=len({k[0] for k in selected}), violation=sum(canonical[k]["violation_label"] == "violation" for k in selected),
            no_violation=sum(canonical[k]["violation_label"] == "no_violation" for k in selected),
            first_case=min(canonical[k]["decision_date"] for k in selected),
            last_case=max(canonical[k]["decision_date"] for k in selected), target_keys_sha256=digest(selected)))
        rates, boot = performance(selected, predictions, canonical, args.draws, args.seed)
        for (model, arm), row in rates.items():
            scores.append(dict(cohort=name, model=model, label=LABELS[model], input=arm, **row))
        if name.isdigit():
            continue
        for old, _, _ in OLD:
            for model, _, _ in MODELS + OLD[1:]:
                if old == model or (old == OLD[1][0] and model in {m for m,_,_ in OLD}):
                    continue
                for arm in ("full_record", "summary"):
                    for metric in ("accuracy", "balanced_accuracy"):
                        left, right = (old, arm), (model, arm)
                        lo, hi = ci(boot[right][metric] - boot[left][metric])
                        differences.append(dict(cohort=name, reference_model=old, comparison_model=model,
                            input=arm, targets=len(selected), metric=metric,
                            difference_pp=rates[right][metric+"_pct"]-rates[left][metric+"_pct"],
                            lower_95=lo, upper_95=hi))

    nationality, nationality_coverage, nationality_contrasts = [], [], []
    for model, _, _ in OLD:
        path = f"data/experiments/syco_nationality/{model.replace('/', '_')}/syco_nationality_results.jsonl"
        rows = list(source.jsonl(path)); assert len(rows) == 1000
        assert len({r['key'] for r in rows}) == 1000
        eligible = [r for r in rows if r["eligible"]]
        arms = ("neutral", "matched", "mismatched")
        matched = [r for r in eligible if all(finite(r["arms"][a]["post_score"]) for a in arms)]
        for arm in arms:
            valid = [r for r in eligible if finite(r["arms"][arm]["post_score"])]
            for r in valid:
                assert r["arms"][arm]["flipped"] == (code(r["arms"][arm]["post_score"]) == -code(r["initial_score"]))
            nationality_coverage.append(dict(model=model, arm=arm, records=len(rows), eligible=len(eligible),
                valid_post_scores=len(valid), missing_post_scores=len(eligible)-len(valid), common_three_arms=len(matched)))
        nk = [(r["item_id"],str(r["article"])) for r in matched]
        nb = {k:r["initial_score"] for k,r in zip(nk,matched)}
        ncols = [np.ones(len(matched))]
        for arm in arms:
            na = {k:r["arms"][arm]["post_score"] for k,r in zip(nk,matched)}
            nationality.append(paired_changes(nk,nb,na,canonical,
                dict(model=model, family="nationality_one_turn_lawyer", arm=arm, cohort="complete_three_arms")))
            ncols.append(np.array([code(na[k]) == -code(nb[k]) for k in nk]))
        point, boot, _ = bootstrap_totals(np.column_stack(ncols),[k[0] for k in nk],args.draws,args.seed)
        for i, arm in enumerate(arms[1:],start=2):
            lo,hi = ci(ratio(boot[:,i]-boot[:,1],boot[:,0]))
            nationality_contrasts.append(dict(model=model, reference_arm="neutral", comparison_arm=arm,
                targets=len(nk), reversal_difference_pp=float(ratio(point[i]-point[1],point[0])), lower_95=lo,upper_95=hi))

    tables = dict(cohorts=cohorts, performance=scores, paired_model_differences=differences,
        perturbation_changes=perturbations, result_inventory=inventory, nationality=nationality,
        nationality_coverage=nationality_coverage, nationality_contrasts=nationality_contrasts)
    for name, rows in tables.items():
        write_csv(out / (name+".csv"), rows)
    manifest = dict(source_revision=source.revision, release="v1.0", inputs=source.inputs,
        temporal_scope="Cutoff splits are defined only by GPT-4o mini and GPT-4.1 mini. The six primary models supply same-case reference results; they have no separate own-cutoff partitions in this analysis.",
        analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        cutoffs_file="configs/model_knowledge_cutoffs.json", cutoffs_sha256=hashlib.sha256(cutoffs_path.read_bytes()).hexdigest(),
        bootstrap=dict(draws=args.draws,seed=args.seed,unit="judgment",interval="percentile_95"),
        scoring="Threshold mean of valid scores: <40 no_violation, >60 violation, otherwise abstention. Missing means are failures and stay in accuracy denominators.",
        run_identity_checks=checks, outputs={name+".csv":dict(rows=len(rows),sha256=hashlib.sha256((out/(name+".csv")).read_bytes()).hexdigest()) for name,rows in tables.items()})
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"revision":source.revision,"outputs":{k:len(v) for k,v in tables.items()},"inputs":len(source.inputs)}))


if __name__ == "__main__":
    main()
