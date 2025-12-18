"""
Baseline Experiment - Simple N violations + N no-violations

This is the simplest possible experiment: sample N cases with violations and N cases
without violations, then evaluate LLM performance.

For a given sample size N:
1. Sample N cases with violations
2. Sample N cases with no violations
3. Evaluate LLM on all cases (total: 2N cases)
4. Output overall accuracy and violation detection bias
"""

import asyncio
import argparse
import logging
import pandas as pd
from pathlib import Path
from inspect_ai.model import GenerateConfig

from src.client import LLMClient
from src.real_cases.config import DEFAULT_JUDGE_MODEL, DEFAULT_SIMPLIFICATION_MODEL, get_cache_dir_name
from src.real_cases.utils.simplification_prompts import (
    get_simplification_system_prompt,
    get_simplification_prompt_template,
    get_anonymization_system_prompt,
    get_anonymization_prompt_template,
    get_story_system_prompt,
    get_story_prompt_template,
)

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Suppress verbose logs
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


async def simplify_case(case_text: str, model_id: str, word_range: tuple = (150, 200), temperature: float = 0.3) -> str:
    """Simplify a single case with anonymization."""
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


async def anonymize_case(case_text: str, model_id: str, temperature: float = 0.3) -> str:
    """Anonymize a case without summarizing (keep full length)."""
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=temperature, max_tokens=4000)
    )

    system_prompt = get_anonymization_system_prompt()
    prompt_template = get_anonymization_prompt_template()
    prompt = prompt_template.format(case_text=case_text)

    anonymized = await client.generate(
        prompt=prompt,
        system_message=system_prompt
    )

    return anonymized.strip()


async def story_case(case_text: str, model_id: str, word_range: tuple = (150, 200), temperature: float = 0.3) -> str:
    """Convert case to story-based narrative format."""
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=temperature, max_tokens=400)
    )

    system_prompt = get_story_system_prompt(word_range)
    prompt_template = get_story_prompt_template(word_range)
    prompt = prompt_template.format(case_text=case_text)

    story = await client.generate(
        prompt=prompt,
        system_message=system_prompt
    )

    return story.strip()


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


