"""Small CPU tensors only, no model/optimizer/backward/CUDA operations."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import io
import json
import mmap
import os
from pathlib import Path
import random
import unittest
from unittest.mock import patch
import numpy as np
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, learning_rate_prefix
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.protocol import Profile, identity, digest
from yuntapr.experimental.phase_b_v2_integration.controls import synthetic_epoch_order
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.checkpoint import SCHEMA, Schedule
from yuntapr.experimental.phase_b_v2_p1_integration_candidate.contract import Contract
from yuntapr.experimental.phase_b_v2_p1_integration_candidate.scope import Workspace
from yuntapr.experimental.phase_b_v2_p1_integration_candidate import checkpoint as cp


def fixture():
    profile = Profile('SYNTHETIC_SMALL', 2, 2)
    spec = RunSpec(experiment_id='E0', model='B0_MATCHED_V2', seed=2026)
    ident = identity(spec, profile, {k: digest('ARTIFICIAL_'+k) for k in
                                   ('data','qualification','scaler','mask','sp04','protocol','resource')})
    model = {k: torch.ones(2, dtype=torch.float32) for k in ('backbone.weight','occ.weight','qr.weight')}
    group = dict(params=[0,1,2], lr=learning_rate_prefix(1), betas=(.9,.999), eps=1e-8,
                 weight_decay=.01, amsgrad=False, maximize=False, capturable=False,
                 differentiable=False, foreach=False, fused=False)
    template = dict(param_groups=[group], _shapes={i:(2,) for i in range(3)})
    opt = dict(param_groups=[group], state={i:dict(step=torch.tensor(1.), exp_avg=torch.zeros(2),
                                                exp_avg_sq=torch.ones(2)) for i in range(3)})
    name, keys, pos, gauss, cache = np.random.RandomState(2026).get_state()
    rng = dict(python=random.Random(2026).getstate(), numpy=dict(name=name,
               keys=torch.tensor(keys.astype(np.int64)), pos=pos, gauss=gauss, cache=cache),
               cpu=torch.Generator().manual_seed(2026).get_state(), cuda=[])
    report = dict(complete=True, source_sha=digest(ident), ids_sha=digest(profile.ids('development')),
                  summary=dict(scenes=2, n_valid=6860))
    report['receipt_sha'] = digest(report)
    schedule = Schedule(); schedule.completed = 1
    initial = digest('ARTIFICIAL_INITIAL')
    payload = dict(schema=SCHEMA, identity=ident, model=model, optimizer=opt,
                   scheduler=schedule.state_dict(), rng=rng, initial_sha=initial, epoch=1, update=1,
                   train=dict(scenes=2,batches=1,mode='SYNTHETIC_SMALL',
                              ids_sha=digest(synthetic_epoch_order(profile.ids('train'),2026,0))),
                   validation=report,parent_last_sha=None,
                   quota=dict(FORMAL_OPTIMIZER_STEPS=0,hard_limit=4,reserved=1))
    return payload, Contract(ident,model,template,initial)


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Workspace(); self.addCleanup(self.workspace.close)
        self.payload, self.contract = fixture()
        self.store = cp.Store(self.workspace,self.contract)
        # Fail loudly if any inherited validator tries to query GPU topology.
        self.gpu = patch.multiple(torch.cuda, is_available=unittest.mock.Mock(side_effect=AssertionError('GPU')),
                                  device_count=unittest.mock.Mock(side_effect=AssertionError('GPU')),
                                  get_rng_state_all=unittest.mock.Mock(side_effect=AssertionError('GPU')))
        self.gpu.start(); self.addCleanup(self.gpu.stop)

    def committed(self): return self.store.save('artificial_LAST',self.payload)

    def test_roundtrip_complete_state_and_fixture_restore(self):
        commit = self.committed(); target = cp.FixtureState()
        self.store.restore_fixture(commit.reference,target,epoch=1,update=1,last_sha=commit.payload_sha)
        self.assertTrue(torch.equal(target.value['model']['qr.weight'], self.payload['model']['qr.weight']))
        self.assertEqual(target.value['scheduler'], self.payload['scheduler'])
        self.assertEqual(target.value['validation'], self.payload['validation'])

    def test_deserializer_receives_only_verified_bytesio(self):
        commit=self.committed(); real=torch.load
        def load(stream,**kw):
            self.assertIs(type(stream),io.BytesIO); self.assertTrue(kw['weights_only'])
            self.assertEqual(kw['map_location'],'cpu'); self.assertEqual(cp.sha(stream.getvalue()),commit.payload_sha)
            return real(stream,**kw)
        with patch.object(cp.torch,'load',side_effect=load): self.store.read(commit.reference)

    def test_post_verification_replacement_uses_original_bytes(self):
        commit=self.committed(); original=torch.load
        def replaced(stream,**kw):
            part=self.workspace.file('replacement.bin'); part.write_bytes(b'REPLACED_AFTER_SHA')
            part.replace(commit.payload)
            return original(stream,**kw)
        with patch.object(cp.torch,'load',side_effect=replaced):
            result=self.store.read(commit.reference)
        self.assertEqual(result['epoch'],1)
        with self.assertRaises(ValueError): self.store.read(commit.reference)

    def test_replacement_same_content_new_object_rejected(self):
        commit=self.committed(); temp=self.workspace.file('replace.bin')
        temp.write_bytes(commit.payload.read_bytes()); temp.replace(commit.payload)
        with patch.object(cp.torch,'load',side_effect=AssertionError('No deserialize')):
            with self.assertRaises(ValueError): self.store.read(commit.reference)

    def test_truncated_payload_stops_before_deserialize(self):
        commit=self.committed(); commit.payload.write_bytes(b'partial')
        with patch.object(cp.torch,'load',side_effect=AssertionError('No deserialize')):
            with self.assertRaises(ValueError): self.store.read(commit.reference)

    def test_sha_mismatch_even_when_object_metadata_pinned(self):
        commit=self.committed()
        # Fault injection only: corrupted registry SHA, unchanged valid bytes.
        bad=replace(commit,payload_sha='f'*64)
        self.store._registered[str(commit.reference)]=bad
        with self.assertRaises(ValueError): self.store.read(commit.reference)

    def test_receipt_tamper_rejected(self):
        commit=self.committed(); commit.reference.write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError): self.store.read(commit.reference)

    def test_orphan_and_restart_registry_not_adopted(self):
        commit=self.committed(); fresh=cp.Store(self.workspace,self.contract)
        with patch.object(cp,'ReadHandle',side_effect=AssertionError('No open')):
            with self.assertRaises(PermissionError): fresh.read(commit.reference)

    def test_lexical_reject_before_file_api(self):
        with patch.object(cp,'ReadHandle',side_effect=AssertionError('No file API')):
            for path in (self.workspace.root/'2025.ref.json',self.workspace.root/'..'/'x.ref.json',
                         Path('C:/private/LAST.ref.json'), Path('relative.ref.json')):
                fresh=cp.Store(self.workspace,self.contract)
                with self.assertRaises(PermissionError): fresh.read(path)

    def test_reject_year_on_save_before_serialize(self):
        with patch.object(cp.torch,'save',side_effect=AssertionError('No serialize')):
            with self.assertRaises(PermissionError): self.store.save('LAST_2025',self.payload)

    def test_foreign_pathlike_not_invoked(self):
        class Poison:
            def __fspath__(self): raise AssertionError('No fspath')
        with self.assertRaises(PermissionError): self.store.read(Poison())

    def test_handle_blocks_writes_and_rename_during_read(self):
        commit=self.committed(); real=cp.ReadHandle.readinto; probed=[]
        def inject(h,buf):
            if h.final_path==str(commit.payload) and not probed:
                probed.append(True)
                with self.assertRaises(OSError):
                    with commit.payload.open('r+b') as stream: stream.write(b'x')
                part=self.workspace.file('rename.bin');part.write_bytes(b'x')
                with self.assertRaises(OSError): part.replace(commit.payload)
            return real(h,buf)
        with patch.object(cp.ReadHandle,'readinto',inject): self.store.read(commit.reference)
        self.assertTrue(probed)

    def test_existing_write_handle_prevents_read(self):
        commit=self.committed()
        with commit.payload.open('r+b'):
            with self.assertRaises(OSError): self.store.read(commit.reference)

    def test_metadata_change_detected(self):
        commit=self.committed(); real=cp.ReadHandle.snapshot
        def changed(h):
            row=real(h)
            if h.final_path==str(commit.payload): row['mtime_100ns']+=1
            return row
        with patch.object(cp.ReadHandle,'snapshot',changed):
            with self.assertRaises(ValueError):self.store.read(commit.reference)

    def test_sha_detects_concurrent_mapped_write(self):
        commit=self.committed()
        # Windows writable mapping can outlive its original file handle: deny-
        # share alone is insufficient; SHA must still protect consumed bytes.
        with commit.payload.open('r+b') as stream: mapping=mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_WRITE)
        self.addCleanup(mapping.close)
        real=cp.ReadHandle.readinto; done=[]
        def modify(h,buf):
            if h.final_path==str(commit.payload) and not done:
                done.append(True); mapping[0:1]=bytes([mapping[0]^1]); mapping.flush()
            return real(h,buf)
        with patch.object(cp.ReadHandle,'readinto',modify), patch.object(cp.torch,'load',side_effect=AssertionError('No deserialize')):
            with self.assertRaises((ValueError,OSError)):self.store.read(commit.reference)

    def test_failed_store_cannot_retry(self):
        commit=self.committed();commit.payload.write_bytes(b'x')
        with self.assertRaises(ValueError):self.store.read(commit.reference)
        with self.assertRaises(PermissionError):self.store.read(commit.reference)
        with self.assertRaises(PermissionError):self.store.save('another',self.payload)

    def test_save_failure_orphan_not_adopted(self):
        with self.assertRaises(OSError):self.store.save('orphan',self.payload,fault='after_blob')
        self.assertTrue(self.workspace.file('orphan.pt').exists())
        with self.assertRaises(PermissionError):self.store.read(self.workspace.file('orphan.ref.json'))

    def test_complete_validator_rejects_fields_and_no_mutation(self):
        changes = [('model',lambda p:p['model'].pop('qr.weight')),
                   ('optimizer',lambda p:p.pop('optimizer')),
                   ('moments',lambda p:p['optimizer']['state'][0].pop('exp_avg')),
                   ('step',lambda p:p['optimizer']['state'][0].update(step=torch.tensor(2.))),
                   ('schedule',lambda p:p['scheduler'].update(completed=2)),
                   ('rng',lambda p:p['rng'].update(cuda=[torch.zeros(1,dtype=torch.uint8)])),
                   ('epoch',lambda p:p.update(epoch=2)),('update',lambda p:p.update(update=0)),
                   ('validation',lambda p:p['validation'].update(complete=False)),
                   ('source',lambda p:p['identity'].update(code_sha='f'*64)),
                   ('nan',lambda p:p['model']['occ.weight'].fill_(float('nan')))]
        for label,alter in changes:
            with self.subTest(field=label):
                p=deepcopy(self.payload);alter(p)
                with self.assertRaises((ValueError,KeyError,TypeError)):self.contract.validate(p)

    def test_invalid_loaded_payload_cannot_mutate_fixture(self):
        commit=self.committed(); target=cp.FixtureState()
        p=deepcopy(self.payload);p['optimizer']['state'].pop(1)
        with patch.object(cp.torch,'load',return_value=p):
            with self.assertRaises(ValueError):self.store.restore_fixture(commit.reference,target,epoch=1,update=1,last_sha=commit.payload_sha)
        self.assertIsNone(target.value)

    def test_no_budget_rollback_or_wrong_last(self):
        commit=self.committed();target=cp.FixtureState()
        with self.assertRaises(ValueError):self.store.restore_fixture(commit.reference,target,epoch=0,update=0,last_sha='f'*64)
        self.assertIsNone(target.value)

    def test_no_live_model_target(self):
        commit=self.committed()
        with self.assertRaises(PermissionError):self.store.restore_fixture(commit.reference,object(),epoch=1,update=1,last_sha=commit.payload_sha)

    def test_receipt_strict_parser(self):
        commit=self.committed();row=json.loads(commit.reference.read_bytes())
        faults=[dict(row,bytes=True),dict(row,bytes=cp.MAX_PAYLOAD+1),dict(row,filename='../old.pt'),
                dict(row,filename='2025.pt'),dict(row,sha256='bad'),dict(row,scope='APPROVED'),
                dict(row,extra=1),dict(row,workspace_key='x')]
        for p in faults:
            with self.subTest(row=p):
                with self.assertRaises(ValueError):cp.parse_receipt(json.dumps(p).encode())
        with self.assertRaises(ValueError):cp.parse_receipt(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):cp.parse_receipt(b' '* (cp.MAX_RECEIPT+1))

    def test_storage_admission_stop(self):
        with patch.object(cp.shutil,'disk_usage',return_value=type('D',(),{'free':0})()):
            with self.assertRaises(RuntimeError):self.committed()

    def test_save_registration_replacement_is_rejected(self):
        old=cp.SyntheticStore.save
        def swap(store,*args,**kwargs):
            ref=old(store,*args,**kwargs)
            temp=self.workspace.file('swapped.bin');temp.write_bytes(b'FOREIGN_BYTES')
            temp.replace(store._path(args[0]))
            return ref
        with patch.object(cp.SyntheticStore,'save',swap):
            with self.assertRaises(ValueError):self.committed()
        self.assertTrue(self.store.failed)

    def test_contract_cannot_adopt_approved_flags(self):
        identity=deepcopy(self.contract._identity);identity['flags']['V2_PHASE_B_AUTHORIZED']=True
        with self.assertRaises(PermissionError):
            Contract(identity,self.contract._model,self.contract._optimizer,self.contract._initial)

    def test_payload_sha_stops_even_if_metadata_fault_is_hidden(self):
        commit=self.committed();data=bytearray(commit.payload.read_bytes());data[0]^=1
        commit.payload.write_bytes(data)
        # Emulate an attacker hiding metadata change: SHA is independently required.
        with cp.ReadHandle(str(commit.payload),payload=True) as h: current=dict(h.before)
        self.store._registered[str(commit.reference)]=replace(commit,payload_object=current)
        with patch.object(cp.torch,'load',side_effect=AssertionError('No deserialize')):
            with self.assertRaisesRegex(ValueError,'Payload SHA mismatch'):self.store.read(commit.reference)

    def test_payload_size_bound_before_read(self):
        path=self.workspace.file('oversized.pt');path.write_bytes(b'x'*(cp.MAX_PAYLOAD+1))
        with patch.object(cp.ReadHandle,'readinto',side_effect=AssertionError('No payload read')):
            with self.assertRaisesRegex(ValueError,'File size bound'):self.store._bytes(path,cp.MAX_PAYLOAD)


if __name__=='__main__': unittest.main(verbosity=2)
