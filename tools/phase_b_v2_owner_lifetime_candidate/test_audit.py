"""Artificial SQLite/metadata only; demonstrate stale ACTIVE never grants start."""
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
import hashlib,sqlite3,sys,unittest,uuid
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_owner_lifetime_candidate import audit as a

class Tests(unittest.TestCase):
 def setUp(self):
  self.folder=ROOT/'docs/phase_b_v2_owner_lifetime_repair/v1/.local'/('artificial_audit_'+uuid.uuid4().hex);self.folder.mkdir()
  self.db=self.folder/'fixture.sqlite'
  with closing(sqlite3.connect(self.db)) as c:
   c.executescript('CREATE TABLE campaign(id,status,reason);CREATE TABLE attempts(status);CREATE TABLE runs(id,status,epoch,updates,last_sha,ordinal);CREATE TABLE epochs(run,epoch,phase);')
   c.execute('INSERT INTO campaign VALUES(?,?,NULL)',(a.CAMPAIGN,'ACTIVE'))
   c.execute("INSERT INTO attempts VALUES('RETURNED_VERIFIED')")
   c.execute("INSERT INTO runs VALUES('ARTIFICIAL','RUNNING',7,36597,?,0)",('a'*64,))
   c.execute("INSERT INTO epochs VALUES('ARTIFICIAL',8,'TRAINING')")
   c.commit()
  me=dict(pid=999,creation_filetime=111,image_path_key='b'*64);nonce='c'*32
  self.owner=dict(**me,campaign=a.CAMPAIGN,session=1,nonce=nonce,job_name='Local\\'+a.CAMPAIGN+'__1__'+nonce)
  self.worker=dict(**me,campaign=a.CAMPAIGN,nonce=nonce)
 def run_audit(self,process='ABSENT'):
  values={'supervisor_identity.json':self.owner,'worker_identity.json':self.worker,'heartbeat.json':{'utc':'2026-10-21T00:00:00+00:00'}}
  with patch.object(a,'DB',self.db),patch.object(a,'SESSION',self.folder),patch.object(a,'read_json_snapshot',side_effect=lambda path,root:values[path.name]),patch.object(a.native,'process',return_value={'status':process}),patch.object(a.native,'job',return_value={'status':'ABSENT','pids':[]}),patch.object(a.native,'clock',return_value=('2026-10-21T00:05:00+00:00','2026-10-20T23:00:00+00:00')):
   return a.inspect()
 def test_stale_active_is_effectively_stopped_and_sqlite_unchanged(self):
  before=hashlib.sha256(self.db.read_bytes()).hexdigest();r=self.run_audit()
  self.assertEqual(r['observation']['effective_state'],'STOPPED_UNCLEAN_LAST_NOT_VERIFIED');self.assertFalse(r['observation']['resume_allowed'])
  self.assertEqual(before,hashlib.sha256(self.db.read_bytes()).hexdigest());self.assertEqual(before,r['stopped_ledger_sha256'])
  self.assertEqual(r['new_reserved'],1);self.assertEqual(r['cumulative_reserved'],164836)
 def test_live_session_never_reclassified_as_dead(self):
  r=self.run_audit('LIVE_MATCH');self.assertFalse(r['observation']['observed_process_tree_empty']);self.assertNotIn('stopped_ledger_sha256',r)
 def test_unknown_probe_is_not_stop_proof(self):
  self.assertEqual(self.run_audit('UNKNOWN')['observation']['effective_state'],'NOT_VERIFIED_NATIVE_PROBE')
 def test_no_training_import_or_execution_capability(self):
  r=self.run_audit();self.assertNotIn('torch',sys.modules);self.assertEqual(r['new_optimizer_updates'],0)
  self.assertFalse(r['original_ledger_modified']);self.assertFalse(r['actual_termination_receipt_generated'])

if __name__=='__main__':unittest.main(verbosity=2)