async def run_baseline_experiment(
    n: int,
    evaluation_model: str = DEFAULT_JUDGE_MODEL,
    simplification_model: str = DEFAULT_SIMPLIFICATION_MODEL,
    word_range: tuple = (150, 200),
    anonymize_only: bool = False,
    story_mode: bool = False,
    data_dir: str = None,
    output_dir: str = None,
    random_seed: int = 42,
):
    """Run baseline experiment: N violations + N no-violations."""

    if data_dir is None:
        data_dir = Path('/Users/mac/Desktop/llm-human-rights/data/real_cases/echr_new/unanimous')
    else:
        data_dir = Path(data_dir)

    if output_dir is None:
        output_dir = Path('/Users/mac/Desktop/llm-human-rights/data/real_cases/echr_new/evaluations')
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    if anonymize_only:
        mode = "ANONYMIZATION ONLY"
    elif story_mode:
        mode = "STORY MODE"
    else:
        mode = "WITH SUMMARIZATION"

    logger.info("=" * 80)
    logger.info(f"BASELINE EXPERIMENT ({mode})")
    logger.info("=" * 80)
    logger.info(f"Sample size per group: {n}")
    logger.info(f"Simplification model: {simplification_model}")
    if not anonymize_only:
        logger.info(f"Word range: {word_range[0]}-{word_range[1]} words")
    logger.info(f"Evaluation model: {evaluation_model}")
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Random seed: {random_seed}")

    # Load data
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: LOADING AND SAMPLING DATA")
    logger.info("=" * 80)

    csv_file = data_dir / 'cases.csv'
    df = pd.read_csv(csv_file)

    logger.info(f"Total cases loaded: {len(df)}")
    logger.info(f"Total violations: {(df['violation_label'] == 'violation').sum()}")
    logger.info(f"Total no violations: {(df['violation_label'] == 'no_violation').sum()}")

    # Sample N violations
    violation_cases = df[df['violation_label'] == 'violation']
    if len(violation_cases) < n:
        logger.warning(f"⚠️  Only {len(violation_cases)} violation cases available (requested {n})")
        sampled_violations = violation_cases
    else:
        sampled_violations = violation_cases.sample(n=n, random_state=random_seed)

    sampled_violations = sampled_violations.copy()
    sampled_violations['ground_truth'] = 'violation'

    logger.info(f"✓ Sampled {len(sampled_violations)} violation cases")

    # Sample N no-violations
    no_violation_cases = df[df['violation_label'] == 'no_violation']
    if len(no_violation_cases) < n:
        logger.warning(f"⚠️  Only {len(no_violation_cases)} no-violation cases available (requested {n})")
        sampled_no_violations = no_violation_cases
    else:
        sampled_no_violations = no_violation_cases.sample(n=n, random_state=random_seed)

    sampled_no_violations = sampled_no_violations.copy()
    sampled_no_violations['ground_truth'] = 'no_violation'

    logger.info(f"✓ Sampled {len(sampled_no_violations)} no-violation cases")

    # Combine and shuffle
    df_experiment = pd.concat([sampled_violations, sampled_no_violations], ignore_index=True)
    df_experiment = df_experiment.sample(frac=1, random_state=random_seed).reset_index(drop=True)

    logger.info(f"\n📊 Total cases in experiment: {len(df_experiment)}")
    logger.info(f"   Violations: {(df_experiment['ground_truth'] == 'violation').sum()}")
    logger.info(f"   No violations: {(df_experiment['ground_truth'] == 'no_violation').sum()}")

    # Step 2: Process cases
    if anonymize_only:
        step_name = "ANONYMIZING"
    elif story_mode:
        step_name = "STORY-IFYING"
    else:
        step_name = "SIMPLIFYING"

    logger.info("\n" + "=" * 80)
    logger.info(f"STEP 2: {step_name} CASES (WITH CACHING)")
    logger.info("=" * 80)

    # Create cache directory with model name
    cache_dir_name = get_cache_dir_name(anonymize_only, story_mode, word_range, simplification_model)
    cache_dir = data_dir.parent / cache_dir_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Cache directory: {cache_dir}")

    async def process_single_case(row):
        """Process one case, using cache if available."""
        item_id = row['item_id']
        case_text = row['full_case_text']

        # Check cache first
        cache_file = cache_dir / f"{item_id}.txt"

        if cache_file.exists():
            processed = cache_file.read_text(encoding='utf-8')
            logger.info(f"✓ {item_id} (from cache)")
            return processed

        # Not in cache, process it
        try:
            if anonymize_only:
                processed = await anonymize_case(case_text, simplification_model)
                action = "anonymized"
            elif story_mode:
                processed = await story_case(case_text, simplification_model, word_range)
                action = "story-ified"
            else:
                processed = await simplify_case(case_text, simplification_model, word_range)
                action = "simplified"

            # Save to cache
            cache_file.write_text(processed, encoding='utf-8')
            logger.info(f"✓ {item_id} ({action} & cached)")
            return processed
        except Exception as e:
            logger.error(f"❌ Error processing {item_id}: {e}")
            return ""

    logger.info(f"{step_name.capitalize()} {len(df_experiment)} cases (will use cache when available)...")
    processed_texts = await asyncio.gather(*[process_single_case(row) for _, row in df_experiment.iterrows()])

    df_experiment['processed_text'] = processed_texts

    logger.info(f"✓ Completed {step_name.lower()} of {len(df_experiment)} cases")

    # Step 3: Evaluate
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: EVALUATING PROCESSED CASES")
    logger.info("=" * 80)

    async def evaluate_single_case(row):
        """Evaluate one processed case."""
        item_id = row['item_id']
        case_text = row['processed_text']

        try:
            prediction = await evaluate_case(case_text, evaluation_model)
            logger.info(f"✓ {item_id} (truth: {row['ground_truth']}): {prediction}")
            return prediction
        except Exception as e:
            logger.error(f"❌ {item_id}: {e}")
            return "error"

    logger.info(f"Evaluating {len(df_experiment)} processed cases...")
    predictions = await asyncio.gather(*[evaluate_single_case(row) for _, row in df_experiment.iterrows()])

    df_experiment['llm_prediction'] = predictions

    logger.info(f"✓ Completed evaluation")

    # Filter out unclear and error predictions
    valid_predictions = df_experiment[
        ~df_experiment['llm_prediction'].isin(['unclear', 'error'])
    ].copy()

    excluded_count = len(df_experiment) - len(valid_predictions)
    if excluded_count > 0:
        logger.info(f"\nExcluded {excluded_count} cases with unparseable or error predictions")
        logger.info(f"  'unclear': {(df_experiment['llm_prediction'] == 'unclear').sum()}")
        logger.info(f"  'error': {(df_experiment['llm_prediction'] == 'error').sum()}")
        logger.info(f"Analyzing {len(valid_predictions)} cases with valid predictions")

    # Calculate metrics only on valid predictions
    valid_predictions['llm_finds_violation'] = valid_predictions['llm_prediction'] == 'violation'
    valid_predictions['correct'] = valid_predictions['llm_prediction'] == valid_predictions['ground_truth']

    # Step 4: Results
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: RESULTS ANALYSIS")
    logger.info("=" * 80)

    overall_accuracy = valid_predictions['correct'].mean()
    llm_violation_rate = valid_predictions['llm_finds_violation'].mean()

    logger.info(f"\n{'Metric':<50} {'Value':<15}")
    logger.info("-" * 70)
    logger.info(f"{'Overall accuracy':<50} {overall_accuracy:>13.1%}")
    logger.info(f"{'LLM violation detection rate':<50} {llm_violation_rate:>13.1%}")

    # Per-class statistics
    logger.info(f"\n{'Ground Truth':<20} {'N':<8} {'LLM Says Violation':<20} {'Accuracy':<15}")
    logger.info("-" * 70)

    for truth in ['no_violation', 'violation']:
        subset = valid_predictions[valid_predictions['ground_truth'] == truth]
        count = len(subset)
        llm_viol_rate = subset['llm_finds_violation'].mean()
        accuracy = subset['correct'].mean()
        logger.info(f"{truth:<20} {count:<8} {llm_viol_rate:>18.1%} {accuracy:>14.1%}")

    # Confusion matrix
    tp = ((valid_predictions['ground_truth'] == 'violation') & (valid_predictions['llm_prediction'] == 'violation')).sum()
    tn = ((valid_predictions['ground_truth'] == 'no_violation') & (valid_predictions['llm_prediction'] == 'no_violation')).sum()
    fp = ((valid_predictions['ground_truth'] == 'no_violation') & (valid_predictions['llm_prediction'] == 'violation')).sum()
    fn = ((valid_predictions['ground_truth'] == 'violation') & (valid_predictions['llm_prediction'] == 'no_violation')).sum()

    logger.info(f"\nConfusion Matrix:")
    logger.info(f"  True Positives: {tp}, True Negatives: {tn}")
    logger.info(f"  False Positives: {fp}, False Negatives: {fn}")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    logger.info(f"\nMetrics:")
    logger.info(f"  Precision: {precision:.1%}")
    logger.info(f"  Recall: {recall:.1%}")
    logger.info(f"  F1 Score: {f1:.1%}")

    # Bias check
    if fp > fn * 2:
        logger.info(f"\n⚠️  STRONG VIOLATION BIAS DETECTED!")
        logger.info(f"    Model has {fp} false positives vs {fn} false negatives")
    elif fn > fp * 2:
        logger.info(f"\n⚠️  STRONG NO-VIOLATION BIAS DETECTED!")
        logger.info(f"    Model has {fn} false negatives vs {fp} false positives")

    # Save results
    logger.info("\n" + "=" * 80)
    logger.info("SAVING RESULTS")
    logger.info("=" * 80)

    eval_model_name = evaluation_model.replace('/', '-')
    if anonymize_only:
        mode_str = "anon"
    elif story_mode:
        mode_str = f"story_{word_range[0]}_{word_range[1]}"
    else:
        mode_str = f"simp_{word_range[0]}_{word_range[1]}"

    results_file = output_dir / f"baseline_{mode_str}_{eval_model_name}_n{n}.csv"
    df_experiment.to_csv(results_file, index=False)
    logger.info(f"📊 Detailed results: {results_file}")

    summary = {
        'n': n,
        'mode': 'anonymize_only' if anonymize_only else ('story_mode' if story_mode else 'summarize'),
        'word_range': f"{word_range[0]}-{word_range[1]}" if not anonymize_only else 'N/A',
        'evaluation_model': evaluation_model,
        'total_cases': len(df_experiment),
        'valid_cases': len(valid_predictions),
        'excluded_cases': excluded_count,
        'overall_accuracy': overall_accuracy,
        'llm_violation_rate': llm_violation_rate,
        'true_positives': tp,
        'true_negatives': tn,
        'false_positives': fp,
        'false_negatives': fn,
        'precision': precision,
        'recall': recall,
        'f1': f1,
    }

    summary_file = output_dir / f"baseline_summary_{mode_str}_{eval_model_name}_n{n}.csv"
    pd.DataFrame([summary]).to_csv(summary_file, index=False)
    logger.info(f"📈 Summary: {summary_file}")

    logger.info("\n" + "=" * 80)
    logger.info("✓ EXPERIMENT COMPLETE")
    logger.info("=" * 80)

    return df_experiment, summary


