#!/usr/bin/env python3
"""
Per-Article Violation Detection Experiment

This experiment evaluates whether the model can correctly identify violations
of SPECIFIC articles (e.g., "Was Article 3: Prohibition of torture violated?")
rather than just asking if ANY violation occurred.

For each case, we create separate evaluations for each article the applicant claimed
was violated, comparing the model's prediction against the court's actual finding
for that specific article.
"""

import asyncio
import logging
import random
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd
import argparse
from inspect_ai.model import GenerateConfig

from src.client import LLMClient
from src.real_cases.config import DEFAULT_JUDGE_MODEL, DEFAULT_SIMPLIFICATION_MODEL, get_cache_dir_name
from src.real_cases.anonymization_utils import (
    verify_anonymization,
    anonymize_case_with_verification,
    summarize_case_with_verification
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Article mapping with full names
ARTICLE_NAMES = {
    '1': 'Obligation to respect human rights',
    '2': 'Right to life',
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
    'P1-1': 'Protection of property',
    'P1-2': 'Right to education',
    'P1-3': 'Right to free elections',
    'P4-2': 'Freedom of movement',
    'P4-3': 'Prohibition of expulsion of nationals',
    'P4-4': 'Prohibition of collective expulsion of aliens',
}


async def summarize_case(
    case_text: str,
    model_id: str,
    word_count: int = 200,
    temperature: float = 0.3,
    cache_path: Path = None,
    verification_model_id: str = "openai/gpt-4o"
) -> str:
    """
    Summarize and anonymize a case with verification.

    Checks cache first, verifies cached content, generates if needed.
    """
    # Check cache first
    if cache_path and cache_path.exists():
        logger.info(f"    Using cached summary, verifying...")
        cached_text = cache_path.read_text(encoding='utf-8')

        # Verify cached file
        is_valid, corrected = await verify_anonymization(
            text=cached_text,
            is_summary=True,
            word_count=word_count,
            model_id=verification_model_id
        )

        if not is_valid:
            logger.warning(f"    Cached file failed verification, updating cache")
            cache_path.write_text(corrected, encoding='utf-8')
            return corrected

        return cached_text

    # Generate new summary with verification
    logger.info(f"    Generating new summary...")
    summarized = await summarize_case_with_verification(
        case_text=case_text,
        model_id=model_id,
        word_count=word_count,
        verification_model_id=verification_model_id,
        temperature=temperature
    )

    # Cache the verified result
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(summarized, encoding='utf-8')

    return summarized


async def anonymize_case(
    case_text: str,
    model_id: str,
    temperature: float = 0.3,
    cache_path: Path = None,
    verification_model_id: str = "openai/gpt-4o"
) -> str:
    """
    Anonymize a case without summarizing (keep full length) with verification.

    Checks cache first, verifies cached content, generates if needed.
    """
    # Check cache first
    if cache_path and cache_path.exists():
        logger.info(f"    Using cached anonymization, verifying...")
        cached_text = cache_path.read_text(encoding='utf-8')

        # Verify cached file
        is_valid, corrected = await verify_anonymization(
            text=cached_text,
            is_summary=False,
            model_id=verification_model_id
        )

        if not is_valid:
            logger.warning(f"    Cached file failed verification, updating cache")
            cache_path.write_text(corrected, encoding='utf-8')
            return corrected

        return cached_text

    # Generate new anonymization with verification
    logger.info(f"    Generating new anonymization...")
    anonymized = await anonymize_case_with_verification(
        case_text=case_text,
        model_id=model_id,
        verification_model_id=verification_model_id,
        temperature=temperature
    )

    # Cache the verified result
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(anonymized, encoding='utf-8')

    return anonymized


async def evaluate_article_violation(
    case_text: str,
    article: str,
    article_name: str,
    model_id: str,
    temperature: float = 0.0
) -> str:
    """
    Evaluate whether a specific article was violated in the case.

    Args:
        case_text: The case facts/description
        article: Article number (e.g., "3", "8", "P1-1")
        article_name: Full article name (e.g., "Prohibition of torture")
        model_id: LLM model identifier
        temperature: Sampling temperature

    Returns:
        'YES', 'NO', or None if unparseable
    """
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=temperature, max_tokens=20)
    )

    system_prompt = """You are an expert legal evaluator for the European Court of Human Rights. Answer questions about specific article violations based on case facts."""

    prompt = f"""Based on the case facts below, answer this question:

Was Article {article}: {article_name} violated in this case?

Answer with ONLY "YES" or "NO", nothing else.

Case facts:
{case_text}

Answer (YES or NO):"""

    try:
        response = await client.generate(
            prompt=prompt,
            system_message=system_prompt
        )

        # Parse response
        response_clean = response.strip().upper()

        # Check for NO first (important for Chinese: 不是 contains both 不 and 是)
        if 'NO' in response_clean:
            return 'NO'
        elif 'YES' in response_clean:
            return 'YES'

        logger.warning(f"Unexpected response for Article {article}: {response}")
        return None

    except Exception as e:
        logger.error(f"Error evaluating Article {article}: {e}")
        return None


