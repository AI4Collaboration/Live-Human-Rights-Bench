"""Offline identity and coverage checks for the selected annual-balanced cohort."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.validate_eval_dataset import MANIFEST, REPO, sha256_lf, validate


class EvaluationDatasetTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_current_frozen_cohort(self):
        result = validate(self.config)
        self.assertEqual((result["instances"], result["judgments"]), (1000, 947))
        self.assertEqual(result["annual_counts"], self.config["dataset"]["annual_counts"])
        self.assertEqual(result["instance_coverage_by_version"], [995, 994, 998])

    def test_current_missing_slots_warn(self):
        result = validate(self.config)
        self.assertEqual(len(result["missing_slots_zero_based"]), 9)
        self.assertEqual(result["missing_judgments"], ["001-219988"])
        self.assertEqual(len(result["warnings"]), 1)

    def test_require_complete_fails(self):
        with self.assertRaisesRegex(ValueError, "9 missing summary slots"):
            validate(self.config, require_complete=True)

    def test_wrong_dataset_hash_fails(self):
        self.config["dataset"]["sha256_lf"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Dataset SHA256 mismatch"):
            validate(self.config)

    def test_wrong_summary_hash_fails(self):
        self.config["summaries"]["sha256_lf"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Summaries SHA256 mismatch"):
            validate(self.config)

    def test_wrong_summarizer_fails(self):
        self.config["summaries"]["summarizer"] = "x-ai/grok-4.6"
        with self.assertRaisesRegex(ValueError, "Summarizer mismatch"):
            validate(self.config)

    def test_annual_distribution_drift_fails(self):
        self.config["dataset"]["annual_counts"]["2026"] = 68
        with self.assertRaisesRegex(ValueError, "Annual distribution mismatch"):
            validate(self.config)

    def test_crlf_and_lf_hashes_match(self):
        lf = b'{\n  "judgment": "no violation"\n}\n'
        self.assertEqual(sha256_lf(lf), sha256_lf(lf.replace(b"\n", b"\r\n")))

    def test_duplicate_compound_keys_fail(self):
        rows = json.loads((REPO / self.config["dataset"]["path"]).read_text(encoding="utf-8"))
        rows[1] = copy.deepcopy(rows[0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicated.json"
            raw = json.dumps(rows).encode("utf-8")
            path.write_bytes(raw)
            self.config["dataset"].update(path=str(path), sha256_lf=sha256_lf(raw))
            with self.assertRaisesRegex(ValueError, "Duplicate compound instance keys"):
                validate(self.config)


if __name__ == "__main__":
    unittest.main()
