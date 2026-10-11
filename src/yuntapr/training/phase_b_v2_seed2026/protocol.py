"""Closed execution scope from the latest direct researcher instruction.

This module does not approve other seeds, interruption recovery or FinalFit.
Old candidate authorization flags and historical evidence remain untouched.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).absolute().parents[4]
OUT = ROOT/'docs/phase_b_v2_formal_execution/seed2026_v1'
LOCAL = OUT/'.local'
CAMPAIGN = 'RESEARCHER_PHASE_B_V2_SEED2026_SIX_RUNS_2131d576_V1'
BASELINE = '2131d576906e3dc6a4cbb91f2d03ea38331d3b42'
ORDER = (('B0_MATCHED_V2','E0'),('B1_V2','E0'),('B0_MATCHED_V2','E1'),
         ('B1_V2','E1'),('B0_MATCHED_V2','E2'),('B1_V2','E2'))
TRAIN_N, DEV_N, STEPS, EPOCHS = 10455, 10501, 5228, 9
TOTAL = 282312
GiB = 1024**3
# Fixed before launch. These are hard safety bounds, not measured duration estimates.
LIMITS = dict(max_seconds=7*24*3600, max_working_set_bytes=6*GiB,
              max_process_commit_bytes=12*GiB, max_job_commit_bytes=16*GiB,
              minimum_available_ram_bytes=6*GiB, minimum_available_commit_bytes=10*GiB,
              minimum_cuda_free_bytes=5*GiB, max_cuda_reserved_bytes=6*GiB,
              minimum_disk_free_bytes=12*GiB, max_read_bytes=32*1024*GiB,
              frame_cache_bytes=256*1024**2, target_cache_bytes=128*1024**2,
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
