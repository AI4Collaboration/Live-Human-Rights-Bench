"""
Complete Format Comparison Experiment Pipeline

This script runs the full experiment:
1. Sample balanced cases (N violations + N no-violations)
2. Simplify sampled cases to 1-paragraph format
3. Evaluate LLM on ORIGINAL format
4. Evaluate LLM on SIMPLIFIED format
5. Compare results and output statistics
"""

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
    DEFAULT_JUDGE_MODEL,
    METADATA_FILE,
    ORIGINAL_DIR,
    EVALUATIONS_DIR,
    DATA_DIR,
    get_simplified_dir_name,
)
from src.real_cases.utils.simplification_prompts import (
    get_simplification_system_prompt,
    get_simplification_prompt_template,
)

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Suppress verbose logs from httpx and other libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)

# Evaluation prompts (neutral, without explicit convention mention)
EVALUATION_SYSTEM_PROMPT = """You are an expert legal analyst specializing in human rights law.

Analyze the case objectively and determine whether the state's actions constituted a violation of human rights."""

EVALUATION_PROMPT_TEMPLATE = """Case:

{case_text}

Based on the facts presented, did the state's actions constitute a violation of human rights?
Respond with ONLY one word: YES or NO

Your answer:"""


async def simplify_case(case_text: str, model_id: str, word_range: tuple, temperature: float = 0.3) -> str:
    """Simplify a single case."""
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=temperature, max_tokens=400)
    )

    system_prompt = get_simplification_system_prompt(word_range)
    prompt_template = get_simplification_prompt_template(word_range)
    prompt = prompt_template.format(case_text=case_text)

    simplified = await client.generate(
        prompt=prompt,
        system_message=system_prompt
    )

    return simplified.strip()


async def evaluate_case(case_text: str, model_id: str) -> str:
    """Evaluate whether case is violation or no_violation."""
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=0.0, max_tokens=10)
    )

    prompt = EVALUATION_PROMPT_TEMPLATE.format(case_text=case_text)
    response = await client.generate(
        prompt=prompt,
        system_message=EVALUATION_SYSTEM_PROMPT
    )

    # Parse response (YES = violation, NO = no_violation)
    response_clean = response.strip().upper()

    if "YES" in response_clean:
        return "violation"
    elif "NO" in response_clean:
        return "no_violation"
    else:
        logger.warning(f"Unclear response: {response}")
        return "unclear"


