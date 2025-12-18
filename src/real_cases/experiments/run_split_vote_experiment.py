"""
Split Vote Experiment

This script evaluates LLM performance on normatively uncertain cases by comparing
split-vote decisions (at least one dissenting judge) vs unanimous decisions.

For a given sample size N:
1. Sample N split-vote cases (N/2 violations, N/2 no-violations)
2. Sample N non-split-vote cases (N/2 violations, N/2 no-violations)
3. Evaluate LLM on all cases (total: 2N cases)
4. Output results comparing:
   - Accuracy on split-vote vs unanimous cases
   - Violation detection bias in each group
   - Whether LLMs show uncertainty on normatively ambiguous cases
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


async def run_split_vote_experiment(
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
    """Run split-vote experiment comparing normatively uncertain vs unanimous cases."""

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
    logger.info(f"SPLIT-VOTE EXPERIMENT ({mode})")
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

    # Check split_vote distribution
    split_vote_count = df['split_vote'].sum()
    non_split_vote_count = len(df) - split_vote_count
    logger.info(f"Split vote cases: {split_vote_count}")
    logger.info(f"Non-split vote cases: {non_split_vote_count}")

    # Sample N split-vote cases (N/2 violations, N/2 no-violations)
    logger.info(f"\n--- Sampling {n} split-vote cases ({n//2} violations + {n//2} no-violations) ---")

    split_vote_df = df[df['split_vote'] == True]
    split_vote_violations = split_vote_df[split_vote_df['violation_label'] == 'violation']
    split_vote_no_violations = split_vote_df[split_vote_df['violation_label'] == 'no_violation']

    logger.info(f"Available split-vote violations: {len(split_vote_violations)}")
    logger.info(f"Available split-vote no-violations: {len(split_vote_no_violations)}")

    # Sample split-vote violations
    if len(split_vote_violations) < n // 2:
        logger.warning(f"⚠️  Only {len(split_vote_violations)} split-vote violations available (requested {n//2})")
        sampled_split_violations = split_vote_violations
    else:
        sampled_split_violations = split_vote_violations.sample(n=n//2, random_state=random_seed)

    # Sample split-vote no-violations
    if len(split_vote_no_violations) < n // 2:
        logger.warning(f"⚠️  Only {len(split_vote_no_violations)} split-vote no-violations available (requested {n//2})")
        sampled_split_no_violations = split_vote_no_violations
    else:
        sampled_split_no_violations = split_vote_no_violations.sample(n=n//2, random_state=random_seed)

    sampled_split_violations = sampled_split_violations.copy()
    sampled_split_violations['ground_truth'] = 'violation'
    sampled_split_violations['vote_type'] = 'split_vote'

    sampled_split_no_violations = sampled_split_no_violations.copy()
    sampled_split_no_violations['ground_truth'] = 'no_violation'
    sampled_split_no_violations['vote_type'] = 'split_vote'

    logger.info(f"✓ Sampled {len(sampled_split_violations)} split-vote violations")
    logger.info(f"✓ Sampled {len(sampled_split_no_violations)} split-vote no-violations")

    # Sample N non-split-vote cases (N/2 violations, N/2 no-violations)
    logger.info(f"\n--- Sampling {n} non-split-vote cases ({n//2} violations + {n//2} no-violations) ---")

    non_split_vote_df = df[df['split_vote'] == False]
    non_split_violations = non_split_vote_df[non_split_vote_df['violation_label'] == 'violation']
    non_split_no_violations = non_split_vote_df[non_split_vote_df['violation_label'] == 'no_violation']

    logger.info(f"Available non-split-vote violations: {len(non_split_violations)}")
    logger.info(f"Available non-split-vote no-violations: {len(non_split_no_violations)}")

    # Sample non-split-vote violations
    if len(non_split_violations) < n // 2:
        logger.warning(f"⚠️  Only {len(non_split_violations)} non-split-vote violations available (requested {n//2})")
        sampled_non_split_violations = non_split_violations
    else:
        sampled_non_split_violations = non_split_violations.sample(n=n//2, random_state=random_seed)

    # Sample non-split-vote no-violations
    if len(non_split_no_violations) < n // 2:
        logger.warning(f"⚠️  Only {len(non_split_no_violations)} non-split-vote no-violations available (requested {n//2})")
        sampled_non_split_no_violations = non_split_no_violations
    else:
        sampled_non_split_no_violations = non_split_no_violations.sample(n=n//2, random_state=random_seed)

    sampled_non_split_violations = sampled_non_split_violations.copy()
    sampled_non_split_violations['ground_truth'] = 'violation'
    sampled_non_split_violations['vote_type'] = 'non_split_vote'

    sampled_non_split_no_violations = sampled_non_split_no_violations.copy()
    sampled_non_split_no_violations['ground_truth'] = 'no_violation'
    sampled_non_split_no_violations['vote_type'] = 'non_split_vote'

    logger.info(f"✓ Sampled {len(sampled_non_split_violations)} non-split-vote violations")
    logger.info(f"✓ Sampled {len(sampled_non_split_no_violations)} non-split-vote no-violations")

    # Combine all samples
    df_experiment = pd.concat([
        sampled_split_violations,
        sampled_split_no_violations,
        sampled_non_split_violations,
        sampled_non_split_no_violations
    ], ignore_index=True)

    # Shuffle
    df_experiment = df_experiment.sample(frac=1, random_state=random_seed).reset_index(drop=True)

    logger.info(f"\n📊 Total cases in experiment: {len(df_experiment)}")
    logger.info(f"   Split-vote: {(df_experiment['vote_type'] == 'split_vote').sum()}")
    logger.info(f"   Non-split-vote: {(df_experiment['vote_type'] == 'non_split_vote').sum()}")
    logger.info(f"   Violations: {(valid_predictions['ground_truth'] == 'violation').sum()}")
    logger.info(f"   No violations: {(valid_predictions['ground_truth'] == 'no_violation').sum()}")

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
            logger.info(f"✓ {item_id} (truth: {row['ground_truth']}): {prediction}")
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

    # Split-vote vs Non-split-vote comparison
    logger.info("\n" + "=" * 80)
    logger.info("SPLIT-VOTE vs NON-SPLIT-VOTE COMPARISON")
    logger.info("=" * 80)

    logger.info(f"\n{'Vote Type':<20} {'N':<8} {'LLM Says Violation':<20} {'Accuracy':<15}")
    logger.info("-" * 70)

    for vote_type in ['split_vote', 'non_split_vote']:
        subset = df_experiment[df_experiment['vote_type'] == vote_type]

        if len(subset) == 0:
            continue

        count = len(subset)
        llm_viol_rate = subset['llm_finds_violation'].mean()
        accuracy = subset['correct'].mean()

        vote_label = "Split-vote" if vote_type == 'split_vote' else "Non-split-vote"
        logger.info(f"{vote_label:<20} {count:<8} {llm_viol_rate:>18.1%} {accuracy:>14.1%}")

    # Per-class statistics (broken down by vote type)
    logger.info("\n" + "=" * 80)
    logger.info("DETAILED BREAKDOWN BY VOTE TYPE AND GROUND TRUTH")
    logger.info("=" * 80)

    logger.info(f"\n{'Vote Type':<20} {'Ground Truth':<20} {'N':<8} {'LLM Says Violation':<20} {'Accuracy':<15}")
    logger.info("-" * 100)

    for vote_type in ['split_vote', 'non_split_vote']:
        for truth in ['no_violation', 'violation']:
            subset = df_experiment[
                (df_experiment['vote_type'] == vote_type) &
                (valid_predictions['ground_truth'] == truth)
            ]

            if len(subset) == 0:
                continue

            count = len(subset)
            llm_viol_rate = subset['llm_finds_violation'].mean()
            accuracy = subset['correct'].mean()

            vote_label = "Split-vote" if vote_type == 'split_vote' else "Non-split-vote"
            logger.info(f"{vote_label:<20} {truth:<20} {count:<8} {llm_viol_rate:>18.1%} {accuracy:>14.1%}")

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

    # Confusion matrix by vote type
    logger.info("\n" + "-" * 80)
    logger.info("CONFUSION MATRICES BY VOTE TYPE")
    logger.info("-" * 80)

    for vote_type in ['split_vote', 'non_split_vote']:
        subset = df_experiment[df_experiment['vote_type'] == vote_type]

        tp_subset = ((subset['ground_truth'] == 'violation') & (subset['llm_prediction'] == 'violation')).sum()
        tn_subset = ((subset['ground_truth'] == 'no_violation') & (subset['llm_prediction'] == 'no_violation')).sum()
        fp_subset = ((subset['ground_truth'] == 'no_violation') & (subset['llm_prediction'] == 'violation')).sum()
        fn_subset = ((subset['ground_truth'] == 'violation') & (subset['llm_prediction'] == 'no_violation')).sum()

        precision_subset = tp_subset / (tp_subset + fp_subset) if (tp_subset + fp_subset) > 0 else 0
        recall_subset = tp_subset / (tp_subset + fn_subset) if (tp_subset + fn_subset) > 0 else 0
        f1_subset = 2 * (precision_subset * recall_subset) / (precision_subset + recall_subset) if (precision_subset + recall_subset) > 0 else 0

        vote_label = "SPLIT-VOTE" if vote_type == 'split_vote' else "NON-SPLIT-VOTE"
        logger.info(f"\n{vote_label} Confusion Matrix:")
        logger.info(f"  True Positives: {tp_subset}, True Negatives: {tn_subset}")
        logger.info(f"  False Positives: {fp_subset}, False Negatives: {fn_subset}")
        logger.info(f"  Precision: {precision_subset:.1%}, Recall: {recall_subset:.1%}, F1: {f1_subset:.1%}")

        # Bias check per vote type
        if fp_subset > fn_subset * 2:
            logger.info(f"  ⚠️  Violation bias in {vote_label} cases (FP={fp_subset}, FN={fn_subset})")
        elif fn_subset > fp_subset * 2:
            logger.info(f"  ⚠️  No-violation bias in {vote_label} cases (FP={fp_subset}, FN={fn_subset})")

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
    results_file = output_dir / f"simple_{mode_str}_{eval_model_name}_n{n}.csv"
    df_experiment.to_csv(results_file, index=False)
    logger.info(f"📊 Detailed results: {results_file}")

    # Calculate split-vote specific metrics for summary
    split_vote_subset = df_experiment[df_experiment['vote_type'] == 'split_vote']
    non_split_vote_subset = df_experiment[df_experiment['vote_type'] == 'non_split_vote']

    split_vote_accuracy = split_vote_subset['correct'].mean() if len(split_vote_subset) > 0 else 0
    non_split_vote_accuracy = non_split_vote_subset['correct'].mean() if len(non_split_vote_subset) > 0 else 0

    split_vote_viol_rate = split_vote_subset['llm_finds_violation'].mean() if len(split_vote_subset) > 0 else 0
    non_split_vote_viol_rate = non_split_vote_subset['llm_finds_violation'].mean() if len(non_split_vote_subset) > 0 else 0

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
        'split_vote_accuracy': split_vote_accuracy,
        'non_split_vote_accuracy': non_split_vote_accuracy,
        'split_vote_viol_rate': split_vote_viol_rate,
        'non_split_vote_viol_rate': non_split_vote_viol_rate,
        'true_positives': tp,
        'true_negatives': tn,
        'false_positives': fp,
        'false_negatives': fn,
        'precision': precision,
        'recall': recall,
        'f1': f1,
    }

    summary_file = output_dir / f"simple_summary_{mode_str}_{eval_model_name}_n{n}.csv"
    pd.DataFrame([summary]).to_csv(summary_file, index=False)
    logger.info(f"📈 Summary statistics: {summary_file}")

    logger.info("\n" + "=" * 80)
    logger.info("✓ EXPERIMENT COMPLETE")
    logger.info("=" * 80)

    return df_experiment, summary


def main():
    parser = argparse.ArgumentParser(
        description="Run split-vote experiment to compare LLM performance on normatively uncertain vs unanimous cases"
    )
    parser.add_argument(
        "-n",
        type=int,
        required=True,
        help="Number of cases to sample per vote type (N split-vote + N non-split-vote, each with N/2 violations + N/2 no-violations, total 2N cases)"
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
        run_split_vote_experiment(
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
