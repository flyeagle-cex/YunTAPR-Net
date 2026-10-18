"""Hold all three failed ancestors unchanged. Never reinterpret stale ACTIVE as PAUSED."""
from __future__ import annotations
from contextlib import ExitStack
from datetime import datetime
import hashlib,json,os,sqlite3
from pathlib import Path
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from yuntapr.experimental.phase_b_v2_stability_review.review import inspect
from yuntapr.training.phase_b_v2_seed2027_restart_v2.ancestor import Guard as FirstFailureGuard
from .protocol import ROOT,OUT,ORDER,LIMITS

PREFIX='docs/phase_b_v2_formal_execution/seed2027_restart_v2/'
OLD_DB='.git/phase_b_v2_seed2027_fresh_restart_v2.sqlite'
STOPPED_CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_FRESH_RESTART_V2'
REGISTERED=frozenset([OLD_DB,'.git/phase_b_v2_seed2027_fresh_restart_v2.once',
    PREFIX+'FAILED_ANCESTOR.json',PREFIX+'release.json',PREFIX+'execution_status.json',
    PREFIX+'.local/B0_MATCHED_V2__E0__s2027/identity.json']+
    [PREFIX+'.local/sessions/session_0001/'+n for n in (
        'supervisor_identity.json','worker_identity.json','bound_identity.json','launch.json',
        'launch.once','operator_launch.json','heartbeat.json','access_and_events.jsonl')])

def evidence_path(relative: str) -> Path:
    # Exact registry before stat/open/resolve. No checkpoint payloads admitted.
    if type(relative) is not str or relative not in REGISTERED or '2025' in relative:
        raise PermissionError('EXACT_STOPPED_ANCESTOR_AUDIT_REGISTRY')
    return ROOT/relative

def read_registered(stack: ExitStack, relative: str) -> bytes:
    path=evidence_path(relative)
    h=stack.enter_context(ReadHandle(str(path),payload=True))
    if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or not 0<h.before['size']<=64*1024**2:
        raise PermissionError('STOPPED_ANCESTOR_OBJECT_OR_SIZE')
    raw=bytearray(h.before['size']);n=0
    while n<len(raw):
        count=h.readinto(memoryview(raw)[n:])
        if not count:raise EOFError('STOPPED_ANCESTOR_TRUNCATED')
        n+=count
    if h.readinto(bytearray(1)) or h.snapshot()!=h.before:raise ValueError('STOPPED_ANCESTOR_CHANGED')
    return bytes(raw)

def verify_old_rows(con) -> None:
    if con.execute('SELECT id,status,reason FROM campaign').fetchone()!=(STOPPED_CAMPAIGN,'ACTIVE',None):
        raise ValueError('EXACT_UNCLEAN_ACTIVE_ANCESTOR_REQUIRED')
    if dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status'))!={'RETURNED_VERIFIED':960}:
        raise ValueError('PRIOR_960_ALL_VERIFIED_REQUIRED')
    expected=[(f'{m}__{a}__s2027',i,'RUNNING' if i==0 else 'PENDING',0,960 if i==0 else 0,None) for i,(m,a) in enumerate(ORDER)]
    if con.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()!=expected:
        raise ValueError('NO_COMPLETE_EPOCH_OR_LAST_REQUIRED')
    if con.execute('SELECT run,epoch,phase FROM epochs').fetchall()!=[(expected[0][0],1,'TRAINING')]:
        raise ValueError('EXACT_INTERRUPTED_FIRST_EPOCH_REQUIRED')
    if con.execute('SELECT n,status FROM sessions ORDER BY n').fetchall()!=[(1,'ACTIVE')]:
        raise ValueError('EXACT_ANCESTOR_SESSION_REQUIRED')

def accounted_bytes(events: list[dict], carried: int, heartbeat: int, allow_trailing_abandon: bool=False):
    """Closed reads only; a single trailing reservation never closed is conservatively
    recorded as abandoned and is NOT charged, instead of guessing its payload bytes."""
    pending=None;total=carried
    for row in events:
        event=row['event']
        if event=='READ_RESERVED':
            if pending is not None:raise ValueError('AMBIGUOUS_ANCESTOR_READ')
            pending=(row['file_key'],row['opened_utc'])
        elif event=='READ_FINISHED':
            if pending!=(row['file_key'],row['opened_utc']):raise ValueError('UNMATCHED_ANCESTOR_READ')
            if row['status']!='SHA_PASS' or row['expected_sha256']!=row['actual_sha256']:
                raise ValueError('ANCESTOR_READ_NOT_VERIFIED')
            pending=None
        elif event!='PUBLIC_METADATA_READ':continue
        if event in ('READ_FINISHED','PUBLIC_METADATA_READ'):
            if type(row['bytes']) is not int or row['bytes']<0:raise ValueError('ANCESTOR_BYTES')
            total+=row['bytes']
    abandoned=None
    if pending is not None:
        if not allow_trailing_abandon:raise ValueError('UNFINISHED_READ_OR_BYTE_ROLLBACK')
        abandoned=pending
    if total<heartbeat:raise ValueError('UNFINISHED_READ_OR_BYTE_ROLLBACK')
    return total,abandoned

