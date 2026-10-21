"""One launch, automated Windows Job monitoring, no manual polling needed.

The Job is assigned atomically at process creation, including venv descendants.
Closing/crashing this noninherited owner handle kills the entire owned tree.
"""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime,timezone
import json
import os
import secrets
import sqlite3
import sys
import time
import traceback
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
    Job,ExtendedLimit,set_job,checked,memory,exited,code,K,native_identity,create_job,close_handle)
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.watchdog import interpreter_keys
from .protocol import ROOT,OUT,LOCAL,DB,CAMPAIGN,LIMITS,atomic_json,verify_release,session_root,owned_json
from .resources import host_admission

class FormalJob(Job):
    def __init__(self,name=None):
        super().__init__()
        try:
            if name is not None:
                close_handle(self.handle);self.handle=None
                C.set_last_error(0);self.handle=checked(create_job(None,name))
                if C.get_last_error()==183:raise PermissionError('NAMED_JOB_ALREADY_EXISTS')
            limits=ExtendedLimit();limits.basic.flags=0x2000|0x8|0x200|0x100
            limits.basic.active_limit=16;limits.job_memory=LIMITS['max_job_commit_bytes']
            limits.process_memory=LIMITS['max_process_commit_bytes']
            checked(set_job(self.handle,9,C.byref(limits),C.sizeof(limits)))
        except BaseException:self.close();raise

def main():
    if len(sys.argv)!=2:raise PermissionError('CLAIMED_SESSION_REQUIRED')
    n=int(sys.argv[1]);os.environ['YUNTAPR_OPERATOR_SESSION']=str(n)
    local=session_root();release=verify_release();host_admission()
    from .quota import Ledger,carry
    ledger=Ledger()
    row=ledger.con.execute('SELECT status,nonce FROM sessions WHERE n=?',(n,)).fetchone()
    if not row or row[0]!='CLAIMED':raise PermissionError('SESSION_NOT_CLAIMED')
    nonce=row[1]
    if os.environ.get('YUNTAPR_SYSTEM_TASK_OWNER_NONCE')!=nonce:
        raise PermissionError('FIXED_OS_TASK_OWNER_BOOTSTRAP_REQUIRED')
    from .task_owner import validate_owner_request
    validate_owner_request(n,nonce)
    owner_started=owned_json(local/'task_owner_started.json')
    K.GetCurrentProcess.restype=W.HANDLE
    if any(owner_started[k]!=v for k,v in native_identity(K.GetCurrentProcess()).items()):
        raise PermissionError('TASK_OWNER_NATIVE_PID_CREATION_IMAGE_MISMATCH')
    with (local/'launch.once').open('x',encoding='ascii') as f:f.write(CAMPAIGN);f.flush();os.fsync(f.fileno())
    ledger.activate_session(n,nonce);ledger.close()
    K.GetCurrentProcess.restype=W.HANDLE
    name=f'Local\\{CAMPAIGN}__{n}__{nonce}'
    allowed=interpreter_keys();job=FormalJob(name);ancestor=carry()
    atomic_json(local/'supervisor_identity.json',dict(**native_identity(K.GetCurrentProcess()),nonce=nonce,campaign=CAMPAIGN,session=n,job_name=name))
    launched=time.monotonic();start=launched-ancestor['elapsed_seconds'];worker=None;identity=None;peak_ws=peak_commit=0;failure=None;clean=False;success=False;paused=False
    atomic_json(local/'launch.json',dict(campaign=CAMPAIGN,nonce=nonce,session=n,release=release,limits=LIMITS,
        utc=datetime.now(timezone.utc).isoformat(),automatic_retries=0))
    watch=dict(phase='worker_spawn',peak_ws=0,peak_commit=0,success=False,paused=False,worker_identity=None)
    try:
        os.environ.update(PYTHONPATH=str(ROOT/'src'),PYTHONUTF8='1',PYTHONHASHSEED='2026',CUBLAS_WORKSPACE_CONFIG=':4096:8')
        job.spawn([sys.executable,'-m','yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v6.worker',str(n),nonce],ROOT)
        from .monitor import monitor
        monitor(job,local,allowed,nonce,n,start,launched,watch)
    except BaseException as exc:
        # Keep private paths and full stack local; never ignore permission faults.
        (local/'supervisor_failure_private.txt').write_text(traceback.format_exc(),encoding='utf-8',newline='\n')
        failure=dict(type=type(exc).__name__,winerror=getattr(exc,'winerror',None),
            code=('WINERROR_'+str(exc.winerror)) if getattr(exc,'winerror',None) else type(exc).__name__,
            phase=watch.get('phase'),process_identity=watch.get('process_identity'))
    finally:
        try:
            job.stop();deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                if not job.pids() and all(not h or exited(h) for h in job.handles.values()):clean=True;break
                time.sleep(.05)
        finally:job.close()
        success=watch['success'];paused=watch['paused'];identity=watch['worker_identity'];peak_ws=watch['peak_ws'];peak_commit=watch['peak_commit']
        status=dict(campaign=CAMPAIGN,status='COMPLETE' if success and clean else ('PAUSED' if paused and clean else 'STOPPED_NO_RETRY'),
            worker_identity=identity,job_empty_and_handles_signaled=clean,peak_process_working_set_bytes=peak_ws,
            peak_process_private_commit_bytes=peak_commit,elapsed_seconds=time.monotonic()-start,failure=failure,
            automatic_retries=0,refunds=0)
        atomic_json(local/'termination.json',status)
        if not ((success or paused) and clean):
            # A kernel termination cannot run worker finally. Mark the fixed
            # quota FAILED without decrementing any reserved attempt.
            db=DB
            if db.exists():
                with sqlite3.connect(db,timeout=5) as con:
                    con.execute('PRAGMA synchronous=FULL')
                    con.execute("UPDATE campaign SET status='FAILED_NO_RETRY',reason=? WHERE status IN ('ACTIVE','PAUSED')",('WATCHDOG_TERMINATED',))
            atomic_json(OUT/'watchdog_failure.json',status)
    return 0 if (success or paused) and clean else 1

if __name__=='__main__':raise SystemExit(main())
