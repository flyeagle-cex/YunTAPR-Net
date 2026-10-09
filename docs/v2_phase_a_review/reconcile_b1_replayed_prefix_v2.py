"""Read closed journals only: retained epoch-15 replay vs both discarded attempts."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from completion_gate import reconcile_selection

REPO = Path(__file__).resolve().parents[2]
LOCAL = Path('F:/pytorch/Research/outputs/formal_training/b1_v2_phase_a/run_20261007T070503_825795Z')
PUBLIC = REPO / 'docs/formal_training_v2/pair_20261007T070503_825794Z/B1_V2'
RESUME = REPO / 'docs/v2_phase_a_authorized/pair_20261007T070503_825794Z/resume_20261009T003216_479921Z'
RETAINED = 'run_20261009T004140_659958Z'
DISCARDED = (('run_20261008T010824_279406Z', 3095), ('run_20261009T001234_525667Z', 382))
FIELDS = ('update', 'sample_ids', 'indices', 'LR', 'loss', 'L_occ', 'L_qr',
          'pre_clip_norm', 'post_clip_norm', 'actual_denominator', 'clipped')


def load(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return json.load(stream)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def completed(path):
    with path.open(encoding='utf-8') as stream:
        return [row for line in stream if (row := json.loads(line))['event'] == 'OPTIMIZER_STEP_COMPLETED']


def main():
    final = load(PUBLIC / 'final_report.json')
    history = load(PUBLIC / 'training_validation_history.json')
    assert final['status'] == 'COMPLETE' and final['completed_epoch'] == 17
    assert final['all_attempt_reconciliation']['all_attempt_updates_lower_bound'] == 92353
    assert final['all_attempt_reconciliation']['all_attempt_updates_upper_bound'] == 92353
    assert final['all_attempt_reconciliation']['retained_trajectory_updates'] == 88876
    assert final['all_attempt_reconciliation']['discarded_updates_lower_bound'] == 3477
    assert final['all_attempt_reconciliation']['discarded_updates_upper_bound'] == 3477
    selection = reconcile_selection(history)
    assert selection['completed_epoch'] == 17 and selection['final_early_stop_counter'] == 8
    current_path = LOCAL / 'audit' / RETAINED / 'epoch_015/steps.jsonl'
    receipts = [LOCAL / 'audit' / RETAINED / 'resume_identity.json',
                RESUME / 'applied_resume_identity_snapshot.json',
                RESUME / 'applied_resume_identity_verification.json',
                RESUME / 'resume_precheck.json']
    sources = [PUBLIC / 'final_report.json', PUBLIC / 'training_validation_history.json', current_path, *receipts]
    sources.extend(LOCAL / 'audit' / attempt / 'epoch_015/steps.jsonl' for attempt, _ in DISCARDED)
    before = {str(p): sha(p) for p in sources}
    receipt, snapshot, verification, precheck = (load(p) for p in receipts)
    assert receipt == snapshot and sha(receipts[0]) == verification['applied_receipt_sha256']
    assert sha(receipts[3]) == verification['precheck_sha256'] and precheck['status'] == 'PASS'
    assert receipt['LAST'] == verification['LAST'] == history[13]['checkpoint']
    assert receipt['LAST']['epoch'] == 14 and receipt['retained_updates'] == 73192
    assert not receipt['half_epoch_reused']
    assert verification['model_optimizer_scheduler_rng_exact_match'] is True
    current = completed(current_path)
    assert len(current) == 5228
    assert [r['update'] for r in current] == list(range(73193, 78421))
    comparisons = []
    for attempt, expected in DISCARDED:
        previous = completed(LOCAL / 'audit' / attempt / 'epoch_015/steps.jsonl')
        assert len(previous) == expected
        differences = [(i + 1, key) for i, (old, new) in enumerate(zip(previous, current))
                       for key in FIELDS if old[key] != new[key]]
        assert not differences, differences[:10]
        comparisons.append({'discarded_attempt': attempt, 'completed_updates_compared': len(previous),
                            'tolerance': 0, 'mismatches': [], 'fields': list(FIELDS)})
    assert all(sha(path) == digest for path, digest in before.items())
    result = {'status': 'B1_RETAINED_EPOCH_15_REPLAY_PREFIX_PASS',
        'source_sha256': before, 'audit_code_sha256': sha(Path(__file__)),
        'verified_resume_LAST': receipt['LAST'],
        'restored_state_sha256': receipt['verified_state_sha256'],
        'restore_identity_scope': 'Actual applied model/optimizer/scheduler/RNG receipt; terminal audit verifies completed checkpoint selection and permutation against history',
        'resume_completed_epoch': 14, 'resume_retained_updates': 73192,
        'early_stop_state_at_resume': history[13]['selection'],
        'early_stop_counters_after_completed_epochs_15_16_17':
            [row['selection']['non_improvement_count'] for row in history[14:]],
        'terminal_early_stopping_reconciliation': selection,
        'comparisons': comparisons, 'retained_epoch_15_complete_updates': 5228,
        'retained_trajectory_updates': 88876, 'all_attempt_updates': 92353,
        'discarded_uncheckpointed_updates': 3477, 'half_epoch_state_reused': False,
        'historical_sources_unchanged': True, 'FORMAL_OPTIMIZER_STEPS_ADDED': 0,
        'AUDIT_FORWARD_CALLS': 0, 'AUDIT_BACKWARD_CALLS': 0,
        'AUDIT_RAW_SOURCE_OPENS': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
        'V2_PHASE_B_AUTHORIZED': False, 'completed_utc': datetime.now(timezone.utc).isoformat()}
    out = REPO / 'docs/v2_phase_a_review/recovery_reconciliations' / datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ')
    out.mkdir(parents=True, exist_ok=False)
    with (out / 'b1_epoch15_replay_prefix_reconciliation.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'status': result['status'], 'output': str(out)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
