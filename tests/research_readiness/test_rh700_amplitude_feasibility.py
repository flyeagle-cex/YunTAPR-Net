import unittest

import numpy as np

from tools.research_readiness.rh700_amplitude_feasibility import (
    POINT_ROUNDING_BOUNDARY, measure, required_interval,
)


def fixture(humidity, truth=(35., 4., .8), probability=(.75, .75, .75), valid=(True, True, True)):
    nodes = np.tile(np.log1p(np.linspace(14, 19, 32)), (3, 1))
    return np.array(probability), nodes, np.array(truth, dtype=np.float32), np.array(humidity), np.array(valid)


class RH700AmplitudeFeasibilityTests(unittest.TestCase):
    def test_high_humidity_negative_blocks_all_uniform_shifts(self):
        inputs = fixture([90., 95., 90.])
        bounds = required_interval(*inputs)
        self.assertFalse(bounds["analytically_nonempty"])
        self.assertLess(bounds["point_stop"], bounds["first_hit"])
        result = measure(12., *inputs)
        self.assertEqual((result["true_hits"], result["false_hits"]), (1, 2))
        self.assertEqual(result["additional_q32_false_support"], 2)
        self.assertGreater(result["weak_log_pinball_delta"], 0.)

    def test_a_feasible_fixture_has_a_single_verifiable_witness(self):
        inputs = fixture([100., 5., np.nan], valid=(True, True, False))
        interval = required_interval(*inputs)
        self.assertTrue(interval["analytically_nonempty"])
        self.assertLess(interval["first_hit"], 12.)
        self.assertLess(12., interval["upper"])
        result = measure(12., *inputs)
        self.assertEqual((result["true_hits"], result["false_hits"]), (1, 0))
        self.assertEqual(result["additional_q32_false_support"], 0)
        self.assertLess(result["physical_strong_pinball_delta"], 0.)
        self.assertAlmostEqual(result["weak_log_pinball_delta"], 0., places=14)

    def test_zero_probability_and_q32_support_are_separate_guards(self):
        inputs = fixture([100., 5., 0.], probability=(.75, 0., .75))
        interval = required_interval(*inputs)
        self.assertIsNone(interval["point_stop"])
        self.assertAlmostEqual(interval["tail_stop"], 20.)
        self.assertFalse(required_interval(*fixture([100., 0., 0.], probability=(0., .75, .75)))["analytically_nonempty"])

    def test_fp32_threshold_rounds_exact_midpoint_down(self):
        self.assertEqual(np.float32(POINT_ROUNDING_BOUNDARY), np.float32(20.))
        self.assertGreater(np.float32(np.nextafter(POINT_ROUNDING_BOUNDARY, np.inf)), np.float32(20.))


if __name__ == "__main__":
    unittest.main()
