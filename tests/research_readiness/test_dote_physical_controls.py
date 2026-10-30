"""Only new nonzero-control construction and new exact-count arithmetic."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np
import torch

from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.dote import dote_proxy
from yuntapr.experimental.core_innovation.stage2.fusion import paired_fusion_candidates
from yuntapr.experimental.research_readiness.dynamic_terrain import PhysicalDote,DoteDefinition
from yuntapr.experimental.research_readiness.dote_physical_controls import PerpendicularGradientDote,joint_mask_permutation

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('new_counts',ROOT/'tools/research_readiness/diagnose_dote_reliability_increment.py')
counts=importlib.util.module_from_spec(spec);spec.loader.exec_module(counts)


class PhysicalControlTests(unittest.TestCase):
    def pack(self):
        values=np.ones((6,100,100),np.float64);values[0]=1000;values[1]=5;values[2]=7
        return SimpleNamespace(channels=tuple(range(6)),values=values,valid=np.ones_like(values,bool),grid=GridSpec(np.linspace(20,30,100),np.linspace(97,107,100)),region=np.ones((100,100),bool))
    def test_exact_rotation_norm_geography_and_static_inputs(self):
        p=self.pack();before=p.values.copy();d=DoteDefinition(31.85768219039871,'FROZEN_2023_TRAIN')
        a=PhysicalDote(p,d).terrain;b=PerpendicularGradientDote(p,d).physical.terrain
        np.testing.assert_array_equal(b.east_gradient,-a.north_gradient);np.testing.assert_array_equal(b.north_gradient,a.east_gradient)
        np.testing.assert_array_equal(np.hypot(a.east_gradient,a.north_gradient),np.hypot(b.east_gradient,b.north_gradient))
        np.testing.assert_array_equal(a.elevation_m,b.elevation_m);np.testing.assert_array_equal(a.gradient_valid,b.gradient_valid);np.testing.assert_array_equal(p.values,before)
    def test_projection_direction_changes_with_real_mask_preserved(self):
        p=self.pack();d=DoteDefinition(31.85768219039871,'FROZEN_2023_TRAIN');a=PhysicalDote(p,d).terrain;b=PerpendicularGradientDote(p,d).physical.terrain
        u=np.full((2,100,100),2.);v=np.full_like(u,3.);valid=np.ones_like(u,bool);ps=np.full((100,100),80000.);ps[0,0]=np.nan
        def calculate(t,u):return dote_proxy(t,u,v,valid,np.array([850.,700.]),ps,np.isfinite(ps),wind_grid=p.grid,wind_unit='m/s',pressure_unit='hPa',surface_pressure_unit='Pa')
        real=calculate(a,u);rot=calculate(b,u)
        np.testing.assert_array_equal(real.valid,rot.valid);self.assertFalse(rot.valid[0].any());self.assertTrue(rot.valid[1,1,1])
        self.assertEqual(real.orographic_proxy_m_s[1,1,1],31.);self.assertEqual(rot.orographic_proxy_m_s[1,1,1],1.)
    def test_joint_permutation_preserves_vectors_marginals_masks_and_outside(self):
        rng=np.random.default_rng(37);x=rng.normal(size=(8,100,100)).astype(np.float32);m=np.ones_like(x,bool);m[0,:20]=False;x[~m]=0
        region=np.zeros((100,100),bool);region[10:90,10:90]=True;before=x.copy();y,v,mapping=joint_mask_permutation(x,m,region)
        np.testing.assert_array_equal(v,m);np.testing.assert_array_equal(x,before);np.testing.assert_array_equal(y[:,~region],x[:,~region])
        np.testing.assert_array_equal(y,x.reshape(8,-1)[:,mapping.ravel()].reshape(x.shape))
        for c in range(8):np.testing.assert_array_equal(np.sort(y[c,m[c]&region]),np.sort(x[c,m[c]&region]))
        self.assertTrue(np.all(mapping[region]!=np.arange(10000).reshape(100,100)[region]))
    def test_permutation_is_fixed_and_requires_explicit_masks(self):
        x=np.ones((8,100,100),np.float32);m=np.ones_like(x,bool);r=np.ones((100,100),bool)
        np.testing.assert_array_equal(joint_mask_permutation(x,m,r)[2],joint_mask_permutation(x,m,r)[2])
        with self.assertRaises(ValueError):joint_mask_permutation(x,m.astype(np.uint8),r)
        x[0,0,0]=np.nan
        with self.assertRaises(ValueError):joint_mask_permutation(x,m,r)
    def test_nonzero_columns_can_all_receive_loss_gradients(self):
        torch.manual_seed(2029)
        fusion,_=paired_fusion_candidates(feature_channels=[48],gfs_channels=[26],terrain_channels=[28],projection_width=16,modulation_limit=.1)
        f=torch.randn(1,48,3,3);g=torch.randn(1,26,3,3);t=torch.randn(1,28,3,3)
        with torch.no_grad():fusion.fuse[0].weight.fill_(.001)
        grid=GridSpec([25.,25.1,25.2],[101.,101.1,101.2]);mask=[torch.ones(1,1,3,3,dtype=torch.bool)]
        out=fusion([f],[g],[t],mask,mask,mask,feature_grids=[grid],gfs_grids=[grid],terrain_grids=[grid]).values[0]
        out.square().sum().backward();grad=fusion.terrain[0].weight.grad[:,12:20]
        self.assertEqual(grad.numel(),128);self.assertEqual(torch.count_nonzero(grad).item(),128);self.assertTrue(torch.isfinite(grad).all())
    def test_native_score_identity_and_brier_are_not_only_reliability(self):
        rows=[(.1,1,9),(.4,4,6),(.8,8,2)];r=counts.exact_counts(rows)
        self.assertAlmostEqual(r['brier'],r['empirical_score_reliability']-r['empirical_score_resolution']+r['uncertainty'])
        self.assertAlmostEqual(r['empirical_score_reliability'],0)
        self.assertGreater(r['empirical_score_resolution'],0)
        with self.assertRaises(ValueError):counts.exact_counts([(1.1,1,2)])


if __name__=='__main__':unittest.main()
