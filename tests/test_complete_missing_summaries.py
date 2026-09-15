"""Offline tests: no provider requests; existing summary text must never change."""

import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import complete_missing_summaries as repair


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    special = sorted({item_id for item_id, _ in repair.EXPECTED_MISSING})
    ids = special + [f"test-{i:04}" for i in range(947 - len(special))]
    rows = [{"item_id": item_id, "case_name": item_id,
             "full_case_text_no_verdict": "x" * 50003} for item_id in ids]
    rows += copy.deepcopy(rows[:53])
    mapping = {item_id: [f"original {item_id} v{v}" for v in range(3)] for item_id in ids}
    for item_id, version in repair.EXPECTED_MISSING:
        mapping[item_id][version] = None
    del mapping["001-219988"]
    blob = {"summarizer": repair.MODEL, "versions": 3, "n_judgments": 947,
            "n_complete": 941, "prompt_tokens": 123, "completion_tokens": 456,
            "summaries": mapping}
    cases, summaries, manifest, checkpoint = [tmp_path / name for name in
                                            ("cases.json", "summaries.json", "manifest.json", "checkpoint.json")]
    cases.write_bytes(repair.serialized(rows))
    summaries.write_bytes(repair.serialized(blob))
    data_hash, summary_hash = repair.sha256_lf(cases.read_bytes()), repair.sha256_lf(summaries.read_bytes())
    monkeypatch.setattr(repair, "EXPECTED_DATA_SHA256", data_hash)
    monkeypatch.setattr(repair, "EXPECTED_BASE_SUMMARIES_SHA256", summary_hash)
    manifest.write_bytes(repair.serialized({
        "dataset": {"sha256_lf": data_hash, "annual_counts": {"2026": 57}},
        "summaries": {"sha256_lf": summary_hash, "summarizer": repair.MODEL,
                      "versions": 3, "missing_slots_zero_based": repair.EXPECTED_MISSING},
        "unrelated": "preserve this",
    }))
    return cases, summaries, manifest, checkpoint, blob


def execute(fixture, **kwargs):
    return repair.run(*fixture[:4], **kwargs)


def test_dry_run_never_creates_checkpoint_or_client(fixture, monkeypatch):
    original = [path.read_bytes() for path in fixture[:3]]
    monkeypatch.setattr(repair, "summarise", lambda *_: pytest.fail("No generation in dry-run"))
    assert execute(fixture) == 0
    assert not fixture[3].exists()
    assert [path.read_bytes() for path in fixture[:3]] == original


def test_missing_credential_causes_no_writes(fixture, monkeypatch):
    monkeypatch.delenv("REPAIR_TEST_KEY", raising=False)
    with pytest.raises(ValueError, match="Set REPAIR_TEST_KEY"):
        execute(fixture, execute=True, api_key_env="REPAIR_TEST_KEY")
    assert not fixture[3].exists()


def test_bounded_parallel_fill_preserves_exact_slots(fixture, monkeypatch):
    monkeypatch.setenv("REPAIR_TEST_KEY", "offline-test-key")
    monkeypatch.setattr(repair, "summarise", lambda client, model, case, limit:
                        (f"summary for {case['item_id']}", {"prompt": 1, "completion": 1}))
    assert execute(fixture, execute=True, api_key_env="REPAIR_TEST_KEY",
                   client_factory=lambda **_: object(), workers=4) == 0
    attempts=repair.read_json(fixture[3])["attempts"]
    assert sorted([r["item_id"], r["version"]] for r in attempts) == repair.EXPECTED_MISSING
    assert repair.read_json(fixture[1])["n_complete"] == 947
    for workers in (0, 5):
        with pytest.raises(ValueError, match="between 1 and 4"):
            execute(fixture, workers=workers)


def test_fills_only_nine_preserves_originals_and_metadata(fixture, monkeypatch):
    monkeypatch.setenv("REPAIR_TEST_KEY", "offline-test-key")
    calls = []
    data_before = fixture[0].read_bytes()
    manifest_before = repair.read_json(fixture[2])

    def fake(client, model, case, max_tokens):
        assert model == repair.MODEL and max_tokens == 4000
        assert len(case["text"]) == 50000
        calls.append(case["item_id"])
        return f"new summary {len(calls)}", {"prompt": 10, "completion": 20}

    monkeypatch.setattr(repair, "summarise", fake)
    assert execute(fixture, execute=True, api_key_env="REPAIR_TEST_KEY",
                   client_factory=lambda **_: object()) == 0
    assert len(calls) == 9
    output = repair.read_json(fixture[1])
    assert output["n_complete"] == 947
    assert output["prompt_tokens"] == 123 and output["completion_tokens"] == 456
    for item_id, versions in fixture[4]["summaries"].items():
        for version, value in enumerate(versions):
            if value is not None:
                assert output["summaries"][item_id][version] == value
    new_manifest = repair.read_json(fixture[2])
    assert new_manifest["dataset"] == manifest_before["dataset"]
    assert new_manifest["unrelated"] == manifest_before["unrelated"]
    assert new_manifest["summaries"]["usable_summaries"] == 2841
    assert new_manifest["summaries"]["missing_slots_zero_based"] == []
    assert new_manifest["summaries"]["sha256_lf"] == repair.sha256_lf(fixture[1].read_bytes())
    checkpoint = repair.read_json(fixture[3])
    assert checkpoint["repair_usage"] == {"prompt": 90, "completion": 180}
    assert len(checkpoint["attempts"]) == 9
    assert fixture[0].read_bytes() == data_before
    monkeypatch.delenv("REPAIR_TEST_KEY")
    assert execute(fixture, execute=True, api_key_env="REPAIR_TEST_KEY") == 0
    assert len(calls) == 9


