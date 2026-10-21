"""Bounded human operator commands; no new scope, retry, or quota reset API."""
from __future__ import annotations
import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import time
from .protocol import ROOT, OUT, LOCAL, DB, CAMPAIGN, session_root, atomic_json, verify_release, owned_json
from .quota import Ledger, ro


def now():return datetime.now(timezone.utc).isoformat()


def status():
    if not DB.exists():return dict(status='NOT_STARTED',campaign=CAMPAIGN)
    with ro() as con:
        state,reason=con.execute('SELECT status,reason FROM campaign').fetchone()
        counts=dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status'))
        from .protocol import OLD_RESERVED,OLD_VERIFIED,TOTAL
        row=con.execute('SELECT n,status FROM sessions ORDER BY n DESC LIMIT 1').fetchone()
        result=dict(status=state,reason=reason,campaign=CAMPAIGN,reserved=OLD_RESERVED+sum(counts.values()),
            returned_verified=OLD_VERIFIED+counts.get('RETURNED_VERIFIED',0),hard_cap=TOTAL,
            prior_reserved=OLD_RESERVED,prior_returned_verified=OLD_VERIFIED,prior_unverified=OLD_RESERVED-OLD_VERIFIED,
            new_reserved=sum(counts.values()),new_returned_verified=counts.get('RETURNED_VERIFIED',0),
            pause_requested=bool(con.execute('SELECT pause_requested FROM control').fetchone()[0]),
            runs=[dict(zip(('id','status','complete_epoch','logical_updates','last_sha'),r)) for r in con.execute('SELECT id,status,epoch,updates,last_sha FROM runs ORDER BY ordinal')],
            updated_utc=now())
    if row:
        n,s=row;result['session']=dict(number=n,status=s)
        heartbeat=session_root(n)/'heartbeat.json'
        if heartbeat.exists():
            from yuntapr.experimental.phase_b_v2_status_snapshot_io.reader import read_json_snapshot
            result['heartbeat']=read_json_snapshot(heartbeat,OUT)
        term=session_root(n)/'termination.json'
        if term.exists():result['termination']=owned_json(term)
        owner_path=session_root(n)/'supervisor_identity.json';worker_path=session_root(n)/'worker_identity.json'
        result['ledger_state']=state
        if owner_path.exists() and worker_path.exists():
            from yuntapr.experimental.phase_b_v2_stability_review import native
            from yuntapr.experimental.phase_b_v2_stability_review.classification import scope,DEAD
            expected=scope(owned_json(owner_path),owned_json(worker_path),CAMPAIGN,n)
            probes=dict(owner=native.process(expected['owner']),worker=native.process(expected['worker']),job=native.job(expected['job_name']))
            result['native_probes']=probes
            if any(probes[k]['status']=='UNKNOWN' for k in probes):result['effective_state']='NOT_VERIFIED_NATIVE_PROBE'
            elif probes['owner']['status']=='LIVE_MATCH' and probes['worker']['status']=='LIVE_MATCH' and probes['job']['status']=='PRESENT':result['effective_state']='RUNNING'
            elif probes['owner']['status'] in DEAD and probes['worker']['status'] in DEAD and probes['job']['status']=='ABSENT':result['effective_state']='STOPPED_UNCLEAN' if state=='ACTIVE' else state
            else:result['effective_state']='NOT_VERIFIED_PROCESS_TRANSITION'
        else:result['effective_state']='STARTING_NOT_YET_NATIVE_BOUND' if state=='ACTIVE' else state
    return result


def start():
    """One new session at READY or verified PAUSED boundary; no FAILED restart."""
    release=verify_release()
    from .protocol import require_predecessor
    require_predecessor()
    from .resources import host_admission
    host_admission()
    runtime=owned_json(LOCAL/'runtime.json')
    if os.path.normcase(sys.executable)!=os.path.normcase(runtime['python']):
        raise PermissionError('FROZEN_OPERATOR_INTERPRETER_REQUIRED')
    ledger=Ledger.initialize(release)
    n=nonce=None
    try:
        n,nonce=ledger.claim_session();folder=session_root(n);folder.mkdir(parents=True,exist_ok=False)
        from .task_owner import start_owner
        task=start_owner(n,nonce,release)
        row=dict(status='START_REQUESTED',campaign=CAMPAIGN,session=n,system_task=task,utc=now(),
            automatic_retries=0,quota=ledger.snapshot())
        atomic_json(folder/'operator_launch.json',row);return row
    except BaseException:
        # Once claimed, an uncertain spawn is NEVER retried by this command.
        if n is not None:ledger.fail('OPERATOR_SPAWN_FAILED_OR_UNCERTAIN')
        raise
    finally:ledger.close()


