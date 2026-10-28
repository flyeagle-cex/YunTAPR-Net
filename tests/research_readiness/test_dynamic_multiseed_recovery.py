"""Only new B7/2030 recovery wiring/caps; all receipts below are CPU fixtures."""
import copy,json,os,random,sqlite3,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import torch
from yuntapr.training.phase_a_protocol import state_digest,lr_for_update
from yuntapr.experimental.research_readiness import dynamic_multiseed_recovery as r

ROOT=Path(__file__).resolve().parents[2]


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
        self.stop=r.read(ROOT/r.STOP);self.launch=r.read(ROOT/r.LAUNCH)
        self.prepared=dict(roles={'Train':dict(bytes_per_pass=26424262556,file_count=7918),'Development':dict(bytes_per_pass=26639253112,file_count=7950)})
        self.caps=r.budget(self.prepared,self.stop,self.launch,123)
    def objects(self):
        p=dict(execution_code_commit='c'*40,proposal_sha256='p'*64,tasks=[dict(model=k,seed=s) for k,s in r.TASKS],budget=self.caps,scientific_choices={},checkpoint={'sha256':'w'*64})
        v=dict(output_root=str(self.folder/'new'),parent=str(self.folder/'old'));a=dict(approved_by_researcher=True,code_commit='c'*40,proposal_sha256=p['proposal_sha256'],tasks=p['tasks'],budget=p['budget'],scientific_choices={},output_root=v['output_root'],approved_checkpoint_sha256='w'*64,approved_replay_updates=441,decision_id='SYNTHETIC_ONLY_NOT_HUMAN_APPROVAL')
        return p,v,a
    def state(self):return r.B7Resume(dict(parent=str(self.folder),data_identity={},decision_id='SYNTHETIC_ONLY',prior_updates=3321,replayed_updates=441))
    def test_exact_441_replay_and_no_extra_time_or_source_scope(self):
        c=self.caps
        self.assertEqual(c['new_task_updates'],[1440,4320,4320,4320]);self.assertEqual(c['total_updates'],14400);self.assertEqual(c['cumulative_updates'],17721)
        self.assertEqual(c['replay_allowance'],441);self.assertEqual(c['cumulative_B7_attempts'],4761)
        self.assertEqual((c['total_source_bytes'],c['total_source_files']),(1591906721352,476044))
        self.assertEqual((c['cumulative_source_bytes'],c['cumulative_source_files']),(1934666227950,578566))
        self.assertEqual(c['task_wall_seconds'][0]+c['prior_wall_seconds_ceil'],21600)
        self.assertEqual(c['max_package_seconds']+c['prior_wall_seconds_ceil'],86400)
        wrong=copy.deepcopy(self.prepared);wrong['roles']['Train']['file_count']+=1
        with self.assertRaises(ValueError):r.budget(wrong,self.stop,self.launch,123)
    def test_old_or_incomplete_grant_is_rejected(self):
        p,v,a=self.objects();r.validate_approval(a,p,v,'c'*40)
        for key,value in [('approved_replay_updates',0),('approved_replay_updates',62),('approved_checkpoint_sha256','x'*64),('code_commit','d'*40),('approved_by_researcher',False)]:
            with self.assertRaises(PermissionError):r.validate_approval(dict(a,**{key:value}),p,v,'c'*40)
    def test_original_coupled_host_stops_before_input_checks(self):
        with patch.object(r,'independent_admission',side_effect=PermissionError('COUPLED')),patch.object(r,'checked') as checked:
            with self.assertRaises(PermissionError):r.execute(ROOT,'p','v','a','c'*40)
            checked.assert_not_called()
    def test_B7_ledger_starts2881_accounts441_and_never_reuses_or_overruns(self):
        state=self.state();db=state.ledger(self.folder/'updates.sqlite',{})
        try:
            with self.assertRaises(PermissionError):db.reserve('B8',2881)
            with self.assertRaises(PermissionError):db.reserve('B7',3322)
            db.reserve('B7',2881)
            with self.assertRaises(PermissionError):db.reserve('B7',2882)
            db.returned('B7',2881)
            with db.db:db.db.executemany('INSERT INTO updates VALUES (?,?,?)',[('B7',u,'RETURNED') for u in range(2882,4321)])
            self.assertEqual(db.db.execute('SELECT COUNT(*) FROM updates WHERE u<=3321').fetchone()[0],441)
            with self.assertRaises(PermissionError):db.reserve('B7',4321)
        finally:db.close()
        with self.assertRaises(PermissionError):state.ledger(self.folder/'updates.sqlite',{})
    def test_B7_2030_restores_model_AdamW_LR_all_RNG_without_update(self):
        model=torch.nn.Linear(2,1);opt=torch.optim.AdamW(model.parameters(),lr=lr_for_update(2880,steps_per_epoch=480),foreach=False)
        for p in model.parameters():opt.state[p]=dict(step=torch.tensor(2880.),exp_avg=torch.full_like(p,.2),exp_avg_sq=torch.full_like(p,.3))
        rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch_cpu=torch.get_rng_state(),torch_cuda=[torch.tensor([1,2],dtype=torch.uint8)])
        payload=dict(identity=dict(data={},model='B7',decision={'seed':2030}),epoch=6,updates=2880,scheduler=dict(completed=2880,steps_per_epoch=480,original_horizon=24000),optimizer_groups={},model=model.state_dict(),optimizer=opt.state_dict(),rng=rng)
        weight=self.folder/'B7_LAST_epoch_06.pt';torch.save(payload,weight)
        for e in range(1,7):r.write(self.folder/f'B7_development_{e:02d}.json',{'fixture_epoch':e})
        state=self.state();state.request['checkpoint_sha256']=r.sha(weight)
        new=torch.nn.Linear(2,1);newopt=torch.optim.AdamW(new.parameters(),lr=9.,foreach=False)
        with patch('torch.cuda.set_rng_state_all') as cuda,patch.object(newopt,'step',side_effect=AssertionError('NO_UPDATE')):
            u,reports=state.restore('B7',new,newopt,{})
        self.assertEqual((u,len(reports)),(2880,6));self.assertEqual(state_digest(model.state_dict()),state_digest(new.state_dict()));self.assertEqual(state_digest(opt.state_dict()),state_digest(newopt.state_dict()))
        self.assertEqual(random.getstate(),rng['python']);self.assertTrue(np.array_equal(np.random.get_state()[1],rng['numpy'][1]));self.assertTrue(torch.equal(torch.get_rng_state(),rng['torch_cpu']));self.assertTrue(torch.equal(cuda.call_args.args[0][0],rng['torch_cuda'][0]))
        self.assertNotEqual(lr_for_update(u+1,steps_per_epoch=480),lr_for_update(1,steps_per_epoch=480))
        with self.assertRaises(PermissionError):state.restore('B8',new,newopt,{})
    def test_remaining_reader_cannot_revisit_E1_E6_or_wrong_model(self):
        with patch.object(r.ReaderFactory,'__call__',return_value='SYNTHETIC') as base:
            reader=object.__new__(r.RemainingReaders)
            for kind,e in [('B7',6),('B8',7),('B7',10)]:
                with self.assertRaises(PermissionError):reader('Train',e,(),self.folder/f'{kind}_train_reads_{e:02d}')
            self.assertEqual(reader('Train',7,(),self.folder/'B7_train_reads_07'),'SYNTHETIC');base.assert_called_once()
    def test_failure_does_not_start_later_tasks_or_retry(self):
        p,v,a=self.objects();calls=[]
        class Failed:
            def __init__(inner,cmd,**kw):calls.append((cmd,kw))
            def wait(inner,timeout):return 2
            def poll(inner):return 2
        with patch.object(r,'independent_admission'),patch.object(r,'checked',return_value=(p,v,a,self.prepared,{})),patch.object(r,'resources',return_value={}),patch.object(r.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)),patch.object(r.original,'admit_source'),patch.object(r.subprocess,'Popen',Failed):
            with self.assertRaises(RuntimeError):r.execute(ROOT,'p','v','a','c'*40)
            with self.assertRaises(PermissionError):r.execute(ROOT,'p','v','a','c'*40)
        self.assertEqual(len(calls),1);self.assertFalse((Path(v['output_root'])/'task_2_claim.json').exists())
        self.assertIn('SEE_PRESERVED',r.read(Path(v['output_root'])/'failure.json')['partial_task_counts'])
    def test_controller_closes_exact_four_tasks_and_three_seed_summary(self):
        p,v,a=self.objects();calls=[]
        class Done:
            def __init__(inner,cmd,**kw):
                i=int(cmd[-1]);kind,seed=r.TASKS[i];calls.append((kind,seed,kw['env']['PYTHONHASHSEED'],kw['creationflags']))
                folder=Path(v['output_root'])/f'{kind}_s{seed}';folder.mkdir()
                result=dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',model=kind,seed=seed,optimizer_updates=4320,code_commit='c'*40,segment_updates=p['budget']['new_task_updates'][i],segment_source_bytes=p['budget']['new_source_bytes_per_task'][i],segment_source_files=p['budget']['new_source_files_per_task'][i])
                r.write(folder/('completion.json' if i==0 else 'segment_completion.json'),result)
                for name in ('paired_initial_identity.json','paired_orders.json'):r.write(folder/name,{'SYNTHETIC_SEED':seed})
                r.write(folder/f'{kind}_development_09.json',{'SYNTHETIC_ONLY':True})
            def wait(inner,timeout):return 0
            def poll(inner):return 0
        with patch.object(r,'independent_admission'),patch.object(r,'checked',return_value=(p,v,a,self.prepared,{})),patch.object(r,'resources',return_value={}),patch.object(r.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)),patch.object(r.original,'admit_source'),patch.object(r.subprocess,'Popen',Done),patch.object(r,'paired_difference',return_value={'SYNTHETIC':True}),patch.object(r.original,'summarize') as summary:
            result=r.execute(ROOT,'p','v','a','c'*40)
        self.assertEqual([x[:2] for x in calls],list(r.TASKS));self.assertEqual([x[2] for x in calls],['2030','2030','2031','2031']);self.assertTrue(all(x[3]==r.worker_creation_flags() for x in calls));summary.assert_called_once()
        self.assertEqual((result['segment_updates'],result['cumulative_updates'],result['replay']),(14400,17721,441))
    def test_new_B7_three_epoch_seals_inherit_six_without_old_weight_access(self):
        p,_,_=self.objects();p.update(data={'population_sha256':'fixture'},inherited_checkpoints=[{'epoch':e,'code_commit':r.PARENT_COMMIT} for e in range(1,7)])
        folder=self.folder/'new';folder.mkdir();db=sqlite3.connect(folder/'updates.sqlite');db.execute('CREATE TABLE updates(model TEXT,u INTEGER,state TEXT)');db.executemany('INSERT INTO updates VALUES (?,?,?)',[('B7',u,'RETURNED') for u in range(2881,4321)]);db.commit();db.close()
        for e in (7,8,9):
            weight=folder/f'B7_LAST_epoch_{e:02d}.pt';weight.write_bytes(b'SYNTHETIC_WEIGHT_ONLY')
            dev={'SYNTHETIC_EPOCH':e};seal=dict(model='B7',epoch=e,updates=e*480,code_commit='c'*40,population_sha256='fixture',validation_receipt_sha256=r.digest(dev),checkpoint_sha256=r.sha(weight))
            for name,obj in [(f'B7_train_{e:02d}.json',{'updates':e*480}),(f'B7_development_{e:02d}.json',dev),(f'B7_tail_{e:02d}.json',{}),(f'B7_LAST_epoch_{e:02d}.receipt.json',seal)]:r.write(folder/name,obj)
            for role,n,b in [('train',7918,26424262556),('dev',7950,26639253112)]:
                d=folder/f'B7_{role}_reads_{e:02d}';d.mkdir();r.write(d/'pass_receipt.json',dict(during_failure=False,expected_bytes=b,expected_files=n,actual_reads=dict(delivered_bytes=b,opened_files=n,states={'READ_COMPLETE':n})))
        result=r.close_b7(folder,p,'c'*40)
        self.assertEqual(len(result['checkpoints']),9);self.assertEqual(result['inherited_epochs'],6);self.assertEqual(result['replay_updates'],441);self.assertEqual(result['segment_source_bytes'],159190859832)
    def test_untouched_workers_use_same_seed_B7_reference_and_frozen2031_reference(self):
        p,v,a=self.objects();out=Path(v['output_root']);out.mkdir();r.write(out/'authorization_binding.json',dict(controller_pid=os.getppid(),approval=a));inherited=dict(seed_references={'2031':str(self.folder/'frozen2031')})
        for index in (1,2,3):
            kind,seed=r.TASKS[index];r.write(out/f'task_{index+1}_claim.json',dict(index=index,controller_pid=os.getppid(),code_commit='c'*40));(out/f'{kind}_s{seed}').mkdir()
            with patch.object(r,'checked',return_value=(p,v,a,self.prepared,inherited)),patch.object(r.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)),patch.dict(os.environ,PYTHONHASHSEED=str(seed)),patch.object(r,'run_task',return_value=dict(total_logical_source_bytes=477571953840,total_logical_source_files=142813)) as run:
                result=r.worker(ROOT,'p','v','a','c'*40,index)
            self.assertEqual(run.call_args.args[6:8],(kind,seed))
            expected=out/f'B7_s{seed}' if kind=='B8' else self.folder/'frozen2031'
            self.assertEqual(run.call_args.kwargs['pair_reference'],expected);self.assertEqual(result['segment_updates'],4320)


if __name__=='__main__':unittest.main()