def main():
    parser = argparse.ArgumentParser(
        description="Run baseline experiment: N violations + N no-violations"
    )
    parser.add_argument(
        "-n",
        type=int,
        required=True,
        help="Number of cases per group (N violations + N no-violations, total 2N cases)"
    )
    parser.add_argument(
        "--simplification_model",
        default=DEFAULT_SIMPLIFICATION_MODEL,
        help="Model for case simplification"
    )
    parser.add_argument(
        "--evaluation_model",
        default=DEFAULT_JUDGE_MODEL,
        help="Model for evaluation/judgment"
    )
    parser.add_argument(
        "--word_range_min",
        type=int,
        default=150,
        help="Minimum words for summary (default: 150)"
    )
    parser.add_argument(
        "--word_range_max",
        type=int,
        default=200,
        help="Maximum words for summary (default: 200)"
    )
    parser.add_argument(
        "--anonymize_only",
        action="store_true",
        help="Only anonymize cases (keep full length), don't summarize"
    )
    parser.add_argument(
        "--story_mode",
        action="store_true",
        help="Use story-based narrative format"
    )
    parser.add_argument(
        "--data_dir",
        default=None,
        help="Data directory (default: data/real_cases/echr_new/unanimous)"
    )
    parser.add_argument(
        "--output_dir",
        default=None,
        help="Output directory (default: data/real_cases/echr_new/evaluations)"
    )
    parser.add_argument(
        "--random_seed",
        type=int,
        default=42,
        help="Random seed for sampling (default: 42)"
    )

    args = parser.parse_args()

    word_range = (args.word_range_min, args.word_range_max)

    asyncio.run(
        run_baseline_experiment(
            n=args.n,
            evaluation_model=args.evaluation_model,
            simplification_model=args.simplification_model,
            word_range=word_range,
            anonymize_only=args.anonymize_only,
            story_mode=args.story_mode,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            random_seed=args.random_seed,
        )
    )


if __name__ == "__main__":
    main()
