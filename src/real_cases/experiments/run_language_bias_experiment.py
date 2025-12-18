"""
Language Bias Experiment - Test for language bias in violation detection

This experiment tests whether LLMs show bias based on the language in which cases
are presented and evaluated.

For a given sample size N:
1. Sample N cases with violations + N cases with no violations
2. Process cases (anonymize/summarize/story as specified) in English
3. Translate to Romanian, Russian, and Chinese
4. Evaluate in each language (including English baseline) with language-specific prompts
5. Compare violation detection rates across languages

Languages tested:
- English (baseline)
- Romanian (Eastern European, Latin script, Romance language)
- Russian (Eastern European, Cyrillic script, Slavic language)
- Chinese (Non-European, Logographic script)

Output metrics:
- Violation detection rate per language
- English vs non-English comparison
- Per-article breakdown by language
"""

import asyncio
import argparse
import logging
import pandas as pd
import re
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
    get_translation_system_prompt,
    get_translation_prompt_template,
    get_evaluation_prompts,
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

# Languages to test
LANGUAGES = ['English', 'Romanian', 'Russian', 'Chinese']

# YES/NO patterns for each language
YES_NO_PATTERNS = {
    'english': {'yes': ['yes'], 'no': ['no']},
    'romanian': {'yes': ['da'], 'no': ['nu']},
    'russian': {'yes': ['да', 'da'], 'no': ['нет', 'net']},
    'chinese': {'yes': ['是', 'shi'], 'no': ['否', 'bu', '不']},
}


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


async def translate_case(case_text: str, target_language: str, model_id: str, temperature: float = 0.3) -> str:
    """Translate case text to target language.

    Args:
        case_text: English case text to translate
        target_language: Target language name (e.g., 'Romanian', 'Russian', 'Chinese')
        model_id: Model to use for translation
        temperature: Temperature for generation

    Returns:
        Translated case text
    """
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=temperature, max_tokens=4000)
    )

    system_prompt = get_translation_system_prompt(target_language)
    prompt_template = get_translation_prompt_template()
    prompt = prompt_template.format(case_text=case_text, target_language=target_language)

    translated = await client.generate(
        prompt=prompt,
        system_message=system_prompt
    )

    return translated.strip()


async def evaluate_case(case_text: str, language: str, model_id: str, temperature: float = 0.0) -> str:
    """Evaluate a case in a specific language and return YES/NO.

    Args:
        case_text: Case text (in the specified language)
        language: Language of the case and evaluation ('english', 'romanian', 'russian', 'chinese')
        model_id: Model to use for evaluation
        temperature: Temperature for generation

    Returns:
        'YES' or 'NO' (normalized to English)
    """
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=temperature, max_tokens=20)
    )

    # Get language-specific prompts
    system_prompt, prompt_template = get_evaluation_prompts(language)
    prompt = prompt_template.format(case_text=case_text)

    response = await client.generate(
        prompt=prompt,
        system_message=system_prompt
    )

    # Parse response based on language
    response_lower = response.strip().lower()
    lang_lower = language.lower()

    # Debug logging for Chinese responses
    if lang_lower == 'chinese':
        logger.info(f"Chinese response: '{response.strip()}' (length: {len(response.strip())})")

    # Check for NO patterns FIRST (important for Chinese: 不是 contains both 不 and 是)
    if lang_lower in YES_NO_PATTERNS:
        for no_pattern in YES_NO_PATTERNS[lang_lower]['no']:
            if no_pattern in response_lower:
                if lang_lower == 'chinese':
                    logger.info(f"  → Matched NO pattern: '{no_pattern}'")
                return 'NO'
        # Then check for YES patterns
        for yes_pattern in YES_NO_PATTERNS[lang_lower]['yes']:
            if yes_pattern in response_lower:
                if lang_lower == 'chinese':
                    logger.info(f"  → Matched YES pattern: '{yes_pattern}'")
                return 'YES'

    # Fallback: try English patterns (NO first, then YES)
    if 'no' in response_lower:
        return 'NO'
    elif 'yes' in response_lower:
        return 'YES'

    logger.warning(f"Unexpected response in {language}: {response}, excluding from analysis")
    return None


