"""Isolated writable campaign; unchanged legacy code/data are read from LIVE_ROOT."""
from __future__ import annotations
import hashlib,json,os,subprocess
from pathlib import Path
from yuntapr.training.phase_b_v2_seed2026_operator_v3.protocol import LIMITS as ORIGINAL_LIMITS
from .authority import execution_instruction,EXECUTION_SCOPE
from .accounting import FRESH_CAP,COMBINED_CAP,PRIOR_RESERVED,PRIOR_VERIFIED,ABANDONED

ROOT=Path(__file__).absolute().parents[4]
LIVE_ROOT=ROOT.parent/'YunTAPR-Net-push-chunks'
PREVIOUS_ROOT=ROOT.parent/'YunTAPR-Net-completed-review-20261021'
BOOTSTRAP_PATH=os.pathsep.join([str(ROOT/'tools/seed2027_b1_e1_epoch6_recovery/bootstrap'),str(LIVE_ROOT/'src')])
SEED=2027
if os.environ.get('YUNTAPR_REPLICATION_SEED') not in (None,'2027'):raise PermissionError('ONLY_SEED2027')
OUT=ROOT/'docs/formal_recovery/seed2027_b1_e1_epoch6_v1'
LOCAL=OUT/'.local'
CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_B1_E1_EPOCH6_RECOVERY_V1'
OLD_CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_FRESH_V1'
LIVE_BASE='96a2a61eeb9b0c4a8513133133c75bfdf4b58726'
ORDER=(('B0_MATCHED_V2','E0'),('B1_V2','E0'),('B0_MATCHED_V2','E1'),('B1_V2','E1'),('B0_MATCHED_V2','E2'),('B1_V2','E2'))
TRAIN_N,DEV_N,STEPS,EPOCHS=10455,10501,5228,9
MAX_NEW,TOTAL,OLD_RESERVED,OLD_VERIFIED=FRESH_CAP,COMBINED_CAP,PRIOR_RESERVED,PRIOR_VERIFIED
LAST_SHA='245619dbc66e60c677c2288660286a88748c9bf3121200610d3e7b13ebe4bc2b'
SOURCE_EPOCH,SOURCE_UPDATE=6,31368
SOURCE_RUN='B1_V2__E1__s2027'
LIMITS=dict(ORIGINAL_LIMITS)
DB=ROOT/'.git/phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.sqlite'
LEGACY_RELEASE=LIVE_ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v7/release.json'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def atomic_json(path,value):
    if not path.is_absolute() or not path.is_relative_to(OUT):raise PermissionError('ISOLATED_OUTPUT_ONLY')
    if path.name in ('heartbeat.json','progress.json','execution_status.json'):
        from yuntapr.experimental.phase_b_v2_status_snapshot_io.reader import atomic_status_json
        return atomic_status_json(path,value,OUT)
    raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
    temp=path.with_name(path.name+'.part')
    with temp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def run_id(model,arm):
    if (model,arm) not in ORDER:raise PermissionError('ONLY_SIX_REGISTERED_RUNS')
    return f'{model}__{arm}__s2027'


def epoch_order(ids,epoch):
    if len(ids)!=TRAIN_N or len(set(ids))!=TRAIN_N or type(epoch) is not int or not 1<=epoch<=9:raise ValueError('FROZEN_TRAIN_COVERAGE_OR_EPOCH')
    import torch
    generator=torch.Generator().manual_seed(SEED+epoch-1)
    return tuple(ids[i] for i in torch.randperm(TRAIN_N,generator=generator).tolist())


def session_root(number=None):
    n=int(number if number is not None else os.environ['YUNTAPR_OPERATOR_SESSION'])
    if not 1<=n<=999:raise PermissionError('BOUNDED_OWNED_SESSION')
    return LOCAL/'sessions'/f'session_{n:04d}'


