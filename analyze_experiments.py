#!/usr/bin/env python3
"""
Generic Experiment Analysis Script
Analyzes and compares any experiment results.
"""

import argparse
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict


def load_results(results_file: str) -> pd.DataFrame:
    """Load results CSV file."""
    return pd.read_csv(results_file)


def load_metrics(metrics_file: str) -> dict:
    """Load metrics JSON file."""
    with open(metrics_file, 'r') as f:
        return json.load(f)


def print_summary_table(scenarios: List[str], metrics: Dict[str, dict]):
    """Print summary comparison table."""
    print("\n" + "="*100)
    print("EXPERIMENT SUMMARY")
    print("="*100)

    # Overall metrics table
    print("\n" + "-"*100)
    print(f"{'Scenario':<30} {'Distance Score':<18} {'Avg Rating':<15} {'Confident %':<15} {'Unsure'}")
    print("-"*100)

    for scenario in scenarios:
        m = metrics[scenario]
        dist_score = f"{m['avg_distance_score']:.4f}"
        avg_rating = f"{m['avg_rating_overall']:.2f}"
        confident = f"{m['confidence_rate']*100:.1f}%"
        unsure = str(m['unsure_predictions'])

        print(f"{scenario:<30} {dist_score:<18} {avg_rating:<15} {confident:<15} {unsure}")

    print("-"*100)

    # Calculate ranges
    dist_scores = [metrics[s]['avg_distance_score'] for s in scenarios]
    ratings = [metrics[s]['avg_rating_overall'] for s in scenarios]

    print(f"\nRange (max - min):")
    print(f"  Distance Score: {max(dist_scores) - min(dist_scores):.4f}")
    print(f"  Average Rating: {max(ratings) - min(ratings):.2f}")

    best_dist = scenarios[dist_scores.index(max(dist_scores))]
    worst_dist = scenarios[dist_scores.index(min(dist_scores))]

    print(f"\nBest performing (distance score): {best_dist} ({max(dist_scores):.4f})")
    print(f"Worst performing (distance score): {worst_dist} ({min(dist_scores):.4f})")


def print_detailed_metrics(scenarios: List[str], metrics: Dict[str, dict]):
    """Print detailed metrics for each scenario."""
    print("\n" + "="*100)
    print("DETAILED METRICS BY SCENARIO")
    print("="*100)

    for scenario in scenarios:
        m = metrics[scenario]

        print(f"\n{'-'*100}")
        print(f"Scenario: {scenario}")
        print(f"{'-'*100}")

        print(f"\nDistance Scores:")
        print(f"  Overall:        {m['avg_distance_score']:.4f}")
        print(f"  Violations:     {m['avg_distance_score_violations']:.4f}")
        print(f"  No Violations:  {m['avg_distance_score_no_violations']:.4f}")

        print(f"\nAverage Ratings (1=violation, 5=no violation):")
        print(f"  Overall:        {m['avg_rating_overall']:.2f}")
        print(f"  Violations:     {m['avg_rating_violations']:.2f} (ideal=1.0)")
        print(f"  No Violations:  {m['avg_rating_no_violations']:.2f} (ideal=5.0)")

        print(f"\nRating Distribution:")
        dist = m['rating_distribution']
        print(f"  1:  {int(dist['1']*100):2d} cases ({dist['1']*100:4.1f}%)")
        print(f"  2:  {int(dist['2']*100):2d} cases ({dist['2']*100:4.1f}%)")
        print(f"  3:  {int(dist['3']*100):2d} cases ({dist['3']*100:4.1f}%)")
        print(f"  4:  {int(dist['4']*100):2d} cases ({dist['4']*100:4.1f}%)")
        print(f"  5:  {int(dist['5']*100):2d} cases ({dist['5']*100:4.1f}%)")

        print(f"\nConfidence:")
        print(f"  Confident (1 or 5): {m['confident_predictions']} ({m['confidence_rate']*100:.1f}%)")
        print(f"  Moderate (2 or 4):  {m['moderate_predictions']}")
        print(f"  Unsure (3):         {m['unsure_predictions']}")


