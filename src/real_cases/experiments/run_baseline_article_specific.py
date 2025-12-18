"""
Baseline Experiment with Article-Specific Evaluation

Uses the balanced 50+50 dataset and evaluates each case based on the specific
article assigned to it (not general violation detection).
"""

import asyncio
import argparse
import logging
import json
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

# Article names
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
    model_id: str,
    temperature: float = 0.0
) -> str:
    """Evaluate whether a specific article was violated."""

    article_name = ARTICLE_NAMES.get(article, f"Article {article}")

    system_prompt = """You are an expert legal evaluator for the European Court of Human Rights. Answer questions about specific article violations based on case facts."""

    prompt = f"""Based on the case facts below, answer this question:

Was Article {article}: {article_name} violated in this case?

Answer with ONLY "YES" or "NO", nothing else.

Case facts:
{case_text}

Answer (YES or NO):"""

    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=temperature, max_tokens=10)
    )

    response = await client.generate(
        prompt=prompt,
        system_message=system_prompt
    )

    # Parse response
    response_clean = response.strip().upper()

    if "YES" in response_clean:
        return "violation"
    elif "NO" in response_clean:
        return "no_violation"
    else:
        logger.warning(f"Unclear response for article {article}: {response}")
        return "unclear"


async def run_baseline_article_specific(
    evaluation_model: str = DEFAULT_JUDGE_MODEL,
    data_path: str = None,
    output_dir: str = None,
):
    """Run baseline experiment with article-specific evaluation."""

    if data_path is None:
        data_path = Path('data/real_cases/echr_new/unanimous/balanced_sample_50_50_full_cases.json')
    else:
        data_path = Path(data_path)

    if output_dir is None:
        output_dir = Path('data/real_cases/echr_new/evaluations')
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 80)
    logger.info("BASELINE EXPERIMENT - ARTICLE-SPECIFIC EVALUATION")
    logger.info("=" * 80)
    logger.info(f"Evaluation model: {evaluation_model}")
    logger.info(f"Data file: {data_path}")

    # Load data
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: LOADING DATA")
    logger.info("=" * 80)

    with open(data_path, 'r', encoding='utf-8') as f:
        cases = json.load(f)

    logger.info(f"Total cases loaded: {len(cases)}")

    violation_count = sum(1 for c in cases if c['violation_label'] == 'violation')
    no_violation_count = sum(1 for c in cases if c['violation_label'] == 'no_violation')

    logger.info(f"  Violations: {violation_count}")
    logger.info(f"  No-violations: {no_violation_count}")

    # Count by article
    from collections import Counter
    article_counts = Counter(c['article'] for c in cases)
    logger.info("\nCases by article:")
    for article in sorted(article_counts.keys()):
        logger.info(f"  Article {article}: {article_counts[article]}")

    # Step 2: Evaluate
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: EVALUATING CASES (ARTICLE-SPECIFIC)")
    logger.info("=" * 80)

    async def evaluate_single_case(case):
        """Evaluate one case based on its assigned article."""
        item_id = case['item_id']
        article = case['article']
        case_text = case['full_case_text']
        ground_truth = case['violation_label']

        try:
            prediction = await evaluate_article_violation(
                case_text=case_text,
                article=article,
                model_id=evaluation_model
            )
            logger.info(f"✓ {item_id} [Article {article}] (truth: {ground_truth}): {prediction}")
            return {
                'item_id': item_id,
                'case_name': case['case_name'],
                'article': article,
                'ground_truth': ground_truth,
                'llm_prediction': prediction
            }
        except Exception as e:
            logger.error(f"❌ {item_id} [Article {article}]: {e}")
            return {
                'item_id': item_id,
                'case_name': case['case_name'],
                'article': article,
                'ground_truth': ground_truth,
                'llm_prediction': 'error'
            }

    logger.info(f"Evaluating {len(cases)} cases...")
    results = await asyncio.gather(*[evaluate_single_case(case) for case in cases])

    logger.info(f"✓ Completed evaluation")

    # Filter out unclear and error predictions
    valid_results = [r for r in results if r['llm_prediction'] not in ['unclear', 'error']]

    excluded_count = len(results) - len(valid_results)
    if excluded_count > 0:
        logger.info(f"\nExcluded {excluded_count} cases with unparseable or error predictions")
        unclear_count = sum(1 for r in results if r['llm_prediction'] == 'unclear')
        error_count = sum(1 for r in results if r['llm_prediction'] == 'error')
        logger.info(f"  'unclear': {unclear_count}")
        logger.info(f"  'error': {error_count}")
        logger.info(f"Analyzing {len(valid_results)} cases with valid predictions")

    # Calculate metrics
    correct = sum(1 for r in valid_results if r['llm_prediction'] == r['ground_truth'])
    llm_violations = sum(1 for r in valid_results if r['llm_prediction'] == 'violation')

    overall_accuracy = correct / len(valid_results) if valid_results else 0
    llm_violation_rate = llm_violations / len(valid_results) if valid_results else 0

    # Step 3: Results
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: RESULTS ANALYSIS")
    logger.info("=" * 80)

    logger.info(f"\n{'Metric':<50} {'Value':<15}")
    logger.info("-" * 70)
    logger.info(f"{'Overall accuracy':<50} {overall_accuracy:>13.1%}")
    logger.info(f"{'LLM violation detection rate':<50} {llm_violation_rate:>13.1%}")

    # Per-class statistics
    logger.info(f"\n{'Ground Truth':<20} {'N':<8} {'LLM Says Violation':<20} {'Accuracy':<15}")
    logger.info("-" * 70)

    for truth in ['no_violation', 'violation']:
        subset = [r for r in valid_results if r['ground_truth'] == truth]
        count = len(subset)
        if count > 0:
            llm_viol_count = sum(1 for r in subset if r['llm_prediction'] == 'violation')
            llm_viol_rate = llm_viol_count / count
            correct_count = sum(1 for r in subset if r['llm_prediction'] == r['ground_truth'])
            accuracy = correct_count / count
            logger.info(f"{truth:<20} {count:<8} {llm_viol_rate:>18.1%} {accuracy:>14.1%}")

    # Confusion matrix
    tp = sum(1 for r in valid_results if r['ground_truth'] == 'violation' and r['llm_prediction'] == 'violation')
    tn = sum(1 for r in valid_results if r['ground_truth'] == 'no_violation' and r['llm_prediction'] == 'no_violation')
    fp = sum(1 for r in valid_results if r['ground_truth'] == 'no_violation' and r['llm_prediction'] == 'violation')
    fn = sum(1 for r in valid_results if r['ground_truth'] == 'violation' and r['llm_prediction'] == 'no_violation')

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

    # Per-article analysis
    logger.info(f"\n{'Article':<10} {'N':<6} {'Accuracy':<12} {'LLM Viol Rate':<15}")
    logger.info("-" * 50)

    for article in sorted(set(r['article'] for r in valid_results)):
        subset = [r for r in valid_results if r['article'] == article]
        count = len(subset)
        if count > 0:
            correct_count = sum(1 for r in subset if r['llm_prediction'] == r['ground_truth'])
            accuracy = correct_count / count
            viol_count = sum(1 for r in subset if r['llm_prediction'] == 'violation')
            viol_rate = viol_count / count
            logger.info(f"{article:<10} {count:<6} {accuracy:>10.1%} {viol_rate:>14.1%}")

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

    # Save detailed results as JSON
    results_file = output_dir / f"baseline_article_specific_{eval_model_name}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"📊 Detailed results: {results_file}")

    # Save summary
    summary = {
        'evaluation_model': evaluation_model,
        'total_cases': len(cases),
        'valid_cases': len(valid_results),
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

    summary_file = output_dir / f"baseline_article_specific_summary_{eval_model_name}.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    logger.info(f"📈 Summary: {summary_file}")

    logger.info("\n" + "=" * 80)
    logger.info("✓ EXPERIMENT COMPLETE")
    logger.info("=" * 80)

    return results, summary


def main():
    parser = argparse.ArgumentParser(
        description="Run baseline experiment with article-specific evaluation"
    )
    parser.add_argument(
        "--evaluation_model",
        default=DEFAULT_JUDGE_MODEL,
        help="Model for evaluation/judgment"
    )
    parser.add_argument(
        "--data_path",
        default=None,
        help="Path to JSON data file (default: balanced_sample_50_50_full_cases.json)"
    )
    parser.add_argument(
        "--output_dir",
        default=None,
        help="Output directory (default: data/real_cases/echr_new/evaluations)"
    )

    args = parser.parse_args()

    asyncio.run(
        run_baseline_article_specific(
            evaluation_model=args.evaluation_model,
            data_path=args.data_path,
            output_dir=args.output_dir,
        )
    )


if __name__ == "__main__":
    main()
