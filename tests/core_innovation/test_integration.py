from datetime import datetime,timedelta,timezone
import unittest
import numpy as np
import torch
from yuntapr.experimental.core_innovation.grid import GridSpec,BilinearMap
from yuntapr.experimental.core_innovation.gfs import ForecastIdentity,GFSFile,Field,combine_environment
from yuntapr.experimental.core_innovation.terrain import terrain_features,project_terrain
from yuntapr.experimental.core_innovation.dote import dote_proxy
from yuntapr.experimental.core_innovation.dtfm import MaskedTerrainModulation


class IntegrationTests(unittest.TestCase):
    def test_synthetic_environment_terrain_dote_dtfm_chain(self):
        grid=GridSpec(np.linspace(25.01,25.,7),np.linspace(101.,101.01,7))
        terrain=terrain_features(np.tile(np.arange(7)*10.,(7,1)),np.ones((7,7),bool),grid,elevation_unit='m')
        now=datetime(2023,5,1,tzinfo=timezone.utc);identity=ForecastIdentity(now,timedelta(0),now)
        def field(x,q,unit,level=None):return Field(np.full((7,7),x),np.ones((7,7),bool),q,unit,level)
        a=GFSFile(identity,grid,{'u850':field(3.,'u','m/s',85000),'v850':field(1.,'v','m/s',85000),'ps':field(100000.,'surface_pressure','Pa')},{'synthetic':True})
        b=GFSFile(identity,grid,{'t850':field(280.,'temperature','K',85000)},{'synthetic':True})
        env=combine_environment(a,b,target_valid_time=now,decision_time=now,mode='retrospective')
        o=dote_proxy(terrain,env.fields['u850'].values[None],env.fields['v850'].values[None],
            (env.fields['u850'].valid&env.fields['v850'].valid)[None],np.array([850]),env.fields['ps'].values,env.fields['ps'].valid,
            wind_grid=grid,wind_unit='m/s',pressure_unit='hPa',surface_pressure_unit='Pa')
        self.assertTrue(o.valid[:,1:-1,1:-1].all());self.assertFalse(o.valid[:,0,:].any())
        conditions=torch.from_numpy(np.where(o.valid,o.orographic_proxy_m_s,0).astype('float32'))[None]
        cmask=torch.from_numpy(o.valid)[None]
        features=torch.ones((1,2,7,7),requires_grad=True);fmask=torch.ones((1,1,7,7),dtype=torch.bool)
        module=MaskedTerrainModulation(feature_channels=[2],condition_channels=[1],modulation_limit=.25)
        result=module([features],[conditions],[fmask],[cmask],feature_grids=[grid],condition_grids=[grid])
        torch.testing.assert_close(result.values[0],features)
        result.values[0].sum().backward();self.assertTrue(torch.isfinite(features.grad).all())

    def test_gradients_before_optional_target_mapping(self):
        grid=GridSpec([25.02,25.01,25.,24.99,24.98],[101.,101.01,101.02,101.03,101.04])
        features=terrain_features(np.tile(np.arange(5)*20.,(5,1)),np.ones((5,5),bool),grid,elevation_unit='m')
        target=GridSpec([25.005,24.995],[101.015,101.025])
        projected=project_terrain(features,BilinearMap.build(grid,target))
        self.assertTrue(projected.gradient_valid.all());self.assertTrue((projected.east_gradient>0).all())


if __name__=='__main__':unittest.main()
