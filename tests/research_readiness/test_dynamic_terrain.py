"""Only new B7/B8 connections and the affected shared entrances."""
import copy
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import torch
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.experimental.core_innovation.grid import GridSpec,frozen_sp04_grid
from yuntapr.experimental.core_innovation.gfs import ForecastIdentity,EnvironmentFrame,Field
from yuntapr.experimental.core_innovation.stage4.data import Batch
from yuntapr.experimental.core_innovation.stage4.launch import ReaderFactory
from yuntapr.experimental.research_readiness.static_terrain import StaticPack,B6_CHANNELS,UNITS,fit_static_train_scalers
from yuntapr.experimental.research_readiness.dynamic_terrain import PhysicalDote,DoteDefinition,model_factory


def pack():
    grid=frozen_sp04_grid(REPO_ROOT);v=np.zeros((6,100,100),np.float32)
    v[0]=1000;v[1]=.1;v[2]=.2;v[3]=10;v[5]=1
    m=np.ones_like(v,bool);region=np.ones((100,100),bool)
    return StaticPack(grid,v,m,region,B6_CHANNELS,UNITS,'a'*64,'SYNTHETIC_ONLY')


def frame(p,reverse=False,missing=False):
    fields={};mask=np.ones((100,100),bool);sign=-1 if reverse else 1
    for level in (850,700):
        for axis,value in [('u',3.),('v',2.)]:fields[f'{axis}{level}']=Field(np.full(mask.shape,sign*value),mask,axis,'m/s',level*100.)
    ps=np.full(mask.shape,90000.);ps[10:20]=80000.
    fields['ps']=Field(ps,mask,'surface_pressure','Pa',None)
    pm=mask.copy();pm[30:40]=not missing
    fields['pwat']=Field(np.full(mask.shape,80.),pm,'precipitable_water','kg m-2',None)
    valid=datetime(2023,5,1,6,tzinfo=timezone.utc)
    return EnvironmentFrame(ForecastIdentity(valid-timedelta(hours=6),timedelta(hours=6),valid),p.grid,fields,'retrospective',())


