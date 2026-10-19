"""Streaming immutable ancestry with held handles; one explicit committed LAST."""
from contextlib import ExitStack
from importlib import import_module
import atexit,hashlib,json,os,sqlite3
from .protocol import ROOT,OUT,ORDER,LAST_SHA,LIMITS
from .evidence import scan
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from yuntapr.experimental.phase_b_v2_stability_review import native
from yuntapr.experimental.phase_b_v2_stability_review.classification import scope,DEAD

PREFIX='docs/phase_b_v2_formal_execution/seed2027_restart_v4/'
OLD_DB='.git/phase_b_v2_seed2027_fresh_restart_v4.sqlite'
RUN='B0_MATCHED_V2__E0__s2027'
CP=PREFIX+'.local/'+RUN+'/checkpoints/'
LOCAL_NAMES=('release.json','FAILED_ANCESTOR.json','execution_status.json','watchdog_failure.json',
    '.local/'+RUN+'/identity.json','.local/'+RUN+'/progress.json')
CURRENT=set([OLD_DB,'.git/phase_b_v2_seed2027_fresh_restart_v4.once']+
    [PREFIX+n for n in LOCAL_NAMES]+[CP+n for n in ('LAST_epoch_01.pt','LAST_epoch_01.ref.json','LAST_epoch_01.registration.json')]+
    [PREFIX+'.local/sessions/session_0001/'+n for n in ('supervisor_identity.json','worker_identity.json',
    'bound_identity.json','launch.json','launch.once','operator_launch.json','heartbeat.json','access_and_events.jsonl',
    'termination.json','failure_private.txt')])
ZERO_PREFIX='docs/phase_b_v2_formal_execution/seed2027_epoch1_recovery_v1/'
ZERO_DB='.git/phase_b_v2_seed2027_epoch1_recovery_v1.sqlite'
ZERO_CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_EPOCH1_RECOVERY_V1'
ZERO_FILES={ZERO_DB,'.git/phase_b_v2_seed2027_epoch1_recovery_v1.once'}|{
    ZERO_PREFIX+n for n in ('release.json','FAILED_ANCESTOR.json','execution_status.json','watchdog_failure.json',
        '.local/'+RUN+'/identity.json')}|{
    ZERO_PREFIX+'.local/sessions/session_0001/'+n for n in ('supervisor_identity.json','worker_identity.json',
        'bound_identity.json','launch.json','launch.once','operator_launch.json','heartbeat.json','preflight.json',
        'access_and_events.jsonl','termination.json','failure_private.txt')}
CURRENT|=ZERO_FILES
LAYERS=tuple(import_module('yuntapr.training.phase_b_v2_seed2027_restart_v'+str(i)+'.ancestor') for i in range(1,5))
REGISTERED=frozenset(CURRENT|set().union(*(set(m.REGISTERED) if hasattr(m,'REGISTERED') else set() for m in LAYERS)))
# First predecessor has a format-checked registry in its already-pinned receipt.
FIRST_RECEIPT='docs/phase_b_v2_formal_execution/seed2027_restart_v1/FAILED_ANCESTOR.json'
FIRST_PREFIX='docs/phase_b_v2_formal_execution/seed2027_execution_v1/'
FIRST_DB='.git/phase_b_v2_seed2027_fresh_v1.sqlite'
_CACHE={}

def lexical(relative):
    if type(relative) is not str or '2025' in relative or ':' in relative or '\\' in relative or any(x in ('','.','..') for x in relative.split('/')):
        raise PermissionError('ANCESTOR_LEXICAL_SCOPE')
    if relative not in REGISTERED and relative not in (FIRST_DB,'.git/phase_b_v2_seed2027_fresh_v1.once'):
        if not relative.startswith(FIRST_PREFIX) or relative.endswith(('.pt','.pth','.ckpt')):
            raise PermissionError('EXACT_ANCESTOR_REGISTRY')
    if relative.endswith('.pt') and relative!=CP+'LAST_epoch_01.pt':raise PermissionError('ONLY_APPROVED_LAST_PAYLOAD')
    return ROOT/relative

