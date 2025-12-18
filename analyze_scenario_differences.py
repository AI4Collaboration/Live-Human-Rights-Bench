#!/usr/bin/env python3
"""
Statistical Analysis Script
Compares all scenarios in a model's results folder against generic_generic baseline.
Uses paired t-tests to detect significant differences in ratings.
"""

import argparse
import pandas as pd
from pathlib import Path
from scipy import stats
import numpy as np


def load_scenario_results(results_dir: Path, scenario_name: str) -> pd.DataFrame:
    """Load results CSV for a scenario."""
    csv_file = results_dir / f"{scenario_name}_results.csv"
    if not csv_file.exists():
        return None
    return pd.read_csv(csv_file)


def paired_t_test(baseline_ratings, comparison_ratings, scenario_name):
    """
    Perform paired t-test between baseline and comparison ratings.

    Returns dict with test results.
    """
    # Ensure same length (should be same 100 cases)
    if len(baseline_ratings) != len(comparison_ratings):
        return {
            'scenario': scenario_name,
            'error': f"Length mismatch: {len(baseline_ratings)} vs {len(comparison_ratings)}",
        }

    # Paired t-test
    t_stat, p_value = stats.ttest_rel(baseline_ratings, comparison_ratings)

    # Effect size (Cohen's d for paired samples)
    differences = comparison_ratings - baseline_ratings
    cohens_d = differences.mean() / differences.std()

    # Mean difference
    mean_diff = differences.mean()

    return {
        'scenario': scenario_name,
        't_statistic': t_stat,
        'p_value': p_value,
        'mean_difference': mean_diff,
        'cohens_d': cohens_d,
        'baseline_mean': baseline_ratings.mean(),
        'comparison_mean': comparison_ratings.mean(),
        'significant': p_value < 0.05,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Compare all scenarios against generic_generic baseline using paired t-tests'
    )
    parser.add_argument(
        'results_dir',
        type=str,
        help='Directory containing scenario results (e.g., data/experiments/llama-3.2-3b-instruct)'
    )
    parser.add_argument(
        '--alpha',
        type=float,
        default=0.05,
        help='Significance level (default: 0.05)'
    )
    parser.add_argument(
        '--baseline',
        type=str,
        default='generic_generic',
        help='Baseline scenario name (default: generic_generic)'
    )

    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}")
        return

    # Load baseline
    print(f"Loading baseline: {args.baseline}")
    baseline_df = load_scenario_results(results_dir, args.baseline)
    if baseline_df is None:
        print(f"Error: Baseline scenario '{args.baseline}' not found in {results_dir}")
        return

    baseline_ratings = baseline_df['rating'].values
    print(f"  ✓ Loaded {len(baseline_ratings)} cases\n")

    # Find all other scenarios
    scenario_files = sorted(results_dir.glob("*_results.csv"))
    scenarios = [f.stem.replace("_results", "") for f in scenario_files]
    scenarios = [s for s in scenarios if s != args.baseline]

    if not scenarios:
        print("No other scenarios found to compare.")
        return

    print(f"Found {len(scenarios)} scenarios to compare:\n")

    # Run t-tests
    results = []
    for scenario in scenarios:
        df = load_scenario_results(results_dir, scenario)
        if df is None:
            continue

        comparison_ratings = df['rating'].values
        result = paired_t_test(baseline_ratings, comparison_ratings, scenario)
        results.append(result)

    # Create results dataframe
    results_df = pd.DataFrame(results)

    # Sort by p-value
    results_df = results_df.sort_values('p_value')

    # Print results
    print("="*100)
    print(f"STATISTICAL COMPARISON vs {args.baseline} (α = {args.alpha})")
    print("="*100)
    print()

    # Significant results
    significant = results_df[results_df['significant']]
    if len(significant) > 0:
        print(f"🔴 SIGNIFICANT DIFFERENCES ({len(significant)} scenarios):")
        print("-"*100)
        for _, row in significant.iterrows():
            direction = "higher" if row['mean_difference'] > 0 else "lower"
            print(f"\n{row['scenario']:<30}")
            print(f"  Mean difference: {row['mean_difference']:+.4f} ({direction} ratings)")
            print(f"  Baseline mean:   {row['baseline_mean']:.4f}")
            print(f"  Scenario mean:   {row['comparison_mean']:.4f}")
            print(f"  p-value:         {row['p_value']:.6f} {'***' if row['p_value'] < 0.001 else '**' if row['p_value'] < 0.01 else '*'}")
            print(f"  Cohen's d:       {row['cohens_d']:+.4f} ({'large' if abs(row['cohens_d']) > 0.8 else 'medium' if abs(row['cohens_d']) > 0.5 else 'small'} effect)")
        print()
    else:
        print("✓ No significant differences found")
        print()

    # Non-significant results
    non_significant = results_df[~results_df['significant']]
    if len(non_significant) > 0:
        print(f"⚪ NON-SIGNIFICANT ({len(non_significant)} scenarios):")
        print("-"*100)
        for _, row in non_significant.iterrows():
            print(f"{row['scenario']:<30} p={row['p_value']:.4f}  diff={row['mean_difference']:+.4f}  d={row['cohens_d']:+.4f}")
        print()

    print("="*100)
    print(f"\nSummary: {len(significant)}/{len(results)} scenarios significantly different from {args.baseline}")
    print()

    # Save detailed results
    output_file = results_dir / f"statistical_analysis_{args.baseline}.csv"
    results_df.to_csv(output_file, index=False)
    print(f"Detailed results saved to: {output_file}")


if __name__ == "__main__":
    main()
