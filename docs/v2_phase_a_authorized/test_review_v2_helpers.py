"""CPU-only synthetic tests; no source/model/checkpoint access or optimizer steps."""
from pathlib import Path
import json
import math
import tempfile
from types import SimpleNamespace
import unittest
import torch
import review_v2_helpers as review


def fixture(batch=1, probability=.2, rainy=False):
    mask = torch.zeros((1, 1, 100, 100), dtype=torch.bool)
    mask.reshape(-1)[:3430] = True
    valid = torch.ones((batch, 1, 100, 100), dtype=torch.bool)
    target = torch.full((batch, 1, 100, 100), float(rainy), dtype=torch.float32)
    quantiles = (.2 + .03 * torch.arange(32, dtype=torch.float64))[None, :, None, None].expand(batch, 32, 100, 100).clone()
    class Output(SimpleNamespace):
        @property
        def conditional_quantiles_physical(self):
            raise AssertionError('Physical materialization must not be requested')
    output = Output(rain_prob=torch.full_like(target, probability),
                    rain_logit=torch.full_like(target, math.log(probability / (1 - probability))),
                    conditional_quantiles_log=quantiles)
    return output, target, valid, mask


class ReadOnlyReviewTests(unittest.TestCase):
    def test_analytic_brier_and_exact_tie_conventions(self):
        acc = review.ReadOnlyMetrics()
        output, target, valid, mask = fixture(batch=2, probability=.5)
        target[0] = 1
        acc.add(output, target, valid, mask)
        result = acc.report()
        self.assertEqual(result['N_valid'], 6860)
        self.assertEqual(result['N_rain'], 3430)
        self.assertEqual(result['Brier_Score'], .25)
        self.assertEqual(result['AUROC'], .5)
        self.assertEqual(result['Average_Precision'], .5)

    def test_float32_event_boundary_before_double_promotion(self):
        acc = review.ReadOnlyMetrics()
        output, target, valid, mask = fixture()
        target.fill_(.1)
        self.assertTrue(bool((target.double() > .1).all()))
        acc.add(output, target, valid, mask)
        result = acc.report()
        self.assertEqual(result['N_rain'], 0)
        self.assertIsNone(result['conditional_mean_pinball'])
        self.assertIsNone(result['Average_Precision'])
        self.assertIsNone(result['AUROC'])

    def test_conditional_pinball_units_and_analytic_mean(self):
        acc = review.ReadOnlyMetrics()
        args = fixture(rainy=True)
        acc.add(*args)
        result = acc.report()
        z = math.log1p(1)
        expected = sum(max(((i + .5) / 32) * (z - (.2 + .03 * i)),
                           (((i + .5) / 32) - 1) * (z - (.2 + .03 * i))) for i in range(32)) / 32
        self.assertAlmostEqual(result['conditional_mean_pinball'], expected, places=14)
        self.assertEqual(result['conditional_pinball_units'], 'log1p(mm/h)')
        self.assertFalse(result['physical_materialization'])

    def test_outside_extreme_does_not_enter_metrics_or_physical_transform(self):
        original, target, valid, mask = fixture(rainy=True)
        first = review.ReadOnlyMetrics(); first.add(original, target, valid, mask)
        original.conditional_quantiles_log[:, -1, -1, -1] = 1000
        second = review.ReadOnlyMetrics(); second.add(original, target, valid, mask)
        self.assertEqual(first.report(), second.report())

    def test_frozen_strict_guards_reject_nonfinite_and_crossing(self):
        for value in (float('nan'), .1):
            output, target, valid, mask = fixture()
            output.conditional_quantiles_log[:, 10, 0, 0] = value
            with self.assertRaises((FloatingPointError, ValueError)):
                review.ReadOnlyMetrics().add(output, target, valid, mask)

    def test_readonly_context_blocks_backward(self):
        tensor = torch.tensor(1., requires_grad=True)
        with review.inference_only():
            with self.assertRaises(PermissionError): tensor.backward()
            with self.assertRaises(PermissionError): torch.autograd.backward(tensor)

    def test_partial_pair_rejected_without_touching_sources(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix='review_fixture_', dir=root) as name:
            fixture_root = Path(name).resolve()
            self.assertTrue(fixture_root.is_relative_to(root.resolve()))
            with self.assertRaises(PermissionError): review.require_completed_pair(fixture_root)
            for kind in ('B0_MATCHED_V2', 'B1_V2'):
                dest = fixture_root / kind; dest.mkdir()
                (dest / 'final_report.json').write_text(json.dumps({'status': 'COMPLETE', 'model': kind,
                    'completed_epoch': 14, 'final_early_stop_counter': 5, 'patience': 8,
                    'min_delta': 1e-4, 'termination_reason': 'MAX_EPOCH_50'}))
            with self.assertRaises(ValueError): review.require_completed_pair(fixture_root)
            self.assertTrue(fixture_root.is_relative_to(root.resolve()))


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main(verbosity=2)
