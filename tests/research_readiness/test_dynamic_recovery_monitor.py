"""Read-only recovery counters only; never import training or real data."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('recovery_monitor',ROOT/'tools/b2_monitor/server.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj),encoding='utf-8')

class MonitorTests(unittest.TestCase):
    def fixture(self,root,n):
        parent=root/'old';out=root/'new';p=json.loads((ROOT/'docs/research_readiness/20261025/evidence/b7_b8_multiseed_recovery_proposal_20261028.json').read_bytes())
        a=dict(code_commit=p['execution_code_commit'],proposal_sha256=p['proposal_sha256'],tasks=p['tasks'],budget=p['budget'])
        write(out/'authorization_binding.json',dict(controller_pid=123,approval=a,recovery_parent=str(parent)))
        for epoch in range(1,7):
            base=parent/'B7_s2030';write(base/f'B7_train_{epoch:02d}.json',dict(weighted_mean=1))
            write(base/f'B7_development_{epoch:02d}.json',dict(groups={'all':{'summary':{'coverage':[.9]*32}}}))
            write(base/f'B7_LAST_epoch_{epoch:02d}.receipt.json',dict(checkpoint_sha256='SYNTHETIC'))
            for role in ('train','dev'):write(base/f'B7_{role}_reads_{epoch:02d}/pass_receipt.json',dict(actual_reads=dict(opened_files=1,delivered_bytes=1000,reserved_bytes=1000)))
        # These deliberately invalid old SQLite payloads must never be queried.
        (parent/'B7_s2030/updates.sqlite').write_bytes(b'SYNTHETIC_OLD_DO_NOT_QUERY')
        oldpartial=parent/'B7_s2030/B7_train_reads_07';oldpartial.mkdir();(oldpartial/'reads.sqlite').write_bytes(b'SYNTHETIC_HOT_OLD_DO_NOT_QUERY')
        import sqlite3
        folder=out/'B7_s2030';folder.mkdir();db=sqlite3.connect(folder/'updates.sqlite');db.execute('CREATE TABLE updates(model TEXT,u INTEGER,state TEXT)');db.executemany('INSERT INTO updates VALUES (?,?,?)',[('B7',u,'RETURNED') for u in range(2881,2881+n)]);db.commit();db.close()
        for dbpath,size in ((out/'B7_s2030_static_source.sqlite',312828),(folder/'B7_train_reads_07/reads.sqlite',54321)):
            dbpath.parent.mkdir(parents=True,exist_ok=True);db=sqlite3.connect(dbpath);db.execute('CREATE TABLE file_io(actual_bytes INTEGER,expected_bytes INTEGER)');db.execute('INSERT INTO file_io VALUES (?,?)',(size,size));db.commit();db.close()
        return out,p
    def test_replay_counter_survives_queued_B8_and_prior_IO_is_not_doubled(self):
        for n in (12,500):
            with self.subTest(n=n),tempfile.TemporaryDirectory() as tmp,patch.object(m.base,'process_token',return_value=134000000000000000):
                out,p=self.fixture(Path(tmp),n);s=m.CampaignReader(out,123).snapshot(include_resources=False)
                self.assertEqual(s['state'],'RUNNING');self.assertEqual(s['returned'],3321+n);self.assertEqual(s['segment_returned'],n);self.assertEqual(s['replay_returned'],min(n,441))
                self.assertEqual(s['runs'][0]['returned'],2880+n);self.assertEqual(s['sealed_epochs'],6)
                self.assertEqual(s['io']['bytes'],p['budget']['prior_source_bytes']+312828+54321)
                self.assertEqual(s['io']['files'],p['budget']['prior_source_files']+2)
                self.assertEqual(s['limits']['updates'],17721);self.assertTrue(all(r['state']=='PENDING' for r in s['runs'][1:]))
    def test_wrong_replay_budget_is_rejected_before_ledger_reads(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(m.base,'process_token',return_value=None):
            out,_=self.fixture(Path(tmp),1);binding=json.loads((out/'authorization_binding.json').read_bytes());binding['approval']['budget']['replay_allowance']=0;write(out/'authorization_binding.json',binding)
            with self.assertRaises(ValueError):m.CampaignReader(out,123)

if __name__=='__main__':unittest.main()
