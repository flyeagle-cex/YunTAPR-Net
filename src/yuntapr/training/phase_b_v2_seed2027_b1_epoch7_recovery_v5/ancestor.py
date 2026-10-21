"""Seal the zero-update v4 failed launch; keep the 922-update ancestry unchanged."""
import atexit,hashlib,json,os,sqlite3,subprocess
from contextlib import closing
from .protocol import ROOT,OUT,ORDER,LAST_SHA,LIMITS,SOURCE_EPOCH,SOURCE_UPDATE,SOURCE_RUN
from .evidence import scan
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v4 import ancestor as prior
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle

SOURCE_PREFIX='docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v4/'
SOURCE_DB='.git/phase_b_v2_seed2027_b1_epoch7_recovery_v4.sqlite'
SOURCE_CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_B1_EPOCH7_RECOVERY_V4'
SOURCE_TASK='YunTAPR_Seed2027_B1E7V4_0001_0a767d2a74795f003b574cb318cd77aa'
COMPLETE_RUN='B0_MATCHED_V2__E0__s2027'
COMPLETE_SHA='34022dd6970a95a1fc8ef7a910d5b4a80a1f029ad3617dee577d6dff2b1f4673'
RUN=SOURCE_RUN
CURRENT={SOURCE_DB,'.git/phase_b_v2_seed2027_b1_epoch7_recovery_v4.once'}|{
 SOURCE_PREFIX+n for n in ('release.json','FAILED_ANCESTOR.json','config.json')}|{
 SOURCE_PREFIX+'.local/sessions/session_0001/'+n for n in ('task_request.json','gui_failure.json','gui_bootstrap_failure_private.txt')}
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
    if con.execute('SELECT id,status,reason FROM campaign').fetchone()!=(SOURCE_CAMPAIGN,'FAILED_NO_RETRY','OPERATOR_SPAWN_FAILED_OR_UNCERTAIN'):
        raise ValueError('EXACT_ZERO_UPDATE_FAILED_LAUNCH_PREDECESSOR')
    if con.execute('SELECT status,count(*) FROM attempts GROUP BY status').fetchall()!=[]:
        raise ValueError('ZERO_NEW_ATTEMPTS_REQUIRED')
    want=[(f'{m}__{a}__s2027',i,'COMPLETE' if i==0 else ('RUNNING' if i==1 else 'PENDING'),
        9 if i==0 else (7 if i==1 else 0),47052 if i==0 else (36596 if i==1 else 0),COMPLETE_SHA if i==0 else (LAST_SHA if i==1 else None)) for i,(m,a) in enumerate(ORDER)]
    if con.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()!=want:raise ValueError('EXACT_ADOPTED_B0_B1_ZERO_UPDATE_BOUNDARY')
    phases=[(COMPLETE_RUN,e,'LAST_COMMITTED') for e in range(1,10)]+[(RUN,e,'LAST_COMMITTED') for e in range(1,8)]
    if con.execute('SELECT run,epoch,phase FROM epochs ORDER BY run,epoch').fetchall()!=phases:raise ValueError('EXACT_16_COMMITTED_EPOCHS_REQUIRED')
    if con.execute('SELECT n,status FROM sessions').fetchall()!=[(1,'CLAIMED')]:raise ValueError('EXACT_CLAIMED_ZERO_UPDATE_SESSION')
    if con.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('SOURCE_SQLITE_INTEGRITY')

def task_state():
    script=("$t=Get-ScheduledTask -TaskName '"+SOURCE_TASK+"' -ErrorAction SilentlyContinue;"
            "if(-not $t){'ABSENT'}else{[pscustomobject]@{state=$t.State.ToString();result=(Get-ScheduledTaskInfo -TaskName $t.TaskName).LastTaskResult}|ConvertTo-Json -Compress}")
    r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20)
    if r.returncode:raise PermissionError('SOURCE_SCHEDULED_TASK_QUERY_FAILED')
    out=r.stdout.strip()
    if out=='ABSENT':return dict(status='ABSENT')
    return dict(status='PRESENT',**json.loads(out))

def stopped(pool):
    task=task_state()
    if task['status']!='PRESENT' or task.get('state') not in ('Ready','Completed','Disabled') or int(task.get('result'))!=1:
        raise PermissionError('ZERO_UPDATE_FAILED_TASK_OBSERVATION_REQUIRED')
    for name in ('supervisor_identity.json','worker_identity.json','task_registration.json','operator_launch.json'):
        if (ROOT/SOURCE_PREFIX/'.local/sessions/session_0001'/name).exists():raise PermissionError('NO_OWNER_WORKER_ARTIFACTS_ALLOWED')
    return dict(scheduled_task=task)

def load_chain(pool):
    prior_receipt=pool.read(SOURCE_PREFIX+'FAILED_ANCESTOR.json');release=pool.read(SOURCE_PREFIX+'release.json')
    if pool.summaries[SOURCE_PREFIX+'FAILED_ANCESTOR.json']['sha256']!=release['failed_ancestor_sha256']:raise ValueError('FAILED_RELEASE_ANCESTRY')
    for relative,expected in prior_receipt['pins'].items():pool.read(relative,expected)
    prior.load_chain(pool)
    for relative in sorted(CURRENT):pool.read(relative)
    with closing(sqlite3.connect((ROOT/SOURCE_DB).as_uri()+'?mode=ro',uri=True)) as con:
        con.execute('PRAGMA query_only=ON');verify_source(con)
    stopped(pool);return pool

class Guard:
    def __init__(self,expected_sha):
        raw=(OUT/'FAILED_ANCESTOR.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('RECOVERY_ANCESTOR_SHA')
        row=json.loads(raw)
        expected=dict(last_sha256=LAST_SHA,prior_reserved=166305,prior_returned_verified=166304,source_epoch=7,source_update=36596,
            source_campaign=SOURCE_CAMPAIGN,zero_update_failed_launch=True,abandoned_epoch8_updates=922,additional_replay_attempts=922,
            abandoned_old_updates=82657,adopted_prior_updates=83648,original_termination_receipt=False,
            restart_kind='EXPLICIT_B1_EPOCH7_RECOVERY_WITH_AUTHORIZED_EPOCH8_REPLAY')
        if any(row.get(k)!=v for k,v in expected.items()):raise ValueError('EXACT_ZERO_UPDATE_REISSUE_ANCESTRY')
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
