"""Regressions for current experiment inputs and checkpoint identity."""

import json
from types import SimpleNamespace

import pytest

from experiments import paraphrase_run as paraphrase
from experiments import syco_run as syco
from experiments import stateswap_summary_run as stateswap


def test_syco_followups_keep_each_initial_provision(tmp_path, monkeypatch):
    cases = [{"item_id": "same-judgment", "article_full": article,
              "respondent": "State A", "violation_label": "violation"}
             for article in ["3", "6"]]
    source = tmp_path / "cases.json"
    source.write_text(json.dumps(cases), encoding="utf-8")
    summaries = tmp_path / "summaries.json"
    summaries.write_text(json.dumps({"summaries": {"same-judgment": ["Shared facts."]}}), encoding="utf-8")
    output = tmp_path / "results"
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-no-network")
    # Canonical-input validation has its own tests; this fixture isolates the
    # same-judgment/different-provision join across the complete runner path.
    monkeypatch.setattr(syco, "bind_run_inputs", lambda *args: None)
    monkeypatch.setattr(syco, "condition_grid", lambda: [
        ("baseline_high", {"strategy": "Baseline", "variation": "none", "pressure": "high"})])
    monkeypatch.setattr(syco, "call", lambda *args, **kwargs: '{"violation_likelihood":80}')
    observed = []

    def trajectory(pack, case, *args):
        observed.append((case["target_provision"], case["target_question"]))
        return [20, 20, 20]

    monkeypatch.setattr(syco, "run_trajectory", trajectory)
    monkeypatch.setattr(syco.sys, "argv", ["syco_run.py", "--cases", str(source),
        "--summaries", str(summaries), "--out", str(output),
        "--targets", "offline-target", "--workers", "1"])
    syco.main()
    assert observed.count(("Article 3", "the ECtHR finds a violation of Article 3")) == 2
    assert observed.count(("Article 6", "the ECtHR finds a violation of Article 6")) == 2
    rows = [json.loads(line) for line in (output / "trajectories.jsonl").read_text().splitlines()]
    assert {(r["article_full"], r["arm"]) for r in rows} == {
        (article, arm) for article in ["3", "6"] for arm in ["static", "adaptive"]}


def test_syco_rejects_duplicate_case_provision():
    row = {"item_id": "same", "article_full": "3"}
    with pytest.raises(ValueError, match="Duplicate"):
        syco.index_cases([row, row])


def syco_args(tmp_path):
    cases, summaries = tmp_path / "cases.json", tmp_path / "summaries.json"
    cases.write_text("[]", encoding="utf-8")
    summaries.write_text("{}", encoding="utf-8")
    return SimpleNamespace(cases=str(cases), summaries=str(summaries),
        out=str(tmp_path / "run"), targets=["offline-target"], turns=3, limit=0)


def test_syco_rejects_unversioned_and_changed_checkpoints(tmp_path):
    args = syco_args(tmp_path)
    from pathlib import Path
    output = Path(args.out)
    output.mkdir()
    checkpoint = output / "trajectories.jsonl"
    checkpoint.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unversioned"):
        syco.bind_syco_config(args, {})
    checkpoint.unlink()
    first = syco.bind_syco_config(args, {})
    assert syco.bind_syco_config(args, {}) == first
    args.turns = 2
    with pytest.raises(ValueError, match="settings changed"):
        syco.bind_syco_config(args, {})


def test_paraphrase_missing_inputs_cannot_report_an_empty_success(tmp_path):
    with pytest.raises(FileNotFoundError, match="Generate or supply"):
        paraphrase.load_pairs(tmp_path / "absent.json")


def test_paraphrase_does_not_score_an_article_number_as_the_answer():
    assert paraphrase.parse_rating("Under Article 8, the likelihood is 80") == 80
    assert paraphrase.parse_rating("Article 8") is None
    assert paraphrase.parse_rating("ERROR: 429 Too Many Requests") is None


def test_stateswap_does_not_score_an_article_number_as_the_answer():
    assert stateswap.parse_rating("Under Article 8, the likelihood is 80") == 80
    assert stateswap.parse_rating("Article 8") is None


def test_stateswap_rejects_changed_and_unversioned_checkpoints(tmp_path):
    cases, summaries = tmp_path / "cases.json", tmp_path / "summaries.json"
    cases.write_text("[]", encoding="utf-8")
    summaries.write_text("{}", encoding="utf-8")
    args = SimpleNamespace(model="offline", samples=10, limit=0,
        cases=str(cases), summaries=str(summaries))
    output = tmp_path / "run"
    output.mkdir()
    checkpoint = output / "stateswap_summary_results.jsonl"
    checkpoint.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unversioned"):
        stateswap.bind_run_config(output, args)
    checkpoint.unlink()
    first = stateswap.bind_run_config(output, args)
    assert stateswap.bind_run_config(output, args) == first
    args.samples = 5
    with pytest.raises(ValueError, match="settings changed"):
        stateswap.bind_run_config(output, args)


