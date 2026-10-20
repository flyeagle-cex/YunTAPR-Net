"""Recovery delta only: artificial ledger/status fixtures, no model/real update."""
from pathlib import Path
from contextlib import contextmanager,nullcontext
from types import SimpleNamespace
from unittest.mock import patch
import ast,copy,hashlib,importlib.util,json,re,sqlite3,sys,unittest,uuid
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v1 import protocol as p,quota as q,ancestor as anc,accounting as a
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v1.authority import execution_instruction,require_execution_authority
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v1.recovery import validate_history_metrics
OLD=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_epoch2_recovery_v2';NEW=OLD.with_name('phase_b_v2_seed2027_b1_epoch7_recovery_v1')

def node(path,name,cls=None):
 rows=ast.parse(path.read_bytes()).body
 if cls:rows=next(n.body for n in rows if isinstance(n,ast.ClassDef) and n.name==cls)
 return next(n for n in rows if getattr(n,'name',None)==name)

@contextmanager
def fixture():
 folder=p.LOCAL/('artificial_ledger_'+uuid.uuid4().hex);folder.mkdir()
 old=folder/'old.sqlite';con=sqlite3.connect(old)
 con.executescript('CREATE TABLE campaign(id,status,reason);CREATE TABLE attempts(status);CREATE TABLE runs(id,ordinal,status,epoch,updates,last_sha);CREATE TABLE epochs(run,epoch,phase,train,validation,last_receipt);CREATE TABLE sessions(n,status);')
 con.execute('INSERT INTO campaign VALUES(?,?,?)',(anc.SOURCE_CAMPAIGN,'FAILED_NO_RETRY','OSError'))
 con.executemany('INSERT INTO attempts VALUES(?)',[('RETURNED_VERIFIED',)]*78420)
 for i,(m,arm) in enumerate(p.ORDER):
  con.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(p.run_id(m,arm),i,'COMPLETE' if i==0 else ('RUNNING' if i==1 else 'PENDING'),9 if i==0 else (7 if i==1 else 0),47052 if i==0 else (41824 if i==1 else 0),anc.COMPLETE_SHA if i==0 else (p.LAST_SHA if i==1 else None)))
 for run,limit in ((anc.COMPLETE_RUN,9),(anc.RUN,8)):
  for e in range(1,limit+1):con.execute('INSERT INTO epochs VALUES(?,?,?,?,?,?)',(run,e,'WAIT_VALIDATION' if run==anc.RUN and e==8 else 'LAST_COMMITTED','t'+str(e),'v'+str(e),'r'+str(e)))
 con.execute("INSERT INTO sessions VALUES(1,'ACTIVE')");con.commit();con.close()
 release={'failed_ancestor_sha256':'a'*64}
 with patch.object(q,'ROOT',folder),patch.object(q,'DB',folder/'new.sqlite'),patch.object(p,'verify_release',return_value=release),patch.object(anc,'SOURCE_DB','old.sqlite'),patch.object(anc,'Guard',return_value=nullcontext()):yield folder,release

