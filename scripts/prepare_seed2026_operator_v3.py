"""Record the new crash-recovery LAST-bound grant; retain all failed old ledgers."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2026_operator_v3.protocol import (
    OUT,LOCAL,CAMPAIGN,LIMITS,OLD_RESERVED,MAX_NEW,TOTAL,LAST_SHA,atomic_json,code_identity)
from yuntapr.training.phase_b_v2_seed2026_operator_v3.recovery import verify_crashed_operator
PREVIOUS=ROOT/'docs/phase_b_v2_formal_execution/seed2026_operator_v2'


def main():
    if (OUT/'release.json').exists():raise PermissionError('FIXED_RELEASE_NO_REPLACEMENT')
    gate=json.loads((OUT/'prelaunch_directory_gate.json').read_bytes())
    if gate['status']!='PRELAUNCH_FROZEN_DIRECTORY_AND_METADATA_PASS' or gate['directory_handles']!=518:
        raise ValueError('FROZEN_METADATA_GATE_REQUIRED')
    db=ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v2.sqlite'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON');verify_crashed_operator(c)
    session=PREVIOUS/'.local/sessions/session_0001'
    heartbeat=json.loads((session/'heartbeat.json').read_bytes())
    if heartbeat['elapsed_seconds']!=137201.68699999998 or heartbeat['content_bytes']!=9606971512822:
        raise ValueError('CRASHED_HEARTBEAT_CHANGED')
    if (session/'termination.json').exists():raise ValueError('CRASHED_SESSION_MUST_NOT_HAVE_TERMINATION_RECEIPT')
    age=time.time()-(session/'heartbeat.json').stat().st_mtime
    if age<3600:raise ValueError('HEARTBEAT_NOT_CONFIRMED_STALE')
    prior=json.loads((PREVIOUS/'ancestor.json').read_bytes());pins=dict(prior['pins'])
    for name,expected in pins.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('OLD_ANCESTOR_CHANGED')
    paths=[PREVIOUS/'release.json',PREVIOUS/'ancestor.json',db,ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v2.once']
    paths.extend(session/name for name in ('launch.once','launch.json','operator_launch.json',
        'supervisor_identity.json','worker_identity.json','bound_identity.json','preflight.json','heartbeat.json','access_and_events.jsonl'))
    paths.append(PREVIOUS/'execution_status.json')
    pins.update({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    prior.update(pins=pins,reserved=OLD_RESERVED,verified=OLD_RESERVED,last_sha256=LAST_SHA,
        source_epoch=7,source_update=36596,abandoned_updates=16162,
        elapsed_seconds=heartbeat['elapsed_seconds']+gate['elapsed_seconds'],
        content_bytes=heartbeat['content_bytes']+128*1024**2+gate['public_metadata_bytes'],
        conservative_unobserved_read_tail_debit=128*1024**2,measured_prior_heartbeat_bytes=heartbeat['content_bytes'],
        latest_crash_ancestor=dict(reserved=1795,verified=1795,phase='TRAINING',
            no_epoch8_last_adopted=True,attempts_not_refunded=True,no_termination_receipt=True,
            gpu_driver_error='nvlddmkm_153_LiveKernelEvent_at_2026-10-14T00:26:59Z'))
    atomic_json(OUT/'ancestor.json',prior)
    original=json.loads((PREVIOUS/'release.json').read_bytes());actual=code_identity()
    for name,expected in original['source_pins'].items():
        if actual['pins'].get(name)!=expected:raise ValueError('EXISTING_EXECUTABLE_SOURCE_CHANGED: '+name)
    original.update(source_commit=actual['commit'],source_sha256=actual['sha256'],source_pins=actual['pins'],
        campaign=CAMPAIGN,ancestor_receipt_sha256=hashlib.sha256((OUT/'ancestor.json').read_bytes()).hexdigest(),
        authorization=dict(source='DIRECT_RESEARCHER_LAST_BOUND_REPLY_IN_THIS_CHAT_20261014_V3',
            question='LAST7 SHA205839... recovery; spent193914 nonrefundable; replay5228; cap298474; fixed seed2026 remaining scope',
            answer='从 B1/E1 第 7 轮 LAST 205839…（update 36596）恢复并重放第 8 轮；本次已记账未落盘的 1,795 次更新不退款；累计上限 296,679 → 298,474；种子 2026、固定顺序与全部资源上限不变。',
            last_sha256=LAST_SHA,source_epoch=7,source_update=36596,combined_attempt_cap=TOTAL,new_attempt_cap=MAX_NEW,
            additional_replay_allowance=5228,seed=2026,other_seeds_authorized=False,test_2025_authorized=False,
            clean_pause_policy='FULL_EPOCH_TRAIN_VALIDATION_LAST_THEN_EXIT',
            manual_clean_pause_continuation='SAME_REMAINING_SCOPE_SAME_LIFETIME_QUOTA',
            emergency_restart='NEW_INDEPENDENT_LAST_BOUND_DECISION_REQUIRED'),
        original_resource_limits=LIMITS,remaining_time_seconds=LIMITS['max_seconds']-prior['elapsed_seconds'],
        remaining_content_bytes=LIMITS['max_read_bytes']-prior['content_bytes'],
        immediate_predecessor_commit='c212a4e1701fd69cbf41a07a22929e15fc579faa',
        prelaunch_root_reconnected=dict(initial_failure=None,researcher_reply='H: 盘持续挂载，无需重连',optimizer_attempts_before_successful_gate=0))
    atomic_json(OUT/'release.json',original)
    atomic_json(LOCAL/'runtime.json',dict(python=r'F:\pytorch\Research\.venv-cuda\Scripts\python.exe'))
    from yuntapr.training.phase_b_v2_seed2026_operator_v3.protocol import verify_release
    verify_release()
    print(json.dumps(dict(status='NEW_LAST_BOUND_OPERATOR_RELEASE_FIXED_NOT_LAUNCHED',source_commit=actual['commit'],
        combined_cap=TOTAL,new_cap=MAX_NEW,old_nonrefundable=OLD_RESERVED)))

if __name__=='__main__':main()
