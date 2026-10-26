"""New launcher checks only; synthetic metadata/tensors, no weather payloads."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.experimental.core_innovation.stage4 import engine
from yuntapr.experimental.core_innovation.stage4.data import sha
from yuntapr.experimental.core_innovation.stage4.evaluation import Evaluation
from yuntapr.experimental.core_innovation.stage3.planning import digest
from yuntapr.experimental.research_readiness import multiseed as m


class MultiseedTests(unittest.TestCase):
    def setUp(self):
        parent = REPO_ROOT/'tests/research_readiness/.local'
        parent.mkdir(parents=True, exist_ok=True)
        self.base = parent/('multiseed_'+uuid.uuid4().hex)
        self.base.mkdir()
        self.proposal = dict(proposal_sha256='a'*64)
        self.private = dict(output_root=str(self.base/'package'), historical_pair=str(self.base/'old'))
        self.approval = dict(approved_by_researcher=True, proposal_sha256='a'*64,
                             code_commit='b'*40, tasks=[dict(model=k, seed=s) for k,s in m.TASKS],
                             budget=copy.deepcopy(m.BUDGET), output_root=self.private['output_root'],
                             decision_id='SYNTHETIC_TEST_ONLY_NEVER_A_REAL_RESEARCHER_GRANT')

    def test_exact_package_authorization_and_storage_binding(self):
        m.validate_approval(self.approval, self.proposal, self.private, 'b'*40)
        for field,value in [('approved_by_researcher',False),('code_commit','c'*40),
                            ('tasks',[dict(model='B3',seed=2029)]),('output_root','other'),
                            ('budget',dict(m.BUDGET,replay_allowance=1)),('decision_id','')]:
            a=copy.deepcopy(self.approval);a[field]=value
            with self.subTest(field=field), self.assertRaises(PermissionError):
                m.validate_approval(a,self.proposal,self.private,'b'*40)

    def test_no_approval_stops_before_resources_outputs_or_optimizer(self):
        for name,body in [('proposal.json',self.proposal),('private.json',self.private),('approval.json',{})]:
            (self.base/name).write_text(json.dumps(body),encoding='utf-8')
        # A valid digest reaches the actual approval validator, never resources.
        p=dict(self.proposal);p.pop('proposal_sha256');p['proposal_sha256']=digest(p)
        (self.base/'proposal.json').write_text(json.dumps(p),encoding='utf-8')
        with patch.object(m,'resources',side_effect=AssertionError('No GPU before approval')):
            with self.assertRaises(PermissionError):
                m.run_package(REPO_ROOT,self.base/'proposal.json',self.base/'private.json',self.base/'approval.json','b'*40)
        self.assertFalse(Path(self.private['output_root']).exists())

    def test_seeded_common_initialization_and_orders_change_across_seed(self):
        common=[];orders=[]
        for seed in (2030,2031):
            with patch.dict(os.environ,PYTHONHASHSEED=str(seed),CUBLAS_WORKSPACE_CONFIG=':4096:8'):
                models=engine.paired_models(seed,REPO_ROOT)
                a=state_digest(dict(backbone=models['B3'].backbone.state_dict(),heads=models['B3'].heads.state_dict()))
                b=state_digest(dict(backbone=models['B4'].backbone.state_dict(),heads=models['B4'].heads.state_dict()))
                self.assertEqual(a,b);common.append(a)
                ids=tuple(f'synthetic_{i}' for i in range(959))
                order=engine.epoch_order(ids,seed,1)
                self.assertEqual(order,engine.epoch_order(ids,seed,1));orders.append(order)
        self.assertNotEqual(common[0],common[1]);self.assertNotEqual(orders[0],orders[1])
        # Inherited seed+epoch-1 ordering intentionally remains unchanged.
        self.assertEqual(orders[1],engine.epoch_order(ids,2030,2))

    def test_single_arm_uses_existing_engine_and_deadline_before_update(self):
        decision=engine.FormalDecision('SYNTHETIC_ONLY',2030,m.POPULATION_SHA,True,True,True)
        with patch.object(engine,'resources',side_effect=AssertionError('Deadline must precede GPU')):
            with self.assertRaisesRegex(RuntimeError,'synthetic deadline'):
                engine.PairedExecutor(None,self.base/'never',decision=decision,kinds=('B4',),
                    deadline=lambda: (_ for _ in ()).throw(RuntimeError('synthetic deadline'))).run(None)
        self.assertFalse((self.base/'never').exists())
        with self.assertRaises(PermissionError):
            engine.PairedExecutor(None,self.base/'never',decision=decision,kinds=('B2',)).run(None)

    def test_single_arm_full_engine_loop_with_tiny_cpu_fixture(self):
        class Toy(torch.nn.Module):
            def __init__(self):
                super().__init__();self.kind='B4'
                self.backbone=torch.nn.Linear(1,1);self.heads=torch.nn.Linear(1,1)
            def cuda(self):return self
        a=Toy();b=copy.deepcopy(a)
        train=('2023-05-01T05:30:00+00:00',);dev=('2024-05-01T05:30:00+00:00',)
        plan=SimpleNamespace(root=REPO_ROOT,strong_scene_ids=(),identity={'synthetic':True},
             ids=lambda role:train if role=='Train' else dev,
             rows={'Development':{dev[0]:{'analysis_time':'2024-05-01T06:00:00+00:00'}}})
        class Reader:
            def batch(self,role,ids):
                batch=SimpleNamespace(identity=plan.identity,role=role,ids=ids)
                batch.to=lambda device:batch;return batch
            def close(self):pass
        class Evaluator:
            def __init__(self,*args,**kwargs):pass
            def add(self,*args):pass
            def finish(self):return {'synthetic_only':True}
            def close(self):pass
        def forward(model,batch):
            value=sum(p.square().sum() for p in model.parameters())
            return None,SimpleNamespace(training_objective=value,n_valid=3430,n_rain=1,s_occ=value,s_qr=value*0)
        decision=engine.FormalDecision('SYNTHETIC_CPU_FIXTURE_ONLY',2030,m.POPULATION_SHA,True,True,True)
        with contextlib.ExitStack() as stack:
            for name,value in dict(TRAIN_N=1,DEV_N=1,EPOCHS=1,STEPS=1).items():stack.enter_context(patch.object(engine,name,value))
            for name,value in dict(resources=lambda **kw:{},paired_models=lambda *args:{'B3':a,'B4':b},
                new_adamw=lambda model:(torch.optim.AdamW(model.parameters(),lr=1e-4),{}),
                forward=forward,Evaluation=Evaluator).items():stack.enter_context(patch.object(engine,name,value))
            stack.enter_context(patch.object(torch,'autocast',lambda *a,**k:contextlib.nullcontext()))
            stack.enter_context(patch.object(torch.cuda,'get_rng_state_all',return_value=[]))
            stack.enter_context(patch.object(torch.cuda,'empty_cache'))
            result=engine.PairedExecutor(plan,self.base/'toy',decision=decision,kinds=('B4',),code_commit='b'*40).run(lambda *a:Reader())
        self.assertEqual(result['updates'],1)
        self.assertFalse((self.base/'toy'/'B3_train_01.json').exists())
        self.assertEqual(json.loads((self.base/'toy'/'B4_LAST_epoch_01.receipt.json').read_text(encoding='utf-8'))['code_commit'],'b'*40)

    def test_b4_pair_mismatch_stops_before_optimizer(self):
        class Toy(torch.nn.Module):
            def __init__(self):
                super().__init__();self.backbone=torch.nn.Linear(1,1);self.heads=torch.nn.Linear(1,1)
        a=Toy();b=copy.deepcopy(a)
        ref=self.base/'reference';ref.mkdir()
        for name in ('paired_initial_identity.json','paired_orders.json'):m.write(ref/name,{'different':True})
        ids=tuple(f'synthetic_{i}' for i in range(959))
        plan=SimpleNamespace(root=REPO_ROOT,strong_scene_ids=(),identity={},ids=lambda role:ids if role=='Train' else tuple(range(963)))
        decision=engine.FormalDecision('SYNTHETIC_ONLY',2030,m.POPULATION_SHA,True,True,True)
        with patch.object(engine,'resources'),patch.object(engine,'paired_models',return_value={'B3':a,'B4':b}),\
             patch.object(engine,'new_adamw',side_effect=AssertionError('No optimizer before pair check')):
            with self.assertRaisesRegex(RuntimeError,'differs from its completed B3 pair'):
                engine.PairedExecutor(plan,self.base/'mismatched',decision=decision,kinds=('B4',),pair_reference=ref).run(None)

    def test_additive_tail_matches_existing_evaluator_on_same_batch(self):
        ids=('2024-05-01T05:30:00+00:00',)
        rate=torch.tensor([[[[0.,.2,25.,40.]]]])
        mask=torch.ones_like(rate,dtype=torch.bool)
        q=torch.linspace(.1,4.,32,dtype=torch.float64)[None,:,None,None].expand(1,32,1,4)
        out=SimpleNamespace(rain_logit=torch.zeros_like(rate),rain_prob=torch.full_like(rate,.5),conditional_quantiles_log=q)
        batch=SimpleNamespace(role='Development',ids=ids,analyses=('2024-05-01T06:00:00+00:00',),
                              rate=rate,valid=mask,region=mask)
        ev=Evaluation(ids,batch.analyses,{'synthetic':True},self.base/'evaluation')
        tail=m.BatchTail()
        try:
            ev.add(out,batch);tail.add_batch(out,batch);report=ev.finish()
            result=tail.finish_checked(report,ids)
        finally:ev.close()
        self.assertEqual(sum(r['n_rain'] for r in result['strata']),3)
        changed=copy.deepcopy(report);changed['groups']['all']['summary']['n_rain']+=1
        with self.assertRaises(RuntimeError):tail.finish_checked(changed,ids)

    def test_three_seed_summary_uses_sample_sd_and_all_seeds(self):
        pairs={s:dict(brier=v,auroc=-v,q32_coverage=-v) for s,v in zip((2029,2030,2031),(-1.,0.,1.))}
        r=m.aggregate_pairs(pairs)
        self.assertEqual(r['metrics']['brier']['mean'],0.)
        self.assertEqual(r['metrics']['brier']['sample_sd'],1.)
        self.assertEqual(len(r['metrics']['brier']['B4_minus_B3_by_seed']),3)
        with self.assertRaises(ValueError):m.aggregate_pairs({2030:pairs[2030]})

    def test_endpoint_requires_all_nine_seals_and_exact_budget(self):
        folder=self.base/'endpoint';folder.mkdir()
        db=sqlite3.connect(folder/'updates.sqlite')
        db.execute('CREATE TABLE updates(model TEXT,u INTEGER,state TEXT)')
        db.executemany('INSERT INTO updates VALUES (?,?,?)',[('B4',i,'RETURNED') for i in range(1,4321)])
        db.commit();db.close()
        for e in range(1,10):
            checkpoint=folder/f'B4_LAST_epoch_{e:02d}.pt';checkpoint.write_bytes(b'SYNTHETIC_NOT_A_TORCH_WEIGHT')
            dev=dict(synthetic=True)
            receipt=dict(model='B4',epoch=e,updates=e*480,code_commit='b'*40,
                         population_sha256=m.POPULATION_SHA,validation_receipt_sha256=digest(dev),checkpoint_sha256=sha(checkpoint))
            for name,value in [(f'B4_train_{e:02d}.json',dict(updates=e*480)),
                               (f'B4_development_{e:02d}.json',dev),(f'B4_tail_{e:02d}.json',{}),
                               (f'B4_LAST_epoch_{e:02d}.receipt.json',receipt)]:m.write(folder/name,value)
            for role,files,bytes_ in [('train',7918,26424262556),('dev',7950,26639253112)]:
                d=folder/f'B4_{role}_reads_{e:02d}';d.mkdir()
                m.write(d/'pass_receipt.json',dict(during_failure=False,expected_files=files,expected_bytes=bytes_,
                      actual_reads=dict(opened_files=files,delivered_bytes=bytes_,states={'READ_COMPLETE':files})))
        self.assertEqual(m.endpoint(folder,'B4',2030,'b'*40)['status'],'COMPLETE_TRAIN_AND_DEV_EVALUATION')
        (folder/'B4_LAST_epoch_09.pt').write_bytes(b'CHANGED')
        with self.assertRaises(RuntimeError):m.endpoint(folder,'B4',2030,'b'*40)

    def controller_fixture(self,fail_at=None,timeout_at=None):
        calls=[];parent=self;package=Path(self.private['output_root'])
        def report(kind):
            return dict(source_identity={},population_ids_sha256='x',partition_sha256='y',groups={
                'all':dict(ids_sha='z',summary=dict(n_valid=10,brier=.1,auroc=.8,average_precision=.5,
                    conditional_pinball=.2,q32_signed_bias=-.08,core_fp64=.1,coverage=[.9]*32,rain_strata=[]))})
        old=Path(self.private['historical_pair']);old.mkdir()
        for k in ('B3','B4'):m.write(old/f'{k}_development_09.json',report(k))
        class Process:
            def __init__(self,command,**kw):
                index=int(command[-1]);calls.append((m.TASKS[index],kw['env']['PYTHONHASHSEED']))
                self.index=index;self.killed=False
            def wait(self,timeout=None):
                if self.index==timeout_at and not self.killed:raise subprocess.TimeoutExpired('synthetic',timeout)
                if self.killed:return -9
                if self.index==fail_at:return 7
                kind,seed=m.TASKS[self.index];f=package/f'{kind}_s{seed}';f.mkdir()
                m.write(f/'completion.json',dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',code_commit='b'*40,
                    optimizer_updates=4320,logical_source_bytes=m.BUDGET['source_bytes_per_model']))
                m.write(f/'paired_initial_identity.json',{'same_within_seed':seed})
                m.write(f/'paired_orders.json',{'same_within_seed':seed})
                m.write(f/f'{kind}_development_09.json',report(kind))
                return 0
            def poll(self):return -9 if self.killed else None
            def kill(self):self.killed=True
        with patch.object(m,'checked_inputs',return_value=(self.proposal,self.private,self.approval,{})),\
             patch.object(m,'resources',return_value={}),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=100*m.GIB)),\
             patch.object(m.subprocess,'Popen',Process):
            if fail_at is None and timeout_at is None:
                r=m.run_package(REPO_ROOT,'p','q','a','b'*40)
                self.assertEqual(r['optimizer_updates'],17280)
                with self.assertRaises(PermissionError):m.run_package(REPO_ROOT,'p','q','a','b'*40)
            else:
                with self.assertRaises(RuntimeError):m.run_package(REPO_ROOT,'p','q','a','b'*40)
                self.assertTrue((package/'failure.json').exists());self.assertFalse((package/'completion.json').exists())
        return calls

    def test_serial_order_no_duplicate_run(self):
        calls=self.controller_fixture()
        self.assertEqual([a for a,b in calls],list(m.TASKS))
        self.assertEqual([b for a,b in calls],['2030','2030','2031','2031'])

    def test_failure_stops_dependent_tasks_without_replay(self):
        calls=self.controller_fixture(fail_at=1)
        self.assertEqual(len(calls),2)

    def test_hard_time_cap_kills_worker_without_replay(self):
        calls=self.controller_fixture(timeout_at=0)
        self.assertEqual(len(calls),1)

    @unittest.skipUnless(os.name=='nt','Windows console isolation only')
    def test_actual_worker_creation_has_no_console(self):
        result=subprocess.check_output([sys._base_executable,'-B','-c',
            'import ctypes,json; k=ctypes.WinDLL("kernel32",use_last_error=True); k.GetConsoleWindow.restype=ctypes.c_void_p; print(json.dumps({"console_window":k.GetConsoleWindow()}))'],
            creationflags=m.worker_creation_flags(),text=True)
        self.assertIsNone(json.loads(result)['console_window'])


if __name__=='__main__':unittest.main()
