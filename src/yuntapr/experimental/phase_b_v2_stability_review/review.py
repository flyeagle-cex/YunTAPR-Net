"""Exact registered stopped run only; no arbitrary data/checkpoint paths."""
from __future__ import annotations
from contextlib import ExitStack
from importlib import import_module
import hashlib,json,os,sqlite3
from pathlib import Path
from . import native
from .classification import classify,scope,identity
from .memory import sample
from .receipts import ROOT,LOCAL,save
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle

DEFAULT_CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_FRESH_RESTART_V1'
TARGETS={
    DEFAULT_CAMPAIGN:dict(run='docs/phase_b_v2_formal_execution/seed2027_restart_v1',
        db='.git/phase_b_v2_seed2027_fresh_restart_v1.sqlite',
        accounting=('yuntapr.training.phase_b_v2_seed2027_restart_v1.accounting','fields')),
    'YUNTAPR_PHASE_B_V2_SEED2027_FRESH_RESTART_V2':dict(run='docs/phase_b_v2_formal_execution/seed2027_restart_v2',
        db='.git/phase_b_v2_seed2027_fresh_restart_v2.sqlite',
        accounting=('yuntapr.training.phase_b_v2_seed2027_restart_v2.accounting','fields')),
    'YUNTAPR_PHASE_B_V2_SEED2027_FRESH_RESTART_V3':dict(run='docs/phase_b_v2_formal_execution/seed2027_restart_v3',
        db='.git/phase_b_v2_seed2027_fresh_restart_v3.sqlite',
        accounting=('yuntapr.training.phase_b_v2_seed2027_restart_v3.accounting','fields'),
        sessions=[(1,'PAUSED'),(2,'ACTIVE')]),
}

def _target(campaign):
    if type(campaign) is not str or campaign not in TARGETS:
        raise PermissionError('EXACT_REGISTERED_STOPPED_CAMPAIGN_REQUIRED')
    cfg=TARGETS[campaign];run=ROOT/cfg['run'];db=ROOT/cfg['db']
    session=run/'.local/sessions/session_0001'
    return campaign,cfg,run,db,session

def lexical(path: Path, registered: frozenset) -> None:
    if path not in registered or not path.is_absolute() or '..' in path.parts or '2025' in str(path):
        raise PermissionError('EXACT_REGISTERED_AUDIT_FILES_BEFORE_ACCESS')

def read(stack,path: Path,maximum: int,pins: dict,registered: frozenset) -> bytes:
    lexical(path,registered)
    h=stack.enter_context(ReadHandle(str(path),payload=True))
    if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or not 0<h.before['size']<=maximum:
        raise PermissionError('AUDIT_NATIVE_OBJECT_OR_SIZE')
    data=bytearray(h.before['size']);n=0
    while n<len(data):
        count=h.readinto(memoryview(data)[n:])
        if not count:raise EOFError('AUDIT_METADATA_TRUNCATED')
        n+=count
    if h.readinto(bytearray(1)) or h.snapshot()!=h.before:raise ValueError('AUDIT_METADATA_CHANGED')
    pins[path.relative_to(ROOT).as_posix()]=hashlib.sha256(data).hexdigest()
    return bytes(data)

