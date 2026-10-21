"""Preserve the zero-update v5 failure and every earlier immutable ancestor."""
import atexit,hashlib,json,os,sqlite3
from contextlib import closing
from .protocol import ROOT,OUT,ORDER,LAST_SHA,LIMITS,SOURCE_EPOCH,SOURCE_UPDATE,SOURCE_RUN
from .evidence import scan
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v5 import ancestor as prior
# Consumer-facing source identities come from their original audited provider,
# not the failed v5 module which accidentally omitted these three bindings.
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v4.ancestor import COMPLETE_PREFIX,RECOVERY_PREFIX,SOURCE_CP
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from yuntapr.experimental.phase_b_v2_stability_review import native
from yuntapr.experimental.phase_b_v2_stability_review.classification import scope,DEAD

SOURCE_PREFIX='docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v5/'
SOURCE_DB='.git/phase_b_v2_seed2027_b1_epoch7_recovery_v5.sqlite'
SOURCE_CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_B1_EPOCH7_RECOVERY_V5'
COMPLETE_RUN=prior.COMPLETE_RUN
COMPLETE_SHA=prior.COMPLETE_SHA
RUN=SOURCE_RUN
CURRENT={SOURCE_DB,'.git/phase_b_v2_seed2027_b1_epoch7_recovery_v5.once'}|{
 SOURCE_PREFIX+n for n in ('release.json','FAILED_ANCESTOR.json','config.json','execution_status.json','watchdog_failure.json')}|{
 SOURCE_PREFIX+'.local/sessions/session_0001/'+n for n in ('supervisor_identity.json','worker_identity.json','bound_identity.json',
 'launch.json','launch.once','operator_launch.json','termination.json','gui_bootstrap_identity.json','gui_termination.json',
 'task_owner_started.json','task_registration.json','task_request.json','heartbeat.json','access_and_events.jsonl',
 'preflight.json','worker_console_isolation.json','failure_private.txt','supervisor_failure_private.txt')}
REGISTERED=frozenset(set(prior.REGISTERED)|CURRENT)
_CACHE={}

def lexical(relative):
    if type(relative) is not str or '2025' in relative or ':' in relative or '\\' in relative or any(x in ('','.','..') for x in relative.split('/')):
        raise PermissionError('EXACT_ANCESTOR_LEXICAL_SCOPE')
    if relative not in CURRENT:return prior.lexical(relative)
    return ROOT/relative

class Pool(prior.Pool):
    def read(self,relative,expected=None):
        path=lexical(relative)
        if relative in self.files:
            h=self.files[relative]
            if h.snapshot()!=h.before or expected and self.summaries[relative]['sha256']!=expected:raise ValueError('PINNED_OBJECT_CHANGED')
            return self.metadata.get(relative)
        self.parent(path);h=self.stack.enter_context(ReadHandle(str(path),payload=True))
        maximum=2*1024**3 if relative.endswith('.jsonl') else (LIMITS['max_checkpoint_bytes'] if relative.endswith('.pt') else 16*1024**2)
        if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or not 0<h.before['size']<=maximum:raise ValueError('ANCESTOR_SIZE_OR_OBJECT')
        summary,raw=scan(h,event_log=relative.endswith('.jsonl'),keep=relative.endswith('.json'))
        if summary['bytes']!=h.before['size'] or h.snapshot()!=h.before or expected and summary['sha256']!=expected:raise ValueError('ANCESTOR_FULL_SHA_MISMATCH')
        self.files[relative]=h;self.summaries[relative]=summary
        if raw is not None:self.metadata[relative]=json.loads(raw)
        return self.metadata.get(relative)

def verify_source(con):
    if con.execute('SELECT id,status,reason FROM campaign').fetchone()!=(SOURCE_CAMPAIGN,'FAILED_NO_RETRY','GUI_OWNER_FAILED_NO_RETRY'):
        raise ValueError('EXACT_ZERO_UPDATE_INTERFACE_FAILURE')
    if con.execute('SELECT count(*) FROM attempts').fetchone()!=(0,):raise ValueError('ZERO_NEW_ATTEMPTS_REQUIRED')
    want=[(f'{m}__{a}__s2027',i,'COMPLETE' if i==0 else ('RUNNING' if i==1 else 'PENDING'),
        9 if i==0 else (7 if i==1 else 0),47052 if i==0 else (36596 if i==1 else 0),COMPLETE_SHA if i==0 else (LAST_SHA if i==1 else None)) for i,(m,a) in enumerate(ORDER)]
    if con.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()!=want:raise ValueError('EXACT_ADOPTED_B0_B1_ZERO_UPDATE_BOUNDARY')
    phases=[(COMPLETE_RUN,e,'LAST_COMMITTED') for e in range(1,10)]+[(RUN,e,'LAST_COMMITTED') for e in range(1,8)]
    if con.execute('SELECT run,epoch,phase FROM epochs ORDER BY run,epoch').fetchall()!=phases:raise ValueError('EXACT_16_COMMITTED_EPOCHS_REQUIRED')
    if con.execute('SELECT n,status FROM sessions').fetchall()!=[(1,'ACTIVE')]:raise ValueError('EXACT_ACTIVE_FAILED_SESSION')
    if con.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('SOURCE_SQLITE_INTEGRITY')

