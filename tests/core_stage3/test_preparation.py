import unittest
from pathlib import Path
import tempfile,uuid
from datetime import datetime,timedelta,timezone
import numpy as np
from yuntapr.experimental.core_innovation.stage3.planning import *
from yuntapr.experimental.core_innovation.stage3.statistics import *
from yuntapr.experimental.core_innovation.stage2.population import TrainMoments
from yuntapr.experimental.core_innovation.multispectral import TrainNormalization
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.gfs import Field,EnvironmentFrame,ForecastIdentity


class PreparationTests(unittest.TestCase):
    def path(self):
        root=Path(__file__).resolve().parents[2]/'tests/core_stage3/.local'/uuid.uuid4().hex
        root.mkdir(parents=True);return root/'cache.sqlite'

    def manifest(self):return {'a':dict(year=2023,bytes=10,files=1,expected_sha256='a'*64)}

    def grant(self,manifest):return dict(authorized=True,decision_id='SYNTHETIC_TEST_ONLY',manifest_sha=digest(manifest),max_bytes=10,max_files=1)

    def payload(self):return dict(year=2023,source_sha256='a'*64,raw_bytes_read=10,value='synthetic_sufficient_statistics')

    def test_resume_dedup_and_changed_processor_rejection(self):
        path=self.path();m=self.manifest();g=self.grant(m);calls=[]
        cache=SourceCache(path,manifest=m,manifest_sha=digest(m),grant=g)
        first=cache.read_once('a',lambda:(calls.append(1) or self.payload()));cache.close()
        cache=SourceCache(path,manifest=m,manifest_sha=digest(m),grant=g)
        self.assertEqual(cache.read_once('a',lambda:self.fail('Decoded twice')),first);self.assertEqual(len(calls),1);cache.close()
        with self.assertRaises(ValueError):SourceCache(path,manifest=m,manifest_sha=digest(m),grant=g,processor_id='different')

    def test_uncertain_read_is_reserved_and_cannot_auto_retry(self):
        path=self.path();m=self.manifest();g=self.grant(m);cache=SourceCache(path,manifest=m,manifest_sha=digest(m),grant=g)
        def interrupted():raise RuntimeError('synthetic interruption after intent commit')
        with self.assertRaises(RuntimeError):cache.read_once('a',interrupted)
        cache.close();cache=SourceCache(path,manifest=m,manifest_sha=digest(m),grant=g)
        with self.assertRaisesRegex(RuntimeError,'no automatic retry'):cache.read_once('a',lambda:self.fail('Unsafe retry'))
        self.assertEqual(cache.db.execute('SELECT SUM(bytes) FROM jobs').fetchone()[0],10);cache.close()

    def test_grant_and_budget_checked_before_loader(self):
        m=self.manifest();g=self.grant(m);g['authorized']=False
        with self.assertRaises(PermissionError):SourceCache(self.path(),manifest=m,manifest_sha=digest(m),grant=g)
        g=self.grant(m);g['max_bytes']=9;cache=SourceCache(self.path(),manifest=m,manifest_sha=digest(m),grant=g)
        with self.assertRaises(PermissionError):cache.read_once('a',lambda:self.fail('Read without budget'))
        cache.close()

    def test_cached_exposure_weighting_equals_inherited_train_moments(self):
        ids=['2023-05-01T00:00:00Z','2023-05-01T00:30:00Z']
        x=np.arange(9*7*3*3,dtype=np.float32).reshape(9,7,3,3)
        first=datetime(2023,4,30,23,30,tzinfo=timezone.utc)
        summaries=[satellite_statistics(v,np.ones_like(v,bool),year=2023,receipt={'nominal':(first+timedelta(minutes=i*10)).isoformat()}) for i,v in enumerate(x)]
        original=TrainMoments(ids,population_id='synthetic');cached=CachedTrainMoments(ids,population_id='synthetic')
        for index,sid in enumerate(ids):
            values=x[index*3:index*3+6]
            original.update(sid,values,np.ones_like(values,bool),channels=CHANNELS,role='Train');cached.update_cached(sid,summaries[index*3:index*3+6])
        np.testing.assert_allclose(cached.mean,original.mean);np.testing.assert_allclose(cached.m2,original.m2)
        b13=TrainNormalization('B13',271.,20.,'K',(2023,),'Train',0,'frozen')
        self.assertIs(cached.finish(frozen_b13=b13)['B13'],b13)
        with self.assertRaises(ValueError):cached.update_cached(ids[0],summaries)

    def test_development_has_no_fitted_sufficient_statistics(self):
        x=np.ones((7,3,3));r=satellite_statistics(x,np.ones_like(x,bool),year=2024,receipt={})
        self.assertEqual(r['moments'],{})
        fit=CachedTrainMoments(['2023-05-01T00:00:00Z'],population_id='synthetic')
        with self.assertRaises(ValueError):fit.update_cached('2023-05-01T00:00:00Z',[r]*6)
        with self.assertRaises(ValueError):satellite_statistics(x,np.ones_like(x,bool),year=2025,receipt={})

    def frame(self):
        grid=GridSpec([26.,25.,24.],[101.,102.,103.]);now=datetime(2023,5,1,tzinfo=timezone.utc)
        fields={}
        for key,unit in zip(V13_KEYS,V13_UNITS):
            level=85000. if '850' in key else 70000. if '700' in key else 50000. if '500' in key else None
            quantity='surface_pressure' if key=='ps' else 'precipitable_water' if key=='pwat' else 'temperature' if key.startswith('temperature') else 'relative_humidity' if key.startswith('relative') else key[0] if key[0] in ('u','v') else 'cape'
            values=np.arange(9,dtype=float).reshape(3,3)+(80000. if key=='ps' else 0.)
            fields[key]=Field(values,np.ones((3,3),bool),quantity,unit,level)
        return EnvironmentFrame(ForecastIdentity(now,timedelta(0),now),grid,fields,'retrospective',())

    def test_gfs_masks_positive_pwat_and_11_13_channel_contract(self):
        frame=self.frame();r=environment_statistics(frame,keys=V13_KEYS,target_grid=frame.grid)
        self.assertEqual(r['moments']['temperature850']['n'],0);self.assertEqual(r['moments']['temperature500']['n'],9)
        self.assertEqual(r['pwat_positive_count'],8);self.assertEqual(r['pwat_positive_sum']/8,4.5)
        frame.fields['pwat']=Field(np.ones((3,3)),np.ones((3,3),bool),'precipitable_water','kg/m2',None)
        with self.assertRaisesRegex(ValueError,'Canonical physical units'):environment_statistics(frame,keys=MEE_KEYS,target_grid=frame.grid)

    def test_same_valid_leads_and_different_valid_not_mixed(self):
        def row(init,lead):return dict(relative_path=f'2023\\20230501\\gfs_0p25_{init}_f{lead:03d}.nc',size_bytes='100')
        main=forecast_index([row('2023050100',6),row('2023050106',0),row('2023050100',3)],kind='main')
        thermo={k:dict(v,kind='thermo',readable='True') for k,v in main.items()}
        pairs,_=pair_index(main,thermo)
        target=dict(sample_id='2023-05-01T05:30:00Z',window_start='2023-05-01T05:30:00Z',analysis_time='2023-05-01T06:00:00Z')
        result=scene_options([target],pairs);self.assertEqual([p['lead'] for p in result[0]['options']],[0,6])
        self.assertEqual(len(select_by_lead(result,3)),0)

    def test_satellite_dedup_preserves_exposure_counts(self):
        row={f'slot_{i}_nominal':f'2023-05-01T00:{i*10:02d}:00Z' for i in range(6)};row['sample_id']='synthetic'
        frames={v:dict(relative_path=v.replace(':','_')+'.nc',source_bytes='100',source_sha256='a'*64,status='FULL_VALID',obs_start=v,obs_end=v) for k,v in row.items() if k.startswith('slot_')}
        manifest=satellite_manifest([dict(record=row),dict(record=row)],frames)
        self.assertEqual(len(manifest['files']),6);self.assertEqual(manifest['scene_slot_exposures'],12)
        self.assertTrue(all(f['exposure_count']==2 for f in manifest['files']))

    def test_exact_training_budget_not_reported_for_unverified_population(self):
        self.assertIsNone(training_budget()['exact_optimizer_attempt_cap'])
        result=training_budget(final_train_ids=['2023-05-01T00:00:00Z']*1,final_dev_ids=['2024-05-01T00:00:00Z'],final_population_sha='a'*64)
        self.assertEqual(result['exact_optimizer_attempt_cap'],18);self.assertEqual(result['inherited_allowance'],0)


if __name__=='__main__':unittest.main()
