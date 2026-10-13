"""Pin one new release; preserve both the stopped training and failed v1."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2026_resume_v2.protocol import OUT,LOCAL,CAMPAIGN,LIMITS,atomic_json,code_identity
from yuntapr.training.phase_b_v2_seed2026_resume_v2.recovery import verify_zero_predecessor
PREVIOUS=ROOT/'docs/phase_b_v2_formal_execution/seed2026_resume_v1'

def main():
    if (OUT/'release.json').exists():raise PermissionError('NO_REPLACE_FIXED_REPUBLICATION_RELEASE')
    gate=json.loads((OUT/'prelaunch_directory_gate.json').read_bytes())
    if gate['status']!='PRELAUNCH_FROZEN_DIRECTORY_AND_METADATA_PASS' or gate['directory_handles']!=518:
        raise ValueError('PRELAUNCH_DIRECTORY_GATE_REQUIRED')
    db=ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.sqlite'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON');verify_zero_predecessor(c)
    prior=json.loads((PREVIOUS/'ancestor.json').read_bytes())
    stop=json.loads((PREVIOUS/'.local/termination.json').read_bytes())
    fail=json.loads((PREVIOUS/'failure_receipt.json').read_bytes())
    if not stop['job_empty_and_handles_signaled'] or fail['new_optimizer_reserved'] or fail['new_optimizer_returned']:
        raise ValueError('FAILED_V1_NOT_STOPPED_ZERO_UPDATES')
    pins=dict(prior['pins'])
    for p,expected in pins.items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=expected:raise ValueError('ORIGINAL_ANCESTOR_CHANGED')
    names=('release.json','ancestor.json','failure_receipt.json','final_status.json','execution_status.json','watchdog_failure.json',
        'root_availability_failure.json','.local/launch.once','.local/launch.json','.local/bound_identity.json',
        '.local/worker_identity.json','.local/termination.json','.local/failure_private.txt','.local/access_and_events.jsonl')
    paths=[PREVIOUS/n for n in names]+[db,ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.once']
    pins.update({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    prior.update(pins=pins,elapsed_seconds=stop['elapsed_seconds']+gate['elapsed_seconds'],
        content_bytes=prior['content_bytes']+fail['public_metadata_content_bytes']+gate['public_metadata_bytes'],
        zero_update_predecessor=dict(campaign=stop['campaign'],reserved=0,returned=0,epochs_adopted=0,job_empty=True,
            failure='FROZEN_H_DRIVE_UNAVAILABLE',user_confirmed_reconnected_H=True))
    atomic_json(OUT/'ancestor.json',prior)
    original=json.loads((PREVIOUS/'release.json').read_bytes());actual=code_identity()
    for p,expected in original['source_pins'].items():
        if actual['pins'].get(p)!=expected:raise ValueError('PRIOR_FROZEN_SOURCE_CHANGED: '+p)
    original.update(source_commit=actual['commit'],source_sha256=actual['sha256'],source_pins=actual['pins'],campaign=CAMPAIGN,
        ancestor_receipt_sha256=hashlib.sha256((OUT/'ancestor.json').read_bytes()).hexdigest(),
        republication_authorization=dict(source='DIRECT_RESEARCHER_REPLY_IN_THIS_CHAT_20261013',
            question='H盘连接后，授权对此次零更新失败任务重新发布启动一次；累计287540，旧162068不退还。',
            answer='已连接 H:，授权重新发布启动',zero_update_predecessor=stop['campaign'],
            additional_attempt_allowance=0,one_launch_only=True),
        remaining_time_seconds=LIMITS['max_seconds']-prior['elapsed_seconds'],
        remaining_content_bytes=LIMITS['max_read_bytes']-prior['content_bytes'])
    atomic_json(OUT/'release.json',original)
    scope=json.loads((PREVIOUS/'execution_scope.json').read_bytes());scope['campaign']=CAMPAIGN
    scope['republication_authorization']=original['republication_authorization'];atomic_json(OUT/'execution_scope.json',scope)
    print(json.dumps(dict(status='ZERO_UPDATE_RECOVERY_REPUBLICATION_FIXED_NOT_LAUNCHED',source_commit=actual['commit'],
                         combined_cap=287540,new_cap=125472,old_reserved=162068)))

if __name__=='__main__':main()
