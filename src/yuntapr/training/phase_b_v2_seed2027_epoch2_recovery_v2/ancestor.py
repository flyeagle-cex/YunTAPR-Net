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
V4_LAST_SHA='e4c0162492ab10bfe3136fa8117c0f5e111078957fa35832e0a88cb5dc1ab0ff'
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
SOURCE_PREFIX='docs/phase_b_v2_formal_execution/seed2027_epoch1_recovery_v2/'
SOURCE_DB='.git/phase_b_v2_seed2027_epoch1_recovery_v2.sqlite'
SOURCE_CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_EPOCH1_RECOVERY_V2'
SOURCE_CP=SOURCE_PREFIX+'.local/'+RUN+'/checkpoints/'
SOURCE_FILES={SOURCE_DB,'.git/phase_b_v2_seed2027_epoch1_recovery_v2.once'}|{
    SOURCE_PREFIX+n for n in ('release.json','FAILED_ANCESTOR.json','execution_status.json',
        '.local/'+RUN+'/identity.json','.local/'+RUN+'/progress.json',
        '.local/'+RUN+'/authorized_epoch1_recovery.json')}|{
    SOURCE_CP+n for n in ('LAST_epoch_02.pt','LAST_epoch_02.ref.json','LAST_epoch_02.registration.json')}|{
    SOURCE_PREFIX+'.local/sessions/session_0001/'+n for n in ('supervisor_identity.json','worker_identity.json',
        'bound_identity.json','launch.json','launch.once','operator_launch.json','heartbeat.json','preflight.json','access_and_events.jsonl')}
CURRENT|=SOURCE_FILES
FAILED_PREFIX='docs/phase_b_v2_formal_execution/seed2027_epoch2_recovery_v1/'
FAILED_DB='.git/phase_b_v2_seed2027_epoch2_recovery_v1.sqlite'
FAILED_CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_EPOCH2_RECOVERY_V1'
FAILED_FILES={FAILED_DB,'.git/phase_b_v2_seed2027_epoch2_recovery_v1.once'}|{
    FAILED_PREFIX+n for n in ('release.json','FAILED_ANCESTOR.json','execution_status.json','watchdog_failure.json',
        '.local/'+RUN+'/identity.json','.local/'+RUN+'/authorized_epoch2_recovery.json')}|{
    FAILED_PREFIX+'.local/sessions/session_0001/'+n for n in ('supervisor_identity.json','worker_identity.json',
        'bound_identity.json','launch.json','launch.once','operator_launch.json','heartbeat.json','heartbeat.json.part',
        'preflight.json','access_and_events.jsonl','termination.json','failure_private.txt')}
CURRENT|=FAILED_FILES
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
    if relative.endswith('.pt') and relative not in (CP+'LAST_epoch_01.pt',SOURCE_CP+'LAST_epoch_02.pt'):
        raise PermissionError('ONLY_EXACT_LAST_AND_REGISTERED_ANCESTOR_HASH')
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
    want=[(f'{m}__{a}__s2027',i,'RUNNING' if i==0 else 'PENDING',1 if i==0 else 0,5228 if i==0 else 0,V4_LAST_SHA if i==0 else None) for i,(m,a) in enumerate(ORDER)]
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
    s=SOURCE_PREFIX+'.local/sessions/session_0001/'
    a=scope(pool.metadata[s+'supervisor_identity.json'],pool.metadata[s+'worker_identity.json'],SOURCE_CAMPAIGN,1)
    recent=dict(owner=native.process(a['owner']),worker=native.process(a['worker']),job=native.job(a['job_name']))
    if recent['owner']['status'] not in DEAD or recent['worker']['status'] not in DEAD or recent['job']['status']!='ABSENT':
        raise PermissionError('UNCLEAN_SOURCE_PROCESS_OR_JOB_NOT_GONE')
    probes['unclean_epoch3_source']=recent
    f=FAILED_PREFIX+'.local/sessions/session_0001/'
    a=scope(pool.metadata[f+'supervisor_identity.json'],pool.metadata[f+'worker_identity.json'],FAILED_CAMPAIGN,1)
    failed=dict(owner=native.process(a['owner']),worker=native.process(a['worker']),job=native.job(a['job_name']))
    if failed['owner']['status'] not in DEAD or failed['worker']['status'] not in DEAD or failed['job']['status']!='ABSENT':
        raise PermissionError('MUTEX_FAILURE_PROCESS_OR_JOB_NOT_GONE')
    probes['status_io_failed_predecessor']=failed
    return probes

