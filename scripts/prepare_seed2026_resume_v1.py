"""Freeze the exact approved recovery release; never launch or consume updates."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2026_resume_v1.protocol import (
    OUT, LOCAL, OLD_OUT, CAMPAIGN, LIMITS, LAST_SHA, digest, atomic_json, code_identity)


def main():
    OUT.mkdir(exist_ok=True); LOCAL.mkdir(exist_ok=True)
    if (OUT/'release.json').exists():
        raise PermissionError('RELEASE_ALREADY_FIXED_NO_REPUBLICATION')
    db = ROOT/'.git/phase_b_v2_seed2026_a1863dc_republish_v2.sqlite'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        counts = dict(c.execute('SELECT status,count(*) FROM attempts GROUP BY status').fetchall())
        if counts != {'RETURNED_VERIFIED':162068}:
            raise ValueError('ANCESTOR_NOT_EXACTLY_162068_VERIFIED')
        runs = c.execute('SELECT * FROM runs ORDER BY ordinal').fetchall()
        if ([r[2] for r in runs] != ['COMPLETE']*3+['RUNNING','PENDING','PENDING']
                or runs[3][3:] != (3,20912,LAST_SHA)
                or c.execute('SELECT status FROM campaign').fetchone()!=('FAILED_NO_RETRY',)):
            raise ValueError('ANCESTOR_FIXED_RUN_STATE')
    stop = json.loads((OLD_OUT/'.local/termination.json').read_bytes())
    heartbeat = json.loads((OLD_OUT/'.local/heartbeat.json').read_bytes())
    if not stop['job_empty_and_handles_signaled']:
        raise ValueError('OLD_JOB_NOT_EMPTY')
    names = ['release.json','old_zero_update_ancestor.json','.local/termination.json','.local/heartbeat.json',
        '.local/researcher_stop_20261012T154201_423813Z/stop_receipt.json',
        '.local/researcher_stop_20261012T154201_423813Z/stop_request.json',
        '.local/B1_V2__E1__s2026/identity.json','.local/B1_V2__E1__s2026/progress.json',
        '.local/B1_V2__E1__s2026/checkpoints/LAST_epoch_03.ref.json',
        '.local/B1_V2__E1__s2026/checkpoints/LAST_epoch_03.registration.json']
    for r in runs[:3]: names += [r[0]+'.json','.local/'+r[0]+'/identity.json']
    paths = [OLD_OUT/n for n in names]+[db,ROOT/'.git/phase_b_v2_seed2026_a1863dc_republish_v2.once']
    pins = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    row = dict(reserved=162068,verified=162068,last_sha256=LAST_SHA,source_epoch=3,source_update=15684,
        abandoned_updates=5228,elapsed_seconds=stop['elapsed_seconds'],content_bytes=heartbeat['content_bytes'],
        pins=pins,runs=runs,old_job_empty=True,old_attempts_not_refunded=True,
        historical_2025_path_attribute_access='NOT_INSTRUMENTED')
    atomic_json(OUT/'ancestor.json',row)
    old = json.loads((OLD_OUT/'release.json').read_bytes())
    actual = code_identity()
    for p,expected in old['source_pins'].items():
        if actual['pins'].get(p)!=expected: raise ValueError('PROTECTED_PREVIOUS_SOURCE_CHANGED: '+p)
    authorization = dict(source='DIRECT_RESEARCHER_REPLY_IN_THIS_CHAT_20261013',
        question='从指定 B1/E1 第3轮 LAST 恢复，重跑第4轮后完成本组及两组E2；不退还162068，额外5228，总上限287540。',
        answer='授权此恢复和额外额度（推荐）',last_sha256=LAST_SHA,
        source_epoch=3,source_update=15684,combined_attempt_cap=287540,new_attempt_cap=125472,
        additional_replay_allowance=5228,seed=2026,other_seeds_authorized=False,
        historical_recovery_ratification='NOT_GRANTED',test_2025_authorized=False,
        no_automatic_retry=True,science_design_unchanged='D1/Q1/N0/I3/B9/S0/V0; M-C_EXPLORATORY')
    release = dict(source_commit=actual['commit'],source_sha256=actual['sha256'],source_pins=actual['pins'],
        campaign=CAMPAIGN,publication_kind='EXPLICIT_LAST_BOUND_RECOVERY_WITH_NONREFUNDABLE_REPLAY',
        ancestor_receipt_sha256=hashlib.sha256((OUT/'ancestor.json').read_bytes()).hexdigest(),
        dependency_manifest_sha256=old['dependency_manifest_sha256'],authorization=authorization,
        original_resource_limits=LIMITS,ancestral_code_commit=old['source_commit'],
        remaining_time_seconds=LIMITS['max_seconds']-row['elapsed_seconds'],
        remaining_content_bytes=LIMITS['max_read_bytes']-row['content_bytes'])
    atomic_json(OUT/'release.json',release)
    atomic_json(OUT/'execution_scope.json',dict(campaign=CAMPAIGN,total_attempt_cap=287540,
        old_reserved=162068,new_attempt_cap=125472,epochs_per_run=9,updates_per_epoch=5228,
        resource_hard_limits=LIMITS,authorization=authorization))
    print(json.dumps(dict(status='RECOVERY_RELEASE_FIXED_NOT_LAUNCHED',source_commit=actual['commit'],
                         remaining_time_seconds=release['remaining_time_seconds'],new_attempt_cap=125472)))


if __name__=='__main__': main()
