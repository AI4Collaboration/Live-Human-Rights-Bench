"""Stale input text and unversioned result caches must not reach target models."""
import json
from pathlib import Path

import pytest

from experiments import input_gate as gate


@pytest.fixture
def approved(monkeypatch):
    source = "The applicant spent 27 days in detention."
    summaries = ["One factual summary."]
    spec = {"status": "APPROVED", "release_id": "test-release",
            "dataset_sha256_lf": "dataset-hash", "summaries_sha256_lf": "summary-hash",
            "source_inputs": {"001-known": gate.text_digest(source)},
            "summary_inputs": {"001-known": list(map(gate.text_digest, summaries))}}
    monkeypatch.setattr(gate, "release", lambda: spec)
    monkeypatch.setattr(gate, "cohort_ids", lambda: {"001-known"})
    return spec, source, summaries


def test_current_source_is_accepted(approved):
    _, source, _ = approved
    assert gate.case_input({"item_id": "001-known", "full_case_text_no_verdict": source}) == source


def test_stale_source_is_rejected(approved):
    with pytest.raises(ValueError, match="Stale or unreviewed"):
        gate.case_input({"item_id": "001-known", "full_case_text_no_verdict": "The Court found a violation."})


def test_missing_release_fails_closed(approved, monkeypatch):
    monkeypatch.setattr(gate, "release", lambda: None)
    with pytest.raises(ValueError, match="leakage-release gate"):
        gate.case_input({"item_id": "001-known", "full_case_text_no_verdict": approved[1]})


def test_single_summary_content_is_bound(approved):
    summaries = approved[2]
    gate.verify_summaries({"001-known": summaries})
    for wrong in [[], summaries * 3, ["The Court found a violation."]]:
        with pytest.raises(ValueError):
            gate.verify_summaries({"001-known": wrong})


def test_extractive_control_is_bound_to_source_and_selected_paragraphs(tmp_path, approved, monkeypatch):
    source = "1. The applicant was detained.\n\n2. The domestic court dismissed the appeal."
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([{"item_id": "001-known", "full_case_text_no_verdict": source}]), encoding="utf-8")
    monkeypatch.setattr(gate, "CASES_PATH", path)
    spec = {**approved[0], "source_inputs": {"001-known": gate.text_digest(source)}}
    from experiments.extractive import source_units, selection_record, SELECTION_SCHEMA
    record = selection_record(source_units(source), ["2"])
    meta = {"mode": "extractive", "versions": 1, "source_inputs": spec["source_inputs"],
            "selection_schema": SELECTION_SCHEMA, "selections": {"001-known": record}}
    extract = {"001-known": ["2. The domestic court dismissed the appeal."]}
    gate.verify_summaries(extract, spec, metadata=meta)
    with pytest.raises(ValueError, match="verbatim"):
        gate.verify_summaries({"001-known": ["The Court found a violation."]}, spec, metadata=meta)
    with pytest.raises(ValueError, match="Stale extractive source"):
        gate.verify_summaries(extract, spec, metadata={**meta, "source_inputs": {}})
    with pytest.raises(ValueError, match="verbatim"):
        gate.verify_summaries(extract, spec, metadata={**meta, "selections": {"001-known": selection_record(source_units(source), ["1"])}})


def test_candidate_builder_cannot_overwrite_canonical_summary():
    with pytest.raises(ValueError, match="publication gate"):
        gate.guard_candidate_output(gate.ROOT / "data/processed/summaries_dsv41flash.json")


def test_actual_50000_character_prefix_is_checked(approved):
    spec = {**approved[0], "source_inputs": {"001-known": gate.text_digest("x" * 50000)}}
    assert gate.case_input({"item_id": "001-known", "full_case_text_no_verdict": "x" * 50000 + "tail"}, spec) == "x" * 50000


def test_empty_input_is_rejected(approved):
    with pytest.raises(ValueError, match="Empty case"):
        gate.case_input({"item_id": "001-new", "full_case_text_no_verdict": ""})


def test_custom_fixture_is_not_claimed_as_approved(approved):
    assert gate.case_input({"item_id": "001-new", "full_case_text": "fixture"}) == "fixture"


def test_result_identity_blocks_stale_checkpoints(tmp_path, approved):
    cases = tmp_path / "cases.json"
    cases.write_text("[]\n", encoding="utf-8")
    output = tmp_path / "results"
    identity = gate.bind_run_inputs(output, cases)
    assert gate.bind_run_inputs(output, cases) == identity
    cases.write_text("[1]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="different inputs"):
        gate.bind_run_inputs(output, cases)


def test_old_unversioned_results_cannot_resume(tmp_path, approved):
    cases = tmp_path / "cases.json"
    cases.write_text("[]\n", encoding="utf-8")
    output = tmp_path / "old-results"
    output.mkdir()
    (output / "baseline.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="pre-repair checkpoints"):
        gate.bind_run_inputs(output, cases)


def test_line_endings_do_not_change_file_identity(tmp_path):
    path = tmp_path / "input.json"
    path.write_bytes(b"{\n}\n")
    digest = gate.file_digest(path)
    path.write_bytes(b"{\r\n}\r\n")
    assert gate.file_digest(path) == digest
