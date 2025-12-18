"""
Download and process latest ECHR cases from TSV file.

This script:
1. Reads latest_echr_cases.tsv
2. Downloads HTML for each case from HUDOC
3. Extracts the FACTS section
4. Saves to JSONL format with violations data
"""

import asyncio
import csv
import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Constants
HUDOC_HTML_URL = "https://hudoc.echr.coe.int/app/conversion/docx/html/body?library=ECHR&id={item_id}"
HUDOC_API_URL = "https://hudoc.echr.coe.int/app/query/results?query=(contentsitename=ECHR)%20AND%20(itemid=%22{item_id}%22)&select=itemid,importance,separateopinion&sort=&start=0&length=1"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
REQUEST_TIMEOUT = 30  # seconds
RATE_LIMIT_DELAY = 1  # seconds between requests


def parse_article_list(article_str: str) -> List[str]:
    """Parse article string from TSV (e.g., "['8', '5']" -> ['8', '5'])."""
    if not article_str or article_str == '[]':
        return []

    # Remove brackets and quotes, split by comma
    article_str = article_str.strip("[]")
    articles = [a.strip().strip("'\"") for a in article_str.split(',')]
    return [a for a in articles if a]


def extract_facts_section(html_content: str) -> Optional[str]:
    """
    Extract the FACTS section from ECHR case HTML.

    The facts section starts with "FACTS" heading and ends with either:
    - "RELEVANT LEGAL FRAMEWORK"
    - "THE LAW"
    - Other major section headings
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all text content
    text = soup.get_text()

    # Check if this is a non-English case
    non_english_indicators = [
        "The text is only available in",
        "Le texte n'est disponible",
        "available only in French",
        "disponible uniquement en français",
    ]
    for indicator in non_english_indicators:
        if indicator in text:
            logger.warning("Non-English case detected")
            return None

    # Look for FACTS section
    # Common patterns: "THE FACTS", "I. THE FACTS", "FACTS", "I.  THE FACTS"
    facts_pattern = r'(?:I\.?\s*)?(?:THE\s+)?FACTS'

    # Common end patterns
    end_patterns = [
        r'(?:II\.?\s*)?(?:THE\s+)?RELEVANT\s+LEGAL\s+FRAMEWORK',
        r'(?:II\.?\s*)?(?:THE\s+)?LAW',
        r'(?:II\.?\s*)?RELEVANT\s+DOMESTIC\s+LAW',
        r'(?:III\.?\s*)?(?:THE\s+)?LAW',
    ]

    # Find FACTS section
    facts_match = re.search(facts_pattern, text, re.IGNORECASE)
    if not facts_match:
        logger.warning("Could not find FACTS section")
        return None

    facts_start = facts_match.end()

    # Find end of FACTS section
    facts_end = len(text)
    for end_pattern in end_patterns:
        end_match = re.search(end_pattern, text[facts_start:], re.IGNORECASE)
        if end_match:
            facts_end = facts_start + end_match.start()
            break

    # Extract facts text
    facts_text = text[facts_start:facts_end].strip()

    # Clean up the text (remove excessive whitespace)
    facts_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', facts_text)  # Multiple newlines to double newline
    facts_text = re.sub(r' +', ' ', facts_text)  # Multiple spaces to single space

    if len(facts_text) < 100:  # Sanity check
        logger.warning(f"Facts section too short ({len(facts_text)} chars)")
        return None

    return facts_text


async def fetch_metadata(
    session: aiohttp.ClientSession,
    item_id: str,
    semaphore: asyncio.Semaphore
) -> Tuple[Optional[str], Optional[bool]]:
    """
    Fetch case metadata from HUDOC API.

    Returns:
        Tuple of (importance level, split_vote boolean) or (None, None) if fetch failed
    """
    url = HUDOC_API_URL.format(item_id=item_id)

    async with semaphore:  # Limit concurrent requests
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        data = await response.json()
                        await asyncio.sleep(RATE_LIMIT_DELAY)  # Rate limiting

                        # Parse API response
                        if data.get('results') and len(data['results']) > 0:
                            result = data['results'][0]
                            columns = result.get('columns', {})

                            # Extract importance (1-4, or None if not set)
                            importance = columns.get('importance')
                            if importance and importance.strip():
                                importance = str(importance.strip())
                            else:
                                importance = None

                            # Extract split_vote (separateopinion field)
                            # "TRUE" means there are dissenting/separate opinions
                            separate_opinion = columns.get('separateopinion', '').upper()
                            split_vote = separate_opinion == 'TRUE'

                            return importance, split_vote
                        else:
                            logger.warning(f"No metadata found for {item_id}")
                            return None, None

                    elif response.status == 404:
                        logger.warning(f"Metadata for {item_id} not found (404)")
                        return None, None
                    else:
                        logger.warning(f"Metadata API for {item_id} returned status {response.status}")

            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching metadata for {item_id} (attempt {attempt + 1}/{MAX_RETRIES})")
            except Exception as e:
                logger.error(f"Error fetching metadata for {item_id}: {e}")

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        logger.error(f"Failed to fetch metadata for {item_id} after {MAX_RETRIES} attempts")
        return None, None


async def download_case(
    session: aiohttp.ClientSession,
    item_id: str,
    semaphore: asyncio.Semaphore
) -> Optional[str]:
    """
    Download case HTML from HUDOC with retries.

    Returns:
        HTML content or None if download failed
    """
    url = HUDOC_HTML_URL.format(item_id=item_id)

    async with semaphore:  # Limit concurrent requests
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        html = await response.text()
                        await asyncio.sleep(RATE_LIMIT_DELAY)  # Rate limiting
                        return html
                    elif response.status == 404:
                        logger.warning(f"Case {item_id} not found (404)")
                        return None
                    else:
                        logger.warning(f"Case {item_id} returned status {response.status}")

            except asyncio.TimeoutError:
                logger.warning(f"Timeout downloading {item_id} (attempt {attempt + 1}/{MAX_RETRIES})")
            except Exception as e:
                logger.error(f"Error downloading {item_id}: {e}")

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        logger.error(f"Failed to download {item_id} after {MAX_RETRIES} attempts")
        return None


async def process_case(
    session: aiohttp.ClientSession,
    case_data: Dict,
    semaphore: asyncio.Semaphore
) -> Optional[Dict]:
    """
    Process a single case: download HTML, extract facts, fetch metadata, create output record.

    Args:
        session: aiohttp session
        case_data: Dict with item_id, case_name, date, articles, violations
        semaphore: Semaphore for rate limiting

    Returns:
        Dict with case data or None if processing failed
    """
    item_id = case_data['item_id']

    logger.info(f"Processing {item_id}: {case_data['case_name']}")

    # Fetch metadata and HTML in parallel
    metadata_task = fetch_metadata(session, item_id, semaphore)
    html_task = download_case(session, item_id, semaphore)

    importance, split_vote = await metadata_task
    html = await html_task

    if html is None:
        return None

    # Extract facts
    facts = extract_facts_section(html)
    if facts is None:
        logger.warning(f"Could not extract facts for {item_id}")
        return None

    # Parse articles and violations
    articles = parse_article_list(case_data['articles'])
    violations = parse_article_list(case_data['violations'])

    # Determine violation label
    violation_label = 'violation' if len(violations) > 0 else 'no_violation'

    # Create output record
    record = {
        'item_id': item_id,
        'case_name': case_data['case_name'],
        'judgement_date': case_data['date'],
        'importance': importance,  # Case importance level (1-4)
        'split_vote': split_vote,  # Whether case has dissenting opinions
        'articles': articles,  # Alleged violations
        'violations': violations,  # Actual violations found by court
        'violation_label': violation_label,
        'facts': facts,
        'facts_word_count': len(facts.split()),
    }

    logger.info(f"✓ {item_id}: {len(facts)} chars, {record['facts_word_count']} words, "
                f"importance={importance}, split_vote={split_vote}, "
                f"articles={articles}, violations={violations}")

    return record


async def download_all_cases(tsv_path: Path, output_path: Path, max_concurrent: int = 5):
    """
    Download and process all cases from TSV file.

    Args:
        tsv_path: Path to input TSV file
        output_path: Path to output JSONL file
        max_concurrent: Maximum number of concurrent downloads
    """
    # Read TSV file
    logger.info(f"Reading cases from {tsv_path}")
    cases = []
    with open(tsv_path, 'r', encoding='utf-8') as f:
        # Check if first line is a header or data
        first_line = f.readline()
        f.seek(0)  # Reset to start

        # If first line starts with item_id pattern (001-), it's data not a header
        if first_line.startswith('001-'):
            # No header row, provide column names
            reader = csv.DictReader(f, delimiter='\t',
                                   fieldnames=['item_id', 'case_name', 'date', 'articles', 'violations'])
        else:
            # Has header row
            reader = csv.DictReader(f, delimiter='\t')

        for row in reader:
            cases.append(row)

    logger.info(f"Found {len(cases)} cases to process")

    # Create semaphore for rate limiting
    semaphore = asyncio.Semaphore(max_concurrent)

    # Process all cases
    start_time = time.time()
    successful_cases = []
    failed_cases = []

    async with aiohttp.ClientSession() as session:
        tasks = [process_case(session, case, semaphore) for case in cases]
        results = await asyncio.gather(*tasks)

        for case, result in zip(cases, results):
            if result is not None:
                successful_cases.append(result)
            else:
                failed_cases.append(case['item_id'])

    # Save results to JSONL
    logger.info(f"\nSaving {len(successful_cases)} cases to {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in successful_cases:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    # Print summary
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 80)
    logger.info("DOWNLOAD COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total cases: {len(cases)}")
    logger.info(f"Successful: {len(successful_cases)}")
    logger.info(f"Failed: {len(failed_cases)}")
    logger.info(f"Success rate: {len(successful_cases) / len(cases) * 100:.1f}%")
    logger.info(f"Time elapsed: {elapsed:.1f}s")
    logger.info(f"Output saved to: {output_path}")

    if failed_cases:
        logger.info(f"\nFailed cases ({len(failed_cases)}):")
        for item_id in failed_cases[:20]:  # Show first 20
            logger.info(f"  - {item_id}")
        if len(failed_cases) > 20:
            logger.info(f"  ... and {len(failed_cases) - 20} more")

    # Print violation statistics
    violation_counts = {}
    no_violation_count = 0
    for case in successful_cases:
        if case['violation_label'] == 'violation':
            for article in case['violations']:
                violation_counts[article] = violation_counts.get(article, 0) + 1
        else:
            no_violation_count += 1

    logger.info("\nViolation statistics:")
    logger.info(f"  No violations: {no_violation_count}")
    for article in sorted(violation_counts.keys()):
        logger.info(f"  Article {article}: {violation_counts[article]} violations")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download and process latest ECHR cases from TSV file"
    )
    parser.add_argument(
        "--tsv",
        type=str,
        default="latest_echr_cases.tsv",
        help="Path to input TSV file (default: latest_echr_cases.tsv)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/real_cases/latest_echr_cases.jsonl",
        help="Path to output JSONL file (default: data/real_cases/latest_echr_cases.jsonl)"
    )
    parser.add_argument(
        "--max_concurrent",
        type=int,
        default=5,
        help="Maximum concurrent downloads (default: 5)"
    )

    args = parser.parse_args()

    tsv_path = Path(args.tsv)
    output_path = Path(args.output)

    if not tsv_path.exists():
        logger.error(f"TSV file not found: {tsv_path}")
        return

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run async download
    asyncio.run(download_all_cases(tsv_path, output_path, args.max_concurrent))


if __name__ == "__main__":
    main()
