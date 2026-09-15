"""Create or replace the single approved summary for selected judgments.

This is the repository's only summary-generation entry point. The fixed summarizer,
prompt, temperature, and 50,000-character cap are retained. Every candidate receives
a deterministic screen and either direct review or an optional model review before
acceptance. Canonical files are changed only by the separate publication gate.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import threading
import subprocess

from openai import OpenAI
from dotenv import dotenv_values, load_dotenv
from review_input_leakage import digest, review
from leak_audit.reviews import read_reviews, passed

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "4a1ba1117a047dac7553ca2cfd3100a18171a841"
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "experiments"))
from summaries import (
    LEAK_SAFE_SUMMARY_TEMPLATE,
    appears_truncated,
    asserts_outcome,
    narrates_current_court_assessment,
)

MODEL = "deepseek/deepseek-v4.1-flash"
DEFAULT_REVIEW_MODEL = "anthropic/claude-opus-4.6"


def generate(client, task, review_model, journal=None, stop_file=None):
    prompt = LEAK_SAFE_SUMMARY_TEMPLATE.format(case_name=task["case_name"], full_text=task["source"])
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
            finish_reason = response.choices[0].finish_reason
            row.update({"response_id": response.id, "text": text,
                "finish_reason": finish_reason,
                "usage": response.usage.model_dump() if response.usage else {}})
            if journal:
                journal({"phase": "generation", "key": task["key"], "source_sha256": task["source_sha256"], **row})
            if not text:
                row["status"] = "empty"
                limit *= 2
                continue
            if finish_reason != "stop":
                row["status"] = "truncated"
                limit *= 2
                continue
            if appears_truncated(text):
                row["status"] = "truncated_text_rejected"
                limit *= 2
                continue
            if asserts_outcome(text, task["source"]) or narrates_current_court_assessment(text):
                row["status"] = "deterministic_leak_rejected"
                if journal:
                    journal({"phase": "deterministic_review", "key": task["key"],
                             "source_sha256": task["source_sha256"], "attempt": attempt,
                             "status": row["status"]})
                continue
            if review_model is None:
                row["status"] = "pending_manual_review"
                return {**{k:v for k,v in task.items() if k != "source"},
                    "status": "pending_manual_review", "summary": text,
                    "summary_sha256": digest(text), "generation_prompt_sha256": digest(prompt),
                    "attempts": attempts}
            checked = review(client, {"key": task["key"], "item_id": task["item_id"],
                "version": task["version"], "text": text, "input_sha256": digest(text)},
                model=review_model)
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


def approve_manual_candidates(path, item_ids):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    pending = {}
    active = {}
    for row in rows:
        key = (row.get("key"), row.get("source_sha256"))
        if row.get("status") == "accepted":
            active[key] = row
        elif row.get("status") == "invalidated" and key in active:
            if active[key].get("summary_sha256") == row.get("summary_sha256"):
                active.pop(key)
        elif row.get("status") == "pending_manual_review":
            pending[row["item_id"]] = row
    missing = set(item_ids) - set(pending)
    if missing:
        raise ValueError(f"No pending manual candidate for: {sorted(missing)}")
    additions = []
    for item_id in item_ids:
        row = pending[item_id]
        if (appears_truncated(row["summary"])
                or asserts_outcome(row["summary"], "")
                or narrates_current_court_assessment(row["summary"])):
            raise ValueError(f"Candidate still triggers leakage screen: {item_id}")
        key = (row["key"], row["source_sha256"])
        if key in active and active[key]["summary_sha256"] != row["summary_sha256"]:
            additions.append({"status": "invalidated", "key": row["key"],
                "item_id": item_id, "source_sha256": row["source_sha256"],
                "summary_sha256": active[key]["summary_sha256"],
                "reason": "direct review found incomplete or unsafe content",
                "utc": datetime.now(timezone.utc).isoformat()})
        accepted = {**row, "status": "accepted", "review_model": "direct_manual_review",
                    "manual_review": {"conclusion": False, "reasoning": False,
                                      "insufficient_facts": False,
                                      "method": "sentence-level comparison with approved factual source"},
                    "utc": datetime.now(timezone.utc).isoformat()}
        accepted_attempts = []
        for attempt in row["attempts"]:
            attempt = dict(attempt)
            if attempt.get("text") == row["summary"]:
                attempt["status"] = "accepted"
                attempt["review"] = {"status": "reviewed", "input_sha256": row["summary_sha256"],
                    "result": {"conclusion": False, "reasoning": False,
                               "insufficient_facts": False, "evidence": []},
                    "reviewer": "direct_manual_review"}
            accepted_attempts.append(attempt)
        accepted["attempts"] = accepted_attempts
        additions.append(accepted)
    with path.open("a", encoding="utf-8") as output:
        for row in additions:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"approved": len(item_ids), "invalidations":
        sum(row["status"] == "invalidated" for row in additions)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--source-reviews", type=Path, required=True)
    parser.add_argument("--summary-reviews", type=Path, required=True)
    parser.add_argument("--env-file", type=Path,
                        help="Existing ignored dotenv file containing OPENROUTER_API_KEY")
    parser.add_argument("--provenance", type=Path,
                        default=ROOT / "data/audits/leakage_20260915/proposed_sources.provenance.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-commit", default=BASE_COMMIT,
                        help="Immutable original inputs, also when rerun after publication")
    parser.add_argument("--completed-from", type=Path, nargs="+", default=[],
                        help="Additional completed checkpoint files; never repeat accepted slots")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--stop-file", type=Path,
                        help="Creating this file pauses queued work without discarding completed calls")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--force-ids", nargs="+", default=[])
    parser.add_argument("--exclude-ids", nargs="+", default=[])
    parser.add_argument("--review-model", default=DEFAULT_REVIEW_MODEL)
    parser.add_argument("--manual-review", action="store_true",
                        help="save locally screened candidates for direct human review")
    parser.add_argument("--approve-ids", nargs="+",
                        help="record direct review approval for pending candidates")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.env_file:
        for name, value in dotenv_values(args.env_file).items():
            if value:
                os.environ.setdefault(name.lstrip("\ufeff"), value)
    if args.approve_ids:
        approve_manual_candidates(args.out, args.approve_ids)
        return
    stop_file = args.stop_file or args.out.parent / "PAUSE_REGENERATION"
    if stop_file.exists():
        print(json.dumps({"status": "paused", "stop_file": str(stop_file)}), flush=True)
        return
    def original(path):
        return json.loads(subprocess.check_output(["git", "show", f"{args.base_commit}:{path}"], cwd=ROOT))
    old_rows = original("data/processed/echr_unified.json")
    old_by = {r["item_id"]:r for r in old_rows}
    new_by = {r["item_id"]:r for r in json.loads(args.sources.read_text(encoding="utf-8"))}
    old_summaries = original("data/processed/summaries_dsv41flash.json")["summaries"]
    current_summaries = json.loads((ROOT / "data/processed/summaries_dsv41flash.json").read_text(
        encoding="utf-8"))["summaries"]
    sources_review = read_reviews(args.source_reviews)
    postcut_reviews = ROOT / "data/audits/verdict_spans/postcut_source_reviews.jsonl"
    if postcut_reviews.exists():
        sources_review.update(read_reviews(postcut_reviews))
    summaries_review = read_reviews(args.summary_reviews)
    blocked = {r["item_id"] for r in json.loads(args.provenance.read_text(encoding="utf-8"))["unresolved"]}
    forced = set(args.force_ids)
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
        old = old_summaries[item_id][0]
        key = f"{item_id}:0"
        old_review = summaries_review.get((key, digest(old)))
        needed = changed or not passed(old_review) or item_id in forced
        if not needed:
            continue
        required += 1
        if (key, source_sha) in completed and item_id not in forced:
            continue
        if not source_ok:
            deferred += 1
            continue
        reason = ("forced_semantic_second_pass" if item_id in forced else
                  "source_input_changed" if changed else "summary_review_failed")
        tasks.append({"key": key, "item_id": item_id, "version": 0,
            "case_name": case["case_name"], "source": source, "source_sha256": source_sha,
            "previous_summary_sha256": digest(old),
            "supersedes_summary_sha256": digest(current_summaries[item_id][0]) if item_id in forced else None,
            "generation_prompt_version": "leak-safe-v3", "reason": reason})
    if args.limit:
        tasks = tasks[:args.limit]
    print(json.dumps({"required_slots_known": required, "eligible_pending": len(tasks),
        "deferred_source_review": deferred, "summaries_per_judgment": 1,
        "execute": args.execute}), flush=True)
    if not args.execute or not tasks:
        return
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"],
                    timeout=180, max_retries=1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    accepted, failures, paused = 0, 0, 0
    journal_lock = threading.Lock()
    with args.out.with_suffix(".attempts.jsonl").open("a", encoding="utf-8") as trace, args.out.open("a", encoding="utf-8") as out, ThreadPoolExecutor(max_workers=args.workers) as pool:
        def journal(event):
            with journal_lock:
                trace.write(json.dumps({**event, "utc": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)+"\n")
                trace.flush()
        review_model = None if args.manual_review else args.review_model
        futures = {pool.submit(generate, client, task, review_model, journal, stop_file): task for task in tasks}
        for index, future in enumerate(as_completed(futures), 1):
            result = future.result()
            result.update({"model": MODEL, "temperature": 1.0,
                "review_model": review_model or "direct_manual_review",
                "max_source_characters": 50000,
                "utc": datetime.now(timezone.utc).isoformat()})
            out.write(json.dumps(result, ensure_ascii=False)+"\n")
            out.flush()
            accepted += result["status"] == "accepted"
            failures += result["status"] == "failed"
            paused += result["status"] == "paused"
            print(f"Processed {index}/{len(tasks)}; accepted {accepted}; failed {failures}; paused {paused}", flush=True)


if __name__ == "__main__":
    main()
