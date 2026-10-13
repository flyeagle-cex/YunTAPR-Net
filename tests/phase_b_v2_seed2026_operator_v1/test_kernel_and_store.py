"""New named-Job and same-campaign LAST reopening; artificial inputs only."""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import sys
import time
import unittest
import uuid
from unittest.mock import patch
from yuntapr.training.phase_b_v2_seed2026_operator_v1 import protocol as p
from yuntapr.training.phase_b_v2_seed2026_operator_v1.supervisor import FormalJob
from yuntapr.training.phase_b_v2_seed2026_operator_v1.control import open_owned_job
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import K,native_identity,close_handle,exited
K.GetCurrentProcess.restype=W.HANDLE


class TestKernel(unittest.TestCase):
    def fixture(self):
        nonce=uuid.uuid4().hex
        name=f'Local\\{p.CAMPAIGN}__997__{nonce}'
        job=FormalJob(name)
        identity=dict(**native_identity(K.GetCurrentProcess()),campaign=p.CAMPAIGN,nonce=nonce,session=997,job_name=name)
        return job,identity
    def test_named_owned_job_terminates_tree(self):
        job,identity=self.fixture();other=owner=None
        try:
            # Two standard-library artificial processes, no torch/data/GPU.
            job.spawn([sys.executable,'-c','import subprocess,sys,time;subprocess.Popen([sys.executable,"-c","import time;time.sleep(10)"]);time.sleep(10)'],p.ROOT)
            deadline=time.monotonic()+3
            while len(job.snapshot())<3 and time.monotonic()<deadline:time.sleep(.05)
            self.assertGreaterEqual(len(job.snapshot()),3)
            other,owner=open_owned_job(identity);other.stop()
            deadline=time.monotonic()+3
            while (other.pids() or not all(exited(h) for h in other.handles.values())) and time.monotonic()<deadline:time.sleep(.05)
            self.assertFalse(other.pids());self.assertTrue(all(exited(h) for h in other.handles.values()))
        finally:
            if other:other.close()
            if owner:close_handle(owner)
            job.stop();job.close()
    def test_wrong_creation_identity_cannot_stop(self):
        job,identity=self.fixture()
        try:
            job.spawn([sys.executable,'-c','import time;time.sleep(10)'],p.ROOT)
            identity['creation_filetime']+=1
            with self.assertRaises(PermissionError):open_owned_job(identity)
            self.assertTrue(job.pids())
        finally:job.stop();job.close()
    def test_normal_exit_job_empty(self):
        job,identity=self.fixture()
        try:
            job.spawn([sys.executable,'-c','pass'],p.ROOT)
            deadline=time.monotonic()+3
            while job.pids() and time.monotonic()<deadline:time.sleep(.05)
            self.assertFalse(job.pids());self.assertTrue(all(exited(h) for h in job.handles.values()))
        finally:job.stop();job.close()


class MinimalContract:
    key='a'*64
    def validate(self,payload):
        if set(payload)!={'fixture','tensor'} or payload['fixture']!='SYNTHETIC_METADATA_ONLY':raise ValueError('FIXTURE_CONTRACT')


class TestOwnedLast(unittest.TestCase):
    def setUp(self):
        import torch
        from yuntapr.training.phase_b_v2_seed2026_operator_v1 import checkpoint as cp
        self.cp=cp;self.local=p.ROOT/'tests/phase_b_v2_seed2026_operator_v1/.local'/uuid.uuid4().hex
        self.folder=self.local/'run';self.folder.mkdir(parents=True)
        self.patch=patch.object(cp,'LOCAL',self.local);self.patch.start()
        self.store=cp.Store(self.folder/'checkpoints',MinimalContract())
        self.ref=self.store.save('LAST_epoch_08',dict(fixture='SYNTHETIC_METADATA_ONLY',tensor=torch.tensor([1.,2.])))
        self.sha=self.store.receipt(self.ref)['payload_sha256'];self.store.close()
    def tearDown(self):self.patch.stop()
    def test_reopen_same_bytes_and_contract(self):
        store=self.cp.Store.reopen_owned(self.folder/'checkpoints',MinimalContract(),8,self.sha)
        try:self.assertEqual(store.read(self.ref)['tensor'].tolist(),[1.,2.])
        finally:store.close()
    def test_wrong_last_sha_rejected_before_load(self):
        with self.assertRaises(ValueError):self.cp.Store.reopen_owned(self.folder/'checkpoints',MinimalContract(),8,'0'*64)
    def test_truncated_payload_rejected_before_load(self):
        (self.folder/'checkpoints/LAST_epoch_08.pt').write_bytes(b'truncated')
        store=self.cp.Store.reopen_owned(self.folder/'checkpoints',MinimalContract(),8,self.sha)
        try:
            with self.assertRaises(ValueError):store.read(self.ref)
        finally:store.close()


if __name__=='__main__':unittest.main(verbosity=2)
