"""Closed execution scope from the latest direct researcher instruction.

Only the bound epoch7 recovery and complete-LAST operator continuation apply.
Old candidate authorization flags and historical evidence remain untouched.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).absolute().parents[4]
OUT = ROOT/'docs/phase_b_v2_formal_execution/seed2026_operator_v2'
LOCAL = OUT/'.local'
CAMPAIGN = 'RESEARCHER_PHASE_B_V2_SEED2026_EPOCH7_OPERATOR_20261014_V2'
BASELINE = 'a1863dc8bc3ce90f96bd8d40228a6543380331f1'
ORDER = (('B0_MATCHED_V2','E0'),('B1_V2','E0'),('B0_MATCHED_V2','E1'),
         ('B1_V2','E1'),('B0_MATCHED_V2','E2'),('B1_V2','E2'))
TRAIN_N, DEV_N, STEPS, EPOCHS = 10455, 10501, 5228, 9
TOTAL = 296679
OLD_RESERVED = 192119
MAX_NEW = 104560
ABANDONED = 14367
LAST_SHA = '2058390159ecc9195acf9812078ac56f7e63756bf3f176228e3c1ed6c1cf0ec2'
OLD_OUT = ROOT/'docs/phase_b_v2_formal_execution/seed2026_v2'
GiB = 1024**3
# Fixed before launch. These are hard safety bounds, not measured duration estimates.
LIMITS = dict(max_seconds=7*24*3600, max_working_set_bytes=6*GiB,
              max_process_commit_bytes=12*GiB, max_job_commit_bytes=16*GiB,
              minimum_available_ram_bytes=6*GiB, minimum_available_commit_bytes=10*GiB,
              minimum_cuda_free_bytes=5*GiB, max_cuda_reserved_bytes=6*GiB,
              minimum_disk_free_bytes=12*GiB, max_read_bytes=32*1024*GiB,
              frame_cache_bytes=256*1024**2, target_cache_bytes=128*1024**2,
              directory_handle_limit=518,
              max_checkpoint_bytes=128*1024**2, max_score_database_bytes=256*1024**2)

def digest(value) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def atomic_json(path: Path, value) -> None:
    raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
    temp=path.with_name(path.name+'.part')
    with temp.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp,path)

def code_identity() -> dict:
    """All tracked Python and frozen science config; never enumerate raw data."""
    files=subprocess.check_output(['git','ls-files','src/yuntapr','config/science_v2'],cwd=ROOT,text=True).splitlines()
    pins={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files if p.endswith(('.py','.json'))}
    return dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                pins=pins,sha256=digest(pins))

def verify_release() -> dict:
    release=json.loads((OUT/'release.json').read_bytes())
    actual=code_identity()
    # release records the source commit; the later launch receipt commit may differ
    # only in docs. All executable/frozen source bytes must remain pinned.
    if actual['sha256']!=release['source_sha256'] or actual['pins']!=release['source_pins']:
        raise ValueError('FORMAL_SOURCE_BYTES_CHANGED')
    if subprocess.check_output(['git','remote','get-url','origin'],cwd=ROOT,text=True).strip() not in (
        'https://github.com/flyeagle-cex/YunTAPR-Net.git','https://github.com/flyeagle-cex/YunTAPR-Net'):
        raise ValueError('REPOSITORY_IDENTITY_MISMATCH')
    if subprocess.run(['git','merge-base','--is-ancestor',release['source_commit'],actual['commit']],cwd=ROOT).returncode:
        raise ValueError('RELEASE_COMMIT_NOT_ANCESTOR')
    if release.get('publication_kind')!='EXPLICIT_LAST_BOUND_RECOVERY_WITH_NONREFUNDABLE_REPLAY':
        raise ValueError('EXPLICIT_RECOVERY_RELEASE_REQUIRED')
    a=release.get('authorization',{})
    if (release.get('campaign')!=CAMPAIGN or a.get('last_sha256')!=LAST_SHA
            or a.get('source_epoch')!=7 or a.get('source_update')!=36596
            or a.get('combined_attempt_cap')!=TOTAL or a.get('new_attempt_cap')!=MAX_NEW
            or a.get('additional_replay_allowance')!=5228 or a.get('seed')!=2026
            or a.get('other_seeds_authorized') is not False or a.get('test_2025_authorized') is not False
            or release.get('original_resource_limits')!=LIMITS):
        raise ValueError('EXACT_HUMAN_RECOVERY_SCOPE_AND_FIXED_RESOURCES')
    from .recovery import Guard
    guard=Guard(release['ancestor_receipt_sha256']);guard.close()
    return release

def run_id(model: str, arm: str) -> str:
    if (model,arm) not in ORDER: raise PermissionError('ONLY_SIX_SEED2026_RUNS')
    return f'{model}__{arm}__s2026'

def epoch_order(ids: tuple[str,...], epoch: int) -> tuple[str,...]:
    import torch
    if len(ids)!=TRAIN_N or len(set(ids))!=TRAIN_N or type(epoch) is not int or not 1<=epoch<=9:
        raise ValueError('FROZEN_TRAIN_COVERAGE_OR_EPOCH')
    generator=torch.Generator().manual_seed(2026+epoch-1)
    return tuple(ids[i] for i in torch.randperm(TRAIN_N,generator=generator).tolist())

DB = ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v2.sqlite'

def session_root(number=None):
    n=int(number if number is not None else os.environ['YUNTAPR_OPERATOR_SESSION'])
    if not 1<=n<=999:raise PermissionError('BOUNDED_OWNED_SESSION')
    return LOCAL/'sessions'/f'session_{n:04d}'

def owned_json(path,maximum=16*1024**2):
    """Fixed own metadata only; lexical/native rejection precedes content reads."""
    if not path.is_absolute() or not path.is_relative_to(LOCAL) or path.suffix!='.json' or '..' in path.parts or '2025' in str(path):
        raise PermissionError('OWNED_METADATA_LEXICAL_SCOPE')
    from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
    with ReadHandle(str(path),payload=True) as h:
        if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or not 0<h.before['size']<=maximum:
            raise PermissionError('OWNED_METADATA_NATIVE_OBJECT_OR_SIZE')
        buf=bytearray(h.before['size']);n=0
        while n<len(buf):
            count=h.readinto(memoryview(buf)[n:])
            if not count:raise EOFError('OWNED_METADATA_TRUNCATED')
            n+=count
        if h.snapshot()!=h.before:raise ValueError('OWNED_METADATA_CONCURRENT_CHANGE')
    return json.loads(buf)
