"""Numerical and cohort checks for the offline reliability analyses."""

import itertools
import unittest

import numpy as np

from analysis.analyze_reliability_controls import (
    bootstrap_totals,
    category,
    complete,
    finite,
    mean_absolute_cross,
    sampling_metrics,
)


class ReliabilityControlsTests(unittest.TestCase):
    def test_threshold_boundaries(self):
        np.testing.assert_array_equal(category([0, 39.9, 40, 50, 60, 60.1, 100]),
                                      [-1, -1, 0, 0, 0, 1, 1])

    def test_missing_scores_and_incomplete_conversations(self):
        for value in (None, True, "80", float("nan"), float("inf"), -1, 101):
            self.assertFalse(finite(value))
        row = dict(scores=[80, 40, 10], any_turn_persuaded=True, final_persuaded=True)
        self.assertTrue(complete(row))
        for changes in ({"scores": [80, 10]}, {"scores": [80, None, 10]},
                        {"final_persuaded": None}, {"any_turn_persuaded": 1}):
            self.assertFalse(complete({**row, **changes}))

    def test_fast_absolute_distance_matches_cartesian_product(self):
        for a, b in (([1, 1, 7], [2, 5]), ([40, 60], [40, 40, 60]),
                     ([-2.5, 0, 100], [0.5, 0.5, 99])):
            expected = np.mean([abs(x - y) for x, y in itertools.product(a, b)])
            self.assertAlmostEqual(mean_absolute_cross(np.array(a), np.array(b)), expected)

    def test_subset_probabilities_match_direct_enumeration(self):
        reference = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        summary = np.array([5, 5, 15, 25, 35, 45, 65, 75, 95, 95])
        selections = list(itertools.combinations(range(10), 5))
        a = np.array([reference[list(s)].mean() for s in selections])
        b = np.array([summary[list(s)].mean() for s in selections])
        ca, cb = category(a), category(b)
        actual = sampling_metrics(reference, summary)
        self.assertAlmostEqual(actual["cross_input_change_pct"],
                               100 * np.mean(ca[:, None] != cb[None, :]))
        self.assertAlmostEqual(actual["cross_input_strict_reversal_pct"],
                               100 * np.mean(ca[:, None] * cb[None, :] == -1))
        self.assertAlmostEqual(actual["cross_input_absolute_score_difference"],
                               np.abs(a[:, None] - b[None, :]).mean())
        complement_means = np.array([
            reference[[i for i in range(10) if i not in s]].mean() for s in selections])
        self.assertAlmostEqual(actual["reference_split_change_pct"],
                               100 * np.mean(ca != category(complement_means)))

    def test_identical_stable_inputs_have_zero_changes(self):
        actual = sampling_metrics([80] * 10, [80] * 10)
        self.assertTrue(all(value == 0 for value in actual.values()))

    def test_deterministic_opposite_inputs_have_full_excess(self):
        actual = sampling_metrics([20] * 10, [80] * 10)
        for name in ("cross_input_change_pct", "cross_input_strict_reversal_pct",
                     "cross_minus_reference_change_pp", "cross_minus_symmetric_change_pp"):
            self.assertEqual(actual[name], 100)
        self.assertEqual(actual["reference_split_change_pct"], 0)
        self.assertEqual(actual["summary_split_change_pct"], 0)
        self.assertEqual(actual["cross_input_absolute_score_difference"], 60)

    def test_judgment_bootstrap_keeps_provisions_together(self):
        # Two targets belong to judgment A and one to judgment B. Each draw
        # resamples two whole judgments, so only these three totals are possible.
        values = np.array([[1, 10], [1, 20], [1, 100]], dtype=float)
        point, boot, n_groups = bootstrap_totals(values, ["A", "A", "B"], draws=100, seed=731)
        np.testing.assert_array_equal(point, [3, 130])
        self.assertEqual(n_groups, 2)
        self.assertEqual(set(map(tuple, boot)), {(4, 60), (3, 130), (2, 200)})


if __name__ == "__main__":
    unittest.main()
