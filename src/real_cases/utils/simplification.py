"""Pipeline for simplifying ECHR cases into 1-paragraph format."""

import asyncio
import argparse
import logging
import pandas as pd
from pathlib import Path
from inspect_ai.model import GenerateConfig

from src.client import LLMClient
from src.real_cases.config import (
    SIMPLIFICATION_CONFIG,
    DEFAULT_SIMPLIFICATION_MODEL,
    METADATA_FILE,
    ORIGINAL_DIR,
    SIMPLIFIED_DIR,
)
from src.real_cases.utils.simplification_prompts import (
    SIMPLIFICATION_SYSTEM_PROMPT,
    SIMPLIFICATION_PROMPT_TEMPLATE,
)

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def simplify_case(
    case_data: dict,
    model_id: str = DEFAULT_SIMPLIFICATION_MODEL,
    temperature: float = None,
) -> str:
    """Simplify a single ECHR case to 1-paragraph format.

    Args:
        case_data: Dictionary containing case information
        model_id: LLM model to use for simplification
        temperature: Generation temperature (default from config)

    Returns:
        Simplified case text (150-200 words)
    """
    if temperature is None:
        temperature = SIMPLIFICATION_CONFIG["temperature"]

    # Read original case file
    original_file = Path(case_data["original_file"])
    if not original_file.exists():
        original_file = Path(ORIGINAL_DIR) / original_file.name

    case_text = original_file.read_text(encoding="utf-8")

    # Create client
    client = LLMClient(
        model_id,
        config=GenerateConfig(
            temperature=temperature,
            max_tokens=400,  # ~200 words
        ),
    )

    # Format prompt - handle both manual and downloaded datasets
    prompt = SIMPLIFICATION_PROMPT_TEMPLATE.format(case_text=case_text)

    # Generate simplified version
    simplified = await client.generate(
        prompt=prompt, system_message=SIMPLIFICATION_SYSTEM_PROMPT
    )

    return simplified.strip()


async def simplify_all_cases(
    metadata_file: str = METADATA_FILE,
    output_dir: str = SIMPLIFIED_DIR,
    model_id: str = DEFAULT_SIMPLIFICATION_MODEL,
    overwrite: bool = False,
    test_mode: bool = False,
    sample_size: int = None,
    balance_judgments: bool = False,
):
    """Simplify all cases in the dataset.

    Args:
        metadata_file: Path to metadata CSV
        output_dir: Directory to save simplified cases
        model_id: LLM model to use
        overwrite: Whether to overwrite existing simplified cases
        test_mode: If True, only simplify first case
        sample_size: If provided, randomly sample this many cases (per judgment if balanced)
        balance_judgments: If True with sample_size, sample equally from violations and no_violations
    """
    # Load metadata
    df = pd.read_csv(metadata_file)

    if test_mode:
        logger.info("🧪 Running in TEST MODE - only processing first case")
        df = df.head(1)
    elif sample_size is not None:
        if balance_judgments and 'judgment' in df.columns:
            # Sample equally from violations and no_violations
            violations = df[df['judgment'] == 'violation']
            no_violations = df[df['judgment'] == 'no_violation']

            per_class = sample_size // 2

            sampled_violations = violations.sample(n=min(per_class, len(violations)), random_state=42)
            sampled_no_violations = no_violations.sample(n=min(per_class, len(no_violations)), random_state=42)

            df = pd.concat([sampled_violations, sampled_no_violations]).sample(frac=1, random_state=42)

            logger.info(f"📊 Balanced sampling: {len(sampled_violations)} violations + {len(sampled_no_violations)} no_violations")
        else:
            # Random sample
            df = df.sample(n=min(sample_size, len(df)), random_state=42)
            logger.info(f"📊 Random sampling: {len(df)} cases")

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    logger.info(f"📋 Simplifying {len(df)} cases using model: {model_id}")
    logger.info(f"📁 Output directory: {output_dir}")

    # Simplify each case
    simplified_texts = []
    for idx, row in df.iterrows():
        case_id = row["case_id"]
        output_file = Path(output_dir) / f"{case_id}.txt"

        # Skip if already exists and not overwriting
        if output_file.exists() and not overwrite:
            logger.info(
                f"⏭️  Skipping {case_id} (already exists, use --overwrite to regenerate)"
            )
            simplified = output_file.read_text(encoding="utf-8")
            simplified_texts.append(simplified)
            continue

        # Handle both dataset formats (manual has 'article', downloaded has 'hudoc_id')
        extra_info = f"Article {row['article']}" if 'article' in row else f"HUDOC {row.get('hudoc_id', 'N/A')}"
        logger.info(f"🔄 Simplifying case {idx+1}/{len(df)}: {case_id} ({extra_info})")

        try:
            simplified = await simplify_case(row.to_dict(), model_id=model_id)
            simplified_texts.append(simplified)

            # Save individual file
            output_file.write_text(simplified, encoding="utf-8")

            # Log word count
            word_count = len(simplified.split())
            logger.info(f"   ✅ Simplified ({word_count} words)")

        except Exception as e:
            logger.error(f"   ❌ Error simplifying {case_id}: {e}")
            simplified_texts.append("")

    # Add to dataframe
    df["simplified_text"] = simplified_texts
    df["simplified_file"] = [f"simplified/{row['case_id']}.txt" for _, row in df.iterrows()]

    # Save updated metadata
    output_metadata = Path(metadata_file).parent / "metadata_with_simplified.csv"
    df.to_csv(output_metadata, index=False)

    logger.info(f"\n✅ Simplification complete!")
    logger.info(f"📊 Updated metadata saved to: {output_metadata}")

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Simplify ECHR cases into 1-paragraph format"
    )
    parser.add_argument(
        "--metadata",
        default=METADATA_FILE,
        help="Path to metadata CSV file",
    )
    parser.add_argument(
        "--output_dir",
        default=SIMPLIFIED_DIR,
        help="Directory to save simplified cases",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_SIMPLIFICATION_MODEL,
        help="Model to use for simplification",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing simplified cases",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode - only process first case",
    )
    parser.add_argument(
        "--sample",
        type=int,
        help="Sample N cases randomly (if --balance, samples N/2 violations + N/2 no_violations)",
    )
    parser.add_argument(
        "--balance",
        action="store_true",
        help="Balance violations and no_violations when sampling (requires --sample)",
    )

    args = parser.parse_args()

    asyncio.run(
        simplify_all_cases(
            metadata_file=args.metadata,
            output_dir=args.output_dir,
            model_id=args.model,
            overwrite=args.overwrite,
            test_mode=args.test,
            sample_size=args.sample,
            balance_judgments=args.balance,
        )
    )


if __name__ == "__main__":
    main()
