"""
State-swap Δ analysis. Pairs the 4 arms by swap_group_id and measures how the
country label moves each model's judgment, holding facts byte-fixed. All
contrasts are against control_neutral (Iceland):

  probe_ukraine   - control_neutral  -> Ukraine country prior (headline; time-free)
  probe_russia    - control_neutral  -> generic adversarial-state prior
  control_original- control_neutral  -> real-state prior

Positive mean_rating_delta / net_into_violation = the probe country pushes the
model TOWARD "violation" relative to Iceland, on identical facts.

Reported per contrast:
  * exact McNemar (two-sided binomial on the discordant pairs, no scipy needed)
  * Benjamini-Hochberg q across every contrast in the run (10 models x 3 = 30
    tests, so an uncorrected 0.05 is not a decision rule)
  * 95% CI on the paired difference in violation rate, so a null reads as "the
    effect is at most this large" rather than "there is no effect"
  * abstention kept separate from no_violation in the flip counts

Run: python scripts/stateswap_analysis.py
"""
import argparse
import glob
import math
import os
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "data" / "experiments" / "stateswap"
ANALYSIS_DIR = RESULTS_DIR / "analysis"
CONTROL = "control_neutral"
PROBES = ["probe_ukraine", "probe_russia", "control_original"]
ALPHA = 0.05

# The eight codes that had a mapped heading before ARTICLE_TITLES was completed.
# Runs made before that fix prompted everything else with a heading that merely
# repeated the code ("Article 13 - Article 13"), i.e. those instances were scored
# on a different prompt from the rest of the set. --mapped-articles-only restricts
# the analysis to these codes, which tests whether the headline survives on the
# rows that were never affected, without paying for a re-run.
LEGACY_TITLED_ARTICLES = {"2", "3", "5", "6", "8", "10", "14", "P1-1"}


