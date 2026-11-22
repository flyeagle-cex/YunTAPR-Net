import unittest

import numpy as np

from tools.research_readiness import mfc700_amplitude_bounds as bounded
from tools.research_readiness.rh700_amplitude_feasibility import TAU


def fixture(truth, low, high, probability=None, mfc=None, valid=None):
    truth = np.asarray(truth, dtype=np.float32)
    nodes = np.stack([np.log1p(np.linspace(lo, hi, len(TAU))) for lo, hi in zip(low, high)])
    return (
        np.asarray(np.ones(truth.size) if probability is None else probability),
        nodes,
        truth,
        np.asarray(np.full(truth.size, 5.) if mfc is None else mfc, dtype=np.float32),
        np.asarray(np.ones(truth.size, dtype=bool) if valid is None else valid),
    )


def physical_change(delta, knots, active_fraction):
    before = np.maximum(TAU * (knots / 20.), (TAU - 1.) * (knots / 20.))
    after = np.maximum(TAU * ((knots - delta) / 20.), (TAU - 1.) * ((knots - delta) / 20.))
    return float((after - before).mean() * active_fraction)


class MFC700AmplitudeBoundsTests(unittest.TestCase):
    def test_analytic_change_matches_the_frozen_physical_pinball(self):
        knots = np.random.default_rng(7).normal(0., 3., (7, len(TAU)))
        self.assertEqual(bounded._analytic_change(0., knots, .75), 0.)
        for delta in (1e-3, .37, 2.5, 6.3, 40.):
            self.assertAlmostEqual(
                bounded._analytic_change(delta, knots, .75),
                physical_change(delta, knots, .75), places=12)

    def test_a_feasible_fixture_has_one_verified_joint_witness(self):
        bounds = bounded.AmplitudeBounds()
        bounds.update(*fixture((21., 2.), (.5, .01), (2.5, 1.), probability=(1., .2)))
        report = bounds.finish()
        self.assertEqual(report["decision"], "LOCAL_JOINT_NECESSARY_CONDITIONS_NOT_EXCLUDED")
        self.assertTrue(report["local_joint_witness_verified"])
        self.assertGreater(report["first_hit_lower_open_mm_h"], 18.5)
        self.assertLess(report["first_hit_lower_open_mm_h"], 18.6)
        self.assertAlmostEqual(report["nonstrong_q32_upper_inclusive_mm_h"], 19., places=12)
        self.assertLess(report["strong_physical_pinball_delta_at_witness"], 0.)
        self.assertGreaterEqual(report["a_tp_at_witness"], 1)
        self.assertFalse(report["weak_guard_checked"])
        self.assertEqual(report["coefficient_fits"], 0)
        self.assertEqual((report["strong"], report["nonstrong"]), (1, 1))

    def test_untouched_mfc_gate_has_no_candidate_hit(self):
        bounds = bounded.AmplitudeBounds()
        bounds.update(*fixture((21., 2.), (.5, .01), (2.5, 1.), probability=(1., .2), mfc=(0., 5.)))
        report = bounds.finish()
        self.assertEqual(report["decision"], "STOP_NO_POTENTIAL_STRONG_HIT")
        self.assertIsNone(report["first_hit_lower_open_mm_h"])
        self.assertAlmostEqual(report["nonstrong_upper_inclusive_mm_h"], 19., places=12)

    def test_negative_ceiling_stops_the_uniform_shift(self):
        bounds = bounded.AmplitudeBounds()
        bounds.update(*fixture((21., 5.), (.5, 15.), (2.5, 19.), probability=(1., .99)))
        report = bounds.finish()
        self.assertEqual(report["decision"], "STOP_NEGATIVE_CEILING")
        self.assertGreater(report["first_hit_lower_open_mm_h"], 18.5)
        self.assertLess(report["nonstrong_upper_inclusive_mm_h"], 18.5)

    def test_nonpositive_knots_reject_uniform_improvement(self):
        bounds = bounded.AmplitudeBounds()
        bounds.update(*fixture((20.5,), (21.,), (22.,)))
        report = bounds.finish()
        self.assertEqual(report["decision"], "STOP_NO_STRONG_PINBALL_IMPROVEMENT")
        self.assertEqual(report["first_hit_lower_open_mm_h"], 0.)

    def test_update_rejects_malformed_or_non_ordered_inputs(self):
        bounds = bounded.AmplitudeBounds()
        probability, qlog, truth, mfc, valid = fixture((21.,), (.5,), (2.5,))
        with self.assertRaisesRegex(ValueError, "ordered nodes"):
            bounds.update(probability, np.full_like(qlog, np.log1p(2.)), truth, mfc, valid)
        with self.assertRaisesRegex(ValueError, "ordered nodes"):
            bounds.update(np.array([1.5]), qlog, truth, mfc, valid)
        with self.assertRaisesRegex(ValueError, "ordered nodes"):
            bounds.update(probability, qlog, truth.astype(np.float64), mfc, valid)
        with self.assertRaisesRegex(ValueError, "strong-population cap"):
            bounds.update(*fixture((21.,) * 485, (.5,) * 485, (2.5,) * 485))


if __name__ == "__main__":
    unittest.main()
