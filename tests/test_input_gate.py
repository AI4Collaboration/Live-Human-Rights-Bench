"""Stale input text and unversioned result caches must not reach target models."""
import json
from pathlib import Path

import pytest

from experiments import input_gate as gate


@pytest.fixture
def approved(monkeypatch):
    source = "The applicant spent 27 days in detention."
    summaries = ["Facts version one.", "Facts version two.", "Facts version three."]
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


def test_summary_order_and_content_are_bound(approved):
    summaries = approved[2]
    gate.verify_summaries({"001-known": summaries})
    for wrong in [summaries[::-1], summaries[:2], ["The Court found a violation.", *summaries[1:]]]:
        with pytest.raises(ValueError, match="Stale or unreviewed"):
            gate.verify_summaries({"001-known": wrong})


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