def mcnemar_exact(b, c):
    """Two-sided exact McNemar: binomial(b+c, 0.5) on the discordant pairs.

    b = pairs that moved into violation, c = pairs that moved out of it.
    Returns 1.0 when there is nothing discordant to test.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def _binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))


def _clopper_pearson(k, n, alpha=0.05, tol=1e-10):
    """Exact CI for a binomial proportion, by bisection (no scipy)."""
    if n == 0:
        return 0.0, 1.0
    lo = 0.0
    if k > 0:                       # solve P(X >= k | p) = alpha/2
        a, b_ = 0.0, 1.0
        while b_ - a > tol:
            mid = (a + b_) / 2
            if 1 - _binom_cdf(k - 1, n, mid) < alpha / 2:
                a = mid
            else:
                b_ = mid
        lo = (a + b_) / 2
    hi = 1.0
    if k < n:                       # solve P(X <= k | p) = alpha/2
        a, b_ = 0.0, 1.0
        while b_ - a > tol:
            mid = (a + b_) / 2
            if _binom_cdf(k, n, mid) > alpha / 2:
                a = mid
            else:
                b_ = mid
        hi = (a + b_) / 2
    return lo, hi


def paired_diff_ci(b, c, n):
    """95% CI on (b - c)/n, the paired difference in violation rate.

    Conditional on the discordant pairs, which is the same view the exact
    McNemar test takes: with m = b + c discordant pairs, the difference is
    (m/n)(2p - 1) for p = P(into violation | discordant), so an exact
    Clopper-Pearson interval on p carries straight over.

    A Wald interval was used here first and is wrong in exactly the case that
    matters most: with zero discordant pairs it collapses to [0, 0], which reads
    as "the effect is provably nil" when the data merely never saw a flip. With
    m = 0 the rule of three bounds the discordant rate by 3/n instead.
    """
    if n == 0:
        return float("nan"), float("nan")
    m = b + c
    if m == 0:
        return -3.0 / n, 3.0 / n
    p_lo, p_hi = _clopper_pearson(b, m)
    return (m / n) * (2 * p_lo - 1), (m / n) * (2 * p_hi - 1)


def benjamini_hochberg(pvals):
    """BH q-values, returned in the order of the input."""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [0.0] * m
    prev = 1.0
    for rank, idx in enumerate(reversed(order), start=1):
        i = m - rank + 1
        prev = min(prev, pvals[idx] * m / i)
        q[idx] = prev
    return q


def contrast(piv_r, piv_p, probe):
    if probe not in piv_r.columns or CONTROL not in piv_r.columns:
        return None
    r = piv_r.dropna(subset=[CONTROL, probe])
    p = piv_p.dropna(subset=[CONTROL, probe])
    # Rows whose calls all failed carry prediction "failed"; they are not data.
    p = p[(p[CONTROL] != "failed") & (p[probe] != "failed")]
    r = r.loc[r.index.intersection(p.index)]
    p = p.loc[r.index]
    n = len(r)
    if n == 0:
        return None
    delta = r[CONTROL] - r[probe]                      # >0 => probe leans more violation
    into = (p[CONTROL] != "violation") & (p[probe] == "violation")
    out_of = (p[CONTROL] == "violation") & (p[probe] != "violation")
    b, c = int(into.sum()), int(out_of.sum())
    lo, hi = paired_diff_ci(b, c, n)
    return {
        "probe": probe,
        "n": n,
        "flip_rate": round((p[CONTROL] != p[probe]).mean(), 4),
        "mean_rating_delta": round(float(delta.mean()), 4),   # + = toward violation
        "n_toward_violation": int((r[probe] < r[CONTROL]).sum()),
        "n_away": int((r[probe] > r[CONTROL]).sum()),
        "pred_into_violation": b,
        "pred_out_of_violation": c,
        # abstention is not no_violation: on the abstention-heavy models the two
        # routes into "violation" behave differently and must stay separable
        "into_violation_from_noviol": int(
            ((p[CONTROL] == "no_violation") & (p[probe] == "violation")).sum()),
        "into_violation_from_abstain": int(
            ((p[CONTROL] == "abstention") & (p[probe] == "violation")).sum()),
        "out_of_violation_to_noviol": int(
            ((p[CONTROL] == "violation") & (p[probe] == "no_violation")).sum()),
        "out_of_violation_to_abstain": int(
            ((p[CONTROL] == "violation") & (p[probe] == "abstention")).sum()),
        "net_into_violation": b - c,
        "net_rate": round((b - c) / n, 5),
        "ci95_low": round(lo, 5),
        "ci95_high": round(hi, 5),
        "mcnemar_p": mcnemar_exact(b, c),
    }


def main():
    ap = argparse.ArgumentParser(description="State-swap contrast analysis")
    ap.add_argument("--mapped-articles-only", action="store_true",
                    help="restrict to articles that had a mapped prompt heading "
                         "before ARTICLE_TITLES was completed (sensitivity check "
                         "for runs made before that fix)")
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = ap.parse_args()

    results_dir = args.results_dir
    analysis_dir = results_dir / "analysis"
    files = sorted(glob.glob(str(results_dir / "*_stateswap_samples*.csv")))
    if not files:
        print(f"No state-swap CSVs in {results_dir}. Run stateswap_evaluation.py first.")
        sys.exit(1)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    if args.mapped_articles_only:
        print(f"[--mapped-articles-only] restricted to {sorted(LEGACY_TITLED_ARTICLES)}\n")

    all_rows = []
    for f in files:
        name = os.path.basename(f).split("_stateswap")[0]
        df = pd.read_csv(f)
        if args.mapped_articles_only:
            before = df["swap_group_id"].nunique()
            df = df[df["article"].astype(str).isin(LEGACY_TITLED_ARTICLES)]
            after = df["swap_group_id"].nunique()
            print(f"[{name}] kept {after} of {before} groups "
                  f"({100 * (before - after) / max(1, before):.1f}% dropped as "
                  f"degraded-prompt rows)")
            if df.empty:
                print(f"[{name}] nothing left after the restriction; skipped")
                continue
        if "num_failed_calls" in df.columns and df["num_failed_calls"].sum():
            print(f"[{name}] {int(df['num_failed_calls'].sum())} failed calls in the "
                  f"source run; rows with no usable sample are dropped pairwise.")
        piv_r = df.pivot_table(index="swap_group_id", columns="arm",
                               values="avg_rating", aggfunc="first")
        piv_p = df.pivot_table(index="swap_group_id", columns="arm",
                               values="prediction", aggfunc="first")
        for probe in PROBES:
            c = contrast(piv_r, piv_p, probe)
            if c:
                c["model"] = name
                all_rows.append(c)

    if not all_rows:
        print("No usable contrasts."); sys.exit(1)

    qs = benjamini_hochberg([r["mcnemar_p"] for r in all_rows])
    for r, q in zip(all_rows, qs):
        r["bh_q"] = q
        r["significant_bh"] = bool(q < ALPHA)

    for name in sorted({r["model"] for r in all_rows}):
        print("=" * 112)
        print(f"MODEL: {name}   (pairs with both arms present and scored shown as n)")
        print("-" * 112)
        print(f"{'contrast':36} {'n':>4} {'flip':>6} {'d_rating':>9} "
              f"{'into':>5} {'out':>5} {'net':>5} {'net%':>7} "
              f"{'95% CI':>20} {'p':>7} {'BH q':>7}")
        for r in [x for x in all_rows if x["model"] == name]:
            print(f"{r['probe'] + ' - ' + CONTROL:36} {r['n']:>4} {r['flip_rate']:>6.3f} "
                  f"{r['mean_rating_delta']:>+9.3f} {r['pred_into_violation']:>5} "
                  f"{r['pred_out_of_violation']:>5} {r['net_into_violation']:>+5} "
                  f"{100 * r['net_rate']:>+6.2f}% "
                  f"[{100 * r['ci95_low']:>+6.2f}%,{100 * r['ci95_high']:>+6.2f}%] "
                  f"{r['mcnemar_p']:>7.3f} {r['bh_q']:>7.3f}"
                  + ("  *" if r["significant_bh"] else ""))
        print()

    out = pd.DataFrame(all_rows)[
        ["model", "probe", "n", "flip_rate", "mean_rating_delta",
         "n_toward_violation", "n_away", "pred_into_violation",
         "pred_out_of_violation", "into_violation_from_noviol",
         "into_violation_from_abstain", "out_of_violation_to_noviol",
         "out_of_violation_to_abstain", "net_into_violation", "net_rate",
         "ci95_low", "ci95_high", "mcnemar_p", "bh_q", "significant_bh"]
    ]
    out_name = ("stateswap_contrasts_mapped_articles.csv" if args.mapped_articles_only
                else "stateswap_contrasts.csv")
    out.to_csv(analysis_dir / out_name, index=False)

    n_sig = int(out["significant_bh"].sum())
    print("=" * 112)
    print("HEADLINE = 'probe_ukraine - control_neutral'. Positive mean_rating_delta / "
          "net_into_violation\nmeans relabeling identical facts as Ukraine pushes the "
          "model toward 'violation' (a country prior,\nwith the time confound removed). "
          "Compare against probe_russia to see if it is Ukraine-specific.")
    print(f"\n{len(out)} contrasts tested, {n_sig} significant after Benjamini-Hochberg "
          f"at alpha={ALPHA}.")
    print("A non-significant contrast is not evidence of no effect: read the 95% CI, "
          "which bounds how\nlarge a country prior the data still permits.")
    if args.mapped_articles_only:
        print("Restricted run: these rows were never exposed to the degenerate prompt "
              "heading, so a\nheadline that holds here does not depend on the article-title "
              "fix and needs no re-run.")
    print(f"\nSaved {analysis_dir / out_name}")


if __name__ == "__main__":
    main()
