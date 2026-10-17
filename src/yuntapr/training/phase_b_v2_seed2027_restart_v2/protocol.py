"""Fixed seed2027 execution release bound to the new direct human instruction."""
from __future__ import annotations
import hashlib,json,os,subprocess
from pathlib import Path
from yuntapr.training.phase_b_v2_seed2026_operator_v3.protocol import LIMITS as ORIGINAL_LIMITS
from .authority import execution_instruction,EXECUTION_SCOPE

ROOT=Path(__file__).absolute().parents[4]
if os.environ.get('YUNTAPR_REPLICATION_SEED') not in (None,'2027'):
    raise PermissionError('ONLY_PUBLISHED_SEED2027_SCOPE')
SEED=2027
OUT=ROOT/'docs/phase_b_v2_formal_execution/seed2027_restart_v2'
LOCAL=OUT/'.local'
CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_FRESH_RESTART_V2'
OLD_CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_FRESH_V1'
BASELINE='125e42b66477ba0ceb9f3905c0d0464cdc202bb9'
ORDER=(('B0_MATCHED_V2','E0'),('B1_V2','E0'),('B0_MATCHED_V2','E1'),
       ('B1_V2','E1'),('B0_MATCHED_V2','E2'),('B1_V2','E2'))
TRAIN_N,DEV_N,STEPS,EPOCHS=10455,10501,5228,9
from .accounting import FRESH_CAP,COMBINED_CAP,PRIOR_RESERVED,PRIOR_VERIFIED
MAX_NEW=FRESH_CAP
TOTAL=COMBINED_CAP
OLD_RESERVED=ABANDONED=PRIOR_RESERVED
OLD_VERIFIED=PRIOR_VERIFIED
LAST_SHA=None
LIMITS=dict(ORIGINAL_LIMITS)
# Explicit one-time fresh restart: cumulative prior 1127 + bounded new 282312.
DB=ROOT/'.git/phase_b_v2_seed2027_fresh_restart_v2.sqlite'

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def atomic_json(path,value):
    raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
    temp=path.with_name(path.name+'.part')
    with temp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
def run_id(model,arm):
    if (model,arm) not in ORDER:raise PermissionError('ONLY_SIX_REGISTERED_FRESH_RUNS')
    return f'{model}__{arm}__s2027'
def epoch_order(ids,epoch):
    if len(ids)!=TRAIN_N or len(set(ids))!=TRAIN_N or type(epoch) is not int or not 1<=epoch<=9:
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
def code_identity():
    roots=['src/yuntapr','config/science_v2','scripts/phase_b_v2_replication','tools/phase_b_v2_replication',
           'scripts/phase_b_v2_seed2027','tools/phase_b_v2_seed2027_release',
           'scripts/phase_b_v2_seed2027_restart_v2','tools/phase_b_v2_seed2027_restart','tools/phase_b_v2_seed2027_restart_v2',
           'scripts/phase_b_v2_seed2027_restart_v1']
    files=subprocess.check_output(['git','ls-files',*roots],cwd=ROOT,text=True).splitlines()
    pins={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files if p.endswith(('.py','.json','.ps1'))}
    return dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),pins=pins,sha256=digest(pins))
def validate_plan(plan):
    if (plan.get('seed')!=SEED or plan.get('campaign')!=OLD_CAMPAIGN or plan.get('kind')!='PREPARATION_NOT_EXECUTION_AUTHORIZATION'
        or plan.get('limits')!=LIMITS or plan.get('attempt_cap')!=MAX_NEW or plan.get('initial_checkpoint') is not None
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
def validate_record(release,actual,config_raw):
    if (release.get('schema')!='SEED2027_HUMAN_AUTHORIZED_FRESH_RESTART_v2'
        or release.get('campaign')!=CAMPAIGN or release.get('seed')!=2027
        or release.get('human_instruction')!=execution_instruction()
        or release.get('human_instruction_sha256')!=digest(execution_instruction())
        or release.get('execution_scope')!=EXECUTION_SCOPE
        or release.get('launch_authorized') is not True or release.get('planned_attempt_cap')!=TOTAL
        or release.get('new_attempt_cap')!=MAX_NEW or release.get('prior_reserved')!=OLD_RESERVED
        or release.get('prior_returned_verified')!=OLD_VERIFIED
        or release.get('original_execution_commit')!=BASELINE
        or type(release.get('failed_ancestor_sha256')) is not str
        or len(release['failed_ancestor_sha256'])!=64
        or any(c not in '0123456789abcdef' for c in release['failed_ancestor_sha256'])
        or release.get('held_publication_commit')!='ed45c6c817b9c5ab47b1e3f30ce30e99ddb9e38c'
        or release.get('dependency_manifest_sha256')!='2d02c5757f9da5fc1fef8b82168ffd689b96c07056d1cc13acf354a3fd88e780'
        or release.get('original_resource_limits')!=LIMITS
        or release.get('source_sha256')!=actual['sha256'] or release.get('source_pins')!=actual['pins']
        or release.get('config_sha256')!=hashlib.sha256(config_raw).hexdigest()):
        raise ValueError('ACTIVATED_RELEASE_IDENTITY_OR_HUMAN_SCOPE')
    return release
def verify_published_release():
    config_raw=(OUT/'config.json').read_bytes()
    # The frozen design/config has not become an authority by being copied.
    validate_plan(json.loads(config_raw))
    raw=(OUT/'release.json').read_bytes()
    if not 0<len(raw)<=1024**2:raise ValueError('PUBLISHED_RELEASE_METADATA_SIZE')
    release=validate_record(json.loads(raw),code_identity(),config_raw)
    if subprocess.run(['git','merge-base','--is-ancestor',release['source_commit'],code_identity()['commit']],cwd=ROOT,capture_output=True).returncode:
        raise ValueError('PUBLISHED_SOURCE_COMMIT_NOT_ANCESTOR')
    remote=subprocess.check_output(['git','remote','get-url','origin'],cwd=ROOT,text=True).strip()
    if remote not in ('https://github.com/flyeagle-cex/YunTAPR-Net.git','https://github.com/flyeagle-cex/YunTAPR-Net'):
        raise ValueError('PUBLISHED_REPOSITORY_IDENTITY')
    return release
def verify_release():
    from .authority import require_execution_authority
    require_execution_authority(SEED) # BEFORE host/CUDA/ledger/Job/data access
    release=verify_published_release()
    from .ancestor import Guard
    with Guard(release['failed_ancestor_sha256']) as guard:
        if release.get('prior_fresh_b0_sha256')!=guard.receipt['prior_fresh_b0_sha256']:
            raise ValueError('FRESH_INITIAL_ANCESTRY_IDENTITY')
    return release
def require_predecessor():
    from .ancestor import Guard
    release=verify_published_release()
    with Guard(release['failed_ancestor_sha256']) as guard:return dict(guard.receipt)
