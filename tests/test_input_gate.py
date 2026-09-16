"""Atomic targets and reviewed content must be validated before model calls."""

import json

import pytest

from experiments import input_gate as gate


def make_case(item_id, article, respondent_code, respondent, issue, text, label):
    return {
        "item_id": item_id,
        "case_name": f"Fixture {item_id}",
        "article": article,
        "article_full": article,
        "violation_label": label,
        "full_case_text_no_verdict": text,
        "target_respondent_code": respondent_code,
        "target_respondent": respondent,
        "target_provision": gate.provision_name(article),
        "target_issue": issue,
        "target_aspect": "unspecified",
        "target_question": gate.target_question(respondent, article, issue),
        "target_status": "verified",
    }


@pytest.fixture
def active(tmp_path, monkeypatch):
    cases = [
        make_case(
            "001-known",
            "5",
            "AAA",
            "State A",
            "lawfulness of the applicant's detention",
            "1. The applicant was detained.\n\n2. The domestic court dismissed the appeal.",
            "violation",
        ),
        make_case(
            "001-other",
            "6",
            "BBB",
            "State B",
            "fairness of the civil proceedings",
            "A factual hearing record.",
            "no_violation",
        ),
    ]
    summaries = {
        "001-known": ["One factual detention summary."],
        "001-other": ["One factual hearing summary."],
    }
    payload = {
        "dataset_id": "fixture-atomic-v1",
        "summarizer": "fixture/summarizer",
        "versions": 1,
        "n_judgments": 2,
        "n_complete": 2,
        "summaries": summaries,
    }
    manifest = {
        "dataset_id": "fixture-atomic-v1",
        "dataset": {
            "target_contract": {
                "unit": "one judgment, one respondent State, one provision, one sub-conclusion"
            }
        },
        "summaries": {"summarizer": "fixture/summarizer", "versions": 1},
    }
    cases_path = tmp_path / "cases.json"
    summaries_path = tmp_path / "summaries.json"
    manifest_path = tmp_path / "manifest.json"
    cases_path.write_text(json.dumps(cases), encoding="utf-8")
    summaries_path.write_text(json.dumps(payload), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(gate, "CASES_PATH", cases_path)
    monkeypatch.setattr(gate, "SUMMARIES_PATH", summaries_path)
    monkeypatch.setattr(gate, "MANIFEST_PATH", manifest_path)
    gate.manifest.cache_clear()
    gate.canonical_cases.cache_clear()
    gate.canonical_summaries.cache_clear()
    yield {
        "cases": cases,
        "summaries": summaries,
        "payload": payload,
        "manifest": manifest,
        "cases_path": cases_path,
        "summaries_path": summaries_path,
        "manifest_path": manifest_path,
    }
    gate.manifest.cache_clear()
    gate.canonical_cases.cache_clear()
    gate.canonical_summaries.cache_clear()


def test_current_source_and_target_are_accepted(active):
    case = active["cases"][0]
    assert gate.case_input(case) == case["full_case_text_no_verdict"]


def test_stale_source_is_rejected(active):
    case = {**active["cases"][0], "full_case_text_no_verdict": "Altered source."}
    with pytest.raises(ValueError, match="Source text differs"):
        gate.case_input(case)


def test_missing_or_stale_target_is_rejected(active):
    missing = dict(active["cases"][0])
    missing.pop("target_issue")
    with pytest.raises(ValueError, match="Missing target fields"):
        gate.verify_case(missing)
    stale = {**active["cases"][0], "target_question": "a different question"}
    with pytest.raises(ValueError, match="Stale target question"):
        gate.verify_case(stale)


def test_single_summary_content_is_bound(active):
    gate.verify_summaries(active["summaries"], metadata=active["payload"])
    wrong = dict(active["summaries"])
    wrong["001-known"] = ["A different summary."]
    with pytest.raises(ValueError, match="reviewed active summary"):
        gate.verify_summaries(wrong, metadata=active["payload"])


def test_extractive_control_is_exact_assembly(active):
    from experiments.extractive import SELECTION_SCHEMA, selection_record, source_units

    source = active["cases"][0]["full_case_text_no_verdict"]
    record = selection_record(source_units(source), ["2"])
    metadata = {
        "mode": "extractive",
        "versions": 1,
        "selection_schema": SELECTION_SCHEMA,
        "selections": {"001-known": record, "001-other": None},
    }
    extract = {
        "001-known": ["2. The domestic court dismissed the appeal."],
        "001-other": ["A factual hearing record."],
    }
    other_units = source_units(active["cases"][1]["full_case_text_no_verdict"])
    metadata["selections"]["001-other"] = selection_record(
        other_units, [other_units[0]["id"]]
    )
    gate.verify_summaries(extract, metadata=metadata)
    with pytest.raises(ValueError, match="Invalid extractive summary assembly"):
        gate.verify_summaries(
            {**extract, "001-known": ["Paraphrased text."]}, metadata=metadata
        )


def test_candidate_builder_cannot_overwrite_canonical_summary(active):
    with pytest.raises(ValueError, match="candidate file"):
        gate.guard_candidate_output(active["summaries_path"])


def test_empty_input_is_rejected(active):
    case = {**active["cases"][0], "full_case_text_no_verdict": ""}
    with pytest.raises(ValueError, match="Empty case"):
        gate.verify_case(case, compare_canonical=False)


def test_unregistered_target_is_rejected(active):
    case = {**active["cases"][0], "target_respondent_code": "ZZZ"}
    with pytest.raises(ValueError, match="not in the active cohort"):
        gate.case_input(case)


def test_result_identity_is_semantic_and_blocks_changed_dataset_id(active):
    output = active["cases_path"].parent / "results"
    identity = gate.bind_run_inputs(
        output, active["cases_path"], active["summaries_path"]
    )
    assert identity["dataset_id"] == "fixture-atomic-v1"
    assert len(identity["target_keys"]) == 2
    assert gate.bind_run_inputs(
        output, active["cases_path"], active["summaries_path"]
    ) == identity

    changed = {**active["manifest"], "dataset_id": "fixture-atomic-v2"}
    active["manifest_path"].write_text(json.dumps(changed), encoding="utf-8")
    gate.manifest.cache_clear()
    with pytest.raises(ValueError, match="different inputs"):
        gate.bind_run_inputs(output, active["cases_path"], active["summaries_path"])


def test_old_unidentified_results_cannot_resume(active):
    output = active["cases_path"].parent / "old-results"
    output.mkdir()
    (output / "baseline.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="semantic input identity"):
        gate.bind_run_inputs(output, active["cases_path"], active["summaries_path"])
