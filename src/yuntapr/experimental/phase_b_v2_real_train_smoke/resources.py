"""Durable access receipts; a fresh budget has no restart/refund interface."""
from __future__ import annotations
import json
import os
from pathlib import Path
import time
import torch
from yuntapr.experimental.phase_b_v2_real_forward_pilot.resources import memory, utcnow
from . import LIMITS, SCOPE

class Budget:
    def __init__(self, folder: Path):
        self.start=time.monotonic(); self.bytes=0; self.stopped=False
        self.events=(folder/'events.jsonl').open('xb')
    def emit(self, kind: str, **values):
        self.events.write((json.dumps(dict(event=kind,utc=utcnow(),scope=SCOPE,**values),allow_nan=False)+'\n').encode())
        self.events.flush(); os.fsync(self.events.fileno())
    def check(self):
        if self.stopped: raise RuntimeError('SMOKE_ALREADY_STOPPED_NO_RETRY')
        if time.monotonic()-self.start>=LIMITS['MAX_ELAPSED_SECONDS']: raise TimeoutError('SMOKE_TIME_LIMIT')
        usage=memory()
        if usage['peak_working_set_bytes']>LIMITS['MAX_CPU_WORKING_SET_BYTES']: raise MemoryError('SMOKE_CPU_LIMIT')
        if torch.cuda.is_initialized() and torch.cuda.max_memory_reserved()>LIMITS['MAX_TORCH_CUDA_RESERVED_BYTES']:
            raise MemoryError('SMOKE_CUDA_RESERVED_LIMIT')
        return usage
    def admit_bytes(self, size: int):
        self.check()
        if type(size) is not int or size<=0 or self.bytes+size>LIMITS['MAX_REAL_CONTENT_BYTES']:
            raise MemoryError('SMOKE_CONTENT_BYTE_LIMIT')
    def account_bytes(self, size: int):
        if type(size) is not int or size<0 or self.bytes+size>LIMITS['MAX_REAL_CONTENT_BYTES']:
            raise MemoryError('SMOKE_CONTENT_BYTE_LIMIT')
        self.bytes+=size
    def close(self): self.events.close()

def cuda_admission():
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError('CUDA_BF16_REQUIRED_NO_FALLBACK')
    free,total=torch.cuda.mem_get_info(0)
    if free<LIMITS['MIN_CUDA_FREE_BYTES']: raise MemoryError('SMOKE_CUDA_ADMISSION_LIMIT')
    return dict(free_bytes=free,total_bytes=total,name=torch.cuda.get_device_name(0),
                torch_version=str(torch.__version__),cuda_build=torch.version.cuda)
