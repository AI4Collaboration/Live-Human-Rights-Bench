"""Exercise the full-case and summary arms with a fake transport and inspect its messages.

This is a semantic payload check. It makes no network requests and does not use
file or prompt hashes. A sentinel replaces the gold label and must never appear in
any model-visible message.
"""

import argparse
from collections import Counter
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import MagicMock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
sys.modules["mlflow"] = MagicMock()
import input_gate as gate
import run_perturbation_fullcase as runner
from checkpoint import Checkpoint


SENTINEL = "GOLD_LABEL_MUST_NEVER_REACH_MODEL_7e93c43a"


def _configure_gate():
    gate.MANIFEST_PATH = ROOT / "configs/evaluation_dataset.json"
    gate.CASES_PATH = ROOT / "data/processed/echr_unified.json"
    gate.SUMMARIES_PATH = ROOT / "data/processed/summaries_dsv41flash.json"
    gate.manifest.cache_clear()
    gate.canonical_cases.cache_clear()
    gate.canonical_summaries.cache_clear()


def verify():
    _configure_gate()
    cases = json.loads(gate.CASES_PATH.read_text(encoding="utf-8"))
    summary_payload = json.loads(gate.SUMMARIES_PATH.read_text(encoding="utf-8"))
    summaries = summary_payload["summaries"]
    gate.verify_cases(cases)
    gate.verify_summaries(summaries, metadata=summary_payload)

    expected_prompts = set()
    for case in cases:
        expected_prompts.add(
            runner.prompt_for(runner.PREDICTIVE_TEMPLATE, case, runner.case_text(case))
        )
        summary = summaries[case["item_id"]][0]
        expected_prompts.add(runner.prompt_for(runner.PREDICTIVE_TEMPLATE, case, summary))

    cases = [{**row, "gold_sentinel": SENTINEL} for row in cases]
    calls, unique_messages, stage = Counter(), set(), "baseline"

    def complete(**kwargs):
        messages = kwargs["messages"]
        serialized = json.dumps(messages, ensure_ascii=False, sort_keys=True)
        if SENTINEL in serialized or "violation_label" in serialized:
            raise AssertionError("Gold-label field leaked into model messages")
        if messages[0] != {"role": "system", "content": runner.SYSTEM_PROMPT}:
            raise AssertionError("Unexpected system message")
        if messages[1].get("role") != "user" or messages[1].get("content") not in expected_prompts:
            raise AssertionError("The model prompt contains unapproved or altered text")
        if len(messages) != 2:
            raise AssertionError("Unexpected conversation history")
        calls[stage] += 1
        unique_messages.add(serialized)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="80"))]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=complete))
    )
    disabled = lambda: Checkpoint(None, enabled=False)
    with contextlib.redirect_stdout(io.StringIO()):
        baseline = runner.run_baseline(
            client, "offline-no-model", cases, 1, ckpt=disabled(), workers=1
        )
        stage = "summarization"
        summary_results = runner.run_summarization(
            client, "offline-no-model", cases, 1, baseline, summaries,
            ckpt=disabled(), workers=1,
        )

    n = len(cases)
    expected_calls = {
        "baseline": n,
        "summarization": n,
    }
    if dict(calls) != expected_calls:
        raise AssertionError(f"Unexpected transport coverage: {dict(calls)}")
    if [len(baseline), len(summary_results)] != [n, n]:
        raise AssertionError("A runner silently skipped an atomic target")

    manifest = gate.manifest()
    return {
        "status": "PASSED",
        "mode": "offline_fake_transport_not_an_experiment",
        "runner": "experiments/run_perturbation_fullcase.py",
        "dataset_id": manifest["dataset_id"],
        "target_unit": manifest["dataset"]["target_contract"]["unit"],
        "instances": n,
        "judgments": len({row["item_id"] for row in cases}),
        "outgoing_message_checks": dict(calls),
        "total_checks": sum(calls.values()),
        "unique_outgoing_messages": len(unique_messages),
        "gold_label_sentinel_hits": 0,
        "unapproved_initial_prompts": 0,
        "network_requests": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = verify()
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