async def run_experiment(
    sample_size: int = None,
    word_range: tuple = None,
    simplification_model: str = DEFAULT_SIMPLIFICATION_MODEL,
    evaluation_model: str = DEFAULT_JUDGE_MODEL,
    metadata_file: str = METADATA_FILE,
    output_dir: str = EVALUATIONS_DIR,
):
    """Run the complete format comparison experiment."""

    # Use default word range if not specified
    if word_range is None:
        word_range = SIMPLIFICATION_CONFIG['word_range']

    # Get simplified directory name based on word range
    simplified_dir_name = get_simplified_dir_name(word_range)
    simplified_dir = Path(DATA_DIR) / simplified_dir_name

    logger.info("=" * 80)
    logger.info("FORMAT COMPARISON EXPERIMENT")
    logger.info("=" * 80)

    # Step 1: Load and sample data
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: SAMPLING CASES")
    logger.info("=" * 80)

    df = pd.read_csv(metadata_file)

    if sample_size is None:
        # Use ALL cases from original directory
        original_files = list(Path(ORIGINAL_DIR).glob("*.txt"))
        original_case_ids = [f.stem for f in original_files]
        df_sample = df[df['case_id'].isin(original_case_ids)]

        violations = df_sample[df_sample['judgment'] == 'violation']
        no_violations = df_sample[df_sample['judgment'] == 'no_violation']

        logger.info(f"📂 Using all {len(df_sample)} cases from original/")
        logger.info(f"   Violations: {len(violations)}")
        logger.info(f"   No violations: {len(no_violations)}")
    else:
        # Sample specified number
        violations = df[df['judgment'] == 'violation']
        no_violations = df[df['judgment'] == 'no_violation']

        per_class = sample_size // 2

        sampled_violations = violations.sample(n=min(per_class, len(violations)), random_state=42)
        sampled_no_violations = no_violations.sample(n=min(per_class, len(no_violations)), random_state=42)

        df_sample = pd.concat([sampled_violations, sampled_no_violations]).sample(frac=1, random_state=42)

        logger.info(f"📊 Sampled {len(df_sample)} cases (requested: {sample_size})")
        logger.info(f"   Violations: {len(sampled_violations)}")
        logger.info(f"   No violations: {len(sampled_no_violations)}")

    logger.info(f"Word range: {word_range[0]}-{word_range[1]} words")
    logger.info(f"Simplified directory: {simplified_dir}")
    logger.info(f"Simplification model: {simplification_model}")
    logger.info(f"Evaluation model: {evaluation_model}")

    # Step 2: Simplify cases (PARALLEL)
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: SIMPLIFYING CASES (PARALLEL)")
    logger.info("=" * 80)

    simplified_dir.mkdir(parents=True, exist_ok=True)

    async def process_simplification(row):
        """Process one case simplification."""
        case_id = row['case_id']

        # Read original text
        original_file = Path(ORIGINAL_DIR) / f"{case_id}.txt"
        original_text = original_file.read_text(encoding='utf-8')

        # Check if already simplified
        simplified_file = simplified_dir / f"{case_id}.txt"

        if simplified_file.exists():
            simplified_text = simplified_file.read_text(encoding='utf-8')
        else:
            try:
                simplified_text = await simplify_case(original_text, simplification_model, word_range)
                simplified_file.write_text(simplified_text, encoding='utf-8')
            except Exception as e:
                logger.error(f"❌ {case_id}: {e}")
                simplified_text = ""

        return original_text, simplified_text

    # Run simplifications in parallel
    logger.info(f"Processing {len(df_sample)} cases...")
    results = await asyncio.gather(*[process_simplification(row) for _, row in df_sample.iterrows()])

    original_texts = [r[0] for r in results]
    simplified_texts = [r[1] for r in results]

    df_sample['original_text'] = original_texts
    df_sample['simplified_text'] = simplified_texts

    logger.info(f"✓ Completed simplification of {len(df_sample)} cases")

    # Step 3: Evaluate ORIGINAL format (PARALLEL)
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: EVALUATING ORIGINAL FORMAT (PARALLEL)")
    logger.info("=" * 80)

    async def evaluate_original(row):
        """Evaluate one original case."""
        case_id = row['case_id']
        try:
            prediction = await evaluate_case(row['original_text'], evaluation_model)
            return prediction
        except Exception as e:
            logger.error(f"❌ {case_id}: {e}")
            return "error"

    logger.info(f"Evaluating {len(df_sample)} original cases...")
    original_predictions = await asyncio.gather(*[evaluate_original(row) for _, row in df_sample.iterrows()])

    df_sample['original_prediction'] = original_predictions
    df_sample['original_finds_violation'] = df_sample['original_prediction'] == 'violation'

    logger.info(f"✓ Completed evaluation of {len(df_sample)} original cases")

    # Step 4: Evaluate SIMPLIFIED format (PARALLEL)
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: EVALUATING SIMPLIFIED FORMAT (PARALLEL)")
    logger.info("=" * 80)

    async def evaluate_simplified(row):
        """Evaluate one simplified case."""
        case_id = row['case_id']
        try:
            prediction = await evaluate_case(row['simplified_text'], evaluation_model)
            return prediction
        except Exception as e:
            logger.error(f"❌ {case_id}: {e}")
            return "error"

    logger.info(f"Evaluating {len(df_sample)} simplified cases...")
    simplified_predictions = await asyncio.gather(*[evaluate_simplified(row) for _, row in df_sample.iterrows()])

    df_sample['simplified_prediction'] = simplified_predictions

    logger.info(f"✓ Completed evaluation of {len(df_sample)} simplified cases")

    # Filter out cases with unclear or error predictions in EITHER format
    valid_comparisons = df_sample[
        (~df_sample['original_prediction'].isin(['unclear', 'error'])) &
        (~df_sample['simplified_prediction'].isin(['unclear', 'error']))
    ].copy()

    excluded_count = len(df_sample) - len(valid_comparisons)
    if excluded_count > 0:
        logger.info(f"\nExcluded {excluded_count} cases with unparseable or error predictions")
        logger.info(f"  Original 'unclear': {(df_sample['original_prediction'] == 'unclear').sum()}")
        logger.info(f"  Original 'error': {(df_sample['original_prediction'] == 'error').sum()}")
        logger.info(f"  Simplified 'unclear': {(df_sample['simplified_prediction'] == 'unclear').sum()}")
        logger.info(f"  Simplified 'error': {(df_sample['simplified_prediction'] == 'error').sum()}")
        logger.info(f"Analyzing {len(valid_comparisons)} cases with valid predictions for both formats")

    # Calculate on valid comparisons only
    valid_comparisons['original_finds_violation'] = valid_comparisons['original_prediction'] == 'violation'
    valid_comparisons['simplified_finds_violation'] = valid_comparisons['simplified_prediction'] == 'violation'

    # Step 5: Compare results
    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: RESULTS COMPARISON")
    logger.info("=" * 80)

    # Calculate statistics
    original_violation_rate = valid_comparisons['original_finds_violation'].mean()
    simplified_violation_rate = valid_comparisons['simplified_finds_violation'].mean()
    reduction = original_violation_rate - simplified_violation_rate

    # Accuracy (if we have ground truth)
    original_accuracy = (valid_comparisons['original_prediction'] == valid_comparisons['judgment']).mean()
    simplified_accuracy = (valid_comparisons['simplified_prediction'] == valid_comparisons['judgment']).mean()

    # Calculate accuracy by ground truth category
    violation_subset = valid_comparisons[valid_comparisons['judgment'] == 'violation']
    no_violation_subset = valid_comparisons[valid_comparisons['judgment'] == 'no_violation']

    # Accuracy = correctly predicted violations / total violations
    orig_violation_accuracy = (violation_subset['original_prediction'] == 'violation').mean() if len(violation_subset) > 0 else 0
    simp_violation_accuracy = (violation_subset['simplified_prediction'] == 'violation').mean() if len(violation_subset) > 0 else 0

    # Accuracy = correctly predicted no_violations / total no_violations
    orig_no_violation_accuracy = (no_violation_subset['original_prediction'] == 'no_violation').mean() if len(no_violation_subset) > 0 else 0
    simp_no_violation_accuracy = (no_violation_subset['simplified_prediction'] == 'no_violation').mean() if len(no_violation_subset) > 0 else 0

    # Print results
    logger.info(f"\n{'Metric':<50} {'Original':<15} {'Simplified':<15} {'Difference':<15}")
    logger.info("-" * 95)
    logger.info(f"{'Percent of cases returning violation':<50} {original_violation_rate:>13.1%} {simplified_violation_rate:>13.1%} {reduction:>13.1%}")
    logger.info(f"{'Final accuracy (overall)':<50} {original_accuracy:>13.1%} {simplified_accuracy:>13.1%} {simplified_accuracy - original_accuracy:>13.1%}")
    logger.info(f"{'Accuracy when ground truth is violation':<50} {orig_violation_accuracy:>13.1%} {simp_violation_accuracy:>13.1%} {simp_violation_accuracy - orig_violation_accuracy:>13.1%}")
    logger.info(f"{'Accuracy when ground truth is no violation':<50} {orig_no_violation_accuracy:>13.1%} {simp_no_violation_accuracy:>13.1%} {simp_no_violation_accuracy - orig_no_violation_accuracy:>13.1%}")

    # Save results
    logger.info("\n" + "=" * 80)
    logger.info("SAVING RESULTS")
    logger.info("=" * 80)

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Save detailed results
    eval_model_name = evaluation_model.replace('/', '-')
    word_range_str = f"{word_range[0]}_{word_range[1]}"
    results_file = Path(output_dir) / f"comparison_{word_range_str}w_{eval_model_name}_n{sample_size}.csv"

    df_sample.to_csv(results_file, index=False)
    logger.info(f"📊 Detailed results: {results_file}")

    # Save summary
    summary = {
        'sample_size': sample_size,
        'word_range_min': word_range[0],
        'word_range_max': word_range[1],
        'simplification_model': simplification_model,
        'evaluation_model': evaluation_model,
        'original_violation_rate': original_violation_rate,
        'simplified_violation_rate': simplified_violation_rate,
        'reduction': reduction,
        'original_accuracy': original_accuracy,
        'simplified_accuracy': simplified_accuracy,
    }

    summary_file = Path(output_dir) / f"summary_{word_range_str}w_{eval_model_name}_n{sample_size}.csv"
    pd.DataFrame([summary]).to_csv(summary_file, index=False)
    logger.info(f"📈 Summary: {summary_file}")

    # Interpretation
    logger.info("\n" + "=" * 80)
    logger.info("INTERPRETATION")
    logger.info("=" * 80)

    if reduction < 0.05:
        logger.info("🔍 Hypothesis 1: Training data bias dominates (style has minimal effect)")
    elif reduction > 0.20:
        logger.info("🔍 Hypothesis 2: Document style bias dominates")
    else:
        logger.info("🔍 Hypothesis 3: BOTH training data AND style contribute to bias")

    logger.info(f"\n{'Style bias effect:':<30} {reduction:.1%} reduction in violation rate")

    return df_sample, summary


