"""
Step 1c — Analyze MFT evaluation results.

Consolidates per-evaluator MFT CSVs into pass-rate summaries by model, by
article, and (new, using the v1.1 stratification axes) by group
(regular vs ukr). Also flags cases that fail MFT for all / some models.

Input : data/experiments/mft/*_mft_samples*.csv
Output: data/experiments/mft/analysis/*.csv, mft_summary.json
"""

import argparse
import json
from pathlib import Path
import sys
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "data" / "experiments" / "mft"
ANALYSIS_DIR = REPO_ROOT / "data" / "experiments" / "mft" / "analysis"


def load_result_files(results_dir: Path):
    files = sorted(results_dir.glob("*_mft_samples*.csv"))
    if not files:
        print(f"ERROR: No MFT result CSVs found in {results_dir}")
        print("Run experiments/mft_evaluation.py first.")
        sys.exit(1)
    evaluator_dfs = {}
    for path in files:
        evaluator_name = path.name.split("_mft_samples")[0]
        df = pd.read_csv(path)
        evaluator_dfs[evaluator_name] = df
        print(f"Loaded {path.name}: {len(df)} cases")
    return evaluator_dfs


def per_model_summary(evaluator_dfs: dict) -> pd.DataFrame:
    """Per-model MFT summary.

    Reports both the raw pass rate (prevalence-weighted — misleading here because
    the set is 72-94% violation, so an always-'violation' model scores that high)
    and per-class accuracy + balanced accuracy (mean of the two class accuracies),
    which is prevalence-independent and the number to trust.
    """
    rows = []
    for name, df in evaluator_dfs.items():
        n_cases = len(df)
        acc = df["is_accurate"].astype(bool)
        abst = (df["num_abstentions"].sum() / (n_cases * df["num_samples"].iloc[0])
                if {"num_abstentions", "num_samples"} <= set(df.columns) else float("nan"))

        # Per-class accuracy (recall for each true label).
        by_class = df.assign(_acc=acc).groupby("violation_label")["_acc"]
        class_acc = by_class.mean()
        class_n = by_class.size()
        acc_v = class_acc.get("violation", float("nan"))
        acc_nv = class_acc.get("no_violation", float("nan"))
        present = [x for x in (acc_v, acc_nv) if pd.notna(x)]
        balanced = round(sum(present) / len(present), 4) if present else float("nan")

        rows.append({
            "model": name,
            "n_cases": n_cases,
            "n_violation": int(class_n.get("violation", 0)),
            "n_no_violation": int(class_n.get("no_violation", 0)),
            "n_passed": int(acc.sum()),
            "mft_pass_rate": round(acc.mean(), 4),        # raw, prevalence-weighted
            "acc_violation": round(acc_v, 4) if pd.notna(acc_v) else float("nan"),
            "acc_no_violation": round(acc_nv, 4) if pd.notna(acc_nv) else float("nan"),
            "balanced_acc": balanced,                     # prevalence-independent
            "abstention_rate": round(abst, 4),
        })
    return pd.DataFrame(rows).sort_values("model").reset_index(drop=True)


def per_article_summary(evaluator_dfs: dict) -> pd.DataFrame:
    rows = []
    for name, df in evaluator_dfs.items():
        for article, sub in df.groupby("article"):
            rows.append({
                "model": name, "article": article,
                "n_cases": len(sub),
                "mft_pass_rate": round(sub["is_accurate"].mean(), 4),
            })
    return pd.DataFrame(rows).sort_values(["model", "article"]).reset_index(drop=True)


def per_group_summary(evaluator_dfs: dict) -> pd.DataFrame:
    """Accuracy by model x group (regular vs ukr).

    Reports balanced_acc alongside raw pass rate: the groups have very different
    base rates (regular ~72% violation, ukr ~94%), so raw pass rate is NOT
    comparable across groups. Compare balanced_acc for the real signal.
    """
    rows = []
    for name, df in evaluator_dfs.items():
        if "group" not in df.columns:
            continue
        for group, sub in df.groupby("group"):
            acc = sub["is_accurate"].astype(bool)
            by_class = sub.assign(_a=acc).groupby("violation_label")["_a"].mean()
            av = by_class.get("violation", float("nan"))
            anv = by_class.get("no_violation", float("nan"))
            present = [x for x in (av, anv) if pd.notna(x)]
            bal = round(sum(present) / len(present), 4) if present else float("nan")
            rows.append({
                "model": name, "group": group, "n_cases": len(sub),
                "mft_pass_rate": round(acc.mean(), 4),
                "acc_violation": round(av, 4) if pd.notna(av) else float("nan"),
                "acc_no_violation": round(anv, 4) if pd.notna(anv) else float("nan"),
                "balanced_acc": bal,
            })
    return pd.DataFrame(rows).sort_values(["model", "group"]).reset_index(drop=True)


