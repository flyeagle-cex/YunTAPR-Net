"""Fixed Win32 counter types, bounded counters and durable safe event receipts."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from . import LIMITS, SCOPE

class Counters(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ('peak', 'working', 'qpp', 'pp',
        'qpnp', 'pnp', 'pagefile', 'peakpagefile', 'private')]

K = ctypes.WinDLL('kernel32', use_last_error=True)
K.GetCurrentProcess.restype = wintypes.HANDLE
GET_MEMORY = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
GET_MEMORY.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
GET_MEMORY.restype = wintypes.BOOL

def memory(handle=None) -> dict:
    values = Counters(); values.cb = ctypes.sizeof(values)
    handle = K.GetCurrentProcess() if handle is None else handle
    if not GET_MEMORY(handle, ctypes.byref(values), values.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'working_set_bytes': int(values.working),
            'peak_working_set_bytes': int(values.peak),
            'private_bytes': int(values.private),
            'peak_pagefile_bytes': int(values.peakpagefile)}

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

class Budget:
    """No refund or retry: bytes/calls are charged before advancing the loop."""
    def __init__(self, folder: Path, *, carry: dict | None = None):
        self.start = time.monotonic()
        self.bytes = 0
        self.attempts = {'B0_MATCHED_V2': 0, 'B1_V2': 0}
        self.successes = {'B0_MATCHED_V2': 0, 'B1_V2': 0}
        self.stopped = False
        self.next_pair = 0
        if carry is not None:
            if (carry.get('raw_payload_content_bytes') != 0 or carry.get('model_forward_attempts') != 0
                or carry.get('reason') != 'PRE_ACCESS_DYNAMO_WRAPPER_REPAIR'):
                raise PermissionError('NO_REAL_SCENE_OR_FORWARD_RETRY')
            self.bytes = carry['public_metadata_content_bytes']
            original = datetime.fromisoformat(carry['original_started_at_utc'])
            self.start -= (datetime.now(timezone.utc)-original).total_seconds()
        self.events = (folder/'events.jsonl').open('xb')

    def emit(self, kind: str, **value) -> None:
        raw = (json.dumps(dict(event=kind, utc=utcnow(), scope=SCOPE, **value),
                          allow_nan=False) + '\n').encode()
        self.events.write(raw); self.events.flush(); os.fsync(self.events.fileno())

    def check(self) -> dict:
        if self.stopped: raise RuntimeError('PILOT_ALREADY_STOPPED')
        if time.monotonic()-self.start >= LIMITS['max_elapsed_seconds']:
            raise TimeoutError('THIRTY_MINUTE_LIMIT')
        usage = memory()
        if usage['peak_working_set_bytes'] > LIMITS['max_working_set_bytes']:
            raise MemoryError('THREE_GIB_WORKING_SET_LIMIT')
        return usage

    def admit_bytes(self, size: int) -> None:
        self.check()
        if type(size) is not int or size <= 0 or self.bytes+size > LIMITS['max_content_bytes']:
            raise MemoryError('FOUR_GIB_CONTENT_LIMIT')

    def account_bytes(self, size: int) -> None:
        if type(size) is not int or size < 0 or self.bytes+size > LIMITS['max_content_bytes']:
            raise MemoryError('FOUR_GIB_CONTENT_LIMIT')
        self.bytes += size

    def reserve_forward(self, kind: str, pair: int, size: int) -> None:
        self.check()
        if self.attempts != self.successes:
            raise RuntimeError('UNFINISHED_FORWARD_NO_CONTINUATION')
        if kind not in self.attempts or size != 2 or pair != self.next_pair:
            raise ValueError('CLOSED_BATCH_MODEL_ORDER')
        expected = 'B0_MATCHED_V2' if self.attempts['B0_MATCHED_V2'] == self.attempts['B1_V2'] else 'B1_V2'
        if kind != expected or sum(self.attempts.values()) >= 48 or self.attempts[kind]*2+size > 48:
            raise RuntimeError('MODEL_FORWARD_BUDGET_OR_ORDER')
        self.attempts[kind] += 1
        self.emit('FORWARD_RESERVED', model=kind, pair=pair, size=size,
                  attempts=self.attempts.copy())

    def complete_forward(self, kind: str) -> None:
        if kind not in self.successes or self.successes[kind]+1 != self.attempts[kind]:
            raise RuntimeError('NO_UNRESERVED_OR_DUPLICATE_SUCCESS')
        self.successes[kind] += 1
        if kind == 'B1_V2': self.next_pair += 1

    def close(self) -> None:
        self.events.close()

def cuda_admission() -> dict:
    import torch
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError('CUDA_BF16_REQUIRED_NO_FALLBACK')
    free, total = torch.cuda.mem_get_info(0)
    if free < LIMITS['minimum_cuda_free_bytes']:
        raise MemoryError('FIVE_GIB_CUDA_FREE_REQUIRED')
    return {'free_bytes': free, 'total_bytes': total,
            'name': torch.cuda.get_device_name(0), 'torch_version': torch.__version__,
            'cuda_build': torch.version.cuda}
