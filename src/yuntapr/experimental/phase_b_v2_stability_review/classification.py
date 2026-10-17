"""Fail-closed inference from ledger metadata and independent native probes."""
from __future__ import annotations
from datetime import datetime
import re

DEAD=frozenset(('ABSENT','EXITED','PID_REUSED'))

def identity(value: dict) -> dict:
    keys=('pid','creation_filetime','image_path_key')
    if (not isinstance(value,dict) or any(k not in value for k in keys) or
        type(value['pid']) is not int or not 0<value['pid']<=0xffffffff or
        type(value['creation_filetime']) is not int or value['creation_filetime']<=0 or
        not isinstance(value['image_path_key'],str) or not re.fullmatch('[0-9a-f]{64}',value['image_path_key'])):
        raise ValueError('NATIVE_PROCESS_IDENTITY_FORMAT')
    return {k:value[k] for k in keys}

def scope(owner: dict,worker: dict,campaign: str,session: int) -> dict:
    """Validate nonce and Job name BEFORE querying any supplied PID/Job."""
    if (not re.fullmatch('[A-Z0-9_]{1,96}',campaign) or type(session) is not int or
        not 1<=session<=999 or owner.get('campaign')!=campaign or owner.get('session')!=session or
        not isinstance(owner.get('nonce'),str) or not re.fullmatch('[0-9a-f]{32}',owner['nonce'])):
        raise ValueError('SESSION_SCOPE_OR_NONCE')
    name=f"Local\\{campaign}__{session}__{owner['nonce']}"
    if owner.get('job_name')!=name or worker.get('campaign')!=campaign or worker.get('nonce')!=owner['nonce']:
        raise ValueError('OWNED_JOB_AND_WORKER_SCOPE')
    return dict(owner=identity(owner),worker=identity(worker),job_name=name)

def classify(snapshot: dict,probes: dict,now_utc: str,boot_utc: str) -> dict:
    """This result is an observation, never permission to resume or retry."""
    heartbeat=datetime.fromisoformat(snapshot['heartbeat_utc'])
    now=datetime.fromisoformat(now_utc);boot=datetime.fromisoformat(boot_utc)
    if any(x.tzinfo is None for x in (heartbeat,now,boot)):raise ValueError('UTC_OFFSETS_REQUIRED')
    age=(now-heartbeat).total_seconds()
    owner,worker,job=(probes[k]['status'] for k in ('owner','worker','job'))
    base=dict(record_kind='POSTMORTEM_OBSERVATION_NOT_TERMINATION_RECEIPT',
        ledger_state_observed=snapshot['ledger_state'],ledger_was_modified=False,
        heartbeat_age_seconds=age,heartbeat_before_current_boot=heartbeat<boot,
        formal_launch_capability=False,resume_allowed=False,automatic_retries=0,
        historical_cleanup_execution='NOT_VERIFIED',observed_process_tree_empty=False)
    if age<0:state='NOT_VERIFIED_CLOCK_SKEW'
    elif owner=='UNKNOWN' or worker=='UNKNOWN' or job=='UNKNOWN':state='NOT_VERIFIED_NATIVE_PROBE'
    elif owner=='LIVE_MATCH' or worker=='LIVE_MATCH':
        state='LIVE_HEARTBEAT_STALE' if age>60 else 'LIVE'
    elif job=='PRESENT' and probes['job']['pids']:state='ORPHAN_JOB_PRESENT_DO_NOT_RESTART'
    elif owner in DEAD and worker in DEAD and (job=='ABSENT' or (job=='PRESENT' and not probes['job']['pids'])):
        base['observed_process_tree_empty']=True
        # PAUSED/LAST metadata alone never proves a checkpoint payload is valid.
        if snapshot['termination_receipt_present']:
            state='STOPPED_WITH_PRIOR_RECEIPT_REQUIRES_SEPARATE_VALIDATION'
        elif snapshot['ledger_state'] in ('ACTIVE','PAUSED','FAILED_NO_RETRY'):
            state='STOPPED_UNCLEAN_NO_LAST' if not snapshot['last_claimed'] else 'STOPPED_UNCLEAN_LAST_NOT_VERIFIED'
        else:state='STOPPED_UNCLEAN_OTHER_LEDGER_STATE'
    else:state='NOT_VERIFIED_INCONSISTENT_NATIVE_OBSERVATION'
    return dict(**base,effective_state=state)
