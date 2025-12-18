"""Configuration for real ECHR case experiments."""

# Simplification configuration
SIMPLIFICATION_CONFIG = {
    "word_range": (150, 200),  # (min_words, max_words)
    "temperature": 0.3,
    "preserve_elements": [
        "factual_claims",
        "counterclaims",
        "contested_points",
        "relevant_context",
    ],
    "remove_elements": [
        "procedural_dates",
        "legal_jargon",
        "citation_references",
        "paragraph_numbers",
    ],
}

# Helper function to get directory name from word range
def get_simplified_dir_name(word_range):
    """Get directory name for a given word range.

    Args:
        word_range: Tuple of (min_words, max_words)

    Returns:
        Directory name like 'simplified_150_200'
    """
    min_words, max_words = word_range
    return f"simplified_{min_words}_{max_words}"


def get_cache_dir_name(anonymize_only: bool, story_mode: bool, word_range: tuple, model_id: str) -> str:
    """Get cache directory name based on processing mode and model.

    Args:
        anonymize_only: If True, only anonymization (no summarization)
        story_mode: If True, story-based narrative format
        word_range: Tuple of (min_words, max_words) for summarization
        model_id: Model identifier (e.g., 'openai/gpt-4o')

    Returns:
        Directory name like 'anonymized_full_gpt-4o' or 'simplified_150_200_gpt-4o'
    """
    # Extract model name from model_id (e.g., 'openai/gpt-4o' -> 'gpt-4o')
    model_name = model_id.split('/')[-1] if '/' in model_id else model_id
    # Replace any special characters that might cause filesystem issues
    model_name = model_name.replace(':', '-').replace('.', '-')

    if anonymize_only:
        return f"anonymized_full_{model_name}"
    elif story_mode:
        word_range_str = f"{word_range[0]}_{word_range[1]}"
        return f"story_{word_range_str}_{model_name}"
    else:
        word_range_str = f"{word_range[0]}_{word_range[1]}"
        return f"simplified_{word_range_str}_{model_name}"

# Articles to test (from provided cases)
ECHR_TEST_ARTICLES = [
    "3",  # Torture - high bias expected
    "5",  # Liberty
    "6",  # Fair trial
    "8",  # Privacy
    "10", # Expression
    "11", # Assembly
    "P1-1",  # Property - lower bias expected
    "P1-2",  # Education
]

# Default model for simplification
DEFAULT_SIMPLIFICATION_MODEL = "openai/gpt-4o"

# Default judge model for evaluation
DEFAULT_JUDGE_MODEL = "openai/gpt-4o"

# Paths
DATA_DIR = "data/real_cases/echr"
METADATA_FILE = f"{DATA_DIR}/metadata.csv"
ORIGINAL_DIR = f"{DATA_DIR}/original"
SIMPLIFIED_DIR = f"{DATA_DIR}/simplified"
EVALUATIONS_DIR = f"{DATA_DIR}/evaluations"
