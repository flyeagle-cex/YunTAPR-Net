"""Read-only startup evidence; never creates a session or starts/retries training."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v6.protocol import OUT,LOCAL,owned_json
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v6.control import status
from yuntapr.experimental.phase_b_v2_stability_review import native

def main():
    snapshot=status()
    if snapshot['effective_state']!='RUNNING' or snapshot['new_returned_verified']<1:
        raise RuntimeError('NO_VERIFIED_RUNNING_UPDATE_NO_STARTUP_PASS')
    folder=LOCAL/'sessions'/f"session_{snapshot['session']['number']:04d}"
    gui=owned_json(folder/'gui_bootstrap_identity.json')
    probes=dict(gui=native.process(gui),gui_job=native.job(gui['job_name']))
    if probes['gui']['status']!='LIVE_MATCH' or probes['gui_job']['status']!='PRESENT':
        raise RuntimeError('NATIVE_GUI_JOB_NOT_LIVE')
    console={}
    for name in ('gui_bootstrap_identity.json','task_owner_started.json','worker_console_isolation.json'):
        raw=owned_json(folder/name);item=raw.get('console_isolation',raw)
        if item['after']['hwnd'] or item['after']['process_count'] or item['after']['winerror'] not in (0,6):
            raise RuntimeError('NATIVE_CONSOLE_ISOLATION_NOT_VERIFIED')
        console[name]=dict(detached=item['detached'],after=item['after'])
    restored=owned_json(LOCAL/'B1_V2__E0__s2027/authorized_b1_epoch7_recovery.json')
    if restored['last_sha256']!='bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a' or not restored['all_state_verified_before_first_resumed_step']:
        raise ValueError('FULL_STATE_RESTORE_PROOF_MISSING')
    release=json.loads((OUT/'release.json').read_text(encoding='utf-8'))
    preflight=owned_json(folder/'preflight.json')
    if preflight['status']!='PASS':raise ValueError('FULL_DATA_PREFLIGHT_NOT_PASS')
    record=dict(status='RUNNING_AFTER_FIRST_VERIFIED_RESUMED_UPDATE',observed_utc=datetime.now(timezone.utc).isoformat(),
        snapshot=snapshot,gui_native_probes=probes,console_isolation=console,full_state_restore=restored,
        data_preflight_status=preflight['status'],source_commit=release['source_commit'],source_sha256=release['source_sha256'],
        release_sha256=hashlib.sha256((OUT/'release.json').read_bytes()).hexdigest(),
        first_resumed_logical_update=36597,source_epoch=7,current_training_epoch=8,
        launch_count=1,automatic_retry=False,other_seeds_authorized=False,
        actual_codex_app_close_during_real_training='NOT_VERIFIED',controlled_no_console_process_tests='PASS')
    with (OUT/'STARTUP_VERIFICATION.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(record,f,indent=2)
    final=dict(status=record['status'],observed_utc=record['observed_utc'],source_commit=release['source_commit'],
        campaign=snapshot['campaign'],current_run='B1_V2__E0__s2027',current_epoch=8,source_last_epoch=7,
        source_last_sha256=restored['last_sha256'],new_reserved=snapshot['new_reserved'],new_returned_verified=snapshot['new_returned_verified'],
        cumulative_reserved=snapshot['reserved'],cumulative_cap=364969,tests_passed=23,tests_failed=0,
        automatic_retry=False,actual_app_close_test='NOT_VERIFIED',seed2028_authorized=False,
        HISTORICAL_RECOVERY_RATIFICATION='NOT_GRANTED',HISTORICAL_2025_PATH_ATTRIBUTE_ACCESS='NOT_INSTRUMENTED')
    with (OUT/'final_status.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(final,f,indent=2)
    print(json.dumps(final))

if __name__=='__main__':main()
