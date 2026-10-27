"""New approval/package entrances; no real training and no optimizer calls."""
import unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.experimental.research_readiness import dynamic_training as module
from yuntapr.experimental.core_innovation.stage4.launch import ReaderFactory
from yuntapr.experimental.core_innovation.stage4 import data

class DynamicTrainingTests(unittest.TestCase):
    def test_new_ledger_arms_remain_intent_guarded(self):
        from yuntapr.experimental.core_innovation.stage4.engine import UpdateLedger
        for kind in ('B7','B8'):
            d=REPO_ROOT/'tests/research_readiness/.local'/uuid.uuid4().hex;d.mkdir(parents=True)
            ledger=UpdateLedger(d/'SYNTHETIC_NO_OPTIMIZER.sqlite',{},allowed_models=(kind,))
            try:
                ledger.reserve(kind,1)
                with self.assertRaises(PermissionError):ledger.reserve(kind,2)
                ledger.returned(kind,1)
                with self.assertRaises(PermissionError):ledger.reserve('B6',2)
                with self.assertRaises(PermissionError):ledger.reserve(kind,4321)
            finally:ledger.close()
    def test_supplementary_elevation_bins_preserve_total_and_core_partition(self):
        import numpy as np,torch
        from test_dynamic_terrain import pack
        p=pack();p.values[0,:30]=500;p.values[0,30:70]=1500;p.values[0,70:]=2500
        tail=module.TerrainTail(p);rate=torch.full((1,1,100,100),.2)
        b=SimpleNamespace(valid=torch.ones_like(rate,dtype=torch.bool),region=torch.ones_like(rate,dtype=torch.bool),rate=rate,ids=('2024-05-01T05:30:00+00:00',))
        o=SimpleNamespace(rain_prob=torch.full_like(rate,.5),conditional_quantiles_log=torch.zeros(1,32,100,100,dtype=torch.float64))
        tail.add_batch(o,b);s=dict(n_valid=10000,n_rain=10000,coverage=[0.]*32,conditional_pinball=float(np.log1p(float(rate[0,0,0,0]))*.5))
        r=tail.finish_checked({'groups':{'all':{'summary':s}}},b.ids)['elevation_diagnostics']['bins']
        self.assertEqual([v['n_valid'] for v in r.values()],[3000,4000,3000])
        self.assertTrue(all(v['brier']==.25 and v['q32_coverage']==0. for v in r.values()))
    def test_budget_comes_from_role_manifests_and_counts_two_B6_packs(self):
        p={'roles':{'Train':{'bytes_per_pass':10,'file_count':2},'Development':{'bytes_per_pass':20,'file_count':3}}}
        b=module.budget(p,7)
        self.assertEqual(b['weather_source_bytes_per_model'],270)
        self.assertEqual(b['total_source_bytes'],554);self.assertEqual(b['total_source_files'],92)
        self.assertEqual(b['dynamic_extra_raw_source_bytes'],0);self.assertEqual(b['replay_allowance'],0)
    def test_prior_B6_grant_cannot_authorize_B7_B8(self):
        p=dict(proposal_sha256='a'*64,tasks=[{'model':'B7','seed':2029},{'model':'B8','seed':2029}],budget={'total_updates':8640},scientific_choices={'basis':'windward_W'})
        v={'output_root':'SYNTHETIC_ONLY'}
        for a in ({},{'approved_by_researcher':False},{'approved_by_researcher':True,'code_commit':'old B6'}):
            with self.assertRaises(PermissionError):module.validate_approval(a,p,v,'b'*40)
    def test_actual_reader_factory_for_both_new_arms_roles_and_no_repeated_pass(self):
        ids=('SYNTHETIC_2023','SYNTHETIC_2024');files={'SYNTHETIC_SOURCE':dict(bytes=123,sha='a'*64)}
        scope=dict(ids=list(ids),file_count=1,bytes_per_pass=123,files=files);prepared={'roles':{'Train':scope,'Development':scope}};transform=object()
        def fake(*a,**kw):
            self.assertIs(kw['dynamic_transform'],transform)
            return SimpleNamespace(meter=SimpleNamespace(files=files),close=lambda:None)
        with patch.object(data,'BatchReader',side_effect=fake) as construct:
            for kind in ('B7','B8'):
                f=ReaderFactory(None,prepared,'SYNTHETIC',allowed_models=(kind,),dynamic_transform=transform)
                for role in ('Train','Development'):
                    f(role,1,ids,Path(f'{kind}_{role}_reads_01'))
                    with self.assertRaises(PermissionError):f(role,1,ids,Path(f'{kind}_{role}_reads_01'))
            self.assertEqual(construct.call_count,4)
    def controller(self,fail=False):
        directory=REPO_ROOT/'tests/research_readiness/.local'/uuid.uuid4().hex;directory.mkdir(parents=True)
        out=directory/'new';base=directory/'base.json';p={'budget':module.budget({'roles':{'Train':{'bytes_per_pass':10,'file_count':2},'Development':{'bytes_per_pass':20,'file_count':3}}},7)};calls=[]
        def report():return dict(source_identity={},population_ids_sha256='a',partition_sha256='b',groups={'all':dict(ids_sha='c',summary=dict(n_valid=1,brier=.1,auroc=.8,average_precision=.5,conditional_pinball=.2,q32_signed_bias=-.084375,q32_absolute_error=.084375,core_fp64=.1,coverage=[.9]*32,rain_strata=[]))})
        module.write(base,report());v=dict(output_root=str(out),baseline_paths={k:str(base) for k in ('B4','B5','B6')})
        class Process:
            def __init__(self,cmd,**kwargs):self.index=int(cmd[-1]);calls.append(self.index)
            def wait(self,timeout=None):
                if fail:return 2
                kind=module.TASKS[self.index][0];folder=out/f'{kind}_s2029';folder.mkdir()
                module.write(folder/'completion.json',dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',code_commit='b'*40,optimizer_updates=4320,total_logical_source_bytes=p['budget']['total_source_bytes_per_model'][kind],total_logical_source_files=p['budget']['total_source_files']//2))
                module.write(folder/f'{kind}_development_09.json',report());return 0
            def poll(self):return 2 if fail else 0
        with patch.object(module,'checked',return_value=(p,v,{},{})),patch.object(module,'resources',return_value={}),patch.object(module.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)),patch.object(module.subprocess,'Popen',Process):
            if fail:
                with self.assertRaises(RuntimeError):module.execute(REPO_ROOT,'p','v','a','b'*40)
                self.assertTrue((out/'failure.json').exists());self.assertFalse((out/'completion.json').exists())
            else:
                module.execute(REPO_ROOT,'p','v','a','b'*40)
                with self.assertRaises(PermissionError):module.execute(REPO_ROOT,'p','v','a','b'*40)
        return calls
    def test_serial_once_only_B7_then_B8(self):self.assertEqual(self.controller(),[0,1])
    def test_failure_blocks_B8_without_replay(self):self.assertEqual(self.controller(fail=True),[0])

if __name__=='__main__':unittest.main()
