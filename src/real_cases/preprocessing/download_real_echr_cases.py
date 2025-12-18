"""
Download ALL real ECHR cases from HuggingFace dataset.

This script downloads all 11,478 cases from glnmario/ECHR dataset and saves them
with proper judgment labels (violation/no_violation).
"""

import csv
from pathlib import Path
from datasets import load_dataset
import logging

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Output directory
OUTPUT_DIR = Path("data/real_cases/echr_downloaded")


def get_article_name(article_num):
    """Get article name from number."""
    names = {
        '3': 'Prohibition of torture',
        '4': 'Prohibition of slavery and forced labour',
        '5': 'Right to liberty and security',
        '6': 'Right to a fair trial',
        '7': 'No punishment without law',
        '8': 'Right to respect for private and family life',
        '9': 'Freedom of thought, conscience and religion',
        '10': 'Freedom of expression',
        '11': 'Freedom of assembly and association',
        '12': 'Right to marry',
        '13': 'Right to an effective remedy',
        '14': 'Prohibition of discrimination',
    }
    return names.get(str(article_num), f'Article {article_num}')


def main():
    logger.info("=" * 80)
    logger.info("DOWNLOADING ALL ECHR CASES")
    logger.info("=" * 80)

    # Load dataset
    logger.info("\n📥 Loading glnmario/ECHR dataset from HuggingFace...")
    ds = load_dataset('glnmario/ECHR')
    train = ds['train']
    logger.info(f"✅ Loaded {len(train)} cases")

    # Create output directories
    (OUTPUT_DIR / "original").mkdir(parents=True, exist_ok=True)

    # Process all cases
    logger.info("\n" + "=" * 80)
    logger.info("SAVING ALL CASES")
    logger.info("=" * 80)

    metadata = []

    for i, ex in enumerate(train):
        if (i + 1) % 1000 == 0:
            logger.info(f"Processing case {i+1}/{len(train)}...")

        # Create case ID
        case_id = f"echr_{ex['itemid'].replace('-', '_')}"

        # Determine judgment
        judgment = 'violation' if ex['binary_judgement'] == 1 else 'no_violation'

        # Save case text
        case_file = OUTPUT_DIR / "original" / f"{case_id}.txt"
        case_file.write_text(ex['text'], encoding='utf-8')

        # Add to metadata
        metadata.append({
            'case_id': case_id,
            'hudoc_id': ex['itemid'],
            'respondent': ex['respondent'],
            'date': ex['date'],
            'judgment': judgment,
            'binary_judgement': ex['binary_judgement'],
            'conclusion': ex['conclusion'],
            'branch': ex['branch'],
            'importance': ex['importance'],
            'text_length': len(ex['text']),
            'original_file': f"original/{case_id}.txt",
        })

    # Save metadata
    logger.info("\n" + "=" * 80)
    logger.info("SAVING METADATA")
    logger.info("=" * 80)

    metadata_file = OUTPUT_DIR / "metadata.csv"
    with open(metadata_file, 'w', newline='', encoding='utf-8') as f:
        if metadata:
            writer = csv.DictWriter(f, fieldnames=metadata[0].keys())
            writer.writeheader()
            writer.writerows(metadata)

    logger.info(f"\n✅ Saved {len(metadata)} cases")
    logger.info(f"📁 Cases: {OUTPUT_DIR / 'original'}")
    logger.info(f"📊 Metadata: {metadata_file}")

    # Statistics
    violations = sum(1 for m in metadata if m['judgment'] == 'violation')
    no_violations = sum(1 for m in metadata if m['judgment'] == 'no_violation')

    logger.info("\n" + "=" * 80)
    logger.info("STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Total cases: {len(metadata)}")
    logger.info(f"Violations: {violations} ({violations/len(metadata):.1%})")
    logger.info(f"No violations: {no_violations} ({no_violations/len(metadata):.1%})")


if __name__ == "__main__":
    main()
