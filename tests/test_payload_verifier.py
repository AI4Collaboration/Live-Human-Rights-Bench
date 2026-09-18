"""The outgoing-message verifier exercises the current full-case and summary arms without network calls."""

import json
from pathlib import Path
import subprocess
import sys

from experiments.targets import provision_name, target_question


def case(item_id, article, code, respondent, issue, label, text):
    return {
        "item_id": item_id,
        "case_name": f"Fixture {item_id}",
        "article": article,
        "article_full": article,
        "violation_label": label,
        "full_case_text_no_verdict": text,
        "target_respondent_code": code,
        "target_respondent": respondent,
        "target_provision": provision_name(article),
        "target_issue": issue,
        "target_aspect": "unspecified",
        "target_question": target_question(respondent, article, issue),
        "target_status": "verified",
    }


def test_real_runner_with_offline_fixture(tmp_path):
    folder = tmp_path / "data/processed"
    config_folder = tmp_path / "configs"
    folder.mkdir(parents=True)
    config_folder.mkdir()
    cases = [
        case(
            "offline-one", "3", "AAA", "State A", "detention conditions",
            "violation", "A factual detention record.",
        ),
        case(
            "offline-two", "6", "BBB", "State B", "fairness of the hearing",
            "no_violation", "A factual hearing record.",
        ),
    ]
    summaries = {
        "offline-one": ["A short detention record."],
        "offline-two": ["A short hearing record."],
    }
    dataset_id = "offline-fixture-atomic-v1"
    payload = {
        "dataset_id": dataset_id,
        "summarizer": "fixture/summarizer",
        "versions": 1,
        "n_judgments": 2,
        "n_complete": 2,
        "summaries": summaries,
    }
    manifest = {
        "dataset_id": dataset_id,
        "dataset": {
            "target_contract": {
                "unit": "one judgment, one respondent State, one provision, one sub-conclusion"
            }
        },
        "summaries": {"summarizer": "fixture/summarizer", "versions": 1},
    }
    (folder / "echr_unified.json").write_text(json.dumps(cases), encoding="utf-8")
    (folder / "summaries_dsv41flash.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    (config_folder / "evaluation_dataset.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    code = """import sys,json
from pathlib import Path
import scripts.verify_model_input_payloads as verifier
verifier.ROOT = Path(sys.argv[1])
print(json.dumps(verifier.verify()))
"""
    output = subprocess.check_output(
        [sys.executable, "-X", "utf8", "-c", code, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],
    )
    report = json.loads(output)
    assert report["status"] == "PASSED"
    assert report["dataset_id"] == dataset_id
    assert report["total_checks"] == 4
    assert report["outgoing_message_checks"] == {
        "baseline": 2,
        "summarization": 2,
    }
    assert report["network_requests"] == 0
    assert report["gold_label_sentinel_hits"] == 0
