#!/usr/bin/env python3
"""
Anonymize vs Summarize Comparison Experiment (Article-Specific)

This experiment compares how different text formats affect article-specific violation detection:
- Anonymize Only: Full-length anonymized cases
- Summarize: Anonymized + summarized to N words (default: 200)

For each case:
1. Process in both formats (anonymize and summarize)
2. For each article claimed, evaluate both versions with article-specific prompt
3. Compare accuracy and violation detection rates per article
"""

import asyncio
import logging
import random
from pathlib import Path
from typing import List
import pandas as pd
import argparse
from inspect_ai.model import GenerateConfig

from src.client import LLMClient
from src.real_cases.config import DEFAULT_JUDGE_MODEL, DEFAULT_SIMPLIFICATION_MODEL
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


async def evaluate_article_violation(
    case_text: str,
    article: str,
    article_name: str,
    model_id: str,
    temperature: float = 0.0
) -> str:
    """
    Evaluate whether a specific article was violated in the case.

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

        response_clean = response.strip().upper()

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
    """Parse the articles string from the CSV into a list of article numbers."""
    if pd.isna(articles_str):
        return []

    articles_str = str(articles_str).strip()
    articles_str = articles_str.replace('[', '').replace(']', '')

    if '+' in articles_str:
        parts = articles_str.split('+')
    elif ',' in articles_str:
        parts = articles_str.split(',')
    else:
        parts = [articles_str]

    articles = []
    for part in parts:
        part = part.strip()
        if part and part in ARTICLE_NAMES:
            articles.append(part)

    return articles


def get_article_ground_truth(row: pd.Series, article: str) -> int:
    """Get the ground truth for a specific article from the dataframe row."""
    col_name = f'violated_{article}'
    if col_name in row.index:
        return int(row[col_name])
    return 0


async def run_anonymize_vs_summarize_experiment(
    n: int,
    data_dir: Path,
    processing_model: str,
    judge_model: str,
    random_seed: int = 42,
    word_count: int = 200
) -> None:
    """
    Compare anonymize vs summarize formats using article-specific evaluation.
    """
    random.seed(random_seed)

    logger.info("=" * 80)
    logger.info("ANONYMIZE vs SUMMARIZE COMPARISON (Article-Specific)")
    logger.info("=" * 80)
    logger.info(f"Sample size: {n} violations + {n} no-violations = {2*n} total cases")
    logger.info(f"Processing model: {processing_model}")
    logger.info(f"Judge model: {judge_model}")
    logger.info(f"Summary word count: {word_count}")
    logger.info(f"Random seed: {random_seed}")
    logger.info("")

    # ========================================
    # STEP 1: LOAD AND SAMPLE CASES
    # ========================================
    logger.info("=" * 80)
    logger.info("STEP 1: LOAD AND SAMPLE CASES")
    logger.info("=" * 80)

    cases_file = data_dir / 'unanimous' / 'cases.csv'
    df = pd.read_csv(cases_file)

    logger.info(f"Total cases in dataset: {len(df)}")

    violation_cases = df[df['violation_label'] == 'violation']
    no_violation_cases = df[df['violation_label'] == 'no_violation']

    sampled_violation = violation_cases.sample(n=min(n, len(violation_cases)), random_state=random_seed)
    sampled_no_violation = no_violation_cases.sample(n=min(n, len(no_violation_cases)), random_state=random_seed)

    sampled_cases = pd.concat([sampled_violation, sampled_no_violation], ignore_index=True)

    logger.info(f"Sampled {len(sampled_cases)} cases:")
    logger.info(f"  Violations: {len(sampled_violation)}")
    logger.info(f"  No violations: {len(sampled_no_violation)}")

    # ========================================
    # STEP 2: PROCESS IN BOTH FORMATS
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: PROCESS CASES IN BOTH FORMATS")
    logger.info("=" * 80)

    cache_dir_name = f'anonymized_full_{processing_model.replace("/", "-")}'
    cache_dir = data_dir / cache_dir_name
    cache_dir.mkdir(exist_ok=True, parents=True)

    anonymized_texts = []
    summarized_texts = []

    for idx, row in sampled_cases.iterrows():
        item_id = row['item_id']

        # Anonymize (with verification)
        logger.info(f"  {item_id} (anonymize): Processing with verification...")
        anonymize_cache = cache_dir / f'{item_id}_english_anonymize_only.txt'
        anonymized = await anonymize_case(
            case_text=row['full_case_text'],
            model_id=processing_model,
            cache_path=anonymize_cache
        )
        anonymized_texts.append(anonymized)

        # Summarize (with verification)
        logger.info(f"  {item_id} (summarize): Processing with verification...")
        summarize_cache = cache_dir / f'{item_id}_english_summarize_{word_count}.txt'
        summarized = await summarize_case(
            case_text=row['full_case_text'],
            model_id=processing_model,
            word_count=word_count,
            cache_path=summarize_cache
        )
        summarized_texts.append(summarized)

    sampled_cases['anonymized_text'] = anonymized_texts
    sampled_cases['summarized_text'] = summarized_texts

    # ========================================
    # STEP 3: SELECT ONE RANDOM ARTICLE PER CASE
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: SELECT ONE RANDOM ARTICLE PER CASE")
    logger.info("=" * 80)

    article_evaluations = []

    for idx, row in sampled_cases.iterrows():
        claimed_articles = parse_articles(row['articles'])

        if not claimed_articles:
            logger.warning(f"  {row['item_id']}: No articles found, skipping")
            continue

        # Randomly select ONE article from the claimed articles
        selected_article = random.choice(claimed_articles)
        article_name = ARTICLE_NAMES.get(selected_article, f"Article {selected_article}")
        actual_violated = get_article_ground_truth(row, selected_article)

        logger.info(f"  {row['item_id']}: Selected Article {selected_article} from {len(claimed_articles)} claimed: {', '.join(claimed_articles)}")

        article_evaluations.append({
            'item_id': row['item_id'],
            'case_name': row['case_name'],
            'article': selected_article,
            'article_name': article_name,
            'anonymized_text': row['anonymized_text'],
            'summarized_text': row['summarized_text'],
            'actual_violated': actual_violated,
            'overall_violation_label': row['violation_label']
        })

    eval_df = pd.DataFrame(article_evaluations)
    logger.info(f"\nTotal evaluations (1 per case): {len(eval_df)}")
    logger.info(f"  Actual violations: {eval_df['actual_violated'].sum()}")
    logger.info(f"  Actual no-violations: {(eval_df['actual_violated'] == 0).sum()}")

    # ========================================
    # STEP 4: EVALUATE BOTH FORMATS
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: EVALUATE BOTH FORMATS (Article-Specific)")
    logger.info("=" * 80)

    # Evaluate anonymized versions
    logger.info("\nEvaluating ANONYMIZED versions...")
    anonymize_tasks = [
        evaluate_article_violation(
            row['anonymized_text'],
            row['article'],
            row['article_name'],
            judge_model
        )
        for _, row in eval_df.iterrows()
    ]
    anonymize_predictions = await asyncio.gather(*anonymize_tasks)
    eval_df['anonymize_prediction'] = anonymize_predictions

    # Evaluate summarized versions
    logger.info("Evaluating SUMMARIZED versions...")
    summarize_tasks = [
        evaluate_article_violation(
            row['summarized_text'],
            row['article'],
            row['article_name'],
            judge_model
        )
        for _, row in eval_df.iterrows()
    ]
    summarize_predictions = await asyncio.gather(*summarize_tasks)
    eval_df['summarize_prediction'] = summarize_predictions

    # Convert to binary
    eval_df['anonymize_pred_binary'] = (pd.Series(anonymize_predictions, index=eval_df.index) == 'YES').astype(int)
    eval_df['summarize_pred_binary'] = (pd.Series(summarize_predictions, index=eval_df.index) == 'YES').astype(int)

    # ========================================
    # STEP 5: ANALYZE RESULTS
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: RESULTS")
    logger.info("=" * 80)

    # Filter valid cases
    valid_evals = eval_df[
        eval_df['anonymize_prediction'].notna() &
        eval_df['summarize_prediction'].notna()
    ].copy()

    if len(valid_evals) < len(eval_df):
        logger.info(f"Excluded {len(eval_df) - len(valid_evals)} evaluations with unparseable predictions")

    logger.info(f"Analyzing {len(valid_evals)} valid evaluations (1 per case)")

    total_evals = len(valid_evals)
    actual_violations = valid_evals['actual_violated'].sum()

    # Anonymize metrics
    anonymize_correct = (valid_evals['anonymize_pred_binary'] == valid_evals['actual_violated']).sum()
    anonymize_accuracy = anonymize_correct / total_evals * 100
    anonymize_viol_rate = valid_evals['anonymize_pred_binary'].sum() / total_evals * 100

    # Summarize metrics
    summarize_correct = (valid_evals['summarize_pred_binary'] == valid_evals['actual_violated']).sum()
    summarize_accuracy = summarize_correct / total_evals * 100
    summarize_viol_rate = valid_evals['summarize_pred_binary'].sum() / total_evals * 100

    logger.info("\n" + "=" * 80)
    logger.info("OVERALL COMPARISON")
    logger.info("=" * 80)
    logger.info(f"\nDataset:")
    logger.info(f"  Total evaluations (1 per case): {total_evals}")
    logger.info(f"  Actual violations: {actual_violations}")
    logger.info(f"  Actual no-violations: {total_evals - actual_violations}")

    logger.info(f"\nANONYMIZE (Full Length):")
    logger.info(f"  Accuracy: {anonymize_accuracy:.1f}% ({anonymize_correct}/{total_evals})")
    logger.info(f"  Violation detection rate: {anonymize_viol_rate:.1f}%")

    logger.info(f"\nSUMMARIZE ({word_count} words):")
    logger.info(f"  Accuracy: {summarize_accuracy:.1f}% ({summarize_correct}/{total_evals})")
    logger.info(f"  Violation detection rate: {summarize_viol_rate:.1f}%")

    logger.info(f"\nDIFFERENCE (Summarize - Anonymize):")
    logger.info(f"  Accuracy: {summarize_accuracy - anonymize_accuracy:+.1f} percentage points")
    logger.info(f"  Violation rate: {summarize_viol_rate - anonymize_viol_rate:+.1f} percentage points")

    # Disagreements
    disagreements = valid_evals[valid_evals['anonymize_prediction'] != valid_evals['summarize_prediction']]
    logger.info(f"\nCases where formats disagree: {len(disagreements)}/{total_evals} ({len(disagreements)/total_evals*100:.1f}%)")

    # Per-article breakdown
    logger.info("\n" + "=" * 80)
    logger.info("PER-ARTICLE BREAKDOWN")
    logger.info("=" * 80)

    for article in sorted(valid_evals['article'].unique()):
        article_data = valid_evals[valid_evals['article'] == article]
        article_name = article_data.iloc[0]['article_name']

        n_evals = len(article_data)
        anonymize_acc = (article_data['anonymize_pred_binary'] == article_data['actual_violated']).sum() / n_evals * 100
        summarize_acc = (article_data['summarize_pred_binary'] == article_data['actual_violated']).sum() / n_evals * 100

        logger.info(f"\nArticle {article}: {article_name}")
        logger.info(f"  Evaluations: {n_evals}")
        logger.info(f"  Anonymize accuracy: {anonymize_acc:.1f}%")
        logger.info(f"  Summarize accuracy: {summarize_acc:.1f}%")
        logger.info(f"  Difference: {summarize_acc - anonymize_acc:+.1f} pp")

    # ========================================
    # STEP 6: SAVE RESULTS
    # ========================================
    output_dir = data_dir / 'evaluations'
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f'anonymize_vs_summarize_article_{word_count}_n{n}_seed{random_seed}.csv'
    eval_df.to_csv(output_file, index=False)

    logger.info(f"\n✓ Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Compare anonymize vs summarize formats (article-specific)')
    parser.add_argument('-n', type=int, required=True, help='Number of cases per class')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--processing_model', type=str, default='openai/gpt-4o',
                        help='Model for anonymization/summarization')
    parser.add_argument('--judge_model', type=str, default='openai/gpt-4o-mini',
                        help='Model for judging violations')
    parser.add_argument('--word_count', type=int, default=200,
                        help='Word count for summarization')

    args = parser.parse_args()

    data_dir = Path('data/real_cases/echr_new')

    asyncio.run(run_anonymize_vs_summarize_experiment(
        n=args.n,
        data_dir=data_dir,
        processing_model=args.processing_model,
        judge_model=args.judge_model,
        random_seed=args.seed,
        word_count=args.word_count
    ))


if __name__ == '__main__':
    main()