def parse_articles(articles_str) -> List[str]:
    """
    Parse the articles string from the CSV into a list of article numbers.

    Handles formats like:
    - "3" -> ["3"]
    - "3+8" -> ["3", "8"]
    - "3, 8, 10" -> ["3", "8", "10"]
    - "[3, 8]" -> ["3", "8"]
    """
    if pd.isna(articles_str):
        return []

    # Convert to string and clean
    articles_str = str(articles_str).strip()

    # Remove brackets if present
    articles_str = articles_str.replace('[', '').replace(']', '')

    # Split by common delimiters
    if '+' in articles_str:
        parts = articles_str.split('+')
    elif ',' in articles_str:
        parts = articles_str.split(',')
    else:
        parts = [articles_str]

    # Clean and filter
    articles = []
    for part in parts:
        part = part.strip()
        if part and part in ARTICLE_NAMES:
            articles.append(part)

    return articles


def get_article_ground_truth(row: pd.Series, article: str) -> int:
    """
    Get the ground truth for a specific article from the dataframe row.

    Args:
        row: DataFrame row with violated_X columns
        article: Article number (e.g., "3", "8", "P1-1")

    Returns:
        1 if violated, 0 if not violated
    """
    col_name = f'violated_{article}'
    if col_name in row.index:
        return int(row[col_name])
    return 0


