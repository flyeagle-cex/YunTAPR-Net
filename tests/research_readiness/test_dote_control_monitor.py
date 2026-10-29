"""Only the one-model display identity and its static/weather counters."""
import importlib.util,json,sqlite3,unittest,uuid
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('control_monitor',ROOT/'tools/b2_monitor/server.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class ControlMonitorTests(unittest.TestCase):
    def setUp(self):
        self.workspace=ROOT/'tests/research_readiness/.local'/('dote_monitor_'+uuid.uuid4().hex)
        self.workspace.mkdir(parents=True)
    def fixture(self,out):
        p=json.loads((ROOT/'docs/research_readiness/20261025/evidence/dote_control_proposal_20261029.json').read_bytes())
        a=dict(code_commit=p['execution_code_commit'],proposal_sha256=p['proposal_sha256'],tasks=p['tasks'],budget=p['budget'])
        (out/'authorization_binding.json').write_text(json.dumps(dict(controller_pid=123,approval=a)))
        folder=out/'B7_s2029';folder.mkdir();db=sqlite3.connect(folder/'updates.sqlite')
        db.execute('CREATE TABLE updates(model TEXT,u INTEGER,state TEXT)');db.executemany('INSERT INTO updates VALUES (?,?,?)',[('B7',i,'RETURNED') for i in range(1,18)]);db.commit();db.close()
        for dbpath,size in [(out/'B7_ZERO_DOTE_static_source.sqlite',312828),(folder/'B7_train_reads_01/reads.sqlite',1234)]:
            dbpath.parent.mkdir(exist_ok=True);db=sqlite3.connect(dbpath);db.execute('CREATE TABLE file_io(actual_bytes INTEGER,expected_bytes INTEGER)');db.execute('INSERT INTO file_io VALUES (?,?)',(size,size));db.commit();db.close()
        return p
    def test_one_control_counts_and_label_are_distinct_from_original_B7(self):
        with patch.object(m.base,'process_token',return_value=134000000000000000):
            out=self.workspace;self.fixture(out);s=m.CampaignReader(out,123).snapshot(include_resources=False)
            self.assertTrue(s['dote_control']);self.assertEqual(s['state'],'RUNNING');self.assertEqual(s['returned'],17)
            self.assertEqual(s['runs'][0]['model'],'B7_ZERO_DOTE');self.assertEqual(len(s['runs']),1)
            self.assertEqual(s['io']['bytes'],312828+1234);self.assertEqual(s['io']['files'],2)
            self.assertEqual(s['limits']['updates'],4320);self.assertEqual(s['limits']['epochs'],9);self.assertEqual(s['limits']['seconds'],21600)
    def test_wrong_proposal_is_rejected_before_any_ledger_query(self):
        with patch.object(m.base,'process_token',return_value=None):
            out=self.workspace;self.fixture(out);f=out/'authorization_binding.json';a=json.loads(f.read_bytes());a['approval']['proposal_sha256']='WRONG';f.write_text(json.dumps(a))
            with patch.object(m.base,'query',side_effect=AssertionError('No ledger reads')):
                with self.assertRaises(ValueError):m.CampaignReader(out,123)
    def multi_fixture(self,out):
        p=self.fixture(out);f=out/'authorization_binding.json';a=json.loads(f.read_bytes());a['control']='ZERO_NUMERIC_RETAIN_REAL_MASKS_TWO_SEEDS'
        a['approval'].update(approved_by_researcher=True,tasks=[dict(model='B7_ZERO_DOTE',seed=s) for s in (2030,2031)])
        a['approval']['budget'].update(total_updates=8640,total_source_bytes=955143907680,total_source_files=285626,max_package_seconds=43200)
        f.write_text(json.dumps(a));(out/'B7_s2029').rename(out/'B7_s2030');(out/'B7_ZERO_DOTE_static_source.sqlite').rename(out/'B7_ZERO_DOTE_s2030_static_source.sqlite')
        return a
    def test_two_control_budget_labels_static_and_queue(self):
        with patch.object(m.base,'process_token',return_value=134000000000000000):
            out=self.workspace;self.multi_fixture(out);s=m.CampaignReader(out,123).snapshot(include_resources=False)
            self.assertTrue(s['dote_control_multiseed']);self.assertEqual(len(s['runs']),2)
            self.assertEqual([r['model'] for r in s['runs']],['B7_ZERO_DOTE']*2);self.assertEqual(s['runs'][1]['state'],'PENDING')
            self.assertEqual(s['io']['bytes'],312828+1234);self.assertEqual(s['limits']['updates'],8640)
            self.assertEqual(s['limits']['epochs'],18);self.assertEqual(s['limits']['seconds'],43200)
    def test_two_control_wrong_budget_rejected_without_ledger_read(self):
        with patch.object(m.base,'process_token',return_value=None):
            out=self.workspace;a=self.multi_fixture(out);a['approval']['budget']['total_updates']=17280;(out/'authorization_binding.json').write_text(json.dumps(a))
            with patch.object(m.base,'query',side_effect=AssertionError('No ledger reads')):
                with self.assertRaises(ValueError):m.CampaignReader(out,123)


if __name__=='__main__':unittest.main()
