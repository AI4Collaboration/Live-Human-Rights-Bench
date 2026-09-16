"""
Step 1a — Generate MFT (Minimum Functionality Test) minimal case versions.

For each verdict-free case, an LLM compresses the text into a single paragraph
containing ONLY the doctrinally material facts for the relevant article, with no
outcome cues. The evaluator later judges these minimal versions; the pass rate
is the competence floor of the Orders-of-Memorization hierarchy.

Input : data/processed/echr_livehrb_static_2k.json  (from build_contamination_input.py)
Output: data/mft/mft_cases.json
"""

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.queued_client import QueuedLLMClient
from lib.evaluation import make_custom_id
from lib.prompts import (
    MFT_GENERATION_PROMPT,
    ARTICLE_TITLES,
    ARTICLE_LEGAL_TESTS,
    ARTICLE_LEGAL_TEST_FALLBACK,
)

DEFAULT_GENERATOR_MODEL_ID = "openai/gpt-5.4-mini"

INPUT_PATH = REPO_ROOT / "data" / "processed" / "echr_livehrb_static_2k.json"
OUTPUT_PATH = REPO_ROOT / "data" / "mft" / "mft_cases.json"

# The adapter writes the verdict-free text into both full_case_text and
# full_case_text_no_verdict; we read the explicit no-verdict field.
SOURCE_TEXT_KEY = "full_case_text_no_verdict"


def get_article_legal_test(article: str) -> str:
    return ARTICLE_LEGAL_TESTS.get(article, ARTICLE_LEGAL_TEST_FALLBACK)


def build_generation_requests(cases, api_key, generator_model_id):
    requests = []
    for case in cases:
        article = case["article"]
        article_title = ARTICLE_TITLES.get(article, f"Article {article}")
        article_legal_test = get_article_legal_test(article)

        case_text = case.get(SOURCE_TEXT_KEY) or case.get("full_case_text", "")
        if not case_text:
            print(f"'{SOURCE_TEXT_KEY}' missing for {case.get('case_name', '?')}; "
                  f"skipping.")
            continue

        prompt = MFT_GENERATION_PROMPT.format(
            article=article,
            article_title=article_title,
            article_legal_test=article_legal_test,
            case_text=case_text,
        )
        # Row-unique id keyed on (item_id, article, group); a case judged under
        # several articles must NOT collide, or its article-specific MFT texts
        # overwrite each other.
        custom_id = make_custom_id(case, 0)
        requests.append({
            "custom_id": custom_id,
            "model": generator_model_id,
            "messages": [{"role": "user", "content": prompt}],
            "api_key": api_key,
            "backend": "openrouter",
            "max_tokens": 600,
            "temperature": 1.0,
        })
    return requests


def main():
    parser = argparse.ArgumentParser(description="Generate MFT minimal case versions")
    parser.add_argument("--max-workers", type=int, default=25)
    parser.add_argument("--input", type=Path, default=INPUT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--generator-model", default=DEFAULT_GENERATOR_MODEL_ID,
                        help=f"OpenRouter model id (default: {DEFAULT_GENERATOR_MODEL_ID})")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process the first N cases (cheap smoke test)")
    args = parser.parse_args()

    print("MFT VERSION GENERATION")
    print(f"Generator model: {args.generator_model}")
    print(f"Source field   : {SOURCE_TEXT_KEY}")
    print(f"Input          : {args.input}")
    print(f"Output         : {args.output}")
    print(f"Max workers    : {args.max_workers}")

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("\nERROR: OPENROUTER_API_KEY not set in environment / .env")
        sys.exit(1)

    if not args.input.exists():
        print(f"\nERROR: {args.input} not found. "
              f"Run scripts/build_contamination_input.py first.")
        sys.exit(1)

    print(f"\nLoading cases from {args.input}...")
    with open(args.input) as f:
        cases = json.load(f)
    print(f"Loaded {len(cases)} case-article pairs")
    if args.limit:
        cases = cases[:args.limit]
        print(f"[--limit] Restricting to first {len(cases)} cases")

    print("\nPreparing MFT generation requests...")
    requests = build_generation_requests(cases, api_key, args.generator_model)
    print(f"Prepared {len(requests)} requests")
    if not requests:
        print("\nERROR: No requests prepared. Check the source text field.")
        sys.exit(1)

    print("\nExecuting MFT generation...")
    client = QueuedLLMClient(max_workers=args.max_workers, timeout=180)

    def progress_callback(completed, total):
        if completed % 10 == 0 or completed == total:
            print(f" Progress: {completed}/{total} ({100 * completed / total:.1f}%)")

    results = client.execute_all(requests, progress_callback=progress_callback)

    print("\nProcessing results...")
    output = []
    success_count = 0
    error_count = 0
    for case in cases:
        custom_id = make_custom_id(case, 0)
        mft_text = results.get(custom_id, "")
        if mft_text and not mft_text.startswith("ERROR:"):
            mft_text = mft_text.strip()
            status = "success"
            success_count += 1
        else:
            print(f"Generation failed for {case.get('case_name', '?')}: "
                  f"{mft_text[:120] if mft_text else 'empty response'}")
            mft_text = ""
            status = "error"
            error_count += 1

        output.append({
            "item_id": case.get("item_id", ""),
            "case_name": case["case_name"],
            "article": case["article"],
            "violation_label": case["violation_label"],
            # Carry stratification axes through so downstream analysis can slice
            # MFT results by group / country / time without a re-join.
            "respondent": case.get("respondent", ""),
            "group": case.get("group", ""),
            "decision_date": case.get("decision_date", ""),
            "importance": case.get("importance", ""),
            "mft_text": mft_text,
            "mft_generation_status": status,
            "source_text_key": SOURCE_TEXT_KEY,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {success_count}/{len(cases)} MFT versions to {args.output}")
    if error_count:
        print(f"{error_count} generation errors (saved with empty mft_text)")


if __name__ == "__main__":
    main()
