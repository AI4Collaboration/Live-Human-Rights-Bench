"""Exercise launchers with a local stub; no model clients are invoked."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
GIT_BASH = Path("C:/Program Files/Git/bin/bash.exe")
BASH = str(GIT_BASH) if os.name == "nt" and GIT_BASH.exists() else shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="Bash is required for shell launcher checks")


@pytest.fixture
def launch(tmp_path):
    stub = tmp_path / "fake-python"
    stub.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\037" "$@" >> "$FAKE_PYTHON_LOG"\n'
        'printf "\\n" >> "$FAKE_PYTHON_LOG"\nexit "${FAKE_PYTHON_EXIT:-0}"\n',
        encoding="utf-8", newline="\n",
    )
    stub.chmod(0o755)
    log = tmp_path / "calls.log"

    def run(name, args=("offline/model",), **overrides):
        # Normalize checkout line endings so this also tests Windows checkouts.
        script = tmp_path / name
        script.write_text((ROOT / name).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        env = {key: value for key, value in os.environ.items()
               if not any(part in key.upper() for part in ("KEY", "TOKEN", "SECRET"))}
        for key in ("BENCHMARK_VENV", "OUT", "SAMPLES", "WORKERS", "SLURM_SUBMIT_DIR"):
            env.pop(key, None)
        env.update(PYTHON=stub.as_posix(), SLURM_SUBMIT_DIR=ROOT.as_posix(),
                   FAKE_PYTHON_LOG=log.as_posix(), OPENROUTER_API_KEY="offline-test")
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        result = subprocess.run([BASH, str(script), *args], env=env, cwd=tmp_path,
                                capture_output=True, text=True, encoding="utf-8", timeout=20)
        calls = [line.rstrip("\x1f").split("\x1f") for line in
                 log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
        return result, calls

    return run


@pytest.mark.parametrize("script", ["oldmodels.sh", "syco_nationality.sh"])
@pytest.mark.parametrize("missing", ["model", "key"])
def test_missing_configuration_never_invokes_python(launch, script, missing):
    result, calls = launch(script, args=() if missing == "model" else ("offline/model",),
                           OPENROUTER_API_KEY=None if missing == "key" else "offline-test")
    assert result.returncode != 0
    assert not calls


@pytest.mark.parametrize("script", ["oldmodels.sh", "syco_nationality.sh", "syco_controls.sh",
                                     "stateswap_applicant.sh", "syco_cot.sh"])
def test_failure_stops_the_launcher_and_is_reported(launch, script):
    result, calls = launch(script, FAKE_PYTHON_EXIT="17")
    assert result.returncode == 17, result.stderr
    assert len(calls) == 1
    assert "Completed" not in result.stdout


def test_earlier_model_stages_use_separate_new_outputs(launch):
    result, calls = launch("oldmodels.sh", OUT="data/experiments/offline_test", SAMPLES="4", WORKERS="2")
    assert result.returncode == 0, result.stderr
    assert [call[0] for call in calls] == ["experiments/run_perturbation_fullcase.py",
        "experiments/paraphrase_run.py", "experiments/stateswap_summary_run.py"]
    assert calls[0][calls[0].index("--rq") + 1] == "all"
    for call, stage in zip(calls, ("fullcase", "paraphrase", "country_swap")):
        assert call[call.index("--model") + 1] == "offline/model"
        assert call[call.index("--samples") + 1] == "4"
        assert call[call.index("--workers") + 1] == "2"
        assert call[-1] == "data/experiments/offline_test/" + stage


@pytest.mark.parametrize("script,output", [
    ("oldmodels.sh", "earlier_models_new/fullcase"),
    ("syco_nationality.sh", "syco_nationality_new"),
    ("syco_controls.sh", "syco_controls_new"),
    ("stateswap_applicant.sh", "stateswap_applicant_new"),
    ("syco_cot.sh", "syco_cot_new"),
])
def test_defaults_do_not_target_published_results(launch, script, output):
    result, calls = launch(script)
    assert result.returncode == 0, result.stderr
    assert calls[0][-1] == "data/experiments/" + output
