"""New smoke safeguards only: no raw data, full models or optimizer updates."""
import io
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
import torch
from yuntapr.experimental.phase_b_v2_real_train_smoke import MODELS,OUT,formal_entry
from yuntapr.experimental.phase_b_v2_real_train_smoke.quota import QuotaCore
from yuntapr.experimental.phase_b_v2_real_train_smoke.checkpoint import SmokeStore,SCHEMA,formal_restore
from yuntapr.experimental.phase_b_v2_real_train_smoke.operations import guarded_operations
from yuntapr.experimental.phase_b_v2_real_train_smoke.data import SmokeAdapter
from yuntapr.experimental.phase_b_v2_real_train_smoke.run import optimizer_check,gradients

TEST_TEMP=OUT/'.local/development/unit_temp'
TEST_TEMP.mkdir(parents=True,exist_ok=True)

class OwnedTemp:
    """Inherit workspace ACLs; Windows tempfile mode 0700 rejects sandbox token."""
    def __init__(self):
        path=TEST_TEMP/('unit_'+uuid.uuid4().hex)
        path.mkdir(); self.name=str(path)
    def cleanup(self):
        path=Path(self.name).resolve()
        if path.parent!=TEST_TEMP.resolve() or not path.name.startswith('unit_'):
            raise PermissionError('UNIT_TEST_CLEANUP_OUTSIDE_OWNED_WORKSPACE')
        shutil.rmtree(path)

class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp=OwnedTemp(); self.path=Path(self.temp.name)/'quota.sqlite'
        self.q=QuotaCore(self.path,create=True,campaign='UNIT_TEST_NO_REAL_PERMISSION')
    def tearDown(self): self.q.close(); self.temp.cleanup()
    def stage(self,model):
        for stage in ('forward','backward','step'): self.q.reserve(model,stage)
    def test_full_two_transaction_logic_without_updates(self):
        for model in MODELS:
            self.stage(model); self.q.entered(model); self.q.returned(model); self.q.completed(model)
        self.q.seal(False); self.assertEqual(self.q.snapshot()['returned_optimizer_calls'],2)
        with self.assertRaises(PermissionError): self.q.reserve(MODELS[0],'step')
    def test_no_out_of_order_step(self):
        with self.assertRaises(PermissionError): self.q.reserve(MODELS[0],'step')
    def test_b1_requires_b0_complete(self):
        with self.assertRaises(PermissionError): self.q.reserve(MODELS[1],'forward')
    def test_duplicate_forward(self):
        self.q.reserve(MODELS[0],'forward')
        with self.assertRaises(PermissionError): self.q.reserve(MODELS[0],'forward')
    def test_unknown_model(self):
        with self.assertRaises(PermissionError): self.q.reserve('B1_NEW','forward')
    def test_unknown_stage(self):
        with self.assertRaises(PermissionError): self.q.reserve(MODELS[0],'approval')
    def test_no_unreserved_entry(self):
        with self.assertRaises(PermissionError): self.q.entered(MODELS[0])
    def test_duplicate_entry_consumed(self):
        self.stage(MODELS[0]); self.q.entered(MODELS[0])
        with self.assertRaises(PermissionError): self.q.entered(MODELS[0])
    def test_uncertain_failure_no_refund(self):
        self.stage(MODELS[0]); self.q.entered(MODELS[0]); self.q.seal(True)
        q2=QuotaCore(self.path,create=False,campaign='UNIT_TEST_NO_REAL_PERMISSION')
        try:
            self.assertEqual(q2.snapshot()['reserved_step_attempts'],1)
            with self.assertRaises(PermissionError): q2.reserve(MODELS[0],'step')
        finally: q2.close()
    def test_no_existing_ledger_reset(self):
        with self.assertRaises(FileExistsError): QuotaCore(self.path,create=True,campaign='NEW')
    def test_missing_ledger_not_recreated(self):
        with self.assertRaises(PermissionError): QuotaCore(self.path.with_name('absent'),create=False,campaign='NEW')
    def test_identity_mismatch(self):
        with self.assertRaises(PermissionError): QuotaCore(self.path,create=False,campaign='APPROVED')
    def test_no_false_completion(self):
        with self.assertRaises(PermissionError): self.q.seal(False)
    def test_no_completion_without_step_return(self):
        with self.assertRaises(PermissionError): self.q.completed(MODELS[0])
    def test_cross_process_duplicate_reservation(self):
        self.q.reserve(MODELS[0],'forward')
        script="from pathlib import Path; from yuntapr.experimental.phase_b_v2_real_train_smoke.quota import QuotaCore; import sys; q=QuotaCore(Path(sys.argv[1]),create=False,campaign='UNIT_TEST_NO_REAL_PERMISSION');\ntry: q.reserve('B0_MATCHED_V2','forward')\nexcept PermissionError: sys.exit(0)\nsys.exit(1)"
        self.assertEqual(subprocess.run([sys.executable,'-c',script,str(self.path)],capture_output=True).returncode,0)

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=OwnedTemp(); self.store=SmokeStore(Path(self.temp.name)/'owned')
        self.payload={'schema':SCHEMA,'teaching_tensor':torch.tensor([1.,2.])}
    def tearDown(self): self.temp.cleanup()
    def test_same_byte_roundtrip(self):
        ref=self.store.save('test',self.payload); result,receipt=self.store.read(ref)
        self.assertTrue(torch.equal(result['teaching_tensor'],self.payload['teaching_tensor']))
        self.assertEqual(receipt['schema'],SCHEMA)
    def test_guarded_roundtrip(self):
        with guarded_operations([self.store]):
            ref=self.store.save('test',self.payload); self.store.read(ref)
    def test_no_overwrite(self):
        self.store.save('test',self.payload)
        with self.assertRaises(FileExistsError): self.store.save('test',self.payload)
    def test_mid_save_failure_preserved(self):
        with self.assertRaises(OSError): self.store.save('test',self.payload,fault='after_serialization')
        self.assertTrue(list(self.store.root.glob('*.part'))); self.assertFalse(list(self.store.root.glob('*.ref.json')))
    def test_after_blob_failure_no_receipt(self):
        with self.assertRaises(OSError): self.store.save('test',self.payload,fault='after_blob')
        self.assertTrue((self.store.root/'test.pt').is_file()); self.assertFalse((self.store.root/'test.ref.json').exists())
    def test_lock_failure_preserves_evidence(self):
        with self.assertRaises(PermissionError): self.store.save('test',self.payload,fault='rename_locked')
        self.assertTrue(list(self.store.root.glob('*.part')))
    def test_existing_lock_not_removed(self):
        path=self.store.root/'test.lock'; path.write_text('owner')
        with self.assertRaises(FileExistsError): self.store.save('test',self.payload)
        self.assertEqual(path.read_text(),'owner')
    def test_sha_before_load(self):
        ref=self.store.save('test',self.payload); blob=self.store.root/'test.pt'; data=bytearray(blob.read_bytes()); data[-1]^=1; blob.write_bytes(data)
        with patch.object(torch,'load',side_effect=AssertionError('must not load')):
            with self.assertRaises(ValueError): self.store.read(ref)
    def test_incomplete_blob(self):
        ref=self.store.save('test',self.payload); (self.store.root/'test.pt').write_bytes(b'partial')
        with self.assertRaises(ValueError): self.store.read(ref)
    def test_2025_denied_before_readhandle(self):
        with patch('yuntapr.experimental.phase_b_v2_real_train_smoke.checkpoint.ReadHandle',side_effect=AssertionError):
            with self.assertRaises(PermissionError): self.store.read(self.store.root/'2025.ref.json')
    def test_wrong_store_before_open(self):
        with self.assertRaises(PermissionError): self.store.read(Path(self.temp.name)/'other.ref.json')
    def test_schema_missing(self):
        with self.assertRaises(ValueError): self.store.save('test',{'approved':True})
    def test_receipt_escape(self):
        ref=self.store.save('test',self.payload); record=json.loads(ref.read_bytes()); record['filename']='../old.pt'; ref.write_text(json.dumps(record))
        with self.assertRaises(ValueError): self.store.read(ref)

