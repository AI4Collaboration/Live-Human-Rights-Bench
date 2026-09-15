"""Read hash-bound review evidence without importing an API client."""
import hashlib
import json
from pathlib import Path


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_reviews(path):
    path = Path(path)
    records = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["status"] == "reviewed":
                records[(row["key"], row["input_sha256"])] = row
    manual = path.parent / "manual_adjudications.json"
    if manual.exists():
        for decision in json.loads(manual.read_text(encoding="utf-8")):
            key = (decision["item_id"], decision["input_sha256"])
            record = records.get(key)
            if record and decision["decision"] == "allow_sparse_factual_record":
                if record["result"]["conclusion"] or record["result"]["reasoning"]:
                    raise ValueError("Sparse-facts adjudication cannot override an outcome leak")
                records[key] = {**record, "result": {**record["result"], "insufficient_facts": False},
                                "manual_adjudication": decision}
    return records


def passed(record):
    return bool(record) and record.get("status") == "reviewed" and all(
        record.get("result", {}).get(k) is False
        for k in ("conclusion", "reasoning", "insufficient_facts"))


def accepted_generations(paths):
    completed = {}
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["status"] == "invalidated":
                key = (row["key"], row["source_sha256"])
                previous = completed.get(key)
                if previous and previous["summary_sha256"] == row["summary_sha256"]:
                    completed.pop(key)
                continue
            if row["status"] != "accepted":
                continue
            if digest(row["summary"]) != row["summary_sha256"]:
                raise ValueError("Generated summary hash mismatch")
            attempts = [a for a in row["attempts"] if a.get("status") == "accepted"]
            if len(attempts) != 1 or attempts[0]["text"] != row["summary"]:
                raise ValueError("Accepted summary must match exactly one recorded candidate")
            check = attempts[0].get("review")
            if not passed(check) or check["input_sha256"] != row["summary_sha256"]:
                raise ValueError("Accepted summary lacks a matching clean review")
            key = (row["key"], row["source_sha256"])
            if key in completed and completed[key]["summary_sha256"] != row["summary_sha256"]:
                if row.get("supersedes_summary_sha256") != completed[key]["summary_sha256"]:
                    raise ValueError(f"Conflicting accepted summaries for {row['key']}")
            completed[key] = row
    return completed
