"""
Importance Level Experiment

This script evaluates LLM performance across different case importance levels to test
whether model accuracy varies with case significance.

ECHR importance levels (1 = highest, 4 = lowest):
- Level 1: Key cases (precedent-setting, high impact)
- Level 2: Important cases
- Level 3: Medium importance
- Level 4: Lower importance (routine cases)

For a given sample size N and each importance level (1-4):
1. Sample N cases at that importance level (N/2 violations, N/2 no-violations)
2. Evaluate LLM on all cases (total: 4N cases)
3. Output results comparing:
   - Accuracy per importance level
   - Violation detection bias per level
   - Whether LLMs perform better on high-importance (clearer) vs low-importance cases
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


async def run_importance_experiment(
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
    """Run importance level experiment comparing LLM performance across case significance levels."""

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
    logger.info(f"IMPORTANCE LEVEL EXPERIMENT ({mode})")
    logger.info("=" * 80)
    logger.info(f"Sample size per importance level: {n}")
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

    # Check importance distribution
    logger.info(f"\nImportance level distribution:")
    importance_counts = df['importance'].value_counts().sort_index()
    for level, count in importance_counts.items():
        logger.info(f"  Level {level}: {count} cases")

    # Sample N cases for EACH importance level (N/2 violations, N/2 no-violations)
    all_samples = []

    for importance_level in [1, 2, 3, 4]:
        logger.info(f"\n--- Sampling {n} cases at importance level {importance_level} ({n//2} violations + {n//2} no-violations) ---")

        level_df = df[df['importance'] == importance_level]
        level_violations = level_df[level_df['violation_label'] == 'violation']
        level_no_violations = level_df[level_df['violation_label'] == 'no_violation']

        logger.info(f"Available level {importance_level} violations: {len(level_violations)}")
        logger.info(f"Available level {importance_level} no-violations: {len(level_no_violations)}")

        # Sample violations
        if len(level_violations) < n // 2:
            logger.warning(f"⚠️  Only {len(level_violations)} level {importance_level} violations available (requested {n//2})")
            sampled_violations = level_violations
        else:
            sampled_violations = level_violations.sample(n=n//2, random_state=random_seed + importance_level)

        # Sample no-violations
        if len(level_no_violations) < n // 2:
            logger.warning(f"⚠️  Only {len(level_no_violations)} level {importance_level} no-violations available (requested {n//2})")
            sampled_no_violations = level_no_violations
        else:
            sampled_no_violations = level_no_violations.sample(n=n//2, random_state=random_seed + importance_level + 100)

        # Mark ground truth and importance level
        sampled_violations = sampled_violations.copy()
        sampled_violations['ground_truth'] = 'violation'
        sampled_violations['importance_level'] = importance_level

        sampled_no_violations = sampled_no_violations.copy()
        sampled_no_violations['ground_truth'] = 'no_violation'
        sampled_no_violations['importance_level'] = importance_level

        logger.info(f"✓ Sampled {len(sampled_violations)} level {importance_level} violations")
        logger.info(f"✓ Sampled {len(sampled_no_violations)} level {importance_level} no-violations")

        all_samples.extend([sampled_violations, sampled_no_violations])

    # Combine all samples
    df_experiment = pd.concat(all_samples, ignore_index=True)

    # Shuffle
    df_experiment = df_experiment.sample(frac=1, random_state=random_seed).reset_index(drop=True)

    logger.info(f"\n📊 Total cases in experiment: {len(df_experiment)}")
    for level in [1, 2, 3, 4]:
        level_count = (df_experiment['importance_level'] == level).sum()
        logger.info(f"   Level {level}: {level_count} cases")
    logger.info(f"   Violations: {(df_experiment['ground_truth'] == 'violation').sum()}")
    logger.info(f"   No violations: {(df_experiment['ground_truth'] == 'no_violation').sum()}")

    # Step 2: Process cases (simplify, anonymize, or story mode, with caching)
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
        """Process one case (simplify, anonymize, or story mode), using cache if available."""
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
    logger.info(f"   Cache directory: {cache_dir}")

    # Step 3: Evaluate processed cases
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: EVALUATING PROCESSED CASES (PARALLEL)")
    logger.info("=" * 80)

    async def evaluate_single_case(row):
        """Evaluate one processed case."""
        item_id = row['item_id']
        case_text = row['processed_text']

        try:
            prediction = await evaluate_case(case_text, evaluation_model)
            logger.info(f"✓ {item_id} (importance: {row['importance_level']}, truth: {row['ground_truth']}): {prediction}")
            return prediction
        except Exception as e:
            logger.error(f"❌ {item_id}: {e}")
            return "error"

    logger.info(f"Evaluating {len(df_experiment)} processed cases...")
    predictions = await asyncio.gather(*[evaluate_single_case(row) for _, row in df_experiment.iterrows()])

    df_experiment['llm_prediction'] = predictions

    logger.info(f"✓ Completed evaluation of {len(df_experiment)} cases")

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

    # Step 4: Calculate statistics
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: RESULTS ANALYSIS")
    logger.info("=" * 80)

    # Overall statistics
    overall_accuracy = valid_predictions['correct'].mean()
    llm_violation_rate = valid_predictions['llm_finds_violation'].mean()

    logger.info(f"\n{'Metric':<50} {'Value':<15}")
    logger.info("-" * 70)
    logger.info(f"{'Overall accuracy':<50} {overall_accuracy:>13.1%}")
    logger.info(f"{'LLM violation detection rate (all cases)':<50} {llm_violation_rate:>13.1%}")

    # Per-importance-level comparison
    logger.info("\n" + "=" * 80)
    logger.info("IMPORTANCE LEVEL COMPARISON")
    logger.info("=" * 80)

    logger.info(f"\n{'Importance Level':<20} {'N':<8} {'LLM Says Violation':<20} {'Accuracy':<15}")
    logger.info("-" * 70)

    importance_metrics = {}
    for level in [1, 2, 3, 4]:
        subset = valid_predictions[valid_predictions['importance_level'] == level]

        if len(subset) == 0:
            continue

        count = len(subset)
        llm_viol_rate = subset['llm_finds_violation'].mean()
        accuracy = subset['correct'].mean()

        importance_metrics[level] = {
            'count': count,
            'viol_rate': llm_viol_rate,
            'accuracy': accuracy
        }

        logger.info(f"Level {level:<15} {count:<8} {llm_viol_rate:>18.1%} {accuracy:>14.1%}")

    # Per-class statistics (broken down by importance level)
    logger.info("\n" + "=" * 80)
    logger.info("DETAILED BREAKDOWN BY IMPORTANCE LEVEL AND GROUND TRUTH")
    logger.info("=" * 80)

    logger.info(f"\n{'Importance':<15} {'Ground Truth':<20} {'N':<8} {'LLM Says Violation':<20} {'Accuracy':<15}")
    logger.info("-" * 100)

    for level in [1, 2, 3, 4]:
        for truth in ['no_violation', 'violation']:
            subset = valid_predictions[
                (valid_predictions['importance_level'] == level) &
                (valid_predictions['ground_truth'] == truth)
            ]

            if len(subset) == 0:
                continue

            count = len(subset)
            llm_viol_rate = subset['llm_finds_violation'].mean()
            accuracy = subset['correct'].mean()

            logger.info(f"Level {level:<10} {truth:<20} {count:<8} {llm_viol_rate:>18.1%} {accuracy:>14.1%}")

    # Additional insights
    logger.info("\n" + "=" * 80)
    logger.info("INSIGHTS")
    logger.info("=" * 80)

    # Overall confusion matrix
    tp = ((valid_predictions['ground_truth'] == 'violation') & (valid_predictions['llm_prediction'] == 'violation')).sum()
    tn = ((valid_predictions['ground_truth'] == 'no_violation') & (valid_predictions['llm_prediction'] == 'no_violation')).sum()
    fp = ((valid_predictions['ground_truth'] == 'no_violation') & (valid_predictions['llm_prediction'] == 'violation')).sum()
    fn = ((valid_predictions['ground_truth'] == 'violation') & (valid_predictions['llm_prediction'] == 'no_violation')).sum()

    logger.info(f"\nOVERALL Confusion Matrix:")
    logger.info(f"  True Positives (correctly found violation): {tp}")
    logger.info(f"  True Negatives (correctly found no violation): {tn}")
    logger.info(f"  False Positives (incorrectly found violation): {fp}")
    logger.info(f"  False Negatives (missed violation): {fn}")

    # Precision, Recall, F1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    logger.info(f"\nOverall Metrics:")
    logger.info(f"  Precision: {precision:.1%}")
    logger.info(f"  Recall: {recall:.1%}")
    logger.info(f"  F1 Score: {f1:.1%}")

    # Bias check (overall)
    if fp > fn * 2:
        logger.info(f"\n⚠️  STRONG VIOLATION BIAS DETECTED (overall)!")
        logger.info(f"    Model has {fp} false positives vs {fn} false negatives")
    elif fn > fp * 2:
        logger.info(f"\n⚠️  STRONG NO-VIOLATION BIAS DETECTED (overall)!")
        logger.info(f"    Model has {fn} false negatives vs {fp} false positives")

    # Confusion matrix by importance level
    logger.info("\n" + "-" * 80)
    logger.info("CONFUSION MATRICES BY IMPORTANCE LEVEL")
    logger.info("-" * 80)

    for level in [1, 2, 3, 4]:
        subset = valid_predictions[valid_predictions['importance_level'] == level]

        tp_subset = ((subset['ground_truth'] == 'violation') & (subset['llm_prediction'] == 'violation')).sum()
        tn_subset = ((subset['ground_truth'] == 'no_violation') & (subset['llm_prediction'] == 'no_violation')).sum()
        fp_subset = ((subset['ground_truth'] == 'no_violation') & (subset['llm_prediction'] == 'violation')).sum()
        fn_subset = ((subset['ground_truth'] == 'violation') & (subset['llm_prediction'] == 'no_violation')).sum()

        precision_subset = tp_subset / (tp_subset + fp_subset) if (tp_subset + fp_subset) > 0 else 0
        recall_subset = tp_subset / (tp_subset + fn_subset) if (tp_subset + fn_subset) > 0 else 0
        f1_subset = 2 * (precision_subset * recall_subset) / (precision_subset + recall_subset) if (precision_subset + recall_subset) > 0 else 0

        logger.info(f"\nLEVEL {level} Confusion Matrix:")
        logger.info(f"  True Positives: {tp_subset}, True Negatives: {tn_subset}")
        logger.info(f"  False Positives: {fp_subset}, False Negatives: {fn_subset}")
        logger.info(f"  Precision: {precision_subset:.1%}, Recall: {recall_subset:.1%}, F1: {f1_subset:.1%}")

        # Bias check per importance level
        if fp_subset > fn_subset * 2:
            logger.info(f"  ⚠️  Violation bias in Level {level} cases (FP={fp_subset}, FN={fn_subset})")
        elif fn_subset > fp_subset * 2:
            logger.info(f"  ⚠️  No-violation bias in Level {level} cases (FP={fp_subset}, FN={fn_subset})")

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

    # Save detailed results
    results_file = output_dir / f"importance_{mode_str}_{eval_model_name}_n{n}.csv"
    df_experiment.to_csv(results_file, index=False)
    logger.info(f"📊 Detailed results: {results_file}")

    # Save summary statistics
    if anonymize_only:
        mode_value = 'anonymize_only'
    elif story_mode:
        mode_value = 'story_mode'
    else:
        mode_value = 'summarize'

    summary = {
        'n': n,
        'mode': mode_value,
        'word_range': f"{word_range[0]}-{word_range[1]}" if not anonymize_only else 'N/A',
        'evaluation_model': evaluation_model,
        'overall_accuracy': overall_accuracy,
        'llm_violation_rate': llm_violation_rate,
        'level_1_accuracy': importance_metrics.get(1, {}).get('accuracy', 0),
        'level_2_accuracy': importance_metrics.get(2, {}).get('accuracy', 0),
        'level_3_accuracy': importance_metrics.get(3, {}).get('accuracy', 0),
        'level_4_accuracy': importance_metrics.get(4, {}).get('accuracy', 0),
        'level_1_viol_rate': importance_metrics.get(1, {}).get('viol_rate', 0),
        'level_2_viol_rate': importance_metrics.get(2, {}).get('viol_rate', 0),
        'level_3_viol_rate': importance_metrics.get(3, {}).get('viol_rate', 0),
        'level_4_viol_rate': importance_metrics.get(4, {}).get('viol_rate', 0),
        'true_positives': tp,
        'true_negatives': tn,
        'false_positives': fp,
        'false_negatives': fn,
        'precision': precision,
        'recall': recall,
        'f1': f1,
    }

    summary_file = output_dir / f"importance_summary_{mode_str}_{eval_model_name}_n{n}.csv"
    pd.DataFrame([summary]).to_csv(summary_file, index=False)
    logger.info(f"📈 Summary statistics: {summary_file}")

    logger.info("\n" + "=" * 80)
    logger.info("✓ EXPERIMENT COMPLETE")
    logger.info("=" * 80)

    return df_experiment, summary


def main():
    parser = argparse.ArgumentParser(
        description="Run importance level experiment to compare LLM performance across case significance levels (1-4)"
    )
    parser.add_argument(
        "-n",
        type=int,
        required=True,
        help="Number of cases to sample per importance level (4 levels × N cases each, with N/2 violations + N/2 no-violations per level, total 4N cases)"
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
        help="Use story-based narrative format instead of legal summarization"
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
        run_importance_experiment(
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
