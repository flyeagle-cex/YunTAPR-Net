"""Only new completion namespace, inherited-result and budget paths."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import contextmanager
from types import SimpleNamespace

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


class HistoricalPrecisionTests(unittest.TestCase):
    def fixture(self):
        calls=[]
        torch=SimpleNamespace(backends=SimpleNamespace(cudnn=SimpleNamespace(deterministic=False,benchmark=True,allow_tf32=True),cuda=SimpleNamespace(matmul=SimpleNamespace(allow_tf32=True))),inside=False)
        torch.use_deterministic_algorithms=lambda *a,**k:calls.append(('deterministic',a,k))
        torch.set_float32_matmul_precision=lambda value:calls.append(('precision',value))
        @contextmanager
        def inference():
            before=torch.inside;torch.inside=True
            try:yield
            finally:torch.inside=before
        torch.inference_mode=inference
        class Adapter:
            def batches(self):
                assert torch.inside
                yield {'synthetic':True}
        engine=SimpleNamespace(B01Adapter=Adapter,_apply_historical_determinism=lambda *a:calls.append(('inherited',a)))
        m.install_historical_b01_context(engine,torch)
        return engine,torch,calls

    def test_b01_precision_matches_seeded_historical_scope(self):
        engine,torch,calls=self.fixture();engine._apply_historical_determinism('b01',2026,False)
        self.assertTrue(torch.backends.cudnn.deterministic);self.assertFalse(torch.backends.cudnn.benchmark)
        self.assertFalse(torch.backends.cudnn.allow_tf32);self.assertFalse(torch.backends.cuda.matmul.allow_tf32)
        self.assertIn(('precision','highest'),calls);self.assertIn(('deterministic',(True,),{'warn_only':False}),calls)

    def test_core_policy_stays_inherited(self):
        engine,torch,calls=self.fixture();engine._apply_historical_determinism('b7b8',2030,False)
        self.assertEqual(calls,[('inherited',('b7b8',2030,False))])

    def test_generator_and_consumer_share_inference_scope_then_restore(self):
        engine,torch,calls=self.fixture();adapter=engine.B01Adapter()
        self.assertFalse(torch.inside)
        iterator=adapter.batches();self.assertEqual(next(iterator),{'synthetic':True});self.assertTrue(torch.inside)
        iterator.close();self.assertFalse(torch.inside)


if __name__=='__main__':unittest.main()
