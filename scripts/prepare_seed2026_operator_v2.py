"""Record the explicit new LAST-bound grant; retain all failed old ledgers."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2026_operator_v2.protocol import (
    OUT,LOCAL,CAMPAIGN,LIMITS,OLD_RESERVED,MAX_NEW,TOTAL,LAST_SHA,atomic_json,code_identity)
from yuntapr.training.phase_b_v2_seed2026_operator_v2.recovery import verify_stopped_operator
PREVIOUS=ROOT/'docs/phase_b_v2_formal_execution/seed2026_operator_v1'


def main():
    if (OUT/'release.json').exists():raise PermissionError('FIXED_RELEASE_NO_REPLACEMENT')
    gate=json.loads((OUT/'prelaunch_directory_gate.json').read_bytes())
    if gate['status']!='PRELAUNCH_FROZEN_DIRECTORY_AND_METADATA_PASS' or gate['directory_handles']!=518:
        raise ValueError('FROZEN_METADATA_GATE_REQUIRED')
    db=ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v1.sqlite'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON');verify_stopped_operator(c)
    session=PREVIOUS/'.local/sessions/session_0001'
    term=json.loads((session/'termination.json').read_bytes())
    stop=json.loads((session/'emergency_20261013T160903_227450Z/receipt.json').read_bytes())
    heartbeat=json.loads((session/'heartbeat.json').read_bytes())
    if (not term['job_empty_and_handles_signaled'] or stop['status']!='TERMINATED' or not stop['job_empty']
        or stop['quota']['reserved']!=OLD_RESERVED or stop['quota']['returned_verified']!=OLD_RESERVED):
        raise ValueError('OLD_EMERGENCY_STOP_AND_QUOTA_NOT_VERIFIED')
    prior=json.loads((PREVIOUS/'ancestor.json').read_bytes());pins=dict(prior['pins'])
    for name,expected in pins.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('OLD_ANCESTOR_CHANGED')
    paths=[PREVIOUS/'release.json',PREVIOUS/'ancestor.json',db,ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v1.once']
    paths.extend(session/name for name in ('launch.once','launch.json','operator_launch.json',
        'supervisor_identity.json','worker_identity.json','bound_identity.json','preflight.json','heartbeat.json','termination.json',
        'emergency_20261013T160903_227450Z/request.json','emergency_20261013T160903_227450Z/receipt.json'))
    paths.extend(PREVIOUS/'.local/B1_V2__E1__s2026'/name for name in ('identity.json','recovery_receipt.json','train_epoch_08.json'))
    pins.update({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    failed_gate=json.loads((LOCAL/'prelaunch_failure_01.json').read_bytes())
    failed_metadata_debit=128*1024**2  # conservatively use the failed gate's fixed read cap
    prior.update(pins=pins,reserved=OLD_RESERVED,verified=OLD_RESERVED,last_sha256=LAST_SHA,
        source_epoch=7,source_update=36596,abandoned_updates=14367,
        elapsed_seconds=term['elapsed_seconds']+gate['elapsed_seconds']+failed_gate['elapsed_seconds'],
        content_bytes=heartbeat['content_bytes']+128*1024**2+gate['public_metadata_bytes']+failed_metadata_debit,
        conservative_unobserved_read_tail_debit=128*1024**2,measured_prior_heartbeat_bytes=heartbeat['content_bytes'],
        failed_prelaunch_metadata_budget_debit=failed_metadata_debit,
        latest_emergency_ancestor=dict(reserved=5228,verified=5228,phase='WAIT_VALIDATION',
            no_epoch8_last_adopted=True,job_empty=True,attempts_not_refunded=True))
    atomic_json(OUT/'ancestor.json',prior)
    original=json.loads((PREVIOUS/'release.json').read_bytes());actual=code_identity()
    for name,expected in original['source_pins'].items():
        if actual['pins'].get(name)!=expected:raise ValueError('EXISTING_EXECUTABLE_SOURCE_CHANGED: '+name)
    original.update(source_commit=actual['commit'],source_sha256=actual['sha256'],source_pins=actual['pins'],
        campaign=CAMPAIGN,ancestor_receipt_sha256=hashlib.sha256((OUT/'ancestor.json').read_bytes()).hexdigest(),
        authorization=dict(source='DIRECT_RESEARCHER_LAST_BOUND_REPLY_IN_THIS_CHAT_20261014',
            question='LAST7 SHA205839... recovery; spent192119 nonrefundable; additional5228; cap296679; fixed seed2026 remaining scope',
            answer='授权此恢复及 5,228 次额外额度',
            last_sha256=LAST_SHA,source_epoch=7,source_update=36596,combined_attempt_cap=TOTAL,new_attempt_cap=MAX_NEW,
            additional_replay_allowance=5228,seed=2026,other_seeds_authorized=False,test_2025_authorized=False,
            clean_pause_policy='FULL_EPOCH_TRAIN_VALIDATION_LAST_THEN_EXIT',
            manual_clean_pause_continuation='SAME_REMAINING_SCOPE_SAME_LIFETIME_QUOTA',
            emergency_restart='NEW_INDEPENDENT_LAST_BOUND_DECISION_REQUIRED'),
        original_resource_limits=LIMITS,remaining_time_seconds=LIMITS['max_seconds']-prior['elapsed_seconds'],
        remaining_content_bytes=LIMITS['max_read_bytes']-prior['content_bytes'],
        immediate_predecessor_commit='e18dae5e41be29224e7024e50e1523f6a4183034',
        prelaunch_root_reconnected=dict(initial_failure='FROZEN_H_DRIVE_NOT_MOUNTED',
            researcher_reply='已连接原 H: 盘，继续启动检查',optimizer_attempts_before_successful_gate=0))
    atomic_json(OUT/'release.json',original)
    atomic_json(LOCAL/'runtime.json',dict(python=r'F:\pytorch\Research\.venv-cuda\Scripts\python.exe'))
    from yuntapr.training.phase_b_v2_seed2026_operator_v2.protocol import verify_release
    verify_release()
    print(json.dumps(dict(status='NEW_LAST_BOUND_OPERATOR_RELEASE_FIXED_NOT_LAUNCHED',source_commit=actual['commit'],
        combined_cap=TOTAL,new_cap=MAX_NEW,old_nonrefundable=OLD_RESERVED)))

if __name__=='__main__':main()
