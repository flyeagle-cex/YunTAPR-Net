"""Only new completion namespace, inherited-result and budget paths."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

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


class CorrectiveGateTests(unittest.TestCase):
    def grant_fixture(self):
        tasks=['B0_s2026_E0','B1_s2026_E0','B0_s2027_E0','B1_s2027_E0']
        budget=dict(caps={t:dict(source_bytes=10,content_reads=1,seconds=2) for t in tasks},maximum_seconds=8)
        p=dict(execution_code_commit='SYNTHETIC_TEST_ONLY',tasks=tasks,budget=budget,engine_sha256='e'*64,registry_sha256='f'*64,code_sha256={},inherited_metrics_sha256={'saved':'a'*64})
        p['proposal_sha256']=m.digest(p)
        s=dict(correction_proposal='NO_REAL_PROPOSAL',researcher_approval='NO_REAL_APPROVAL_FILE',new_output_root='NO_REAL_OUTPUT',remaining=tasks,caps=budget['caps'],maximum_seconds=8,engine_sha256='e'*64,registry_sha256='f'*64,inherited={'saved':{'sha256':'a'*64}})
        a=dict(approved_by_researcher=True,decision_id='SYNTHETIC_UNIT_TEST_NOT_RESEARCH_AUTHORIZATION',proposal_sha256=p['proposal_sha256'],execution_code_commit=p['execution_code_commit'],tasks=tasks,budget=budget,output_root=s['new_output_root'])
        return s,p,a

    def test_corrective_execution_rejects_false_or_missing_grant(self):
        s,p,a=self.grant_fixture();a['approved_by_researcher']=False
        with patch.object(m,'read',side_effect=[p,a]):
            with self.assertRaises(PermissionError):m.correction_grant(s)
        with patch.object(m,'read',side_effect=[p,FileNotFoundError('missing real grant')]):
            with self.assertRaises(FileNotFoundError):m.correction_grant(s)

    def test_corrective_execution_cannot_change_the_approved_budget(self):
        s,p,a=self.grant_fixture();a['budget']=dict(maximum_seconds=999,caps=s['caps'])
        with patch.object(m,'read',side_effect=[p,a]):
            with self.assertRaises(PermissionError):m.correction_grant(s)

    def test_observed_checkpoint_mismatch_is_not_a_complete_metric_result(self):
        x=dict(run_id='synthetic',status='COMPLETE',gate=dict(passed=True),checkpoint_identity=dict(expected_sha256='a'*64,sha256_actual='b'*64))
        with patch.object(m,'read',return_value=x):
            with self.assertRaises(ValueError):m.valid_result('NOT_READ',dict(run_id='synthetic',checkpoint_sha256='a'*64))

    def test_resource_admission_rejects_low_ram_or_gpu_or_disk(self):
        normal=dict(gpu=dict(total_mib=8192,used_mib=1024),memory=dict(available=16*1024**3),disk_free=10*1024**3)
        for status in [dict(normal,memory=dict(available=1024**3)),dict(normal,gpu=dict(total_mib=8192,used_mib=7000)),dict(normal,disk_free=1024**3)]:
            with patch.object(m,'module',return_value=SimpleNamespace(resources=lambda folder:status)):
                with self.assertRaises(RuntimeError):m.resource_admission('NOT_OPENED')

    def test_inherited_metric_hashes_cannot_be_rebound_after_approval(self):
        s,p,a=self.grant_fixture();s['inherited']['saved']['sha256']='b'*64
        with patch.object(m,'read',side_effect=[p,a]):
            with self.assertRaises(ValueError):m.correction_grant(s)


if __name__=='__main__':unittest.main()
