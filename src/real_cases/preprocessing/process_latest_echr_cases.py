"""
Process latest_echr_cases.jsonl and create organized dataset in echr_new/unanimous directory.

This script:
1. Reads latest_echr_cases.jsonl
2. Creates CSV and JSONL in echr_new/unanimous/ (all cases treated as unanimous by default)
3. Adds one-hot encoding for violation types
4. Uses 'facts' field as full_case_text
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any


def load_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file and return list of dictionaries."""
    cases = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            cases.append(json.loads(line))
    return cases


def prepare_csv_data(cases: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convert cases to DataFrame with important fields for CSV."""
    # Determine all violation types from the dataset
    all_violations = set()
    for case in cases:
        all_violations.update(case.get('violations', []))

    # Sort for consistent ordering
    VIOLATION_TYPES = sorted(list(all_violations))

    print(f"Found violation types: {VIOLATION_TYPES}")

    csv_data = []

    for case in cases:
        violations = case.get('violations', [])
        articles = case.get('articles', [])

        row = {
            'item_id': case.get('item_id', ''),
            'case_name': case.get('case_name', ''),
            'judgement_date': case.get('judgement_date', ''),
            'importance': case.get('importance', ''),  # Case importance level (1-4)
            'split_vote': case.get('split_vote', False),  # Whether case has dissenting opinions
            'articles': ', '.join(articles),
            'violations': ', '.join(violations),
            'violation_label': case.get('violation_label', ''),
        }

        # Add one-hot encoding columns for each violation type
        for vtype in VIOLATION_TYPES:
            # Normalize the violation type (handle both "p1-1" and "P1-1")
            normalized_vtype = vtype.upper() if vtype.startswith('P') else vtype
            col_name = f'violated_{normalized_vtype}'
            row[col_name] = 1 if vtype in violations else 0

        # Add full case text (facts section)
        row['full_case_text'] = case.get('facts', '')

        csv_data.append(row)

    return pd.DataFrame(csv_data)


def save_jsonl(cases: List[Dict[str, Any]], file_path: Path):
    """Save cases to JSONL file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')


def main():
    # Paths
    root_dir = Path('/Users/mac/Desktop/llm-human-rights')
    input_file = root_dir / 'data' / 'real_cases' / 'latest_echr_cases.jsonl'
    output_dir = root_dir / 'data' / 'real_cases' / 'echr_new'

    # Create output directory (use unanimous for all cases)
    unanimous_dir = output_dir / 'unanimous'
    unanimous_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading dataset from {input_file}...")
    cases = load_jsonl(input_file)
    print(f"Loaded {len(cases)} cases")

    # Count violations
    violations = sum(1 for case in cases if case['violation_label'] == 'violation')
    no_violations = sum(1 for case in cases if case['violation_label'] == 'no_violation')

    print(f"\nViolations: {violations}")
    print(f"No violations: {no_violations}")

    # Count by article
    article_counts = {}
    for case in cases:
        if case['violation_label'] == 'violation':
            for article in case.get('violations', []):
                article_counts[article] = article_counts.get(article, 0) + 1

    print(f"\nViolation counts by article:")
    for article in sorted(article_counts.keys()):
        print(f"  Article {article}: {article_counts[article]}")

    # Save cases
    print(f"\nSaving cases to {unanimous_dir}...")
    save_jsonl(cases, unanimous_dir / 'cases.jsonl')
    df = prepare_csv_data(cases)
    df.to_csv(unanimous_dir / 'cases.csv', index=False, encoding='utf-8')
    print(f"Saved {len(cases)} cases (JSONL and CSV)")

    # Print summary statistics
    print("\n✓ Dataset processing complete!")
    print(f"\nOutput structure:")
    print(f"  {output_dir}/")
    print(f"    unanimous/")
    print(f"      cases.jsonl ({len(cases)} cases)")
    print(f"      cases.csv ({len(cases)} rows, {len(df.columns)} columns)")
    print(f"\nDataset statistics:")
    print(f"  Total cases: {len(cases)}")
    print(f"  Violations: {violations} ({violations/len(cases)*100:.1f}%)")
    print(f"  No violations: {no_violations} ({no_violations/len(cases)*100:.1f}%)")
    print(f"  Average facts length: {df['full_case_text'].str.split().str.len().mean():.0f} words")


if __name__ == '__main__':
    main()
