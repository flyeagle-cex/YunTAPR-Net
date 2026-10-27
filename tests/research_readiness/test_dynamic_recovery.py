"""Only B8 recovery gates/state/read scope; CPU fixtures, no real optimizer step."""
import copy,json,os,random,sqlite3,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import torch
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.training.phase_a_protocol import state_digest,lr_for_update
from yuntapr.experimental.core_innovation.stage4.engine import FormalDecision,PairedExecutor
from yuntapr.experimental.research_readiness import dynamic_recovery as r

class DynamicRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.folder=REPO_ROOT/'tests/research_readiness/.local'/('B8_recovery_'+uuid.uuid4().hex);self.folder.mkdir(parents=True)
  self.prepared=dict(roles={'Train':dict(bytes_per_pass=26424262556,file_count=7918),'Development':dict(bytes_per_pass=26639253112,file_count=7950)})
  self.stop=dict(budget_closure=dict(returned_updates=7262,actual_source_bytes=799430612283,actual_source_files=239130),tasks=[{},dict(wall_seconds_mtime_proxy=13283.787945270538)])
  self.caps=r.budget(self.prepared,self.stop,dict(actual_payload_bytes=4096,actual_payload_files=1))
 def test_exact_62_replay_and_source_time_caps(self):
  self.assertEqual(self.caps['new_updates'],1440);self.assertEqual(self.caps['replayed_updates'],2942-2880)
  self.assertEqual(self.caps['cumulative_B8_attempts'],4382);self.assertEqual(self.caps['cumulative_package_attempts'],8702)
  self.assertEqual(self.caps['new_source_bytes'],159190859832);self.assertEqual(self.caps['new_source_files'],47605)
  self.assertEqual(self.caps['cumulative_source_bytes'],958621476211);self.assertEqual(self.caps['cumulative_source_files'],286736)
  self.assertEqual(self.caps['max_wall_seconds'],8316);self.assertEqual(self.caps['additional_retry_allowance'],0)
  wrong=copy.deepcopy(self.prepared);wrong['roles']['Train']['file_count']+=1
  with self.assertRaises(ValueError):r.budget(wrong,self.stop,dict(actual_payload_bytes=4096,actual_payload_files=1))
 def test_case_only_diagnostic_interpretation_never_reopens_source(self):
  d=dict(expected_bytes=123,checks=[dict(status='PASS',result={}) for _ in range(5)])
  d['checks'][1]['result']={'bytes':123};d['checks'][2]['result']=dict(same_path=True,same_basename=False)
  d['checks'][4]['result']=dict(stable_metadata=True,delivered_bytes=4096)
  self.assertTrue(r.diagnostic_access(d))
  d['checks'][2]['result']['same_path']=False;self.assertFalse(r.diagnostic_access(d))
 def proposal(self):
  p=dict(proposal_sha256='p'*64,tasks=[dict(model='B8',seed=2029)],budget=self.caps,checkpoint={'sha256':'s'*64})
  v=dict(output_root=str(self.folder/'new'),parent=str(self.folder/'old'));a=dict(approved_by_researcher=True,code_commit='c'*40,proposal_sha256=p['proposal_sha256'],tasks=p['tasks'],budget=p['budget'],output_root=v['output_root'],approved_checkpoint_sha256='s'*64,approved_replay_updates=62,decision_id='SYNTHETIC_ONLY')
  return p,v,a
 def test_missing_or_wrong_recovery_approval_stops_before_resources(self):
  p,v,a=self.proposal();r.validate_approval(a,p,v,'c'*40)
  for key,value in [('approved_by_researcher',False),('approved_replay_updates',0),('approved_checkpoint_sha256','t'*64),('code_commit','d'*40)]:
   with self.assertRaises(PermissionError):r.validate_approval(dict(a,**{key:value}),p,v,'c'*40)
  with patch.object(r,'checked',side_effect=PermissionError('No recovery grant')),patch.object(r,'resources',side_effect=AssertionError('No GPU')):
   with self.assertRaises(PermissionError):r.execute(REPO_ROOT,'p','v','a','c'*40)
 def state(self):return r.B8Resume(dict(parent=str(self.folder),decision_id='SYNTHETIC',data_identity={},prior_updates=2942,replayed_updates=62))
 def test_B8_offset_ledger_has_exact_replay_and_stops_on_uncertainty_cap_overwrite(self):
  state=self.state();ledger=state.ledger(self.folder/'updates.sqlite',{'synthetic':True})
  try:
   with self.assertRaises(PermissionError):ledger.reserve('B7',2881)
   with self.assertRaises(PermissionError):ledger.reserve('B8',2943)
   ledger.reserve('B8',2881)
   with self.assertRaises(PermissionError):ledger.reserve('B8',2882)
   ledger.returned('B8',2881)
   with ledger.db:ledger.db.executemany('INSERT INTO updates VALUES (?,?,?)',[('B8',u,'RETURNED') for u in range(2882,4321)])
   self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM updates WHERE u<=2942').fetchone()[0],62)
   with self.assertRaises(PermissionError):ledger.reserve('B8',4321)
  finally:ledger.close()
  with self.assertRaises(PermissionError):state.ledger(self.folder/'updates.sqlite',{})
 def test_B8_model_AdamW_all_RNG_and_LR_continue_without_step(self):
  model=torch.nn.Linear(2,1);opt=torch.optim.AdamW(model.parameters(),lr=lr_for_update(2880,steps_per_epoch=480),foreach=False)
  for param in model.parameters():opt.state[param]=dict(step=torch.tensor(2880.),exp_avg=torch.full_like(param,.2),exp_avg_sq=torch.full_like(param,.3))
  rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch_cpu=torch.get_rng_state(),torch_cuda=[torch.tensor([1,2,3],dtype=torch.uint8)])
  payload=dict(identity=dict(data={},model='B8',decision={'seed':2029}),epoch=6,updates=2880,scheduler=dict(completed=2880,steps_per_epoch=480,original_horizon=24000),optimizer_groups={'fixture':True},model=model.state_dict(),optimizer=opt.state_dict(),rng=rng)
  q=self.folder/'B8_LAST_epoch_06.pt';torch.save(payload,q)
  for e in range(1,7):r.write(self.folder/f'B8_development_{e:02d}.json',{'fixture_epoch':e})
  state=self.state();state.request['checkpoint_sha256']=r.sha(q)
  new=torch.nn.Linear(2,1);newopt=torch.optim.AdamW(new.parameters(),lr=9.,foreach=False)
  with patch('torch.cuda.set_rng_state_all') as cuda,patch.object(newopt,'step',side_effect=AssertionError('No optimizer update')):
   u,reports=state.restore('B8',new,newopt,{'fixture':True})
  self.assertEqual((u,len(reports)),(2880,6));self.assertEqual(state_digest(model.state_dict()),state_digest(new.state_dict()));self.assertEqual(state_digest(opt.state_dict()),state_digest(newopt.state_dict()))
  self.assertEqual(random.getstate(),rng['python']);self.assertTrue(np.array_equal(np.random.get_state()[1],rng['numpy'][1]));self.assertTrue(torch.equal(torch.get_rng_state(),rng['torch_cpu']))
  self.assertTrue(torch.equal(cuda.call_args.args[0][0],rng['torch_cuda'][0]));self.assertEqual(newopt.param_groups[0]['lr'],opt.param_groups[0]['lr'])
  self.assertEqual(u+1,2881);self.assertNotEqual(lr_for_update(2881,steps_per_epoch=480),lr_for_update(1,steps_per_epoch=480))
  state.request['checkpoint_sha256']='f'*64
  with patch('torch.load',side_effect=AssertionError('No unbound checkpoint load')):
   with self.assertRaises(ValueError):state.restore('B8',new,newopt,{'fixture':True})
 def test_orders_initial_identity_and_single_B8_engine_hook(self):
  state=self.state();r.write(self.folder/'paired_initial_identity.json',{'shared':'fixture'});r.write(self.folder/'paired_orders.json',{'7':dict(ids=['a','b'],sha256=r.digest(('a','b')))})
  state.check_initial({'shared':'fixture'});state.check_orders({7:('a','b')})
  with self.assertRaises(ValueError):state.check_orders({7:('b','a')})
  with self.assertRaises(ValueError):state.check_initial({'shared':'wrong'})
  decision=FormalDecision('SYNTHETIC',2029,r.read(REPO_ROOT/(r.READY+'b7_b8_training_proposal.json'))['data']['population_sha256'],True,True,True)
  with patch('yuntapr.experimental.core_innovation.stage4.engine.resources',side_effect=RuntimeError('STOP_BEFORE_GPU')):
   with self.assertRaisesRegex(RuntimeError,'STOP_BEFORE_GPU'):PairedExecutor(SimpleNamespace(identity={},strong_scene_ids=()),self.folder/'never',decision=decision,kinds=('B8',),recovery=state,model_factory=lambda:None).run(None)
  self.assertFalse((self.folder/'never').exists())
 def test_reader_refuses_B7_and_E1_E6_before_source_IO(self):
  with patch.object(r.ReaderFactory,'__call__',return_value='SYNTHETIC_BATCH') as base:
   reader=object.__new__(r.RemainingReaders)
   for kind,e in [('B7',7),('B8',6),('B8',10)]:
    with self.assertRaises(PermissionError):reader('Train',e,(),self.folder/f'{kind}_train_reads_{e:02d}')
   self.assertEqual(reader('Train',7,(),self.folder/'B8_train_reads_07'),'SYNTHETIC_BATCH');base.assert_called_once()
 def test_controller_one_worker_hidden_console_failure_stops_no_retry(self):
  p,v,a=self.proposal();calls=[]
  class Failed:
   def __init__(inner,cmd,**kw):calls.append(kw['creationflags'])
   def wait(inner,timeout):return 2
   def poll(inner):return 2
  with patch.object(r,'checked',return_value=(p,v,a,{},{})),patch.object(r,'resources',return_value={}),patch.object(r.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)),patch.object(r.subprocess,'Popen',Failed):
   with self.assertRaises(RuntimeError):r.execute(REPO_ROOT,'p','v','a','c'*40)
   with self.assertRaises(PermissionError):r.execute(REPO_ROOT,'p','v','a','c'*40)
  self.assertEqual(calls,[r.worker_creation_flags()]);self.assertEqual(r.read(Path(v['output_root'])/'failure.json')['status'],'STOP_NO_AUTOMATIC_RETRY')
 def test_close_inherits_six_seals_without_old_weight_reads(self):
  folder=self.folder/'new';folder.mkdir();db=sqlite3.connect(folder/'updates.sqlite');db.execute('CREATE TABLE updates(model TEXT,u INTEGER,state TEXT)');db.executemany('INSERT INTO updates VALUES (?,?,?)',[('B8',u,'RETURNED') for u in range(2881,4321)]);db.commit();db.close()
  data={'population_sha256':'x'};stop={'epochs':[{'model':'B8','checkpoint':{'epoch':e,'code_commit':r.ORIGINAL}} for e in range(1,7)]}
  for e in (7,8,9):
   q=folder/f'B8_LAST_epoch_{e:02d}.pt';q.write_bytes(b'SYNTHETIC_WEIGHT_NOT_REAL')
   dev={'fixture':e};seal=dict(model='B8',epoch=e,updates=e*480,code_commit='c'*40,population_sha256='x',validation_receipt_sha256=r.digest(dev),checkpoint_sha256=r.sha(q))
   for name,value in [(f'B8_train_{e:02d}.json',{'updates':e*480}),(f'B8_development_{e:02d}.json',dev),(f'B8_tail_{e:02d}.json',{}),(f'B8_LAST_epoch_{e:02d}.receipt.json',seal)]:r.write(folder/name,value)
   for role,n,b in [('train',7918,26424262556),('dev',7950,26639253112)]:
    d=folder/f'B8_{role}_reads_{e:02d}';d.mkdir();r.write(d/'pass_receipt.json',dict(during_failure=False,expected_bytes=b,expected_files=n,actual_reads=dict(delivered_bytes=b,opened_files=n,states={'READ_COMPLETE':n})))
  original_read=r.read
  with patch.object(r,'read',side_effect=lambda path:stop if str(path).endswith(r.STOP) else original_read(path)):
   result=r.close_segment(REPO_ROOT,folder,self.folder/'NONEXISTENT_OLD',dict(data=data,budget=self.caps),'c'*40)
  self.assertEqual(len(result['checkpoints']),9);self.assertEqual(result['replay_updates'],62);self.assertEqual(result['segment_source_bytes'],159190859832)
 def test_controller_success_seals_one_B8_without_B7_worker(self):
  p,v,a=self.proposal();calls=[]
  class Done:
   def __init__(inner,cmd,**kw):
    calls.append(cmd[3]);d=Path(v['output_root'])/'B8_s2029';d.mkdir()
    r.write(d/'completion.json',dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',model='B8',seed=2029,epochs=9,optimizer_updates=4320,code_commit='c'*40,segment_updates=1440,segment_source_bytes=159190859832,segment_source_files=47605))
   def wait(inner,timeout):return 0
   def poll(inner):return 0
  with patch.object(r,'checked',return_value=(p,v,a,{},{})),patch.object(r,'resources',return_value={}),patch.object(r.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)),patch.object(r.subprocess,'Popen',Done),patch.object(r,'summarize') as summary:
   r.execute(REPO_ROOT,'p','v','a','c'*40)
  self.assertEqual(calls,['worker']);summary.assert_called_once();self.assertEqual(r.read(Path(v['output_root'])/'completion.json')['replayed_updates'],62)
if __name__=='__main__':unittest.main()