def owned_json(path,maximum=16*1024**2):
    if not path.is_absolute() or not path.is_relative_to(LOCAL) or path.suffix!='.json' or '..' in path.parts or '2025' in str(path):raise PermissionError('OWNED_METADATA_LEXICAL_SCOPE')
    from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
    with ReadHandle(str(path),payload=True) as h:
        if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or not 0<h.before['size']<=maximum:raise PermissionError('OWNED_METADATA_OBJECT')
        buf=bytearray(h.before['size']);n=0
        while n<len(buf):
            count=h.readinto(memoryview(buf)[n:])
            if not count:raise EOFError('OWNED_METADATA_TRUNCATED')
            n+=count
        if h.snapshot()!=h.before:raise ValueError('OWNED_METADATA_CHANGED')
    return json.loads(buf)


def code_identity():
    from yuntapr.training.phase_b_v2_seed2027_b0_e1_recovery_v1.protocol import verify_published_release as verify_previous
    previous=verify_previous()
    pins={}
    for name,value in previous['source_pins'].items():
        bucket='previous' if name.startswith(('recovery_overlay/','tools/')) else 'live'
        pins[bucket+'/'+name]=value
    for directory in (ROOT/'recovery_overlay',ROOT/'tools/seed2027_b1_e1_epoch6_recovery'):
        for path in sorted(directory.rglob('*.py')):pins[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    prior_raw=(PREVIOUS_ROOT/'docs/formal_recovery/seed2027_b0_e1_epoch1_v1/release.json').read_bytes()
    return dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),pins=pins,sha256=digest(pins),
        legacy_release_sha256=hashlib.sha256(LEGACY_RELEASE.read_bytes()).hexdigest(),previous_release_sha256=hashlib.sha256(prior_raw).hexdigest())


def validate_plan(plan):
    # The original immutable data/config remains a preparation, not authority.
    from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v7.protocol import validate_plan as validate_original_plan
    return validate_original_plan(plan)


def verify_published_release():
    raw=(OUT/'release.json').read_bytes();release=json.loads(raw);actual=code_identity()
    config=(OUT/'config.json').read_bytes();validate_plan(json.loads(config))
    expected=dict(schema='ISOLATED_SEED2027_B1_E1_EPOCH6_RECOVERY_v1',campaign=CAMPAIGN,
        human_instruction=execution_instruction(),human_instruction_sha256=digest(execution_instruction()),
        execution_scope=EXECUTION_SCOPE,launch_authorized=True,planned_attempt_cap=TOTAL,new_attempt_cap=MAX_NEW,
        prior_reserved=OLD_RESERVED,prior_returned_verified=OLD_VERIFIED,recovery_last_sha256=LAST_SHA,
        recovery_epoch=SOURCE_EPOCH,recovery_update=SOURCE_UPDATE,additional_replay_attempts=5228,
        original_resource_limits=LIMITS,source_sha256=actual['sha256'],source_pins=actual['pins'],
        config_sha256=hashlib.sha256(config).hexdigest(),legacy_release_sha256=actual['legacy_release_sha256'],
        previous_release_sha256=actual['previous_release_sha256'],
        gui_runtime_sha256=digest(owned_json(LOCAL/'gui_runtime.json')),
        dependency_manifest_sha256='2d02c5757f9da5fc1fef8b82168ffd689b96c07056d1cc13acf354a3fd88e780')
    if any(release.get(k)!=v for k,v in expected.items()):raise ValueError('RELEASE_IDENTITY_OR_HUMAN_SCOPE')
    if not isinstance(release.get('failed_ancestor_sha256'),str) or len(release['failed_ancestor_sha256'])!=64:raise ValueError('ANCESTOR_RECEIPT_SHA')
    if subprocess.run(['git','merge-base','--is-ancestor',release['source_commit'],actual['commit']],cwd=ROOT,capture_output=True).returncode:raise ValueError('RELEASE_SOURCE_COMMIT_NOT_ANCESTOR')
    return release


def verify_release():
    from .authority import require_execution_authority
    require_execution_authority(SEED)
    release=verify_published_release()
    from .ancestor import Guard
    with Guard(release['failed_ancestor_sha256']) as guard:
        if release['prior_fresh_b0_sha256']!=guard.receipt['prior_fresh_b0_sha256']:raise ValueError('PAIRED_FRESH_INITIAL_IDENTITY')
    return release


def require_predecessor():
    release=verify_published_release()
    from .ancestor import Guard
    with Guard(release['failed_ancestor_sha256']) as guard:return dict(guard.receipt)
