"""Targeted synthetic boundary checks; no models or real observation access."""
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import netCDF4
import numpy as np
import torch

ROOT = Path(__file__).absolute().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_real_forward_pilot import LIMITS, SCOPE, formal_entry
from yuntapr.experimental.phase_b_v2_real_forward_pilot import resources, adapter
from yuntapr.experimental.phase_b_v2_real_forward_pilot.plan import sha, FrozenPlan
from yuntapr.experimental.phase_b_v2_real_forward_pilot.adapter import RealBatch, VerifiedReader
from yuntapr.experimental.phase_b_v2_real_forward_pilot.pilot import inference_only_operations, validate_output
from yuntapr.experimental.phase_b_v2_full_payload_integrity.audit import Scope, canonical
from yuntapr.models.quantile_v2.outputs import LogDomainOutput
from yuntapr.training.phase_a_protocol import state_digest

LOW = dict(working_set_bytes=64*1024**2, peak_working_set_bytes=64*1024**2, private_bytes=0, peak_pagefile_bytes=0)
PAYLOAD = b'only synthetic bytes'
PATH = 'F:/synthetic_b13/202303/synthetic.nc'

class FakeHandle:
    """The only handle used in these tests; never touches a real source path."""
    def __init__(self, path, **kwargs):
        self.final_path = path; self.before = {'size': len(PAYLOAD)}; self.done = False
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def close(self): pass
    def snapshot(self): return self.before.copy()
    def readinto(self, target):
        if self.done: return 0
        target[:] = PAYLOAD; self.done = True; return len(target)

