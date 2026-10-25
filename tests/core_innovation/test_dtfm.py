import unittest
import numpy as np
import torch

from yuntapr.experimental.core_innovation.dtfm import MaskedTerrainModulation
from yuntapr.experimental.core_innovation.grid import GridSpec


class DTFMTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.grids = [GridSpec(np.array([24., 25., 26.]), np.array([100., 101., 102., 103.])),
                      GridSpec(np.array([24.5, 25.5]), np.array([100.5, 102.5]))]
        self.features = [torch.linspace(-1., 1., 24).reshape(1, 2, 3, 4), torch.ones(1, 3, 2, 2)]
        self.conditions = [torch.ones(1, 4, 3, 4), torch.ones(1, 2, 2, 2)]
        self.masks = [torch.ones(1, 1, 3, 4, dtype=torch.bool), torch.ones(1, 1, 2, 2, dtype=torch.bool)]
        self.module = MaskedTerrainModulation(feature_channels=[2, 3], condition_channels=[4, 2], modulation_limit=.2)

    def call(self, **changes):
        args = dict(features=self.features, conditions=self.conditions, feature_valid=self.masks,
                    condition_valid=self.masks, feature_grids=self.grids, condition_grids=self.grids)
        args.update(changes)
        return self.module(**args)

    def test_identity_initialization_multiscale_shapes_and_dtype(self):
        result = self.call()
        for original, output, valid in zip(self.features, result.values, result.valid):
            self.assertTrue(torch.equal(original, output))
            self.assertEqual(original.shape, output.shape)
            self.assertEqual(output.dtype, torch.float32)
            self.assertEqual(output.device.type, 'cpu')
            self.assertTrue(bool(valid.all()))

    def test_gradients_reach_features_conditions_and_parameters(self):
        self.features = [x.requires_grad_() for x in self.features]
        self.conditions = [x.requires_grad_() for x in self.conditions]
        with torch.no_grad():
            for layer in self.module.projections:
                layer.weight.fill_(.04)
        result = self.call()
        sum(value.sum() for value in result.values).backward()
        for tensor in self.features + self.conditions:
            self.assertIsNotNone(tensor.grad)
            self.assertTrue(bool(torch.isfinite(tensor.grad).all()))
            self.assertGreater(float(tensor.grad.abs().sum()), 0.)
        for parameter in self.module.parameters():
            self.assertTrue(bool(torch.isfinite(parameter.grad).all()))
            self.assertGreater(float(parameter.grad.abs().sum()), 0.)

    def test_all_invalid_features_neutral_mask_and_zero_gradients(self):
        self.features = [torch.full_like(x, float('nan'), requires_grad=True) for x in self.features]
        self.conditions = [torch.full_like(x, float('nan'), requires_grad=True) for x in self.conditions]
        masks = [torch.zeros_like(x) for x in self.masks]
        result = self.call(feature_valid=masks, condition_valid=masks)
        sum(output.sum() for output in result.values).backward()
        for output, mask, used in zip(result.values, result.valid, result.condition_used):
            self.assertTrue(bool((output == 0).all()))
            self.assertFalse(bool(mask.any()))
            self.assertFalse(bool(used.any()))
        for tensor in self.features + self.conditions:
            self.assertTrue(bool((tensor.grad == 0).all()))

    def test_missing_condition_leaves_valid_backbone_identity(self):
        with torch.no_grad():
            for layer in self.module.projections:
                layer.weight.fill_(.3)
                layer.bias.fill_(.2)
        self.conditions = [torch.full_like(x, float('nan')) for x in self.conditions]
        result = self.call(condition_valid=[torch.zeros_like(mask) for mask in self.masks])
        for original, output, used in zip(self.features, result.values, result.condition_used):
            self.assertTrue(torch.equal(original, output))
            self.assertFalse(bool(used.any()))

    def test_partial_mask_and_nonfinite_marked_valid(self):
        fmask = [mask.clone() for mask in self.masks]
        fmask[0][0, 0, 0, 0] = False
        self.features[0][0, :, 0, 0] = float('nan')
        result = self.call(feature_valid=fmask)
        self.assertTrue(bool((result.values[0][0, :, 0, 0] == 0).all()))
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            self.call()

    def test_grid_shape_mask_and_dtype_mismatches_fail(self):
        wrong = [GridSpec(self.grids[0].lat[::-1], self.grids[0].lon), self.grids[1]]
        with self.assertRaisesRegex(ValueError, 'grid identity'):
            self.call(condition_grids=wrong)
        with self.assertRaisesRegex(ValueError, 'configured channels'):
            self.call(conditions=[self.conditions[0][:, :3], self.conditions[1]])
        with self.assertRaisesRegex(ValueError, 'bool'):
            self.call(condition_valid=[x.float() for x in self.masks])
        with self.assertRaisesRegex(ValueError, 'dtype'):
            self.call(features=[x.double() for x in self.features])
        with self.assertRaisesRegex(ValueError, 'device'):
            self.call(conditions=[torch.empty(self.conditions[0].shape, device='meta'), self.conditions[1]])

    def test_explicit_double_precision_module(self):
        self.module.double()
        result = self.call(features=[x.double() for x in self.features], conditions=[x.double() for x in self.conditions])
        self.assertTrue(all(value.dtype == torch.float64 for value in result.values))

    def test_no_hidden_scale_or_modulation_default(self):
        for limit in (0., 1.1, float('nan')):
            with self.assertRaises(ValueError):
                MaskedTerrainModulation(feature_channels=[2], condition_channels=[1], modulation_limit=limit)
        with self.assertRaises(ValueError):
            MaskedTerrainModulation(feature_channels=[2], condition_channels=[1, 2], modulation_limit=.2)
        with self.assertRaisesRegex(ValueError, 'every configured scale'):
            self.call(features=self.features[:1])


if __name__ == '__main__':
    unittest.main()
