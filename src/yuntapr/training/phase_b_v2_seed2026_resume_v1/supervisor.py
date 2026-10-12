"""One launch, automated Windows Job monitoring, no manual polling needed.

The Job is assigned atomically at process creation, including venv descendants.
Closing/crashing this noninherited owner handle kills the entire owned tree.
"""
from __future__ import annotations
import ctypes as C
from datetime import datetime,timezone
import json
import os
import secrets
import sqlite3
import sys
import time
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
    Job,ExtendedLimit,set_job,checked,memory,exited,code)
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.watchdog import interpreter_keys
from .protocol import ROOT,OUT,LOCAL,CAMPAIGN,LIMITS,atomic_json,verify_release
from .resources import host_admission

class FormalJob(Job):
    def __init__(self):
        super().__init__()
        try:
            limits=ExtendedLimit();limits.basic.flags=0x2000|0x8|0x200|0x100
            limits.basic.active_limit=16;limits.job_memory=LIMITS['max_job_commit_bytes']
            limits.process_memory=LIMITS['max_process_commit_bytes']
            checked(set_job(self.handle,9,C.byref(limits),C.sizeof(limits)))
        except BaseException:self.close();raise

def main():
    release=verify_release();LOCAL.mkdir(exist_ok=True);host_admission()
    # Fixed namespace; no renamed attempts or automatic relaunch after a crash.
    with (LOCAL/'launch.once').open('x',encoding='ascii') as f:
        f.write(CAMPAIGN);f.flush();os.fsync(f.fileno())
    nonce=secrets.token_hex(16);allowed=interpreter_keys();job=FormalJob()
    ancestor=json.loads((OUT/'ancestor.json').read_bytes())
    launched=time.monotonic();start=launched-ancestor['elapsed_seconds'];worker=None;identity=None;peak_ws=peak_commit=0;failure=None;clean=False;success=False
    atomic_json(LOCAL/'launch.json',dict(campaign=CAMPAIGN,nonce=nonce,release=release,limits=LIMITS,
        utc=datetime.now(timezone.utc).isoformat(),automatic_retries=0))
    try:
        os.environ.update(PYTHONPATH=str(ROOT/'src'),PYTHONUTF8='1',PYTHONHASHSEED='2026',CUBLAS_WORKSPACE_CONFIG=':4096:8')
        job.spawn([sys.executable,'-m','yuntapr.training.phase_b_v2_seed2026_resume_v1.worker',nonce],ROOT)
        while True:
            pids=job.snapshot();elapsed=time.monotonic()-start
            if worker is None and (LOCAL/'worker_identity.json').exists():
                with (LOCAL/'worker_identity.json').open('rb') as f:raw=f.read(4097)
                if len(raw)>4096:raise ValueError('WORKER_IDENTITY_SIZE')
                row=json.loads(raw)
                if set(row)!= {'pid','creation_filetime','image_path_key','nonce','campaign'} or row['nonce']!=nonce or row['campaign']!=CAMPAIGN:
                    raise ValueError('WORKER_NATIVE_NONCE_SCOPE')
                worker=job.bind(row['pid']);identity=job.identities[row['pid']]
                if any(row[k]!=identity[k] for k in identity) or identity['image_path_key'] not in allowed:
                    raise ValueError('WORKER_NATIVE_IDENTITY')
                atomic_json(LOCAL/'bound_identity.json',dict(worker=identity,nonce=nonce,campaign=CAMPAIGN))
            if worker is None and time.monotonic()-launched>30:raise TimeoutError('WORKER_REGISTRATION_TIMEOUT')
            for h in job.handles.values():
                if h and not exited(h):
                    m=memory(h);peak_ws=max(peak_ws,m['peak_working_set_bytes']);peak_commit=max(peak_commit,m['private_commit_bytes'])
                    if m['working_set_bytes']>LIMITS['max_working_set_bytes'] or m['private_commit_bytes']>LIMITS['max_process_commit_bytes']:
                        raise MemoryError('EXTERNAL_WORKER_RESOURCE_LIMIT')
            if elapsed>LIMITS['max_seconds']:raise TimeoutError('FIXED_SEVEN_DAY_CAMPAIGN_LIMIT')
            host_admission()
            if worker is not None and exited(worker):
                if code(worker)!=0:raise RuntimeError('WORKER_FAILED_NO_RETRY')
                row=json.loads((LOCAL/'complete.json').read_bytes())
                if row!=dict(nonce=nonce,campaign=CAMPAIGN,status='SIX_RUNS_COMPLETE'):raise ValueError('MISSING_COMPLETE_RECEIPT')
                if not pids:success=True;break
            if not pids and worker is None:raise RuntimeError('EXIT_BEFORE_REGISTRATION')
            time.sleep(1) # automatic safety sampling, not manual realtime polling
    except BaseException as exc:failure=dict(type=type(exc).__name__,code=str(exc))
    finally:
        try:
            job.stop();deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                if not job.pids() and all(not h or exited(h) for h in job.handles.values()):clean=True;break
                time.sleep(.05)
        finally:job.close()
        status=dict(campaign=CAMPAIGN,status='COMPLETE' if success and clean else 'STOPPED_NO_RETRY',
            worker_identity=identity,job_empty_and_handles_signaled=clean,peak_process_working_set_bytes=peak_ws,
            peak_process_private_commit_bytes=peak_commit,elapsed_seconds=time.monotonic()-start,failure=failure,
            automatic_retries=0,refunds=0)
        atomic_json(LOCAL/'termination.json',status)
        if not success:
            # A kernel termination cannot run worker finally. Mark the fixed
            # quota FAILED without decrementing any reserved attempt.
            db=ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.sqlite'
            if db.exists():
                with sqlite3.connect(db,timeout=5) as con:
                    con.execute('PRAGMA synchronous=FULL')
                    con.execute("UPDATE campaign SET status='FAILED_NO_RETRY',reason=? WHERE status='ACTIVE'",('WATCHDOG_TERMINATED',))
            atomic_json(OUT/'watchdog_failure.json',status)
    return 0 if success and clean else 1

if __name__=='__main__':raise SystemExit(main())