def failing_cases(evaluator_dfs: dict) -> pd.DataFrame:
    merged = None
    for name, df in evaluator_dfs.items():
        cols = ["item_id", "case_name", "article", "violation_label", "is_accurate"]
        keep = df[cols].copy()
        # Normalize merge-key dtypes: 'article' is str ('P1-1') in some CSVs but
        # int64 in all-numeric ones — mixed dtypes crash the merge.
        keep["article"] = keep["article"].astype(str)
        keep["item_id"] = keep["item_id"].astype(str)
        keep = keep.rename(columns={"is_accurate": f"pass_{name}"})
        # Merge on (item_id, article) — the UNIQUE per-row key. Merging on
        # case_name alone duplicated rows (2270>2000) when names repeated.
        merged = keep if merged is None else merged.merge(
            keep, on=["item_id", "case_name", "article", "violation_label"], how="outer")
    pass_cols = [c for c in merged.columns if c.startswith("pass_")]
    merged["n_models_passed"] = merged[pass_cols].sum(axis=1)
    merged["n_models_total"] = len(pass_cols)
    merged["failed_all_models"] = merged["n_models_passed"] == 0
    merged["failed_some_models"] = merged["n_models_passed"] < len(pass_cols)
    return merged.sort_values(["n_models_passed", "case_name", "article"]).reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description="Analyze MFT evaluation results")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--analysis-dir", type=Path, default=ANALYSIS_DIR)
    args = parser.parse_args()

    print("=" * 80)
    print("MFT ANALYSIS")
    print("=" * 80)
    print(f"Results dir : {args.results_dir}")
    print(f"Analysis dir: {args.analysis_dir}")

    evaluator_dfs = load_result_files(args.results_dir)
    args.analysis_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "-" * 80 + "\nMFT PASS RATE BY MODEL\n" + "-" * 80)
    model_summary = per_model_summary(evaluator_dfs)
    print(model_summary.to_string(index=False))
    print("  NOTE: trust `balanced_acc` (mean of per-class accuracy). `mft_pass_rate`"
          " is prevalence-weighted and inflated by the 72-94% violation base rate.")
    model_summary.to_csv(args.analysis_dir / "mft_pass_rate_by_model.csv", index=False)

    print("\n" + "-" * 80 + "\nMFT PASS RATE BY MODEL AND ARTICLE\n" + "-" * 80)
    article_summary = per_article_summary(evaluator_dfs)
    print(article_summary.to_string(index=False))
    article_summary.to_csv(args.analysis_dir / "mft_pass_rate_by_article.csv", index=False)

    group_summary = per_group_summary(evaluator_dfs)
    if not group_summary.empty:
        print("\n" + "-" * 80 + "\nMFT PASS RATE BY MODEL AND GROUP (regular vs ukr)\n" + "-" * 80)
        print(group_summary.to_string(index=False))
        group_summary.to_csv(args.analysis_dir / "mft_pass_rate_by_group.csv", index=False)

    print("\n" + "-" * 80 + "\nCASES FLAGGED FOR DOWNSTREAM CAUTION\n" + "-" * 80)
    case_table = failing_cases(evaluator_dfs)
    case_table.to_csv(args.analysis_dir / "mft_per_case_pass_fail.csv", index=False)
    n_failed_all = int(case_table["failed_all_models"].sum())
    n_failed_some = int(case_table["failed_some_models"].sum())
    n_total = len(case_table)
    print(f"  Cases failing MFT for ALL models : {n_failed_all}/{n_total}")
    print(f"  Cases failing MFT for SOME models: {n_failed_some}/{n_total}")

    summary_json = {
        "n_models": len(evaluator_dfs),
        "models": model_summary.to_dict(orient="records"),
        "n_cases_failed_all_models": n_failed_all,
        "n_cases_failed_some_models": n_failed_some,
        "n_cases_total": n_total,
    }
    with open(args.analysis_dir / "mft_summary.json", "w") as f:
        json.dump(summary_json, f, indent=2)

    print("\n" + "=" * 80)
    print("MFT analysis complete. Outputs in:", args.analysis_dir)
    print("=" * 80)


if __name__ == "__main__":
    main()
