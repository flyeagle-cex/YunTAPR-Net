"""Read immutable applied-state receipt and read-only monitor, not mutable runner JSON."""
import hashlib
import json
from pathlib import Path
import urllib.request

REPO = Path(__file__).resolve().parents[2]
BASE = REPO / 'docs/v2_phase_a_authorized/pair_20261007T070503_825794Z/resume_20261009T003216_479921Z'
LOCAL = Path('F:/pytorch/Research/outputs/formal_training/b1_v2_phase_a/run_20261007T070503_825795Z/audit')


def read(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return json.load(stream)


def main():
    proof = read(BASE / 'resume_precheck.json')
    attempts = sorted(LOCAL.glob('run_*'))
    latest = attempts[-1]
    identity_path = latest / 'resume_identity.json'
    if latest.name <= 'run_20261009T001234_525667Z' or not identity_path.exists():
        print('PENDING_APPLIED_STATE_RECEIPT', flush=True)
        raise SystemExit(3)
    value = read(identity_path)
    assert value['LAST'] == proof['checkpoint']
    assert value['verified_state_sha256'] == proof['verified_state_sha256']
    assert value['retained_updates'] == 73192 and value['half_epoch_reused'] is False
    provenance = read(latest / 'provenance.json')
    origin = read(BASE.parent / 'authorization.json')
    for key in ('code_sha256', 'protocol_sha256', 'head_sha256', 'normalization_sha256', 'execution_commit', 'pair_id'):
        assert provenance[key] == origin[key], key
    with urllib.request.urlopen('http://127.0.0.1:8771/api/status', timeout=10) as response:
        status = json.load(response)
    assert status['pid'] == 43428 and status['process_alive'] is True
    assert status['monitor_reads_mutable_runner_json'] is False
    event = status.get('latest_step_event')
    if not event:
        print('APPLIED_STATE_PASS_PENDING_FIRST_COMPLETED_STEP', flush=True)
        raise SystemExit(3)
    assert status['epoch'] == 15 and status['step'] > 0
    original_path = LOCAL / 'run_20261008T010824_279406Z/epoch_015/steps.jsonl'
    matched = None
    with original_path.open(encoding='utf-8') as stream:
        for line in stream:
            candidate = json.loads(line)
            if candidate['event'] == 'OPTIMIZER_STEP_COMPLETED' and candidate['update'] == event['update']:
                matched = candidate
                break
    assert matched is not None
    keys = ('update', 'sample_ids', 'indices', 'LR', 'loss', 'L_occ', 'L_qr', 'pre_clip_norm',
            'post_clip_norm', 'actual_denominator', 'clipped')
    assert all(matched[key] == event[key] for key in keys)
    snapshot = BASE / 'applied_resume_identity_snapshot.json'
    with snapshot.open('xb') as stream:
        stream.write(identity_path.read_bytes())
    report = {'status': 'APPLIED_STATE_AND_COMPLETED_UPDATE_PASS',
        'applied_receipt_path': str(identity_path), 'applied_receipt_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        'precheck_sha256': hashlib.sha256((BASE / 'resume_precheck.json').read_bytes()).hexdigest(),
        'model_optimizer_scheduler_rng_exact_match': True, 'LAST': value['LAST'],
        'half_epoch_reused': False, 'retained_updates_at_resume': 73192,
        'observed_completed_step': status['step'], 'observed_update': event['update'],
        'observed_update_matches_original_zero_tolerance': True, 'fields_compared': keys,
        'comparison_scope': 'One observed completed update; not a claim about the entire future epoch',
        'observed_step_event': event, 'formal_pid': 43428, 'monitor_url': 'http://127.0.0.1:8771/',
        'audit_added_formal_optimizer_steps': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
        'V2_PHASE_B_AUTHORIZED': False, 'PAIR_PHASE_A_COMPLETE': False}
    with (BASE / 'applied_resume_identity_verification.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps({'status': report['status'], 'attempt': latest.name, 'epoch': 15,
                      'step': status['step'], 'update': event['update']}), flush=True)


if __name__ == '__main__':
    main()
