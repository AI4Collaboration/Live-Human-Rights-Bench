"""Validate the active cohort by content and target semantics."""

from functools import lru_cache
import json
from pathlib import Path

try:
    from .targets import provision_name, target_key, target_question
except ImportError:
    from targets import provision_name, target_key, target_question


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "configs/evaluation_dataset.json"
CASES_PATH = ROOT / "data/processed/echr_unified.json"
SUMMARIES_PATH = ROOT / "data/processed/summaries_dsv41flash.json"
MAX_CASE_CHARS = 50000
REQUIRED_TARGET_FIELDS = {
    "target_respondent_code", "target_respondent", "target_provision",
    "target_issue", "target_aspect", "target_question", "target_status",
}


@lru_cache(maxsize=1)
def manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def canonical_cases():
    rows = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return {target_key(row): row for row in rows}


@lru_cache(maxsize=1)
def canonical_summaries():
    return json.loads(SUMMARIES_PATH.read_text(encoding="utf-8"))


def _text(case):
    return (
        case.get("full_case_text_no_verdict")
        or case.get("verdict_free_text")
        or case.get("full_case_text")
        or ""
    )[:MAX_CASE_CHARS]


def verify_case(case, *, compare_canonical=True):
    missing = REQUIRED_TARGET_FIELDS - set(case)
    if missing:
        raise ValueError(f"Missing target fields for {case.get('item_id')}: {sorted(missing)}")
    article = str(case.get("article_full", ""))
    if not article or article == "41" or case.get("article") != article:
        raise ValueError(f"Invalid target provision for {case.get('item_id')}")
    if case.get("violation_label") not in {"violation", "no_violation"}:
        raise ValueError(f"Invalid target label for {case.get('item_id')}")
    if case.get("target_status") != "verified":
        raise ValueError(f"Unverified target for {case.get('item_id')}")
    if case["target_provision"] != provision_name(article):
        raise ValueError(f"Stale target provision for {case.get('item_id')}")
    expected = target_question(case["target_respondent"], article, case["target_issue"])
    if case["target_question"] != expected:
        raise ValueError(f"Stale target question for {case.get('item_id')}")
    text = _text(case)
    if not text:
        raise ValueError(f"Empty case input: {case.get('item_id')}")
    if compare_canonical:
        canonical = canonical_cases().get(target_key(case))
        if canonical is None:
            raise ValueError(f"Target is not in the active cohort: {target_key(case)}")
        if text != _text(canonical):
            raise ValueError(f"Source text differs from the active cohort: {target_key(case)}")
    return text


def case_input(case, approved=None):
    """Return only verdict-free source text after semantic target validation."""
    return verify_case(case)


def guard_candidate_output(path):
    if Path(path).resolve() == SUMMARIES_PATH.resolve():
        raise ValueError(
            "Write to a candidate file; replace canonical summaries only after review"
        )


def verify_summaries(mapping, approved=None, metadata=None, *, require_exact=True):
    try:
        from .summaries import validate_single_summaries
    except ImportError:
        from summaries import validate_single_summaries
    validate_single_summaries(mapping)
    metadata = metadata or {}
    if metadata.get("versions", 1) != 1:
        raise ValueError("Exactly one summary per judgment is required")
    expected_ids = {row[0] for row in canonical_cases()}
    if require_exact and set(mapping) != expected_ids:
        raise ValueError("Summary judgment coverage differs from the active cohort")

    if metadata.get("mode") == "extractive":
        try:
            from .extractive import assemble_units, source_units, selection_record, SELECTION_SCHEMA
        except ImportError:
            from extractive import assemble_units, source_units, selection_record, SELECTION_SCHEMA
        sources = {}
        for row in canonical_cases().values():
            sources.setdefault(row["item_id"], row)
        if metadata.get("selection_schema") != SELECTION_SCHEMA:
            raise ValueError("Unknown extractive-selection schema")
        for item_id, values in mapping.items():
            units = source_units(_text(sources[item_id]))
            record = metadata.get("selections", {}).get(item_id, {})
            chosen = record.get("selected_units")
            ids = {unit["id"] for unit in units}
            if (
                not isinstance(chosen, list)
                or not chosen
                or len(chosen) != len(set(chosen))
                or not set(chosen) <= ids
                or selection_record(units, chosen) != record
                or assemble_units(units, chosen) != values[0]
            ):
                raise ValueError(f"Invalid extractive summary assembly for {item_id}")
        return

    canonical = canonical_summaries()["summaries"]
    for item_id, values in mapping.items():
        if item_id in canonical and values != canonical[item_id]:
            raise ValueError(f"Summary differs from the reviewed active summary: {item_id}")


def verify_cases(cases):
    if not isinstance(cases, list) or not cases:
        raise ValueError("Cases must be a nonempty list")
    seen = set()
    for case in cases:
        verify_case(case)
        key = target_key(case)
        if key in seen:
            raise ValueError(f"Duplicate target: {key}")
        seen.add(key)


def bind_run_inputs(directory, cases_path, summaries_path=None):
    """Bind a result directory to semantic dataset and summary settings."""
    directory = Path(directory)
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    verify_cases(cases)
    keys = {target_key(row) for row in cases}
    if keys != set(canonical_cases()):
        raise ValueError("Run cases must exactly match the active atomic-target cohort")
    summary_identity = None
    if summaries_path:
        payload = json.loads(Path(summaries_path).read_text(encoding="utf-8"))
        verify_summaries(payload["summaries"], metadata=payload)
        summary_identity = {
            "dataset_id": payload.get("dataset_id"),
            "summarizer": payload.get("summarizer"),
            "mode": payload.get("mode", "abstractive"),
            "versions": payload.get("versions", 1),
            "judgments": len(payload["summaries"]),
        }
    identity = {
        "dataset_id": manifest()["dataset_id"],
        "targets": len(cases),
        "judgments": len({row["item_id"] for row in cases}),
        "target_unit": manifest()["dataset"]["target_contract"]["unit"],
        "target_keys": [list(key) for key in sorted(keys)],
        "summaries": summary_identity,
    }
    marker = directory / "input_identity.json"
    if marker.exists():
        if json.loads(marker.read_text(encoding="utf-8")) != identity:
            raise ValueError("This result directory belongs to different inputs")
        return identity
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Existing results lack a matching semantic input identity")
    directory.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    return identity