def verify_failed(con):
    """The 632 completed attempts remain charged; no synthetic PAUSED rewrite."""
    if con.execute('SELECT id,status,reason FROM campaign').fetchone()!=(FAILED_CAMPAIGN,'FAILED_NO_RETRY','PermissionError'):
        raise ValueError('EXACT_STATUS_IO_FAILURE')
    if dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status'))!={'RETURNED_VERIFIED':632}:
        raise ValueError('EXACT_632_NONREFUNDABLE_ATTEMPTS')
    want=[(f'{m}__{a}__s2027',i,'RUNNING' if i==0 else 'PENDING',2 if i==0 else 0,11088 if i==0 else 0,LAST_SHA if i==0 else None) for i,(m,a) in enumerate(ORDER)]
    if con.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()!=want:raise ValueError('EXACT_FAILED_EPOCH3_BOUNDARY')
    if con.execute('SELECT run,epoch,phase FROM epochs ORDER BY epoch').fetchall()!=[(RUN,1,'LAST_COMMITTED'),(RUN,2,'LAST_COMMITTED'),(RUN,3,'TRAINING')]:
        raise ValueError('EXACT_FAILED_EPOCH_PHASES')
    if con.execute('SELECT n,status FROM sessions').fetchall()!=[(1,'ACTIVE')]:raise ValueError('EXACT_FAILED_SESSION')

def verify_zero(con):
    if con.execute('SELECT id,status,reason FROM campaign').fetchone()!=(ZERO_CAMPAIGN,'FAILED_NO_RETRY','AUTHORIZED_LAST_METRICS'):
        raise ValueError('EXACT_ZERO_UPDATE_FAILURE')
    if con.execute('SELECT count(*) FROM attempts').fetchone()!=(0,):raise ValueError('ZERO_UPDATE_PREDECESSOR_CONSUMED_QUOTA')
    want=[(f'{m}__{a}__s2027',i,'RUNNING' if i==0 else 'PENDING',1 if i==0 else 0,5228 if i==0 else 0,V4_LAST_SHA if i==0 else None) for i,(m,a) in enumerate(ORDER)]
    if con.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()!=want:raise ValueError('ZERO_UPDATE_BOUNDARY_CHANGED')
    if con.execute('SELECT run,epoch,phase FROM epochs').fetchall()!=[(RUN,1,'LAST_COMMITTED')]:
        raise ValueError('ZERO_UPDATE_UNFINISHED_EPOCH')