def pause():
    ledger=Ledger()
    try:
        requested=ledger.request_pause()
        return dict(status='SAFE_PAUSE_REQUESTED' if requested else 'NOT_RUNNING',
            resource_release='AFTER_COMPLETE_TRAIN_VALIDATION_AND_LAST',quota=ledger.snapshot(),utc=now())
    finally:ledger.close()


def open_owned_job(identity):
    """Bind native supervisor identity and nonce-named kernel Job before stop."""
    from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
        K,bind,checked,open_process,native_identity,close_handle,exited,Job)
    expected=f"Local\\{CAMPAIGN}__{identity['session']}__{identity['nonce']}"
    if identity['campaign']!=CAMPAIGN or identity['job_name']!=expected or len(identity['nonce'])!=32:
        raise PermissionError('OWNED_JOB_SCOPE')
    owner=checked(open_process(0x00100000|0x1000,False,identity['pid']))
    try:
        actual=native_identity(owner)
        if exited(owner) or any(identity[k]!=actual[k] for k in actual):raise PermissionError('SUPERVISOR_NATIVE_IDENTITY_MISMATCH')
        open_job=bind(K,'OpenJobObjectW',[W.DWORD,W.BOOL,W.LPCWSTR],W.HANDLE)
        h=checked(open_job(4|8,False,expected))
        job=object.__new__(Job);job.handle=h;job.root=None;job.handles={};job.identities={};job.terminated=False
        try:job.snapshot()
        except BaseException:job.close();raise
        return job,owner
    except BaseException:close_handle(owner);raise


def emergency_stop():
    from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import close_handle,exited
    ledger=Ledger();job=owner=None
    try:
        n,s,nonce=ledger.con.execute('SELECT n,status,nonce FROM sessions ORDER BY n DESC LIMIT 1').fetchone()
        if s!='ACTIVE' or ledger.con.execute('SELECT status FROM campaign').fetchone()!=('ACTIVE',):
            raise PermissionError('NO_ACTIVE_OWNED_JOB')
        identity=owned_json(session_root(n)/'supervisor_identity.json')
        if identity['session']!=n or identity['nonce']!=nonce:raise PermissionError('SESSION_NONCE_MISMATCH')
        job,owner=open_owned_job(identity)
        directory=session_root(n)/('emergency_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
        directory.mkdir(exist_ok=False)
        atomic_json(directory/'request.json',dict(utc=now(),supervisor=identity,quota=ledger.snapshot(),pids=job.pids()))
        # Permanent FAILED status blocks any next reservation before termination.
        ledger.fail('RESEARCHER_EMERGENCY_STOP_NO_RETRY')
        job.stop();deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if not job.pids() and all(exited(h) for h in job.handles.values()):break
            time.sleep(.05)
        empty=not job.pids() and all(exited(h) for h in job.handles.values())
        row=dict(status='TERMINATED' if empty else 'TERMINATION_NOT_VERIFIED',utc=now(),job_empty=empty,
            quota=ledger.snapshot(),automatic_retries=0,refunds=0,
            restart='NEW_LAST_BOUND_RESEARCHER_DECISION_AND_REPLAY_BUDGET_REQUIRED')
        atomic_json(directory/'receipt.json',row);return row
    finally:
        if job is not None:job.close()
        if owner:close_handle(owner)
        ledger.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('start','pause','status','emergency-stop'))
    action=parser.parse_args().action
    result={'start':start,'pause':pause,'status':status,'emergency-stop':emergency_stop}[action]()
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))


if __name__=='__main__':main()