def stopped(pool):
    probes=prior.stopped(pool);folder=SOURCE_PREFIX+'.local/sessions/session_0001/'
    old=scope(pool.metadata[folder+'supervisor_identity.json'],pool.metadata[folder+'worker_identity.json'],SOURCE_CAMPAIGN,1)
    gui=pool.metadata[folder+'gui_bootstrap_identity.json']
    latest=dict(owner=native.process(old['owner']),worker=native.process(old['worker']),job=native.job(old['job_name']),
        gui=native.process(gui),gui_job=native.job(gui['job_name']))
    if any(latest[k]['status'] not in DEAD for k in ('owner','worker','gui')) or any(latest[k]['status']!='ABSENT' for k in ('job','gui_job')):
        raise PermissionError('FAILED_V5_GUI_OWNER_WORKER_TREE_NOT_EMPTY')
    probes['zero_update_v5_interface_failure']=latest;return probes

def load_chain(pool):
    receipt=pool.read(SOURCE_PREFIX+'FAILED_ANCESTOR.json');release=pool.read(SOURCE_PREFIX+'release.json')
    if pool.summaries[SOURCE_PREFIX+'FAILED_ANCESTOR.json']['sha256']!=release['failed_ancestor_sha256']:raise ValueError('FAILED_RELEASE_ANCESTRY')
    for relative,expected in receipt['pins'].items():pool.read(relative,expected)
    prior.load_chain(pool)
    for relative in sorted(CURRENT):pool.read(relative)
    with closing(sqlite3.connect((ROOT/SOURCE_DB).as_uri()+'?mode=ro',uri=True)) as con:
        con.execute('PRAGMA query_only=ON');verify_source(con)
    folder=SOURCE_PREFIX+'.local/sessions/session_0001/'
    term=pool.metadata[folder+'termination.json'];gui=pool.metadata[folder+'gui_termination.json']
    if term['status']!='STOPPED_NO_RETRY' or not term['job_empty_and_handles_signaled'] or gui['supervisor_exit_code']!=1 or not gui['job_empty_and_handles_signaled']:
        raise ValueError('FAILED_V5_TERMINATION_RECEIPTS')
    result=pool.metadata[SOURCE_PREFIX+'execution_status.json']
    if result['error_type']!='ImportError' or result['quota']['new_reserved']!=0:raise ValueError('EXACT_V5_ZERO_UPDATE_IMPORT_ERROR')
    if pool.summaries[SOURCE_CP+'LAST_epoch_07.pt']['sha256']!=LAST_SHA:raise ValueError('EXACT_B1_EPOCH7_SHA')
    stopped(pool);return pool

class Guard:
    def __init__(self,expected_sha):
        raw=(OUT/'FAILED_ANCESTOR.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('RECOVERY_ANCESTOR_SHA')
        row=json.loads(raw)
        expected=dict(last_sha256=LAST_SHA,prior_reserved=166305,prior_returned_verified=166304,source_epoch=7,source_update=36596,
            source_campaign=SOURCE_CAMPAIGN,zero_update_failed_launch=True,abandoned_epoch8_updates=922,additional_replay_attempts=922,
            abandoned_old_updates=82657,adopted_prior_updates=83648,original_termination_receipt=True,
            restart_kind='EXPLICIT_B1_EPOCH7_RECOVERY_WITH_AUTHORIZED_EPOCH8_REPLAY')
        if any(row.get(k)!=v for k,v in expected.items()):raise ValueError('EXACT_ZERO_UPDATE_INTERFACE_REISSUE_ANCESTRY')
        if expected_sha not in _CACHE:
            pool=Pool()
            try:
                for p,h in row['pins'].items():pool.read(p,h)
                load_chain(pool)
                if set(row['pins'])!=set(pool.files):raise ValueError('ANCESTRY_PIN_COVERAGE')
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
    with Guard(release['failed_ancestor_sha256']) as guard:return dict(guard.receipt['carried_resources'])
