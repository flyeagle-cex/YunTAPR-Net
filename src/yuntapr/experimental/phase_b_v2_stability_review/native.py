"""Read-only native identity/Job queries; no termination or creation APIs."""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime,timedelta,timezone
from .classification import identity
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
    K,bind,open_process,native_identity,exited,close_handle,Pids,query_job)

open_job=bind(K,'OpenJobObjectW',[W.DWORD,W.BOOL,W.LPCWSTR],W.HANDLE)
uptime=bind(K,'GetTickCount64',[],C.c_uint64)

def process(expected: dict) -> dict:
    expected=identity(expected)
    C.set_last_error(0);h=open_process(0x00100000|0x1000,False,expected['pid'])
    if not h:
        error=C.get_last_error()
        return dict(status='ABSENT' if error==87 else 'UNKNOWN',winerror=error)
    try:
        if exited(h):return dict(status='EXITED')
        actual=native_identity(h)
        return dict(status='LIVE_MATCH' if actual==expected else 'PID_REUSED',actual_identity=actual)
    except OSError as exc:return dict(status='UNKNOWN',winerror=exc.winerror)
    finally:close_handle(h)

def job(name: str) -> dict:
    # Caller has already authenticated the exact nonce-bound name via scope().
    C.set_last_error(0);h=open_job(4,False,name) # JOB_OBJECT_QUERY only
    if not h:
        error=C.get_last_error()
        return dict(status='ABSENT' if error==2 else 'UNKNOWN',pids=[],winerror=error)
    try:
        p=Pids()
        if not query_job(h,3,C.byref(p),C.sizeof(p),None):
            return dict(status='UNKNOWN',pids=[],winerror=C.get_last_error())
        if p.count>16 or p.assigned!=p.count:return dict(status='UNKNOWN',pids=[],reason='UNEXPECTED_MEMBER_COUNT')
        return dict(status='PRESENT',pids=list(p.ids[:p.count]))
    finally:close_handle(h)

def clock() -> tuple[str,str]:
    now=datetime.now(timezone.utc)
    return now.isoformat(),(now-timedelta(milliseconds=uptime())).isoformat()
