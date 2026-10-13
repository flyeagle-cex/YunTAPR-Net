"""One SHA-bound release for the direct epoch7 continuation instruction."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2026_operator_v1.protocol import (
    OUT,LOCAL,CAMPAIGN,LIMITS,OLD_RESERVED,MAX_NEW,TOTAL,LAST_SHA,atomic_json,code_identity)
PREVIOUS=ROOT/'docs/phase_b_v2_formal_execution/seed2026_resume_v2'


def main():
    if (OUT/'release.json').exists():raise PermissionError('FIXED_RELEASE_NO_REPLACEMENT')
    gate=json.loads((OUT/'prelaunch_directory_gate.json').read_bytes())
    if gate['status']!='PRELAUNCH_FROZEN_DIRECTORY_AND_METADATA_PASS' or gate['directory_handles']!=518:
        raise ValueError('DIRECTORY_METADATA_GATE_REQUIRED')
    prior=json.loads((PREVIOUS/'ancestor.json').read_bytes())
    term=json.loads((PREVIOUS/'.local/termination.json').read_bytes())
    stop=json.loads((PREVIOUS/'.local/researcher_stop_20261013T100815_756780Z/stop_receipt.json').read_bytes())
    heartbeat=json.loads((PREVIOUS/'.local/heartbeat.json').read_bytes())
    if not term['job_empty_and_handles_signaled'] or not stop['job_empty'] or not stop['member_handles_signaled'] or not stop['supervisor_exited']:
        raise ValueError('STOPPED_OLD_JOB_NOT_PROVEN')
    pins=dict(prior['pins'])
    for p,expected in pins.items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=expected:raise ValueError('PREVIOUS_ANCESTOR_CHANGED')
    names=('release.json','ancestor.json','execution_scope.json','.local/launch.once','.local/launch.json',
        '.local/termination.json','.local/heartbeat.json','.local/bound_identity.json','.local/worker_identity.json',
        '.local/researcher_stop_20261013T100815_756780Z/stop_receipt.json',
        '.local/researcher_stop_20261013T100815_756780Z/stop_request.json',
        '.local/B1_V2__E1__s2026/identity.json','.local/B1_V2__E1__s2026/progress.json',
        '.local/B1_V2__E1__s2026/checkpoints/LAST_epoch_07.ref.json',
        '.local/B1_V2__E1__s2026/checkpoints/LAST_epoch_07.registration.json')
    paths=[PREVIOUS/n for n in names]+[ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v2.sqlite',
        ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v2.once']
    pins.update({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    # Heartbeat byte measurement may lag the killed worker. Conservatively debit
    # 128MiB for the unobserved tail; this is budget accounting, not measured I/O.
    prior.update(pins=pins,reserved=OLD_RESERVED,verified=OLD_RESERVED,last_sha256=LAST_SHA,
        source_epoch=7,source_update=36596,abandoned_updates=9139,
        elapsed_seconds=term['elapsed_seconds']+gate['elapsed_seconds'],
        content_bytes=heartbeat['content_bytes']+128*1024**2+gate['public_metadata_bytes'],
        conservative_unobserved_read_tail_debit=128*1024**2,
        measured_prior_heartbeat_bytes=heartbeat['content_bytes'])
    atomic_json(OUT/'ancestor.json',prior)
    original=json.loads((PREVIOUS/'release.json').read_bytes());actual=code_identity()
    for p,expected in original['source_pins'].items():
        if actual['pins'].get(p)!=expected:raise ValueError('EXISTING_SOURCE_CHANGED: '+p)
    original.pop('republication_authorization',None)
    original.update(source_commit=actual['commit'],source_sha256=actual['sha256'],source_pins=actual['pins'],
        campaign=CAMPAIGN,publication_kind='EXPLICIT_LAST_BOUND_RECOVERY_WITH_NONREFUNDABLE_REPLAY',
        ancestor_receipt_sha256=hashlib.sha256((OUT/'ancestor.json').read_bytes()).hexdigest(),
        authorization=dict(source='DIRECT_RESEARCHER_CONTINUATION_INSTRUCTION_IN_THIS_CHAT',
            instruction='继续训练，然后把启动训练和暂停训练的命令给我，供我以后自己启动训练',
            preceding_explicit_proposal='LAST7 recovery; 186891 consumed; replay3911; combined cap291451',
            last_sha256=LAST_SHA,source_epoch=7,source_update=36596,combined_attempt_cap=TOTAL,
            new_attempt_cap=MAX_NEW,additional_replay_allowance=3911,seed=2026,
            other_seeds_authorized=False,test_2025_authorized=False,
            clean_pause_policy='FULL_EPOCH_TRAIN_VALIDATION_LAST_THEN_EXIT',
            human_policy_reply='完整 epoch 后安全暂停（推荐）',
            manual_clean_pause_continuation='SAME_REMAINING_SCOPE_SAME_LIFETIME_QUOTA',
            emergency_restart='NEW_INDEPENDENT_LAST_BOUND_DECISION_REQUIRED'),
        original_resource_limits=LIMITS,
        remaining_time_seconds=LIMITS['max_seconds']-prior['elapsed_seconds'],
        remaining_content_bytes=LIMITS['max_read_bytes']-prior['content_bytes'])
    atomic_json(OUT/'release.json',original)
    atomic_json(LOCAL/'runtime.json',dict(python=r'F:\pytorch\Research\.venv-cuda\Scripts\python.exe'))
    from yuntapr.training.phase_b_v2_seed2026_operator_v1.protocol import verify_release
    verify_release()
    print(json.dumps(dict(status='EPOCH7_OPERATOR_RELEASE_FIXED_NOT_LAUNCHED',source_commit=actual['commit'],
        combined_cap=TOTAL,new_cap=MAX_NEW,old_reserved=OLD_RESERVED)))

if __name__=='__main__':main()
