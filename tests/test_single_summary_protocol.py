"""One summary is a protocol constraint, not just a generator default."""
import ast
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script,removed_flag", [
    ("scripts/build_extractive.py", "--versions"),
])
def test_builders_do_not_expose_multiple_draws(script, removed_flag):
    result = subprocess.run([sys.executable, "-X", "utf8", script, "--help"],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert removed_flag not in result.stdout


def test_retired_generation_entrypoints_are_absent():
    for path in ["experiments/generate_summary_versions.py",
                 "experiments/summary_comparison_matrix_optimized.py",
                 "scripts/complete_missing_summaries.py",
                 "scripts/run_full_experiment.py"]:
        assert not (ROOT / path).exists()


def test_no_runner_enumerates_summary_draws():
    for path in (ROOT / "experiments").glob("run_perturbation_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "run_summarization")
        source = ast.unparse(function)
        assert "validate_single_summaries(summaries)" in source
        assert "summary_for(" in source
        assert "n_versions" not in source
        assert "enumerate(summaries" not in source


def test_analysis_does_not_pool_old_draws():
    from scripts.analyse_perturbation_run import validate_summary_results
    row = {"item_id": "x", "target_respondent_code": "AAA",
           "article_full": "3", "target_issue": "detention conditions",
           "summary_version": 0}
    validate_summary_results([row])
    for wrong in [[row, row], [{**row, "summary_version": 1}]]:
        with pytest.raises(ValueError, match="one summary result"):
            validate_summary_results(wrong)


def test_atomic_verifier_receives_a_string(monkeypatch):
    from scripts import build_atomic_coverage as instrument
    prompts = []
    def fake_complete(client, model, prompt):
        prompts.append(prompt)
        return '[{"i": 1, "supported": true}]'
    monkeypatch.setattr(instrument, "complete", fake_complete)
    claims = [{"claim": "The applicant was detained."}]
    assert instrument.verify(None, "independent", "The applicant was detained.", claims) == [True]
    assert "SUMMARY:\nThe applicant was detained.\n" in prompts[0]
    with pytest.raises(ValueError, match="one usable summary string"):
        instrument.verify(None, "independent", ["first", "second", "third"], claims)


def test_atomic_checkpoint_rejects_stale_summary(tmp_path):
    from scripts.build_atomic_coverage import bind_instrument, bind_variant
    output = tmp_path / "coverage"
    identity = {"dataset_id": "atomic-v1", "judgments": ["one"]}
    bind_instrument(output, identity)
    bind_instrument(output, identity)
    with pytest.raises(ValueError, match="inputs or settings changed"):
        bind_instrument(output, {"dataset_id": "atomic-v2", "judgments": ["one"]})
    bind_variant(output, "abstractive", "one-summary")
    bind_variant(output, "extractive", "verbatim-control")
    bind_variant(output, "abstractive", "one-summary")
    with pytest.raises(ValueError, match="summary changed"):
        bind_variant(output, "abstractive", "old-summary")


def test_atomic_claims_only_cover_model_visible_facts(monkeypatch):
    from scripts import build_atomic_coverage as instrument
    from experiments.checkpoint import Checkpoint
    monkeypatch.setattr(instrument, "fact_paragraphs", lambda text: {"1": "1. Seen fact.", "2": "2. Unseen fact."})
    monkeypatch.setattr(instrument, "relied_upon_numbers", lambda text: {"1", "2"})
    prompts = []
    def fake_complete(client, model, prompt, max_tokens=None):
        prompts.append(prompt)
        return '["Seen fact."]'
    monkeypatch.setattr(instrument, "complete", fake_complete)
    claims = instrument.claims_for(None, "independent", "THE FACTS\nTHE LAW\nReasoning", "fixture",
        Checkpoint(None, enabled=False), 8, 6, source_input="1. Seen fact.")
    assert len(claims) == 1 and claims[0]["paragraph"] == "1"
    assert "Unseen fact" not in prompts[0]


def test_disabled_checkpoint_needs_no_path():
    from experiments.checkpoint import Checkpoint
    checkpoint = Checkpoint(None, enabled=False)
    checkpoint.record("fixture", {"value": 1})
    assert checkpoint.rows() == [{"value": 1}]


def test_extractive_preflight_handles_all_formats_without_excluding_cases():
    from scripts.build_extractive import preflight
    rows = [{"item_id": "valid", "text": "1. First.\n2. Second.\n3. Third.\n4. Fourth."},
            {"item_id": "short", "text": "One unnumbered source."},
            {"item_id": "duplicate", "text": "1. First.\n2. Second.\n1. Another.\n3. Third."}]
    result = preflight(rows)
    assert (result["eligible"], result["blocked"]) == (3, 0)
    assert preflight([{"item_id": "empty", "text": "  "}])["blocked"] == 1
