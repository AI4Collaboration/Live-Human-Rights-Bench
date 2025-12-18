"""
Identity Framing Experiment

Tests whether evaluator identity framing affects violation detection rates.
Evaluates the same cases with different evaluator personas (e.g., "You are a judge" vs "How would a judge respond?")
"""

import asyncio
import argparse
import logging
import pandas as pd
from pathlib import Path
from inspect_ai.model import GenerateConfig

from src.client import LLMClient
from src.real_cases.config import (
    DEFAULT_JUDGE_MODEL,
    METADATA_FILE,
    ORIGINAL_DIR,
    EVALUATIONS_DIR,
)
from src.real_cases.utils.evaluator_prompts import (
    EVALUATION_PROMPT_TEMPLATE,
    EVALUATOR_IDENTITIES,
    get_evaluator_prompt,
    list_evaluator_identities,
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


async def evaluate_case(case_text: str, system_prompt: str, model_id: str) -> str:
    """Evaluate whether case is violation or no_violation using specified system prompt."""
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=0.0, max_tokens=10)
    )

    prompt = EVALUATION_PROMPT_TEMPLATE.format(case_text=case_text)
    response = await client.generate(
        prompt=prompt,
        system_message=system_prompt
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


async def run_identity_experiment(
    identities: list = None,
    sample_size: int = None,
    evaluation_model: str = DEFAULT_JUDGE_MODEL,
    metadata_file: str = METADATA_FILE,
    output_dir: str = EVALUATIONS_DIR,
    use_original: bool = True,
    simplified_dir: str = None,
):
    """Run identity framing experiment.

    Args:
        identities: List of identity keys to test. If None, tests all.
        sample_size: Number of cases to sample. If None, uses all from original/.
        evaluation_model: Model to use for evaluation.
        use_original: If True, evaluate original format. If False, use simplified.
        simplified_dir: Path to simplified cases (only if use_original=False).
    """

    logger.info("=" * 80)
    logger.info("IDENTITY FRAMING EXPERIMENT")
    logger.info("=" * 80)

    # Determine which identities to test
    if identities is None:
        identities = list(EVALUATOR_IDENTITIES.keys())

    logger.info(f"\nTesting {len(identities)} evaluator identities:")
    for identity_key in identities:
        name, _ = get_evaluator_prompt(identity_key)
        logger.info(f"  - {identity_key}: {name}")

    # Step 1: Load and sample data
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: LOADING CASES")
    logger.info("=" * 80)

    df = pd.read_csv(metadata_file)

    if sample_size is None:
        # Use ALL cases from original directory
        if use_original:
            original_files = list(Path(ORIGINAL_DIR).glob("*.txt"))
            case_ids = [f.stem for f in original_files]
        else:
            simplified_files = list(Path(simplified_dir).glob("*.txt"))
            case_ids = [f.stem for f in simplified_files]

        df_sample = df[df['case_id'].isin(case_ids)]
        logger.info(f"📂 Using all {len(df_sample)} cases")
    else:
        # Sample specified number
        violations = df[df['judgment'] == 'violation']
        no_violations = df[df['judgment'] == 'no_violation']

        per_class = sample_size // 2

        sampled_violations = violations.sample(n=min(per_class, len(violations)), random_state=42)
        sampled_no_violations = no_violations.sample(n=min(per_class, len(no_violations)), random_state=42)

        df_sample = pd.concat([sampled_violations, sampled_no_violations]).sample(frac=1, random_state=42)
        logger.info(f"📊 Sampled {len(df_sample)} cases")

    violations = df_sample[df_sample['judgment'] == 'violation']
    no_violations = df_sample[df_sample['judgment'] == 'no_violation']
    logger.info(f"   Violations: {len(violations)}")
    logger.info(f"   No violations: {len(no_violations)}")

    # Load case texts
    case_texts = []
    case_dir = Path(ORIGINAL_DIR) if use_original else Path(simplified_dir)

    for _, row in df_sample.iterrows():
        case_id = row['case_id']
        case_file = case_dir / f"{case_id}.txt"
        case_text = case_file.read_text(encoding='utf-8')
        case_texts.append(case_text)

    df_sample['case_text'] = case_texts

    # Step 2: Evaluate with each identity
    results_by_identity = {}

    for identity_key in identities:
        logger.info("\n" + "=" * 80)
        identity_name, system_prompt = get_evaluator_prompt(identity_key)
        logger.info(f"EVALUATING: {identity_name}")
        logger.info("=" * 80)

        async def evaluate_with_identity(row):
            """Evaluate one case with current identity."""
            case_id = row['case_id']
            try:
                prediction = await evaluate_case(row['case_text'], system_prompt, evaluation_model)
                return prediction
            except Exception as e:
                logger.error(f"❌ {case_id}: {e}")
                return "error"

        logger.info(f"Evaluating {len(df_sample)} cases...")
        predictions = await asyncio.gather(*[evaluate_with_identity(row) for _, row in df_sample.iterrows()])

        df_sample[f'pred_{identity_key}'] = predictions

        # Filter out unclear and error predictions for this identity
        valid_for_identity = df_sample[~df_sample[f'pred_{identity_key}'].isin(['unclear', 'error'])].copy()
        excluded_count = len(df_sample) - len(valid_for_identity)

        if excluded_count > 0:
            logger.info(f"   Excluded {excluded_count} cases with unparseable/error predictions")
            logger.info(f"   Analyzing {len(valid_for_identity)} valid predictions")

        valid_for_identity[f'finds_violation_{identity_key}'] = valid_for_identity[f'pred_{identity_key}'] == 'violation'

        # Calculate metrics only on valid predictions
        violation_rate = valid_for_identity[f'finds_violation_{identity_key}'].mean()
        accuracy = (valid_for_identity[f'pred_{identity_key}'] == valid_for_identity['judgment']).mean()

        violation_subset = valid_for_identity[valid_for_identity['judgment'] == 'violation']
        no_violation_subset = valid_for_identity[valid_for_identity['judgment'] == 'no_violation']

        violation_accuracy = (violation_subset[f'pred_{identity_key}'] == 'violation').mean() if len(violation_subset) > 0 else 0
        no_violation_accuracy = (no_violation_subset[f'pred_{identity_key}'] == 'no_violation').mean() if len(no_violation_subset) > 0 else 0

        results_by_identity[identity_key] = {
            'identity_key': identity_key,
            'identity_name': identity_name,
            'violation_rate': violation_rate,
            'accuracy': accuracy,
            'violation_accuracy': violation_accuracy,
            'no_violation_accuracy': no_violation_accuracy,
        }

        logger.info(f"✓ Completed: {identity_name}")
        logger.info(f"   Violation rate: {violation_rate:.1%}")
        logger.info(f"   Accuracy: {accuracy:.1%}")

    # Step 3: Compare results
    logger.info("\n" + "=" * 80)
    logger.info("RESULTS COMPARISON")
    logger.info("=" * 80)

    # Create comparison table
    results_df = pd.DataFrame(list(results_by_identity.values()))

    # Sort by violation rate
    results_df = results_df.sort_values('violation_rate', ascending=False)

    # Print results table
    logger.info(f"\n{'Identity':<30} {'Violation Rate':<15} {'Accuracy':<15} {'Viol Acc':<15} {'No-Viol Acc':<15}")
    logger.info("-" * 90)

    for _, row in results_df.iterrows():
        logger.info(f"{row['identity_name']:<30} {row['violation_rate']:>13.1%} {row['accuracy']:>13.1%} {row['violation_accuracy']:>13.1%} {row['no_violation_accuracy']:>13.1%}")

    # Calculate variance
    violation_rate_std = results_df['violation_rate'].std()
    violation_rate_range = results_df['violation_rate'].max() - results_df['violation_rate'].min()

    logger.info(f"\nVariance Analysis:")
    logger.info(f"  Violation rate range: {violation_rate_range:.1%} ({results_df['violation_rate'].min():.1%} to {results_df['violation_rate'].max():.1%})")
    logger.info(f"  Violation rate std dev: {violation_rate_std:.1%}")

    # Interpretation
    logger.info("\n" + "=" * 80)
    logger.info("INTERPRETATION")
    logger.info("=" * 80)

    if violation_rate_range < 0.05:
        logger.info("🔍 Identity framing has MINIMAL effect (<5% range)")
    elif violation_rate_range < 0.10:
        logger.info("🔍 Identity framing has SMALL effect (5-10% range)")
    elif violation_rate_range < 0.20:
        logger.info("🔍 Identity framing has MODERATE effect (10-20% range)")
    else:
        logger.info("🔍 Identity framing has LARGE effect (>20% range)")

    # Find highest and lowest
    highest = results_df.iloc[0]
    lowest = results_df.iloc[-1]

    logger.info(f"\nHighest violation rate: {highest['identity_name']} ({highest['violation_rate']:.1%})")
    logger.info(f"Lowest violation rate: {lowest['identity_name']} ({lowest['violation_rate']:.1%})")

    # Save results
    logger.info("\n" + "=" * 80)
    logger.info("SAVING RESULTS")
    logger.info("=" * 80)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    eval_model_name = evaluation_model.replace('/', '-')
    format_str = "original" if use_original else "simplified"

    # Save detailed results
    results_file = Path(output_dir) / f"identity_comparison_{format_str}_{eval_model_name}_n{len(df_sample)}.csv"
    df_sample.to_csv(results_file, index=False)
    logger.info(f"📊 Detailed results: {results_file}")

    # Save summary
    summary_file = Path(output_dir) / f"identity_summary_{format_str}_{eval_model_name}_n{len(df_sample)}.csv"
    results_df.to_csv(summary_file, index=False)
    logger.info(f"📈 Summary: {summary_file}")

    return df_sample, results_df


def main():
    parser = argparse.ArgumentParser(
        description="Test how evaluator identity framing affects violation detection"
    )
    parser.add_argument(
        "--identities",
        nargs="+",
        help=f"Identity keys to test (space-separated). Available: {list(EVALUATOR_IDENTITIES.keys())}. If not specified, tests all."
    )
    parser.add_argument(
        "--sample",
        type=int,
        help="Total sample size (will split 50/50 violations/no-violations). If not specified, uses all cases in original/"
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
        "--simplified",
        action="store_true",
        help="Use simplified cases instead of original"
    )
    parser.add_argument(
        "--simplified_dir",
        help="Path to simplified cases directory (required if --simplified is used)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available evaluator identities and exit"
    )

    args = parser.parse_args()

    # List identities if requested
    if args.list:
        print("\nAvailable Evaluator Identities:")
        print("=" * 60)
        for key, name in list_evaluator_identities():
            print(f"  {key:<25} {name}")
        print()
        return

    # Validate simplified args
    if args.simplified and not args.simplified_dir:
        parser.error("--simplified_dir is required when using --simplified")

    asyncio.run(
        run_identity_experiment(
            identities=args.identities,
            sample_size=args.sample,
            evaluation_model=args.evaluation_model,
            metadata_file=args.metadata,
            output_dir=args.output_dir,
            use_original=not args.simplified,
            simplified_dir=args.simplified_dir,
        )
    )


if __name__ == "__main__":
    main()