def has_identifiable_individual(case_text: str) -> bool:
    """Check if case has an identifiable individual applicant."""
    case_lower = case_text.lower()

    # Skip if it's clearly corporate/organizational
    corporate_indicators = [
        'company', 'corporation', 'organization', 'association',
        'foundation', 'society', 'partnership', 'limited', 'ltd',
        'inc.', 'llc', 'gmbh', 'sa', 'ngo'
    ]

    corporate_count = sum(1 for indicator in corporate_indicators if indicator in case_lower)
    if corporate_count >= 2:
        return False

    # Check for individual indicators
    individual_indicators = ['applicant', 'he', 'she', 'his', 'her', 'him']
    has_individual = any(indicator in case_lower for indicator in individual_indicators)

    return has_individual


async def run_language_bias_experiment(
    n: int,
    data_dir: Path,
    simplification_model: str,
    judge_model: str,
    random_seed: int = 42,
    anonymize_only: bool = False,
    story_mode: bool = False,
    word_range: tuple = (150, 200),
):
    """Run language bias experiment.

    Args:
        n: Number of cases per category (violations/no_violations)
        data_dir: Directory containing cases.csv
        simplification_model: Model for processing and translation
        judge_model: Model for evaluation
        random_seed: Random seed for sampling
        anonymize_only: If True, anonymize without summarizing
        story_mode: If True, use story-based narrative format
        word_range: Word range for summarization
    """
    logger.info("=" * 80)
    logger.info("LANGUAGE BIAS EXPERIMENT")
    logger.info("=" * 80)
    logger.info(f"Sample size per category: {n}")
    logger.info(f"Total cases: {2 * n}")
    logger.info(f"Total evaluations: {2 * n * 4} (4 languages)")
    logger.info(f"Languages tested: {', '.join(LANGUAGES)}")
    logger.info(f"Simplification/Translation model: {simplification_model}")
    logger.info(f"Judge model: {judge_model}")
    logger.info(f"Random seed: {random_seed}")

    if anonymize_only:
        mode_str = "anonymize_only"
        step_name = "ANONYMIZE"
    elif story_mode:
        mode_str = f"story_{word_range[0]}_{word_range[1]}"
        step_name = f"STORY MODE ({word_range[0]}-{word_range[1]} words)"
    else:
        mode_str = f"summarize_{word_range[0]}_{word_range[1]}"
        step_name = f"SUMMARIZE ({word_range[0]}-{word_range[1]} words)"

    logger.info(f"Processing mode: {mode_str}")

    # ========================================
    # STEP 1: SAMPLE CASES
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: SAMPLE CASES")
    logger.info("=" * 80)

    csv_path = data_dir / 'cases.csv'
    df = pd.read_csv(csv_path)

    logger.info(f"Total cases in dataset: {len(df)}")
    logger.info(f"  Violations: {len(df[df['violation_label'] == 'violation'])}")
    logger.info(f"  No violations: {len(df[df['violation_label'] == 'no_violation'])}")

    # Sample N violations
    violation_cases = df[df['violation_label'] == 'violation']
    if len(violation_cases) < n:
        logger.warning(f"Only {len(violation_cases)} violation cases available, using all")
        sampled_violations = violation_cases
    else:
        sampled_violations = violation_cases.sample(n=n, random_state=random_seed)

    # Sample N no-violations
    no_violation_cases = df[df['violation_label'] == 'no_violation']
    if len(no_violation_cases) < n:
        logger.warning(f"Only {len(no_violation_cases)} no-violation cases available, using all")
        sampled_no_violations = no_violation_cases
    else:
        sampled_no_violations = no_violation_cases.sample(n=n, random_state=random_seed)

    # Combine samples
    sampled_cases = pd.concat([sampled_violations, sampled_no_violations], ignore_index=True)

    logger.info(f"\nSampled cases: {len(sampled_cases)}")
    logger.info(f"  Violations: {len(sampled_violations)}")
    logger.info(f"  No violations: {len(sampled_no_violations)}")

    # ========================================
    # STEP 2: PROCESS CASES IN ENGLISH (WITH CACHING)
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info(f"STEP 2: {step_name} CASES IN ENGLISH (WITH CACHING)")
    logger.info("=" * 80)

    # Create cache directory
    cache_dir_name = get_cache_dir_name(anonymize_only, story_mode, word_range, simplification_model)
    cache_dir = data_dir.parent / cache_dir_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Cache directory: {cache_dir}")

    async def process_single_case(row):
        """Process one case in English, using cache if available."""
        item_id = row['item_id']
        case_text = row['full_case_text']

        cache_file = cache_dir / f"{item_id}.txt"

        # Check cache
        if cache_file.exists():
            processed_text = cache_file.read_text(encoding='utf-8')
            logger.info(f"  {item_id}: Using cached")
            return processed_text

        # Process case
        if anonymize_only:
            processed_text = await anonymize_case(case_text, simplification_model)
        elif story_mode:
            processed_text = await story_case(case_text, simplification_model, word_range)
        else:
            processed_text = await simplify_case(case_text, simplification_model, word_range)

        # Save to cache
        cache_file.write_text(processed_text, encoding='utf-8')
        logger.info(f"  {item_id}: Processed and cached")

        return processed_text

    # Process all cases in parallel
    tasks = [process_single_case(row) for _, row in sampled_cases.iterrows()]
    processed_texts = await asyncio.gather(*tasks)

    # Add processed text to dataframe
    sampled_cases['english_text'] = processed_texts

    # Filter out non-individual cases
    logger.info("\n" + "=" * 80)
    logger.info("FILTERING NON-INDIVIDUAL CASES")
    logger.info("=" * 80)

    initial_count = len(sampled_cases)
    sampled_cases['has_individual'] = sampled_cases['english_text'].apply(has_identifiable_individual)
    sampled_cases = sampled_cases[sampled_cases['has_individual']].copy()

    filtered_count = initial_count - len(sampled_cases)
    logger.info(f"Filtered out {filtered_count} non-individual cases")
    logger.info(f"Remaining cases: {len(sampled_cases)}")

    if len(sampled_cases) == 0:
        logger.error("No individual cases remaining after filtering!")
        return

    # ========================================
    # STEP 3: TRANSLATE TO OTHER LANGUAGES (WITH CACHING)
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: TRANSLATE TO OTHER LANGUAGES (WITH CACHING)")
    logger.info("=" * 80)

    async def translate_with_cache(row, target_language: str):
        """Translate case with caching."""
        item_id = row['item_id']
        english_text = row['english_text']

        lang_lower = target_language.lower()
        cache_file = cache_dir / f"{item_id}_{lang_lower}.txt"

        # Check cache
        if cache_file.exists():
            translated_text = cache_file.read_text(encoding='utf-8')
            logger.info(f"  {item_id} ({target_language}): Using cached")
            return translated_text

        # Translate
        translated_text = await translate_case(english_text, target_language, simplification_model)

        # Save to cache
        cache_file.write_text(translated_text, encoding='utf-8')
        logger.info(f"  {item_id} ({target_language}): Translated and cached")

        return translated_text

    # Translate to each non-English language
    for language in LANGUAGES:
        if language.lower() == 'english':
            continue  # English already processed

        logger.info(f"\nTranslating to {language.upper()}...")
        tasks = [translate_with_cache(row, language) for _, row in sampled_cases.iterrows()]
        texts = await asyncio.gather(*tasks)
        sampled_cases[f'{language.lower()}_text'] = texts

    # ========================================
    # STEP 4: EVALUATE IN ALL LANGUAGES
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: EVALUATE IN ALL LANGUAGES")
    logger.info("=" * 80)

    # Evaluate in each language
    for language in LANGUAGES:
        logger.info(f"\nEvaluating in {language.upper()}...")
        lang_lower = language.lower()
        texts = sampled_cases[f'{lang_lower}_text'].tolist()

        eval_tasks = [evaluate_case(text, lang_lower, judge_model) for text in texts]
        predictions = await asyncio.gather(*eval_tasks)

        sampled_cases[f'{lang_lower}_prediction'] = predictions
        # IMPORTANT: Preserve dataframe index when creating binary column to avoid index misalignment
        sampled_cases[f'{lang_lower}_pred_binary'] = (pd.Series(predictions, index=sampled_cases.index) == 'YES').astype(int)

    # Add true labels
    sampled_cases['true_label_binary'] = (sampled_cases['violation_label'] == 'violation').astype(int)

    # ========================================
    # STEP 5: ANALYZE RESULTS
    # ========================================
    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: RESULTS")
    logger.info("=" * 80)

    # Filter out cases with any None predictions (unparseable responses)
    pred_cols = [f'{lang.lower()}_prediction' for lang in LANGUAGES]
    valid_mask = sampled_cases[pred_cols].notna().all(axis=1)
    valid_cases = sampled_cases[valid_mask].copy()

    excluded_count = len(sampled_cases) - len(valid_cases)
    if excluded_count > 0:
        logger.info(f"\nExcluded {excluded_count} cases with unparseable predictions")
        logger.info(f"Analyzing {len(valid_cases)} cases with valid predictions for all languages")

    total_cases = len(valid_cases)

    # Calculate metrics for each language (only on valid cases)
    language_metrics = {}
    for language in LANGUAGES:
        lang_lower = language.lower()
        pred_col = f'{lang_lower}_prediction'

        # Recalculate binary from valid cases
        valid_cases[f'{lang_lower}_pred_binary'] = (valid_cases[pred_col] == 'YES').astype(int)

        violation_rate = valid_cases[f'{lang_lower}_pred_binary'].mean() * 100
        correct = (valid_cases[f'{lang_lower}_pred_binary'] == valid_cases['true_label_binary']).sum()
        accuracy = correct / total_cases * 100

        language_metrics[language] = {
            'violation_rate': violation_rate,
            'accuracy': accuracy,
            'correct': correct
        }

    # Overall results
    logger.info("\n" + "=" * 80)
    logger.info("OVERALL RESULTS")
    logger.info("=" * 80)
    logger.info(f"Total cases evaluated: {total_cases}")
    logger.info(f"Actual violations: {valid_cases['true_label_binary'].sum()}")
    logger.info(f"Actual no-violations: {total_cases - valid_cases['true_label_binary'].sum()}")

    # Per-language results
    logger.info("\n" + "=" * 80)
    logger.info("PER-LANGUAGE RESULTS")
    logger.info("=" * 80)

    for language in LANGUAGES:
        metrics = language_metrics[language]
        logger.info(f"\n{language.upper()}:")
        logger.info("-" * 80)
        logger.info(f"  Violation detection rate: {metrics['violation_rate']:.1f}%")
        logger.info(f"  Accuracy: {metrics['accuracy']:.1f}%")
        logger.info(f"  Correct predictions: {metrics['correct']}/{total_cases}")

    # Language comparison
    logger.info("\n" + "=" * 80)
    logger.info("LANGUAGE COMPARISON")
    logger.info("=" * 80)

    english_rate = language_metrics['English']['violation_rate']
    non_english_rates = [language_metrics[lang]['violation_rate'] for lang in LANGUAGES if lang != 'English']
    non_english_avg = sum(non_english_rates) / len(non_english_rates)

    logger.info(f"English (baseline): {english_rate:.1f}%")
    logger.info(f"Non-English average: {non_english_avg:.1f}%")
    logger.info(f"Difference (English - Non-English): {english_rate - non_english_avg:+.1f} percentage points")

    # Variance analysis
    all_rates = [metrics['violation_rate'] for metrics in language_metrics.values()]

    # Handle NaN values from very small samples
    import math
    valid_rates = [rate for rate in all_rates if not math.isnan(rate)]

    if valid_rates:
        min_rate = min(valid_rates)
        max_rate = max(valid_rates)
        rate_range = max_rate - min_rate

        logger.info("\n" + "=" * 80)
        logger.info("VARIANCE ANALYSIS")
        logger.info("=" * 80)
        min_lang = [lang for lang, metrics in language_metrics.items() if metrics['violation_rate'] == min_rate][0]
        max_lang = [lang for lang, metrics in language_metrics.items() if metrics['violation_rate'] == max_rate][0]
        logger.info(f"Minimum violation rate: {min_rate:.1f}% ({min_lang})")
        logger.info(f"Maximum violation rate: {max_rate:.1f}% ({max_lang})")
        logger.info(f"Range: {rate_range:.1f} percentage points")
    else:
        logger.info("\n" + "=" * 80)
        logger.info("VARIANCE ANALYSIS")
        logger.info("=" * 80)
        logger.info("Insufficient data for variance analysis (all rates are NaN)")

    # Per-article breakdown
    logger.info("\n" + "=" * 80)
    logger.info("PER-ARTICLE BREAKDOWN")
    logger.info("=" * 80)

    # Get unique articles
    all_articles = set()
    for articles_str in valid_cases['articles']:
        if pd.notna(articles_str):
            articles = [a.strip() for a in str(articles_str).split(',')]
            all_articles.update(articles)

    for article in sorted(all_articles):
        # Filter cases involving this article
        article_cases = valid_cases[valid_cases['articles'].str.contains(article, na=False)]

        if len(article_cases) == 0:
            continue

        logger.info(f"\nArticle {article} ({len(article_cases)} cases):")

        article_rates = []
        for language in LANGUAGES:
            lang_lower = language.lower()
            pred_col = f'{lang_lower}_pred_binary'
            viol_rate = article_cases[pred_col].mean() * 100
            article_rates.append(viol_rate)
            logger.info(f"  {language}: {viol_rate:.1f}%")

        article_range = max(article_rates) - min(article_rates)
        logger.info(f"  Range: {article_range:.1f} percentage points")

    # Save results
    output_dir = data_dir.parent / 'evaluations'
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f'language_bias_{mode_str}_n{n}_seed{random_seed}.csv'
    sampled_cases.to_csv(output_file, index=False)
    logger.info(f"\n✓ Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Run language bias experiment on ECHR cases")
    parser.add_argument('-n', type=int, default=25, help='Number of cases per category (default: 25)')
    parser.add_argument('--data_dir', type=str, default='data/real_cases/echr_new/unanimous',
                        help='Directory containing cases.csv')
    parser.add_argument('--simplification_model', type=str, default=DEFAULT_SIMPLIFICATION_MODEL,
                        help=f'Model for case processing and translation (default: {DEFAULT_SIMPLIFICATION_MODEL})')
    parser.add_argument('--judge_model', type=str, default=DEFAULT_JUDGE_MODEL,
                        help=f'Model for evaluation (default: {DEFAULT_JUDGE_MODEL})')
    parser.add_argument('--seed', type=int, default=42, help='Random seed (default: 42)')
    parser.add_argument('--anonymize_only', action='store_true',
                        help='Only anonymize without summarizing')
    parser.add_argument('--story_mode', action='store_true',
                        help='Use story-based narrative format')
    parser.add_argument('--word_range', type=str, default='150,200',
                        help='Word range for summarization (default: 150,200)')

    args = parser.parse_args()

    # Parse word range
    word_range = tuple(map(int, args.word_range.split(',')))

    # Run experiment
    asyncio.run(run_language_bias_experiment(
        n=args.n,
        data_dir=Path(args.data_dir),
        simplification_model=args.simplification_model,
        judge_model=args.judge_model,
        random_seed=args.seed,
        anonymize_only=args.anonymize_only,
        story_mode=args.story_mode,
        word_range=word_range,
    ))


if __name__ == "__main__":
    main()
