"""Auditable native monitoring; every error remains fatal, no API bypass."""
from __future__ import annotations
import json,time
from .protocol import CAMPAIGN,LIMITS,atomic_json,owned_json
from .resources import host_admission
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import memory,exited,code

def monitor(job,local,allowed,nonce,n,start,launched,watch):
    worker=None;identity=None
    watch.update(phase='job.snapshot',peak_ws=0,peak_commit=0,success=False,paused=False,worker_identity=None)
    while True:
        watch['phase']='job.snapshot'
        pids=job.snapshot();elapsed=time.monotonic()-start
        if worker is None and (local/'worker_identity.json').exists():
            watch['phase']='worker_identity_read'
            with (local/'worker_identity.json').open('rb') as f:raw=f.read(4097)
            if len(raw)>4096:raise ValueError('WORKER_IDENTITY_SIZE')
            row=json.loads(raw)
            if set(row)!= {'pid','creation_filetime','image_path_key','nonce','campaign'} or row['nonce']!=nonce or row['campaign']!=CAMPAIGN:
                raise ValueError('WORKER_NATIVE_NONCE_SCOPE')
            watch['phase']='job.bind_worker'
            worker=job.bind(row['pid']);identity=job.identities[row['pid']]
            if any(row[k]!=identity[k] for k in identity) or identity['image_path_key'] not in allowed:raise ValueError('WORKER_NATIVE_IDENTITY')
            watch['worker_identity']=identity
            watch['phase']='bound_identity_write'
            atomic_json(local/'bound_identity.json',dict(worker=identity,nonce=nonce,campaign=CAMPAIGN,session=n))
        if worker is None and time.monotonic()-launched>30:raise TimeoutError('WORKER_REGISTRATION_TIMEOUT')
        for pid,h in job.handles.items():
            watch['process_identity']=job.identities.get(pid)
            watch['phase']='process_wait_before_memory'
            if h and not exited(h):
                watch['phase']='GetProcessMemoryInfo'
                m=memory(h);watch['peak_ws']=max(watch['peak_ws'],m['peak_working_set_bytes']);watch['peak_commit']=max(watch['peak_commit'],m['private_commit_bytes'])
                if m['working_set_bytes']>LIMITS['max_working_set_bytes'] or m['private_commit_bytes']>LIMITS['max_process_commit_bytes']:
                    raise MemoryError('EXTERNAL_WORKER_RESOURCE_LIMIT')
        if elapsed>LIMITS['max_seconds']:raise TimeoutError('FIXED_SEVEN_DAY_CAMPAIGN_LIMIT')
        watch['phase']='host_admission';host_admission()
        watch['phase']='worker_exit_wait'
        if worker is not None and exited(worker):
            watch['phase']='GetExitCodeProcess'
            if code(worker)!=0:raise RuntimeError('WORKER_FAILED_NO_RETRY')
            if (local/'paused.json').exists():
                watch['phase']='pause_receipt_read';row=owned_json(local/'paused.json')
                if row['nonce']!=nonce or row['campaign']!=CAMPAIGN or row['session']!=n or row['status']!='PAUSED_VERIFIED':raise ValueError('PAUSE_RECEIPT_IDENTITY')
                if not pids:watch['paused']=True;return
            else:
                watch['phase']='completion_receipt_read';row=owned_json(local/'complete.json')
                if row!=dict(nonce=nonce,campaign=CAMPAIGN,status='SIX_RUNS_COMPLETE'):raise ValueError('MISSING_COMPLETE_RECEIPT')
                if not pids:watch['success']=True;return
        if not pids and worker is None:raise RuntimeError('EXIT_BEFORE_REGISTRATION')
        watch['phase']='sampling_sleep';time.sleep(1)
