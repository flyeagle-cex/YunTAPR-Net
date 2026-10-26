"""Recovery changes only: synthetic checkpoints/metadata, no optimizer updates."""
import copy,json,os,sqlite3,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import torch
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.experimental.core_innovation.stage4.engine import PairedExecutor,FormalDecision
from yuntapr.experimental.research_readiness import multiseed_recovery as r


class RecoveryPreparationTests(unittest.TestCase):
    def setUp(self):
        self.folder=REPO_ROOT/'tests/research_readiness/.local'/('recovery_'+uuid.uuid4().hex)
        self.folder.mkdir(parents=True)
        self.prior=dict(returned_updates=5190,reserved_source_bytes=552318045013,source_files=165179)
        self.caps=r.budget(self.prior,3332713,14498,2016)

    def test_exact_recovery_and_cumulative_arithmetic(self):
        self.assertEqual(self.caps['new_updates'],12480)
        self.assertEqual(self.caps['cumulative_updates'],17670)
        self.assertEqual(self.caps['new_source_bytes'],1379654740081)
        self.assertEqual(self.caps['cumulative_source_bytes'],1931972785094)
        self.assertEqual(self.caps['new_source_files'],412569)
        self.assertEqual(self.caps['cumulative_source_files'],577748)
        self.assertEqual(self.caps['task_wall_seconds'],[19584,21600,21600])
        self.assertEqual(self.caps['max_wall_seconds'],62784)
        with self.assertRaises(ValueError):r.budget(dict(self.prior,returned_updates=5191),3332713,14498,2016)

    def test_consumed_or_incomplete_approval_rejected_before_read_or_gpu(self):
        p=dict(proposal_sha256='a'*64,tasks=[dict(model=k,seed=s) for k,s in r.TASKS],budget=self.caps,checkpoint={'sha256':'c'*64})
        v=dict(output_root='SYNTHETIC_NEW_OUTPUT')
        a=dict(approved_by_researcher=True,code_commit='b'*40,proposal_sha256='a'*64,tasks=p['tasks'],budget=self.caps,
               output_root=v['output_root'],approved_checkpoint_sha256='c'*64,approved_replay_updates=390,decision_id='SYNTHETIC_VALIDATOR_ONLY')
        r.validate_approval(a,p,v,'b'*40)
        for key,value in [('approved_by_researcher',False),('approved_replay_updates',0),('approved_checkpoint_sha256','d'*64),('code_commit','d'*40)]:
            x=dict(a);x[key]=value
            with self.assertRaises(PermissionError):r.validate_approval(x,p,v,'b'*40)

    def test_B4_offset_ledger_no_overwrite_uncertainty_or_extra_update(self):
        q=self.folder/'updates.sqlite';l=r.RecoveryLedger(q,{'synthetic_only':True},offsets={'B4':480},segment_cap=3840,prior_updates=870,cumulative_cap=4710)
        try:
            with self.assertRaises(PermissionError):l.reserve('B4',1)
            with self.assertRaises(PermissionError):l.reserve('B3',481)
            l.reserve('B4',481)
            with self.assertRaises(PermissionError):l.reserve('B4',482)
            l.returned('B4',481)
            with l.db:l.db.executemany('INSERT INTO updates VALUES (?,?,?)',[('B4',u,'RETURNED') for u in range(482,4321)])
            self.assertEqual(l.db.execute('SELECT COUNT(*) FROM updates WHERE u<=870').fetchone()[0],390)
            with self.assertRaises(PermissionError):l.reserve('B4',4321)
        finally:l.close()
        with self.assertRaises(PermissionError):r.RecoveryLedger(q,{},offsets={'B4':480})

    def test_B4_model_optimizer_scheduler_and_rng_restore_without_step(self):
        import random
        model=torch.nn.Linear(2,1);opt=torch.optim.AdamW(model.parameters(),lr=1e-4,foreach=False)
        for param in model.parameters():opt.state[param]=dict(step=torch.tensor(480.),exp_avg=torch.full_like(param,.2),exp_avg_sq=torch.full_like(param,.3))
        rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch_cpu=torch.get_rng_state(),torch_cuda=[])
        payload=dict(identity=dict(data={'synthetic':True},model='B4',decision={'seed':2030}),optimizer_groups={'synthetic':True},
            epoch=1,updates=480,scheduler=dict(completed=480,steps_per_epoch=480,original_horizon=24000),model=model.state_dict(),optimizer=opt.state_dict(),rng=rng)
        q=self.folder/'B4_LAST_epoch_01.pt';torch.save(payload,q)
        report={'synthetic':True};r.write(self.folder/'B4_development_01.json',report)
        r.write(self.folder/'B4_LAST_epoch_01.receipt.json',{'validation_receipt_sha256':r.digest(report)})
        state=r.B4Resume(dict(parent=str(self.folder),data_identity={'synthetic':True},checkpoint_sha256=r.sha(q),decision_id='SYNTHETIC'))
        new=torch.nn.Linear(2,1);newopt=torch.optim.AdamW(new.parameters(),lr=1e-4,foreach=False)
        with patch('torch.cuda.set_rng_state_all') as cuda,patch.object(newopt,'step',side_effect=AssertionError('No update')):
            u,reports=state.restore('B4',new,newopt,{'synthetic':True})
        self.assertEqual((u,len(reports)),(480,1));self.assertEqual(state_digest(model.state_dict()),state_digest(new.state_dict()))
        self.assertEqual(state_digest(opt.state_dict()),state_digest(newopt.state_dict()));self.assertTrue(torch.equal(torch.get_rng_state(),rng['torch_cpu']))
        cuda.assert_called_once_with([])
        state.request['checkpoint_sha256']='f'*64
        with patch('torch.load',side_effect=AssertionError('No changed checkpoint load')):
            with self.assertRaises(ValueError):state.restore('B4',new,newopt,{'synthetic':True})

    def test_single_B4_recovery_hook_accepted_before_resources(self):
        state=r.B4Resume(dict(parent=str(self.folder),data_identity={},decision_id='SYNTHETIC'))
        plan=SimpleNamespace(identity={},strong_scene_ids=())
        decision=FormalDecision('SYNTHETIC',2030,r.POPULATION_SHA,True,True,True)
        with patch('yuntapr.experimental.core_innovation.stage4.engine.resources',side_effect=RuntimeError('STOP_BEFORE_GPU')):
            with self.assertRaisesRegex(RuntimeError,'STOP_BEFORE_GPU'):
                PairedExecutor(plan,self.folder/'never',decision=decision,kinds=('B4',),recovery=state).run(None)
        self.assertFalse((self.folder/'never').exists())

    def test_worker_inherits_E1_and_never_reopens_it(self):
        old=self.folder/'old';package=self.folder/'new';old.mkdir();package.mkdir()
        a={'decision_id':'SYNTHETIC_ONLY'};p=dict(proposal_sha256='a'*64,budget=self.caps,data={},checkpoint={'sha256':'c'*64})
        v=dict(parent=str(old),output_root=str(package),source={'synthetic':True})
        r.write(package/'authorization_binding.json',dict(controller_pid=os.getppid(),approval=a))
        r.write(package/'task_1_claim.json',dict(index=0,controller_pid=os.getppid(),code_commit='b'*40))
        test=self
        class Executor:
            def __init__(self,plan,folder,**kw):
                self.folder=folder;test.assertEqual(kw['kinds'],('B4',));test.assertEqual(kw['recovery'].completed_epochs('B4'),1)
                test.assertEqual(kw['pair_reference'],old/'B3_s2030')
            def run(self,factory):
                self.folder.mkdir()
                with test.assertRaises(PermissionError):factory('Train',1,(),self.folder/'B4_train_reads_01')
        with patch.object(r,'checked',return_value=(p,v,a,dict(private_inputs={'stage3_run':'synthetic','request':'synthetic'}))),\
             patch.object(r.shutil,'disk_usage',return_value=SimpleNamespace(free=100*r.GIB)),\
             patch.object(r,'verify_source',return_value={}) as verification,patch.object(r,'PopulationPlan',return_value=SimpleNamespace(identity={})),\
             patch.object(r,'PairedExecutor',Executor),patch.object(r,'endpoint',return_value={'status':'SYNTHETIC_ONLY'}),patch.dict(os.environ,PYTHONHASHSEED='2030'):
            result=r.run_worker(REPO_ROOT,'p','v','a','b'*40,0)
        self.assertEqual(result['segment_updates'],3840)
        self.assertEqual(result['cumulative_attempt_updates'],4710)
        self.assertEqual(result['cumulative_actual_source_bytes'],499257862058);verification.assert_called_once()

    def test_composed_endpoint_preserves_original_E1_commit(self):
        old=self.folder/'E1';new=self.folder/'E2_E9';old.mkdir();new.mkdir()
        db=sqlite3.connect(new/'updates.sqlite');db.execute('CREATE TABLE updates(model TEXT,u INTEGER,state TEXT)')
        db.executemany('INSERT INTO updates VALUES (?,?,?)',[('B4',u,'RETURNED') for u in range(481,4321)]);db.commit();db.close()
        for e in range(1,10):
            source=old if e==1 else new;q=source/f'B4_LAST_epoch_{e:02d}.pt';q.write_bytes(b'SYNTHETIC_METADATA_NOT_TORCH_WEIGHT')
            dev={'synthetic':True};receipt=dict(model='B4',epoch=e,updates=480*e,code_commit=r.PARENT_COMMIT if e==1 else 'b'*40,
                validation_receipt_sha256=r.digest(dev),checkpoint_sha256=r.sha(q),population_sha256=r.POPULATION_SHA)
            for name,value in [(f'B4_train_{e:02d}.json',{'updates':480*e}),(f'B4_development_{e:02d}.json',dev),
                (f'B4_LAST_epoch_{e:02d}.receipt.json',receipt),(f'B4_tail_{e:02d}.json',{})]:r.write(source/name,value)
            for role,n,b in [('train',7918,26424262556),('dev',7950,26639253112)]:
                d=source/f'B4_{role}_reads_{e:02d}';d.mkdir();r.write(d/'pass_receipt.json',dict(during_failure=False,expected_files=n,expected_bytes=b,
                    actual_reads=dict(opened_files=n,delivered_bytes=b,states={'READ_COMPLETE':n})))
        result=r.endpoint(new,'B4',2030,'b'*40,inherited=old,inherited_commit=r.PARENT_COMMIT)
        self.assertEqual(result['status'],'COMPLETE_TRAIN_AND_DEV_EVALUATION')
        self.assertEqual(result['checkpoints'][0]['code_commit'],r.PARENT_COMMIT)
        self.assertFalse((new/'B4_train_01.json').exists())

    def controller(self,fail=False):
        package=self.folder/'package';p=dict(budget=self.caps);v=dict(output_root=str(package),parent=str(self.folder/'old'),historical_pair='synthetic');calls=[];test=self
        class Process:
            def __init__(self,command,**kw):
                self.i=int(command[-1]);calls.append(r.TASKS[self.i]);test.assertEqual(kw['creationflags'],r.worker_creation_flags())
            def wait(self,timeout=None):
                if fail:return 2
                k,s=r.TASKS[self.i];d=package/f'{k}_s{s}';d.mkdir()
                r.write(d/'completion.json',dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',code_commit='b'*40,segment_updates=self.caps['new_task_updates'][self.i],
                    segment_source_files=(8 if self.i==0 else 9)*15868,segment_source_bytes=(8 if self.i==0 else 9)*53063515668))
                if self.i==0:
                    q=package/'interrupted_source_verification';q.mkdir();r.write(q/'source_verification_receipt.json',dict(states={'READ_COMPLETE':1},delivered_bytes=3332713))
                return 0
            @property
            def caps(self):return test.caps
            def poll(self):return 0
        with patch.object(r,'checked',return_value=(p,v,{'synthetic':True},{})),patch.object(r,'resources',return_value={}),\
             patch.object(r.shutil,'disk_usage',return_value=SimpleNamespace(free=100*r.GIB)),patch.object(r.subprocess,'Popen',Process),patch.object(r,'summarize'):
            if fail:
                with self.assertRaises(RuntimeError):r.execute(REPO_ROOT,'p','v','a','b'*40)
            else:self.assertEqual(r.execute(REPO_ROOT,'p','v','a','b'*40)['cumulative_updates'],17670)
        return calls

    def test_recovery_then_seed2031_serial_order_and_exact_closure(self):
        self.assertEqual(self.controller(),list(r.TASKS))

    def test_failed_recovery_never_starts_seed2031(self):
        self.assertEqual(self.controller(fail=True),[('B4',2030)])


if __name__=='__main__':unittest.main()