def test_partial_failure_retries_only_remaining_slot(fixture, monkeypatch):
    monkeypatch.setenv("REPAIR_TEST_KEY", "offline-secret")
    calls = []

    def fake(*args):
        calls.append(args[2]["item_id"])
        if len(calls) == 1:
            return "ERROR: offline-secret unavailable", {"prompt": 1, "completion": 0}
        return f"summary {len(calls)}", {"prompt": 1, "completion": 2}

    monkeypatch.setattr(repair, "summarise", fake)
    kwargs = dict(execute=True, api_key_env="REPAIR_TEST_KEY", client_factory=lambda **_: object())
    assert execute(fixture, **kwargs) == 1
    assert len(calls) == 9
    assert repair.read_json(fixture[2])["summaries"]["missing_slots_zero_based"] == [["001-166954", 2]]
    assert "offline-secret" not in fixture[3].read_text(encoding="utf-8")
    assert execute(fixture, **kwargs) == 0
    assert len(calls) == 10


@pytest.mark.parametrize("which", ["dataset", "original_summary", "extra_missing"])
def test_rejects_changed_inputs_before_any_client(fixture, monkeypatch, which):
    if which == "dataset":
        fixture[0].write_text("[]", encoding="utf-8")
    else:
        blob = repair.read_json(fixture[1])
        blob["summaries"]["test-0000"][0] = None if which == "extra_missing" else "changed"
        fixture[1].write_bytes(repair.serialized(blob))
    with pytest.raises(ValueError):
        execute(fixture, execute=True, client_factory=lambda **_: pytest.fail("No API calls"))
    assert not fixture[3].exists()


def test_checkpoint_cannot_be_reused_for_another_source(fixture, monkeypatch):
    monkeypatch.setenv("REPAIR_TEST_KEY", "offline-test-key")
    monkeypatch.setattr(repair, "summarise", lambda *_: ("ERROR: unavailable", {"prompt": 0, "completion": 0}))
    execute(fixture, execute=True, api_key_env="REPAIR_TEST_KEY", client_factory=lambda **_: object())
    checkpoint = repair.read_json(fixture[3])
    checkpoint["dataset_sha256_lf"] = "wrong-source"
    fixture[3].write_bytes(repair.serialized(checkpoint))
    with pytest.raises(ValueError, match="does not match"):
        execute(fixture)


def test_all_failures_leave_artifact_and_manifest_untouched(fixture, monkeypatch):
    monkeypatch.setenv("REPAIR_TEST_KEY", "offline-test-key")
    before = [path.read_bytes() for path in fixture[:3]]
    monkeypatch.setattr(repair, "summarise", lambda *_: ("ERROR: unavailable", {"prompt": 0, "completion": 0}))
    assert execute(fixture, execute=True, api_key_env="REPAIR_TEST_KEY",
                   client_factory=lambda **_: object()) == 1
    assert [path.read_bytes() for path in fixture[:3]] == before
    assert repair.read_json(fixture[3])["remaining_missing_slots_zero_based"] == repair.EXPECTED_MISSING


def test_interrupted_publication_resumes_without_more_calls(fixture, monkeypatch):
    monkeypatch.setenv("REPAIR_TEST_KEY", "offline-test-key")
    calls = []

    def fake(*args):
        calls.append(args[2]["item_id"])
        return f"new summary {len(calls)}", {"prompt": 1, "completion": 1}

    monkeypatch.setattr(repair, "summarise", fake)
    atomic = repair.atomic_json

    def interrupt_manifest(path, value):
        if path == fixture[2]:
            raise OSError("Simulated interruption before manifest publication")
        atomic(path, value)

    monkeypatch.setattr(repair, "atomic_json", interrupt_manifest)
    with pytest.raises(OSError, match="Simulated interruption"):
        execute(fixture, execute=True, api_key_env="REPAIR_TEST_KEY", client_factory=lambda **_: object())
    assert len(calls) == 9
    monkeypatch.setattr(repair, "atomic_json", atomic)
    monkeypatch.delenv("REPAIR_TEST_KEY")
    assert execute(fixture, execute=True, api_key_env="REPAIR_TEST_KEY") == 0
    assert len(calls) == 9


def test_concurrent_manifest_edit_is_not_overwritten(fixture, monkeypatch):
    monkeypatch.setenv("REPAIR_TEST_KEY", "offline-test-key")

    def fake(*_):
        manifest = repair.read_json(fixture[2])
        manifest["unrelated"] = "external collaborator edit"
        repair.atomic_json(fixture[2], manifest)
        return "new summary", {"prompt": 1, "completion": 1}

    monkeypatch.setattr(repair, "summarise", fake)
    with pytest.raises(ValueError, match="changed during generation"):
        execute(fixture, execute=True, api_key_env="REPAIR_TEST_KEY", client_factory=lambda **_: object())
    assert repair.read_json(fixture[2])["unrelated"] == "external collaborator edit"
    assert repair.read_json(fixture[1]) == fixture[4]