def main():
    parser = argparse.ArgumentParser(
        description="Run complete format comparison experiment"
    )
    parser.add_argument(
        "--sample",
        type=int,
        help="Total sample size (will split 50/50 violations/no-violations). If not specified, uses all cases in original/"
    )
    parser.add_argument(
        "--simplification_model",
        default=DEFAULT_SIMPLIFICATION_MODEL,
        help="Model for simplification"
    )
    parser.add_argument(
        "--evaluation_model",
        default=DEFAULT_JUDGE_MODEL,
        help="Model for evaluation/judgment"
    )
    parser.add_argument(
        "--metadata",
        default=METADATA_FILE,
        help="Path to metadata CSV"
    )
    parser.add_argument(
        "--output_dir",
        default=EVALUATIONS_DIR,
        help="Output directory for results"
    )
    parser.add_argument(
        "--word_range_min",
        type=int,
        help=f"Minimum words for summary (default: {SIMPLIFICATION_CONFIG['word_range'][0]})"
    )
    parser.add_argument(
        "--word_range_max",
        type=int,
        help=f"Maximum words for summary (default: {SIMPLIFICATION_CONFIG['word_range'][1]})"
    )

    args = parser.parse_args()

    # Build word range tuple
    word_range = None
    if args.word_range_min and args.word_range_max:
        word_range = (args.word_range_min, args.word_range_max)

    asyncio.run(
        run_experiment(
            sample_size=args.sample,
            word_range=word_range,
            simplification_model=args.simplification_model,
            evaluation_model=args.evaluation_model,
            metadata_file=args.metadata,
            output_dir=args.output_dir,
        )
    )


if __name__ == "__main__":
    main()
