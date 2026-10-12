"""Only NEW recovery boundaries; no real data or full architecture is exercised."""
from __future__ import annotations
import copy
import ast
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
import torch
from yuntapr.training.phase_b_v2_seed2026_resume_v1 import quota, recovery
from yuntapr.training.phase_b_v2_seed2026_resume_v1.protocol import TOTAL,OLD_RESERVED,MAX_NEW,ABANDONED
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.checkpoint import Schedule
from yuntapr.experimental.phase_b_v2_runner_candidate import rng
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import clip_and_check
from yuntapr.training.phase_a_protocol import state_digest


@contextmanager
def fixture_directory():
    """Retain only artificial test files in this workspace; never clean ancestors."""
    base=Path(__file__).absolute().parents[2]/'docs/phase_b_v2_formal_execution/seed2026_resume_v1/.local/test_fixtures'
    base.mkdir(parents=True,exist_ok=True)
    # mkdtemp(mode=0700) on this Windows runtime denies the sandbox token even
    # under an allowed root. Ordinary inherited workspace ACLs are retained.
    path=(base/('case_'+uuid.uuid4().hex)).absolute()
    path.mkdir()
    if not path.is_relative_to(base): raise PermissionError('TEST_WORKSPACE_BOUNDARY')
    yield str(path)


class RecoveryTests(unittest.TestCase):
    def test_budget_math_without_refund(self):
        self.assertEqual(TOTAL,287540)
        self.assertEqual(OLD_RESERVED+MAX_NEW,TOTAL)
        self.assertEqual(TOTAL,282312+ABANDONED)
        self.assertEqual(MAX_NEW,6*5228+2*47052)

    def fixture(self, root):
        (root/'.git').mkdir()
        out=root/'docs/phase_b_v2_formal_execution/seed2026_v2';out.mkdir(parents=True)
        for model,arm in quota.ORDER[:3]:
            (out/(quota.run_id(model,arm)+'.json')).write_text(json.dumps({'epochs':[{'checkpoint':{'payload_sha256':'a'*64}}]}))

    def test_reserved_attempt_never_refunded_or_restarted(self):
        with fixture_directory() as t:
            root=Path(t);self.fixture(root)
            with patch.object(quota,'ROOT',root),patch.object(quota,'MAX_NEW',1):
                ledger=quota.Ledger({'ancestor_receipt_sha256':'b'*64})
                ident=quota.run_id('B1_V2','E1');ledger.start_run(ident);ledger.begin_epoch(ident,4)
                ledger.reserve(ident,15685)
                self.assertEqual(ledger.snapshot()['reserved'],162069)
                self.assertEqual(ledger.snapshot()['returned_verified'],162068)
                with self.assertRaises(PermissionError):ledger.reserve(ident,15685)
                ledger.returned(ident,15685)
                with self.assertRaises(PermissionError):ledger.reserve(ident,15686)
                ledger.fail('TEST_INTERRUPT')
                with self.assertRaises(PermissionError):ledger.start_run(ident)
                self.assertEqual(ledger.snapshot()['reserved'],162069)
                ledger.close()
                with self.assertRaises(FileExistsError):quota.Ledger({'ancestor_receipt_sha256':'b'*64})

    def test_wrong_source_path_rejected_before_native_access(self):
        with fixture_directory() as t:
            out=Path(t)
            row={'reserved':OLD_RESERVED,'verified':OLD_RESERVED,'last_sha256':recovery.LAST_SHA,
                 'source_epoch':3,'source_update':15684,'abandoned_updates':5228,'pins':{'2025/private.pt':'f'*64}}
            raw=json.dumps(row).encode();(out/'ancestor.json').write_bytes(raw)
            with patch.object(recovery,'OUT',out),patch.object(recovery,'ReadHandle') as native:
                with self.assertRaises(PermissionError):recovery.Guard(hashlib.sha256(raw).hexdigest())
                native.assert_not_called()

    def test_altered_ancestor_sha_rejected_before_native_access(self):
        with fixture_directory() as t:
            out=Path(t);(out/'ancestor.json').write_text('{}')
            with patch.object(recovery,'OUT',out),patch.object(recovery,'ReadHandle') as native:
                with self.assertRaises(ValueError):recovery.Guard('0'*64)
                native.assert_not_called()

    def test_cpu_adamw_rng_schedule_exact_next_step(self):
        # Three tiny CPU synthetic optimizer calls only: save step, control step,
        # restored step. These are NEVER formal quota reservations or full models.
        with patch.object(torch.cuda,'is_available',return_value=False),patch.object(torch.cuda,'device_count',return_value=0):
            torch.manual_seed(2026)
            control=torch.nn.Sequential(torch.nn.Linear(3,2),torch.nn.Dropout(.5))
            opt=torch.optim.AdamW(control.parameters(),lr=1e-4,foreach=False,fused=False)
            schedule=Schedule();x=torch.arange(12,dtype=torch.float32).reshape(4,3)/10
            def step(model,optim,sched):
                optim.zero_grad(set_to_none=True);sched.prepare(optim)
                model(x).square().mean().backward();clip_and_check(model);optim.step();sched.commit()
            step(control,opt,schedule)
            payload=copy.deepcopy({'model':control.state_dict(),'optimizer':opt.state_dict(),
                                   'scheduler':schedule.state_dict(),'rng':rng.capture()})
            step(control,opt,schedule)
            expected_model=state_digest(control.state_dict());expected_opt=state_digest(opt.state_dict())
            target=torch.nn.Sequential(torch.nn.Linear(3,2),torch.nn.Dropout(.5))
            target_opt=torch.optim.AdamW(target.parameters(),lr=1e-4,foreach=False,fused=False)
            target_schedule=Schedule()
            proof=recovery.apply_validated_state(target,target_opt,target_schedule,payload)
            self.assertTrue(proof['all_state_verified_before_first_resumed_step'])
            step(target,target_opt,target_schedule)
            self.assertEqual(state_digest(target.state_dict()),expected_model)
            self.assertEqual(state_digest(target_opt.state_dict()),expected_opt)
            self.assertEqual(target_schedule.state_dict(),schedule.state_dict())

    def test_no_automatic_restore_in_legacy_source(self):
        root=Path(__file__).absolute().parents[2]
        old=(root/'src/yuntapr/training/phase_b_v2_seed2026_v2/checkpoint.py').read_text(encoding='utf-8')
        self.assertIn('NEW_LAST_BOUND_HUMAN_RECOVERY_DECISION_REQUIRED',old)
        self.assertEqual(OLD_RESERVED,162068)

    def test_training_and_evaluation_arithmetic_unchanged(self):
        root=Path(__file__).absolute().parents[2]/'src/yuntapr/training'
        def functions(folder):
            tree=ast.parse((root/folder/'engine.py').read_text(encoding='utf-8'))
            engine=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Engine')
            return {n.name:ast.dump(n,include_attributes=False) for n in engine.body if isinstance(n,ast.FunctionDef)}
        old=functions('phase_b_v2_seed2026_v2');new=functions('phase_b_v2_seed2026_resume_v1')
        self.assertEqual(old['train'],new['train'])
        self.assertEqual(old['validate'],new['validate'])

    def test_original_resource_limits_not_relaxed(self):
        from yuntapr.training.phase_b_v2_seed2026_v2.protocol import LIMITS as old
        from yuntapr.training.phase_b_v2_seed2026_resume_v1.protocol import LIMITS as new
        self.assertEqual(old,new)


if __name__=='__main__': unittest.main(verbosity=2)
