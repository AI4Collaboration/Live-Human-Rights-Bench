"""
Dataset Comparison Experiment with Simplification

This experiment compares old vs new datasets with case simplification:
1. Simplify all cases using gpt-4o-mini with simplification prompts
2. Evaluate with article-specific prompts using gpt-4o
3. Compare violation rate and accuracy
"""

import asyncio
import logging
import pandas as pd
from pathlib import Path
from inspect_ai.model import GenerateConfig

from src.client import LLMClient
from src.real_cases.config import DEFAULT_JUDGE_MODEL
from src.real_cases.utils.simplification_prompts import (
    get_simplification_system_prompt,
    get_simplification_prompt_template
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

# Article mapping
ARTICLE_NAMES = {
    '2': 'Right to life',
    '3': 'Prohibition of torture',
    '5': 'Right to liberty and security',
    '8': 'Right to respect for private and family life',
    '9': 'Freedom of thought, conscience and religion',
    '10': 'Freedom of expression',
    '14': 'Prohibition of discrimination',
    'P1-1': 'Protection of property',
}


async def simplify_case(case_text: str, model_id: str = "openai/gpt-4o-mini", word_range: tuple = (150, 200), temperature: float = 0.3) -> str:
    """Simplify a case using the simplification prompts."""
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=temperature, max_tokens=400)
    )

    system_prompt = get_simplification_system_prompt(word_range)
    prompt_template = get_simplification_prompt_template(word_range)
    prompt = prompt_template.format(case_text=case_text)

    try:
        simplified = await client.generate(
            prompt=prompt,
            system_message=system_prompt
        )
        return simplified.strip()
    except Exception as e:
        logger.error(f"Error simplifying case: {e}")
        return case_text[:1000]  # Fallback to truncation


async def evaluate_article_violation(
    case_text: str,
    article: str,
    article_name: str,
    model_id: str,
    temperature: float = 0.0
) -> str:
    """Evaluate whether a specific article was violated."""
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

        if "YES" in response_clean:
            return "YES"
        elif "NO" in response_clean:
            return "NO"
        else:
            logger.warning(f"Unclear response: {response}")
            return "unclear"
    except Exception as e:
        logger.error(f"Error evaluating article {article}: {e}")
        return "unclear"