class Pool:
    def __init__(self):self.stack=ExitStack();self.files={};self.metadata={};self.summaries={};self.parents={}
    def parent(self,path):
        chain=[];p=path.parent
        while p not in self.parents:
            if not p.is_relative_to(ROOT):raise PermissionError('ANCESTOR_PARENT_SCOPE')
            chain.append(p)
            if p==ROOT:break
            p=p.parent
        for p in reversed(chain):
            h=self.stack.enter_context(ReadHandle(str(p),directory=True))
            if os.path.normcase(h.final_path)!=os.path.normcase(str(p)):raise PermissionError('PARENT_NATIVE_IDENTITY')
            self.parents[p]=h
    def read(self,relative,expected=None):
        path=lexical(relative)
        if relative in self.files:
            h=self.files[relative]
            if h.snapshot()!=h.before or expected and self.summaries[relative]['sha256']!=expected:raise ValueError('PINNED_OBJECT_CHANGED')
            return self.metadata.get(relative)
        self.parent(path);h=self.stack.enter_context(ReadHandle(str(path),payload=True))
        max_size=2*1024**3 if relative.endswith('.jsonl') else (LIMITS['max_checkpoint_bytes'] if relative.endswith('.pt') else 32*1024**2)
        if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or not 0<h.before['size']<=max_size:raise ValueError('ANCESTOR_SIZE_OR_OBJECT')
        summary,raw=scan(h,event_log=relative.endswith('.jsonl'),keep=relative.endswith('.json'))
        if summary['bytes']!=h.before['size'] or h.snapshot()!=h.before or expected and summary['sha256']!=expected:raise ValueError('ANCESTOR_FULL_SHA_MISMATCH')
        self.files[relative]=h;self.summaries[relative]=summary
        if raw is not None:self.metadata[relative]=json.loads(raw)
        return self.metadata.get(relative)
    def check(self):
        if any(h.snapshot()!=h.before for h in self.files.values()):raise ValueError('HELD_ANCESTOR_CHANGED')
    def close(self):self.stack.close()

def verify_current(con):
    if con.execute('SELECT id,status,reason FROM campaign').fetchone()!=('YUNTAPR_PHASE_B_V2_SEED2027_FRESH_RESTART_V4','FAILED_NO_RETRY','MemoryError'):raise ValueError('EXACT_STOPPED_CAMPAIGN')
    if dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status'))!={'RETURNED_VERIFIED':5228}:raise ValueError('EXACT_NO_REPLAY_QUOTA')
    want=[(f'{m}__{a}__s2027',i,'RUNNING' if i==0 else 'PENDING',1 if i==0 else 0,5228 if i==0 else 0,LAST_SHA if i==0 else None) for i,(m,a) in enumerate(ORDER)]
    if con.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()!=want:raise ValueError('EXACT_COMMITTED_EPOCH1')
    if con.execute('SELECT run,epoch,phase FROM epochs').fetchall()!=[(RUN,1,'LAST_COMMITTED')]:raise ValueError('NO_UNFINISHED_UPDATE_AFTER_LAST')

def stopped(pool):
    owner=pool.metadata[PREFIX+'.local/sessions/session_0001/supervisor_identity.json']
    worker=pool.metadata[PREFIX+'.local/sessions/session_0001/worker_identity.json']
    a=scope(owner,worker,'YUNTAPR_PHASE_B_V2_SEED2027_FRESH_RESTART_V4',1)
    probes=dict(owner=native.process(a['owner']),worker=native.process(a['worker']),job=native.job(a['job_name']))
    if probes['owner']['status'] not in DEAD or probes['worker']['status'] not in DEAD or probes['job']['status']!='ABSENT':raise PermissionError('OLD_PROCESS_OR_JOB_NOT_GONE')
    z=ZERO_PREFIX+'.local/sessions/session_0001/'
    a=scope(pool.metadata[z+'supervisor_identity.json'],pool.metadata[z+'worker_identity.json'],ZERO_CAMPAIGN,1)
    zero=dict(owner=native.process(a['owner']),worker=native.process(a['worker']),job=native.job(a['job_name']))
    if zero['owner']['status'] not in DEAD or zero['worker']['status'] not in DEAD or zero['job']['status']!='ABSENT':
        raise PermissionError('ZERO_UPDATE_PREDECESSOR_NOT_GONE')
    probes['zero_update_predecessor']=zero
    return probes

def verify_zero(con):
    if con.execute('SELECT id,status,reason FROM campaign').fetchone()!=(ZERO_CAMPAIGN,'FAILED_NO_RETRY','AUTHORIZED_LAST_METRICS'):
        raise ValueError('EXACT_ZERO_UPDATE_FAILURE')
    if con.execute('SELECT count(*) FROM attempts').fetchone()!=(0,):raise ValueError('ZERO_UPDATE_PREDECESSOR_CONSUMED_QUOTA')
    want=[(f'{m}__{a}__s2027',i,'RUNNING' if i==0 else 'PENDING',1 if i==0 else 0,5228 if i==0 else 0,LAST_SHA if i==0 else None) for i,(m,a) in enumerate(ORDER)]
    if con.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()!=want:raise ValueError('ZERO_UPDATE_BOUNDARY_CHANGED')
    if con.execute('SELECT run,epoch,phase FROM epochs').fetchall()!=[(RUN,1,'LAST_COMMITTED')]:
        raise ValueError('ZERO_UPDATE_UNFINISHED_EPOCH')

