"""Semantic coverage checks for the 1,000 atomic-target cohort."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.validate_eval_dataset import MANIFEST, REPO, validate


class EvaluationDatasetTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_current_atomic_cohort(self):
        result = validate(self.config)
        self.assertEqual((result["instances"], result["judgments"]), (1000, 947))
        self.assertEqual(result["unique_atomic_targets"], 1000)
        self.assertEqual(result["versions"], 1)
        self.assertEqual(result["annual_counts"], self.config["dataset"]["annual_counts"])
        self.assertEqual(result["labels"], {"violation": 700, "no_violation": 300})

    def test_current_summaries_are_complete(self):
        result = validate(self.config, require_complete=True)
        self.assertEqual(result["usable_summaries"], 947)
        self.assertEqual(result["missing_slots_zero_based"], [])
        self.assertEqual(result["warnings"], [])

    def test_require_complete_rejects_missing_summary(self):
        payload = json.loads(
            (REPO / self.config["summaries"]["path"]).read_text(encoding="utf-8")
        )
        item_id = sorted(payload["summaries"])[0]
        payload["summaries"][item_id][0] = None
        payload["n_complete"] -= 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "incomplete.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.config["summaries"].update(
                path=str(path),
                complete_judgments=946,
                usable_summaries=946,
                missing_slots_zero_based=[[item_id, 0]],
            )
            with self.assertRaisesRegex(ValueError, "Full-coverage run"):
                validate(self.config, require_complete=True)

    def test_wrong_summarizer_fails(self):
        self.config["summaries"]["summarizer"] = "x-ai/grok-4.6"
        with self.assertRaisesRegex(ValueError, "Summarizer mismatch"):
            validate(self.config)

    def test_annual_distribution_drift_fails(self):
        self.config["dataset"]["annual_counts"]["2026"] = 68
        with self.assertRaisesRegex(ValueError, "Annual distribution mismatch"):
            validate(self.config)

    def test_duplicate_atomic_target_fails(self):
        rows = json.loads(
            (REPO / self.config["dataset"]["path"]).read_text(encoding="utf-8")
        )
        rows[1] = copy.deepcopy(rows[0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicated.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            self.config["dataset"]["path"] = str(path)
            with self.assertRaisesRegex(ValueError, "Duplicate atomic targets"):
                validate(self.config)

    def test_cilei_rosip_target_is_country_and_issue_specific(self):
        rows = json.loads(
            (REPO / self.config["dataset"]["path"]).read_text(encoding="utf-8")
        )
        row = next(value for value in rows if value["item_id"] == "001-211017")
        self.assertEqual(row["target_respondent"], "the Republic of Moldova")
        self.assertEqual(row["article_full"], "13")
        self.assertIn("second applicant", row["target_issue"])
        self.assertIn("Republic of Moldova", row["target_question"])
        self.assertNotIn("Russia", row["target_question"])


if __name__ == "__main__":
    unittest.main()
