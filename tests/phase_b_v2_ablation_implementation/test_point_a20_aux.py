"""Synthetic checks for the fixed A-point intervention."""

import math
import unittest

import torch

from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.point_a20_aux import point_a20_aux_loss
from yuntapr.experimental.phase_b_v2_ablations.total import candidate_loss
from yuntapr.models.quantile_v2.outputs import LogDomainOutput


def inputs(rates, points, *, valid=None, region=None, overflowing_indices=()):
    rate = torch.tensor(rates, dtype=torch.float32).reshape(1, 1, 1, -1)
    logit = torch.zeros_like(rate, requires_grad=True)
    mean = 2.0 * torch.tensor(points, dtype=torch.float64)
    offsets = torch.linspace(-0.3, 0.3, steps=32, dtype=torch.float64)
    qlog = torch.log1p(mean[None, :] + offsets[:, None])
    for index in overflowing_indices:
        qlog[:, index] = torch.linspace(710.0, 711.0, steps=32, dtype=torch.float64)
    qlog = qlog.reshape(1, 32, 1, -1).requires_grad_()
    output = LogDomainOutput(rain_logit=logit, rain_prob=torch.sigmoid(logit), conditional_quantiles_log=qlog)
    valid_mask = torch.ones_like(rate, dtype=torch.bool) if valid is None else torch.tensor(valid).reshape(rate.shape)
    region_mask = torch.ones_like(rate, dtype=torch.bool) if region is None else torch.tensor(region).reshape(rate.shape)
    return output, rate, valid_mask, region_mask