def load_chain(pool):
    """Immutable receipt graph, verified iteratively rather than recursive full logs."""
    top=pool.read(PREFIX+'FAILED_ANCESTOR.json')
    release=pool.read(PREFIX+'release.json')
    if pool.summaries[PREFIX+'FAILED_ANCESTOR.json']['sha256']!=release['failed_ancestor_sha256']:
        raise ValueError('PREDECESSOR_RELEASE_ANCESTRY')
    zero_ancestor=pool.read(ZERO_PREFIX+'FAILED_ANCESTOR.json')
    zero_release=pool.read(ZERO_PREFIX+'release.json')
    if pool.summaries[ZERO_PREFIX+'FAILED_ANCESTOR.json']['sha256']!=zero_release['failed_ancestor_sha256']:
        raise ValueError('ZERO_UPDATE_RELEASE_ANCESTRY')
    queue=[top,zero_ancestor];seen=set()
    while queue:
        row=queue.pop()
        for relative,expected in row['pins'].items():
            val=pool.read(relative,expected)
            if relative.endswith('/FAILED_ANCESTOR.json') and relative not in seen:
                seen.add(relative);queue.append(val)
    for relative in sorted(CURRENT):pool.read(relative)
    for module in LAYERS:
        with sqlite3.connect((ROOT/module.OLD_DB).as_uri()+'?mode=ro',uri=True) as con:
            con.execute('PRAGMA query_only=ON');module.verify_old_rows(con)
    with sqlite3.connect((ROOT/OLD_DB).as_uri()+'?mode=ro',uri=True) as con:
        con.execute('PRAGMA query_only=ON');verify_current(con)
    with sqlite3.connect((ROOT/ZERO_DB).as_uri()+'?mode=ro',uri=True) as con:
        con.execute('PRAGMA query_only=ON');verify_zero(con)
        if con.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('ZERO_UPDATE_SQLITE_INTEGRITY')
    term=pool.metadata[ZERO_PREFIX+'.local/sessions/session_0001/termination.json']
    if not term['job_empty_and_handles_signaled'] or term['status']!='STOPPED_NO_RETRY':
        raise ValueError('ZERO_UPDATE_TERMINATION_RECEIPT')
    stopped(pool)
    return pool

class Guard:
    def __init__(self,expected_sha):
        raw=(OUT/'FAILED_ANCESTOR.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('RECOVERY_ANCESTOR_SHA')
        row=json.loads(raw)
        if (row['last_sha256']!=LAST_SHA or row['prior_reserved']!=75327 or row['prior_returned_verified']!=75326 or row['source_update']!=5228
            or row['source_epoch']!=1 or row['restart_kind']!='EXPLICIT_LAST_RECOVERY_NO_REPLAY'):
            raise ValueError('EXACT_RECOVERY_ANCESTRY')
        if row['zero_update_predecessor']!=ZERO_CAMPAIGN or row['zero_update_attempts']!=0:
            raise ValueError('EXACT_ZERO_UPDATE_REPUBLICATION')
        if expected_sha not in _CACHE:
            pool=Pool()
            try:
                for p,h in row['pins'].items():pool.read(p,h)
                load_chain(pool)
                if set(row['pins'])!=set(pool.files):raise ValueError('ANCESTRY_PIN_COVERAGE')
                if pool.summaries[CP+'LAST_epoch_01.pt']['sha256']!=LAST_SHA:raise ValueError('APPROVED_LAST_SHA')
                _CACHE[expected_sha]=pool
            except BaseException:pool.close();raise
        self.pool=_CACHE[expected_sha];self.pool.check();stopped(self.pool);self.receipt=row
    def close(self):pass # Process-owned no-write/delete handles remain held until process exit.
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

def close_all():
    for p in _CACHE.values():p.close()
    _CACHE.clear()
atexit.register(close_all)

def carried_resources():
    r=json.loads((OUT/'release.json').read_bytes())
    with Guard(r['failed_ancestor_sha256']) as g:return dict(g.receipt['carried_resources'])
