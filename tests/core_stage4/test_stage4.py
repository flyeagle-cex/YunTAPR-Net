import json,math,sqlite3,unittest,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import netCDF4
import numpy as np
import torch
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.experimental.core_innovation.stage2 import CHANNELS,MEE_KEYS,MEE_V13_KEYS
from yuntapr.experimental.core_innovation.stage2.models import MEECandidate,paired_spectral_candidates
from yuntapr.experimental.core_innovation.stage2.environment import EnvironmentScaler,V13_UNITS,prepare_mee
from yuntapr.experimental.core_innovation.gfs import Field,EnvironmentFrame,ForecastIdentity
from yuntapr.experimental.core_innovation.grid import frozen_sp04_grid
from yuntapr.experimental.core_innovation.stage4 import *
from yuntapr.experimental.core_innovation.stage4.engine import UpdateLedger,FormalDecision,PairedExecutor,epoch_order,lr_for_update,seed_all
from yuntapr.experimental.core_innovation.stage4.data import target_memory
from yuntapr.experimental.core_innovation.stage4.evaluation import Evaluation,elevation_groups,paired_difference
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics
from yuntapr.models.quantile_v2.outputs import LogDomainOutput
from yuntapr.spatial.sp04_mapping import load_sp04


def folder():
    p=REPO_ROOT/'tests/core_stage4/.local'/uuid.uuid4().hex;p.mkdir(parents=True);return p


