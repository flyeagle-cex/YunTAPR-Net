"""Read-only adoption of the failed B0/E1 recovery campaign."""
from contextlib import ExitStack,closing
from datetime import datetime,timezone
import atexit,hashlib,json,os,sqlite3
from .protocol import LIVE_ROOT,PREVIOUS_ROOT,OUT,ORDER,LAST_SHA,LIMITS,SOURCE_RUN,digest
from .evidence import scan
from .accounting import PRIOR_RESERVED,PRIOR_VERIFIED,ADOPTED,ABANDONED
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from yuntapr.experimental.phase_b_v2_stability_review import native
from yuntapr.experimental.phase_b_v2_stability_review.classification import scope,DEAD
SOURCE_PREFIX='previous/docs/formal_recovery/seed2027_b0_e1_epoch1_v1/'
SOURCE_DB='previous/.git/phase_b_v2_seed2027_b0_e1_epoch1_recovery_v1.sqlite'
SOURCE_CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_B0_E1_EPOCH1_RECOVERY_V1'
SOURCE_CP=SOURCE_PREFIX+'.local/'+SOURCE_RUN+'/checkpoints/'
SESSION=SOURCE_PREFIX+'.local/sessions/session_0001/'
COMPLETE_LAST={
 'B0_MATCHED_V2__E0__s2027':'34022dd6970a95a1fc8ef7a910d5b4a80a1f029ad3617dee577d6dff2b1f4673',
 'B1_V2__E0__s2027':'73715f1e0a45cd364362406ea2d2d62b0dccb5b0aa16a69b02944ddd8d69dd43',
 'B0_MATCHED_V2__E1__s2027':'bfe0e2edfcd5c6544f682148cafff36f2e458855452143fe6f74b141416f847a'}
COMPLETE_RESULTS={
 'B0_MATCHED_V2__E0__s2027':'live/docs/phase_b_v2_formal_execution/seed2027_epoch2_recovery_v2/B0_MATCHED_V2__E0__s2027.json',
 'B1_V2__E0__s2027':'live/docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v7/B1_V2__E0__s2027.json',
 'B0_MATCHED_V2__E1__s2027':SOURCE_PREFIX+'B0_MATCHED_V2__E1__s2027.json'}
REQUIRED={SOURCE_DB,SOURCE_DB.removesuffix('.sqlite')+'.once',*COMPLETE_RESULTS.values()}|{
 SOURCE_PREFIX+n for n in ('release.json','FAILED_ANCESTOR.json','config.json','execution_status.json','watchdog_failure.json')}|{
 SOURCE_PREFIX+'.local/'+SOURCE_RUN+'/'+n for n in ('identity.json','progress.json','train_epoch_06.json','train_epoch_07.json')}|{
 SOURCE_CP+'LAST_epoch_06'+s for s in ('.pt','.ref.json','.registration.json')}|{
 SESSION+n for n in ('supervisor_identity.json','worker_identity.json','gui_bootstrap_identity.json','gui_termination.json','termination.json',
 'heartbeat.json','access_and_events.jsonl','preflight.json','task_registration.json','task_owner_started.json',
 'worker_console_isolation.json','launch.once','launch.json','operator_launch.json','supervisor_failure_private.txt')}
REGISTERED=frozenset(REQUIRED)
_CACHE={}

def lexical(relative):
    if type(relative) is not str or relative not in REGISTERED or '2025' in relative or ':' in relative or '\\' in relative or any(p in ('','.','..') for p in relative.split('/')):raise PermissionError('EXACT_REGISTERED_FAILED_EVIDENCE_SCOPE')
    bucket,name=relative.split('/',1)
    return {'previous':PREVIOUS_ROOT,'live':LIVE_ROOT}[bucket]/name

def source_database():return lexical(SOURCE_DB)