def inspect(campaign=None) -> dict:
    if campaign is None:campaign=DEFAULT_CAMPAIGN
    CAMPAIGN,cfg,RUN,DB,SESSION=_target(campaign)
    REGISTERED={DB,RUN/'release.json',SESSION/'supervisor_identity.json',SESSION/'worker_identity.json',
        SESSION/'bound_identity.json',SESSION/'heartbeat.json',SESSION/'termination.json'}
    pins={};now,boot=native.clock()
    # Holding parents prevents directory rename/reparse swaps of audit evidence.
    parents={p.parent for p in REGISTERED}
    for path in tuple(parents):
        while path!=ROOT:
            path=path.parent;parents.add(path)
    with ExitStack() as stack:
        for path in sorted(parents,key=lambda p:len(p.parts)):
            if not path.is_relative_to(ROOT) or '2025' in str(path):raise PermissionError('AUDIT_ANCESTOR_SCOPE')
            h=stack.enter_context(ReadHandle(str(path),directory=True))
            if os.path.normcase(h.final_path)!=os.path.normcase(str(path)):raise PermissionError('AUDIT_ANCESTOR_IDENTITY')
        owner=json.loads(read(stack,SESSION/'supervisor_identity.json',8192,pins,REGISTERED))
        worker=json.loads(read(stack,SESSION/'worker_identity.json',8192,pins,REGISTERED))
        authenticated=scope(owner,worker,CAMPAIGN,1)
        bound=json.loads(read(stack,SESSION/'bound_identity.json',8192,pins,REGISTERED))
        if (bound.get('campaign')!=CAMPAIGN or bound.get('session')!=1 or bound.get('nonce')!=owner['nonce'] or
            identity(bound['worker'])!=authenticated['worker']):raise ValueError('BOUND_WORKER_IDENTITY')
        heartbeat=json.loads(read(stack,SESSION/'heartbeat.json',8192,pins,REGISTERED))
        release=json.loads(read(stack,RUN/'release.json',1024**2,pins,REGISTERED))
        read(stack,DB,32*1024**2,pins,REGISTERED) # No write-capable SQLite handle is opened.
        with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as con:
            con.execute('PRAGMA query_only=ON');con.execute('BEGIN')
            campaign_row=con.execute('SELECT id,status,reason FROM campaign').fetchone()
            sessions=con.execute('SELECT n,status FROM sessions ORDER BY n').fetchall()
            counts=dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status'))
            runs=[dict(zip(('run_id','status','epoch','updates','last_sha'),r)) for r in con.execute('SELECT id,status,epoch,updates,last_sha FROM runs ORDER BY ordinal')]
            epochs=con.execute('SELECT run,epoch,phase FROM epochs').fetchall();con.execute('COMMIT')
        expected_sessions=cfg.get('sessions')
        if (campaign_row[0]!=CAMPAIGN or not sessions or
            (expected_sessions is not None and sessions!=expected_sessions) or
            (expected_sessions is None and sessions[-1][0]!=1)):raise ValueError('REGISTERED_CAMPAIGN_SESSION')
        try:read(stack,SESSION/'termination.json',65536,pins,REGISTERED);has_term=True
        except FileNotFoundError:has_term=False
        snapshot=dict(ledger_state=campaign_row[1],heartbeat_utc=heartbeat['utc'],
            termination_receipt_present=has_term,last_claimed=any(r['last_sha'] is not None for r in runs))
        probes=dict(owner=native.process(authenticated['owner']),worker=native.process(authenticated['worker']),
            job=native.job(authenticated['job_name']))
        observation=classify(snapshot,probes,now,boot)
        module_name,function_name=cfg['accounting']
        fields=getattr(import_module(module_name),function_name)
        # Pure counter function only: never import its training engine/authority.
        quota=fields(sum(counts.values()),counts.get('RETURNED_VERIFIED',0))
        return dict(schema='STOPPED_SESSION_REVIEW_v1',observed_utc=now,estimated_current_boot_utc=boot,
            boot_estimate_method='UTC minus GetTickCount64; supporting evidence, not authority',campaign=CAMPAIGN,
            observation=observation,native_probes=probes,ledger_state_observed=campaign_row[1],ledger_reason=campaign_row[2],
            session_state_observed=sessions[-1][1],quota=quota,runs=runs,epochs=epochs,
            heartbeat=heartbeat,source_commit_of_stopped_run=release['source_commit'],
            source_sha256_of_stopped_run=release['source_sha256'],source_evidence_sha256=pins,
            current_memory=sample(),new_real_data_reads=0,new_optimizer_updates=0,
            driver_or_system_settings_changed=False,original_ledgers_modified=False,
            historic_2025_path_attribute_access='NOT_INSTRUMENTED')

def run(campaign=None, record: bool=False) -> dict:
    try:result=inspect(campaign)
    except (OSError,ValueError,KeyError,sqlite3.Error,TypeError) as exc:
        # Do not convert unreadable/shared evidence into proof of process death.
        return dict(status='NOT_VERIFIED',error_type=type(exc).__name__,
            error_code=str(exc) if str(exc).replace('_','').isalnum() else 'AUDIT_PROBE_OR_SHARING_ERROR',
            resume_allowed=False,formal_launch_capability=False,old_ledger_modified=False)
    if record:
        path=save(result);result['postmortem_receipt_relative_path']=path.relative_to(ROOT).as_posix()
    return result