class Stage4Tests(unittest.TestCase):
    def test_selected_seed_must_match_startup_environment(self):
        with patch.dict('os.environ',{'CUBLAS_WORKSPACE_CONFIG':':4096:8','PYTHONHASHSEED':'2027'}):
            with self.assertRaises(RuntimeError):seed_all(DRY_SEED)
        with patch.dict('os.environ',{'CUBLAS_WORKSPACE_CONFIG':':4096:8','PYTHONHASHSEED':str(DRY_SEED)}):seed_all(DRY_SEED)

    def test_13_independent_masks_and_no_500_wind_fallback(self):
        m=MEECandidate(width=16,keys=MEE_V13_KEYS)
        with torch.no_grad():m.output.weight.fill_(.1)
        x=torch.randn(1,13,5,5,requires_grad=True);v=torch.ones_like(x,dtype=torch.bool)
        v[:,[2,3,4,5,6,7,8,9]]=False
        y,used=m(x,v,keys=MEE_V13_KEYS);self.assertFalse(used.any());self.assertTrue((y==0).all())
        v[:,[3,5,8,9]]=True
        y,used=m(x,v,keys=MEE_V13_KEYS);self.assertTrue(used.all());y.sum().backward()
        self.assertTrue(torch.isfinite(x.grad).all());self.assertTrue((x.grad[:,[2,4,6,7]]==0).all())
        invalid=x.detach().clone();invalid[~v]=float('nan')
        torch.testing.assert_close(y.detach(),m(invalid,v,keys=MEE_V13_KEYS)[0])
        with self.assertRaises(ValueError):m(x,v,keys=MEE_V13_KEYS[::-1])

    def test_b3_unchanged_common_initialization_and_parameter_delta(self):
        kw=dict(numerics=CandidateNumerics(1e-4,1e-4),mee_width=16)
        torch.manual_seed(DRY_SEED);old=paired_spectral_candidates(**kw)
        torch.manual_seed(DRY_SEED);new=paired_spectral_candidates(**kw,mee_keys=MEE_V13_KEYS)
        for k,v in old[0].state_dict().items():self.assertTrue(torch.equal(v,new[0].state_dict()[k]))
        for part in ('backbone','heads'):
            for k,v in getattr(new[0],part).state_dict().items():self.assertTrue(torch.equal(v,getattr(new[1],part).state_dict()[k]))
        self.assertEqual(sum(p.numel() for p in new[1].parameters())-sum(p.numel() for p in old[1].parameters()),576)

    def test_13_scalers_keep_levels_and_train_provenance(self):
        grid=frozen_sp04_grid();shape=grid.shape;fields={};scalers={}
        for key,unit in zip(MEE_V13_KEYS,V13_UNITS):
            quantity=('surface_pressure' if key=='ps' else 'precipitable_water' if key=='pwat' else 'cape' if key=='cape' else 'relative_humidity' if key.startswith('relative') else 'temperature' if key.startswith('temperature') else key[0])
            level=float(key[-3:])*100 if key[-3:].isdigit() else None
            fields[key]=Field(np.full(shape,75000. if key=='ps' else 280.),np.ones(shape,bool),quantity,unit,level)
            scalers[key]=EnvironmentScaler(key,10.,2.,unit,(2023,),'Train',POPULATION_SHA)
        a=datetime(2023,5,1,6,tzinfo=timezone.utc);f=EnvironmentFrame(ForecastIdentity(a-timedelta(hours=6),timedelta(hours=6),a),grid,fields,'retrospective',())
        x,v,keys=prepare_mee(f,target_grid=grid,scalers=scalers,keys=MEE_V13_KEYS)
        self.assertEqual(keys,MEE_V13_KEYS);self.assertFalse(v[2].any());self.assertTrue((x[2]==0).all());self.assertTrue(v[3].all());self.assertTrue(v[11].all())
        with self.assertRaises(ValueError):EnvironmentScaler('temperature500',1.,2.,'K',(2024,),'Development',POPULATION_SHA)

    def test_target_memory_half_hour_axes_and_fill(self):
        mapping=load_sp04();ds=netCDF4.Dataset('fixture.nc','w',memory=4*1024**2)
        for name,n in (('time',48),('lat',130),('lon',140)):ds.createDimension(name,n)
        ds.source='GPM_3IMERGHH_07';ds.title='IMERG Final Run V07 synthetic fixture'
        # Only the frozen [10:110,20:120] crop is used by the inherited reader.
        lat=ds.createVariable('lat','f4',('lat',));lon=ds.createVariable('lon','f4',('lon',))
        lat[:]=0;lon[:]=0;lat[10:110]=mapping.axes['target_lat'];lon[20:120]=mapping.axes['target_lon']
        t=ds.createVariable('time','f8',('time',));t.units='minutes since 2023-05-01 00:00:00';t[:]=np.arange(48)*30
        v=ds.createVariable('precipitation','f4',('time','lat','lon'),fill_value=-9999.);v.units='mm hr-1';v[:]=2.;v[11,10,20]=-9999.
        raw=bytes(ds.close());y,valid=target_memory(raw,11,mapping,'2023-05-01T05:30:00+00:00')
        self.assertFalse(valid[0,0]);self.assertTrue(np.isnan(y[0,0]));self.assertEqual(y[1,1],2.)
        with self.assertRaises(ValueError):target_memory(raw,11,mapping,'2023-05-01T06:00:00+00:00')

    def test_order_last_partial_batch_and_480_step_schedule(self):
        ids=tuple(f'synthetic_{i}' for i in range(TRAIN_N));o=epoch_order(ids,DRY_SEED,1)
        self.assertEqual(o,epoch_order(ids,DRY_SEED,1));self.assertNotEqual(o,epoch_order(ids,DRY_SEED,2));self.assertEqual(set(ids),set(o))
        batches=[o[i:i+2] for i in range(0,len(o),2)];self.assertEqual(len(batches),480);self.assertEqual(len(batches[-1]),1)
        self.assertEqual(PAIR_CAP,8640);self.assertAlmostEqual(lr_for_update(1,steps_per_epoch=STEPS),1e-4/480)
        self.assertEqual(lr_for_update(480,steps_per_epoch=STEPS),1e-4)
        self.assertAlmostEqual(lr_for_update(4320,steps_per_epoch=STEPS),1e-6+(1e-4-1e-6)*(1+math.cos(math.pi*3840/23520))/2)

    def test_durable_attempts_cap_and_uncertainty_no_retry(self):
        p=folder()/'updates.sqlite';l=UpdateLedger(p,{'fixture':'SYNTHETIC_NO_OPTIMIZER'})
        try:
            l.reserve('B3',1)
            with self.assertRaises(PermissionError):l.reserve('B3',1)
            with self.assertRaises(PermissionError):l.reserve('B3',2)
            l.returned('B3',1);l.reserve('B3',2);l.returned('B3',2)
            with l.db:
                l.db.executemany('INSERT INTO updates VALUES (?,?,?)',[(k,u,'RETURNED') for k in ('B3','B4') for u in range(1,4321) if (k,u) not in (('B3',1),('B3',2))])
            with self.assertRaises(PermissionError):l.reserve('B4',4321)
        finally:l.close()
        with self.assertRaises(PermissionError):UpdateLedger(p,{})

    def test_formal_launch_requires_researcher_decision_before_optimizer(self):
        p=folder()/'never_created'
        with patch('yuntapr.experimental.core_innovation.stage4.engine.new_adamw',side_effect=AssertionError('Optimizer must not be constructed')):
            with self.assertRaises(PermissionError):PairedExecutor(None,p).run(None)
        self.assertFalse(p.exists())
        with self.assertRaises(PermissionError):FormalDecision('fixture',DRY_SEED,POPULATION_SHA,True,True,True).validate()

    def test_reused_exact_metrics_partitions_and_paired_differences(self):
        ids=('2024-05-01T05:30:00+00:00','2024-05-01T11:30:00+00:00');a=('2024-05-01T06:00:00+00:00','2024-05-01T12:00:00+00:00')
        x=torch.zeros(2,1,100,100);p=torch.full_like(x,.5);q=torch.linspace(.11,2,32,dtype=torch.float64)[None,:,None,None].expand(2,32,100,100).clone()
        rate=torch.zeros_like(x);rate[:,:,:1,:4]=torch.tensor([0.,.2,2.,25.]);mask=torch.zeros_like(x,dtype=torch.bool);mask[:,:,:1,:4]=True
        b=SimpleNamespace(role='Development',ids=ids,analyses=a,rate=rate,valid=torch.ones_like(mask),region=mask)
        grid=frozen_sp04_grid();z=np.full((100,100),2000.);z[0,:2]=1000.
        alt=elevation_groups(z,np.ones_like(z,bool),edges_m=(0.,1500.,4000.),grid=grid,expected_grid=grid,source_sha='0'*64)
        e=Evaluation(ids,a,{'fixture':'SYNTHETIC'},folder()/'evaluation',strong_scene_ids=(ids[0],),altitude=alt)
        try:e.add(LogDomainOutput(x,p,q),b);r=e.finish()
        finally:e.close()
        s=r['groups']['all']['summary'];self.assertEqual(s['n_valid'],8);self.assertEqual(s['brier'],.25);self.assertEqual(s['auroc'],.5);self.assertEqual(s['average_precision'],.75)
        self.assertEqual(r['groups']['scene_max_ge20']['summary']['scenes'],1)
        self.assertEqual(r['groups']['elevation_0']['summary']['n_valid'],4)
        self.assertEqual(r['groups']['all']['scope'],'STAGE4_2024_DEV_FIXED_F006_RETROSPECTIVE')
        self.assertEqual(paired_difference(r,r)['groups']['all']['brier'],0.)
        different=dict(r,partition_sha256='1'*64)
        with self.assertRaises(ValueError):paired_difference(r,different)
