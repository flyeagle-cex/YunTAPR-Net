"""Read-only binding to the stopped 386-attempt predecessor; no weights opened."""
from __future__ import annotations
import ctypes as C
import hashlib,json,os,sqlite3
from pathlib import Path
from ctypes import wintypes as W
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
    K,bind,open_process,native_identity,exited,close_handle)
from .protocol import ROOT,OUT,OLD_CAMPAIGN,ORDER
from .accounting import prior_content_bytes

PREFIX='docs/phase_b_v2_formal_execution/seed2027_execution_v1/'
OLD_DB='.git/phase_b_v2_seed2027_fresh_v1.sqlite'
WITNESSES={OLD_DB,'.git/phase_b_v2_seed2027_fresh_v1.once'}

def evidence_path(relative: str) -> Path:
    if (type(relative) is not str or '\\' in relative or ':' in relative or
        relative.startswith('/') or any(p in ('','..','.') for p in relative.split('/')) or
        '2025' in relative or not (relative.startswith(PREFIX) or relative in WITNESSES) or
        Path(relative).suffix not in ('.json','.jsonl','.txt','.once','.sqlite')):
        raise PermissionError('EXACT_PRIOR_AUDIT_SCOPE_NO_MODEL_WEIGHTS')
    return ROOT/relative

def verify_old_rows(con) -> None:
    if con.execute('SELECT id,status,reason FROM campaign').fetchone()!=(OLD_CAMPAIGN,'FAILED_NO_RETRY','AVAILABLE_COMMIT_LIMIT'):
        raise ValueError('FAILED_PREDECESSOR_STATE')
    counts=dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status'))
    if counts!={'RETURNED_VERIFIED':385,'RESERVED_BEFORE_CALL':1}:
        raise ValueError('PRIOR_386_ATTEMPTS_385_VERIFIED_ONE_UNVERIFIED')
    expected=[(f'{m}__{a}__s2027',i,'RUNNING' if i==0 else 'PENDING',0,385 if i==0 else 0,None) for i,(m,a) in enumerate(ORDER)]
    if con.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()!=expected:
        raise ValueError('NO_COMPLETED_RUN_EPOCH_OR_ADOPTED_LAST')
    if con.execute('SELECT run,epoch,phase FROM epochs').fetchall()!=[(expected[0][0],1,'TRAINING')]:
        raise ValueError('EXACT_INCOMPLETE_FIRST_EPOCH')

def assert_process_gone(identity):
    C.set_last_error(0);h=open_process(0x00100000|0x1000,False,identity['pid'])
    if not h:
        if C.get_last_error()==87:return
        raise C.WinError(C.get_last_error())
    try:
        actual=native_identity(h)
        if all(actual[k]==identity[k] for k in actual) and not exited(h):
            raise PermissionError('OLD_NATIVE_PROCESS_STILL_RUNNING')
    finally:close_handle(h)

class Guard:
    def __init__(self,expected_sha: str):
        self.handles=[];self.receipt=None
        try:
            raw=(OUT/'FAILED_ANCESTOR.json').read_bytes()
            if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('FAILED_ANCESTOR_RECEIPT_SHA')
            row=json.loads(raw)
            if (row.get('schema')!='SEED2027_FAILED_386_FRESH_RESTART_ANCESTOR_v1' or
                row.get('old_campaign')!=OLD_CAMPAIGN or row.get('prior_reserved')!=386 or
                row.get('prior_returned_verified')!=385 or row.get('prior_unverified')!=1 or
                row.get('completed_epochs')!=0 or row.get('adopted_last') is not None or
                row.get('job_empty_and_handles_signaled') is not True):
                raise ValueError('NO_LAST_FRESH_RESTART_ANCESTRY_ONLY')
            verified_json={};verified_events=None
            events_key=PREFIX+'.local/sessions/session_0001/access_and_events.jsonl'
            required={OLD_DB,'.git/phase_b_v2_seed2027_fresh_v1.once',
                PREFIX+'.local/sessions/session_0001/termination.json',
                PREFIX+'.local/sessions/session_0001/supervisor_identity.json',
                PREFIX+'.local/B0_MATCHED_V2__E0__s2027/identity.json',events_key,
                PREFIX+'.local/sessions/session_0001/heartbeat.json'}
            if not required.issubset(row['pins']):raise ValueError('REQUIRED_FAILED_EVIDENCE_PINS')
            for relative,expected in row['pins'].items():
                path=evidence_path(relative);h=ReadHandle(str(path),payload=True);self.handles.append(h)
                if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or not 0<h.before['size']<=64*1024**2:
                    raise PermissionError('OLD_AUDIT_NATIVE_OBJECT_OR_SIZE')
                digest=hashlib.sha256();buf=bytearray(1024**2);n=0;parts=[]
                while count:=h.readinto(buf):
                    n+=count;digest.update(memoryview(buf)[:count])
                    if relative in required and relative.endswith(('.json','.jsonl')):parts.append(bytes(buf[:count]))
                if n!=h.before['size'] or h.snapshot()!=h.before or digest.hexdigest()!=expected:
                    raise ValueError('OLD_SEALED_EVIDENCE_CHANGED')
                if parts:
                    if relative==events_key:verified_events=[json.loads(line) for line in b''.join(parts).splitlines()]
                    else:verified_json[relative]=json.loads(b''.join(parts))
            if not WITNESSES.issubset(row['pins']):raise ValueError('SEALED_DB_AND_ONCE_REQUIRED')
            with sqlite3.connect((ROOT/OLD_DB).as_uri()+'?mode=ro',uri=True) as con:
                con.execute('PRAGMA query_only=ON');verify_old_rows(con)
            term=verified_json[PREFIX+'.local/sessions/session_0001/termination.json']
            owner=verified_json[PREFIX+'.local/sessions/session_0001/supervisor_identity.json']
            initial=verified_json[PREFIX+'.local/B0_MATCHED_V2__E0__s2027/identity.json']
            if initial['initial_sha256']!=row['prior_fresh_b0_sha256'] or initial['warm_start'] is not False:
                raise ValueError('PRIOR_FRESH_INITIAL_SHA')
            if term['job_empty_and_handles_signaled'] is not True:raise PermissionError('OLD_JOB_NOT_CLOSED')
            assert_process_gone(term['worker_identity']);assert_process_gone(owner)
            open_job=bind(K,'OpenJobObjectW',[W.DWORD,W.BOOL,W.LPCWSTR],W.HANDLE)
            C.set_last_error(0);job=open_job(4,False,owner['job_name'])
            if job:
                close_handle(job);raise PermissionError('OLD_NAMED_JOB_STILL_EXISTS')
            if C.get_last_error()!=2:raise C.WinError(C.get_last_error())
            resources=row['carried_resources']
            heartbeat=verified_json[PREFIX+'.local/sessions/session_0001/heartbeat.json']
            if (type(resources['content_bytes']) is not int or resources['content_bytes']<0 or
                resources['content_bytes']!=prior_content_bytes(verified_events,heartbeat['content_bytes']) or
                resources['elapsed_seconds']<term['elapsed_seconds']):
                raise ValueError('OLD_RESOURCE_USAGE_CANNOT_BE_REFUNDED')
            self.receipt=row
        except BaseException:self.close();raise
    def close(self):
        for h in reversed(self.handles):h.close()
        self.handles.clear()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

def carried_resources() -> dict:
    release=json.loads((OUT/'release.json').read_bytes())
    with Guard(release['failed_ancestor_sha256']) as g:return dict(g.receipt['carried_resources'])