class Pool:
    def __init__(self):self.stack=ExitStack();self.files={};self.metadata={};self.summaries={};self.parents={}
    def parent(self,path):
        base=PREVIOUS_ROOT if path.is_relative_to(PREVIOUS_ROOT) else LIVE_ROOT
        chain=[];p=path.parent
        while p not in self.parents:
            if not p.is_relative_to(base):raise PermissionError('READ_ONLY_REGISTERED_PARENT_SCOPE')
            chain.append(p)
            if p==base:break
            p=p.parent
        for p in reversed(chain):
            h=self.stack.enter_context(ReadHandle(str(p),directory=True))
            if os.path.normcase(h.final_path)!=os.path.normcase(str(p)):raise PermissionError('PARENT_NATIVE_IDENTITY')
            self.parents[p]=h
    def read(self,relative,expected=None):
        path=lexical(relative)
        if relative in self.files:
            if self.files[relative].snapshot()!=self.files[relative].before or expected and self.summaries[relative]['sha256']!=expected:raise ValueError('PINNED_FAILED_OBJECT_CHANGED')
            return self.metadata.get(relative)
        self.parent(path);h=self.stack.enter_context(ReadHandle(str(path),payload=True))
        maximum=2*1024**3 if relative.endswith('.jsonl') else LIMITS['max_checkpoint_bytes'] if relative.endswith('.pt') else 16*1024**2
        if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or not 0<h.before['size']<=maximum:raise ValueError('FAILED_EVIDENCE_SIZE_OR_OBJECT')
        summary,raw=scan(h,event_log=relative.endswith('.jsonl'),keep=relative.endswith('.json'))
        if summary['bytes']!=h.before['size'] or h.snapshot()!=h.before or expected and summary['sha256']!=expected:raise ValueError('FAILED_EVIDENCE_FULL_SHA')
        self.files[relative]=h;self.summaries[relative]=summary
        if raw is not None:self.metadata[relative]=json.loads(raw)
        return self.metadata.get(relative)
    def check(self):
        if any(h.snapshot()!=h.before for h in self.files.values()):raise ValueError('HELD_FAILED_EVIDENCE_CHANGED')
    def close(self):self.stack.close()

def verify_source(con):
    if con.execute('SELECT id,status,reason FROM campaign').fetchone()!=(SOURCE_CAMPAIGN,'FAILED_NO_RETRY','GUI_OWNER_FAILED_NO_RETRY'):raise ValueError('EXACT_FAILED_NO_RETRY')
    if dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status'))!={'RETURNED_VERIFIED':78420}:raise ValueError('EXACT_NONREFUNDABLE_ATTEMPTS')
    if con.execute('SELECT run,count(*),min(update_no),max(update_no),min(n),max(n) FROM attempts GROUP BY run ORDER BY run').fetchall()!=[
        ('B0_MATCHED_V2__E1__s2027',41824,5229,47052,1,41824),(SOURCE_RUN,36596,1,36596,41825,78420)]:raise ValueError('EXACT_UPDATE_HISTORY')
    want=[]
    for i,(m,a) in enumerate(ORDER):
        ident=f'{m}__{a}__s2027'
        want.append((ident,i,'COMPLETE' if i<3 else 'RUNNING' if i==3 else 'PENDING',9 if i<3 else 6 if i==3 else 0,
            47052 if i<3 else 36596 if i==3 else 0,COMPLETE_LAST.get(ident,LAST_SHA if i==3 else None)))
    if con.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()!=want:raise ValueError('EXACT_FAILED_RUN_BOUNDARIES')
    phases=sorted([(r,e,'LAST_COMMITTED') for r in COMPLETE_LAST for e in range(1,10)]+[(SOURCE_RUN,e,'LAST_COMMITTED') for e in range(1,7)]+[(SOURCE_RUN,7,'WAIT_VALIDATION')])
    if con.execute('SELECT run,epoch,phase FROM epochs ORDER BY run,epoch').fetchall()!=phases:raise ValueError('EXACT_33_LAST_AND_UNSEALED_EPOCH7')
    if con.execute('SELECT n,status FROM sessions').fetchall()!=[(1,'ACTIVE')]:raise ValueError('FAILED_SESSION_HISTORY')
    if con.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('SOURCE_SQLITE_INTEGRITY')

def stopped(pool):
    old=scope(pool.metadata[SESSION+'supervisor_identity.json'],pool.metadata[SESSION+'worker_identity.json'],SOURCE_CAMPAIGN,1)
    gui=pool.metadata[SESSION+'gui_bootstrap_identity.json']
    probes=dict(owner=native.process(old['owner']),worker=native.process(old['worker']),gui=native.process(gui),job=native.job(old['job_name']),gui_job=native.job(gui['job_name']))
    if any(probes[k]['status'] not in DEAD for k in ('owner','worker','gui')) or any(probes[k]['status']!='ABSENT' for k in ('job','gui_job')):raise PermissionError('FAILED_TREE_NOT_PROVEN_STOPPED')
    term=pool.metadata[SESSION+'termination.json'];gui_term=pool.metadata[SESSION+'gui_termination.json']
    if term['status']!='STOPPED_NO_RETRY' or not term['job_empty_and_handles_signaled'] or term['failure']['type']!='MemoryError' or term['failure']['phase']!='host_admission':raise ValueError('SUPERVISOR_TERMINATION_EVIDENCE')
    if gui_term['campaign']!=SOURCE_CAMPAIGN or gui_term['supervisor_exit_code']!=1 or not gui_term['job_empty_and_handles_signaled'] or gui_term['automatic_retries']!=0 or gui_term['refunds']!=0:raise ValueError('GUI_TERMINATION_EVIDENCE')
    return probes

