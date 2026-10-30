"""Only new completion namespace, inherited-result and budget paths."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('metric_completion',ROOT/'tools/research_readiness/resume_metric_backfill.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class CompletionTests(unittest.TestCase):
    def test_valid_result_requires_gate_and_checkpoint(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'docs/research_readiness/.local') as tmp:
            p=Path(tmp)/'r.json';run=dict(run_id='B4_s2031',checkpoint_sha256='a'*64)
            obj=dict(run_id=run['run_id'],status='COMPLETE',gate=dict(passed=True),checkpoint_identity=dict(expected_sha256='a'*64))
            p.write_text(json.dumps(obj));self.assertEqual(m.valid_result(p,run)['status'],'COMPLETE')
            obj['gate']['passed']=False;p.write_text(json.dumps(obj))
            with self.assertRaises(ValueError):m.valid_result(p,run)
    def test_no_overwrite_receipt(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'docs/research_readiness/.local') as tmp:
            p=Path(tmp)/'r.json';m.write(p,dict(status='FAILED_PRESERVED'))
            with self.assertRaises(FileExistsError):m.write(p,dict(status='COMPLETE'))
            self.assertEqual(m.read(p)['status'],'FAILED_PRESERVED')
    def test_no_inference_without_completion_instruction(self):
        with self.assertRaises(PermissionError):m.validate(dict(authorization_basis='OLD_CONSUMED_TRAINING'))
    def test_prior_engine_budget_can_be_tightened_without_scientific_change(self):
        # Inspect the existing formula module only; no torch or data import.
        engine=ROOT.parent/'YunTAPR-metric-backfill-20261029/phaseB_inference/infer_eval.py'
        old=m.module(engine,'frozen_backfill_formula_only').FrozenBudgetStub
        budget=old(max_read_bytes=32);budget.admit_bytes(20);budget.account_bytes(20)
        with self.assertRaises(MemoryError):budget.admit_bytes(13)
        self.assertEqual(budget.bytes,20)


if __name__=='__main__':unittest.main()
