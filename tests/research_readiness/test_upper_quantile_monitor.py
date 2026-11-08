"""Synthetic read-only counters for two B7 arms in separate folders."""

import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
definition = importlib.util.spec_from_file_location('uq_monitor', ROOT / 'tools/b2_monitor/server.py')
monitor = importlib.util.module_from_spec(definition)
definition.loader.exec_module(monitor)


class UpperQuantileMonitorTests(unittest.TestCase):
    def fixture(self, output):
        proposal = json.loads((ROOT / 'docs/research_readiness/20261108_upper_quantile_pair/EXECUTION_PROPOSAL.json').read_bytes())
        approval = dict(code_commit='f43b4225fef462a31035d59a06b85f31e5b257dc',
                        proposal_sha256=proposal['proposal_sha256'], tasks=proposal['tasks'], budget=proposal['budget'])
        (output / 'authorization_binding.json').write_text(json.dumps(dict(controller_pid=123, approval=approval)))
        for task, count in zip(proposal['tasks'], (17, 3)):
            arm = output / task['arm']
            folder = arm / 'B7_s2029'
            folder.mkdir(parents=True)
            with closing(sqlite3.connect(folder / 'updates.sqlite')) as db:
                db.execute('CREATE TABLE updates(model TEXT,u INTEGER,state TEXT)')
                db.executemany('INSERT INTO updates VALUES (?,?,?)', [('B7', i, 'RETURNED') for i in range(1, count + 1)])
                db.commit()
            for path, size in [(arm / 'B7_static_source.sqlite', 312828),
                               (folder / 'B7_train_reads_01/reads.sqlite', 1234)]:
                path.parent.mkdir(exist_ok=True)
                with closing(sqlite3.connect(path)) as db:
                    db.execute('CREATE TABLE file_io(actual_bytes INTEGER,expected_bytes INTEGER)')
                    db.execute('INSERT INTO file_io VALUES (?,?)', (size, size))
                    db.commit()

    def test_two_arms_have_distinct_labels_and_do_not_double_count(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(monitor.base, 'process_token', return_value=134000000000000000):
            output = Path(temporary)
            self.fixture(output)
            snapshot = monitor.CampaignReader(output, 123).snapshot(include_resources=False)
            self.assertEqual(snapshot['returned'], 20)
            self.assertEqual([row['returned'] for row in snapshot['runs']], [17, 3])
            self.assertEqual([row['name'] for row in snapshot['runs']], ['CONTROL_E0', 'CANDIDATE_UQ_MILD'])
            self.assertEqual(snapshot['io']['bytes'], 2 * (312828 + 1234))
            self.assertEqual(snapshot['io']['files'], 4)
            self.assertTrue(snapshot['upper_quantile'])
            self.assertEqual(snapshot['limits']['updates'], 8640)
            self.assertEqual(snapshot['limits']['epochs'], 18)

    def test_changed_proposal_rejects_before_ledger_queries(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(monitor.base, 'process_token', return_value=None):
            output = Path(temporary)
            self.fixture(output)
            path = output / 'authorization_binding.json'
            value = json.loads(path.read_bytes())
            value['approval']['proposal_sha256'] = 'SYNTHETIC_WRONG'
            path.write_text(json.dumps(value))
            with patch.object(monitor.base, 'query', side_effect=AssertionError('No ledger query expected')):
                with self.assertRaises(ValueError):
                    monitor.CampaignReader(output, 123)


if __name__ == '__main__':
    unittest.main()