class GateTests(unittest.TestCase):
    def test_watchdog_actual_worker_handle(self):
        import os
        from yuntapr.experimental.phase_b_v2_real_train_smoke.launch import open_worker,K
        from yuntapr.experimental.phase_b_v2_real_train_smoke.resources import memory
        handle=open_worker(os.getpid())
        try: self.assertGreater(memory(handle)['working_set_bytes'],0)
        finally: K.CloseHandle(handle)
    def test_watchdog_invalid_pid_no_native_call(self):
        from yuntapr.experimental.phase_b_v2_real_train_smoke.launch import open_worker
        with self.assertRaises(ValueError): open_worker(0)
    def test_formal_json_cannot_enable(self):
        with self.assertRaises(PermissionError): formal_entry({'APPROVED':True})
    def test_no_smoke_formal_restore(self):
        with self.assertRaises(PermissionError): formal_restore('APPROVED')
    def test_no_unauthorized_backward(self):
        with guarded_operations([]):
            with self.assertRaises(PermissionError): torch.tensor(1.,requires_grad=True).backward()
    def test_no_unauthorized_optimizer_call(self):
        with guarded_operations([]):
            with self.assertRaises(PermissionError): torch.optim.AdamW.step(object())
    def test_no_checkpoint_path_load(self):
        with guarded_operations([]):
            with self.assertRaises(PermissionError): torch.load('not-accessed.pt',weights_only=True)
    def test_optimizer_constructor_under_guard_no_updates(self):
        from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import new_adamw
        with guarded_operations([]):
            optimizer,_=new_adamw(torch.nn.Conv2d(2,1,1))
            self.assertFalse(optimizer.state)
            with self.assertRaises(PermissionError): optimizer.step()
    def test_no_extra_scene(self):
        adapter=SmokeAdapter.__new__(SmokeAdapter)
        with self.assertRaises(PermissionError): adapter.scene(2)
    def test_no_extra_pair(self):
        adapter=SmokeAdapter.__new__(SmokeAdapter); adapter.next_scene=0
        with self.assertRaises(PermissionError): adapter.pair(1)
    def test_no_reread_pair(self):
        adapter=SmokeAdapter.__new__(SmokeAdapter); adapter.next_scene=2
        with self.assertRaises(PermissionError): adapter.pair(0)

if __name__=='__main__': unittest.main()
