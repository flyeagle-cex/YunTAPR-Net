"""Read-only B5/B6 closeout; never imports a model or reads weather payloads.

Requires the private preparation locator and the frozen execution checkout.
Only the two new E9 weight files are hashed, never deserialized. Existing
historical checks are inherited; only this package's new receipts are audited.
"""
import argparse
import hashlib
import json
import math
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

COMMIT = 'b251fd9ea06c0c90f48d2ac0decba0454114669d'
PROPOSAL = '36fc5dfbbc94c5576442ab95691595a7d4c3a130f373363015b5db13db6b57f1'
PUBLIC = Path('docs/research_readiness/20261025/evidence')
METRICS = ('brier', 'auroc', 'average_precision', 'conditional_pinball',
           'q32_coverage', 'q32_signed_bias', 'q32_absolute_error')


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canonical(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def query(p, sql):
    c = sqlite3.connect(Path(p).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        return c.execute(sql).fetchall()
    finally:
        c.close()


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-12), (a, b)


def stamp(p):
    return datetime.fromtimestamp(Path(p).stat().st_mtime, timezone(timedelta(hours=8))).isoformat()


def values(summary):
    return {k: summary['coverage'][-1] if k == 'q32_coverage' else summary[k] for k in METRICS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', required=True, type=Path)
    parser.add_argument('--frozen-code', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    assert not args.output.exists(), 'Never overwrite an existing closeout.'
    root = Path(__file__).resolve().parents[2]
    private = load(args.preparation)
    output = Path(private['output_root'])
    proposal = load(root / PUBLIC / 'b5_b6_corrected_start_proposal.json')
    assert private['proposal_sha256'] == proposal['proposal_sha256'] == PROPOSAL
    binding = load(output / 'authorization_binding.json')
    approval = binding['approval']
    assert approval['approved_by_researcher'] and approval['code_commit'] == COMMIT
    assert approval['proposal_sha256'] == PROPOSAL and approval['budget'] == proposal['budget']
    assert approval['scientific_choices'] == proposal['scientific_choices']
    assert not (output / 'failure.json').exists()
    completion = load(output / 'completion.json')
    assert completion == dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION', updates=8640,
                             total_logical_source_bytes=955143657680,
                             total_logical_source_files=285626, code_commit=COMMIT)
    assert subprocess.check_output(['git', '-C', str(args.frozen_code), 'rev-parse', 'HEAD'], text=True).strip() == COMMIT
    assert not subprocess.check_output(['git', '-C', str(args.frozen_code), 'status', '--porcelain'], text=True).strip()
    relevant = ('src/yuntapr/experimental/research_readiness/static_training.py',
                'src/yuntapr/experimental/research_readiness/static_terrain.py',
                'src/yuntapr/experimental/core_innovation/stage4/engine.py',
                'src/yuntapr/experimental/core_innovation/stage4/evaluation.py',
                'src/yuntapr/experimental/core_innovation/stage4/launch.py',
                'src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py')
    for file in relevant:
        assert sha(args.frozen_code / file) == proposal['code_sha256'][file]
    sources = {}

    def record(p, alias):
        sources[alias] = dict(sha256=sha(p), bytes=Path(p).stat().st_size, visibility='LOCAL_ONLY')

    record(output / 'authorization_binding.json', 'PACKAGE/authorization_binding.json')
    record(output / 'completion.json', 'PACKAGE/completion.json')
    record(output / 'static_paired_summary.json', 'PACKAGE/static_paired_summary.json')
    historical = Path(private['historical_pair'])
    baseline_path = historical / 'B4_development_09.json'
    assert sha(baseline_path) == proposal['baseline_E9_Dev_sha256']
    baseline = load(baseline_path)
    assert baseline['source_identity'] == proposal['data']
    baseline_orders = load(historical / 'paired_orders.json')
    baseline_initial = load(historical / 'paired_initial_identity.json')
    record(baseline_path, 'INHERITED/B4_development_09.json')
    group_reports = {'B4': {k: dict(summary=v['summary'], ids_sha256=v['ids_sha'],
                                   exact_score_table_sha256=v['exact_score_table_sha256'])
                            for k, v in baseline['groups'].items()}}
    tasks, epochs, tails, initializations = [], [], {}, {}
    total_bytes = total_files = 0
    for index, model in enumerate(('B5', 'B6'), 1):
        folder = output / f'{model}_s2029'
        task = load(folder / 'completion.json')
        assert (task['status'], task['model'], task['seed'], task['epochs'], task['optimizer_updates'],
                task['replay'], task['code_commit']) == ('COMPLETE_TRAIN_AND_DEV_EVALUATION', model, 2029, 9, 4320, 0, COMMIT)
        ledger = query(folder / 'updates.sqlite', 'SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')
        assert ledger == [(model, 'RETURNED', 4320, 1, 4320)]
        record(folder / 'updates.sqlite', f'{model}/updates.sqlite')
        record(folder / 'completion.json', f'{model}/completion.json')
        orders = load(folder / 'paired_orders.json')
        initial = load(folder / 'paired_initial_identity.json')
        assert orders == baseline_orders
        assert initial['B4'] == baseline_initial['B4']
        assert initial[model]['common_sha256'] == baseline_initial['B4']['common_sha256']
        initializations[model] = initial
        record(folder / 'paired_orders.json', f'{model}/paired_orders.json')
        record(folder / 'paired_initial_identity.json', f'{model}/paired_initial_identity.json')
        weather_bytes = weather_files = 0
        for epoch in range(1, 10):
            train = load(folder / f'{model}_train_{epoch:02d}.json')
            dev = load(folder / f'{model}_development_{epoch:02d}.json')
            seal = load(folder / f'{model}_LAST_epoch_{epoch:02d}.receipt.json')
            assert (train['scenes'], train['batches'], train['updates'], train['loss_arm']) == (959, 480, epoch * 480, 'E0')
            assert train['train_order_sha256'] == orders[str(epoch)]['sha256'] == canonical(orders[str(epoch)]['ids'])
            assert seal == task['checkpoints'][epoch - 1] and seal['code_commit'] == COMMIT
            assert seal['validation_receipt_sha256'] == canonical(dev)
            assert seal['population_sha256'] == proposal['data']['population_sha256']
            assert dev['source_identity'] == proposal['data']
            assert dev['partition_sha256'] == baseline['partition_sha256']
            assert dev['population_ids_sha256'] == baseline['population_ids_sha256']
            assert dev['occurrence_event'] == baseline['occurrence_event']
            s = dev['groups']['all']['summary']
            assert (s['scenes'], s['n_valid'], s['n_rain']) == (963, 3303090, 407820)
            assert len(s['tau']) == 32 and s['tau'][-1] == .984375
            close(s['brier_sum'] / s['n_valid'], s['brier'])
            close(s['s_qr'] / s['n_rain'], s['conditional_pinball'])
            close(s['covered'][-1] / s['n_rain'], s['coverage'][-1])
            tail = load(folder / f'{model}_tail_{epoch:02d}.json')
            assert len(tail['scene_sufficient_statistics']) == 963 and tail['nominal_q32'] == .984375
            assert sum(t['n_rain'] for t in tail['strata']) == s['n_rain']
            assert sum(t['q32_covered'] for t in tail['strata']) == s['covered'][-1]
            close(sum(t['n_rain'] * t['conditional_pinball'] for t in tail['strata']) / s['n_rain'], s['conditional_pinball'])
            for suffix in ('train', 'development', 'tail'):
                record(folder / f'{model}_{suffix}_{epoch:02d}.json', f'{model}/{suffix}_{epoch:02d}.json')
            record(folder / f'{model}_LAST_epoch_{epoch:02d}.receipt.json', f'{model}/LAST_epoch_{epoch:02d}.receipt.json')
            assert (folder / f'{model}_LAST_epoch_{epoch:02d}.pt').stat().st_size > 0
            for role in ('train', 'dev'):
                sub = folder / f'{model}_{role}_reads_{epoch:02d}'
                receipt = load(sub / 'pass_receipt.json')
                reads = receipt['actual_reads']
                assert not receipt['during_failure'] and reads['states'] == {'READ_COMPLETE': receipt['expected_files']}
                assert reads['opened_files'] == receipt['expected_files']
                assert reads['delivered_bytes'] == reads['reserved_bytes'] == receipt['expected_bytes']
                q = query(sub / 'reads.sqlite', 'SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state')
                assert q == [('READ_COMPLETE', reads['opened_files'], reads['delivered_bytes'], reads['reserved_bytes'], 0)]
                weather_bytes += reads['delivered_bytes']
                weather_files += reads['opened_files']
                record(sub / 'pass_receipt.json', f'{model}/{role}_{epoch:02d}/pass_receipt.json')
                record(sub / 'reads.sqlite', f'{model}/{role}_{epoch:02d}/reads.sqlite')
            epochs.append(dict(model=model, seed=2029, epoch=epoch, train=train,
                               development=s, checkpoint=seal))
            if epoch == 9:
                assert set(dev['groups']) == set(baseline['groups'])
                group_reports[model] = {}
                for group, data in dev['groups'].items():
                    base = baseline['groups'][group]
                    assert data['ids_sha'] == base['ids_sha']
                    assert data['summary']['n_valid'] == base['summary']['n_valid']
                    assert data['summary']['n_rain'] == base['summary']['n_rain']
                    group_reports[model][group] = dict(summary=data['summary'], ids_sha256=data['ids_sha'],
                                                       exact_score_table_sha256=data['exact_score_table_sha256'])
                tails[model] = {k: tail[k] for k in ('scope', 'nominal_q32', 'independent_event_count', 'strata')}
        assert weather_bytes == task['logical_source_bytes'] == 477571641012
        assert weather_files == task['logical_source_files'] == 142812
        static_bytes = proposal['budget']['static_source_bytes_per_model'][model]
        static_db = output / f'{model}_static_source.sqlite'
        assert query(static_db, 'SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state') == [('READ_COMPLETE', 1, static_bytes, static_bytes, 0)]
        assert query(static_db, 'SELECT state,COUNT(*) FROM jobs GROUP BY state') == [('COMPLETE', 1)]
        static_hash = query(static_db, 'SELECT sha256 FROM file_io')[0][0]
        assert static_hash == proposal['static_source_sha256'][model]
        record(static_db, f'{model}/static_source.sqlite')
        assert task['static_source_reads'] == dict(opened_files=1, delivered_bytes=static_bytes, reserved_bytes=static_bytes, states={'READ_COMPLETE': 1})
        assert task['total_logical_source_bytes'] == weather_bytes + static_bytes
        assert task['total_logical_source_files'] == weather_files + 1
        weight = folder / f'{model}_LAST_epoch_09.pt'
        record(weight, f'{model}/LAST_epoch_09.pt')
        assert sources[f'{model}/LAST_epoch_09.pt']['sha256'] == task['checkpoints'][-1]['checkpoint_sha256']
        elapsed = (folder / 'completion.json').stat().st_mtime - (output / f'task_{index}_claim.json').stat().st_mtime
        assert 0 < elapsed <= proposal['budget']['task_wall_seconds'][model]
        tasks.append(dict(model=model, seed=2029, status=task['status'], epochs=9, optimizer_updates=4320,
                          weather_source_bytes=weather_bytes, weather_source_files=weather_files,
                          static_source_bytes=static_bytes, static_source_files=1,
                          total_source_bytes=weather_bytes + static_bytes, total_source_files=weather_files + 1,
                          endpoint_sha256=task['checkpoints'][-1]['checkpoint_sha256'], code_commit=COMMIT,
                          completed_at=stamp(folder / 'completion.json'), wall_seconds_mtime_proxy=elapsed))
        total_bytes += weather_bytes + static_bytes
        total_files += weather_files + 1
    summary = load(output / 'static_paired_summary.json')
    assert summary['seed'] == 2029 and summary['endpoint'] == 'FIXED_EPOCH_9_LAST'
    computed = {m: values(g['all']['summary']) for m, g in group_reports.items()}
    assert computed == summary['values']
    for target, base in (('B5', 'B4'), ('B6', 'B4'), ('B6', 'B5')):
        assert summary['differences'][target + '_minus_' + base] == {k: computed[target][k] - computed[base][k] for k in METRICS}
    elapsed = (output / 'completion.json').stat().st_mtime - (output / 'authorization_binding.json').stat().st_mtime
    assert 0 < elapsed <= proposal['budget']['max_package_seconds']
    assert total_bytes == 955143657680 and total_files == 285626
    result = dict(status='VERIFIED_COMPLETE_STATIC_PAIR_TRAIN_AND_DEV', verified_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                  completed_at=stamp(output / 'completion.json'), training_commit=COMMIT, proposal_sha256=PROPOSAL,
                  data_version=proposal['data'], protocol=proposal['protocol'], scientific_choices=proposal['scientific_choices'],
                  static_source_sha256=proposal['static_source_sha256'], tasks=tasks, epochs=epochs,
                  endpoint='FIXED_EPOCH_9_LAST', endpoint_groups=group_reports, tail_diagnostics=tails,
                  summary=summary, initializations=initializations,
                  evaluation_script='src/yuntapr/experimental/core_innovation/stage4/evaluation.py',
                  evaluation_script_sha256=proposal['code_sha256']['src/yuntapr/experimental/core_innovation/stage4/evaluation.py'],
                  code_sha256={k: proposal['code_sha256'][k] for k in relevant},
                  budget_closure=dict(new_updates=8640, replay_updates=0, additional_retries=0,
                                      new_source_bytes=total_bytes, new_source_files=total_files,
                                      prior_static_source_bytes=62828, prior_static_source_files=1,
                                      cumulative_source_bytes=total_bytes + 62828, cumulative_source_files=total_files + 1,
                                      wall_seconds_mtime_proxy=elapsed, prior_wall_seconds_charged=13,
                                      cumulative_wall_seconds_mtime_proxy=elapsed + 13, max_package_seconds=43187,
                                      wall_clock_definition='File mtime interval, not exact GPU compute/billing; prior13seconds charged conservatively.'),
                  checks=dict(new_epoch_seals=18, new_weather_read_ledgers=36, new_static_ledgers=2,
                              actual_E9_weight_hashes=2, all_optimizer_returns=True, paired_orders_all_nine_epochs=True,
                              initial_B4_identity_matches_inherited=True, identical_population_partitions=True,
                              endpoint_summary_and_deltas_recomputed=True),
                  closeout_activity=dict(raw_weather_payload_reads=0, checkpoint_deserializations=0, model_inference=0,
                                         optimizer_updates=0, weight_files_hashed=2, historical_full_audits_rerun=False,
                                         final_2025='FROZEN_NO_ACCESS'), sources=sources,
                  scientific_acceptance=dict(training_and_dev='COMPLETE', terrain_ablation='COMPLETE_WITH_LIMITATIONS_SINGLE_SEED_MIXED_RESULTS',
                                             significance='NOT_CLAIMED', generalization='NOT_VERIFIED', B7_B8_training='NOT_STARTED'),
                  closeout_script_sha256=sha(__file__))
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert not re.search(r'[A-Za-z]:[\\/]|/Users/|/home/', text)
    args.output.write_text(text, encoding='utf-8')
    print(json.dumps(dict(status=result['status'], completed_at=result['completed_at'], tasks=tasks,
                          source_identities=len(sources), wall_seconds_proxy=elapsed), ensure_ascii=False))


if __name__ == '__main__':
    main()
