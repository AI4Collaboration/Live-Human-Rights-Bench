"""Exercise the real runner with a fake transport, inspecting every outgoing message.

No credentials, HTTP requests, model outputs, or MLflow services are used. Gold
labels are replaced with a sentinel that must never occur in any model message.
"""
import argparse
from collections import Counter
import contextlib
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
# The runner's logging side effects are disabled before it is imported.
sys.modules["mlflow"] = MagicMock()
import run_perturbation_openai as runner
from input_gate import release, verify_cases, verify_summaries, file_digest
from checkpoint import Checkpoint

SENTINEL = "GOLD_LABEL_MUST_NEVER_REACH_MODEL_7e93c43a"


def verify():
    spec = release()
    if not spec:
        raise ValueError("No approved input release")
    cases_path = ROOT / "data/processed/echr_unified.json"
    summaries_path = ROOT / "data/processed/summaries_dsv41flash.json"
    if file_digest(cases_path) != spec["dataset_sha256_lf"] or file_digest(summaries_path) != spec["summaries_sha256_lf"]:
        raise ValueError("Canonical file identity does not match the approved release")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    summaries = json.loads(summaries_path.read_text(encoding="utf-8"))["summaries"]
    verify_cases(cases)
    verify_summaries(summaries)
    expected_prompts = set()
    for case in cases:
        texts = [runner.case_text(case), *summaries[case["item_id"]]]
        for text in texts:
            for template in (runner.PREDICTIVE_TEMPLATE, runner.NORMATIVE_TEMPLATE, runner.FACTUAL_TEMPLATE):
                expected_prompts.add(template.format(case_text=text, article=case["article"],
                                                    article_title=runner.article_title(case)))
    cases = [{**row, "violation_label": SENTINEL} for row in cases]
    calls, history_hashes, stage = Counter(), set(), "baseline"

    def complete(**kwargs):
        messages = kwargs["messages"]
        raw = json.dumps(messages, ensure_ascii=False)
        if SENTINEL in raw or "violation_label" in raw:
            raise AssertionError("Gold-label field leaked into model messages")
        if messages[0] != {"role": "system", "content": runner.SYSTEM_PROMPT}:
            raise AssertionError("Unexpected system message")
        if messages[1]["role"] != "user" or messages[1]["content"] not in expected_prompts:
            raise AssertionError("The actual model prompt contains unapproved or altered text")
        if len(messages) > 2 and messages[2:] != [
            {"role": "assistant", "content": "80"},
            {"role": "user", "content": runner.RECONSIDERATION_PROMPT}]:
            raise AssertionError("Unexpected reconsideration history")
        calls[stage] += 1
        history_hashes.add(hashlib.sha256(raw.encode("utf-8")).hexdigest())
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="80"))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete)))
    with contextlib.redirect_stdout(io.StringIO()):
        baseline = runner.run_baseline(client, "offline-no-model", cases, 1,
                                       ckpt=Checkpoint("offline-disabled", enabled=False), workers=1)
        stage = "summarization"
        summary_results = runner.run_summarization(client, "offline-no-model", cases, 1, baseline, summaries,
                                                  ckpt=Checkpoint("offline-disabled", enabled=False), workers=1)
        stage = "framing"
        framing = runner.run_framing(client, "offline-no-model", cases, 1, summaries, baseline,
                                    ckpt=Checkpoint("offline-disabled", enabled=False), workers=1)
        stage = "reconsideration"
        reconsideration = runner.run_reconsideration(client, "offline-no-model", cases, 1, baseline,
                                                    ckpt=Checkpoint("offline-disabled", enabled=False), workers=1)
    n = len(cases)
    expected_calls = {"baseline": n, "summarization": n*spec["versions"], "framing": 3*n, "reconsideration": 2*n}
    if dict(calls) != expected_calls:
        raise AssertionError(f"Unexpected transport coverage: {dict(calls)}")
    if [len(baseline), len(summary_results), len(framing), len(reconsideration)] != [n, n*spec["versions"], 3*n, n]:
        raise AssertionError("A runner silently skipped an instance")
    return {"status": "PASSED", "mode": "offline_fake_transport_not_an_experiment",
            "release_id": spec["release_id"], "dataset_sha256_lf": spec["dataset_sha256_lf"],
            "summaries_sha256_lf": spec["summaries_sha256_lf"], "instances": n,
            "outgoing_message_checks": dict(calls), "total_checks": sum(calls.values()),
            "unique_message_hashes": len(history_hashes), "gold_label_sentinel_hits": 0,
            "unapproved_initial_prompts": 0, "network_requests": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = verify()
    if args.out:
        args.out.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
