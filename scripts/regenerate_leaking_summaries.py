"""Regenerate affected summaries only from source inputs that passed review.

The original model, user prompt, temperature, and 50,000-character cap are retained.
Every generated candidate and its review are recorded before acceptance. Canonical
files are never changed by this script; publication is a separate all-inputs gate.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import threading

from openai import OpenAI
from review_input_leakage import MODEL, digest, review
from leak_audit.reviews import read_reviews, passed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
from summaries import SUMMARY_TEMPLATE


def generate(client, task, journal=None, stop_file=None):
    prompt = SUMMARY_TEMPLATE.format(case_name=task["case_name"], full_text=task["source"])
    attempts, limit = [], 4000
    for attempt in range(4):
        if stop_file and stop_file.exists():
            return {**{k:v for k,v in task.items() if k != "source"},
                    "status": "paused", "generation_prompt_sha256": digest(prompt), "attempts": attempts}
        row = {"attempt": attempt, "max_tokens": limit}
        attempts.append(row)
        try:
            response = client.chat.completions.create(model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=1.0, max_tokens=limit)
            text = (response.choices[0].message.content or "").strip()
            row.update({"response_id": response.id, "text": text,
                "usage": response.usage.model_dump() if response.usage else {}})
            if journal:
                journal({"phase": "generation", "key": task["key"], "source_sha256": task["source_sha256"], **row})
            if not text:
                row["status"] = "empty"
                limit *= 2
                continue
            checked = review(client, {"key": task["key"], "item_id": task["item_id"],
                "version": task["version"], "text": text, "input_sha256": digest(text)})
            row["review"] = checked
            if journal:
                journal({"phase": "review", "key": task["key"], "source_sha256": task["source_sha256"],
                         "attempt": attempt, "review": checked})
            if passed(checked):
                row["status"] = "accepted"
                return {**{k:v for k,v in task.items() if k != "source"},
                    "status": "accepted", "summary": text, "summary_sha256": digest(text),
                    "generation_prompt_sha256": digest(prompt), "attempts": attempts}
            row["status"] = "review_rejected" if checked["status"] == "reviewed" else "review_error"
        except Exception as error:
            row["status"] = "transport_error"
            row["error_type"] = type(error).__name__
    return {**{k:v for k,v in task.items() if k != "source"},
            "status": "failed", "generation_prompt_sha256": digest(prompt), "attempts": attempts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--source-reviews", type=Path, required=True)
    parser.add_argument("--summary-reviews", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--completed-from", type=Path, nargs="+", default=[],
                        help="Additional completed checkpoint files; never repeat accepted slots")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--version-indices", type=int, nargs="+", default=[0],
                        help="Preselected original version indices; default: version 0 only")
    parser.add_argument("--stop-file", type=Path,
                        help="Creating this file pauses queued work without discarding completed calls")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--exclude-ids", nargs="+", default=[])
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if any(v < 0 for v in args.version_indices) or len(set(args.version_indices)) != len(args.version_indices):
        parser.error("Version indices must be distinct and nonnegative")
    stop_file = args.stop_file or args.out.parent / "PAUSE_REGENERATION"
    if stop_file.exists():
        print(json.dumps({"status": "paused", "stop_file": str(stop_file)}), flush=True)
        return
    old_rows = json.loads((ROOT / "data/processed/echr_unified.json").read_text(encoding="utf-8"))
    old_by = {r["item_id"]:r for r in old_rows}
    new_by = {r["item_id"]:r for r in json.loads(args.sources.read_text(encoding="utf-8"))}
    old_summaries = json.loads((ROOT / "data/processed/summaries_dsv41flash.json").read_text(encoding="utf-8"))["summaries"]
    sources_review = read_reviews(args.source_reviews)
    summaries_review = read_reviews(args.summary_reviews)
    blocked = {r["item_id"] for r in json.loads(args.sources.with_suffix(".provenance.json").read_text(encoding="utf-8"))["unresolved"]}
    completed = {}
    for checkpoint in [*args.completed_from, args.out]:
        if not checkpoint.exists():
            continue
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["status"] == "accepted":
                completed[(row["key"], row["source_sha256"])] = row
    tasks, deferred, required = [], 0, 0
    for item_id, case in new_by.items():
        if args.ids and item_id not in args.ids:
            continue
        if item_id in args.exclude_ids:
            continue
        source = case["full_case_text_no_verdict"][:50000]
        source_sha = digest(source)
        changed = source != old_by[item_id]["full_case_text_no_verdict"][:50000]
        source_ok = item_id not in blocked and passed(sources_review.get((item_id, source_sha)))
        for version, old in enumerate(old_summaries[item_id]):
            if version not in args.version_indices:
                continue
            key = f"{item_id}:{version}"
            old_review = summaries_review.get((key, digest(old)))
            needed = changed or (old_review is not None and not passed(old_review))
            if not needed:
                continue
            required += 1
            if (key, source_sha) in completed:
                continue
            if not source_ok:
                deferred += 1
                continue
            tasks.append({"key": key, "item_id": item_id, "version": version,
                "case_name": case["case_name"], "source": source, "source_sha256": source_sha,
                "previous_summary_sha256": digest(old),
                "reason": "source_input_changed" if changed else "summary_review_failed"})
    if args.limit:
        tasks = tasks[:args.limit]
    print(json.dumps({"required_slots_known": required, "eligible_pending": len(tasks),
        "deferred_source_review": deferred, "version_indices": args.version_indices,
        "execute": args.execute}), flush=True)
    if not args.execute or not tasks:
        return
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"],
                    timeout=180, max_retries=1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    accepted, failures = 0, 0
    journal_lock = threading.Lock()
    with args.out.with_suffix(".attempts.jsonl").open("a", encoding="utf-8") as trace, args.out.open("a", encoding="utf-8") as out, ThreadPoolExecutor(max_workers=args.workers) as pool:
        def journal(event):
            with journal_lock:
                trace.write(json.dumps({**event, "utc": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)+"\n")
                trace.flush()
        futures = {pool.submit(generate, client, task, journal, stop_file): task for task in tasks}
        for index, future in enumerate(as_completed(futures), 1):
            result = future.result()
            result.update({"model": MODEL, "temperature": 1.0,
                "max_source_characters": 50000, "utc": datetime.now(timezone.utc).isoformat()})
            out.write(json.dumps(result, ensure_ascii=False)+"\n")
            out.flush()
            accepted += result["status"] == "accepted"
            failures += result["status"] != "accepted"
            print(f"Regenerated {index}/{len(tasks)}; accepted {accepted}; failed {failures}", flush=True)


if __name__ == "__main__":
    main()