async def evaluate_dataset(
    assignments_path: str,
    full_cases_path: str,
    dataset_name: str,
    judge_model: str,
    simplification_model: str = "openai/gpt-4o-mini",
    word_range: tuple = (150, 200)
):
    """Evaluate dataset with simplification."""

    logger.info("=" * 80)
    logger.info(f"EVALUATING: {dataset_name}")
    logger.info("=" * 80)

    # Load data
    assignments_df = pd.read_csv(assignments_path)
    full_cases_df = pd.read_csv(full_cases_path)
    df = assignments_df.merge(full_cases_df[['item_id', 'full_case_text']], on='item_id', how='left')

    logger.info(f"Loaded {len(df)} evaluations")
    logger.info(f"  Violation: {len(df[df['violation_label'] == 'violation'])}")
    logger.info(f"  No-violation: {len(df[df['violation_label'] == 'no_violation'])}")

    # Step 1: Simplify all cases
    logger.info(f"\nSimplifying cases with {simplification_model}...")

    simplify_tasks = []
    for idx, row in df.iterrows():
        simplify_tasks.append(simplify_case(row['full_case_text'], simplification_model, word_range))

    simplified_texts = await asyncio.gather(*simplify_tasks)
    df['simplified_text'] = simplified_texts

    logger.info(f"✓ Simplified {len(df)} cases")

    # Step 2: Evaluate with article-specific prompts
    logger.info(f"\nEvaluating with {judge_model}...")

    eval_tasks = []
    for idx, row in df.iterrows():
        article = row['article']
        article_name = ARTICLE_NAMES.get(article, f"Article {article}")
        eval_tasks.append(evaluate_article_violation(
            row['simplified_text'],
            article,
            article_name,
            judge_model
        ))

    predictions = await asyncio.gather(*eval_tasks)
    df['predicted'] = predictions
    df['predicted_label'] = df['predicted'].apply(lambda x: 'violation' if x == 'YES' else 'no_violation' if x == 'NO' else 'unclear')

    # Calculate metrics
    correct = (df['violation_label'] == df['predicted_label']).sum()
    total = len(df)
    accuracy = correct / total * 100

    predicted_violations = (df['predicted_label'] == 'violation').sum()
    violation_rate = predicted_violations / total * 100

    actual_violations = (df['violation_label'] == 'violation').sum()
    actual_violation_rate = actual_violations / total * 100

    # Per-class accuracy
    violation_cases = df[df['violation_label'] == 'violation']
    no_violation_cases = df[df['violation_label'] == 'no_violation']

    violation_correct = (violation_cases['predicted_label'] == 'violation').sum()
    no_violation_correct = (no_violation_cases['predicted_label'] == 'no_violation').sum()

    violation_accuracy = violation_correct / len(violation_cases) * 100 if len(violation_cases) > 0 else 0
    no_violation_accuracy = no_violation_correct / len(no_violation_cases) * 100 if len(no_violation_cases) > 0 else 0

    # Log results
    logger.info("")
    logger.info("=" * 80)
    logger.info("RESULTS")
    logger.info("=" * 80)
    logger.info(f"Overall Accuracy: {accuracy:.1f}% ({correct}/{total})")
    logger.info(f"")
    logger.info(f"Violation Detection Rate:")
    logger.info(f"  Predicted violations: {predicted_violations}/{total} ({violation_rate:.1f}%)")
    logger.info(f"  Actual violations: {actual_violations}/{total} ({actual_violation_rate:.1f}%)")
    logger.info(f"  Difference: {violation_rate - actual_violation_rate:+.1f} percentage points")
    logger.info(f"")
    logger.info(f"Per-Class Accuracy:")
    logger.info(f"  Violation cases: {violation_accuracy:.1f}% ({violation_correct}/{len(violation_cases)})")
    logger.info(f"  No-violation cases: {no_violation_accuracy:.1f}% ({no_violation_correct}/{len(no_violation_cases)})")

    return {
        'dataset_name': dataset_name,
        'total_cases': total,
        'accuracy': accuracy,
        'correct': correct,
        'predicted_violations': predicted_violations,
        'actual_violations': actual_violations,
        'violation_rate': violation_rate,
        'actual_violation_rate': actual_violation_rate,
        'violation_rate_diff': violation_rate - actual_violation_rate,
        'violation_accuracy': violation_accuracy,
        'no_violation_accuracy': no_violation_accuracy,
        'dataframe': df
    }


