#!/usr/bin/env python3
"""
Create agreement heatmap showing how many cases each pair of scenarios agrees on.
"""

import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import List, Dict


def load_results(results_file: str) -> pd.DataFrame:
    """Load results CSV file."""
    return pd.read_csv(results_file)


def calculate_agreement_matrix(scenarios: List[str], results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Calculate pairwise agreement matrix."""
    n = len(scenarios)
    agreement_matrix = np.zeros((n, n), dtype=int)

    for i, scenario1 in enumerate(scenarios):
        for j, scenario2 in enumerate(scenarios):
            if i == j:
                # Diagonal - all cases agree with themselves
                agreement_matrix[i][j] = len(results[scenario1])
            else:
                # Count cases where ratings match
                df1 = results[scenario1]
                df2 = results[scenario2]

                # Ensure same case order
                merged = pd.merge(df1[['case_name', 'rating']],
                                 df2[['case_name', 'rating']],
                                 on='case_name',
                                 suffixes=('_1', '_2'))

                agreement_count = sum(merged['rating_1'] == merged['rating_2'])
                agreement_matrix[i][j] = agreement_count

    # Create DataFrame with scenario names
    df_matrix = pd.DataFrame(agreement_matrix,
                            index=scenarios,
                            columns=scenarios)

    return df_matrix


def create_heatmap(agreement_matrix: pd.DataFrame, output_file: str = None):
    """Create and save agreement heatmap."""

    # Set up the plot
    plt.figure(figsize=(12, 10))

    # Create heatmap
    sns.heatmap(agreement_matrix,
                annot=True,  # Show numbers in cells
                fmt='d',     # Integer format
                cmap='YlGnBu',  # Color scheme
                cbar_kws={'label': 'Number of Cases with Same Rating'},
                square=True,  # Make cells square
                linewidths=0.5,
                linecolor='gray')

    plt.title('Pairwise Agreement: Cases with Same Ratings\n(Out of 100 Total Cases)',
              fontsize=14,
              fontweight='bold',
              pad=20)

    plt.xlabel('Scenario', fontsize=12, fontweight='bold')
    plt.ylabel('Scenario', fontsize=12, fontweight='bold')

    # Rotate labels for better readability
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Heatmap saved to: {output_file}")
    else:
        plt.show()

    plt.close()


def print_agreement_summary(agreement_matrix: pd.DataFrame):
    """Print summary statistics about agreement."""
    scenarios = agreement_matrix.index.tolist()
    n = len(scenarios)

    print("\n" + "="*80)
    print("AGREEMENT SUMMARY")
    print("="*80)

    # Get upper triangle (excluding diagonal)
    mask = np.triu(np.ones_like(agreement_matrix, dtype=bool), k=1)
    upper_triangle = agreement_matrix.where(mask)

    # Overall statistics
    agreements = upper_triangle.values[mask]

    print(f"\nTotal comparisons: {len(agreements)}")
    print(f"Mean agreement: {agreements.mean():.1f} cases ({agreements.mean()}%)")
    print(f"Median agreement: {np.median(agreements):.1f} cases ({np.median(agreements)}%)")
    print(f"Min agreement: {agreements.min():.0f} cases ({agreements.min()}%)")
    print(f"Max agreement: {agreements.max():.0f} cases ({agreements.max()}%)")
    print(f"Std deviation: {agreements.std():.2f} cases")

    # Find most and least agreeing pairs
    print("\n" + "-"*80)
    print("MOST AGREEING PAIRS")
    print("-"*80)

    # Flatten and sort
    pairs = []
    for i, scenario1 in enumerate(scenarios):
        for j, scenario2 in enumerate(scenarios):
            if i < j:  # Upper triangle only
                agreement = agreement_matrix.iloc[i, j]
                pairs.append((scenario1, scenario2, agreement))

    pairs.sort(key=lambda x: x[2], reverse=True)

    for scenario1, scenario2, agreement in pairs[:5]:
        print(f"{scenario1:30s} ↔ {scenario2:30s}  {agreement:3d}/100 ({agreement}%)")

    print("\n" + "-"*80)
    print("LEAST AGREEING PAIRS")
    print("-"*80)

    for scenario1, scenario2, agreement in pairs[-5:]:
        print(f"{scenario1:30s} ↔ {scenario2:30s}  {agreement:3d}/100 ({agreement}%)")

    print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(description='Create agreement heatmap for experiment results')
    parser.add_argument(
        '--results-dir',
        type=str,
        default='data/experiments',
        help='Directory containing result files'
    )
    parser.add_argument(
        '--scenarios',
        type=str,
        nargs='+',
        help='Specific scenarios to include (default: all available)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='results/agreement_heatmap.png',
        help='Output file for heatmap'
    )

    args = parser.parse_args()

    results_path = Path(args.results_dir)

    # Find all available scenarios
    if args.scenarios:
        scenarios = args.scenarios
    else:
        # Auto-detect from CSV files
        csv_files = list(results_path.glob('*_results.csv'))
        scenarios = [f.stem.replace('_results', '') for f in csv_files]
        scenarios.sort()

    if not scenarios:
        print("❌ No scenarios found!")
        return

    print(f"Found {len(scenarios)} scenarios:")
    for s in scenarios:
        print(f"  - {s}")

    # Load all results
    print("\nLoading results...")
    results = {}
    for scenario in scenarios:
        csv_file = results_path / f"{scenario}_results.csv"
        if not csv_file.exists():
            print(f"⚠️  Warning: {csv_file} not found, skipping {scenario}")
            continue
        results[scenario] = load_results(csv_file)

    scenarios = list(results.keys())  # Update to only loaded scenarios
    print(f"✓ Loaded {len(scenarios)} scenario results")

    # Calculate agreement matrix
    print("\nCalculating pairwise agreement...")
    agreement_matrix = calculate_agreement_matrix(scenarios, results)

    # Print summary
    print_agreement_summary(agreement_matrix)

    # Create heatmap
    print(f"\nCreating heatmap...")
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    create_heatmap(agreement_matrix, args.output)

    print("\n✓ Done!")


if __name__ == "__main__":
    main()
