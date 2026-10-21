"""Two independently budgeted fresh campaigns; no launch in this task."""
from __future__ import annotations
import hashlib,json,os,subprocess
from pathlib import Path
from yuntapr.training.phase_b_v2_seed2026_operator_v3.protocol import LIMITS as ORIGINAL_LIMITS

ROOT=Path(__file__).absolute().parents[4]
raw_seed=os.environ.get('YUNTAPR_REPLICATION_SEED')
if raw_seed not in ('2027','2028'):raise PermissionError('EXACT_PREDEFINED_NEW_SEED_REQUIRED')
SEED=int(raw_seed)
OUT=ROOT/f'docs/phase_b_v2_formal_execution/seed{SEED}_v1'
LOCAL=OUT/'.local'
CAMPAIGN=f'YUNTAPR_PHASE_B_V2_SEED{SEED}_FRESH_V1'
BASELINE='3818118f069e910ca0073f03868f9ec1d9cfe483'
ORDER=(('B0_MATCHED_V2','E0'),('B1_V2','E0'),('B0_MATCHED_V2','E1'),
       ('B1_V2','E1'),('B0_MATCHED_V2','E2'),('B1_V2','E2'))
TRAIN_N,DEV_N,STEPS,EPOCHS=10455,10501,5228,9
TOTAL=MAX_NEW=6*STEPS*EPOCHS
OLD_RESERVED=ABANDONED=0
LAST_SHA=None
LIMITS=dict(ORIGINAL_LIMITS)
DB=ROOT/f'.git/phase_b_v2_seed{SEED}_fresh_v1.sqlite'

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def atomic_json(path,value):
    raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
    temp=path.with_name(path.name+'.part')
    with temp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
def run_id(model,arm):
    if (model,arm) not in ORDER:raise PermissionError('ONLY_SIX_REGISTERED_FRESH_RUNS')
    return f'{model}__{arm}__s{SEED}'
def epoch_order(ids,epoch):
    if len(ids)!=TRAIN_N or len(set(ids))!=TRAIN_N or type(epoch) is not int or not 1<=epoch<=EPOCHS:
        raise ValueError('FROZEN_TRAIN_COVERAGE_OR_EPOCH')
    import torch
    generator=torch.Generator().manual_seed(SEED+epoch-1)
    return tuple(ids[i] for i in torch.randperm(TRAIN_N,generator=generator).tolist())
def session_root(number=None):
    n=int(number if number is not None else os.environ['YUNTAPR_OPERATOR_SESSION'])
    if not 1<=n<=999:raise PermissionError('BOUNDED_OWNED_SESSION')
    return LOCAL/'sessions'/f'session_{n:04d}'
def owned_json(path,maximum=16*1024**2):
    if not path.is_absolute() or not path.is_relative_to(LOCAL) or path.suffix!='.json' or '..' in path.parts or '2025' in str(path):
        raise PermissionError('OWNED_METADATA_LEXICAL_SCOPE')
    from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
    with ReadHandle(str(path),payload=True) as h:
        if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or not 0<h.before['size']<=maximum:
            raise PermissionError('OWNED_METADATA_NATIVE_OBJECT_OR_SIZE')
        buf=bytearray(h.before['size']);n=0
        while n<len(buf):
            k=h.readinto(memoryview(buf)[n:])
            if not k:raise EOFError('OWNED_METADATA_TRUNCATED')
            n+=k
        if h.snapshot()!=h.before:raise ValueError('OWNED_METADATA_CONCURRENT_CHANGE')
    return json.loads(buf)
