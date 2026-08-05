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


def paired_diff_ci(b, c, n, z=1.96):
    """95% CI on (b - c)/n, the paired difference in violation rate.

    Wald interval for correlated proportions. With discordant counts this small
    it is the honest way to show how much of an effect the data still allows.
    """
    if n == 0:
        return float("nan"), float("nan")
    d = (b - c) / n
    var = ((b + c) - (b - c) ** 2 / n) / (n ** 2)
    se = math.sqrt(max(var, 0.0))
    return d - z * se, d + z * se


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
    files = sorted(glob.glob(str(RESULTS_DIR / "*_stateswap_samples*.csv")))
    if not files:
        print(f"No state-swap CSVs in {RESULTS_DIR}. Run stateswap_evaluation.py first.")
        sys.exit(1)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for f in files:
        name = os.path.basename(f).split("_stateswap")[0]
        df = pd.read_csv(f)
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
    out.to_csv(ANALYSIS_DIR / "stateswap_contrasts.csv", index=False)

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
    print(f"\nSaved {ANALYSIS_DIR / 'stateswap_contrasts.csv'}")


if __name__ == "__main__":
    main()
