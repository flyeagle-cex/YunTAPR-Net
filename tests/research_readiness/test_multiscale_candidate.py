"""Artificial small CPU tensors only: no optimizer, scientific data or models."""
import unittest
from dataclasses import replace

import numpy as np
import torch

from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.research_readiness.multiscale_candidate import (
    ExplicitScaleSpec,
    paired_multiscale_candidates,
)


class ExplicitMultiscaleTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(812)
        self.grids = (
            GridSpec(np.linspace(26., 24., 9), np.linspace(101., 103., 9)),
            GridSpec(np.linspace(26., 24., 5), np.linspace(101., 103., 5)),
        )
        self.scales = tuple(
            ExplicitScaleSpec(f'artificial_{i}', channels, 3, 4, grid,
                              'SYNTHETIC_ONLY_NOT_NATIVE_ENCODER')
            for i, (channels, grid) in enumerate(zip((2, 4), self.grids))
        )

    def pair(self, scales=None):
        return paired_multiscale_candidates(
            self.scales if scales is None else scales,
            projection_width=3, modulation_limit=.1,
        )

    def inputs(self):
        return dict(
            features=[torch.randn(1, s.feature_channels, *s.grid.shape,
                                  requires_grad=True) for s in self.scales],
            gfs=[torch.randn(1, 3, *g.shape, requires_grad=True) for g in self.grids],
            terrain=[torch.randn(1, 4, *g.shape, requires_grad=True) for g in self.grids],
            feature_valid=[torch.ones(1, 1, *g.shape, dtype=torch.bool) for g in self.grids],
            gfs_valid=[torch.ones(1, 1, *g.shape, dtype=torch.bool) for g in self.grids],
            terrain_valid=[torch.ones(1, 1, *g.shape, dtype=torch.bool) for g in self.grids],
            scale_names=tuple(s.name for s in self.scales),
            feature_grids=self.grids, gfs_grids=self.grids, terrain_grids=self.grids,
        )

    def release_synthetic_zero_gates(self, candidate):
        # Deliberate algebraic probe, not an optimizer step or model training.
        with torch.no_grad():
            for layer in candidate.fusion.fuse:
                layer.weight.fill_(.01)
            if candidate.fusion.modulation:
                for layer in candidate.fusion.modulation.projections:
                    layer.weight.fill_(.01)

    def test_parameter_counts_shared_copies_and_scope_flags(self):
        a, b = self.pair()
        self.assertEqual(sum(p.numel() for p in a.parameters()), 544)
        self.assertEqual(sum(p.numel() for p in a.parameters()),
                         sum(p.numel() for p in b.parameters()))
        for part in ('gfs', 'terrain', 'fuse'):
            x, y = getattr(a.fusion, part), getattr(b.fusion, part)
            for name, value in x.state_dict().items():
                self.assertTrue(torch.equal(value, y.state_dict()[name]), name)
            for p, q in zip(x.parameters(), y.parameters()):
                self.assertNotEqual(p.data_ptr(), q.data_ptr())
        for candidate in (a, b):
            self.assertFalse(candidate.formal_integration)
            self.assertFalse(candidate.native_encoder_connected)
            self.assertFalse(candidate.decoder_connected)
            self.assertFalse(candidate.real_grid_mapping_verified)
            self.assertEqual(candidate.scientific_effectiveness, 'NOT_VERIFIED')

    def test_initial_output_identity_at_both_scales(self):
        data = self.inputs()
        for candidate in self.pair():
            result = candidate(**data)
            for output, original in zip(result.values, data['features']):
                self.assertTrue(torch.equal(output, original))
                self.assertEqual(output.device.type, 'cpu')

    def test_initial_zero_gates_block_upstream_gradients(self):
        for candidate in self.pair():
            data = self.inputs()
            sum(x.square().sum() for x in candidate(**data).values).backward()
            fuse_gradient = 0.
            for name, parameter in candidate.named_parameters():
                self.assertIsNotNone(parameter.grad, name)
                self.assertTrue(torch.isfinite(parameter.grad).all(), name)
                if name.startswith('fusion.fuse.'):
                    fuse_gradient += parameter.grad.abs().sum().item()
                else:
                    self.assertEqual(parameter.grad.count_nonzero().item(), 0, name)
            self.assertGreater(fuse_gradient, 0.)
            for tensor in data['gfs'] + data['terrain']:
                self.assertEqual(tensor.grad.count_nonzero().item(), 0)
            for tensor in data['features']:
                self.assertGreater(tensor.grad.count_nonzero().item(), 0)

    def test_gradients_are_reachable_after_artificial_gate_release(self):
        for candidate in self.pair():
            data = self.inputs()
            self.release_synthetic_zero_gates(candidate)
            sum(x.square().sum() for x in candidate(**data).values).backward()
            for name, parameter in candidate.named_parameters():
                self.assertIsNotNone(parameter.grad, name)
                self.assertTrue(torch.isfinite(parameter.grad).all(), name)
                self.assertGreater(parameter.grad.count_nonzero().item(), 0, name)
            for tensor in data['features'] + data['gfs'] + data['terrain']:
                self.assertTrue(torch.isfinite(tensor.grad).all())
                self.assertGreater(tensor.grad.count_nonzero().item(), 0)

    def test_absent_conditions_preserve_features_without_nan_leakage(self):
        for candidate in self.pair():
            data = self.inputs()
            self.release_synthetic_zero_gates(candidate)
            data['gfs'] = [torch.full_like(x, float('nan')) for x in data['gfs']]
            data['gfs_valid'] = [torch.zeros_like(x) for x in data['gfs_valid']]
            result = candidate(**data)
            for output, original, used in zip(result.values, data['features'], result.condition_used):
                self.assertTrue(torch.equal(output, original))
                self.assertFalse(used.any())

    def test_invalid_feature_is_zero_with_separate_mask(self):
        data = self.inputs()
        data['features'][0] = data['features'][0].detach().clone()
        data['features'][0][:, :, 1, 1] = float('nan')
        data['feature_valid'][0][:, :, 1, 1] = False
        result = self.pair()[0](**data)
        self.assertTrue((result.values[0][:, :, 1, 1] == 0).all())
        self.assertFalse(result.valid[0][:, :, 1, 1].any())
        self.assertTrue(torch.isfinite(result.values[0]).all())

    def test_single_duplicate_or_same_size_scales_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'At least two'):
            self.pair(self.scales[:1])
        repeated = replace(self.scales[1], grid=self.grids[0])
        with self.assertRaisesRegex(ValueError, 'Repeated physical grids'):
            self.pair((self.scales[0], repeated))
        duplicate = replace(self.scales[1], name=self.scales[0].name)
        with self.assertRaisesRegex(ValueError, 'Scale names'):
            self.pair((self.scales[0], duplicate))
        shifted = GridSpec(self.grids[0].lat, self.grids[0].lon+.01)
        with self.assertRaisesRegex(ValueError, 'distinct spatial tensor sizes'):
            self.pair((self.scales[0], replace(self.scales[1], grid=shifted)))

    def test_scale_container_must_be_an_ordered_sequence(self):
        invalid = (
            set(self.scales),
            {s.name: s for s in self.scales},
            'artificial_0,artificial_1',
            b'artificial_0,artificial_1',
            bytearray(b'artificial_0,artificial_1'),
            (s for s in self.scales),
        )
        for container in invalid:
            with self.subTest(kind=type(container).__name__):
                with self.assertRaisesRegex(ValueError, 'ordered Sequence'):
                    self.pair(container)
        # Both explicitly ordered built-in containers remain supported.
        self.pair(list(self.scales))
        self.pair(tuple(self.scales))

    def test_feature_contract_requires_nonempty_4d_tensors(self):
        candidate = self.pair()[0]
        invalid = (
            None,
            np.zeros((1, 2, 9, 9), dtype=np.float32),
            torch.zeros(2, 9, 9),
            torch.zeros(0, 2, 9, 9),
            torch.zeros(1, 0, 9, 9),
        )
        for feature in invalid:
            with self.subTest(kind=type(feature).__name__, shape=getattr(feature, 'shape', None)):
                data = self.inputs()
                data['features'][0] = feature
                with self.assertRaisesRegex(ValueError, 'nonempty 4D Tensor'):
                    candidate(**data)

    def test_batch_size_must_agree_across_scales_even_if_each_scale_is_aligned(self):
        data = self.inputs()
        # Each second-scale feature, condition and mask agrees at B=2, while
        # the first scale remains at B=1.  Per-scale checks alone miss this.
        for key in ('features', 'gfs', 'terrain', 'feature_valid', 'gfs_valid', 'terrain_valid'):
            data[key][1] = data[key][1].repeat(2, 1, 1, 1)
        with self.assertRaisesRegex(ValueError, 'batch size must agree across'):
            self.pair()[0](**data)

    def test_unknown_mapping_and_wrong_order_are_rejected_without_resize(self):
        candidate = self.pair()[0]
        data = self.inputs()
        data['gfs_grids'] = (GridSpec(self.grids[0].lat, self.grids[0].lon+.01), self.grids[1])
        with self.assertRaisesRegex(ValueError, 'grid identity'):
            candidate(**data)
        data = self.inputs()
        data['scale_names'] = data['scale_names'][::-1]
        with self.assertRaisesRegex(ValueError, 'Scale order'):
            candidate(**data)

    def test_mask_dtype_shape_and_nonfinite_valid_values_are_rejected(self):
        candidate = self.pair()[0]
        data = self.inputs()
        data['gfs_valid'][0] = data['gfs_valid'][0].float()
        with self.assertRaises(ValueError):
            candidate(**data)
        data = self.inputs()
        data['terrain_valid'][0] = data['terrain_valid'][0][:, :, :-1]
        with self.assertRaises(ValueError):
            candidate(**data)
        data = self.inputs()
        data['gfs'][0] = torch.full_like(data['gfs'][0], float('nan'))
        with self.assertRaises(ValueError):
            candidate(**data)

    def test_missing_scale_is_rejected(self):
        data = self.inputs()
        data['terrain'] = data['terrain'][:1]
        with self.assertRaisesRegex(ValueError, 'every explicit scale'):
            self.pair()[0](**data)


if __name__ == '__main__':
    unittest.main()
