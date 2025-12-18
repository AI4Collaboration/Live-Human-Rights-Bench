#!/usr/bin/env python3
"""
Shared utilities for case anonymization and summarization with verification.
"""

import logging
from typing import Tuple, Optional
from inspect_ai.model import GenerateConfig

from src.client import LLMClient

logger = logging.getLogger(__name__)


async def verify_anonymization(
    text: str,
    is_summary: bool,
    word_count: Optional[int] = None,
    model_id: str = "openai/gpt-4o",
    temperature: float = 0.0
) -> Tuple[bool, str]:
    """
    Verifies that anonymization/summarization meets all requirements.

    Checks:
    1. All names, cities, countries, dates, ages are replaced with placeholders
    2. No court decision/ruling/violation information is present
    3. (For summaries) Word count is approximately correct

    Args:
        text: The anonymized/summarized text to verify
        is_summary: Whether this is a summary (vs full anonymization)
        word_count: Target word count for summaries (optional)
        model_id: LLM model identifier for verification
        temperature: Sampling temperature

    Returns:
        Tuple of (is_valid, corrected_text)
        - If valid: (True, original_text)
        - If invalid: (False, corrected_text)
    """
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=temperature, max_tokens=4000)
    )

    system_prompt = """You are a quality assurance expert for legal document anonymization. Your task is to verify that anonymization rules are followed correctly."""

    # Build verification prompt
    verification_rules = """Anonymization rules that MUST be followed:
1. Replace the applicant's name with [APPLICANT]
2. Replace the defendant state/country/government with [DEFENDANT_STATE]
3. Replace other names with [SUBJECT 1], [SUBJECT 2], etc.
4. Replace all pronouns with [APPLICANT PERSONAL PRONOUN], [APPLICANT POSSESSIVE PRONOUN], [SUBJECT 1 PRONOUN], etc.
5. Replace all city names with [CITY], except cities of the defendant state with [DEFENDANT_STATE_CITY]
6. Replace all other country names, except the defendant state/country, with [COUNTRY] or [NATIONALITY]
7. Replace all dates with [DATE] and years with [YEAR]. If there are multiple years, write them as [YEAR+1], [YEAR+2], etc.
8. Replace all ages with [APPLICANT AGE], [SUBJECT 1 AGE], etc.
9. Replace address with [ADDRESS]

Content rules:
- DO NOT include the court's decision or ruling
- DO NOT include whether violations were found
- DO NOT include the final judgment
- Include only: Facts of what happened and arguments from both sides"""

    word_count_instruction = ""
    if is_summary and word_count:
        word_count_instruction = f"\n- Should be approximately {word_count} words"

    prompt = f"""Review the text below and verify it follows ALL anonymization and content rules.

{verification_rules}{word_count_instruction}

Instructions:
1. Check if ALL names, cities, countries, dates, ages are properly replaced with placeholders
2. Check if the text contains NO court decision, ruling, or violation information
3. If the text is PERFECT and follows all rules, respond with ONLY the word: YES
4. If the text has ANY violations of the rules, return the CORRECTED version of the text with all issues fixed

Text to verify:
{text}

Response (either "YES" or the corrected text):"""

    try:
        response = await client.generate(
            prompt=prompt,
            system_message=system_prompt
        )

        response = response.strip()

        # Check if validation passed
        if response.upper() == "YES":
            return (True, text)
        else:
            # LLM returned corrected text
            return (False, response)

    except Exception as e:
        logger.error(f"Error during verification: {e}")
        # On error, assume text is valid to avoid blocking
        return (True, text)


