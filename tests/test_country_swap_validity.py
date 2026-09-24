import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.country_swap_validity import build_manifest, bind_manifest
from experiments import stateswap_summary_run as runner


class CountrySwapValidityTests(unittest.TestCase):
    def setUp(self):
        self.targets={k:v for d in runner.TARGET_SETS.values() for k,v in d.items()}

    def build(self,text,respondent="Belgium",arms=("UK",)):
        countries={k:self.targets[k] for k in arms}
        case=dict(item_id="example",article_full="3",target_respondent=respondent)
        with patch.object(runner,"TARGETS",countries):
            return build_manifest([case],{"example":[text]},runner.COUNTRIES,countries,runner.swap)

    def test_cross_border_collapse_is_excluded(self):
        m=self.build("A Turkish national was pushed back from Greece to Türkiye.","Greece",("Turkey",))
        self.assertEqual(m["eligible_targets"],0)
        self.assertIn("destination_already_present:Turkey",m["rows"][0]["reasons"])

    def test_location_dependent_setting_is_excluded(self):
        m=self.build("The Macedonian applicant sought restitution on the Ohrid lakeshore.","North Macedonia")
        self.assertIn("environment",m["rows"][0]["reasons"])

    def test_generic_domestic_record_passes(self):
        m=self.build("A Belgian applicant was slapped by a police officer during questioning.")
        self.assertEqual(m["eligible_targets"],1)
        self.assertNotEqual(m["rows"][0]["original_sha256"],m["rows"][0]["transformed_sha256"]["UK"])

    def test_noop_and_missing_respondent_fail_closed(self):
        self.assertEqual(self.build("The British applicant was arrested.","the United Kingdom")["eligible_targets"],0)
        self.assertIn("unresolved_respondent",self.build("Unknown location.","Unresolved")["rows"][0]["reasons"])

    def test_checkpoint_rejects_changed_screen(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"manifest.json"
            first=self.build("A Belgian applicant was arrested.")
            bind_manifest(path,first)
            bind_manifest(path,first)
            with self.assertRaises(ValueError):
                bind_manifest(path,self.build("A Belgian applicant crossed a border."))

    def test_preflight_never_calls_model_or_requires_api_key(self):
        with tempfile.TemporaryDirectory() as d:
            args=["runner","--model","offline/check","--targets","uk",
                  "--validity-targets","uk","turkey","--preflight-only","--out",d]
            with patch("sys.argv",args),patch.dict("os.environ",{},clear=True),patch.object(runner,"call") as call:
                runner.main()
                call.assert_not_called()
            manifest=json.loads((Path(d)/"offline_check/context_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["targets"],1000)
            self.assertEqual(manifest["eligible_targets"],574)
            self.assertFalse(list(Path(d).rglob("*results.jsonl")))


if __name__=="__main__":
    unittest.main()
