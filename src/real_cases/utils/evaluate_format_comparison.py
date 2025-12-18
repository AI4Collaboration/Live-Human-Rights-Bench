"""
Quick evaluation script for format comparison experiment.

This script:
1. Loads cases (original OR simplified format)
2. Asks LLM to judge: violation or no_violation
3. Saves results with model predictions
"""

import asyncio
import argparse
import logging
import pandas as pd
from pathlib import Path
from inspect_ai.model import GenerateConfig

from src.client import LLMClient
from src.real_cases.config import (
    METADATA_FILE,
    ORIGINAL_DIR,
    SIMPLIFIED_DIR,
    EVALUATIONS_DIR,
    DEFAULT_JUDGE_MODEL,
)

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Evaluation prompt (neutral, without explicit convention mention)
EVALUATION_SYSTEM_PROMPT = """You are an expert legal analyst specializing in human rights law.

Analyze the case objectively and determine whether the state's actions constituted a violation of human rights. Respond with ONLY one word:
- VIOLATION (if the state violated human rights)
- NO_VIOLATION (if the state did not violate human rights)"""

EVALUATION_PROMPT_TEMPLATE = """Case:

{case_text}

Based on the facts presented, did the state's actions constitute a violation of human rights? Respond with only: VIOLATION or NO_VIOLATION

Your answer:"""


async def evaluate_case(
    case_text: str,
    model_id: str,
    client: LLMClient = None
) -> str:
    """Evaluate a single case."""

    if client is None:
        client = LLMClient(
            model_id,
            config=GenerateConfig(temperature=0.0, max_tokens=10)
        )

    prompt = EVALUATION_PROMPT_TEMPLATE.format(case_text=case_text)

    response = await client.generate(
        prompt=prompt,
        system_message=EVALUATION_SYSTEM_PROMPT
    )

    # Parse response
    response_clean = response.strip().upper()

    if "VIOLATION" in response_clean and "NO_VIOLATION" not in response_clean:
        return "violation"
    elif "NO_VIOLATION" in response_clean or "NO VIOLATION" in response_clean:
        return "no_violation"
    else:
        logger.warning(f"Unclear response: {response}")
        return "unclear"


async def evaluate_all_cases(
    format_type: str,  # "original" or "simplified"
    model_id: str = DEFAULT_JUDGE_MODEL,
    metadata_file: str = None,
    output_file: str = None,
    test_mode: bool = False,
):
    """Evaluate all cases in specified format."""

    # Load metadata
    if metadata_file is None:
        metadata_file = METADATA_FILE.replace("metadata.csv", "metadata_with_simplified.csv")

    df = pd.read_csv(metadata_file)

    if test_mode:
        logger.info("🧪 Running in TEST MODE - only first case")
        df = df.head(1)

    logger.info(f"📋 Evaluating {len(df)} cases")
    logger.info(f"📄 Format: {format_type}")
    logger.info(f"🤖 Model: {model_id}")

    # Create client
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=0.0, max_tokens=10)
    )

    # Evaluate each case
    predictions = []

    for idx, row in df.iterrows():
        case_id = row['case_id']
        article = row['article']

        # Load case text
        if format_type == "original":
            case_file = Path(ORIGINAL_DIR) / f"{case_id}.txt"
        else:  # simplified
            case_file = Path(SIMPLIFIED_DIR) / f"{case_id}.txt"

        case_text = case_file.read_text(encoding='utf-8')

        logger.info(f"⚖️  Evaluating {idx+1}/{len(df)}: {case_id} (Article {article})")

        try:
            prediction = await evaluate_case(case_text, model_id, client)
            predictions.append(prediction)
            logger.info(f"   → {prediction.upper()}")
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
            predictions.append("error")

    # Add predictions to dataframe
    df['model_prediction'] = predictions
    df['finds_violation'] = df['model_prediction'] == 'violation'

    # Calculate stats
    violation_rate = df['finds_violation'].mean()
    logger.info(f"\n📊 Results:")
    logger.info(f"   Violation rate: {violation_rate:.1%} ({df['finds_violation'].sum()}/{len(df)} cases)")

    # If we have ground truth, calculate accuracy
    if not df['judgment'].isna().all():
        accuracy = (df['model_prediction'] == df['judgment']).mean()
        logger.info(f"   Accuracy: {accuracy:.1%}")

    # Save results
    if output_file is None:
        Path(EVALUATIONS_DIR).mkdir(parents=True, exist_ok=True)
        model_name = model_id.replace('/', '-')
        output_file = f"{EVALUATIONS_DIR}/{format_type}_{model_name}.csv"

    df.to_csv(output_file, index=False)
    logger.info(f"\n💾 Saved to: {output_file}")

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate cases to test format bias hypothesis"
    )
    parser.add_argument(
        "--format",
        choices=["original", "simplified"],
        required=True,
        help="Case format to evaluate"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_JUDGE_MODEL,
        help="Model to use for evaluation"
    )
    parser.add_argument(
        "--output",
        help="Output CSV file path"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode - only evaluate first case"
    )

    args = parser.parse_args()

    asyncio.run(
        evaluate_all_cases(
            format_type=args.format,
            model_id=args.model,
            output_file=args.output,
            test_mode=args.test,
        )
    )


if __name__ == "__main__":
    main()
