"""Own smoke schema; reuse atomic transport, then deserialize verified bytes only."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import io
import json
import ntpath
import os
from pathlib import Path
import re
import shutil
import torch
from yuntapr.experimental.phase_b_v2_runner_candidate.checkpoint import SyntheticStore
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import check_finite
from yuntapr.experimental.phase_b_v2_runner_candidate import rng
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from yuntapr.training.phase_a_protocol import state_digest

SCHEMA='REAL_TRAIN_SMOKE_ENGINEERING_v1'
MAX_CHECKPOINT_BYTES=256*1024**2

class SmokeStore(SyntheticStore):
    def __init__(self, root: Path):
        # Only the caller-created dedicated directory; no historical store paths.
        self.root=root.absolute()
        self.root.mkdir(exist_ok=False)
        # Windows %TEMP% can contain an 8.3 user alias. Bind the newly created
        # directory to its handle-returned long name; never relax payload identity.
        with ReadHandle(str(self.root),directory=True) as handle:
            self.root=Path(handle.final_path)
        self._io_depth=0
    @contextmanager
    def io(self):
        self._io_depth+=1
        try: yield
        finally: self._io_depth-=1
    def save(self,name,payload,*,fault=None):
        if type(payload) is not dict or payload.get('schema')!=SCHEMA:
            raise ValueError('SMOKE_SCHEMA_REQUIRED')
        if shutil.disk_usage(self.root).free<512*1024**2: raise OSError('SMOKE_CHECKPOINT_STORAGE_LIMIT')
        # Transport reused without altering the prior synthetic implementation.
        ref=super().save(name,payload,fault=fault)
        record=json.loads(ref.read_bytes()); record['schema']=SCHEMA
        if record['bytes']>MAX_CHECKPOINT_BYTES: raise MemoryError('SMOKE_CHECKPOINT_SIZE_LIMIT')
        tmp=ref.with_suffix('.smoke.tmp')
        with tmp.open('xb') as stream:
            stream.write(json.dumps(record,sort_keys=True).encode()); stream.flush(); os.fsync(stream.fileno())
        tmp.replace(ref)
        return ref
    def read(self,reference: Path):
        # Reject path escapes/year before any resolve/stat/open, even negative tests.
        raw=os.fspath(reference)
        if ('2025' in raw or '..' in raw.replace('\\','/').split('/') or
            Path(raw).absolute().parent!=self.root or not re.fullmatch('[A-Za-z0-9_-]+\\.ref\\.json',Path(raw).name)):
            raise PermissionError('ONLY_THIS_SMOKE_COMMIT_REFERENCE')
        record=json.loads(Path(raw).read_bytes())
        if set(record)!={'schema','filename','bytes','sha256'} or record['schema']!=SCHEMA:
            raise ValueError('SMOKE_COMMIT_RECEIPT_IDENTITY')
        if (not re.fullmatch('[A-Za-z0-9_-]+\\.pt',record['filename']) or
            type(record['bytes']) is not int or not 0<record['bytes']<=MAX_CHECKPOINT_BYTES or
            not re.fullmatch('[0-9a-f]{64}',record['sha256'])):
            raise ValueError('SMOKE_COMMIT_RECEIPT_BOUNDS')
        blob=self.root/record['filename']
        with ReadHandle(str(blob),payload=True) as handle:
            if ntpath.normcase(handle.final_path)!=ntpath.normcase(str(blob)) or handle.before['size']!=record['bytes']:
                raise ValueError('SMOKE_CHECKPOINT_HANDLE_IDENTITY')
            buffer=bytearray(record['bytes']); count=0
            while count<len(buffer):
                n=handle.readinto(memoryview(buffer)[count:])
                if not n: raise EOFError('SMOKE_CHECKPOINT_TRUNCATED')
                count+=n
            if handle.snapshot()!=handle.before: raise ValueError('SMOKE_CHECKPOINT_CHANGED')
        immutable=bytes(buffer)
        if hashlib.sha256(immutable).hexdigest()!=record['sha256']:
            raise ValueError('SMOKE_CHECKPOINT_SHA_MISMATCH_NO_DESERIALIZATION')
        with self.io():
            result=torch.load(io.BytesIO(immutable),weights_only=True,map_location='cpu')
        if type(result) is not dict or result.get('schema')!=SCHEMA: raise ValueError('SMOKE_PAYLOAD_SCHEMA')
        return result,record

def validate_roundtrip(actual: dict, expected: dict):
    """Validate all state identities, without installing weights into a live model."""
    if actual.keys()!=expected.keys() or actual.get('schema')!=SCHEMA:
        raise ValueError('SMOKE_CHECKPOINT_FIELDS')
    for key in expected:
        if state_digest(actual[key])!=state_digest(expected[key]): raise ValueError('SMOKE_STATE_MISMATCH_'+key)
    check_finite(actual['model']); check_finite(actual['optimizer']); rng.validate(actual['rng'])
    progress=actual['progress']
    if progress!={'formal_epoch':0,'complete_epoch':False,'validation_complete':False,
                  'FORMAL_PHASE_B_OPTIMIZER_STEPS':0,'model_real_smoke_updates':1}:
        raise ValueError('SMOKE_IS_NOT_AN_EPOCH_OR_FORMAL_RECOVERY')

def formal_restore(*args,**kwargs):
    raise PermissionError('SMOKE_CHECKPOINT_NEVER_A_FORMAL_RESTORE_SOURCE')
