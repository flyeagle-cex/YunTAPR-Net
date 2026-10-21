"""Hold the stopped ACTIVE v3 ledger and all ancestry; never rewrite history."""
import atexit,hashlib,json,os,sqlite3
from contextlib import closing
from .protocol import ROOT,OUT,ORDER,LAST_SHA,LIMITS,SOURCE_EPOCH,SOURCE_UPDATE,SOURCE_RUN
from .evidence import scan
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v3 import ancestor as prior
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from yuntapr.experimental.phase_b_v2_stability_review import native
from yuntapr.experimental.phase_b_v2_stability_review.classification import scope,DEAD
SOURCE_PREFIX='docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v3/'
SOURCE_DB='.git/phase_b_v2_seed2027_b1_epoch7_recovery_v3.sqlite'
SOURCE_CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_B1_EPOCH7_RECOVERY_V3'
OBSERVATION='docs/phase_b_v2_console_lifetime_repair/v1/STOP_OBSERVATION.json'
RECOVERY_PREFIX=prior.RECOVERY_PREFIX
SOURCE_CP=prior.SOURCE_CP
COMPLETE_PREFIX=prior.COMPLETE_PREFIX
COMPLETE_SHA=prior.COMPLETE_SHA
COMPLETE_RUN=prior.COMPLETE_RUN
RUN=SOURCE_RUN
CURRENT={SOURCE_DB,'.git/phase_b_v2_seed2027_b1_epoch7_recovery_v3.once',OBSERVATION}|{
 SOURCE_PREFIX+n for n in ('release.json','FAILED_ANCESTOR.json','STARTUP_VERIFICATION.json')}|{
 SOURCE_PREFIX+'.local/sessions/session_0001/'+n for n in ('supervisor_identity.json','worker_identity.json',
 'bound_identity.json','launch.json','launch.once','operator_launch.json','task_owner_started.json',
 'task_registration.json','task_request.json','heartbeat.json','access_and_events.jsonl','preflight.json')}
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
    if con.execute('SELECT id,status,reason FROM campaign').fetchone()!=(SOURCE_CAMPAIGN,'ACTIVE',None):raise ValueError('EXACT_UNCLEAN_ACTIVE_PREDECESSOR')
    if dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status'))!={'RETURNED_VERIFIED':922}:raise ValueError('EXACT_NONREFUNDABLE_922_ATTEMPTS')
    attempts=con.execute('SELECT n,run,update_no,status FROM attempts ORDER BY n').fetchall()
    if attempts!=[(i,RUN,36596+i,'RETURNED_VERIFIED') for i in range(1,923)]:raise ValueError('EXACT_RETURNED_UPDATE_SEQUENCE')
    want=[(f'{m}__{a}__s2027',i,'COMPLETE' if i==0 else ('RUNNING' if i==1 else 'PENDING'),
        9 if i==0 else (7 if i==1 else 0),47052 if i==0 else (37518 if i==1 else 0),COMPLETE_SHA if i==0 else (LAST_SHA if i==1 else None)) for i,(m,a) in enumerate(ORDER)]
    if con.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()!=want:raise ValueError('EXACT_ADOPTED_B0_B1_INTERRUPTED_BOUNDARY')
    phases=[(COMPLETE_RUN,e,'LAST_COMMITTED') for e in range(1,10)]+[(RUN,e,'LAST_COMMITTED' if e<=7 else 'TRAINING') for e in range(1,9)]
    if con.execute('SELECT run,epoch,phase FROM epochs ORDER BY run,epoch').fetchall()!=phases:raise ValueError('EXACT_EPOCH8_TRAINING_INTERRUPTION')
    if con.execute('SELECT n,status FROM sessions').fetchall()!=[(1,'ACTIVE')]:raise ValueError('EXACT_FAILED_SESSION')
    if con.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('SOURCE_SQLITE_INTEGRITY')

def stopped(pool):
    probes=prior.stopped(pool);folder=SOURCE_PREFIX+'.local/sessions/session_0001/'
    a=scope(pool.metadata[folder+'supervisor_identity.json'],pool.metadata[folder+'worker_identity.json'],SOURCE_CAMPAIGN,1)
    latest=dict(owner=native.process(a['owner']),worker=native.process(a['worker']),job=native.job(a['job_name']))
    if latest['owner']['status'] not in DEAD or latest['worker']['status'] not in DEAD or latest['job']['status']!='ABSENT':raise PermissionError('STOPPED_V3_TREE_NOT_GONE')
    probes['unclean_v3_console_lifetime_interruption']=latest;return probes

def load_chain(pool):
    receipt=pool.read(SOURCE_PREFIX+'FAILED_ANCESTOR.json');release=pool.read(SOURCE_PREFIX+'release.json')
    if pool.summaries[SOURCE_PREFIX+'FAILED_ANCESTOR.json']['sha256']!=release['failed_ancestor_sha256']:raise ValueError('FAILED_RELEASE_ANCESTRY')
    for relative,expected in receipt['pins'].items():pool.read(relative,expected)
    prior.load_chain(pool)
    for relative in sorted(CURRENT):pool.read(relative)
    with closing(sqlite3.connect((ROOT/SOURCE_DB).as_uri()+'?mode=ro',uri=True)) as con:
        con.execute('PRAGMA query_only=ON');verify_source(con)
    observation=pool.metadata[OBSERVATION]
    if (observation['snapshot']['reserved']!=166305 or observation['snapshot']['new_reserved']!=922
        or observation['snapshot']['effective_state']!='STOPPED_UNCLEAN'
        or pool.summaries[SOURCE_DB]['sha256']!=observation['historical_db_sha256']):raise ValueError('PINNED_READ_ONLY_STOP_OBSERVATION')
    if pool.summaries[SOURCE_CP+'LAST_epoch_07.pt']['sha256']!=LAST_SHA:raise ValueError('EXACT_B1_EPOCH7_SHA')
    stopped(pool);return pool

class Guard:
    def __init__(self,expected_sha):
        raw=(OUT/'FAILED_ANCESTOR.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('RECOVERY_ANCESTOR_SHA')
        row=json.loads(raw)
        expected=dict(last_sha256=LAST_SHA,prior_reserved=166305,prior_returned_verified=166304,source_epoch=7,source_update=36596,source_campaign=SOURCE_CAMPAIGN,
            abandoned_epoch8_updates=922,additional_replay_attempts=922,abandoned_old_updates=82657,adopted_prior_updates=83648,original_termination_receipt=False,
            restart_kind='EXPLICIT_B1_EPOCH7_RECOVERY_WITH_AUTHORIZED_EPOCH8_REPLAY')
        if any(row.get(k)!=v for k,v in expected.items()):raise ValueError('EXACT_CONSOLE_FREE_RECOVERY_ANCESTRY')
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
    with Guard(release['failed_ancestor_sha256']) as g:return dict(g.receipt['carried_resources'])