def validate_pool(pool):
    old=pool.metadata[SOURCE_PREFIX+'FAILED_ANCESTOR.json'];release=pool.metadata[SOURCE_PREFIX+'release.json']
    if pool.summaries[SOURCE_PREFIX+'FAILED_ANCESTOR.json']['sha256']!=release['failed_ancestor_sha256']:raise ValueError('INHERITED_SEALED_ANCESTRY_SHA')
    if pool.summaries[SOURCE_CP+'LAST_epoch_06.pt']['sha256']!=LAST_SHA:raise ValueError('EXACT_HUMAN_APPROVED_LAST')
    if pool.summaries[SESSION+'access_and_events.jsonl']['trailing_read_reservation'] is not None:raise ValueError('UNRESOLVED_TRAILING_READ_RESERVATION')
    with closing(sqlite3.connect(source_database().as_uri()+'?mode=ro',uri=True)) as con:
        con.execute('PRAGMA query_only=ON');con.execute('BEGIN');verify_source(con)
        histories={ident:pool.metadata[path]['epochs'] for ident,path in COMPLETE_RESULTS.items()}
        histories[SOURCE_RUN]=pool.metadata[SOURCE_PREFIX+'.local/'+SOURCE_RUN+'/progress.json']['epochs']
        for ident,history in histories.items():
            count=6 if ident==SOURCE_RUN else 9
            if [e['epoch'] for e in history]!=list(range(1,count+1)):raise ValueError('COMMITTED_HISTORY_COVERAGE')
            for item in history:
                row=con.execute('SELECT validation,last_receipt FROM epochs WHERE run=? AND epoch=?',(ident,item['epoch'])).fetchone()
                if row[0]!=item['development']['receipt_sha'] or json.loads(row[1])['payload_sha256']!=item['checkpoint']['payload_sha256']:raise ValueError('SOURCE_LEDGER_HISTORY_RECEIPTS')
            expected=LAST_SHA if ident==SOURCE_RUN else COMPLETE_LAST[ident]
            if history[-1]['checkpoint']['payload_sha256']!=expected:raise ValueError('SOURCE_ENDPOINT_LAST_IDENTITY')
    for ident,path in COMPLETE_RESULTS.items():
        result=pool.metadata[path]
        if result['status']!='COMPLETE' or result['run_id']!=ident or result['updates']!=47052:raise ValueError('COMPLETED_RESULT_IDENTITY')
        if path.startswith('live/') and pool.summaries[path]['sha256']!=old['pins'][path.removeprefix('live/')]:raise ValueError('INHERITED_E0_RESULT_BYTES')
    pool.check();return old,stopped(pool)

class Guard:
    def __init__(self,expected_sha):
        raw=(OUT/'FAILED_ANCESTOR.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('NEW_ANCESTOR_RECEIPT_SHA')
        row=json.loads(raw)
        expected=dict(source_campaign=SOURCE_CAMPAIGN,last_sha256=LAST_SHA,source_epoch=6,source_update=31368,
            prior_reserved=PRIOR_RESERVED,prior_returned_verified=PRIOR_VERIFIED,adopted_prior_updates=ADOPTED,
            abandoned_old_updates=ABANDONED,additional_replay_attempts=5228,source_ledger_unchanged=True)
        if any(row.get(k)!=v for k,v in expected.items()) or set(row['pins'])!=REGISTERED:raise ValueError('EXACT_RECOVERY_ANCESTRY')
        if expected_sha not in _CACHE:
            pool=Pool()
            try:
                for p,h in row['pins'].items():pool.read(p,h)
                old,_=validate_pool(pool)
                if row['prior_fresh_b0_sha256']!=old['prior_fresh_b0_sha256']:raise ValueError('ORIGINAL_FRESH_B0_IDENTITY')
                _CACHE[expected_sha]=pool
            except BaseException:pool.close();raise
        self.pool=_CACHE[expected_sha];self.pool.check();stopped(self.pool);self.receipt=row
    def close(self):pass
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

def close_all():
    for pool in _CACHE.values():pool.close()
    _CACHE.clear()
atexit.register(close_all)

def carried_resources():
    release=json.loads((OUT/'release.json').read_bytes())
    with Guard(release['failed_ancestor_sha256']) as guard:
        row=guard.receipt;resources=dict(row['carried_resources'])
        resources['elapsed_seconds']+=(datetime.now(timezone.utc)-datetime.fromisoformat(row['sealed_utc'])).total_seconds()
        return resources
