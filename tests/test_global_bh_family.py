"""The three-draw migration is a rescore with a new global BH family."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.analyse_perturbation_run import analyze_family, apply_global_bh
from experiments.run_protocol import SCORING, SUMMARY_PROTOCOL, bind_run_config

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(root, count=7):
    family = json.loads((ROOT / "configs/perturbation_analysis.json").read_text(encoding="utf-8"))
    family.update(models=[f"provider/model-{i}" for i in range(count)], expected_comparisons=5*count)
    cases = [{"item_id": "a", "article": "3", "violation_label": "violation"},
             {"item_id": "b", "article": "8", "violation_label": "no_violation"}]
    release = {"status": "APPROVED", "versions": 1, "release_id": "clean",
               "summaries_sha256_lf": "one-summary", "dataset_sha256_lf": "repaired"}
    for model in family["models"]:
        directory = root / model.replace("/", "_")
        write(directory / "input_identity.json", {"release_id": "clean", "cases_sha256_lf": "repaired", "summaries_sha256_lf": "one-summary"})
        config = {"model": model, "samples": 3, "summary_protocol": SUMMARY_PROTOCOL,
                  "scoring": SCORING, "prompts_sha256": "frozen-prompts", "temperature": 1.0}
        write(directory / "run_config.json", config)
        baseline = [{**r, "ratings": [90, 90, 90]} for r in cases]
        # Deliberately wrong stored predictions/metrics must not influence analysis.
        changed = [{**r, "ratings": [90 if i == 0 else 10] * 3, "summary_version": 0,
                    "prediction": "abstention", "accurate": False, "aligned": True, "mcnemar_q": .999}
                   for i, r in enumerate(cases)]
        write(directory / "baseline_results.json", baseline)
        write(directory / "rq1_results.json", changed)
        write(directory / "rq2_results.json", [{**r, "framing": frame} for frame in family["comparisons"]["rq2"] for r in changed])
        write(directory / "rq3_results.json", [{**r, "original_ratings": [10]*3, "challenged_ratings": [90]*3} for r in cases])
    return family, cases, release


@pytest.mark.parametrize("models,expected", [(6, {"rq1": 6, "rq2": 18, "rq3": 6}), (8, {"rq1": 8, "rq2": 24, "rq3": 8})])
def test_full_rescore_has_one_comparison_per_condition(tmp_path, models, expected):
    rows, report = analyze_family(tmp_path, *fixture(tmp_path, models))
    assert report["comparisons_by_arm"] == expected
    assert report["bh_family_size"] == models * 5
    assert all(r["n_instances"] == 2 for r in rows)
    rq1 = next(r for r in rows if r["arm"] == "rq1")
    assert rq1["accuracy"] == 1 and rq1["alignment_rate"] == .5
    assert rq1["accuracy_delta"] == .5
    assert (rq1["better_than_reference"], rq1["worse_than_reference"]) == (1, 0)
    assert rq1["mcnemar_q"] != .999


def test_removing_sixteen_summary_comparisons_recomputes_every_arm():
    retained = [{"model": f"m{i}", "arm": "rq1" if i < 8 else "rq2" if i < 32 else "rq3",
                 "variant": "v", "mcnemar_p": (i + 1) / 1000, "mcnemar_q": 999} for i in range(40)]
    old = deepcopy(retained) + [{"model": f"extra{i}", "arm": "rq1", "variant": "old-draw",
                                "mcnemar_p": .8} for i in range(16)]
    apply_global_bh(old, 56)
    apply_global_bh(retained, 40)
    changed_arms = set()
    for before, after in zip(old, retained):
        assert before["mcnemar_p"] == after["mcnemar_p"]
        assert before["mcnemar_q"] == pytest.approx(.056)
        assert after["mcnemar_q"] == pytest.approx(.04)
        changed_arms.add(after["arm"])
    assert changed_arms == {"rq1", "rq2", "rq3"}


@pytest.mark.parametrize("problem", ["missing_model", "missing_arm", "missing_instance", "three_draws", "nonzero_version", "wrong_release", "incomplete_samples", "different_samples", "changed_prompt"])
def test_incomplete_or_mixed_release_never_produces_q_values(tmp_path, problem):
    family, cases, release = fixture(tmp_path)
    directory = tmp_path / "provider_model-0"
    if problem == "missing_model":
        family["models"][-1] = "provider/absent"
    elif problem == "missing_arm":
        (directory / "rq2_results.json").unlink()
    elif problem == "wrong_release":
        write(directory / "input_identity.json", {"release_id": "old"})
    elif problem in {"different_samples", "changed_prompt"}:
        config = json.loads((directory / "run_config.json").read_text())
        config["samples" if problem == "different_samples" else "prompts_sha256"] = 10 if problem == "different_samples" else "other"
        write(directory / "run_config.json", config)
    else:
        path = directory / "rq1_results.json"
        rows = json.loads(path.read_text())
        if problem == "missing_instance":
            rows.pop()
        elif problem == "three_draws":
            rows *= 3
        elif problem == "nonzero_version":
            rows[0]["summary_version"] = 1
        elif problem == "incomplete_samples":
            rows[0]["ratings"][0] = None
        write(path, rows)
    with pytest.raises((ValueError, FileNotFoundError)):
        analyze_family(tmp_path, family, cases, release)


def test_missing_real_results_does_not_write_statistics(tmp_path):
    out = tmp_path / "stats.csv"
    result = subprocess.run([sys.executable, "scripts/analyse_perturbation_run.py", "--run-dir", str(tmp_path), "--out", str(out)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert "No q-values produced" in result.stderr
    assert not out.exists() and not out.with_suffix(".provenance.json").exists()


def test_resume_rejects_changed_samples_and_old_checkpoint(tmp_path):
    config = {"summary_protocol": SUMMARY_PROTOCOL, "scoring": SCORING, "samples": 3}
    bind_run_config(tmp_path, config)
    bind_run_config(tmp_path, config)
    with pytest.raises(ValueError, match="settings changed"):
        bind_run_config(tmp_path, {**config, "samples": 10})
    old = tmp_path / "old"
    write(old / "baseline_results.json", [])
    with pytest.raises(ValueError, match="relabeled"):
        bind_run_config(old, config)


def test_roster_matches_predeclared_family():
    family = json.loads((ROOT / "configs/perturbation_analysis.json").read_text())
    shell = (ROOT / "scripts/run_roster.sh").read_text()
    import re
    entries = re.findall(r'^  "([^\"]+):(\d+)"$', shell, re.M)
    roster = [model for model, _ in entries]
    workers = [int(value) for _, value in entries]
    assert roster == family["models"]
    assert workers == [69] * 6 and family["workers_per_model"] == 69
    assert len(roster) == 6 and family["expected_comparisons"] == 30
    assert "openai/gpt-5.6-sol" in roster and "anthropic/claude-opus-4.6" in roster
    qwen = [model for model in roster if model.startswith("qwen/")]
    assert qwen == ["qwen/qwen3.8-27b", "qwen/qwen3.8-flash"]
    assert all("max" not in model for model in qwen)
    assert not any("gemini" in model for model in roster)


def test_resume_retries_incomplete_units_without_duplicate_result_rows(tmp_path):
    from experiments.checkpoint import Checkpoint
    import run_perturbation_openai as runner
    checkpoint = Checkpoint(tmp_path / "run.jsonl")
    checkpoint.record("bad", {"ratings": [90, None, 90]})
    checkpoint.record("good", {"ratings": [10, 10, 10]})
    calls = []
    def work(unit):
        calls.append(unit["key"])
        return {"ratings": [90, 90, 90]}
    rows = runner._fan_out([{"key": "bad"}, {"key": "good"}], work, checkpoint, "test", 1, samples=3)
    assert calls == ["bad"] and len(rows) == 2
    assert len(checkpoint.rows()) == 3  # Raw attempts remain append-only evidence.
    checkpoint.close()
