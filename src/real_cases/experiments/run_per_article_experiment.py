"""
Per-Article Experiment

This script evaluates LLM performance on detecting violations for each specific ECHR article.

For a given sample size N and target articles (9, 14, p1-1):
1. For EACH article type:
   - Sample N cases where that article was violated
   - Sample N cases where that article was NOT violated
2. Evaluate LLM on all cases
3. Output results showing performance per article (accuracy, bias, false positive rate)
4. Supports --pure_violations flag to test only cases where ONLY that article was violated
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

# Target violation types for focused analysis
VIOLATION_TYPES = ['9', '14', 'p1-1']


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


async def story_case(case_text: str, model_id: str, word_range: tuple = (150, 200), temperature: float = 0.3) -> str:
    """Convert case to story format."""
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


async def run_per_violation_experiment(
    n: int,
    evaluation_model: str = DEFAULT_JUDGE_MODEL,
    simplification_model: str = DEFAULT_SIMPLIFICATION_MODEL,
    word_range: tuple = (150, 200),
    anonymize_only: bool = False,
    story_mode: bool = False,
    pure_violations: bool = False,
    data_dir: str = None,
    output_dir: str = None,
    random_seed: int = 42,
):
    """Run per-violation-type experiment.

    Args:
        n: Sample size per group
        evaluation_model: Model for evaluation
        simplification_model: Model for processing
        word_range: Word range for summaries
        anonymize_only: If True, only anonymize (no summarization)
        story_mode: If True, use story-based summarization
        pure_violations: If True, only cases with ONLY that violation. If False, any case with that violation.
        data_dir: Data directory
        output_dir: Output directory
        random_seed: Random seed
    """

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
        mode = "LEGAL SUMMARIZATION"

    logger.info("=" * 80)
    logger.info(f"PER-VIOLATION-TYPE EXPERIMENT ({mode})")
    logger.info("=" * 80)
    logger.info(f"Target articles: {', '.join(VIOLATION_TYPES)}")
    logger.info(f"Sample size per group: N={n}")
    logger.info(f"Violation filtering: {'PURE (only that violation)' if pure_violations else 'ANY (may have other violations)'}")
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

    # NEW SAMPLING STRATEGY: For each article, sample N violations + N no-violations
    all_samples = []

    for vtype in VIOLATION_TYPES:
        col_name = f'violated_{vtype}'

        logger.info(f"\n--- Sampling for Article {vtype} ---")

        # Sample N cases where this violation occurred
        if pure_violations:
            # Option B: Only cases where ONLY this article was violated
            violated_cases = df[(df[col_name] == 1) & (df['violations'] == vtype)]
            filter_desc = "pure (only this violation)"
        else:
            # Option A: Any case where this article was violated (may have other violations too)
            violated_cases = df[df[col_name] == 1]
            filter_desc = "any (may have other violations)"

        if len(violated_cases) < n:
            logger.warning(f"⚠️  Article {vtype} violations ({filter_desc}): Only {len(violated_cases)} cases available (requested {n})")
            sampled_violated = violated_cases
        else:
            sampled_violated = violated_cases.sample(n=n, random_state=random_seed + int(vtype) if vtype.isdigit() else random_seed)

        sampled_violated = sampled_violated.copy()
        sampled_violated['violation_type'] = f'{vtype}_violation'
        sampled_violated['target_article'] = vtype
        all_samples.append(sampled_violated)
        logger.info(f"✓ Sampled {len(sampled_violated)} violation cases for Article {vtype}")

        # Sample N cases with NO violations at all
        no_violation_cases = df[df['violation_label'] == 'no_violation']

        if len(no_violation_cases) < n:
            logger.warning(f"⚠️  No-violation cases: Only {len(no_violation_cases)} available (requested {n})")
            sampled_no_violations = no_violation_cases
        else:
            sampled_no_violations = no_violation_cases.sample(n=n, random_state=random_seed + 100 + int(vtype) if vtype.isdigit() else random_seed + 100)

        sampled_no_violations = sampled_no_violations.copy()
        sampled_no_violations['violation_type'] = f'{vtype}_no_violation'
        sampled_no_violations['target_article'] = vtype
        all_samples.append(sampled_no_violations)
        logger.info(f"✓ Sampled {len(sampled_no_violations)} no-violation cases for Article {vtype}")

    # Combine all samples
    df_experiment = pd.concat(all_samples, ignore_index=True)

    logger.info(f"\n📊 Total cases in experiment: {len(df_experiment)}")
    logger.info(f"   Breakdown by article:")
    for vtype in VIOLATION_TYPES:
        viol_count = (df_experiment['violation_type'] == f'{vtype}_violation').sum()
        no_viol_count = (df_experiment['violation_type'] == f'{vtype}_no_violation').sum()
        logger.info(f"      Article {vtype}: {viol_count} violations + {no_viol_count} no-violations = {viol_count + no_viol_count} total")

    # Step 2: Process cases (story, simplify, or anonymize, with caching)
    if anonymize_only:
        step_name = "ANONYMIZING"
    elif story_mode:
        step_name = "STORY MODE"
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
        """Process one case (simplify or anonymize), using cache if available."""
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
                action = "story"
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
            logger.info(f"✓ {item_id} (type: {row['violation_type']}): {prediction}")
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

    # Step 4: Calculate statistics
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: RESULTS ANALYSIS")
    logger.info("=" * 80)

    # Overall statistics
    total_violation_rate = valid_predictions['llm_finds_violation'].mean()
    logger.info(f"\nOverall LLM violation detection rate: {total_violation_rate:.1%}")

    # Statistics per article (separate for violations vs no-violations)
    logger.info(f"\n{'Article':<12} {'Type':<15} {'N':<8} {'LLM Says Violation':<20} {'Accuracy':<15}")
    logger.info("-" * 75)

    stats_rows = []

    for vtype in VIOLATION_TYPES:
        # Violation cases for this article
        subset_viol = df_experiment[df_experiment['violation_type'] == f'{vtype}_violation']
        if len(subset_viol) > 0:
            count = len(subset_viol)
            llm_violation_rate = subset_viol['llm_finds_violation'].mean()
            accuracy = (subset_viol['llm_prediction'] == 'violation').mean()

            logger.info(f"{vtype:<12} {'Violation':<15} {count:<8} {llm_violation_rate:>18.1%} {accuracy:>14.1%}")

            stats_rows.append({
                'article': vtype,
                'type': 'violation',
                'n_cases': count,
                'llm_violation_rate': llm_violation_rate,
                'accuracy': accuracy,
            })

        # No-violation cases for this article
        subset_no_viol = df_experiment[df_experiment['violation_type'] == f'{vtype}_no_violation']
        if len(subset_no_viol) > 0:
            count = len(subset_no_viol)
            llm_violation_rate = subset_no_viol['llm_finds_violation'].mean()
            accuracy = (subset_no_viol['llm_prediction'] == 'no_violation').mean()

            logger.info(f"{vtype:<12} {'No-violation':<15} {count:<8} {llm_violation_rate:>18.1%} {accuracy:>14.1%}")

            stats_rows.append({
                'article': vtype,
                'type': 'no_violation',
                'n_cases': count,
                'llm_violation_rate': llm_violation_rate,
                'accuracy': accuracy,
            })

    stats_df = pd.DataFrame(stats_rows)

    # Additional insights
    logger.info("\n" + "=" * 80)
    logger.info("INSIGHTS")
    logger.info("=" * 80)

    # Best and worst performing articles (on violations)
    violation_stats = stats_df[stats_df['type'] == 'violation'].copy()
    if len(violation_stats) > 0:
        best_article = violation_stats.loc[violation_stats['accuracy'].idxmax()]
        worst_article = violation_stats.loc[violation_stats['accuracy'].idxmin()]

        logger.info(f"\n🏆 Best detected violation: Article {best_article['article']} ({best_article['accuracy']:.1%} accuracy)")
        logger.info(f"📉 Worst detected violation: Article {worst_article['article']} ({worst_article['accuracy']:.1%} accuracy)")

    # No-violation accuracy across articles
    no_viol_stats = stats_df[stats_df['type'] == 'no_violation'].copy()
    if len(no_viol_stats) > 0:
        avg_no_viol_acc = no_viol_stats['accuracy'].mean()
        logger.info(f"\n✓ Average no-violation detection accuracy: {avg_no_viol_acc:.1%}")

        best_no_viol = no_viol_stats.loc[no_viol_stats['accuracy'].idxmax()]
        worst_no_viol = no_viol_stats.loc[no_viol_stats['accuracy'].idxmin()]
        logger.info(f"  Best: Article {best_no_viol['article']} ({best_no_viol['accuracy']:.1%})")
        logger.info(f"  Worst: Article {worst_no_viol['article']} ({worst_no_viol['accuracy']:.1%})")

        if avg_no_viol_acc < 0.5:
            logger.info("  ⚠️  Model has a strong bias toward finding violations even when none exist!")

    # Save results
    logger.info("\n" + "=" * 80)
    logger.info("SAVING RESULTS")
    logger.info("=" * 80)

    eval_model_name = evaluation_model.replace('/', '-')

    # Save detailed results
    results_file = output_dir / f"per_violation_{eval_model_name}_n{n}.csv"
    df_experiment.to_csv(results_file, index=False)
    logger.info(f"📊 Detailed results: {results_file}")

    # Save summary statistics
    summary_file = output_dir / f"per_violation_summary_{eval_model_name}_n{n}.csv"
    stats_df.to_csv(summary_file, index=False)
    logger.info(f"📈 Summary statistics: {summary_file}")

    logger.info("\n" + "=" * 80)
    logger.info("✓ EXPERIMENT COMPLETE")
    logger.info("=" * 80)

    return df_experiment, stats_df


def main():
    parser = argparse.ArgumentParser(
        description="Run per-article experiment to evaluate LLM performance on specific ECHR articles (9, 14, p1-1)"
    )
    parser.add_argument(
        "-n",
        type=int,
        required=True,
        help="Number of cases to sample per violation type"
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
        help="Use story-based summarization (fictional narrative style)"
    )
    parser.add_argument(
        "--pure_violations",
        action="store_true",
        help="Only sample cases where ONLY the target article was violated (no other violations)"
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
        run_per_violation_experiment(
            n=args.n,
            evaluation_model=args.evaluation_model,
            simplification_model=args.simplification_model,
            word_range=word_range,
            anonymize_only=args.anonymize_only,
            story_mode=args.story_mode,
            pure_violations=args.pure_violations,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            random_seed=args.random_seed,
        )
    )


if __name__ == "__main__":
    main()