def compare_pairwise(baseline: str, comparisons: List[str], results: Dict[str, pd.DataFrame]):
    """Compare each scenario to baseline."""
    print("\n" + "="*100)
    print(f"PAIRWISE COMPARISON (Baseline: {baseline})")
    print("="*100)

    baseline_df = results[baseline]

    for scenario in comparisons:
        compare_df = results[scenario]

        print(f"\n{'-'*100}")
        print(f"{baseline} vs {scenario}")
        print(f"{'-'*100}")

        # Agreement metrics
        exact_match = sum(baseline_df['rating'] == compare_df['rating'])
        within_1 = sum(abs(baseline_df['rating'] - compare_df['rating']) <= 1)
        large_diff = sum(abs(baseline_df['rating'] - compare_df['rating']) >= 2)

        print(f"\nAgreement:")
        print(f"  Exact match:        {exact_match}/100 ({exact_match}%)")
        print(f"  Within 1 point:     {within_1}/100 ({within_1}%)")
        print(f"  ≥2 point difference: {large_diff} cases")

        # Bias direction
        scenario_lower = sum(compare_df['rating'] < baseline_df['rating'])
        baseline_lower = sum(baseline_df['rating'] < compare_df['rating'])
        equal = sum(compare_df['rating'] == baseline_df['rating'])

        print(f"\nBias Direction (lower rating = more pro-violation):")
        print(f"  {scenario} rated lower:   {scenario_lower} cases (more strict)")
        print(f"  {baseline} rated lower:   {baseline_lower} cases (more strict)")
        print(f"  Equal ratings:            {equal} cases")

        net_bias = scenario_lower - baseline_lower
        if net_bias > 0:
            print(f"  → Net: {scenario} is MORE strict ({net_bias:+d} cases)")
        elif net_bias < 0:
            print(f"  → Net: {scenario} is MORE lenient ({net_bias:+d} cases)")
        else:
            print(f"  → No net bias")

        # Show cases with large differences if any
        if large_diff > 0 and large_diff <= 5:
            print(f"\nCases with ≥2 point difference:")
            rating_diff = abs(baseline_df['rating'] - compare_df['rating'])
            large_diff_mask = rating_diff >= 2

            diff_df = pd.DataFrame({
                'case_name': baseline_df['case_name'][large_diff_mask],
                'actual': baseline_df['actual'][large_diff_mask],
                f'{baseline}_rating': baseline_df['rating'][large_diff_mask],
                f'{scenario}_rating': compare_df['rating'][large_diff_mask],
                'diff': rating_diff[large_diff_mask]
            })

            for _, row in diff_df.iterrows():
                print(f"\n  {row['case_name']}")
                print(f"    Actual: {row['actual']}")
                print(f"    {baseline} rating: {row[f'{baseline}_rating']}")
                print(f"    {scenario} rating: {row[f'{scenario}_rating']}")
                print(f"    Difference: {row['diff']:.0f} points")


def main():
    parser = argparse.ArgumentParser(description='Analyze experiment results')
    parser.add_argument(
        '--scenarios',
        type=str,
        nargs='+',
        required=True,
        help='Scenario names to analyze (must match result file names without _results.csv)'
    )
    parser.add_argument(
        '--baseline',
        type=str,
        help='Baseline scenario for pairwise comparison (default: first scenario)'
    )
    parser.add_argument(
        '--results-dir',
        type=str,
        default='data/experiments',
        help='Directory containing result files'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Optional output markdown file for report'
    )

    args = parser.parse_args()

    results_path = Path(args.results_dir)

    # Load all results and metrics
    print(f"\nLoading results from {args.results_dir}...")
    results = {}
    metrics = {}

    for scenario in args.scenarios:
        csv_file = results_path / f"{scenario}_results.csv"
        metrics_file = results_path / f"{scenario}_metrics.json"

        if not csv_file.exists():
            raise FileNotFoundError(f"Results file not found: {csv_file}")
        if not metrics_file.exists():
            raise FileNotFoundError(f"Metrics file not found: {metrics_file}")

        results[scenario] = load_results(csv_file)
        metrics[scenario] = load_metrics(metrics_file)

    print(f"✓ Loaded {len(args.scenarios)} scenario(s)")

    # Print analyses
    print_summary_table(args.scenarios, metrics)
    print_detailed_metrics(args.scenarios, metrics)

    # Pairwise comparison if baseline specified or multiple scenarios
    if len(args.scenarios) > 1:
        baseline = args.baseline if args.baseline else args.scenarios[0]
        if baseline not in args.scenarios:
            raise ValueError(f"Baseline '{baseline}' not in scenarios list")

        comparisons = [s for s in args.scenarios if s != baseline]
        compare_pairwise(baseline, comparisons, results)

    print("\n" + "="*100)
    print("ANALYSIS COMPLETE")
    print("="*100 + "\n")


if __name__ == "__main__":
    main()
