"""Small artificial CPU forwards through actual encoder/decoder modules only.

No data, checkpoint, cache, optimizer, backward call or gradient experiment.
"""
import unittest
from dataclasses import replace

import numpy as np
import torch

from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.models.backbone_b0 import B0Backbone
from yuntapr.models.blocks import ResidualBlock
from yuntapr.experimental.research_readiness.multiscale_candidate import ExplicitScaleSpec
from yuntapr.experimental.research_readiness.native_multiscale_adapter import (
    INJECTION_SITE, TAP_NAMES, encoder_tap_grids,
    paired_native_multiscale_adapters,
)


class NativeMultiscaleAdapterTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(711)
        self.config = dict(
            groupnorm_groups=8, downsample_kernel=3, downsample_padding=1,
            decoder_interpolation_mode='nearest', align_corners=None,
            input_projection_skip_initialization='zeros',
        )
        # Reuse the actual backbone and the exact existing 42-channel stem
        # architecture/initialization from NativeBackboneCandidate.__init__.
        # Importing that constructor also imports the unrelated YAML contract
        # loader; these array-only checks need neither YAML nor file access.
        self.backbone = B0Backbone(self.config, (48, 96, 192, 256))
        self.backbone.enc0 = ResidualBlock(42, 48, self.config['groupnorm_groups'])
        torch.nn.init.zeros_(self.backbone.enc0.skip.weight)
        torch.nn.init.zeros_(self.backbone.enc0.skip.bias)
        self.backbone.cpu().eval()
        self.grid = GridSpec(np.linspace(26., 24., 9), np.linspace(101., 103., 9))
        self.grids = encoder_tap_grids(self.backbone, self.grid)
        self.taps = ('enc0', 'enc2')
        self.scales = tuple(
            ExplicitScaleSpec(name, getattr(self.backbone, name).conv2.out_channels,
                              3, 4, self.grids[TAP_NAMES.index(name)],
                              'SYNTHETIC_COORDINATES_ACTUAL_ENCODER_TAP')
            for name in self.taps
        )

    def pair(self, **changes):
        options = dict(
            native_grid=self.grid, scales=self.scales, tap_names=self.taps,
            injection_site=INJECTION_SITE, projection_width=2, modulation_limit=.1,
        )
        options.update(changes)
        return paired_native_multiscale_adapters(self.backbone, **options)

    def inputs(self):
        return dict(
            x=torch.randn(1, 42, 9, 9),
            native_valid=torch.ones(1, 1, 9, 9, dtype=torch.bool),
            gfs=[torch.randn(1, 3, *s.grid.shape) for s in self.scales],
            terrain=[torch.randn(1, 4, *s.grid.shape) for s in self.scales],
            gfs_valid=[torch.ones(1, 1, *s.grid.shape, dtype=torch.bool) for s in self.scales],
            terrain_valid=[torch.ones(1, 1, *s.grid.shape, dtype=torch.bool) for s in self.scales],
            gfs_grids=[s.grid for s in self.scales],
            terrain_grids=[s.grid for s in self.scales],
        )

    @staticmethod
    def original_module_path(backbone, x):
        # The unchanged forward equation from NativeBackboneCandidate, using
        # its actual modules while avoiding its production-only 501 assertion.
        s0 = backbone.enc0(x)
        s1 = backbone.enc1(backbone.down1(s0))
        s2 = backbone.enc2(backbone.down2(s1))
        s3 = backbone.enc3(backbone.down3(s2))
        return backbone.dec0(backbone._up(backbone.dec1(backbone._up(
            backbone.dec2(backbone._up(s3, s2)), s1)), s0))

    def test_tap_geometry_uses_actual_convolution_centers(self):
        self.assertEqual([g.shape for g in self.grids], [(9, 9), (5, 5), (3, 3), (2, 2)])
        for grid, stride in zip(self.grids, (1, 2, 4, 8)):
            np.testing.assert_array_equal(grid.lat, self.grid.lat[::stride])
            np.testing.assert_array_equal(grid.lon, self.grid.lon[::stride])

    def test_existing_encoder_tensors_reach_fusion_and_actual_decoder(self):
        adapter = self.pair()[0]
        data = self.inputs()
        encoder_seen, fusion_seen, decoder_seen = {}, [], []
        handles = []
        for name in TAP_NAMES:
            handles.append(getattr(adapter.backbone, name).register_forward_hook(
                lambda module, args, value, name=name: encoder_seen.__setitem__(name, value)
            ))
        handles.append(adapter.fusion.register_forward_pre_hook(
            lambda module, args: fusion_seen.extend(args[0])
        ))
        handles.append(adapter.backbone.dec0.register_forward_hook(
            lambda module, args, value: decoder_seen.append(value)
        ))
        try:
            with torch.no_grad():
                result = adapter(**data)
        finally:
            for handle in handles:
                handle.remove()
        for name, value in zip(self.taps, fusion_seen):
            self.assertIs(value, encoder_seen[name])
        self.assertIs(result.decoded_native, decoder_seen[0])
        self.assertEqual(result.encoder_feature_shapes,
                         ((1, 48, 9, 9), (1, 96, 5, 5), (1, 192, 3, 3), (1, 256, 2, 2)))
        self.assertEqual(result.fused_taps, self.taps)
        self.assertEqual(result.decoded_native.shape, (1, 48, 9, 9))
        self.assertEqual(result.decoded_native.device.type, 'cpu')
        self.assertFalse(result.decoded_native.requires_grad)

    def test_zero_initialized_pair_preserves_original_decoder_path_and_common_weights(self):
        a, b = self.pair()
        for name, value in a.backbone.state_dict().items():
            self.assertTrue(torch.equal(value, b.backbone.state_dict()[name]), name)
            self.assertTrue(torch.equal(value, self.backbone.state_dict()[name]), name)
        for pa, pb in zip(a.backbone.parameters(), b.backbone.parameters()):
            self.assertNotEqual(pa.data_ptr(), pb.data_ptr())
        self.assertEqual(sum(p.numel() for p in a.parameters()), sum(p.numel() for p in b.parameters()))
        data = self.inputs()
        with torch.no_grad():
            original = self.original_module_path(self.backbone, data['x'])
            for adapter in (a, b):
                result = adapter(**data)
                self.assertTrue(torch.equal(result.decoded_native, original))
                self.assertTrue(adapter.native_encoder_connected)
                self.assertTrue(adapter.decoder_connected)
                self.assertFalse(adapter.formal_integration)
                self.assertFalse(adapter.real_grid_mapping_verified)
                self.assertFalse(adapter.probability_heads_connected)

    def test_selected_fusion_residual_reaches_decoder_without_optimizer_or_backward(self):
        adapter = self.pair()[0]
        data = self.inputs()
        with torch.no_grad():
            initial = adapter(**data).decoded_native.clone()
            adapter.fusion.fusion.fuse[0].bias[0] = .5
            changed = adapter(**data).decoded_native
        self.assertTrue(torch.isfinite(changed).all())
        self.assertFalse(torch.equal(initial, changed))
        self.assertTrue(all(p.grad is None for p in adapter.parameters()))

    def test_condition_grid_mismatch_is_rejected_without_implicit_resize(self):
        data = self.inputs()
        data['gfs_grids'][0] = GridSpec(self.grid.lat, self.grid.lon+.001)
        with torch.no_grad(), self.assertRaisesRegex(ValueError, 'grid identity'):
            self.pair()[0](**data)

    def test_wrong_tap_grid_or_channels_are_rejected(self):
        shifted = GridSpec(self.scales[0].grid.lat, self.scales[0].grid.lon+.001)
        bad = (replace(self.scales[0], grid=shifted), self.scales[1])
        with self.assertRaisesRegex(ValueError, 'grid identity'):
            self.pair(scales=bad)
        bad = (replace(self.scales[0], feature_channels=49), self.scales[1])
        with self.assertRaisesRegex(ValueError, 'actual encoder module'):
            self.pair(scales=bad)

    def test_injection_and_taps_are_explicit_and_unambiguous(self):
        for site in (None, 'PROGRESSIVE_ENCODER', 'SP04_POOLING'):
            with self.assertRaisesRegex(ValueError, 'injection site'):
                self.pair(injection_site=site)
        for taps in (('enc0',), ('enc2', 'enc0'), ('enc0', 'enc0'), {'enc0', 'enc2'}, 'enc0,enc2'):
            with self.assertRaises(ValueError):
                self.pair(tap_names=taps)
        with self.assertRaisesRegex(ValueError, 'scale names'):
            self.pair(tap_names=('enc0', 'enc1'))

    def test_unknown_backbone_geometry_is_rejected(self):
        self.backbone.down1.padding = (0, 0)
        with self.assertRaisesRegex(ValueError, 'unchanged kernel3'):
            self.pair()

    def test_invalid_native_context_and_conditions_are_rejected(self):
        adapter = self.pair()[0]
        for failure in ('partial_native', 'float_native_mask', 'wrong_stem', 'nonfinite', 'bad_condition_mask'):
            data = self.inputs()
            if failure == 'partial_native':
                data['native_valid'][0, 0, 0, 0] = False
            elif failure == 'float_native_mask':
                data['native_valid'] = data['native_valid'].float()
            elif failure == 'wrong_stem':
                data['x'] = data['x'][:, :7]
            elif failure == 'nonfinite':
                data['x'][0, 0, 0, 0] = float('nan')
            else:
                data['gfs_valid'][0] = data['gfs_valid'][0].float()
            with self.subTest(failure=failure), torch.no_grad(), self.assertRaises(ValueError):
                adapter(**data)


if __name__ == '__main__':
    unittest.main()