def validate_plan(plan):
    if (plan.get('seed')!=SEED or plan.get('campaign')!=CAMPAIGN or plan.get('kind')!='PREPARATION_NOT_EXECUTION_AUTHORIZATION'
        or plan.get('limits')!=LIMITS or plan.get('attempt_cap')!=TOTAL or plan.get('initial_checkpoint') is not None
        or plan.get('python_hash_seed')!=2026 or plan.get('epochs')!=EPOCHS or plan.get('updates_per_epoch')!=STEPS
        or plan.get('train_scenes')!=TRAIN_N or plan.get('development_scenes')!=DEV_N
        or plan.get('design')!='D1/Q1/N0/I3/B9/S0/V0' or plan.get('statistics')!='M-C_EXPLORATORY'
        or plan.get('training_batch_size')!=2 or plan.get('validation_batch_size')!=8
        or plan.get('bootstrap_seed')!=2026 or plan.get('warm_start') is not False
        or plan.get('initialization_seed')!=SEED or plan.get('order_seed_rule')!='seed+epoch-1'
        or plan.get('data_roles')!={'2023':'Train','2024':'Development'} or plan.get('forbidden_years')!=[2025]
        or plan.get('batch_predecessor')!=(None if SEED==2027 else 2027)
        or plan.get('execution_authorized') is not False):raise ValueError('FROZEN_NEW_SEED_CONFIGURATION')
    expected=[dict(run_id=run_id(m,a),model=m,arm=a,alpha=.5,gamma=0 if a=='E1' else 2,
                   lambda_q=2 if a=='E2' else 1,updates=47052,seed=SEED) for m,a in ORDER]
    if plan.get('runs')!=expected:raise ValueError('FIXED_SIX_RUN_ORDER_PARAMETERS_AND_BUDGET')
    return plan
def code_identity():
    files=subprocess.check_output(['git','ls-files','src/yuntapr','config/science_v2',
        'scripts/phase_b_v2_replication','tools/phase_b_v2_replication'],cwd=ROOT,text=True).splitlines()
    pins={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files if p.endswith(('.py','.json','.ps1'))}
    return dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),pins=pins,sha256=digest(pins))
def validate_preparation():
    plan=validate_plan(json.loads((OUT/'config.json').read_bytes()))
    release=json.loads((OUT/'prepared_release.json').read_bytes());actual=code_identity()
    if (release['source_sha256']!=actual['sha256'] or release['source_pins']!=actual['pins']
        or release['config_sha256']!=hashlib.sha256((OUT/'config.json').read_bytes()).hexdigest()
        or release['campaign']!=CAMPAIGN or release['kind']!='PREPARED_NOT_AUTHORIZED'):
        raise ValueError('PREPARED_SOURCE_AND_CONFIGURATION_IDENTITY')
    if subprocess.run(['git','merge-base','--is-ancestor',release['source_commit'],actual['commit']],cwd=ROOT,capture_output=True).returncode:
        raise ValueError('PREPARED_SOURCE_COMMIT_NOT_ANCESTOR')
    return release
def verify_release():
    # Deliberately BEFORE host/CUDA/data/ledger/Job work, even with forged JSON.
    from .authority import require_execution_authority
    require_execution_authority(SEED)
    return validate_preparation()

def require_predecessor():
    """Keep seed batches sequential; never start 2028 while 2027 is incomplete."""
    if SEED==2027:return
    from contextlib import closing
    import sqlite3
    peer=ROOT/'.git/phase_b_v2_seed2027_fresh_v1.sqlite'
    campaign,attempts='YUNTAPR_PHASE_B_V2_SEED2027_FRESH_V1',TOTAL
    # The approved v7 recovery adopts 83,648 retained updates and has its own
    # 198,664-attempt ledger. Cumulative 364,969 includes abandoned ancestry;
    # it must not be confused with 282,312 retained scientific updates.
    recovery=ROOT/'.git/phase_b_v2_seed2027_b1_epoch7_recovery_v7.sqlite'
    if recovery.exists():
        peer=recovery
        campaign,attempts='YUNTAPR_PHASE_B_V2_SEED2027_B1_EPOCH7_RECOVERY_V7',198664
    if not peer.exists():raise PermissionError('SEED2027_COMPLETE_BEFORE_SEED2028')
    with closing(sqlite3.connect(peer.as_uri()+'?mode=ro',uri=True,timeout=1)) as con:
        con.execute('PRAGMA query_only=ON')
        con.execute('BEGIN')
        if (con.execute('SELECT id,status FROM campaign').fetchone()!=(campaign,'COMPLETE')
            or con.execute("SELECT count(*) FROM attempts WHERE status='RETURNED_VERIFIED'").fetchone()[0]!=attempts
            or con.execute('SELECT count(*) FROM attempts').fetchone()[0]!=attempts
            or con.execute("SELECT count(*) FROM runs WHERE status='COMPLETE' AND epoch=9 AND updates=47052").fetchone()[0]!=6
            or con.execute("SELECT count(*) FROM epochs WHERE phase='LAST_COMMITTED'").fetchone()[0]!=54):
            raise PermissionError('SEED2027_COMPLETE_BEFORE_SEED2028')