class Tests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.folder = tempfile.TemporaryDirectory()
        self.memory = patch.object(resources, 'memory', return_value=LOW); self.memory.start()
        self.budget = resources.Budget(Path(self.folder.name))
        scope = Scope({'B13': 'F:/synthetic_b13', 'IMERG': 'F:/synthetic_imerg'})
        scope.register(PATH, 'B13', 2023, sha(PAYLOAD), len(PAYLOAD))
        self.plan = SimpleNamespace(scope=scope, mask_ref={'path': 'F:/synthetic_mask/mask.nc', 'sha256': 'a'*64})
        self.reader = VerifiedReader(self.plan, self.budget)
    def tearDown(self):
        self.reader.close(); self.budget.close(); self.memory.stop(); self.folder.cleanup()

    def test_exact_source_same_bytes(self):
        with patch.object(adapter, 'ReadHandle', FakeHandle):
            result = self.reader.read(PATH)
        self.assertIs(type(result), bytes); self.assertEqual(result, PAYLOAD)
        self.assertEqual(self.budget.bytes, len(PAYLOAD))
        self.assertEqual(self.reader.reads[0]['actual_sha256'], sha(result))
        self.assertTrue(self.reader.reads[0]['open_success'])
    def test_sha_failure_stops(self):
        self.plan.scope.entries[canonical(PATH)] = ('B13', 2023, 'b'*64, len(PAYLOAD))
        with patch.object(adapter, 'ReadHandle', FakeHandle), self.assertRaisesRegex(ValueError, 'SHA_MISMATCH'):
            self.reader.read(PATH)
        self.assertTrue(self.budget.stopped)
        self.assertEqual(self.budget.bytes, len(PAYLOAD))
        with self.assertRaises(RuntimeError): self.budget.check()
    def test_changed_handle_stops(self):
        class Changed(FakeHandle):
            def snapshot(self): return {'size': len(PAYLOAD)+1}
        with patch.object(adapter, 'ReadHandle', Changed), self.assertRaisesRegex(ValueError, 'CHANGED'):
            self.reader.read(PATH)
    def test_short_read_stops(self):
        class Empty(FakeHandle):
            def readinto(self, target): return 0
        with patch.object(adapter, 'ReadHandle', Empty), self.assertRaises(EOFError): self.reader.read(PATH)
    def test_wrong_size_no_content(self):
        class Wrong(FakeHandle):
            def __init__(self, *a, **k): super().__init__(*a, **k); self.before['size'] += 1
        with patch.object(adapter, 'ReadHandle', Wrong), self.assertRaisesRegex(ValueError, 'SIZE'):
            self.reader.read(PATH)
        self.assertEqual(self.budget.bytes, 0)
    def test_read_permission_failure(self):
        with patch.object(adapter, 'ReadHandle', side_effect=PermissionError('denied')), self.assertRaises(PermissionError):
            self.reader.read(PATH)
        self.assertFalse(self.reader.reads[0]['open_success']); self.assertTrue(self.budget.stopped)
    def test_forbidden_paths_no_handle(self):
        for path in ('F:/synthetic_b13/202503/a.nc', 'F:/synthetic_other/202303/a.nc',
            'F:/synthetic_b13/202303/../202303/synthetic.nc', 'F:/synthetic_b13/202303/a.pt',
            'F:/synthetic_b13/202303/synthetic.nc:stream', '//server/202303/a.nc'):
            with self.subTest(path=path), patch.object(adapter, 'ReadHandle') as call, self.assertRaises(PermissionError):
                self.reader.read(path)
            call.assert_not_called()
    def test_mask_no_reselection(self):
        with patch.object(adapter, 'ReadHandle') as call, self.assertRaises(PermissionError):
            self.reader.read('F:/synthetic_mask/other.nc')
        call.assert_not_called()
    def test_byte_cap_before_read(self):
        self.budget.bytes = LIMITS['max_content_bytes']-1
        with patch.object(adapter, 'ReadHandle', FakeHandle), self.assertRaisesRegex(MemoryError, 'FOUR_GIB'):
            self.reader.read(PATH)
    def test_immutable_memory_view(self):
        ds = netCDF4.Dataset('synthetic', 'w', diskless=True, persist=False, memory=1000)
        ds.createDimension('x', 2); ds.createVariable('x', 'f4', ('x',))[:] = [1, 2]
        raw = bytes(ds.close())
        with self.reader.view(raw, 'pilot_test.nc') as view:
            with view('pilot_test.nc') as decoded: np.testing.assert_array_equal(decoded['x'][:], [1, 2])
            with self.assertRaises(PermissionError): view('F:/synthetic_b13/202303/a.nc')
            with self.assertRaises(PermissionError): view('pilot_test.nc', 'r')
    def test_mutable_memory_rejected(self):
        with self.assertRaises(PermissionError):
            with self.reader.view(bytearray(PAYLOAD), 'pilot_test.nc'): pass
    def test_time_cap(self):
        self.budget.start -= 1801
        with self.assertRaises(TimeoutError): self.budget.check()
    def test_working_set_cap(self):
        with patch.object(resources, 'memory', return_value={**LOW, 'peak_working_set_bytes': 3*1024**3+1}), self.assertRaises(MemoryError):
            self.budget.check()
    def test_immutable_buffer_reservation(self):
        with patch.object(resources, 'memory', return_value={**LOW, 'working_set_bytes': 3*1024**3-1}), patch.object(adapter, 'ReadHandle', FakeHandle), self.assertRaisesRegex(MemoryError, 'RESERVATION'):
            self.reader.read(PATH)
    def test_forward_budget_exact_48(self):
        for pair in range(24):
            for kind in ('B0_MATCHED_V2', 'B1_V2'):
                self.budget.reserve_forward(kind, pair, 2); self.budget.complete_forward(kind)
        self.assertEqual(sum(self.budget.successes.values()), 48)
        with self.assertRaises(RuntimeError): self.budget.reserve_forward('B0_MATCHED_V2', 24, 2)
    def test_forward_failure_cannot_continue(self):
        self.budget.reserve_forward('B0_MATCHED_V2', 0, 2)
        with self.assertRaises(RuntimeError): self.budget.reserve_forward('B1_V2', 0, 2)
    def test_forward_order(self):
        with self.assertRaises(RuntimeError): self.budget.reserve_forward('B1_V2', 0, 2)
    def test_tail_must_remain_two(self):
        with self.assertRaises(ValueError): self.budget.reserve_forward('B0_MATCHED_V2', 0, 1)
    def test_duplicate_success(self):
        self.budget.reserve_forward('B0_MATCHED_V2', 0, 2); self.budget.complete_forward('B0_MATCHED_V2')
        with self.assertRaises(RuntimeError): self.budget.complete_forward('B0_MATCHED_V2')
    def test_cuda_free_and_bf16_checks(self):
        with patch('torch.cuda.is_available', return_value=True), patch('torch.cuda.is_bf16_supported', return_value=True), patch('torch.cuda.mem_get_info', return_value=(5*1024**3-1, 8*1024**3)), self.assertRaises(MemoryError):
            resources.cuda_admission()
        with patch('torch.cuda.is_available', return_value=False), self.assertRaises(RuntimeError): resources.cuda_admission()
    def test_formal_boolean_never_unlocks(self):
        with self.assertRaises(PermissionError): formal_entry(approved=True)
    def test_no_grad_optimizer_or_weights(self):
        with inference_only_operations():
            for call in (lambda: torch.ones(1).backward(), lambda: torch.autograd.grad([], []),
                         lambda: torch.optim.Optimizer([], {}), lambda: torch.load('forbidden'),
                         lambda: torch.save({}, 'forbidden')):
                with self.assertRaises(PermissionError): call()
    def test_lazy_dynamo_rules_under_protection(self):
        with inference_only_operations():
            import torch._dynamo.trace_rules
            self.assertTrue(torch._dynamo.trace_rules.get_torch_obj_rule_map())
    def test_pre_access_carry_cannot_retry_real_forward(self):
        folder = Path(self.folder.name)/'extra'; folder.mkdir()
        with self.assertRaises(PermissionError):
            resources.Budget(folder, carry={'raw_payload_content_bytes':0,'model_forward_attempts':1})
    def output(self):
        q = (torch.arange(32, dtype=torch.float64)/32+.2).view(1,32,1,1).expand(2,32,100,100).clone()
        logit = torch.zeros(2,1,100,100, dtype=torch.bfloat16)
        return LogDomainOutput(logit, logit.sigmoid(), q, (2,48,501,501), (2,48,100,100),
            torch.ones_like(logit), torch.zeros(2,1), torch.ones(2,1))
    def test_output_contract(self):
        result = validate_output(self.output(), 2, torch.device('cpu'))
        self.assertTrue(result['strictly_monotone']); self.assertFalse(result['scientific_performance_evidence'])
    def test_output_fp64_required(self):
        output = self.output(); output.conditional_quantiles_log = output.conditional_quantiles_log.float()
        with self.assertRaises(ValueError): validate_output(output, 2, torch.device('cpu'))
    def test_output_nonfinite(self):
        output = self.output(); output.conditional_quantiles_log[0,0,0,0] = float('nan')
        with self.assertRaises(FloatingPointError): validate_output(output, 2, torch.device('cpu'))
    def test_output_order_no_repair(self):
        output = self.output(); output.conditional_quantiles_log[:,1] = output.conditional_quantiles_log[:,0]
        with self.assertRaises(FloatingPointError): validate_output(output, 2, torch.device('cpu'))
    def test_output_support_no_repair(self):
        output = self.output(); output.conditional_quantiles_log[:,0] = 0
        with self.assertRaises(FloatingPointError): validate_output(output, 2, torch.device('cpu'))
    def test_output_precision(self):
        output = self.output(); output.rain_prob = output.rain_prob.float()
        with self.assertRaises(ValueError): validate_output(output, 2, torch.device('cpu'))
    def test_output_sigmoid(self):
        output = self.output(); output.rain_prob[:] = 0
        with self.assertRaises(ValueError): validate_output(output, 2, torch.device('cpu'))
    def test_output_geographic_support(self):
        output = self.output(); output.target_support_fraction[0,0,0,0] = .5
        with self.assertRaises(ValueError): validate_output(output, 2, torch.device('cpu'))
    def batch(self):
        owner = object(); x = torch.zeros(2,1,501,501); y = torch.zeros(2,1,100,100)
        valid = torch.ones_like(y, dtype=torch.bool); region = torch.zeros_like(valid)
        region.flatten(1)[:,:3430] = True  # explicitly synthetic test geography
        return RealBatch(x, torch.ones_like(x,dtype=torch.bool), y, valid, region, ('s1','s2'),
            state_digest(x), state_digest({'rate':y,'valid':valid,'region':region}), owner), owner
    def test_synthetic_contract_fixture(self):
        value, owner = self.batch(); value.validate('B0_MATCHED_V2', owner)
    def test_source_owner_rejected(self):
        value, owner = self.batch()
        with self.assertRaises(PermissionError): value.validate('B0_MATCHED_V2', object())
    def test_input_identity_rejected(self):
        value, owner = self.batch(); value.x[0,0,0,0] = 1
        with self.assertRaisesRegex(ValueError, 'INPUT_IDENTITY'): value.validate('B0_MATCHED_V2', owner)
    def test_same_count_geography_tampering_rejected(self):
        value, owner = self.batch(); value.region.flatten(1)[:,0] = False; value.region.flatten(1)[:,4000] = True
        with self.assertRaisesRegex(ValueError, 'GEOGRAPHY_CHANGED'): value.validate('B0_MATCHED_V2', owner)
    def test_FP32_threshold_boundary(self):
        y = np.array([np.nextafter(np.float32(.1),np.float32(0)), np.float32(.1), np.nextafter(np.float32(.1),np.float32(1))])
        self.assertEqual((torch.from_numpy(y) > torch.tensor(.1,dtype=torch.float32)).tolist(), [False,False,True])

if __name__ == '__main__': unittest.main(verbosity=2)
