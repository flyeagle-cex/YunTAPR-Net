"""Read-only current Job metadata; presence alone does not imply Codex ownership."""
import ctypes as C
from ctypes import wintypes as W
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import K,ExtendedLimit,checked,in_job,query_job
K.GetCurrentProcess.restype=W.HANDLE

def current_job_profile():
 b=W.BOOL();checked(in_job(K.GetCurrentProcess(),None,C.byref(b)))
 if not b.value:return dict(in_job=False,flags=0,kill_on_close=False)
 limits=ExtendedLimit();checked(query_job(None,9,C.byref(limits),C.sizeof(limits),None))
 return dict(in_job=True,flags=int(limits.basic.flags),kill_on_close=bool(limits.basic.flags&0x2000))
