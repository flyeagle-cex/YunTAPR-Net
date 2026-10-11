"""Public package checks only; no scientific data, models or subprocess launch."""
import ast
import hashlib
import json
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_p1_integration_remediation/v1'


class DeliveryTests(unittest.TestCase):
    def test_manifest_bytes_and_hashes(self):
        m=json.loads((OUT/'manifest.json').read_bytes())
        for collection in ('artifacts','unchanged_source_evidence'):
            for rel,record in m[collection].items():
                with self.subTest(file=rel):
                    self.assertNotIn('.local',rel)
                    value=(ROOT/rel).read_bytes()
                    self.assertEqual(len(value),record['bytes'])
                    self.assertEqual(hashlib.sha256(value).hexdigest(),record['sha256'])

    def test_no_raw_weights_arrays_private_paths_in_public_artifacts(self):
        m=json.loads((OUT/'manifest.json').read_bytes())
        for rel in m['artifacts']:
            p=ROOT/rel
            self.assertNotIn(p.suffix.lower(),('.pt','.pth','.npy','.nc','.h5','.sqlite'))
            if p.suffix in ('.md','.tex','.json','.log'):
                self.assertNotRegex(p.read_text(encoding='utf-8'),r'[A-Za-z]:[\\/]+(?:Users|pytorch|private)')

    def test_50_functional_methods_not_counting_delivery_checks(self):
        expected={'test_checkpoint.py':27,'test_launcher.py':15,'test_integration.py':8}
        for name,count in expected.items():
            tree=ast.parse((OUT/'tests'/name).read_text(encoding='utf-8'))
            actual=sum(isinstance(n,ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(tree))
            self.assertEqual(actual,count)
        row=json.loads((OUT/'tests/test_summary.json').read_bytes())
        self.assertEqual(row['final_tests']['passed'],50);self.assertEqual(row['nonrefundable_reservations'],15)

    def test_sealed_and_frozen_unchanged(self):
        row=json.loads((OUT/'protected_validation.json').read_bytes())
        self.assertEqual(row['preexisting_tracked_count'],3692)
        self.assertEqual(row['changed_paths'],[])
        self.assertTrue(row['sealed_anchors_unchanged']);self.assertTrue(row['sealed_rows_unchanged'])

    def test_all_event_source_hashes_match_current_source(self):
        rows=json.loads((OUT/'tests/job_durable_receipts.json').read_bytes())['receipts']
        for row in rows:
            for key in ('launch','bound','monitor_crash','termination'):
                if key in row:
                    for rel,sha in row[key]['source_sha'].items():
                        self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),sha)

    def test_all_launch_attempts_audited_and_no_retry(self):
        rows=json.loads((OUT/'tests/job_durable_receipts.json').read_bytes())['receipts']
        self.assertEqual(len(rows),15)
        for row in rows:
            self.assertIn('launch',row)
            if row['case']=='crash_inner':
                self.assertIn('monitor_crash',row)
            else:
                self.assertTrue(row['termination']['job_empty_and_handles_signaled'])
                self.assertEqual(row['termination']['optimizer_steps'],0)
                self.assertEqual(row['termination']['restarts'],0)

    def test_formal_flags_remain_denied(self):
        row=json.loads((OUT/'final_status.json').read_bytes())
        for key in ('V2_PHASE_B_AUTHORIZED','FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED','SCIENTIFIC_APPROVAL_GENERATED'):
            self.assertIs(row[key],False)
        self.assertEqual(row['FORMAL_PHASE_B_OPTIMIZER_STEPS'],0)
        self.assertEqual(row['historical_2025_path_attributes'],'NOT_INSTRUMENTED')
        self.assertEqual(row['FORMAL_REAL_MODEL_RESTORE'],'NOT_VERIFIED')
        self.assertEqual(row['FORMAL_LONG_RUN_STABILITY'],'NOT_VERIFIED')

    def test_plain_lf_and_python_syntax(self):
        m=json.loads((OUT/'manifest.json').read_bytes())
        for rel in m['artifacts']:
            p=ROOT/rel
            if p.suffix in ('.py','.md','.tex','.json','.log'):
                raw=p.read_bytes();self.assertNotIn(b'\r\n',raw)
                if p.suffix=='.py':ast.parse(raw.decode('utf-8'))
        self.assertTrue((OUT/'P1_REMEDIATION_REVIEW.pdf').read_bytes().startswith(b'%PDF'))


if __name__=='__main__':unittest.main(verbosity=2)
