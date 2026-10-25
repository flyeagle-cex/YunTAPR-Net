import unittest
import torch
from yuntapr.experimental.core_innovation.stage2.fusion import paired_fusion_candidates
from yuntapr.experimental.core_innovation.grid import GridSpec


class PrecisionTests(unittest.TestCase):
    def test_b7_b8_autocast_backbone_features_and_float_conditions(self):
        grid = GridSpec([26., 25., 24.], [101., 102., 103.])
        a, b = paired_fusion_candidates(feature_channels=[4], gfs_channels=[11], terrain_channels=[8],
            projection_width=3, modulation_limit=.5)
        for model in (a, b):
            f = torch.randn(1, 4, 3, 3, dtype=torch.bfloat16, requires_grad=True)
            g = torch.randn(1, 11, 3, 3, requires_grad=True); t = torch.randn(1, 8, 3, 3, requires_grad=True)
            mask = torch.ones(1, 1, 3, 3, dtype=torch.bool)
            with torch.autocast('cpu', dtype=torch.bfloat16):
                out = model([f], [g], [t], [mask], [mask], [mask],
                    feature_grids=[grid], gfs_grids=[grid], terrain_grids=[grid])
                self.assertEqual(out.values[0].dtype, f.dtype); self.assertTrue(torch.equal(out.values[0], f))
                out.values[0].float().sum().backward()
            self.assertTrue(torch.isfinite(f.grad).all())


if __name__ == '__main__': unittest.main()