async def run_per_article_experiment(
    n: int,
    data_dir: Path,
    simplification_model: str,
    judge_model: str,
    random_seed: int = 42,
    mode: str = 'anonymize_only',
    word_count: int = 200
) -> None:
    """
    Run per-article violation detection experiment.

    For each case:
    1. Extract the articles claimed by applicant
    2. For each claimed article, ask: "Was Article X: [name] violated?"
    3. Compare prediction against actual violation for that specific article
    """
    random.seed(random_seed)

    logger.info("=" * 80)
    logger.info("PER-ARTICLE VIOLATION DETECTION EXPERIMENT")
    logger.info("=" * 80)
    logger.info(f"Sample size: {n} cases")
    logger.info(f"Simplification model: {simplification_model}")
    logger.info(f"Judge model: {judge_model}")
    logger.info(f"Random seed: {random_seed}")
    logger.info(f"Mode: {mode}")
    logger.info("")

    # ========================================
    # STEP 1: LOAD AND SAMPLE CASES
    # ========================================
    logger.info("=" * 80)
    logger.info("STEP 1: LOAD AND SAMPLE CASES")
    logger.info("=" * 80)

    # Load cases
    cases_file = data_dir / 'unanimous' / 'cases.csv'
    df = pd.read_csv(cases_file)

    logger.info(f"Total cases in dataset: {len(df)}")

    # Sample cases with balanced violation/no-violation
    violation_cases = df[df['violation_label'] == 'violation']
    no_violation_cases = df[df['violation_label'] == 'no_violation']

    n_per_class = n // 2

    sampled_violation = violation_cases.sample(n=min(n_per_class, len(violation_cases)), random_state=random_seed)
    sampled_no_violation = no_violation_cases.sample(n=min(n_per_class, len(no_violation_cases)), random_state=random_seed)

    sampled_cases = pd.concat([sampled_violation, sampled_no_violation], ignore_index=True)

    logger.info(f"Sampled {len(sampled_cases)} cases:")
    logger.info(f"  Violations: {len(sampled_violation)}")
    logger.info(f"  No violations: {len(sampled_no_violation)}")

    # ========================================
    # STEP 2: PROCESS CASES (ANONYMIZE OR SUMMARIZE)
    # ========================================
    logger.info("\n" + "=" * 80)
    if mode == 'summarize':
        logger.info(f"STEP 2: SUMMARIZE AND ANONYMIZE CASES ({word_count} words)")
        cache_suffix = f'_summarize_{word_count}'
    else:
        logger.info("STEP 2: ANONYMIZE CASES (FULL LENGTH)")
        cache_suffix = '_anonymize_only'
    logger.info("=" * 80)

    # Check cache directory
    cache_dir_name = f'anonymized_full_{simplification_model.replace("/", "-")}'
    cache_dir = data_dir / cache_dir_name
    cache_dir.mkdir(exist_ok=True, parents=True)

    processed_texts = []
    for idx, row in sampled_cases.iterrows():
        item_id = row['item_id']
        cache_file = cache_dir / f'{item_id}_english{cache_suffix}.txt'

        logger.info(f"  {item_id}: Processing (with verification)...")

        if mode == 'summarize':
            processed_text = await summarize_case(
                case_text=row['full_case_text'],
                model_id=simplification_model,
                word_count=word_count,
                cache_path=cache_file
            )
        else:
            processed_text = await anonymize_case(
                case_text=row['full_case_text'],
                model_id=simplification_model,
                cache_path=cache_file
            )

        processed_texts.append(processed_text)

    sampled_cases['processed_text'] = processed_texts

    # ========================================
    # STEP 3: EXPAND TO ARTICLE-LEVEL EVALUATIONS
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: EXPAND CASES TO ARTICLE-LEVEL EVALUATIONS")
    logger.info("=" * 80)

    # Create one row per case-article pair
    article_evaluations = []

    for idx, row in sampled_cases.iterrows():
        claimed_articles = parse_articles(row['articles'])

        if not claimed_articles:
            logger.warning(f"  {row['item_id']}: No articles found, skipping")
            continue

        logger.info(f"  {row['item_id']}: {len(claimed_articles)} articles claimed: {', '.join(claimed_articles)}")

        for article in claimed_articles:
            article_name = ARTICLE_NAMES.get(article, f"Article {article}")
            actual_violated = get_article_ground_truth(row, article)

            article_evaluations.append({
                'item_id': row['item_id'],
                'case_name': row['case_name'],
                'article': article,
                'article_name': article_name,
                'processed_text': row['processed_text'],
                'actual_violated': actual_violated,
                'overall_violation_label': row['violation_label']
            })

    eval_df = pd.DataFrame(article_evaluations)
    logger.info(f"\nTotal article evaluations to perform: {len(eval_df)}")
    logger.info(f"  Actual violations (ground truth): {eval_df['actual_violated'].sum()}")
    logger.info(f"  Actual no-violations: {(eval_df['actual_violated'] == 0).sum()}")

    # ========================================
    # STEP 4: EVALUATE EACH ARTICLE
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: EVALUATE ARTICLE VIOLATIONS")
    logger.info("=" * 80)

    # Evaluate all article-case pairs
    eval_tasks = [
        evaluate_article_violation(
            row['processed_text'],
            row['article'],
            row['article_name'],
            judge_model
        )
        for _, row in eval_df.iterrows()
    ]

    predictions = await asyncio.gather(*eval_tasks)
    eval_df['prediction'] = predictions

    # Convert to binary (with proper index alignment)
    eval_df['prediction_binary'] = (pd.Series(predictions, index=eval_df.index) == 'YES').astype(int)

    # ========================================
    # STEP 5: ANALYZE RESULTS
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: RESULTS")
    logger.info("=" * 80)

    # Filter out unparseable predictions
    valid_evals = eval_df[eval_df['prediction'].notna()].copy()

    if len(valid_evals) < len(eval_df):
        logger.info(f"Excluded {len(eval_df) - len(valid_evals)} evaluations with unparseable predictions")

    logger.info(f"Analyzing {len(valid_evals)} valid evaluations")

    # Overall metrics
    correct = (valid_evals['prediction_binary'] == valid_evals['actual_violated']).sum()
    accuracy = correct / len(valid_evals) * 100

    # Violation detection rate
    predicted_violations = valid_evals['prediction_binary'].sum()
    violation_rate = predicted_violations / len(valid_evals) * 100

    # Actual violation rate (for comparison)
    actual_violations = valid_evals['actual_violated'].sum()
    actual_rate = actual_violations / len(valid_evals) * 100

    logger.info("\n" + "=" * 80)
    logger.info("OVERALL RESULTS")
    logger.info("=" * 80)
    logger.info(f"Total evaluations: {len(valid_evals)}")
    logger.info(f"Accuracy: {accuracy:.1f}% ({correct}/{len(valid_evals)})")
    logger.info(f"")
    logger.info(f"Model violation detection rate: {violation_rate:.1f}% ({predicted_violations}/{len(valid_evals)})")
    logger.info(f"Actual violation rate: {actual_rate:.1f}% ({actual_violations}/{len(valid_evals)})")
    logger.info(f"Difference: {violation_rate - actual_rate:+.1f} percentage points")

    # Per-article breakdown
    logger.info("\n" + "=" * 80)
    logger.info("PER-ARTICLE BREAKDOWN")
    logger.info("=" * 80)

    for article in sorted(valid_evals['article'].unique()):
        article_data = valid_evals[valid_evals['article'] == article]
        article_name = article_data.iloc[0]['article_name']

        n_evals = len(article_data)
        n_correct = (article_data['prediction_binary'] == article_data['actual_violated']).sum()
        article_accuracy = n_correct / n_evals * 100

        n_predicted_viol = article_data['prediction_binary'].sum()
        n_actual_viol = article_data['actual_violated'].sum()

        logger.info(f"\nArticle {article}: {article_name}")
        logger.info(f"  Evaluations: {n_evals}")
        logger.info(f"  Accuracy: {article_accuracy:.1f}% ({n_correct}/{n_evals})")
        logger.info(f"  Predicted violations: {n_predicted_viol}")
        logger.info(f"  Actual violations: {n_actual_viol}")

    # ========================================
    # STEP 6: SAVE RESULTS
    # ========================================
    output_dir = data_dir / 'evaluations'
    output_dir.mkdir(exist_ok=True)

    if mode == 'summarize':
        output_file = output_dir / f'per_article_violation_summarize_{word_count}_n{n}_seed{random_seed}.csv'
    else:
        output_file = output_dir / f'per_article_violation_anonymize_only_n{n}_seed{random_seed}.csv'

    eval_df.to_csv(output_file, index=False)

    logger.info(f"\n✓ Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Run per-article violation detection experiment')
    parser.add_argument('-n', type=int, required=True, help='Number of cases to sample')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--simplification_model', type=str, default='openai/gpt-4o',
                        help='Model for case simplification')
    parser.add_argument('--judge_model', type=str, default='openai/gpt-4o-mini',
                        help='Model for judging violations')
    parser.add_argument('--anonymize_only', action='store_true',
                        help='Anonymize only (full length)')
    parser.add_argument('--summarize', action='store_true',
                        help='Summarize and anonymize')
    parser.add_argument('--word_count', type=int, default=200,
                        help='Word count for summarization (default: 200)')

    args = parser.parse_args()

    # Determine mode
    if args.summarize:
        mode = 'summarize'
    else:
        mode = 'anonymize_only'

    data_dir = Path('data/real_cases/echr_new')

    asyncio.run(run_per_article_experiment(
        n=args.n,
        data_dir=data_dir,
        simplification_model=args.simplification_model,
        judge_model=args.judge_model,
        random_seed=args.seed,
        mode=mode,
        word_count=args.word_count
    ))


if __name__ == '__main__':
    main()
