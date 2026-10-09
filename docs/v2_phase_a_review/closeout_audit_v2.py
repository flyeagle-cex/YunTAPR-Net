"""CPU-only terminal-model audit of existing Phase-A evidence, no raw reads or replay.

All training state is only deserialized for identity checks; never applied to a
model/optimizer. One terminal model may be audited while its paired model runs.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback
from completion_gate import reconcile_selection, resolve_authority


def read(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return json.load(stream)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def events(path):
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def verify_ref(ref, root, *, prefix=False):
    path = Path(ref['absolute_local_path']).resolve()
    if not path.is_relative_to(root.resolve()):
        raise PermissionError('Evidence path outside terminal model root')
    size = path.stat().st_size
    if size < ref['bytes'] or (not prefix and size != ref['bytes']):
        raise ValueError('Evidence size changed: ' + str(path))
    if prefix:
        remaining, h = ref['bytes'], hashlib.sha256()
        with path.open('rb') as stream:
            while remaining:
                block = stream.read(min(remaining, 8 * 1024**2))
                if not block:
                    raise ValueError('Truncated evidence prefix')
                h.update(block); remaining -= len(block)
        actual = h.hexdigest()
    else:
        actual = digest(path)
    if actual != ref['sha256']:
        raise ValueError('Evidence SHA changed: ' + str(path))
    return {'path': str(path), 'recorded_bytes': ref['bytes'], 'current_bytes': size,
            'verification': 'EXACT_BYTES' if size == ref['bytes'] else 'APPEND_ONLY_PREFIX_PRESERVED',
            'sha256': actual}


def verify_train(rows, epoch, ordered_ids, order, summary, lr_function, hash_function):
    kinds = Counter(row['event'] for row in rows)
    if kinds != Counter({'FORWARD_START': 5228, 'BACKWARD_CALL': 5228,
                         'OPTIMIZER_STEP_ATTEMPT': 5228, 'OPTIMIZER_STEP_COMPLETED': 5228}):
        raise ValueError('Incomplete retained training call journal')
    if [row['event'] for row in rows] != ['FORWARD_START', 'BACKWARD_CALL',
                   'OPTIMIZER_STEP_ATTEMPT', 'OPTIMIZER_STEP_COMPLETED'] * 5228:
        raise ValueError('Retained training event order differs')
    completed = rows[3::4]
    observed_ids = []
    socc = sqr = 0.0
    denominator = 0
    for step, row in enumerate(completed, 1):
        u = (epoch - 1) * 5228 + step
        indices = order[(step - 1) * 2: step * 2]
        ids = [ordered_ids[index] for index in indices]
        if any(item['update'] != u for item in rows[(step - 1) * 4:step * 4]):
            raise ValueError('Wrong retained update identity')
        if row['indices'] != indices or row['sample_ids'] != ids or rows[(step - 1) * 4]['sample_ids'] != ids:
            raise ValueError('Sample permutation/identity changed')
        if row['LR'] != lr_function(u, steps_per_epoch=5228) or row['actual_denominator'] != len(ids) * 3430:
            raise ValueError('LR or actual denominator changed')
        if not all(math.isfinite(row[key]) and row[key] >= 0 for key in ('loss', 'L_occ', 'L_qr', 'pre_clip_norm', 'post_clip_norm')):
            raise ValueError('Nonfinite/negative retained metrics')
        if row['post_clip_norm'] > 5.00001 or row['clipped'] != (row['pre_clip_norm'] > 5):
            raise ValueError('Gradient clip record differs')
        n = row['actual_denominator']; denominator += n
        socc += row['L_occ'] * n; sqr += row['L_qr'] * n
        observed_ids.extend(ids)
    want = {'scenes': len(observed_ids), 'steps': 5228, 'N_valid': denominator, 'exactly_once': True,
        'ordered_sample_ids_sha256': hash_function(observed_ids), 'global_core_loss': (socc + sqr) / denominator,
        'S_occ': socc, 'S_qr': sqr}
    if len(set(observed_ids)) != 10455 or summary != want:
        raise ValueError('Retained training totals/identity differs')
    return [row['sample_ids'] for row in completed]


def verify_validation(rows, ordered_ids):
    batches = [ordered_ids[index:index + 8] for index in range(0, 10501, 8)]
    if len(rows) != 1313 or len(batches[-1]) != 5:
        raise ValueError('Validation fixed-order coverage differs')
    for step, (row, ids) in enumerate(zip(rows, batches), 1):
        if row['event'] != 'VALIDATION_FORWARD_START' or row['step'] != step or row['sample_ids'] != ids:
            raise ValueError('Validation sample order/identity differs')
    return batches


def verify_diagnostics(rows, phase, batches, summary, observer_type):
    if len(rows) != len(batches):
        raise ValueError('Missing upper-tail forward')
    boundary = math.log1p(sys.float_info.max)
    for index, (row, ids) in enumerate(zip(rows, batches), 1):
        if row['event'] != 'UPPER_TAIL_FORWARD' or row['phase'] != phase or row['forward_index'] != index:
            raise ValueError('Diagnostic forward identity differs')
        if row['sample_ids'] != ids or row['batch_size'] != len(ids):
            raise ValueError('Diagnostic sample identity differs')
        for region, cells in (('YUNNAN_INSIDE', 3430), ('YUNNAN_OUTSIDE', 6570)):
            part = row[region]
            if part['scene_pixel_tau_exposure'] != len(ids) * cells * 32 or part['scene_pixel_any_tau_exposure'] != len(ids) * cells:
                raise ValueError('Diagnostic exposure denominator differs')
            if not math.isfinite(part['max_qlog']) or part['max_qlog'] != part['q32_max_qlog']:
                raise ValueError('Monotonic upper-tail maximum record differs')
            risk = part['max_qlog'] > boundary
            if part['FP64_PHYSICAL_OVERFLOW_RISK'] != risk or (part['fp64_boundary_exceedance_count'] > 0) != risk:
                raise ValueError('FP64 risk record differs')
            loc = part['max_location']
            if not 0 <= loc['batch_index'] < len(ids) or loc['sample_id'] != ids[loc['batch_index']]:
                raise ValueError('Diagnostic argmax scene differs')
            if not (0 <= loc['row'] < 100 and 0 <= loc['column'] < 100 and loc['tau_index'] == 31 and loc['tau'] == 31.5 / 32):
                raise ValueError('Diagnostic argmax coordinate/tau differs')
            previous = {'scene_pixel_tau_exposure': len(ids) * cells * 32,
                        'scene_pixel_any_tau_exposure': len(ids) * cells}
            for threshold in (10, 50, 100, 500, 1000):
                current = part['threshold_exceedances'][str(threshold)]
                if any(type(v) is not int or not 0 <= v <= previous[k] for k, v in current.items()):
                    raise ValueError('Descriptive exceedance counts differ')
                if not current['scene_pixel_any_tau_exposure'] <= current['scene_pixel_tau_exposure'] <= 32 * current['scene_pixel_any_tau_exposure']:
                    raise ValueError('Any-tau vs pixel-tau count relation differs')
                previous = current
    observer = object.__new__(observer_type)
    observer.phase, observer.rows = phase, rows
    if observer.report() != summary:
        raise ValueError('Upper-tail epoch aggregate/percentiles differ')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorization', required=True, type=Path)
    p.add_argument('--authorization-sha256', required=True)
    p.add_argument('--model', choices=('B0_MATCHED_V2', 'B1_V2'), required=True)
    args = p.parse_args()
    if digest(args.authorization) != args.authorization_sha256:
        raise PermissionError('Authority SHA mismatch')
    auth, origin_sha = resolve_authority(args.authorization)
    if auth['scope'] != 'FORMAL_PAIRED_PHASE_A_V2' or not auth['V2_PHASE_A_AUTHORIZED'] or auth['V2_PHASE_B_AUTHORIZED'] or auth['2025_RAW_ACCESS'] or auth['2025_PIXELS_READ']:
        raise PermissionError('Frozen Phase-A scope required')
    repo, execution = Path(auth['publication_repository']), Path(auth['execution_checkout'])
    public = Path(auth['publication_root']) / args.model
    final = read(public / 'final_report.json')
    history = read(public / 'training_validation_history.json')
    selection = reconcile_selection(history)
    if final['status'] != 'COMPLETE' or selection['termination_reason'] == 'NOT_TERMINATED' or any(final[k] != v for k, v in selection.items()):
        raise PermissionError('Only terminal complete model may be audited')
    local = Path(auth['checkpoint_roots'][args.model]) / auth['run_ids'][args.model]
    before = {str(path): digest(path) for path in public.iterdir() if path.is_file()}
    for relative, expected in auth['code_sha256'].items():
        if digest(execution / relative) != expected:
            raise ValueError('Frozen code SHA changed: ' + relative)
    sys.path[:0] = [str(execution / 'src'), str(execution / 'scripts')]
    import torch
    torch.set_num_threads(2)
    from yuntapr.training import formal_phase_a_v2 as f
    from yuntapr.training.checkpoint_v2 import verify_file
    if f.git('rev-parse', 'HEAD', root=execution) != auth['execution_commit'] or f.git('status', '--porcelain', '--untracked-files=normal', root=execution):
        raise ValueError('Execution checkout differs')
    if digest(execution / f.PROTOCOL) != auth['protocol_sha256'] or digest(execution / f.HEAD) != auth['head_sha256']:
        raise ValueError('Science protocol/head changed')
    protocol = read(execution / f.PROTOCOL)
    identities = {}
    for name, ref in protocol['identity'].items():
        path = Path(ref['path']); path = path if path.is_absolute() else execution / path
        if digest(path) != ref['sha256']:
            raise ValueError('Frozen data/config identity changed: ' + name)
        identities[name] = {'path': str(path), 'sha256': ref['sha256']}
    records = {}
    shared_fields = ('sample_id', 'window_start', 'analysis_time', 'imerg_day_path', 'imerg_index', 'imerg_sha256', 'target_valid_yunnan_cells')
    for year, count in ((2023, 10455), (2024, 10501)):
        paired = []
        for kind, label in (('B0_MATCHED_V2', 'B0_MATCHED'), ('B1_V2', 'B1')):
            with Path(identities[f'{label}_{year}']['path']).open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.DictReader(stream))
            if len(rows) != count or len({r['sample_id'] for r in rows}) != count or any(int(r['index']) != i or int(r['year']) != year or r['target_valid_yunnan_cells'] != '3430' for i, r in enumerate(rows)):
                raise ValueError('Frozen manifest scene identity/count differs')
            records[kind, year] = rows
            paired.append([[r[key] for key in shared_fields] for r in rows])
        if paired[0] != paired[1] or any(a['expected_nominal'] != b['slot_5_nominal'] for a, b in zip(records['B0_MATCHED_V2', year], records['B1_V2', year])):
            raise ValueError('Paired sample/latest-slot identity differs')
    out = repo / 'docs/v2_phase_a_review/closure_audits' / datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ') / args.model
    out.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        with (out / name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')
    try:
        registry = read(public / 'checkpoint_registry.json')
        if len(registry['epochs']) != len(history) or registry['LAST'] != history[-1]['checkpoint'] or registry['BEST'] != history[selection['best_checkpoint_epoch'] - 1]['checkpoint']:
            raise ValueError('Registry BEST/LAST differs from core selection')
        checkpoint_proofs, artifact_proofs, epochs = [], [], []
        previous_counters, previous_io = {}, {}
        for row in history:
            epoch, ref = row['epoch'], row['checkpoint']
            if read(public / f'epoch_{epoch:03d}_report.json') != row:
                raise ValueError('Published immutable epoch differs from history')
            marker = read(public / f'epoch_{epoch:03d}_complete.json')
            if marker['checkpoint'] != ref or marker['status'] != 'PASS' or marker['audit']['status'] != 'PASS':
                raise ValueError('Incomplete checkpoint transaction')
            if ref['model'] != args.model or ref['run_id'] != auth['run_ids'][args.model] or ref['epoch'] != epoch or ref['global_update'] != epoch * 5228:
                raise ValueError('Cross-model/run checkpoint identity')
            artifact_proofs.append(verify_ref(ref, local))
            artifact_proofs.extend(verify_ref(item, local) for item in row['local_epoch_artifacts'])
            artifact_proofs.extend(verify_ref(item, local, prefix=True) for item in row['io']['log_files'])
            attempt = Path(ref['absolute_local_path']).parent.name
            directory = local / 'audit' / attempt / f'epoch_{epoch:03d}'
            provenance = read(directory.parent / 'provenance.json')
            for key in ('pair_id', 'protocol_sha256', 'head_sha256', 'normalization_sha256', 'execution_commit', 'code_sha256'):
                if provenance[key] != auth[key]:
                    raise ValueError('Checkpoint authority/provenance differs: ' + key)
            if provenance['origin_authorization_sha256'] != origin_sha or provenance['identity'] != protocol['identity'] or provenance['initialization']['models'] != auth['initial_state_sha256']:
                raise ValueError('Checkpoint origin/data/paired init identity differs')
            payload = verify_file(ref, provenance)
            if any(payload[key] != row[key] for key in ('training', 'validation', 'selection', 'diagnostics')):
                raise ValueError('Checkpoint scientific record differs')
            checkpoint_proofs.append({'checkpoint': ref, 'verified_state_sha256': payload['state_sha256'],
                'scheduler': payload['scheduler'], 'completed_permutation_sha256': payload['completed_permutation_sha256'],
                'next_permutation_sha256': payload['next_permutation_sha256'], 'state_applied': False})
            expected_before = dict(row['counters_this_attempt'])
            expected_before['CHECKPOINT_WRITES'] -= 1
            if payload['counters'] != expected_before:
                raise ValueError('Before-write checkpoint counter boundary differs')
            del payload
            ids = [r['sample_id'] for r in records[args.model, 2023]]
            order = f.epoch_permutation(epoch - 1, count=10455).tolist()
            train_batches = verify_train(events(directory / 'steps.jsonl'), epoch, ids, order, row['training'], f.lr_for_update, f.state_digest)
            validation_batches = verify_validation(events(directory / 'validation_calls.jsonl'), [r['sample_id'] for r in records[args.model, 2024]])
            for phase, filename, batches in (('TRAIN', 'train_diagnostics.jsonl', train_batches), ('VALIDATION', 'validation_diagnostics.jsonl', validation_batches)):
                verify_diagnostics(events(directory / filename), phase, batches, row['diagnostics'][phase], f.UpperTailDiagnostics)
            if read(directory / 'diagnostics.json') != row['diagnostics']:
                raise ValueError('Diagnostics local/public record differs')
            expected_delta = {'FORWARD_CALLS': 6541, 'TRAIN_FORWARDS': 5228, 'VALIDATION_FORWARDS': 1313,
                'BACKWARD_CALLS': 5228, 'OPTIMIZER_STEP_ATTEMPTS': 5228, 'OPTIMIZER_STEPS': 5228, 'CHECKPOINT_WRITES': 1}
            old = previous_counters.get(attempt, dict.fromkeys(expected_delta, 0))
            actual_delta = {k: row['counters_this_attempt'][k] - old[k] for k in expected_delta}
            if actual_delta != expected_delta or row['counters_this_attempt']['scope'] != 'FORMAL':
                raise ValueError('Completed epoch counter delta differs')
            previous_counters[attempt] = row['counters_this_attempt']
            raw_delta = row['io']['RAW_SOURCE_OPENS'] - previous_io.get(attempt, 0)
            if raw_delta != 2 * (10455 + 10501) * (2 if args.model == 'B0_MATCHED_V2' else 7):
                raise ValueError('Completed epoch source exposure mismatch')
            previous_io[attempt] = row['io']['RAW_SOURCE_OPENS']
            if row['io']['DENIED_ATTEMPTS'] or row['io']['2025_RAW_ACCESS'] or row['io']['2025_PIXELS_READ']:
                raise ValueError('Source firewall violation')
            epochs.append({'epoch': epoch, 'status': 'PASS', 'counters_verified_from_actual_journals': actual_delta,
                           'RAW_SOURCE_OPENS': raw_delta, 'diagnostic_forwards': 6541, 'diagnostic_policy_affects_selection': False})
            print(json.dumps({'model': args.model, 'verified_epoch': epoch, 'total_epochs': len(history)}), flush=True)
        all_attempts = f.reconcile_attempts(local, len(history))
        if final['all_attempt_reconciliation'] != all_attempts:
            raise ValueError('Terminal all-attempt reconciliation differs')
        io_all = f.reconcile_io(local / 'audit')
        if io_all['DENIED_ATTEMPTS'] or io_all['2025_RAW_ACCESS'] or io_all['2025_PIXELS_READ']:
            raise ValueError('All-attempt source firewall violation')
        counters = {key: sum(ep['counters_verified_from_actual_journals'][key] for ep in epochs) for key in epochs[0]['counters_verified_from_actual_journals']}
        counters['RAW_SOURCE_OPENS'] = sum(ep['RAW_SOURCE_OPENS'] for ep in epochs)
        exact_attempt_snapshots = {}
        missing_attempt_counters = []
        for attempt in sorted((local / 'audit').glob('run_*')):
            path = attempt / 'attempt_counters.json'
            if path.exists(): exact_attempt_snapshots[attempt.name] = read(path)
            else: missing_attempt_counters.append(attempt.name)
        for path, expected in before.items():
            if digest(path) != expected:
                raise ValueError('Historical public artifact changed during audit')
        save('early_stopping_reconciliation.json', {**selection, 'patience': 8, 'min_delta': 1e-4, 'status': 'PASS',
            'source': str(public / 'training_validation_history.json'), 'uses_only_global_val_core_loss': True})
        save('checkpoint_identity_audit.json', {'status': 'PASS', 'checkpoints': checkpoint_proofs, 'artifacts': artifact_proofs})
        save('epoch_audit.json', {'status': 'PASS', 'model': args.model, 'epochs': epochs, 'paired_sample_sets_equal': True,
            'manifest_identities': identities, 'train_scenes': 10455, 'validation_scenes': 10501})
        save('formal_counter_reconciliation.json', {'status': 'PASS', 'retained_trajectory_exact_counters': counters,
            'all_attempt_optimizer_reconciliation': all_attempts, 'all_attempt_source_io': io_all,
            'exact_attempt_counter_snapshots': exact_attempt_snapshots, 'attempts_without_exact_final_counter_snapshot': missing_attempt_counters,
            'counter_claim_limit': 'Retained epoch counters verified exactly. All-attempt optimizer updates retain documented bounds for unclean exits; missing attempt snapshots are not fabricated.',
            'audit_optimizer_steps': 0, 'audit_backward_calls': 0, 'audit_forward_calls': 0})
        save('terminal_model_audit.json', {'status': 'TERMINAL_MODEL_AUDIT_PASS', 'model': args.model, 'final': final,
            'BEST': registry['BEST'], 'LAST': registry['LAST'], 'origin_authorization_sha256': origin_sha,
            'completion_authorization_sha256': args.authorization_sha256, 'execution_commit': auth['execution_commit'],
            'protocol_sha256': auth['protocol_sha256'], 'head_sha256': auth['head_sha256'], 'normalization_sha256': auth['normalization_sha256'],
            'historical_artifacts_unchanged': True, 'audit_source_sha256': digest(Path(__file__)),
            'MODEL_PARAMETERS_UPDATED': False, 'STATE_APPLICATION_PERFORMED': False, 'OPTIMIZER_STEPS': 0, 'BACKWARD_CALLS': 0,
            '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'V2_PHASE_B_AUTHORIZED': False,
            'PAIR_PHASE_A_COMPLETE_CLAIMED': False, 'completed_utc': datetime.now(timezone.utc).isoformat()})
        print(json.dumps({'status': 'TERMINAL_MODEL_AUDIT_PASS', 'output': str(out)}, ensure_ascii=False), flush=True)
    except BaseException as exc:
        save('failure.json', {'status': 'FAILED_STOP', 'error': repr(exc), 'traceback': traceback.format_exc(),
            'automatic_retry': False, 'OPTIMIZER_STEPS': 0, 'BACKWARD_CALLS': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0})
        raise


if __name__ == '__main__':
    main()