def test_stateswap_saves_raw_responses_and_parse_retries(tmp_path, monkeypatch):
    cases, summaries = tmp_path / "cases.json", tmp_path / "summaries.json"
    cases.write_text(json.dumps([{"item_id": "case-a", "article_full": "3",
        "target_respondent": "Croatia", "violation_label": "violation"}]), encoding="utf-8")
    summaries.write_text(json.dumps({"summaries": {"case-a": ["Facts in Croatia."]}}), encoding="utf-8")
    monkeypatch.setattr(stateswap, "bind_run_inputs", lambda *args: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-no-network")
    replies = iter([None, "80", "20", "50", "90"])
    monkeypatch.setattr(stateswap, "call", lambda *args: next(replies))
    output = tmp_path / "run"
    monkeypatch.setattr(stateswap.sys, "argv", ["stateswap_summary_run.py",
        "--cases", str(cases), "--summaries", str(summaries), "--out", str(output),
        "--model", "offline-target", "--samples", "1", "--workers", "1"])
    stateswap.main()
    checkpoint = output / "offline-target/stateswap_summary_results.jsonl"
    rows = {r["arm"]: r for r in map(json.loads, checkpoint.read_text().splitlines())}
    assert set(rows) == {"original", "US", "Russia", "Ukraine"}
    assert rows["original"]["ratings"] == [80]
    assert rows["original"]["responses"] == ["80"]
    assert rows["original"]["response_attempts"] == [[None, "80"]]
    assert rows["original"]["parse_retry_count"] == 1
    assert rows["original"]["n_unparsed"] == 0
    assert rows["US"]["ratings"] == [20]
    assert rows["Russia"]["prediction"] == "abstention"
    assert rows["Ukraine"]["text_changed"] is True


def test_stateswap_checkpoint_binds_country_aliases(tmp_path, monkeypatch):
    cases, summaries = tmp_path / "cases.json", tmp_path / "summaries.json"
    cases.write_text("[]", encoding="utf-8")
    summaries.write_text("{}", encoding="utf-8")
    args = SimpleNamespace(model="offline", samples=10, limit=0,
        cases=str(cases), summaries=str(summaries))
    first = stateswap.bind_run_config(tmp_path / "run", args)
    assert "country_aliases_and_demonyms" in first
    monkeypatch.setattr(stateswap, "COUNTRIES", {**stateswap.COUNTRIES,
        "Croatia": (["Croatia", "Republic of Croatia"], "Croatian")})
    with pytest.raises(ValueError, match="settings changed"):
        stateswap.bind_run_config(tmp_path / "run", args)


def test_paraphrase_missing_arm_cannot_be_scored_as_original(tmp_path):
    source = tmp_path / "pairs.json"
    source.write_text(json.dumps([{"key": "case|3", "item_id": "case", "article": "3",
        "original": "Original facts", "light": "Light rewrite", "medium": "Medium rewrite"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="Missing paraphrase arm"):
        paraphrase.load_pairs(source)


def test_failed_paraphrase_is_not_recorded_as_a_successful_rewrite(monkeypatch):
    monkeypatch.setattr(paraphrase, "call", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="generation failed"):
        paraphrase.paraphrase_text("Facts", "Rewrite", "offline", "offline")


def test_paraphrase_changed_samples_cannot_reuse_checkpoints(tmp_path):
    args = SimpleNamespace(model="offline", samples=10)
    pairs = [{"key": "case|3", "original": "Facts"}]
    first = paraphrase.bind_eval_config(tmp_path, pairs, args)
    assert paraphrase.bind_eval_config(tmp_path, pairs, args) == first
    args.samples = 5
    with pytest.raises(ValueError, match="settings changed"):
        paraphrase.bind_eval_config(tmp_path, pairs, args)


def test_candidate_sampler_keeps_distinct_case_and_protocol_identities(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    rows = [{"item_id": item, "case_name": "Repeated title", "respondent": "State A",
             "decision_date": "2025-01-01", "article": "1", "article_full": article,
             "violation_label": "violation", "verdict_free_text": "Candidate facts."}
            for item, article in [("case-a", "1"), ("case-b", "1"), ("case-a", "P1-1")]]
    source, output = tmp_path / "source.json", tmp_path / "new/candidates.json"
    source.write_text(json.dumps(rows), encoding="utf-8")
    subprocess.run([sys.executable, "scripts/build_unified_set.py", "--source", str(source),
                    "--out", str(output)], cwd=Path(__file__).resolve().parents[1],
                   check=True, capture_output=True)
    selected = json.loads(output.read_text(encoding="utf-8"))
    assert {(r["item_id"], r["article_full"]) for r in selected} == {
        ("case-a", "1"), ("case-b", "1"), ("case-a", "P1-1")}
    assert all(r["full_case_text_no_verdict"] == "Candidate facts." for r in selected)