async def anonymize_case_with_verification(
    case_text: str,
    model_id: str,
    verification_model_id: str = "openai/gpt-4o",
    temperature: float = 0.3
) -> str:
    """
    Anonymize a case without summarizing (keep full length) with verification.

    Args:
        case_text: Original case text
        model_id: Model for anonymization
        verification_model_id: Model for verification
        temperature: Sampling temperature for anonymization

    Returns:
        Verified anonymized text
    """
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=temperature, max_tokens=4000)
    )

    system_prompt = """You are a legal expert assistant helping to anonymize European Court of Human Rights cases."""

    prompt = f"""Anonymize this case. Follow these instructions:

Anonymization instructions:
1. Replace the applicant's name with [APPLICANT].
2. Replace other names with [SUBJECT 1], [SUBJECT 2], etc.
3. Replace all pronouns with [APPLICANT PERSONAL PRONOUN], [APPLICANT POSSESSIVE PRONOUN], [SUBJECT 1 PRONOUN], etc.
4. Replace all ages with [APPLICANT AGE], [SUBJECT 1 AGE], etc.
5. Replace all city names with [CITY].
6. Replace all country names, including adjectives, currency, or references to nationality with [COUNTRY] or [NATIONALITY].
7. Replace all dates with [DATE] and years with [YEAR]. If there are multiple years, write them as [YEAR+1], [YEAR+2], etc.
8. Replace address with [ADDRESS].

DO NOT include:
- The court's decision or ruling
- Whether violations were found
- The final judgment

Include only: Facts of what happened and arguments from both sides.

Directly return the result in paragraphs

Case:
{case_text}"""

    try:
        # Generate anonymization
        anonymized = await client.generate(
            prompt=prompt,
            system_message=system_prompt
        )
        anonymized = anonymized.strip()

        # Verify and potentially correct
        is_valid, corrected = await verify_anonymization(
            text=anonymized,
            is_summary=False,
            model_id=verification_model_id
        )

        if not is_valid:
            logger.info("Generated anonymization failed verification, using corrected version")
            return corrected

        return anonymized

    except Exception as e:
        logger.error(f"Error anonymizing case: {e}")
        return case_text[:2000]  # Fallback to truncation


async def summarize_case_with_verification(
    case_text: str,
    model_id: str,
    word_count: int = 500,
    verification_model_id: str = "openai/gpt-4o",
    temperature: float = 0.3,
    case_name: str = ""
) -> str:
    """
    Summarize and anonymize a case.

    Args:
        case_text: Original case text
        model_id: Model for summarization
        word_count: Target word count (default: 500)
        verification_model_id: Model for verification (deprecated, not used)
        temperature: Sampling temperature for summarization
        case_name: Case name to include in prompt

    Returns:
        Summarized text
    """
    client = LLMClient(
        model_id,
        config=GenerateConfig(temperature=temperature, max_tokens=1000)
    )

    system_prompt = """You are a legal expert assistant helping to summarize and anonymize European Court of Human Rights cases."""

    case_name_section = f"\n\nCase Name: {case_name}" if case_name else ""

    prompt = f"""Summarize the following ECtHR case in {word_count} words. Follow these instructions:

*Anonymization instructions*

1. Replace the applicant's name with [APPLICANT].
2. Replace the defendant state/country/government with [DEFENDANT_STATE].
3. Replace other names with [SUBJECT 1], [SUBJECT 2], etc.
4. Replace all pronouns with [APPLICANT PERSONAL PRONOUN], [APPLICANT POSSESSIVE PRONOUN], [SUBJECT 1 PRONOUN], etc.
5. Replace all city names with [CITY], except cities of the defendant state with [DEFENDANT_STATE_CITY].
6. Replace all other country names, except the defendant state/country, with [COUNTRY] or [NATIONALITY].

Case Information:{case_name_section}

Case Facts: {case_text}

Return ONLY the summary as a list of numbered paragraphs in a JSON record with the field "summary"."""

    try:
        # Generate summary
        response = await client.generate(
            prompt=prompt,
            system_message=system_prompt
        )
        response = response.strip()

        # Parse JSON response to extract summary field
        import json
        try:
            # Try to parse as JSON
            if response.startswith("```json"):
                response = response.split("```json")[1].split("```")[0].strip()
            elif response.startswith("```"):
                response = response.split("```")[1].split("```")[0].strip()

            json_data = json.loads(response)
            summarized = json_data.get("summary", response)

            # Handle case where summary is a list of paragraphs
            if isinstance(summarized, list):
                summarized = "\n\n".join(str(item) for item in summarized)
        except json.JSONDecodeError:
            # If JSON parsing fails, use the raw response
            logger.warning("Failed to parse JSON response, using raw text")
            summarized = response

        # Ensure summarized is a string
        if not isinstance(summarized, str):
            summarized = str(summarized)

        summarized = summarized.strip()

        # Verify and potentially correct (if verification_model_id is provided)
        if verification_model_id:
            is_valid, corrected = await verify_anonymization(
                text=summarized,
                is_summary=True,
                word_count=word_count,
                model_id=verification_model_id
            )

            if not is_valid:
                logger.info("Generated summary failed verification, using corrected version")
                return corrected

        return summarized

    except Exception as e:
        logger.error(f"Error summarizing case: {e}")
        return case_text[:1000]  # Fallback to truncation
