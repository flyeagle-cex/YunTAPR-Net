import unittest
from datetime import timedelta
import numpy as np
import test_preparation as base
from yuntapr.experimental.core_innovation.stage3.statistics import *
from yuntapr.experimental.core_innovation.stage3.terrain_boundary import join_east_west
from yuntapr.experimental.core_innovation.terrain import DemWindow,terrain_features
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.gfs import Field,ForecastIdentity,EnvironmentFrame
from yuntapr.experimental.core_innovation.multispectral import TrainNormalization


class NewPathTests(unittest.TestCase):
    def test_finalized_population_statistics_end_to_end_without_raw_reads(self):
        sid='2023-05-01T00:00:00Z';analysis=utc(sid)+timedelta(minutes=30);cache={};frame_ids=[]
        for i,m in enumerate((60,50,40,30,20,10)):
            key='frame'+str(i);frame_ids.append(key);x=np.arange(7*9,dtype=float).reshape(7,3,3)+i
            cache[key]=satellite_statistics(x,np.ones_like(x,bool),year=2023,receipt={'nominal':(analysis-timedelta(minutes=m)).isoformat()})
            cache[key]['source_sha256']='a'*64
        f=base.PreparationTests().frame();f.fields['ps']=Field(np.arange(9,dtype=float).reshape(3,3)+100000.,np.ones((3,3),bool),'surface_pressure','Pa',None)
        f=EnvironmentFrame(ForecastIdentity(analysis-timedelta(hours=6),timedelta(hours=6),analysis),f.grid,f.fields,'retrospective',())
        cache['environment']=environment_statistics(f,keys=V13_KEYS,target_grid=f.grid);cache['environment']['source_sha256']='b'*64
        rows=[dict(sample_id=sid,frame_ids=frame_ids,environment_id='environment')]
        b13=TrainNormalization('B13',271.,20.,'K',(2023,),'Train',0,'pinned_frozen')
        population=dict(Train=[sid],Development=['2024-05-01T00:00:00Z'])
        kwargs=dict(final_train_ids=population['Train'],final_dev_ids=population['Development'],final_population_sha=digest(population),source_manifest_sha='d'*64,frozen_b13=b13,environment_keys=V13_KEYS,forecast_lead_hours=6)
        r=finalize_statistics(rows,cache,**kwargs)
        self.assertFalse(r['B13_refitted']);self.assertEqual(r['new_band_count_each'],54)
        self.assertEqual(r['positive_PWAT_reference_kg_m2'],4.5);self.assertEqual(r['positive_PWAT_count'],8)
        self.assertEqual(r['environment_scalers']['temperature500']['count'],9)
        self.assertEqual(r['adapter_status'],'13_CHANNEL_MODEL_ADAPTER_PENDING_RESEARCHER_APPROVAL')
        with self.assertRaisesRegex(ValueError,'complete final'):finalize_statistics([],cache,**kwargs)
        rows[0]['frame_ids']=frame_ids[::-1]
        with self.assertRaisesRegex(ValueError,'six-slot'):finalize_statistics(rows,cache,**kwargs)
        rows[0]['frame_ids']=frame_ids;cache['environment']['forecast_identity']['lead_hours']=0
        with self.assertRaisesRegex(ValueError,'fixed forecast vintage'):finalize_statistics(rows,cache,**kwargs)

    def test_shared_edge_join_preserves_native_gradient_and_rejects_mismatch(self):
        lat=np.array([26.02,26.01,26.,25.99,25.98]);lon=np.array([102.98,102.99,103.,103.01,103.02])
        z=np.broadcast_to(np.arange(5)*10.,(5,5)).copy();mask=np.ones((5,5),bool)
        west=DemWindow(GridSpec(lat,lon[:3]),z[:,:3],mask[:,:3]);east=DemWindow(GridSpec(lat,lon[2:]),z[:,2:],mask[:,2:])
        joined=join_east_west(west,east);features=terrain_features(joined.elevation_m,joined.valid,joined.grid,elevation_unit='m')
        self.assertTrue(features.gradient_valid[2,2]);self.assertGreater(features.east_gradient[2,2],0)
        bad=east.elevation_m.copy();bad[:,0]+=1
        with self.assertRaisesRegex(ValueError,'Shared-edge'):join_east_west(west,DemWindow(east.grid,bad,east.valid))


if __name__=='__main__':unittest.main()
