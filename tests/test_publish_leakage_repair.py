"""Publication must preserve the cohort and use only reviewed original-index-0 summaries."""
import copy

import pytest

from scripts.publish_leakage_repair import MODEL, SUMMARY_TEMPLATE, assemble, digest
from scripts.leak_audit.reviews import accepted_generations, passed


def clean_review():
    return {"status": "reviewed", "result": {"conclusion": False, "reasoning": False, "insufficient_facts": False}}


@pytest.fixture
def inputs():
    old = [{"item_id": "one", "case_name": "A v B", "article_full": "3", "violation_label": "violation",
            "decision_date": "2025-01-01", "full_case_text_no_verdict": "Facts. The Court found a violation."},
           {"item_id": "two", "case_name": "C v D", "article_full": "6", "violation_label": "no_violation",
            "decision_date": "2026-01-01", "full_case_text_no_verdict": "Other facts."}]
    new = copy.deepcopy(old)
    new[0]["full_case_text_no_verdict"] = "Facts."
    blob = {"summarizer": MODEL, "summaries": {"one": ["old one", "unused one", "unused two"],
                                             "two": ["retained zero", "not selected", "not selected either"]}}
    sources = {(row["item_id"], digest(row["full_case_text_no_verdict"])):clean_review() for row in new}
    summaries = {("two:0", digest("retained zero")):clean_review()}
    generation = {("one:0", digest("Facts.")): {
        "version": 0, "model": MODEL, "temperature": 1.0, "max_source_characters": 50000,
        "previous_summary_sha256": digest("old one"), "summary": "A clean factual summary.",
        "generation_prompt_sha256": digest(SUMMARY_TEMPLATE.format(case_name="A v B", full_text="Facts."))}}
    provenance = {"unresolved": [], "source_changes": 1, "model_inputs_changed": 1,
                  "changes": [{"factual_appendix": None}]}
    return old, new, blob, sources, summaries, generation, provenance


def test_complete_single_version_release(inputs):
    blob, spec, report = assemble(*inputs)
    assert blob["versions"] == 1
    assert blob["summaries"] == {"one": ["A clean factual summary."], "two": ["retained zero"]}
    assert spec["status"] == "APPROVED"
    assert report["summaries_regenerated"] == 1 and report["summaries_retained"] == 1


def test_never_fall_back_to_another_version(inputs):
    inputs[5].clear()
    blob, spec, report = assemble(*inputs)
    assert spec["status"] == "PENDING"
    assert "one" not in blob["summaries"]
    assert report["gaps"] == [{"item_id": "one", "reason": "summary_regeneration_pending"}]


@pytest.mark.parametrize("field,value", [("violation_label", "no_violation"), ("decision_date", "2024-01-01"),
                                         ("article_full", "8"), ("case_name", "Changed")])
def test_instance_metadata_is_immutable(inputs, field, value):
    inputs[1][0][field] = value
    with pytest.raises(ValueError, match="metadata changed"):
        assemble(*inputs)


def test_no_approval_when_source_review_missing(inputs):
    inputs[3].clear()
    _, spec, report = assemble(*inputs)
    assert spec["status"] == "PENDING"
    assert len(report["gaps"]) == 2


def test_no_approval_for_a_reviewed_leak(inputs):
    inputs[3][("one", digest("Facts."))]["result"]["conclusion"] = True
    _, spec, report = assemble(*inputs)
    assert spec["status"] == "PENDING"
    assert report["gaps"][0]["reason"] == "source_not_approved"


def test_generation_must_match_frozen_prompt(inputs):
    inputs[5][("one:0", digest("Facts."))]["generation_prompt_sha256"] = "wrong"
    with pytest.raises(ValueError, match="prompt mismatch"):
        assemble(*inputs)


def test_generation_must_match_original_summary(inputs):
    inputs[5][("one:0", digest("Facts."))]["previous_summary_sha256"] = "wrong"
    with pytest.raises(ValueError, match="Original summary mismatch"):
        assemble(*inputs)


def test_review_flags_must_be_explicit_booleans():
    assert not passed({"status": "reviewed", "result": {"conclusion": 0, "reasoning": False, "insufficient_facts": False}})


def test_accepted_checkpoint_requires_matching_review(tmp_path):
    import json
    row = {"status": "accepted", "key": "one:0", "source_sha256": digest("Facts."),
           "summary": "A summary.", "summary_sha256": digest("A summary."),
           "attempts": [{"status": "accepted", "text": "A summary.",
                         "review": {**clean_review(), "input_sha256": "wrong"}}]}
    path = tmp_path / "checkpoint.jsonl"
    path.write_text(json.dumps(row)+"\n", encoding="utf-8")
    with pytest.raises(ValueError, match="matching clean review"):
        accepted_generations([path])
