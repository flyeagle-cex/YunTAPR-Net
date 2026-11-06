"""Artificial exact discrete laws only; no project payloads or metric reruns."""
import math
import unittest

import numpy as np

from tools.research_readiness.extreme_diagnostic_candidates import exceedance_bounds
from yuntapr.experimental.research_readiness.tail_identifiability import (
    DELTA_AT_ZERO, UNKNOWN_NONRAIN, threshold_identifiability,
)


class TailIdentifiabilityTests(unittest.TestCase):
    def setUp(self):
        # Equal masses at 1..64 have exact generalized-inverse quantiles
        # Q((i-.5)/32)=2i-1. The nodes remain strictly increasing despite atoms.
        self.atoms = np.arange(1., 65.)
        self.q = np.array([[math.log1p(float(x)) for x in self.atoms[::2]]])

    def envelope(self, p, threshold, nonrain=DELTA_AT_ZERO, cutoff=None):
        return threshold_identifiability([p], self.q, threshold,
                                         nonrain_component=nonrain,
                                         probability_cutoff=cutoff)

    def assert_encloses(self, bounds, exact):
        self.assertLessEqual(bounds.lower[0], exact + 1e-15)
        self.assertGreaterEqual(bounds.upper[0] + 1e-15, exact)

    def test_discrete_threshold_atoms_including_first_and_last_nodes(self):
        for p in (0., .7, 1.):
            for threshold in (.5, 1., 20., 21., 63., 64., 80.):
                with self.subTest(p=p, threshold=threshold):
                    result = self.envelope(p, threshold)
                    strict = p * np.mean(self.atoms > threshold)
                    inclusive = p * np.mean(self.atoms >= threshold)
                    mass = p * np.mean(self.atoms == threshold)
                    self.assert_encloses(result.strict_exceedance, strict)
                    self.assert_encloses(result.inclusive_exceedance, inclusive)
                    self.assert_encloses(result.cdf_right_limit, 1 - strict)
                    self.assert_encloses(result.cdf_left_limit, 1 - inclusive)
                    self.assert_encloses(result.threshold_mass, mass)

    def test_at_node_inclusive_is_not_mistaken_for_strict(self):
        result = self.envelope(1., 21.)
        exact_inclusive = np.mean(self.atoms >= 21.)
        self.assertGreater(exact_inclusive, result.strict_exceedance.upper[0])
        self.assert_encloses(result.inclusive_exceedance, exact_inclusive)
        self.assertFalse(result.threshold_mass_identified[0])

    def test_same_quantiles_allow_different_upper_tails(self):
        altered = self.atoms.copy(); altered[-1] = 100.
        # Changing only the last atom does not change any of the 32 quantiles.
        np.testing.assert_array_equal(altered[::2], self.atoms[::2])
        result = self.envelope(.8, 80.)
        for atoms in (self.atoms, altered):
            self.assert_encloses(result.strict_exceedance, .8 * np.mean(atoms > 80.))
        self.assertGreater(result.strict_exceedance.upper[0], 0.)
        self.assertFalse(result.strict_probability_identified[0])

    def test_occurrence_boundary_does_not_invent_nonrain_delta_zero(self):
        for p in (0., .7, 1.):
            result = self.envelope(p, .1, UNKNOWN_NONRAIN)
            self.assert_encloses(result.strict_exceedance, p)
            # Two actual laws share p and conditional quantiles: put all
            # remaining mass at zero or exactly .1. Their >=.1 differs.
            for exact_inclusive in (p, 1.):
                self.assert_encloses(result.inclusive_exceedance, exact_inclusive)
                self.assert_encloses(result.threshold_mass, exact_inclusive - p)
            self.assertEqual(result.inclusive_probability_identified[0], p == 1.)

    def test_explicit_delta_zero_resolves_occurrence_boundary(self):
        result = self.envelope(.7, .1, DELTA_AT_ZERO)
        np.testing.assert_array_equal(result.inclusive_exceedance.lower, [.7])
        np.testing.assert_array_equal(result.inclusive_exceedance.upper, [.7])
        np.testing.assert_array_equal(result.threshold_mass.upper, [0.])
        self.assertTrue(result.strict_probability_identified[0])
        self.assertTrue(result.inclusive_probability_identified[0])
        self.assertTrue(result.threshold_mass_identified[0])

    def test_zero_occurrence_resolves_above_boundary_but_unit_occurrence_does_not(self):
        zero = self.envelope(0., 20.)
        for bounds in (zero.strict_exceedance, zero.inclusive_exceedance, zero.threshold_mass):
            np.testing.assert_array_equal(bounds.lower, [0.])
            np.testing.assert_array_equal(bounds.upper, [0.])
        self.assertTrue(zero.strict_probability_identified[0])
        self.assertFalse(self.envelope(1., 20.).strict_probability_identified[0])

    def test_inherited_strict_bounds_are_reused_without_formula_change(self):
        expected = exceedance_bounds([.6], self.q, 21.)
        result = self.envelope(.6, 21.)
        np.testing.assert_array_equal(result.strict_exceedance.lower, expected.lower)
        np.testing.assert_array_equal(result.strict_exceedance.upper, expected.upper)

    def test_threshold_monotonicity_for_both_comparisons(self):
        values = [self.envelope(.7, r) for r in (.1, .5, 1., 20., 21., 63., 80.)]
        for left, right in zip(values, values[1:]):
            for field in ("strict_exceedance", "inclusive_exceedance"):
                a, b = getattr(left, field), getattr(right, field)
                self.assertTrue(np.all(a.lower >= b.lower))
                self.assertTrue(np.all(a.upper >= b.upper))

    def test_strict_and_inclusive_decisions_can_differ_at_atom_boundary(self):
        result = self.envelope(1., 21., cutoff=44 / 64)
        self.assertTrue(result.strict_decision["guaranteed_negative"][0])
        self.assertTrue(result.inclusive_decision["unresolved"][0])
        self.assertIsNone(self.envelope(1., 21.).strict_decision)

    def test_source_integrity_is_not_bypassed_at_zero_probability(self):
        bad = self.q.copy(); bad[0, 5] = bad[0, 4]
        with self.assertRaises(ValueError):
            threshold_identifiability([0.], bad, 20., nonrain_component=DELTA_AT_ZERO)
        bad = self.q.copy(); bad[0, 2] = np.nan
        with self.assertRaises(ValueError):
            threshold_identifiability([0.], bad, 20., nonrain_component=DELTA_AT_ZERO)

    def test_nonrain_assumption_must_be_explicit(self):
        with self.assertRaises(ValueError):
            self.envelope(.7, .1, "CONTINUOUS_BY_NAME")
        with self.assertRaises(TypeError):
            threshold_identifiability([.7], self.q, .1)

    def test_numeric_underflow_is_not_false_exact_identification(self):
        with self.assertRaises(FloatingPointError):
            self.envelope(np.nextafter(0., 1.), 80.)


if __name__ == "__main__":
    unittest.main()
