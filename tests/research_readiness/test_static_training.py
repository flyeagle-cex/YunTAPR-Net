import copy,uuid,unittest
from pathlib import Path
import numpy as np
import torch
from types import SimpleNamespace
from unittest.mock import patch
from yuntapr.experimental.core_innovation.grid import frozen_sp04_grid
from yuntapr.experimental.core_innovation.stage4.engine import paired_models,UpdateLedger
from yuntapr.experimental.research_readiness.static_training import model_factory,training_budget,validate_approval
from yuntapr.experimental.research_readiness import static_training as module
from yuntapr.experimental.research_readiness.static_terrain import StaticPack,fit_static_train_scalers,B6_CHANNELS,UNITS
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.training.phase_a_protocol import parameter_groups

class StaticTrainingTests(unittest.TestCase):
    def test_separate_static_payload_budget_not_assumed_equal_to_B4(self):
        x=training_budget({'B5':123,'B6':456})
        self.assertEqual(x['total_updates'],8640);self.assertEqual(x['total_source_bytes'],955143282024+579)
        self.assertEqual(x['total_source_files'],285626);self.assertEqual(x['replay_allowance'],0)
    def test_prior_or_partial_grant_never_authorizes_new_models(self):
        p=dict(proposal_sha256='a'*64,tasks=[{'model':'B5','seed':2029},{'model':'B6','seed':2029}],budget=training_budget({'B5':1,'B6':2}),scientific_choices={'native_derivative':True})
        v={'output_root':'SYNTHETIC_NEW_OUTPUT'}
        for a in ({},{'approved_by_researcher':False},{'approved_by_researcher':True,'code_commit':'old B2 grant'}):
            with self.assertRaises(PermissionError):validate_approval(a,p,v,'b'*40)
        a=dict(approved_by_researcher=True,code_commit='b'*40,proposal_sha256=p['proposal_sha256'],tasks=p['tasks'],budget=p['budget'],scientific_choices=p['scientific_choices'],output_root=v['output_root'],decision_id='SYNTHETIC_VALIDATOR_ONLY')
        validate_approval(a,p,v,'b'*40);a['scientific_choices']={}
        with self.assertRaises(PermissionError):validate_approval(a,p,v,'b'*40)
    def test_ledger_static_arm_intent_and_old_arm_stays_rejected(self):
        d=REPO_ROOT/'tests/research_readiness/.local'/uuid.uuid4().hex;d.mkdir(parents=True)
        l=UpdateLedger(d/'ledger.sqlite',{},allowed_models=('B5',))
        try:
            with self.assertRaises(PermissionError):l.reserve('B4',1)
            l.reserve('B5',1)
            with self.assertRaises(PermissionError):l.reserve('B5',2)
            l.returned('B5',1)
            with self.assertRaises(PermissionError):l.reserve('B5',4321)
        finally:l.close()
    def test_factory_keeps_full_B4_weights_and_training_rng(self):
        grid=frozen_sp04_grid(REPO_ROOT);region=np.ones((100,100),bool);packs={};scalers={}
        for kind,n in (('B5',1),('B6',6)):
            packs[kind]=StaticPack(grid,np.zeros((n,100,100),np.float32),np.ones((n,100,100),bool),region,('elevation_m',) if n==1 else B6_CHANNELS,UNITS[:n],'a'*64,'SYNTHETIC_ONLY')
            scalers[kind]=fit_static_train_scalers(packs[kind],fit_role='Train',fit_years=[2023],train_region=region,population_sha256='b'*64)
        ref=paired_models(2029,REPO_ROOT);rng=torch.get_rng_state().clone()
        m=model_factory(packs,scalers)(2029,REPO_ROOT)
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        for kind in ('B5','B6'):
            for k,t in ref['B4'].state_dict().items():self.assertTrue(torch.equal(t,m[kind].base.state_dict()[k]),k)
            self.assertEqual(torch.count_nonzero(m[kind].static.output.weight).item(),0)
            _,grouping=parameter_groups(m[kind],check_counts=False)
            self.assertEqual(grouping['counts']['total'],sum(p.numel() for p in m[kind].parameters()))
            self.assertIn('static.output.weight',grouping['names']['DECAY_GROUP'])
            self.assertIn('static.output.bias',grouping['names']['NO_DECAY_GROUP'])
        one=model_factory({'B5':packs['B5']},scalers)(2029,REPO_ROOT)
        self.assertNotIn('B6',one)
    def controller(self,fail=False):
        parent=REPO_ROOT/'tests/research_readiness/.local'/uuid.uuid4().hex;parent.mkdir(parents=True)
        budget=training_budget({'B5':1,'B6':2});out=parent/'new';old=parent/'old';old.mkdir()
        p=dict(budget=budget);v=dict(output_root=str(out),historical_pair=str(old));a={'synthetic_only':True};calls=[]
        def report():return dict(source_identity={},population_ids_sha256='a',partition_sha256='b',groups={'all':dict(ids_sha='c',summary=dict(n_valid=1,brier=.1,auroc=.8,average_precision=.5,conditional_pinball=.2,q32_signed_bias=-.084375,core_fp64=.1,coverage=[.9]*32,rain_strata=[]))})
        module.write(old/'B4_development_09.json',report())
        class Process:
            def __init__(self,command,**kwargs):self.index=int(command[-1]);calls.append(self.index)
            def wait(self,timeout=None):
                if fail:return 2
                kind=module.TASKS[self.index][0];folder=out/f'{kind}_s2029';folder.mkdir()
                module.write(folder/'completion.json',dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',code_commit='b'*40,optimizer_updates=4320,total_logical_source_bytes=budget['total_source_bytes_per_model'][kind],total_logical_source_files=142813))
                module.write(folder/f'{kind}_development_09.json',report());return 0
            def poll(self):return 2 if fail else 0
        with patch.object(module,'checked',return_value=(p,v,a,{})),patch.object(module,'resources',return_value={}),patch.object(module.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)),patch.object(module.subprocess,'Popen',Process):
            if fail:
                with self.assertRaises(RuntimeError):module.execute(REPO_ROOT,'p','v','a','b'*40)
                self.assertTrue((out/'failure.json').is_file());self.assertFalse((out/'completion.json').exists())
            else:
                module.execute(REPO_ROOT,'p','v','a','b'*40)
                with self.assertRaises(PermissionError):module.execute(REPO_ROOT,'p','v','a','b'*40)
                self.assertTrue((out/'static_paired_summary.json').is_file())
        return calls
    def test_serial_B5_B6_no_duplicate_run(self):self.assertEqual(self.controller(),[0,1])
    def test_failure_stops_remaining_model_no_replay(self):self.assertEqual(self.controller(fail=True),[0])

if __name__=='__main__':unittest.main()