def verify_source(con):
    """Observe the stale ACTIVE source; never rewrite it into PAUSED or FAILED."""
    if con.execute('SELECT id,status,reason FROM campaign').fetchone()!=(SOURCE_CAMPAIGN,'ACTIVE',None):
        raise ValueError('EXACT_UNCLEAN_SOURCE_STATE')
    if dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status'))!={'RETURNED_VERIFIED':10456}:
        raise ValueError('EXACT_NONREFUNDABLE_SOURCE_ATTEMPTS')
    want=[(f'{m}__{a}__s2027',i,'RUNNING' if i==0 else 'PENDING',2 if i==0 else 0,15684 if i==0 else 0,LAST_SHA if i==0 else None) for i,(m,a) in enumerate(ORDER)]
    if con.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()!=want:raise ValueError('EXACT_EPOCH2_LAST_EPOCH3_UPDATES')
    if con.execute('SELECT run,epoch,phase FROM epochs ORDER BY epoch').fetchall()!=[(RUN,1,'LAST_COMMITTED'),(RUN,2,'LAST_COMMITTED'),(RUN,3,'WAIT_VALIDATION')]:
        raise ValueError('EXACT_ABANDONED_EPOCH3_BOUNDARY')
    if con.execute('SELECT n,status FROM sessions').fetchall()!=[(1,'ACTIVE')]:raise ValueError('EXACT_SOURCE_SESSION')

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
    source_ancestor=pool.read(SOURCE_PREFIX+'FAILED_ANCESTOR.json')
    source_release=pool.read(SOURCE_PREFIX+'release.json')
    if pool.summaries[SOURCE_PREFIX+'FAILED_ANCESTOR.json']['sha256']!=source_release['failed_ancestor_sha256']:
        raise ValueError('UNCLEAN_SOURCE_RELEASE_ANCESTRY')
    failed_ancestor=pool.read(FAILED_PREFIX+'FAILED_ANCESTOR.json')
    failed_release=pool.read(FAILED_PREFIX+'release.json')
    if pool.summaries[FAILED_PREFIX+'FAILED_ANCESTOR.json']['sha256']!=failed_release['failed_ancestor_sha256']:
        raise ValueError('STATUS_IO_FAILED_RELEASE_ANCESTRY')
    queue=[top,zero_ancestor,source_ancestor,failed_ancestor];seen=set()
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
    with sqlite3.connect((ROOT/SOURCE_DB).as_uri()+'?mode=ro',uri=True) as con:
        con.execute('PRAGMA query_only=ON');verify_source(con)
        if con.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('UNCLEAN_SOURCE_SQLITE_INTEGRITY')
    with sqlite3.connect((ROOT/FAILED_DB).as_uri()+'?mode=ro',uri=True) as con:
        con.execute('PRAGMA query_only=ON');verify_failed(con)
        if con.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('FAILED_SQLITE_INTEGRITY')
    term=pool.metadata[FAILED_PREFIX+'.local/sessions/session_0001/termination.json']
    if not term['job_empty_and_handles_signaled'] or term['status']!='STOPPED_NO_RETRY':
        raise ValueError('FAILED_STATUS_IO_TERMINATION_RECEIPT')
    stopped(pool)
    return pool

class Guard:
    def __init__(self,expected_sha):
        raw=(OUT/'FAILED_ANCESTOR.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('RECOVERY_ANCESTOR_SHA')
        row=json.loads(raw)
        if (row['last_sha256']!=LAST_SHA or row['prior_reserved']!=86415 or row['prior_returned_verified']!=86414 or row['source_update']!=10456
            or row['source_epoch']!=2 or row['restart_kind']!='EXPLICIT_LAST_RECOVERY_WITH_AUTHORIZED_EPOCH3_REPLAY'):
            raise ValueError('EXACT_RECOVERY_ANCESTRY')
        if (row['source_campaign']!=SOURCE_CAMPAIGN or row['abandoned_epoch3_updates']!=5860 or row['additional_replay_attempts']!=632
            or row['latest_failed_campaign']!=FAILED_CAMPAIGN or row['latest_failed_attempts']!=632
            or row['abandoned_old_updates']!=75959):
            raise ValueError('EXACT_AUTHORIZED_EPOCH3_REPLAY')
        if expected_sha not in _CACHE:
            pool=Pool()
            try:
                for p,h in row['pins'].items():pool.read(p,h)
                load_chain(pool)
                if set(row['pins'])!=set(pool.files):raise ValueError('ANCESTRY_PIN_COVERAGE')
                if pool.summaries[SOURCE_CP+'LAST_epoch_02.pt']['sha256']!=LAST_SHA:raise ValueError('APPROVED_LAST_SHA')
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
