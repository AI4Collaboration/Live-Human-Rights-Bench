"""
Dataset Comparison Experiment - Compare Old vs New Balanced Samples

This experiment compares:
- old_balanced_sample_45_45_full_cases.csv (from dataset_v3.jsonl)
- balanced_sample_45_45_full_cases.csv (from latest ECHR cases)

Evaluates LLM performance on both to compare:
1. Violation detection rate
2. Accuracy (against ground truth)
"""

import asyncio
import logging
import pandas as pd
from pathlib import Path
from inspect_ai.model import GenerateConfig

from src.client import LLMClient
from src.real_cases.config import DEFAULT_JUDGE_MODEL

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

# Article mapping with full names
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


async def evaluate_article_violation(
    case_text: str,
    article: str,
    article_name: str,
    model_id: str,
    temperature: float = 0.0
) -> str:
    """
    Evaluate whether a specific article was violated in the case.

    Returns: 'YES', 'NO', or 'unclear'
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


async def evaluate_dataset(assignments_path: str, full_cases_path: str, dataset_name: str, judge_model: str):
    """Evaluate all cases in a dataset using article-specific evaluation."""

    logger.info("=" * 80)
    logger.info(f"EVALUATING: {dataset_name}")
    logger.info("=" * 80)

    # Load assignments (which article to evaluate for each case)
    assignments_df = pd.read_csv(assignments_path)
    # Load full cases (to get full_case_text)
    full_cases_df = pd.read_csv(full_cases_path)

    # Merge to get full case text with article assignments
    df = assignments_df.merge(full_cases_df[['item_id', 'full_case_text']], on='item_id', how='left')

    logger.info(f"Loaded {len(df)} evaluations")
    violation_count = len(df[df['violation_label'] == 'violation'])
    no_violation_count = len(df[df['violation_label'] == 'no_violation'])
    logger.info(f"  Violation evaluations: {violation_count}")
    logger.info(f"  No-violation evaluations: {no_violation_count}")

    # Evaluate all cases with article-specific prompts
    logger.info(f"\nEvaluating with {judge_model}...")

    tasks = []
    for idx, row in df.iterrows():
        article = row['article']
        article_name = ARTICLE_NAMES.get(article, f"Article {article}")
        tasks.append(evaluate_article_violation(
            row['full_case_text'],
            article,
            article_name,
            judge_model
        ))

    predictions = await asyncio.gather(*tasks)

    # Add predictions to dataframe
    df['predicted'] = predictions

    # Convert to violation/no_violation labels for comparison
    df['predicted_label'] = df['predicted'].apply(lambda x: 'violation' if x == 'YES' else 'no_violation' if x == 'NO' else 'unclear')

    # Calculate metrics
    correct = (df['violation_label'] == df['predicted_label']).sum()
    total = len(df)
    accuracy = correct / total * 100

    # Violation detection rate
    predicted_violations = (df['predicted_label'] == 'violation').sum()
    violation_rate = predicted_violations / total * 100

    # Ground truth violation rate
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
    """Run comparison experiment on both datasets."""

    # Paths
    data_dir = Path('data/real_cases/echr_new/unanimous')

    # For old dataset: we need to create article assignments since we don't have them
    # We'll use the full_cases CSV and randomly assign one article per case
    old_full_cases = data_dir / 'old_balanced_sample_45_45_full_cases.csv'

    # For new dataset: we have the balanced_sample_45_45.csv with article assignments
    new_assignments = data_dir / 'balanced_sample_45_45.csv'
    new_full_cases = data_dir / 'balanced_sample_45_45_full_cases.csv'

    output_dir = data_dir / 'evaluations'
    output_dir.mkdir(exist_ok=True, parents=True)

    judge_model = DEFAULT_JUDGE_MODEL

    logger.info("=" * 80)
    logger.info("DATASET COMPARISON EXPERIMENT (Article-Specific)")
    logger.info("=" * 80)
    logger.info(f"Judge model: {judge_model}")
    logger.info("")

    # Create article assignments for old dataset
    logger.info("Creating article assignments for old dataset...")
    old_df = pd.read_csv(old_full_cases)
    old_assignments_data = []

    import random
    random.seed(42)

    for idx, row in old_df.iterrows():
        # Get articles claimed
        articles_str = str(row['articles'])
        claimed_articles = []
        for art in ARTICLE_NAMES.keys():
            if art in articles_str:
                claimed_articles.append(art)

        # Randomly select one article if available
        if claimed_articles:
            article = random.choice(claimed_articles)
            old_assignments_data.append({
                'item_id': row['item_id'],
                'case_name': row['case_name'],
                'article': article,
                'violation_label': row['violation_label']
            })

    old_assignments_df = pd.DataFrame(old_assignments_data)
    old_assignments_path = data_dir / 'old_balanced_sample_45_45_assignments.csv'
    old_assignments_df.to_csv(old_assignments_path, index=False)
    logger.info(f"Created {len(old_assignments_df)} article assignments for old dataset")
    logger.info("")

    # Evaluate both datasets
    old_results = await evaluate_dataset(
        str(old_assignments_path),
        str(old_full_cases),
        "Old Dataset (dataset_v3)",
        judge_model
    )
    logger.info("\n")
    new_results = await evaluate_dataset(
        str(new_assignments),
        str(new_full_cases),
        "New Dataset (latest ECHR)",
        judge_model
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

    # Save results
    old_results['dataframe'].to_csv(output_dir / 'old_dataset_predictions.csv', index=False)
    new_results['dataframe'].to_csv(output_dir / 'new_dataset_predictions.csv', index=False)

    # Save summary
    summary_df = pd.DataFrame([
        {
            'Dataset': 'Old (dataset_v3)',
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
            'Total Cases': new_results['total_cases'],
            'Accuracy': f"{new_results['accuracy']:.1f}%",
            'Violation Rate': f"{new_results['violation_rate']:.1f}%",
            'Actual Violation Rate': f"{new_results['actual_violation_rate']:.1f}%",
            'Violation Rate Diff': f"{new_results['violation_rate_diff']:+.1f}pp",
            'Violation Accuracy': f"{new_results['violation_accuracy']:.1f}%",
            'No-Violation Accuracy': f"{new_results['no_violation_accuracy']:.1f}%",
        }
    ])

    summary_df.to_csv(output_dir / 'dataset_comparison_summary.csv', index=False)

    logger.info(f"\n✓ Results saved to {output_dir}")
    logger.info(f"  - old_dataset_predictions.csv")
    logger.info(f"  - new_dataset_predictions.csv")
    logger.info(f"  - dataset_comparison_summary.csv")


if __name__ == "__main__":
    asyncio.run(main())
