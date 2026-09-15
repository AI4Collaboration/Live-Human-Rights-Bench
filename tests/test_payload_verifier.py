"""The outgoing-message verifier must exercise all four arms without network calls."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def test_real_runner_with_offline_fixture(tmp_path):
    folder = tmp_path / "data/processed"
    folder.mkdir(parents=True)
    cases = [{"item_id": "offline-one", "case_name": "Fixture One", "article": "3",
              "violation_label": "violation", "full_case_text_no_verdict": "A factual detention record."},
             {"item_id": "offline-two", "case_name": "Fixture Two", "article": "6",
              "violation_label": "no_violation", "full_case_text_no_verdict": "A factual hearing record."}]
    summaries = {"offline-one": ["A short detention record."], "offline-two": ["A short hearing record."]}
    data_path, summary_path = folder / "echr_unified.json", folder / "summaries_dsv41flash.json"
    data_path.write_text(json.dumps(cases), encoding="utf-8")
    summary_path.write_text(json.dumps({"summaries": summaries}), encoding="utf-8")
    h = lambda value: hashlib.sha256(value).hexdigest()
    spec = {"status": "APPROVED", "release_id": "offline-fixture-not-a-dataset", "versions": 1,
            "dataset_sha256_lf": h(data_path.read_bytes()), "summaries_sha256_lf": h(summary_path.read_bytes()),
            "source_inputs": {r["item_id"]:h(r["full_case_text_no_verdict"].encode()) for r in cases},
            "summary_inputs": {k:[h(v[0].encode())] for k,v in summaries.items()}}
    (folder / "input_release.json").write_text(json.dumps(spec), encoding="utf-8")
    # Use a subprocess so the verifier's explicit MLflow stub cannot affect any
    # other test importing the production runner.
    code = """import sys,json
from pathlib import Path
import scripts.verify_model_input_payloads as verifier
import input_gate
verifier.ROOT = Path(sys.argv[1])
input_gate.RELEASE_PATH = verifier.ROOT / 'data/processed/input_release.json'
input_gate.CASES_PATH = verifier.ROOT / 'data/processed/echr_unified.json'
print(json.dumps(verifier.verify()))
"""
    output = subprocess.check_output([sys.executable, "-X", "utf8", "-c", code, str(tmp_path)],
                                     cwd=Path(__file__).resolve().parents[1])
    report = json.loads(output)
    assert report["status"] == "PASSED"
    assert report["total_checks"] == 14
    assert report["outgoing_message_checks"] == {"baseline": 2, "summarization": 2, "framing": 6, "reconsideration": 4}
    assert report["network_requests"] == 0 and report["gold_label_sentinel_hits"] == 0
