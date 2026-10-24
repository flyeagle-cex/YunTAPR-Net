"""Manual clean-pause continuation; one attempt, no failure restart or budget change."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import bootstrap as b
from resume_gate import ResumeLedger

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'evidence'
EXPECTED_RELEASE = '184d6170104e5398681047f28d27f4336344fadf5a657ffac496f5b7f5cff5a5'
EXPECTED_LAST = '48104b14a6888fe652a99b3641edc25957785e4161cddcd6a36f026502316d1f'
EXPECTED_RUN = 'B0_MATCHED_V2__E2__s2027'
SOURCES = ('bootstrap.py','resume_gate.py','test_resume_gate.py','operate.py')


def now(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def record(name, value):
    OUT.mkdir(exist_ok=True)
    with (OUT/name).open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2)
        handle.write('\n')


def verify_operator():
    sealed=json.loads((OUT/'operator_release.json').read_text(encoding='utf-8'))
    if sealed['source_pins']!={name:sha(ROOT/name) for name in SOURCES}:
        raise PermissionError('ISOLATED_OPERATOR_SOURCE_CHANGED')
    result=subprocess.run(['git','merge-base','--is-ancestor',sealed['source_commit'],'HEAD'],cwd=ROOT,capture_output=True)
    if result.returncode:raise PermissionError('ISOLATED_OPERATOR_COMMIT_NOT_ANCESTOR')
    return sealed


def ready():
    operator=verify_operator()
    if sha(b.protocol.OUT/'release.json')!=EXPECTED_RELEASE:
        raise PermissionError('EXACT_UNCHANGED_SCIENTIFIC_RELEASE_REQUIRED')
    release=b.protocol.verify_release()
    state=b.control.status()
    if state.get('effective_state')!='PAUSED' or state['session']!={'number':1,'status':'PAUSED'}:
        raise PermissionError('ONLY_EXACT_CLEAN_SESSION1_PAUSE_CONTINUATION')
    if (state['reserved'],state['new_reserved'],state['new_returned_verified'],state['hard_cap'])!=(302233,36596,36596,375425):
        raise PermissionError('EXACT_PAUSED_QUOTA_NO_REPLAY_OR_NEW_BUDGET')
    row=next(r for r in state['runs'] if r['id']==EXPECTED_RUN)
    if row!={'id':EXPECTED_RUN,'status':'RUNNING','complete_epoch':4,'logical_updates':20912,'last_sha':EXPECTED_LAST}:
        raise PermissionError('EXACT_COMMITTED_B0_E2_EPOCH4_LAST_REQUIRED')
    with b.quota.ro() as con:
        if con.execute("SELECT count(*) FROM epochs WHERE phase!='LAST_COMMITTED'").fetchone()!=(0,):
            raise PermissionError('UNSEALED_EPOCH_NOT_A_CLEAN_PAUSE')
        if con.execute('SELECT count(*) FROM epochs').fetchone()!=(40,):
            raise PermissionError('EXPECTED_FORTY_COMPLETE_EPOCH_RECEIPTS')
        if con.execute("SELECT count(*) FROM attempts WHERE status!='RETURNED_VERIFIED'").fetchone()!=(0,):
            raise PermissionError('UNCERTAIN_NEW_ATTEMPT_FORBIDS_CONTINUATION')
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.admission import launch_headroom
    resources=launch_headroom()
    if not resources['ready']:raise MemoryError('UNCHANGED_RESOURCE_HEADROOM_REQUIRED_NO_SESSION_CLAIMED')
    if 'torch' in sys.modules:raise RuntimeError('OPERATOR_IMPORTED_TORCH')
    return {'observed_utc':now(),'operator':operator,'original_release_sha256':EXPECTED_RELEASE,
            'state':state,'resources':resources,'original_ledger_sha256_before_resume':sha(b.protocol.DB),
            'exact_last_sha256':EXPECTED_LAST,'next_logical_update':20913,'additional_budget':0,
            'replayed_updates':0,'automatic_retries':0,'scientific_worker_modified':False,
            'user_instruction':'继续进程','seed2028_authorized':False,'finalfit_authorized':False,'test2025_authorized':False}


def start():
    check=ready()
    record('prelaunch.json',check)
    # This override exists only in this short-lived operator process. The OS task
    # starts the original, source-pinned GUI owner/supervisor/worker from disk.
    original=b.control.Ledger
    b.control.Ledger=ResumeLedger
    try: result=b.control.start()
    finally: b.control.Ledger=original
    record('operator_launch.json',result)
    return result


def verify_startup():
    verify_operator()
    state=b.control.status()
    if state.get('effective_state')!='RUNNING' or state['session']!={'number':2,'status':'ACTIVE'}:
        raise PermissionError('SESSION2_NOT_VERIFIED_RUNNING')
    if state['new_returned_verified']<=36596 or state['hard_cap']!=375425:
        raise PermissionError('NEW_OPTIMIZER_RETURN_NOT_YET_VERIFIED')
    events=b.protocol.session_root(2)/'access_and_events.jsonl'
    with events.open('rb') as handle:
        handle.seek(0,2);size=handle.tell();handle.seek(max(0,size-2*1024**2))
        lines=handle.read(2*1024**2).splitlines()
    selected=[]
    for line in lines:
        try: row=json.loads(line)
        except (ValueError,UnicodeError):continue
        if row.get('event') in ('VERIFIED_SAFE_PAUSE_LAST_RESUMED','STEP_RETURNED'):
            selected.append(row)
    steps=[r for r in selected if r['event']=='STEP_RETURNED']
    if not steps:raise PermissionError('NO_DURABLE_RESUMED_OPTIMIZER_EVENT_IN_BOUNDED_TAIL')
    result={'observed_utc':now(),'status':'ACTUAL_CLEAN_PAUSE_CONTINUATION_VERIFIED',
            'state':state,'original_release_sha256_unchanged':sha(b.protocol.OUT/'release.json'),
            'source_release_check':b.protocol.verify_published_release()['source_sha256'],
            'last_verified_resumed_step':steps[-1],'safe_resume_events':[r for r in selected if r['event']!='STEP_RETURNED'],
            'additional_budget':0,'replayed_updates':0,'automatic_retries':0,
            'scientific_worker_modified':False,'first_update_expected':20913,
            'bounded_event_tail_bytes':min(size,2*1024**2)}
    if result['original_release_sha256_unchanged']!=EXPECTED_RELEASE:raise PermissionError('ORIGINAL_RELEASE_CHANGED')
    record('startup_verification.json',result)
    return result


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ('check','start','status','verify-startup'):
        raise PermissionError('FIXED_MANUAL_OPERATOR_ACTION_ONLY')
    action={'check':ready,'start':start,'status':b.control.status,'verify-startup':verify_startup}[sys.argv[1]]
    print(json.dumps(action(),ensure_ascii=False,indent=2))