async def main():
    """Run comparison experiment with simplification."""

    # Paths
    data_dir = Path('data/real_cases/echr_new/unanimous')

    # Create article assignments for old dataset
    old_full_cases = data_dir / 'old_balanced_sample_45_45_full_cases.csv'
    old_assignments_path = data_dir / 'old_balanced_sample_45_45_assignments.csv'

    # New dataset has assignments already
    new_assignments = data_dir / 'balanced_sample_45_45.csv'
    new_full_cases = data_dir / 'balanced_sample_45_45_full_cases.csv'

    output_dir = data_dir / 'evaluations'
    output_dir.mkdir(exist_ok=True, parents=True)

    judge_model = DEFAULT_JUDGE_MODEL
    simplification_model = "openai/gpt-4o"  # Changed from gpt-4o-mini to gpt-4o
    word_range = (150, 200)

    logger.info("=" * 80)
    logger.info("DATASET COMPARISON WITH SIMPLIFICATION (GPT-4o)")
    logger.info("=" * 80)
    logger.info(f"Simplification model: {simplification_model}")
    logger.info(f"Word range: {word_range}")
    logger.info(f"Judge model: {judge_model}")
    logger.info("")

    # Check if old assignments exist, if not create them
    if not old_assignments_path.exists():
        logger.info("Creating article assignments for old dataset...")
        old_df = pd.read_csv(old_full_cases)
        old_assignments_data = []

        import random
        random.seed(42)

        for idx, row in old_df.iterrows():
            articles_str = str(row['articles'])
            claimed_articles = []
            for art in ARTICLE_NAMES.keys():
                if art in articles_str:
                    claimed_articles.append(art)

            if claimed_articles:
                article = random.choice(claimed_articles)
                old_assignments_data.append({
                    'item_id': row['item_id'],
                    'case_name': row['case_name'],
                    'article': article,
                    'violation_label': row['violation_label']
                })

        old_assignments_df = pd.DataFrame(old_assignments_data)
        old_assignments_df.to_csv(old_assignments_path, index=False)
        logger.info(f"Created {len(old_assignments_df)} assignments")
        logger.info("")

    # Evaluate both datasets
    old_results = await evaluate_dataset(
        str(old_assignments_path),
        str(old_full_cases),
        "Old Dataset (dataset_v3)",
        judge_model,
        simplification_model,
        word_range
    )
    logger.info("\n")
    new_results = await evaluate_dataset(
        str(new_assignments),
        str(new_full_cases),
        "New Dataset (latest ECHR)",
        judge_model,
        simplification_model,
        word_range
    )

    # Comparison summary
    logger.info("\n")
    logger.info("=" * 80)
    logger.info("COMPARISON SUMMARY")
    logger.info("=" * 80)
    logger.info("")
    logger.info(f"{'Metric':<30} {'Old Dataset':<20} {'New Dataset':<20} {'Difference':<15}")
    logger.info("=" * 80)
    logger.info(f"{'Total Cases':<30} {old_results['total_cases']:<20} {new_results['total_cases']:<20} {new_results['total_cases'] - old_results['total_cases']:<15}")
    logger.info(f"{'Accuracy':<30} {old_results['accuracy']:.1f}%{'':<15} {new_results['accuracy']:.1f}%{'':<15} {new_results['accuracy'] - old_results['accuracy']:+.1f}pp")
    logger.info(f"{'Violation Rate':<30} {old_results['violation_rate']:.1f}%{'':<15} {new_results['violation_rate']:.1f}%{'':<15} {new_results['violation_rate'] - old_results['violation_rate']:+.1f}pp")
    logger.info(f"{'Violation Accuracy':<30} {old_results['violation_accuracy']:.1f}%{'':<15} {new_results['violation_accuracy']:.1f}%{'':<15} {new_results['violation_accuracy'] - old_results['violation_accuracy']:+.1f}pp")
    logger.info(f"{'No-Violation Accuracy':<30} {old_results['no_violation_accuracy']:.1f}%{'':<15} {new_results['no_violation_accuracy']:.1f}%{'':<15} {new_results['no_violation_accuracy'] - old_results['no_violation_accuracy']:+.1f}pp")
    logger.info("=" * 80)

    # Save results with model name in filename
    model_suffix = simplification_model.split('/')[-1].replace('-', '_')
    old_results['dataframe'].to_csv(output_dir / f'old_dataset_simplified_{model_suffix}_predictions.csv', index=False)
    new_results['dataframe'].to_csv(output_dir / f'new_dataset_simplified_{model_suffix}_predictions.csv', index=False)

    # Save summary
    summary_df = pd.DataFrame([
        {
            'Dataset': 'Old (dataset_v3)',
            'Simplification': f'{simplification_model}',
            'Total Cases': old_results['total_cases'],
            'Accuracy': f"{old_results['accuracy']:.1f}%",
            'Violation Rate': f"{old_results['violation_rate']:.1f}%",
            'Actual Violation Rate': f"{old_results['actual_violation_rate']:.1f}%",
            'Violation Rate Diff': f"{old_results['violation_rate_diff']:+.1f}pp",
            'Violation Accuracy': f"{old_results['violation_accuracy']:.1f}%",
            'No-Violation Accuracy': f"{old_results['no_violation_accuracy']:.1f}%",
        },
        {
            'Dataset': 'New (latest ECHR)',
            'Simplification': f'{simplification_model}',
            'Total Cases': new_results['total_cases'],
            'Accuracy': f"{new_results['accuracy']:.1f}%",
            'Violation Rate': f"{new_results['violation_rate']:.1f}%",
            'Actual Violation Rate': f"{new_results['actual_violation_rate']:.1f}%",
            'Violation Rate Diff': f"{new_results['violation_rate_diff']:+.1f}pp",
            'Violation Accuracy': f"{new_results['violation_accuracy']:.1f}%",
            'No-Violation Accuracy': f"{new_results['no_violation_accuracy']:.1f}%",
        }
    ])

    summary_df.to_csv(output_dir / f'dataset_comparison_simplified_{model_suffix}_summary.csv', index=False)

    logger.info(f"\n✓ Results saved to {output_dir}")
    logger.info(f"  - old_dataset_simplified_{model_suffix}_predictions.csv")
    logger.info(f"  - new_dataset_simplified_{model_suffix}_predictions.csv")
    logger.info(f"  - dataset_comparison_simplified_{model_suffix}_summary.csv")


if __name__ == "__main__":
    asyncio.run(main())
