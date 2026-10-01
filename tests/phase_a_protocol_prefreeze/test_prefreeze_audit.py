"""Independent numerical checks for protocol audit boundaries and aggregation."""
from pathlib import Path
import math
import sys
import unittest
import numpy as np
import torch

sys.path[:0] = [str(Path(__file__).resolve().parents[2]/"scripts"), str(Path(__file__).resolve().parents[2]/"src")]
from audit_phase_a_prefreeze import classify, exact_percentile, merge_moments, alpha_candidates, global_core_metric
from yuntapr.losses.focal import focal_bce_sum
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.models.probability_heads import B0Output


class PrefreezeNumericsTests(unittest.TestCase):
    def test_focal_positive_negative_alpha_at_zero_logit(self):
        z = torch.tensor([0., 0.], dtype=torch.float64)
        labels = torch.tensor([True, False])
        for gamma in (0, 1, 2, 3):
            positive = float(focal_bce_sum(z, labels, torch.tensor([True, False]), .25, gamma))
            negative = float(focal_bce_sum(z, labels, torch.tensor([False, True]), .25, gamma))
            self.assertAlmostEqual(positive, .25*.5**gamma*math.log(2))
            self.assertAlmostEqual(negative, .75*.5**gamma*math.log(2))

    def test_focal_mask_not_class_count_denominator(self):
        z = torch.tensor([0., 1000.], dtype=torch.float64)
        loss = focal_bce_sum(z, torch.tensor([True, False]), torch.tensor([True, False]), .5, 0)
        self.assertAlmostEqual(float(loss), .5*math.log(2))

    def test_point_one_negative_next_float_positive_and_missing_excluded(self):
        values = np.array([0., .1, np.nextafter(np.float32(.1), np.float32(1)), np.nan], dtype=np.float32)
        selected, positive = classify(values, np.array([True, True, True, False]))
        self.assertEqual(len(selected), 3)
        self.assertEqual(positive.tolist(), [False, False, True])

    def test_valid_nonfinite_raises(self):
        with self.assertRaises(ValueError):
            classify(np.array([np.nan], dtype=np.float32), np.array([True]))

    def test_balanced_alpha_equalizes_gamma_zero_class_mass(self):
        candidate = alpha_candidates(10, 90)["candidates"][2]
        self.assertAlmostEqual(candidate["alpha"], .9)
        self.assertAlmostEqual(candidate["alpha"]*10, candidate["negative_weight"]*90)
        self.assertIsNone(alpha_candidates(10, 90)["recommended_alpha"])

    def test_inverse_frequency_global_scale_not_equal_loss(self):
        result = alpha_candidates(10, 90)
        self.assertAlmostEqual(result["D_inverse_frequency"]["positive_weight_unit_expected_mean"], 5.)
        self.assertAlmostEqual(result["D_inverse_frequency"]["negative_weight_unit_expected_mean"], 1/.9/2)

    def test_exact_linear_percentile_float64_interpolation(self):
        x = np.array([.12, .19, 1.3, 7.4], dtype=np.float32)
        for fraction in (0, .01, .25, .5, .99, 1):
            expected = float(np.quantile(x.astype(np.float64), fraction, method="linear"))
            self.assertAlmostEqual(exact_percentile(x, fraction), expected)

    def test_merged_population_std_matches_direct_array(self):
        x, y = np.array([1., 2., 3.]), np.array([11., 15.])
        state = merge_moments((len(x), x.mean(), ((x-x.mean())**2).sum()), (len(y), y.mean(), ((y-y.mean())**2).sum()))
        combined = np.concatenate([x, y])
        self.assertAlmostEqual(state[1], combined.mean())
        self.assertAlmostEqual(math.sqrt(state[2]/state[0]), combined.std(ddof=0))

    def test_global_metric_invariant_to_unequal_batch_partition(self):
        batches = [{"valid_Yunnan_denominator": 8, "occ_numerator": 8., "qr_numerator": 16.},
                   {"valid_Yunnan_denominator": 1, "occ_numerator": 10., "qr_numerator": 20.}]
        result = global_core_metric(batches)
        self.assertEqual(result["val_core_loss"], 6.)
        whole = global_core_metric([{"valid_Yunnan_denominator": 9, "occ_numerator": 18., "qr_numerator": 36.}])
        self.assertEqual(result, whole)
        self.assertNotEqual(result["val_core_loss"], (3+30)/2)

    def test_zero_denominator_is_undefined_not_pass(self):
        self.assertEqual(global_core_metric([])["status"], "UNDEFINED_NO_VALID_PIXELS")

    def test_core_qr_mean_tau_rain_numerator_valid_denominator(self):
        logits = torch.zeros(1, 1, 1, 2, dtype=torch.float64)
        qlog = torch.ones(1, 32, 1, 2, dtype=torch.float64)
        prob = torch.sigmoid(logits)
        out = B0Output(logits, prob, qlog, torch.expm1(qlog), prob*torch.expm1(qlog).mean(1, keepdim=True),
                       (1,48,501,501), (1,48,100,100), torch.ones_like(logits), torch.zeros(1), torch.ones(1))
        target = torch.tensor([[[[math.expm1(2), 0.]]]], dtype=torch.float64)
        valid = torch.ones_like(logits, dtype=torch.bool)
        loss = b0_core_loss(out, target, valid, valid, focal_alpha=.5, focal_gamma=0, quantile_axis_reduction="mean")
        # Only one rainy error=1; mean of frozen midpoint taus=.5; denominator=2.
        self.assertAlmostEqual(float(loss.conditional_quantile), .25)
        self.assertAlmostEqual(float(loss.occurrence), .5*math.log(2))


if __name__ == "__main__":
    unittest.main()
