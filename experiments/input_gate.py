"""Bind current-cohort model inputs to a reviewed content release.

This is an identity gate, not a lexical classifier or a pretraining-overlap test.
Known benchmark judgments cannot be sent using stale source or summary text.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "data/processed/input_release.json"
CASES_PATH = ROOT / "data/processed/echr_unified.json"
MAX_CASE_CHARS = 50000


def text_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@lru_cache(maxsize=1)
def release():
    if not RELEASE_PATH.exists():
        return None
    result = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    return result if result.get("status") == "APPROVED" else None


@lru_cache(maxsize=1)
def cohort_ids():
    return {r["item_id"] for r in json.loads(CASES_PATH.read_text(encoding="utf-8"))}


def case_input(case, approved=None):
    text = (case.get("full_case_text_no_verdict") or case.get("verdict_free_text")
            or case.get("full_case_text") or "")[:MAX_CASE_CHARS]
    item_id = case["item_id"]
    if not text:
        raise ValueError(f"Empty case input: {item_id}")
    spec = release() if approved is None else approved
    known = item_id in (spec["source_inputs"] if spec else cohort_ids())
    if known:
        if spec is None:
            raise ValueError("Current benchmark inputs have not passed the leakage-release gate")
        if text_digest(text) != spec["source_inputs"][item_id]:
            raise ValueError(f"Stale or unreviewed source input for {item_id}; use the approved release")
    return text


def verify_summaries(mapping, approved=None):
    spec = release() if approved is None else approved
    known_ids = set(spec["source_inputs"]) if spec else cohort_ids()
    for item_id, values in mapping.items():
        if item_id not in known_ids:
            continue
        if spec is None:
            raise ValueError("Current benchmark summaries have not passed the leakage-release gate")
        expected = spec["summary_inputs"][item_id]
        actual = [text_digest(s) if isinstance(s, str) else None for s in values]
        if actual != expected:
            raise ValueError(f"Stale or unreviewed summary versions for {item_id}")


def verify_cases(cases):
    for case in cases:
        case_input(case)


def bind_run_inputs(directory, cases_path, summaries_path=None):
    """Never reuse pre-repair checkpoints as results of the new input release."""
    directory = Path(directory)
    spec = release()
    identity = {"cases_sha256_lf": file_digest(cases_path)}
    if spec and identity["cases_sha256_lf"] == spec["dataset_sha256_lf"]:
        if summaries_path and file_digest(summaries_path) != spec["summaries_sha256_lf"]:
            raise ValueError("Summary file does not match the approved input release")
        identity.update({"release_id": spec["release_id"],
                         "summaries_sha256_lf": spec["summaries_sha256_lf"]})
    elif summaries_path:
        identity["summaries_sha256_lf"] = file_digest(summaries_path)
    marker = directory / "input_identity.json"
    if marker.exists():
        if json.loads(marker.read_text(encoding="utf-8")) != identity:
            raise ValueError("This result directory belongs to different inputs; choose a new output directory")
        return identity
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Unversioned existing results may contain pre-repair checkpoints; choose a new output directory")
    directory.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(identity, indent=2)+"\n", encoding="utf-8")
    return identity
