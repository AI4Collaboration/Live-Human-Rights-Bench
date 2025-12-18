"""
Sample N cases per article and filter original directory.

This creates a smaller working set by sampling random cases per article.
The full dataset is preserved in the 'full' directory.
"""

import pandas as pd
import re
from pathlib import Path
import shutil

METADATA_FILE = "data/real_cases/echr/metadata.csv"
ORIGINAL_DIR = Path("data/real_cases/echr/original")
FULL_DIR = Path("data/real_cases/echr/full")


def extract_main_article(conclusion):
    """Extract main article numbers from conclusion field."""
    if not conclusion or conclusion == "Inadmissible":
        return []

    articles = []
    # Match patterns like "Art. 3", "Art. 6-1", "P1-1"
    patterns = [
        r'Art\.\s*(\d+)',  # Art. 3
        r'Art\.\s*(P\d+-\d+)',  # Art. P1-1
    ]

    for pattern in patterns:
        matches = re.findall(pattern, conclusion)
        for match in matches:
            if 'P' in match:
                articles.append(match)
            elif '-' in match:
                articles.append(match.split('-')[0])
            else:
                articles.append(match)

    return list(set(articles))


def sample_by_article(n_per_article=10):
    """Sample N cases per article and update original directory."""

    print("=" * 80)
    print(f"SAMPLING {n_per_article} CASES PER ARTICLE")
    print("=" * 80)

    # Load metadata
    df = pd.read_csv(METADATA_FILE)
    print(f"\nTotal cases in metadata: {len(df)}")

    # Extract articles for each case
    df['articles'] = df['conclusion'].apply(extract_main_article)

    # Get all unique articles
    all_articles = set()
    for articles_list in df['articles']:
        all_articles.update(articles_list)

    all_articles = sorted(all_articles, key=lambda x: (not x.startswith('P'), x))
    print(f"Articles found: {all_articles}")

    # Sample cases per article
    sampled_case_ids = set()

    print("\n" + "=" * 80)
    print("SAMPLING BY ARTICLE")
    print("=" * 80)

    for article in all_articles:
        # Get all cases mentioning this article
        article_cases = df[df['articles'].apply(lambda x: article in x)]

        if len(article_cases) == 0:
            print(f"Article {article:<6} - No cases found")
            continue

        # Split by judgment
        violations = article_cases[article_cases['judgment'] == 'violation']
        no_violations = article_cases[article_cases['judgment'] == 'no_violation']

        # Sample balanced (n/2 from each category)
        n_per_category = n_per_article // 2

        sampled_violations = violations.sample(n=min(n_per_category, len(violations)), random_state=42)
        sampled_no_violations = no_violations.sample(n=min(n_per_category, len(no_violations)), random_state=42)

        sampled = pd.concat([sampled_violations, sampled_no_violations])

        sampled_case_ids.update(sampled['case_id'].tolist())

        print(f"Article {article:<6} - Sampled {len(sampled_violations):>2}V + {len(sampled_no_violations):>2}NV = {len(sampled):>3} / {len(article_cases):<4} cases")

    # Get unique sampled cases
    sampled_case_ids = list(sampled_case_ids)
    print(f"\n{'Total unique cases sampled:':<30} {len(sampled_case_ids)}")

    # Clear original directory and copy only sampled cases
    print("\n" + "=" * 80)
    print("UPDATING ORIGINAL DIRECTORY")
    print("=" * 80)

    # Remove all files from original
    for file in ORIGINAL_DIR.glob("*.txt"):
        file.unlink()

    # Copy sampled cases from full to original
    copied = 0
    for case_id in sampled_case_ids:
        source = FULL_DIR / f"{case_id}.txt"
        dest = ORIGINAL_DIR / f"{case_id}.txt"

        if source.exists():
            shutil.copy(source, dest)
            copied += 1

    print(f"✅ Copied {copied} cases to original/")

    # Save sampled metadata
    sampled_df = df[df['case_id'].isin(sampled_case_ids)]
    sampled_metadata_file = METADATA_FILE.replace('metadata.csv', 'metadata_sampled.csv')
    sampled_df.to_csv(sampled_metadata_file, index=False)

    print(f"📊 Saved sampled metadata to: {sampled_metadata_file}")

    # Statistics
    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)
    violations = sampled_df[sampled_df['judgment'] == 'violation']
    no_violations = sampled_df[sampled_df['judgment'] == 'no_violation']

    print(f"Sampled cases:    {len(sampled_df)}")
    print(f"Violations:       {len(violations)} ({len(violations)/len(sampled_df):.1%})")
    print(f"No violations:    {len(no_violations)} ({len(no_violations)/len(sampled_df):.1%})")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sample cases by article")
    parser.add_argument(
        "--n",
        type=int,
        default=10,
        help="Number of cases to sample per article (default: 10)"
    )

    args = parser.parse_args()
    sample_by_article(n_per_article=args.n)
