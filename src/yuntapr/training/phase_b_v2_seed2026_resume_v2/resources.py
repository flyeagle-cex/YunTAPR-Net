"""Automated hard bounds; no precision, model or batch fallback."""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
import json
import os
import shutil
import time
from pathlib import Path
from yuntapr.experimental.phase_b_v2_real_forward_pilot.resources import memory, utcnow
from .protocol import LIMITS, LOCAL, atomic_json

class GlobalMemory(C.Structure):
    _fields_=[('length',W.DWORD),('load',W.DWORD)]+[(k,C.c_uint64) for k in
        ('total_phys','available_phys','total_page','available_page','total_virtual','available_virtual','extended')]

def system_memory() -> dict:
    m=GlobalMemory(); m.length=C.sizeof(m)
    if not C.windll.kernel32.GlobalMemoryStatusEx(C.byref(m)): raise C.WinError()
    return {k:int(getattr(m,k)) for k in ('total_phys','available_phys','total_page','available_page')}

def host_admission() -> dict:
    m=system_memory(); free=shutil.disk_usage(LOCAL).free
    if m['available_phys']<LIMITS['minimum_available_ram_bytes']: raise MemoryError('AVAILABLE_RAM_LIMIT')
    if m['available_page']<LIMITS['minimum_available_commit_bytes']: raise MemoryError('AVAILABLE_COMMIT_LIMIT')
    if free<LIMITS['minimum_disk_free_bytes']: raise OSError('DISK_FREE_LIMIT')
    return dict(**m,disk_free_bytes=free)

class Budget:
    def __init__(self):
        ancestor=json.loads((LOCAL.parent/'ancestor.json').read_bytes())
        self.start=time.monotonic()-ancestor['elapsed_seconds']; self.bytes=ancestor['content_bytes']; self.stopped=False
        self.events=(LOCAL/'access_and_events.jsonl').open('xb'); self.last_heartbeat=0
        self.cuda_peak_allocated=self.cuda_peak_reserved=0
    def emit(self, event: str, **fields) -> None:
        line=(json.dumps(dict(event=event,utc=utcnow(),**fields),allow_nan=False)+'\n').encode()
        self.events.write(line); self.events.flush()
        # Critical state/step reservations have their own FULL SQLite transaction.
        # Audit file fsync per completed step; chunk events flush only to avoid
        # duplicating a physical disk barrier for every 8MiB content chunk.
        if event in ('STEP_RETURNED','FAILED','EPOCH_LAST_COMMITTED','READ_FINISHED'):
            os.fsync(self.events.fileno())
    def check(self) -> dict:
        if self.stopped: raise RuntimeError('CAMPAIGN_STOPPED')
        if time.monotonic()-self.start>LIMITS['max_seconds']: raise TimeoutError('FIXED_SEVEN_DAY_TIME_CAP')
        m=memory()
        if m['working_set_bytes']>LIMITS['max_working_set_bytes'] or m['private_bytes']>LIMITS['max_process_commit_bytes']:
            raise MemoryError('WORKER_MEMORY_LIMIT')
        if time.monotonic()-self.last_heartbeat>=2:
            host_admission()
            import sys
            torch=sys.modules.get('torch')
            if torch is not None and torch.cuda.is_initialized():
                self.cuda_peak_allocated=max(self.cuda_peak_allocated,torch.cuda.max_memory_allocated())
                self.cuda_peak_reserved=max(self.cuda_peak_reserved,torch.cuda.max_memory_reserved())
                if torch.cuda.memory_reserved()>LIMITS['max_cuda_reserved_bytes']: raise MemoryError('CUDA_RESERVED_LIMIT')
            atomic_json(LOCAL/'heartbeat.json',dict(utc=utcnow(),elapsed_seconds=time.monotonic()-self.start,
                content_bytes=self.bytes,cpu=m,cuda_peak_allocated=self.cuda_peak_allocated,
                cuda_peak_reserved=self.cuda_peak_reserved))
            self.last_heartbeat=time.monotonic()
        return m
    def admit_bytes(self,size: int) -> None:
        self.check()
        if type(size) is not int or size<=0 or self.bytes+size>LIMITS['max_read_bytes']:
            raise MemoryError('FIXED_CONTENT_READ_LIMIT')
    def account_bytes(self,size: int) -> None:
        if type(size) is not int or size<0 or self.bytes+size>LIMITS['max_read_bytes']:
            raise MemoryError('FIXED_CONTENT_READ_LIMIT')
        self.bytes+=size
    def cuda_admission(self) -> dict:
        import torch
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported(): raise RuntimeError('CUDA_BF16_REQUIRED')
        free,total=torch.cuda.mem_get_info()
        if free<LIMITS['minimum_cuda_free_bytes']: raise MemoryError('CUDA_FREE_ADMISSION_LIMIT')
        torch.cuda.set_per_process_memory_fraction(LIMITS['max_cuda_reserved_bytes']/total)
        return dict(free_bytes=free,total_bytes=total,name=torch.cuda.get_device_name(),torch_version=str(torch.__version__))
    def close(self):
        self.events.flush(); os.fsync(self.events.fileno()); self.events.close()
