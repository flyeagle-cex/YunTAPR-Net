"""Independent mathematical examples; no research data or model evaluation."""
import importlib.util
import itertools
import math
from pathlib import Path
import sys
import unittest

import numpy as np

MODULE = Path(__file__).resolve().parents[2] / "tools/research_readiness/extreme_diagnostic_candidates.py"
SPEC = importlib.util.spec_from_file_location("extreme_diagnostic_candidates", MODULE)
candidate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = candidate
SPEC.loader.exec_module(candidate)


class ProbabilityBoundsTests(unittest.TestCase):
    def setUp(self):
        self.tau = (np.arange(32) + .5) / 32
        self.q = (1 + 3 * self.tau)[None, :]

    def test_known_uniform_log_distribution_is_enclosed(self):
        # Z|rain ~ Uniform[1,4] has the stated exact quantile function.
        r = math.expm1(2.8)
        bounds = candidate.exceedance_bounds([.7], self.q, r)
        exact = .7 * (4 - math.log1p(r)) / 3
        self.assertLessEqual(bounds.lower[0], exact)
        self.assertGreaterEqual(bounds.upper[0], exact)
        self.assertLessEqual(bounds.upper[0] - bounds.lower[0], .7 / 32 + 1e-15)

    def test_upper_tail_is_an_interval_not_a_zero_probability(self):
        bounds = candidate.exceedance_bounds([.8], self.q, math.expm1(5))
        self.assertEqual(bounds.lower[0], 0.)
        self.assertEqual(bounds.upper[0], .8 / 64)

    def test_exact_q32_boundary_uses_strict_exceedance(self):
        q = np.linspace(.2, math.log1p(20), 32)[None, :]
        bounds = candidate.exceedance_bounds([1.], q, 20.)
        self.assertEqual(bounds.upper[0], 1 / 64)

    def test_occurrence_threshold_retains_occurrence_probability(self):
        bounds = candidate.exceedance_bounds([.7], self.q, .1)
        self.assertEqual(bounds.lower[0], .7)
        self.assertEqual(bounds.upper[0], .7)

    def test_zero_occurrence_probability_remains_zero(self):
        bounds = candidate.exceedance_bounds([0.], self.q, 20.)
        self.assertEqual(bounds.lower[0], bounds.upper[0])
        self.assertEqual(bounds.upper[0], 0.)

    def test_bounds_decrease_with_threshold(self):
        pairs = [candidate.exceedance_bounds([.7], self.q, t) for t in [5., 10., 20., 50.]]
        self.assertTrue(all(a.lower[0] >= b.lower[0] and a.upper[0] >= b.upper[0]
                            for a, b in zip(pairs, pairs[1:])))

    def test_invalid_probability_or_quantiles_are_rejected(self):
        for p, q in [([1.1], self.q), ([float("nan")], self.q),
                     ([.5], self.q[:, ::-1]), ([.5], np.ones((1, 32))),
                     ([.5], self.q[:, :31]), ([.5], self.q - 10)]:
            with self.subTest(p=p, shape=q.shape), self.assertRaises(ValueError):
                candidate.exceedance_bounds(p, q, 20.)

    def test_invalid_threshold_is_rejected(self):
        for threshold in [True, -.1, .09, float("inf"), "20"]:
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                candidate.exceedance_bounds([.5], self.q, threshold)

    def test_point_intervals_reproduce_brier(self):
        y = np.array([True, False, True, False])
        p = np.array([.2, .4, .7, .8])
        expected = float(((p - y) ** 2).mean())
        self.assertEqual(candidate.brier_bounds(y, p, p), (expected, expected))

    def test_brier_bounds_match_exhaustive_endpoint_extrema(self):
        y = np.array([True, False, True, False])
        lo, hi = np.array([.1, .3, .5, .2]), np.array([.8, .4, .7, .9])
        values = [float(((np.array(p) - y) ** 2).mean())
                  for p in itertools.product(*zip(lo, hi))]
        bounds = candidate.brier_bounds(y, lo, hi)
        self.assertAlmostEqual(bounds[0], min(values))
        self.assertAlmostEqual(bounds[1], max(values))

    def test_auroc_bounds_match_brute_force_with_ties(self):
        y = np.array([True, False, True, False])
        lo, hi = np.array([.2, .2, .6, .5]), np.array([.5, .5, .8, .7])
        def auc(p):
            return sum(float(a > b) + .5 * float(a == b)
                       for a in p[y] for b in p[~y]) / 4
        values = [auc(np.array(p)) for p in itertools.product(*zip(lo, hi))]
        self.assertEqual(candidate.auroc_bounds(y, lo, hi), (min(values), max(values)))

    def test_auroc_single_class_is_undefined(self):
        self.assertIsNone(candidate.auroc_bounds(np.array([True, True]), [.1, .2], [.3, .4]))

    def test_decision_boundary_does_not_hide_ambiguity(self):
        result = candidate.decision_identification([.5, .1, .49], [.8, .499, .5], .5)
        np.testing.assert_array_equal(result['guaranteed_positive'], [True, False, False])
        np.testing.assert_array_equal(result['guaranteed_negative'], [False, True, False])
        np.testing.assert_array_equal(result['unresolved'], [False, False, True])

    def test_population_and_label_failures_are_explicit(self):
        for y, lo, hi in [(np.array([1]), [.1], [.2]),
                          (np.array([True]), [.8], [.2]),
                          (np.array([], dtype=bool), [], []),
                          (np.array([True, False]), [.1], [.2])]:
            with self.subTest(y=y), self.assertRaises(ValueError):
                candidate.brier_bounds(y, lo, hi)


if __name__ == "__main__":
    unittest.main()