def require_stopped(observation: dict) -> None:
    if (observation['campaign']!=STOPPED_CAMPAIGN or
        observation['observation']['effective_state']!='STOPPED_UNCLEAN_NO_LAST' or
        observation['observation']['observed_process_tree_empty'] is not True or
        observation['quota']['reserved']!=2087 or observation['quota']['returned_verified']!=2086 or
        observation['native_probes']['job']['status']!='ABSENT'):
        raise PermissionError('BOTH_NATIVE_PROCESSES_AND_OLD_JOB_MUST_BE_GONE')

class Guard:
    def __init__(self,expected_sha: str):
        self.stack=ExitStack();self.receipt=None
        try:
            path=OUT/'FAILED_ANCESTOR.json'
            h=self.stack.enter_context(ReadHandle(str(path),payload=True))
            if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or not 0<h.before['size']<=1024**2:
                raise PermissionError('NEW_ANCESTOR_RECEIPT_SCOPE')
            raw=bytearray(h.before['size']);n=0
            while n<len(raw):
                count=h.readinto(memoryview(raw)[n:])
                if not count:raise EOFError('ANCESTOR_RECEIPT_TRUNCATED')
                n+=count
            if h.snapshot()!=h.before or hashlib.sha256(raw).hexdigest()!=expected_sha:
                raise ValueError('ANCESTOR_RECEIPT_SHA')
            row=json.loads(raw)
            if (row['schema']!='SEED2027_STOPPED_2087_FRESH_RESTART_ANCESTOR_v3' or
                row['prior_reserved']!=2087 or row['prior_returned_verified']!=2086 or
                row['prior_unverified']!=1 or row['completed_epochs']!=0 or row['adopted_last'] is not None or
                row['original_termination_receipt'] is not False or set(row['pins'])!=REGISTERED):
                raise ValueError('EXACT_THREE_FAILURES_ANCESTRY')
            parents={evidence_path(r).parent for r in REGISTERED}
            for p in tuple(parents):
                while p!=ROOT:p=p.parent;parents.add(p)
            for p in sorted(parents,key=lambda p:len(p.parts)):
                ph=self.stack.enter_context(ReadHandle(str(p),directory=True))
                if os.path.normcase(ph.final_path)!=os.path.normcase(str(p)):raise PermissionError('AUDIT_PARENT_NATIVE_IDENTITY')
            raws={}
            for relative,expected in row['pins'].items():
                data=read_registered(self.stack,relative)
                if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('SEALED_ANCESTOR_BYTES_CHANGED')
                raws[relative]=data
            old_release=json.loads(raws[PREFIX+'release.json'])
            first=self.stack.enter_context(FirstFailureGuard(old_release['failed_ancestor_sha256']))
            with sqlite3.connect((ROOT/OLD_DB).as_uri()+'?mode=ro',uri=True) as con:
                con.execute('PRAGMA query_only=ON');verify_old_rows(con)
            require_stopped(inspect(STOPPED_CAMPAIGN))
            initial=json.loads(raws[PREFIX+'.local/B0_MATCHED_V2__E0__s2027/identity.json'])
            if initial['warm_start'] is not False or initial['initial_sha256']!=first.receipt['prior_fresh_b0_sha256'] or initial['initial_sha256']!=row['prior_fresh_b0_sha256']:
                raise ValueError('SAME_SEED_FRESH_INITIAL_SHA')
            heartbeat=json.loads(raws[PREFIX+'.local/sessions/session_0001/heartbeat.json'])
            launch=json.loads(raws[PREFIX+'.local/sessions/session_0001/launch.json'])
            events=[json.loads(line) for line in raws[PREFIX+'.local/sessions/session_0001/access_and_events.jsonl'].splitlines()]
            total,abandoned=accounted_bytes(events,first.receipt['carried_resources']['content_bytes'],heartbeat['content_bytes'],allow_trailing_abandon=True)
            recorded=row.get('abandoned_read_reservation')
            if recorded!=(list(abandoned) if abandoned is not None else None):
                raise ValueError('ABANDONED_READ_RESERVATION_NOT_RECORDED')
            # Conservatively charge launch -> sealing time, including downtime.
            elapsed=first.receipt['carried_resources']['elapsed_seconds']+(datetime.fromisoformat(row['sealed_utc'])-datetime.fromisoformat(launch['utc'])).total_seconds()
            resources=row['carried_resources']
            if (resources['content_bytes']!=total or abs(resources['elapsed_seconds']-elapsed)>1e-6 or
                elapsed<heartbeat['elapsed_seconds'] or elapsed>LIMITS['max_seconds'] or total>LIMITS['max_read_bytes']):
                raise ValueError('ANCESTOR_RESOURCE_ACCOUNTING_OR_BOUND')
            self.receipt=row
        except BaseException:self.close();raise
    def close(self):self.stack.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

def carried_resources() -> dict:
    release=json.loads((OUT/'release.json').read_bytes())
    with Guard(release['failed_ancestor_sha256']) as g:return dict(g.receipt['carried_resources'])
