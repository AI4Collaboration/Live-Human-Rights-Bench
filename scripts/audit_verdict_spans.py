#!/usr/bin/env python3
"""Quote the sentences that give the verdict away, one pass over the evaluation inputs.

Read-only: the dataset is never edited here, and nothing downstream consumes the output
until a human pass has adjudicated it. What this produces is evidence, not a rate.

    python scripts/audit_verdict_spans.py \
      --cases data/processed/echr_unified.json \
      --model deepseek/deepseek-v4.1-flash \
      --base-url https://openrouter.ai/api/v1 \
      --api-key-env OPENROUTER_API_KEY \
      --out data/audits/verdict_spans/dsv41flash.json

The unit is the case-article instance, not the judgment. A judgment appears under
several articles -- 1,000 instances over 947 judgments -- and a sentence that resolves
Article 6 is not leakage for the Article 3 row scored from the same text. Auditing per
judgment would answer a question nobody asked of the data.

Each reply is checked against the source before it counts, so an unlocatable quote is
dropped and reported rather than scored. Work is checkpointed per instance, so an
interrupted run resumes. Failed calls are deliberately not checkpointed: they produced
nothing usable, so a rerun should retry them.
"""

import argparse, hashlib, json, os, sys, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments"))
from checkpoint import Checkpoint                                   # noqa: E402
from scoring import MAX_CASE_CHARS                                  # noqa: E402
from verdict_spans import (SPAN_TEMPLATE, TIERS, parse_spans,       # noqa: E402
                           tier_of, verify)

ATTEMPTS = 3


def scan(client, model, case, max_tokens):
    """Spans for one instance, escalating the token ceiling when a reply comes back empty.

    Reasoning models spend their budget before emitting any content, so a ceiling sized
    for the visible answer returns nothing, and retrying at the same ceiling buys the
    same nothing again. This is the failure that cost $8 in three minutes on the summary
    build; each retry here raises the limit instead of repeating the call.
    """
    prompt = SPAN_TEMPLATE.format(case_name=case["case_name"], article=case["article"],
                                  text=case["text"])
    limit, last = max_tokens, "ERROR: no attempt made"
    usage = {"prompt": 0, "completion": 0}
    for attempt in range(ATTEMPTS):
        try:
            response = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}],
                temperature=0.0, max_tokens=limit)
            if response.usage:
                usage["prompt"] += response.usage.prompt_tokens or 0
                usage["completion"] += response.usage.completion_tokens or 0
            reply = (response.choices[0].message.content or "").strip()
            if not reply:
                last, limit = "ERROR: empty reply", limit * 2
                continue
            # An empty array is an answer, and the most common correct one. Only a
            # reply that parses to nothing at all while claiming content is a failure.
            spans = parse_spans(reply)
            if not spans and "[" not in reply:
                last = f"ERROR: unreadable reply: {reply[:80]}"
                continue
            kept, dropped = verify(spans, case["text"])
            return {"spans": kept, "unverifiable_quotes": dropped}, None, usage
        except Exception as error:
            last = f"ERROR: {error}"
            time.sleep(2 * (attempt + 1))
    return None, last, usage


def digest(raw):
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="data/processed/echr_unified.json")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--api-key-env", default="OPENROUTER_API_KEY")
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=2000)
    parser.add_argument("--limit", type=int, help="first N instances, for a dry run")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        sys.exit(f"ERROR: set {args.api_key_env}")

    raw = open(args.cases, "rb").read()
    rows = json.loads(raw)
    cases = [{"item_id": row["item_id"], "case_name": row["case_name"],
              "article": row.get("article_full") or row["article"],
              "violation_label": row["violation_label"],
              # The prefix, not the stored text: this is what the runner sends, and
              # auditing anything else measures a document no model was shown.
              "text": (row.get("full_case_text_no_verdict")
                       or row.get("verdict_free_text") or "")[:MAX_CASE_CHARS]}
             for row in rows]
    if args.limit:
        cases = cases[:args.limit]

    truncated = sum(1 for row in rows
                    if len(row.get("full_case_text_no_verdict") or "") > MAX_CASE_CHARS)
    print(f"Detector: {args.model}   instances: {len(cases)}   "
          f"prefix: {MAX_CASE_CHARS:,} characters ({truncated} judgments truncated)\n")

    checkpoint = Checkpoint(args.out + ".jsonl", enabled=not args.no_resume)
    if checkpoint.resumed:
        print(f"Resuming: {checkpoint.resumed} already recorded\n")
    client = OpenAI(base_url=args.base_url, api_key=api_key)

    pending = [case for case in cases
               if not checkpoint.done(Checkpoint.key("spans", case["item_id"], case["article"]))]
    done = failed = 0
    totals = {"prompt": 0, "completion": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(scan, client, args.model, case, args.max_tokens): case
                   for case in pending}
        for future in as_completed(futures):
            case = futures[future]
            result, error, usage = future.result()
            totals["prompt"] += usage["prompt"]
            totals["completion"] += usage["completion"]
            done += 1
            if result is None:
                failed += 1
                print(f"\n  {case['case_name'][:40]} art {case['article']}: {error[:90]}")
            else:
                checkpoint.record(
                    Checkpoint.key("spans", case["item_id"], case["article"]),
                    {"item_id": case["item_id"], "case_name": case["case_name"],
                     "article": case["article"], "violation_label": case["violation_label"],
                     "tier": tier_of(result["spans"]), **result})
            print(f"\r  {done}/{len(pending)} | failed {failed}", end="", flush=True)
    print()
    checkpoint.close()

    recorded = checkpoint.rows()
    tiers = Counter(row["tier"] for row in recorded)
    categories = Counter(span["category"] for row in recorded for span in row["spans"])
    report = {
        "scope": "Prompt-level verdict leakage in the evaluated prefix; not pretraining contamination",
        "status": "CANDIDATES_WITH_EVIDENCE_NOT_AN_ADJUDICATED_RATE",
        "detector": args.model,
        "dataset": args.cases,
        "dataset_sha256_lf": digest(raw),
        "max_case_chars": MAX_CASE_CHARS,
        "instances_scanned": len(recorded),
        "instances_failed": failed,
        "tiers": dict(tiers),
        "categories": dict(categories),
        # A quote that is not in the source was written, not found. Kept visible
        # because a detector that invents evidence is worth knowing about before its
        # output is read as a leak rate.
        "unverifiable_quotes": sum(len(row["unverifiable_quotes"]) for row in recorded),
        "prompt_tokens": totals["prompt"], "completion_tokens": totals["completion"],
        "tier_definitions": TIERS,
        "next_step": ("Human adjudication of a stratified sample against these spans, "
                      "then an ablation that blanks them and rescores, which is what "
                      "decides whether the leak is material."),
        "rows": sorted(recorded, key=lambda row: (row["tier"] != "leak", row["case_name"])),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({key: report[key] for key in
                      ("instances_scanned", "instances_failed", "tiers", "categories",
                       "unverifiable_quotes")}, indent=2))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