class Tests(unittest.TestCase):
 def test_01_nonrefundable_arithmetic(self):
  row=a.fields(0,0);self.assertEqual((row['reserved'],row['returned_verified'],row['adopted_prior_updates'],row['abandoned_old_updates']),(164835,164834,83648,81187))
  self.assertEqual(p.MAX_NEW,198664);self.assertEqual(p.TOTAL,363499);self.assertEqual(a.fields(p.MAX_NEW,p.MAX_NEW)['reserved'],p.TOTAL)
  self.assertEqual(p.TOTAL-358271,5228);self.assertEqual(282312+81187,p.TOTAL)
  with self.assertRaises(ValueError):a.fields(198665,198665)
  with self.assertRaises(ValueError):a.validate(a.fields(1,0),complete_transaction=True)
 def test_02_source_exact_counts_and_boundary(self):
  with fixture() as (folder,_):
   with sqlite3.connect(folder/'old.sqlite') as con:
    anc.verify_source(con);con.execute("UPDATE runs SET updates=36596 WHERE id=?",(anc.RUN,))
    with self.assertRaises(ValueError):anc.verify_source(con)
 def test_03_adopt_complete_b0_and_b1_seven_not_eight(self):
  with fixture() as (folder,release):
   before=hashlib.sha256((folder/'old.sqlite').read_bytes()).hexdigest();ledger=q.Ledger.initialize(release)
   self.assertEqual(ledger.run_row(anc.COMPLETE_RUN)['status'],'COMPLETE');self.assertEqual(ledger.run_row(anc.RUN)['updates'],36596)
   self.assertEqual(ledger.con.execute('SELECT count(*) FROM epochs').fetchone(),(16,))
   self.assertEqual(ledger.con.execute('SELECT max(epoch) FROM epochs WHERE run=?',(anc.RUN,)).fetchone(),(7,))
   n,nonce=ledger.claim_session();ledger.activate_session(n,nonce);ledger.start_run(anc.RUN);ledger.begin_epoch(anc.RUN,8)
   with self.assertRaises(PermissionError):ledger.reserve(anc.RUN,41825)
   self.assertEqual(ledger.reserve(anc.RUN,36597),1)
   with self.assertRaises(sqlite3.IntegrityError):ledger.reserve(anc.RUN,36597)
   ledger.returned(anc.RUN,36597);self.assertEqual(ledger.snapshot()['reserved'],164836)
   with self.assertRaises(PermissionError):ledger.start_run(p.run_id(*p.ORDER[2]))
   with self.assertRaises(ValueError):ledger.pause_boundary(n,nonce,{})
   ledger.close();self.assertEqual(before,hashlib.sha256((folder/'old.sqlite').read_bytes()).hexdigest())
 def test_04_safe_pause_before_replay_no_refund(self):
  with fixture() as (_,release):
   ledger=q.Ledger.initialize(release);n,nonce=ledger.claim_session();ledger.activate_session(n,nonce);ledger.request_pause()
   with self.assertRaises(q.PauseAtBoundary):ledger.start_run(anc.RUN)
   row=ledger.pause_boundary(n,nonce,{});self.assertEqual(row['quota']['reserved'],164835);ledger.close()
 def test_05_actual_decision_and_unchanged_science(self):
  plan=(p.OUT/'config.json').read_bytes();self.assertEqual(plan,(ROOT/'docs/phase_b_v2_formal_execution/seed2027_epoch2_recovery_v2/config.json').read_bytes());p.validate_plan(json.loads(plan))
  auth=execution_instruction();self.assertEqual((auth['source_run'],auth['source_epoch'],auth['source_update'],auth['maximum_attempts'],auth['additional_attempts']),(anc.RUN,7,36596,363499,5228))
  self.assertEqual(auth['answer'],'已接回原 H: 盘，授权恢复及额外 5,228 次额度')
  for seed in (True,2026,2028):
   with self.assertRaises(PermissionError):require_execution_authority(seed)
 def test_06_unchanged_math_restore_and_watchdog(self):
  for file,cls,names in [('engine.py','Engine',('train','validate')),('checkpoint.py',None,('Store',)),('supervisor.py',None,('main',)),('recovery.py',None,('apply_validated_state',))]:
   for name in names:
    before=ast.dump(node(OLD/file,name,cls),include_attributes=False).replace('phase_b_v2_seed2027_epoch2_recovery_v2','phase_b_v2_seed2027_b1_epoch7_recovery_v1')
    self.assertEqual(before,ast.dump(node(NEW/file,name,cls),include_attributes=False))
 def test_07_new_checkpoint_quota_metadata(self):
  fn=copy.deepcopy(node(NEW/'checkpoint.py','validate','Contract'))
  cut=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='m');fn.body=fn.body[:cut]
  ns=dict(__package__='yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v1',re=re,SCHEMA='ARTIFICIAL',STEPS=p.STEPS,TRAIN_N=p.TRAIN_N,DEV_N=p.DEV_N,CAMPAIGN=p.CAMPAIGN,TOTAL=p.TOTAL,digest=p.digest,epoch_order=lambda ids,epoch:ids)
  exec(compile(ast.Module(body=[fn],type_ignores=[]),'metadata-only','exec'),ns)
  identity=dict(run_id=anc.RUN,code=dict(failed_ancestor_sha256='a'*64));obj=SimpleNamespace(identity=identity,initial='initial',key='source',train_ids=('artificial-train',),dev_ids=('artificial-dev',))
  report=dict(complete=True,source_sha='source',ids_sha=p.digest(obj.dev_ids),summary=dict(scenes=p.DEV_N,n_valid=p.DEV_N*3430));report['receipt_sha']=p.digest(report)
  quota=dict(campaign=p.CAMPAIGN,**a.fields(5228,5228),old_ancestor_receipt_sha256='a'*64,runs=[dict(id=anc.RUN,updates=41824)])
  payload=dict(schema='ARTIFICIAL',identity=identity,model=None,optimizer=None,scheduler=None,rng=None,initial_sha='initial',epoch=8,update=41824,parent_last_sha=p.LAST_SHA,train=dict(scenes=p.TRAIN_N,batches=p.STEPS,ids_sha=p.digest(obj.train_ids),n_valid=p.TRAIN_N*3430),validation=report,quota=quota)
  ns['validate'](obj,payload);quota['reserved']-=1
  with self.assertRaises(ValueError):ns['validate'](obj,payload)
 def test_08_canonical_history(self):
  payload=dict(train={'synthetic':1},validation={'ordered':[1,2]});history=dict(train={'synthetic':1},development={'ordered':[1,2]})
  validate_history_metrics(history,payload);history['development']['ordered'].reverse()
  with self.assertRaises(ValueError):validate_history_metrics(history,payload)
 def test_09_actual_new_status_writer_and_monitor_reader(self):
  folder=p.LOCAL/('artificial_status_'+uuid.uuid4().hex);folder.mkdir();path=folder/'heartbeat.json'
  spec=importlib.util.spec_from_file_location('monitor',ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  for n in range(10):p.atomic_json(path,dict(artificial=n));self.assertEqual(m.read_json(path),dict(artificial=n))
  self.assertEqual(m.APP_ID,'YUNTAPR_READONLY_LIVE_SEED2027_B1_EPOCH7_V1')
  self.assertNotIn('torch',sys.modules);self.assertFalse(p.DB.exists());self.assertFalse(p.DB.with_suffix('.once').exists())
 def test_10_completed_results_survive_future_clean_pause(self):
  fn=copy.deepcopy(node(NEW/'engine.py','completed_result'))
  ns=dict(__package__='yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v1',run_id=p.run_id,ORDER=p.ORDER,OUT=p.OUT,verify_release=lambda:{'failed_ancestor_sha256':'a'*64})
  exec(compile(ast.Module(body=[fn],type_ignores=[]),'completed-report-routing','exec'),ns)
  data={'artificial_completed_b0':True};guard=SimpleNamespace(pool=SimpleNamespace(metadata={anc.SOURCE_PREFIX+anc.COMPLETE_RUN+'.json':data}))
  with patch.object(anc,'Guard',return_value=nullcontext(guard)):
   self.assertIs(ns['completed_result'](anc.COMPLETE_RUN),data)
  from yuntapr.experimental.phase_b_v2_status_snapshot_io import reader
  with patch.object(reader,'read_json_snapshot',return_value={'artificial_completed_b1':True}) as read:
   self.assertEqual(ns['completed_result'](anc.RUN),{'artificial_completed_b1':True});read.assert_called_once_with(p.OUT/(anc.RUN+'.json'),p.OUT)

if __name__=='__main__':unittest.main(verbosity=2)