class DynamicTests(unittest.TestCase):
    def test_native_underground_neighbour_invalidates_bilinear_wind_support(self):
        p=pack();f=frame(p);grid=GridSpec([20.,25.,30.],[97.,102.,107.]);mask=np.ones((3,3),bool)
        fields={k:Field(np.full((3,3),float(v.values[50,50])),mask,v.quantity,v.unit,v.level_pa) for k,v in f.fields.items()}
        ps=np.full((3,3),90000.);ps[1,:]=80000.;fields['ps']=Field(ps,mask,'surface_pressure','Pa',None)
        native=EnvironmentFrame(f.identity,grid,fields,'retrospective',())
        d=PhysicalDote(p,DoteDefinition(40.,'SYNTHETIC')).physical(native)
        # PS interpolates above850hPa near the southern edge, but the four-point
        # support includes an underground850hPa neighbour.700hPa remains usable.
        self.assertFalse(d.valid[0,5,50]);self.assertTrue(d.valid[1,5,50])
    def test_physical_direction_pressure_and_moisture_definitions(self):
        p=pack();d=PhysicalDote(p,DoteDefinition(40.,'SYNTHETIC_TRAIN_REFERENCE'))
        a=d.physical(frame(p));r=d.physical(frame(p,reverse=True))
        self.assertAlmostEqual(a.O[1,50,50],.7,places=6)
        self.assertFalse(a.valid[0,15,50]);self.assertTrue(a.valid[1,15,50])
        np.testing.assert_allclose(a.O,-r.O,equal_nan=True)
        np.testing.assert_allclose(a.W,r.L,equal_nan=True)
        self.assertEqual(r.M[1,50,50],0.)
        signed=PhysicalDote(p,DoteDefinition(40.,'SYNTHETIC','signed_O')).physical(frame(p,reverse=True))
        self.assertLess(signed.M[1,50,50],0.)
        self.assertAlmostEqual(a.M[1,50,50],1.4,places=6)
    def test_pwat_missing_does_not_invalidate_O_or_supervision(self):
        p=pack();d=PhysicalDote(p,DoteDefinition(40.,'SYNTHETIC'))
        x,m=d(frame(p,missing=True))
        self.assertTrue(m[1,35,50]);self.assertFalse(m[7,35,50]);self.assertEqual(x[7,35,50],0.)
        self.assertEqual(p.region.sum(),10000)
        f=frame(p);f.fields['u850']=Field(f.fields['u850'].values,f.fields['u850'].valid,'u','normalized',85000.)
        with self.assertRaises(ValueError):d(f)
    def test_factory_full_B6_identity_rng_and_matched_active_parameters(self):
        from yuntapr.experimental.research_readiness.static_training import model_factory as old_factory
        p=pack();s={'B6':fit_static_train_scalers(p,fit_role='Train',fit_years=[2023],train_region=p.region,population_sha256='b'*64)}
        ref=old_factory({'B6':p},s)(2029,REPO_ROOT);rng=torch.get_rng_state().clone()
        m=model_factory(p,s)(2029,REPO_ROOT)
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        for kind in ('B7','B8'):
            for k,v in ref['B6'].state_dict().items():self.assertTrue(torch.equal(v,m[kind].base.state_dict()[k]),k)
        self.assertEqual(sum(v.numel() for v in m['B7'].parameters()),4411058)
        self.assertEqual(sum(v.numel() for v in m['B7'].parameters()),sum(v.numel() for v in m['B8'].parameters()))
        for side in ('gfs','terrain','fuse'):
            for k,v in getattr(m['B7'].fusion,side).state_dict().items():self.assertTrue(torch.equal(v,getattr(m['B8'].fusion,side).state_dict()[k]))
    def test_both_fusions_have_active_condition_gradients_after_identity_release(self):
        from yuntapr.experimental.core_innovation.stage2.fusion import paired_fusion_candidates
        a,b=paired_fusion_candidates(feature_channels=[48],gfs_channels=[26],terrain_channels=[28],projection_width=16,modulation_limit=.1)
        grid=GridSpec([25.,25.1,25.2],[101.,101.1,101.2]);mask=[torch.ones(1,1,3,3,dtype=torch.bool)]
        for model in (a,b):
            # Synthetic algebraic probe only, never an optimizer update or a
            # change to the actual model/precheck initialization.
            with torch.no_grad():
                model.fuse[0].weight.fill_(.001)
                if model.modulation:model.modulation.projections[0].weight.fill_(.01)
            f=torch.randn(1,48,3,3,requires_grad=True);g=torch.randn(1,26,3,3,requires_grad=True);t=torch.randn(1,28,3,3,requires_grad=True)
            out=model([f],[g],[t],mask,mask,mask,feature_grids=[grid],gfs_grids=[grid],terrain_grids=[grid])
            out.values[0].square().sum().backward()
            for p in model.parameters():self.assertTrue(p.grad is not None and torch.isfinite(p.grad).all() and torch.count_nonzero(p.grad))
            self.assertTrue(torch.count_nonzero(g.grad));self.assertTrue(torch.count_nonzero(t.grad))
    def test_reader_requires_explicit_dynamic_arm_and_batch_optional_fields(self):
        f=lambda x:x
        with self.assertRaises(ValueError):ReaderFactory(None,{},'SYNTHETIC',allowed_models=('B7',))
        with self.assertRaises(ValueError):ReaderFactory(None,{},'SYNTHETIC',dynamic_transform=f)
        factory=ReaderFactory(None,{},'SYNTHETIC',allowed_models=('B8',),dynamic_transform=f)
        self.assertIs(factory.dynamic_transform,f)
        z=torch.zeros(1);batch=Batch(z,z,z,z,z,z,z,('x',),('x',),'Train',{})
        self.assertIsNone(batch.to('cpu').dynamic)


if __name__=='__main__':unittest.main()