class PointA20AuxTests(unittest.TestCase):
    def setUp(self):
        self.config = get_config("E0")

    def base_loss(self, output, rate, valid, region):
        return candidate_loss(output.rain_logit, output.conditional_quantiles_log,
                              rate, valid, region, config=self.config)

    def test_exact_per_class_means_and_two_sided_directions(self):
        tensors = inputs([25.0, 10.0, 0.0], [8.0, 12.0, 22.0])
        output = tensors[0]
        result = point_a20_aux_loss(*tensors, config=self.config)
        self.assertEqual(result.experiment_id, "A20-BISIDE-V1")
        expected_positive = math.log1p(math.exp((20.0 - 8.0) / 20.0))
        expected_negative = (math.log1p(math.exp((12.0 - 20.0) / 20.0))
                             + math.log1p(math.exp((22.0 - 20.0) / 20.0)))
        self.assertEqual((result.n_strong, result.n_non_strong), (1, 2))
        self.assertAlmostEqual(result.s_positive.item(), expected_positive, places=14)
        self.assertAlmostEqual(result.s_negative.item(), expected_negative, places=14)
        self.assertAlmostEqual(result.weighted_point_auxiliary.item(),
                               0.1 * (expected_positive + expected_negative / 2), places=14)
        grad, = torch.autograd.grad(result.weighted_point_auxiliary, (output.conditional_quantiles_log,))
        self.assertTrue(bool((grad[..., 0] < 0).all()))
        self.assertTrue(bool((grad[..., 1:] > 0).all()))

    def test_no_direct_gradient_into_occurrence_and_original_terms_preserved(self):
        tensors = inputs([25.0, 10.0], [10.0, 16.0])
        output = tensors[0]
        base = self.base_loss(*tensors)
        result = point_a20_aux_loss(*tensors, config=self.config)
        gradient, = torch.autograd.grad(result.weighted_point_auxiliary, (output.rain_logit,),
                                        allow_unused=True, retain_graph=True)
        self.assertIsNone(gradient)
        self.assertTrue(torch.equal(base.s_occ, result.s_occ))
        self.assertTrue(torch.equal(base.s_qr, result.s_qr))
        self.assertTrue(torch.equal(base.weighted_quantile_per_valid, result.weighted_quantile_per_valid))
        base_gradient, = torch.autograd.grad(base.training_objective, (output.rain_logit,), retain_graph=True)
        new_gradient, = torch.autograd.grad(result.training_objective, (output.rain_logit,))
        self.assertTrue(torch.equal(new_gradient, base_gradient))

    def test_uses_emitted_bf16_probability_in_fp64_readout(self):
        output, *labels = inputs([25.0], [14.0])
        logit = torch.full_like(output.rain_logit, 0.7, dtype=torch.bfloat16, requires_grad=True)
        output = LogDomainOutput(logit, torch.sigmoid(logit), output.conditional_quantiles_log)
        result = point_a20_aux_loss(output, *labels, config=self.config)
        point = output.rain_prob.item() * 28.0
        self.assertEqual(result.weighted_point_auxiliary.dtype, torch.float64)
        self.assertAlmostEqual(result.weighted_point_auxiliary.item(),
                               0.1 * math.log1p(math.exp((20.0 - point) / 20.0)), places=14)

    def test_fp32_truth_boundary_and_intersection_mask(self):
        boundary = torch.tensor(20.0, dtype=torch.float32)
        above = torch.nextafter(boundary, torch.tensor(math.inf)).item()
        below = torch.nextafter(boundary, torch.tensor(-math.inf)).item()
        tensors = inputs([20.0, above, above, above, below], [12.0] * 5,
                         valid=[True, True, False, True, True], region=[True, True, True, False, True],
                         overflowing_indices=(2, 3))
        result = point_a20_aux_loss(*tensors, config=self.config)
        self.assertEqual((result.n_valid, result.n_strong, result.n_non_strong), (3, 1, 2))
        gradient, = torch.autograd.grad(result.weighted_point_auxiliary, (tensors[0].conditional_quantiles_log,))
        self.assertTrue(bool((gradient[..., 1] < 0).all()))
        self.assertTrue(bool((gradient[..., 0] > 0).all()))
        self.assertTrue(bool((gradient[..., 4] > 0).all()))
        self.assertEqual(torch.count_nonzero(gradient[..., 2:4]).item(), 0)

    def test_no_positives_is_exact_e0(self):
        tensors = inputs([0.0, 20.0], [12.0, 12.0], overflowing_indices=(1,))
        base = self.base_loss(*tensors)
        result = point_a20_aux_loss(*tensors, config=self.config)
        self.assertEqual((result.n_strong, result.n_non_strong), (0, 2))
        self.assertEqual(result.weighted_point_auxiliary.item(), 0.0)
        self.assertTrue(torch.equal(base.training_objective, result.training_objective))

    def test_positives_only_uses_positive_mean_without_division_by_zero(self):
        tensors = inputs([21.0, 28.0], [18.0, 25.0])
        result = point_a20_aux_loss(*tensors, config=self.config)
        self.assertEqual((result.n_strong, result.n_non_strong), (2, 0))
        self.assertEqual(result.s_negative.item(), 0.0)
        self.assertAlmostEqual(result.weighted_point_auxiliary.item(), 0.1 * result.s_positive.item() / 2)
        self.assertTrue(bool(torch.isfinite(result.training_objective)))

    def test_valid_physical_overflow_and_non_e0_are_rejected(self):
        tensors = inputs([25.0, 10.0], [12.0, 12.0], overflowing_indices=(1,))
        with self.assertRaisesRegex(FloatingPointError, 'valid physical quantiles'):
            point_a20_aux_loss(*tensors, config=self.config)
        with self.assertRaises(PermissionError):
            point_a20_aux_loss(*tensors, config=get_config("E2"))

    def test_invalid_emitted_probability_is_rejected(self):
        for value in (math.nan, 1.01):
            output, *labels = inputs([25.0], [12.0])
            output.rain_prob = torch.full_like(output.rain_prob, value)
            with self.subTest(probability=value):
                with self.assertRaises((ValueError, FloatingPointError)):
                    point_a20_aux_loss(output, *labels, config=self.config)


if __name__ == "__main__":
    unittest.main()
