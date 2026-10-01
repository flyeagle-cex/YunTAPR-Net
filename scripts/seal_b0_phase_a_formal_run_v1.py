"""Seal this completed run after the training process and Tee log close.

This performs no training, no raw-data reads, and no checkpoint writes.
The initialization manifest and the pre-log-close evidence index are retained.
"""
import csv
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parent.parent if SCRIPT.parent.name == 'scripts' else SCRIPT.parent / 'YunTAPR-Net-push-chunks'
RUN_ID = 'run_20261001T035003_243409Z'
OUT = ROOT / 'docs/formal_training/b0_phase_a/runs' / RUN_ID
EXPECTED_LOCAL = Path(r'F:\pytorch\Research\outputs\formal_training\b0_phase_a') / RUN_ID


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def atomic_json(path, value):
    temp = path.with_name(path.name + '.seal.tmp')
    with temp.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def rows(name):
    with (OUT / name).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    final = read('final_status.json')
    manifest = read('formal_run_manifest.json')
    runtime = read('runtime_summary.json')
    tests = read('test_summary_post_training.json')
    registry = read('checkpoint_registry.json')
    require(final['run_id'] == manifest['run_id'] == RUN_ID, 'Run identity differs')
    require(Path(manifest['local_checkpoint_directory']).resolve() == EXPECTED_LOCAL.resolve(), 'Checkpoint root differs')
    require(final['TRAIN_SCENES'] == 11720 and final['VALIDATION_SCENES'] == 11727, 'Population differs')
    require(final['PROTOCOL_VERSION'] == 'v1.0' and final['PRIMARY_SEED'] == 2026, 'Protocol/seed differs')
    for flag in ('PHASE_B_EXECUTED', 'PHASE_B_NORMALIZATION_COMPUTED', 'PHASE_B_AUTHORIZED', 'B1_STARTED'):
        require(final[flag] is False, flag)
    require(final['2025_PIXELS_READ'] == 0, '2025 access recorded')
    for relative, expected in manifest['baseline_files_disk_sha256'].items():
        require(sha(ROOT / relative) == expected, 'Historical file changed: ' + relative)
    for relative, expected in manifest['formal_implementation_sha256'].items():
        require(sha(ROOT / relative) == expected, 'Run implementation changed: ' + relative)
    for identity in manifest['identity'].values():
        require(sha(ROOT / identity['path']) == identity['sha256'], 'Frozen identity changed: ' + identity['path'])
    source_check = read('preflight.json')['source_identity']
    require(sha(OUT / 'source_identity_preflight.csv') == source_check['source_identity_ledger_sha256'], 'Source ledger changed')
    source = rows('source_identity_preflight.csv')
    require(len(source) == 23447, 'Source population size')
    for role, year, count in (('Train', '2023', 11720), ('Validation', '2024', 11727)):
        subset = [r for r in source if r['role'] == role]
        require(len(subset) == count and all(r['year'] == year for r in subset), 'Source roles/years differ')
        require([int(r['index']) for r in subset] == list(range(count)), 'Source order differs')
        require(len({r['sample_id'] for r in subset}) == count, 'Duplicate source identities')
    epochs = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(OUT.glob('epoch_[0-9][0-9][0-9].json'))]
    require([e['epoch'] for e in epochs] == list(range(1, len(epochs) + 1)), 'Nonconsecutive completed epochs')
    require(len(epochs) == final['TOTAL_COMPLETED_EPOCHS'], 'Final completed count differs')
    best, best_epoch, early_best, early_count = None, None, None, 0
    for e in epochs:
        n, train, val = e['epoch'], e['train'], e['validation']
        require(train['samples'] == e['training_samples'] == 11720, 'Incomplete Train epoch')
        require(val['samples'] == e['validation_samples'] == 11727, 'Incomplete Validation epoch')
        require(train['updates'] == 5860 and e['global_update_end'] == n * 5860, 'Update count')
        require(train['D_valid'] == 40199600 and val['D_valid'] == val['N_valid'] == 40223610, 'Valid denominators')
        require(val['N_rain'] == 4809183 and train['N_rain'] == 4188966, 'Rain denominators')
        loss = val['global_val_core_loss']
        require(math.isfinite(loss) and loss == (val['S_occ'] + val['S_qr']) / val['D_valid'], 'Global Validation aggregation')
        require(train['global_train_core_loss'] == (train['S_occ'] + train['S_qr']) / train['D_valid'], 'Global Train aggregation')
        require(val['strict_crossing_count'] == val['nonfinite_count'] == 0, 'Quantile/numerical violation')
        require(len(val['per_tau_pinball']) == len(val['per_tau_conditional_coverage']) == 32, 'Per-tau evidence')
        require(train['I_O']['cleanup_success'] and val['I_O']['cleanup_success'], 'Staging cleanup')
        if best is None or loss < best:
            best, best_epoch = loss, n
        if early_best is None or loss < early_best - 1e-4:
            early_best, early_count = loss, 0
        else:
            early_count += 1
        require(e['best_epoch'] == best_epoch and e['selection']['early_stop_best'] == early_best and e['selection']['non_improvement_count'] == early_count, 'Selection/early stopping disagreement')
        require(early_count < 8 or n == len(epochs), 'Execution after early stop')
    if epochs:
        require(final['SELECTED_CHECKPOINT_EPOCH'] == best_epoch and final['SELECTED_CHECKPOINT_VAL_CORE_LOSS'] == best, 'Final selection differs')
    for name, key, block in (('training_history.csv', 'global_train_core_loss', 'train'), ('validation_history.csv', 'global_val_core_loss', 'validation')):
        history = rows(name)
        require(len(history) == len(epochs), 'History count: ' + name)
        require(all(int(r['epoch']) == e['epoch'] and float(r[key]) == e[block][key] for r, e in zip(history, epochs)), 'History values: ' + name)
    identities = {}
    for role, filename in (('BEST', 'best_checkpoint_identity.json'), ('LAST', 'last_checkpoint_identity.json')):
        item = registry.get(role)
        if item:
            path = Path(item['absolute_local_path'])
            require(path.resolve().parent == EXPECTED_LOCAL.resolve() and path.suffix == '.pt', 'Checkpoint outside owned run')
            require(path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], 'Checkpoint integrity: ' + role)
            require(read(filename) == item, 'Checkpoint identity JSON differs: ' + role)
            require(final[role + '_CHECKPOINT_SHA256'] == item['sha256'], 'Final checkpoint identity: ' + role)
            identities[role] = item
    require({p.resolve() for p in EXPECTED_LOCAL.glob('*.pt')} == {Path(i['absolute_local_path']).resolve() for i in identities.values()}, 'Checkpoint retention differs')
    require(len({i['absolute_local_path'] for i in identities.values()}) <= 2, 'Retention exceeds BEST/LAST')
    if final['B0_PHASE_A_TRAINING_COMPLETED']:
        require(final['STOP_REASON'] in ('MAX_EPOCHS', 'EARLY_STOP'), 'Invalid success reason')
        require((len(epochs) == 50) if final['STOP_REASON'] == 'MAX_EPOCHS' else early_count == 8, 'Stop rule differs')
        require(final['POST_TRAINING_162_TESTS_PASS'] and tests['pass'] and tests['current_162_tests_actually_executed'] == 162 and tests['new_formal_tests'] == 9, 'Post-run tests')
        require(all(s['pass'] and s['failures'] == s['errors'] == s['skipped'] == 0 for s in tests['suites']), 'Post-run suite status')
        require(runtime['historical_files_preserved'] and runtime['all_checkpoint_provenance_pass'] and runtime['post_training_test_checkpoint_hashes_unchanged'] and not runtime['staging_cleanup_residual_files'], 'Final gates')
        require(set(identities) == {'BEST', 'LAST'}, 'Missing success checkpoints')
    old_index = read('evidence_sha256.json')
    mismatches = [name for name, expected in old_index.items() if sha(OUT / name) != expected]
    require(set(mismatches) <= {'execution.log'}, 'Unexpected pre-seal evidence mismatch: ' + repr(mismatches))
    require('FINAL ' in (OUT / 'execution.log').read_text(encoding='utf-8-sig'), 'Training log not yet closed/final')
    for source_name, copy_name in (('formal_run_manifest.json', 'formal_run_manifest_initialized.json'), ('evidence_sha256.json', 'evidence_sha256_pre_log_close.json')):
        with (OUT / copy_name).open('xb') as target:
            target.write((OUT / source_name).read_bytes())
        require(sha(OUT / source_name) == sha(OUT / copy_name), 'Initialization snapshot copy differs')
    report_name = 'B0_PHASE_A_FORMAL_TRAINING_REPORT.md'
    generated_report = OUT / 'B0_PHASE_A_FORMAL_TRAINING_REPORT_generated.md'
    with generated_report.open('xb') as target:
        target.write((OUT / report_name).read_bytes())
    original_report = (OUT / report_name).read_text(encoding='utf-8')
    addition = '\n## Completed-epoch observations\n\n'
    addition += 'The table uses only completed Train and Validation epochs. Scalar curves are also available in [training_history.csv](training_history.csv) and [validation_history.csv](validation_history.csv).\n\n'
    addition += '| Epoch | Train core loss | Validation core loss | BEST epoch | Early-stop count |\n| --- | --- | --- | --- | --- |\n'
    for e in epochs:
        addition += f"| {e['epoch']} | {e['train']['global_train_core_loss']:.10g} | {e['validation']['global_val_core_loss']:.10g} | {e['best_epoch']} | {e['selection']['non_improvement_count']} |\n"
    if best_epoch is not None:
        val = epochs[best_epoch - 1]['validation']
        addition += f'\n## Selected checkpoint: completed epoch {best_epoch}\n\n'
        addition += '| Validation observation | Actual value |\n| --- | --- |\n'
        for key in ('global_val_core_loss', 'global_L_occ', 'global_core_L_qr', 'N_valid', 'N_rain', 'prevalence', 'Brier_Score', 'AUROC', 'Average_Precision', 'conditional_mean_pinball', 'strict_crossing_count', 'nonfinite_count'):
            addition += f'| {key} | {val[key]} |\n'
        addition += '\nFull precision, conventions and per-tau observations are retained in ' + f'[epoch_{best_epoch:03d}.json](epoch_{best_epoch:03d}.json). '
        addition += 'The 32 quantile levels use the immutable science-contract formula `(i-0.5)/32`, i=1,...,32. Coverage is conditional on rainy valid cells and uses `R <= physical quantile`; pinball uses the frozen log1p loss domain. No probability cutoff was selected; POD/FAR/CSI remain `THRESHOLD_NOT_FROZEN`.\n\n'
        addition += '| tau | Conditional pinball | Conditional coverage |\n| --- | --- | --- |\n'
        with (OUT / 'selected_checkpoint_quantile_metrics.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(('selected_epoch', 'tau', 'conditional_pinball', 'conditional_coverage'))
            for i, (pinball, coverage) in enumerate(zip(val['per_tau_pinball'], val['per_tau_conditional_coverage']), start=1):
                tau = (i - .5) / 32
                writer.writerow((best_epoch, tau, pinball, coverage))
                addition += f'| {tau} | {pinball:.10g} | {coverage:.10g} |\n'
        addition += '\nThe same observations are exported in [selected_checkpoint_quantile_metrics.csv](selected_checkpoint_quantile_metrics.csv). These are evaluation observations, not an acceptance decision or a new calibration step.\n'
    addition += '\n## Evidence closure\n\n'
    addition += 'The initialization manifest and in-process evidence index are retained as `formal_run_manifest_initialized.json` and `evidence_sha256_pre_log_close.json`. The final manifest mirrors actual final status. The evidence index is refreshed after the final stdout record and the execution log close. The original automatically generated report is retained as `B0_PHASE_A_FORMAL_TRAINING_REPORT_generated.md`; this report adds tables from the already completed epoch evidence. Frozen scientific files, run implementation and checkpoint payloads remain unchanged.\n'
    (OUT / report_name).write_text(original_report + addition, encoding='utf-8', newline='\n')
    closed = datetime.now(timezone.utc).isoformat()
    manifest.update({k: v for k, v in final.items() if k not in ('run_id', 'failure')})
    manifest['initialization_snapshot'] = {'path': 'formal_run_manifest_initialized.json', 'sha256': sha(OUT / 'formal_run_manifest_initialized.json')}
    manifest['final_evidence'] = {name: sha(OUT / name) for name in ('final_status.json', 'training_start.json', 'preflight.json', 'source_identity_preflight.csv', 'training_history.csv', 'validation_history.csv', 'checkpoint_registry.json', 'best_checkpoint_identity.json', 'last_checkpoint_identity.json', 'test_summary_post_training.json', 'test_results_post_training.txt', 'early_stopping_summary.json', 'runtime_summary.json', 'execution.log', report_name)}
    manifest['finalized_evidence_utc'] = closed
    manifest['evidence_closure_script'] = {'path': 'scripts/seal_b0_phase_a_formal_run_v1.py', 'sha256': sha(SCRIPT)}
    manifest['validation_b13_hash_scope'] = 'RUN_PREFLIGHT_IDENTITY; historical identity/order unchanged; four historical sample hashes cross-checked'
    atomic_json(OUT / 'formal_run_manifest.json', manifest)
    seal = {'run_id': RUN_ID, 'sealed_utc': closed, 'training_log_closed': True,
        'closure_script_sha256': sha(SCRIPT),
        'initialization_snapshot_retained': True, 'pre_log_close_evidence_index_retained': True,
        'pre_log_close_mismatches': mismatches, 'mismatch_explanation': 'FINAL stdout and Tee log close occur after the in-process evidence index is created; only the closed log hash is refreshed.',
        'final_manifest_sha256': sha(OUT / 'formal_run_manifest.json'),
        'completed_epochs': len(epochs), 'selection_and_early_stop_independently_recomputed': True,
        'historical_files_and_locked_implementation_unchanged': True,
        'checkpoint_bytes_unchanged': True, 'checkpoint_identities': identities,
        'no_training_or_raw_data_read_during_seal': True,
        'no_phase_b_execution': True, 'status_fields_copied_from_actual_final_status': True}
    atomic_json(OUT / 'publication_seal.json', seal)
    evidence = {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != 'evidence_sha256.json'}
    atomic_json(OUT / 'evidence_sha256.json', evidence)
    require(all(sha(OUT / name) == expected for name, expected in read('evidence_sha256.json').items()), 'Final sealed evidence verification')
    print(json.dumps({'sealed': True, 'completed': final['B0_PHASE_A_TRAINING_COMPLETED'], 'epochs': len(epochs), 'best_epoch': best_epoch, 'best_loss': best, 'verified_public_files': len(evidence), 'checkpoint_roles': list(identities)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
