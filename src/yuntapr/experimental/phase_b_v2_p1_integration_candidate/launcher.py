"""Stdlib-only launcher: atomic owned Job + retained native identity.

Closed artificial worker modes only. No arbitrary argv/model/real runner launch
API, approval verifier, restart or quota refund exists in this version.
"""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
    Job, checked, times, code, exited, memory, close_handle)
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.watchdog import persist, interpreter_keys
from .scope import ROOT, LOCAL, lexical

CAMPAIGN = 'P1_ARTIFICIAL_JOB_INTEGRATION_v1'
MAX_LAUNCHES = 24  # fixed before first run, includes inner monitors; no refunds
MAX_SECONDS = 15
MAX_ALLOCATION = 32*1024**2
CASES = ('normal','wrapper_exit','exit_before','unexpected_exit','memory','cpu',
         'timeout_tree','foreign_pid','wrong_creation','wrong_nonce','invalid_handle',
         'monitor_exit','crash_inner','wrong_image','missing_pid')


def source_identity() -> dict:
    paths = [Path(__file__),Path(__file__).with_name('worker.py'),
             Path(__file__).with_name('scope.py'),
             Path(__file__).parent.parent/'phase_b_v2_execution_watchdog_candidate/winjob.py',
             Path(__file__).parent.parent/'phase_b_v2_execution_watchdog_candidate/watchdog.py']
    return {str(p.relative_to(ROOT)).replace('\\','/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def reserve(case: str, key: str) -> int:
    """Cross-process, nonrefundable attempt reservation BEFORE child creation."""
    if case not in CASES or len(key)!=32: raise ValueError('Closed artificial launch identity')
    LOCAL.mkdir(exist_ok=True)
    db=LOCAL/'launch_campaign.sqlite'
    with sqlite3.connect(db,timeout=2) as con:
        con.execute('PRAGMA synchronous=FULL')
        con.execute('CREATE TABLE IF NOT EXISTS attempts(n INTEGER PRIMARY KEY,key TEXT UNIQUE,case_id TEXT,campaign TEXT)')
        con.execute('BEGIN IMMEDIATE')
        count=con.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
        if count>=MAX_LAUNCHES: raise PermissionError('Fixed launch budget exhausted; no refund/restart')
        con.execute('INSERT INTO attempts VALUES(?,?,?,?)',(count+1,key,case,CAMPAIGN))
        con.commit()
        return count+1


def cpu_seconds(handle) -> float:
    values=[W.FILETIME() for _ in range(4)]
    checked(times(handle,*map(C.byref,values)))
    return sum(((v.dwHighDateTime<<32)|v.dwLowDateTime) for v in values[2:])/1e7


def small_json(path: Path, folder: Path) -> dict:
    lexical(path,folder)
    with path.open('rb') as stream: raw=stream.read(4097)
    if len(raw)>4096: raise ValueError('Artificial registration bound')
    row=json.loads(raw)
    if type(row) is not dict: raise ValueError('Registration mapping required')
    return row


def run(case: str) -> dict:
    """Start -> bind -> monitor -> stop -> prove empty; max 15s/case."""
    if type(case) is not str or case not in CASES: raise ValueError('No arbitrary runner launch')
    key=secrets.token_hex(16)
    attempt=reserve(case,key)
    folder=LOCAL/('job_'+key); lexical(folder,LOCAL);folder.mkdir(exist_ok=False)
    nonce=secrets.token_hex(16);sources=source_identity()
    persist(folder/'launch.json',dict(scope='SYNTHETIC_ENGINEERING_ONLY',campaign=CAMPAIGN,
            case=case,key=key,attempt=attempt,source_sha=sources,
            max_seconds=MAX_SECONDS,max_allocation_bytes=MAX_ALLOCATION,
            utc=datetime.now(timezone.utc).isoformat()))
    allowed=interpreter_keys()
    job=Job(); start=time.monotonic();worker=None;worker_identity=None;root_pid=None
    violation=None;error=None;clean=False;root_exited=False;peak_ws=peak_commit=0;peak_cpu=0
    independent_inner_cleanup=None;member_identities=[];observed_leaf=None
    mode='normal' if case=='wrapper_exit' else ('timeout_tree' if case=='crash_inner' else case)
    argv=[sys.executable,str(Path(__file__).with_name('worker.py')),str(folder),
          'wrapper' if case=='wrapper_exit' else mode,nonce,key,str(os.getpid())]
    if case=='wrapper_exit':argv.append(mode)
    try:
        root_pid=job.spawn(argv,ROOT)
        while True:
            elapsed=time.monotonic()-start
            if elapsed>MAX_SECONDS-3: raise TimeoutError('CASE_HARD_LIMIT')
            pids=job.snapshot();root_exited |= exited(job.root)
            reg=folder/'identity.json'
            if worker is None and reg.exists():
                row=small_json(reg,folder)
                if (set(row)!={'pid','creation_filetime','image_path_key','nonce','key','scope','no_science_imports'}
                        or row['nonce']!=nonce or row['key']!=key
                        or row['scope']!='SYNTHETIC_ENGINEERING_ONLY' or row['no_science_imports'] is not True):
                    raise ValueError('REGISTRATION_NONCE_SCOPE')
                worker=job.bind(row['pid']);worker_identity=dict(job.identities[row['pid']])
                if any(row[k]!=worker_identity[k] for k in worker_identity): raise ValueError('NATIVE_IDENTITY_MISMATCH')
                if worker_identity['image_path_key'] not in allowed:raise ValueError('NATIVE_EXECUTABLE_FAMILY')
                persist(folder/'bound.json',dict(worker_identity=worker_identity,key=key,source_sha=sources))
            if (folder/'leaf.json').exists():
                leaf=small_json(folder/'leaf.json',folder)
                if leaf['pid'] in job.handles: observed_leaf=job.handles[leaf['pid']]
            for h in job.handles.values():
                if h and not exited(h):
                    mem=memory(h);peak_ws=max(peak_ws,mem['working_set_bytes']);peak_commit=max(peak_commit,mem['private_commit_bytes'])
            total_cpu=sum(cpu_seconds(h) for h in job.handles.values() if h)
            peak_cpu=max(peak_cpu,total_cpu)
            if worker is not None:
                if case=='invalid_handle':
                    close_handle(worker);job.handles[worker_identity['pid']]=None
                    worker=None
                    memory(None) # explicit monitor failure: no PID fallback
                elif not exited(worker):
                    if case=='memory' and memory(worker)['working_set_bytes']>24*1024**2:
                        violation='MEMORY_LIMIT';break
                    if case=='cpu' and total_cpu>.12:
                        violation='CPU_TIME_LIMIT';break
                    if case=='crash_inner' and observed_leaf:
                        persist(folder/'monitor_crash.json',dict(key=key,worker_identity=worker_identity,
                                                               leaf_identity=leaf,source_sha=sources))
                        time.sleep(.15) # allow independent outer observer to retain leaf handle
                        os._exit(17) # no finally: last noninherited Job handle closes in kernel
                elif code(worker)!=0:
                    if case=='monitor_exit':
                        until=time.monotonic()+1
                        while observed_leaf and not exited(observed_leaf) and time.monotonic()<until:time.sleep(.01)
                        independent_inner_cleanup=bool(observed_leaf and exited(observed_leaf))
                    violation='WORKER_UNEXPECTED_EXIT';break
                elif not (folder/'complete.json').exists():
                    violation='MISSING_COMPLETION';break
            if not pids:
                if worker is None:violation='EXIT_BEFORE_IDENTITY'
                elif code(worker)!=0:violation='WORKER_UNEXPECTED_EXIT'
                elif small_json(folder/'complete.json',folder)!=dict(key=key,nonce=nonce,status='ARTIFICIAL_COMPLETE'):
                    violation='COMPLETION_MISMATCH'
                break
            if worker is None and elapsed>2:
                violation='IDENTITY_TIMEOUT';break
            if elapsed> (1.8 if case=='timeout_tree' else 4):
                violation='ELAPSED_LIMIT';break
            time.sleep(.015)
    except (OSError,ValueError,KeyError,PermissionError,RuntimeError,TimeoutError) as exc:
        violation='IDENTITY_OR_MONITOR_FAILURE';error=type(exc).__name__
    finally:
        member_identities=list(job.identities.values())
        try:
            job.stop() # owned Job only, also close the late-descendant race on success
            deadline=min(start+MAX_SECONDS,time.monotonic()+3)
            while time.monotonic()<deadline:
                if not job.pids() and all(not h or exited(h) for h in job.handles.values()):clean=True;break
                time.sleep(.015)
        except OSError as exc:
            error=type(exc).__name__;violation='CLEANUP_NOT_VERIFIED'
        finally:job.close()
    result=dict(scope='SYNTHETIC_ENGINEERING_ONLY',campaign=CAMPAIGN,case=case,key=key,attempt=attempt,
                root_pid=root_pid,worker_identity=worker_identity,root_exited_during_monitor=root_exited,
                observed_native_identities=member_identities,violation=violation,error_class=error,
                job_empty_and_handles_signaled=clean,inner_cleanup_before_outer_stop=independent_inner_cleanup,
                peak_process_working_set_bytes=peak_ws,peak_process_private_commit_bytes=peak_commit,
                cumulative_tree_cpu_seconds=peak_cpu,elapsed_seconds=time.monotonic()-start,
                source_sha=sources,restarts=0,refunds=0,optimizer_steps=0,model_imports=0,
                gpu_operations=0,real_data_reads=0)
    persist(folder/'termination.json',result)
    return result
