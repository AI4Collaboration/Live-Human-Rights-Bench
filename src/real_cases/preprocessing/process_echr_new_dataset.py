"""
Process dataset_v3.jsonl and split into unanimous/non-unanimous cases with violation labels.

This script:
1. Reads dataset_v3.jsonl
2. Splits cases by unanimous/non-unanimous
3. Adds violation labels (violation/no_violation)
4. Saves to separate folders with JSONL and CSV formats
5. Merges all text sections into a single 'full_case_text' field for CSV
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


def add_violation_label(case: Dict[str, Any]) -> Dict[str, Any]:
    """Add violation_label field based on violations list."""
    violations = case.get('violations', [])
    case['violation_label'] = 'violation' if violations else 'no_violation'
    return case


def merge_case_text(case: Dict[str, Any]) -> str:
    """Merge all text sections into a single full case text."""
    sections = case.get('sections', {})

    text_parts = []

    # Merge all sections in order
    section_order = ['introduction', 'facts', 'legal_framework', 'parties_submissions', 'courts_assessment']

    for section_name in section_order:
        if section_name in sections and sections[section_name]:
            # Join all paragraphs in this section
            section_text = ' '.join(sections[section_name])
            text_parts.append(section_text)

    return ' '.join(text_parts)


def prepare_csv_data(cases: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convert cases to DataFrame with important fields for CSV."""
    # Define all possible violation types for one-hot encoding
    VIOLATION_TYPES = ['2', '3', '5', '6', '8', '10', '13', 'p1-1']

    csv_data = []

    for case in cases:
        violations = case.get('violations', [])

        row = {
            'item_id': case.get('item_id', ''),
            'judgement_date': case.get('judgement_date', ''),
            'importance': case.get('importance', ''),
            'unanimous': case.get('unanimous', ''),
            'concurring': case.get('concurring', ''),
            'parties': ', '.join(case.get('parties', [])),
            'articles': ', '.join(case.get('articles', [])),
            'violations': ', '.join(violations),
            'violation_label': case.get('violation_label', ''),
            'paragraphs': ', '.join(case.get('paragraphs', [])),
        }

        # Add one-hot encoding columns for each violation type
        for vtype in VIOLATION_TYPES:
            row[f'violated_{vtype}'] = 1 if vtype in violations else 0

        # Add full case text at the end (so one-hot columns appear before the large text)
        row['full_case_text'] = merge_case_text(case)

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
    input_file = root_dir / 'dataset_v3.jsonl'
    output_dir = root_dir / 'data' / 'real_cases' / 'echr_new'

    # Create output directories
    unanimous_dir = output_dir / 'unanimous'
    non_unanimous_dir = output_dir / 'non_unanimous'
    unanimous_dir.mkdir(parents=True, exist_ok=True)
    non_unanimous_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading dataset from {input_file}...")
    cases = load_jsonl(input_file)
    print(f"Loaded {len(cases)} cases")

    # Add violation labels to all cases
    print("Adding violation labels...")
    cases = [add_violation_label(case) for case in cases]

    # Split by unanimous/non-unanimous
    print("Splitting by unanimous decision...")
    unanimous_cases = [case for case in cases if case.get('unanimous', False) == True]
    non_unanimous_cases = [case for case in cases if case.get('unanimous', False) == False]

    print(f"Unanimous cases: {len(unanimous_cases)}")
    print(f"Non-unanimous cases: {len(non_unanimous_cases)}")

    # Count violations in each category
    unanimous_violations = sum(1 for case in unanimous_cases if case['violation_label'] == 'violation')
    unanimous_no_violations = sum(1 for case in unanimous_cases if case['violation_label'] == 'no_violation')
    non_unanimous_violations = sum(1 for case in non_unanimous_cases if case['violation_label'] == 'violation')
    non_unanimous_no_violations = sum(1 for case in non_unanimous_cases if case['violation_label'] == 'no_violation')

    print(f"\nUnanimous: {unanimous_violations} violations, {unanimous_no_violations} no violations")
    print(f"Non-unanimous: {non_unanimous_violations} violations, {non_unanimous_no_violations} no violations")

    # Save unanimous cases
    print(f"\nSaving unanimous cases to {unanimous_dir}...")
    save_jsonl(unanimous_cases, unanimous_dir / 'cases.jsonl')
    unanimous_df = prepare_csv_data(unanimous_cases)
    unanimous_df.to_csv(unanimous_dir / 'cases.csv', index=False, encoding='utf-8')
    print(f"Saved {len(unanimous_cases)} unanimous cases (JSONL and CSV)")

    # Save non-unanimous cases
    print(f"\nSaving non-unanimous cases to {non_unanimous_dir}...")
    save_jsonl(non_unanimous_cases, non_unanimous_dir / 'cases.jsonl')
    non_unanimous_df = prepare_csv_data(non_unanimous_cases)
    non_unanimous_df.to_csv(non_unanimous_dir / 'cases.csv', index=False, encoding='utf-8')
    print(f"Saved {len(non_unanimous_cases)} non-unanimous cases (JSONL and CSV)")

    print("\n✓ Dataset processing complete!")
    print(f"\nOutput structure:")
    print(f"  {output_dir}/")
    print(f"    unanimous/")
    print(f"      cases.jsonl ({len(unanimous_cases)} cases)")
    print(f"      cases.csv ({len(unanimous_cases)} rows)")
    print(f"    non_unanimous/")
    print(f"      cases.jsonl ({len(non_unanimous_cases)} cases)")
    print(f"      cases.csv ({len(non_unanimous_cases)} rows)")


if __name__ == '__main__':
    main()
