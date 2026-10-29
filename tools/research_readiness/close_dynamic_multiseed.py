"""Close only the new B7/B8 seed2030/2031 segment, without model or raw-data reads."""
import argparse
import json
import re
import statistics
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from close_static_pair import canonical, close, load, query, sha, stamp, values

COMMIT = 'e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c'
PUBLIC = Path('docs/research_readiness/20261025/evidence')
TASKS = [('B7', 2030), ('B8', 2030), ('B7', 2031), ('B8', 2031)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--frozen-code', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Never overwrite a closeout receipt'
    root = Path(__file__).resolve().parents[2]
    private = load(args.private)
    out = Path(private['output_root'])
    p = load(root / PUBLIC / 'b7_b8_multiseed_recovery_proposal_20261028.json')
    original = load(root / PUBLIC / 'b7_b8_multiseed_proposal_20261028.json')
    baseline = load(root / PUBLIC / 'b8_recovery_completion_20261028.json')
    budget = p['budget']
    assert canonical({k: v for k, v in p.items() if k != 'proposal_sha256'}) == private['proposal_sha256'] == p['proposal_sha256']
    binding = load(out / 'authorization_binding.json')
    approval = binding['approval']
    assert approval['approved_by_researcher'] is True and approval['code_commit'] == COMMIT
    assert approval['proposal_sha256'] == p['proposal_sha256'] and approval['budget'] == budget
    assert approval['approved_replay_updates'] == 441 and binding['independent_host_verified']
    assert approval['scientific_choices'] == p['scientific_choices']
    assert subprocess.check_output(['git', '-C', str(args.frozen_code), 'rev-parse', 'HEAD'], text=True).strip() == COMMIT
    assert not subprocess.check_output(['git', '-C', str(args.frozen_code), 'status', '--porcelain'], text=True).strip()
    assert not (out / 'failure.json').exists()
    terminal = load(out / 'completion.json')
    assert terminal == dict(status='COMPLETE_FOUR_MODELS_THREE_SEED_INNOVATION_SUMMARY', segment_updates=14400,
                           cumulative_updates=17721, logical_source_bytes=1591906721352, logical_source_files=476044,
                           code_commit=COMMIT, replay=441, proposal_sha256=p['proposal_sha256'])
    summary = load(out / 'three_seed_innovation_summary.json')
    assert summary['seeds'] == [2029, 2030, 2031] and summary['descriptive_only'] and summary['significance'] == 'NOT_CLAIMED'
    for kind in ('B7', 'B8'):
        assert summary['endpoints']['2029'][kind] == baseline['summary']['values'][kind]
    sources, tasks, epochs, groups, tails, identities = {}, [], [], {}, {}, {}

    def record(path, alias):
        sources[alias] = dict(sha256=sha(path), bytes=path.stat().st_size, visibility='LOCAL_ONLY')

    for name in ('authorization_binding.json', 'completion.json', 'three_seed_innovation_summary.json', 'source_admission.json'):
        record(out / name, 'RECOVERY_PACKAGE/' + name)
    reference = None
    for index, (kind, seed) in enumerate(TASKS):
        name = f'{kind}_s{seed}'
        folder = out / name
        assert not (folder / 'failure.json').exists()
        task = load(folder / 'completion.json')
        assert (task['status'], task['model'], task['seed'], task['epochs'], task['optimizer_updates'], task['code_commit'], task['endpoint']) == (
            'COMPLETE_TRAIN_AND_DEV_EVALUATION', kind, seed, 9, 4320, COMMIT, 'FIXED_EPOCH_9_LAST')
        start = 7 if index == 0 else 1
        new_updates = budget['new_task_updates'][index]
        assert query(folder / 'updates.sqlite', 'SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state') == [(kind, 'RETURNED', new_updates, (start - 1) * 480 + 1, 4320)]
        if index == 0:
            assert query(folder / 'updates.sqlite', 'SELECT COUNT(*) FROM updates WHERE u<=3321') == [(441,)]
            assert task['checkpoints'][:6] == p['inherited_checkpoints']
        orders = load(folder / 'paired_orders.json')
        initial = load(folder / 'paired_initial_identity.json')
        identities[name] = dict(initial=initial, order_sha256=sha(folder / 'paired_orders.json'),
                                epoch_order_sha256={k: v['sha256'] for k, v in orders.items()})
        if kind == 'B8':
            paired = out / f'B7_s{seed}'
            assert orders == load(paired / 'paired_orders.json') and initial == load(paired / 'paired_initial_identity.json')
        for file in ('completion.json', 'updates.sqlite', 'paired_orders.json', 'paired_initial_identity.json'):
            record(folder / file, name + '/' + file)
        total = count = 0
        for epoch in range(start, 10):
            train = load(folder / f'{kind}_train_{epoch:02d}.json')
            dev = load(folder / f'{kind}_development_{epoch:02d}.json')
            seal = load(folder / f'{kind}_LAST_epoch_{epoch:02d}.receipt.json')
            tail = load(folder / f'{kind}_tail_{epoch:02d}.json')
            assert (train['scenes'], train['batches'], train['updates'], train['loss_arm']) == (959, 480, epoch * 480, 'E0')
            assert train['train_order_sha256'] == orders[str(epoch)]['sha256'] == canonical(orders[str(epoch)]['ids'])
            assert (seal['model'], seal['epoch'], seal['updates'], seal['code_commit']) == (kind, epoch, epoch * 480, COMMIT)
            assert seal == task['checkpoints'][epoch - 1] and seal['validation_receipt_sha256'] == canonical(dev)
            assert seal['population_sha256'] == p['data']['population_sha256'] and dev['source_identity'] == p['data']
            if reference is None:
                reference = dev
            for key in ('population_ids_sha256', 'partition_sha256', 'occurrence_event'):
                assert dev[key] == reference[key]
            s = dev['groups']['all']['summary']
            assert (s['scenes'], s['n_valid'], s['n_rain']) == (963, 3303090, 407820)
            close(s['brier_sum'] / s['n_valid'], s['brier'])
            close(s['s_qr'] / s['n_rain'], s['conditional_pinball'])
            close(s['covered'][-1] / s['n_rain'], s['coverage'][-1])
            assert len(tail['scene_sufficient_statistics']) == 963 and sum(t['n_rain'] for t in tail['strata']) == s['n_rain']
            assert sum(t['q32_covered'] for t in tail['strata']) == s['covered'][-1]
            close(sum(t['n_rain'] * t['conditional_pinball'] for t in tail['strata']) / s['n_rain'], s['conditional_pinball'])
            bins = tail['elevation_diagnostics']['bins']
            assert sum(b['n_valid'] for b in bins.values()) == s['n_valid'] and sum(b['n_rain'] for b in bins.values()) == s['n_rain']
            close(sum(b['brier_sum'] for b in bins.values()), s['brier_sum'])
            epochs.append(dict(model=kind, seed=seed, epoch=epoch, train=train, development=s,
                               checkpoint=seal, elevation_diagnostics=tail['elevation_diagnostics'], code_commit=COMMIT))
            for stem in ('train', 'development', 'tail'):
                record(folder / f'{kind}_{stem}_{epoch:02d}.json', f'{name}/{stem}_{epoch:02d}.json')
            record(folder / f'{kind}_LAST_epoch_{epoch:02d}.receipt.json', f'{name}/LAST_epoch_{epoch:02d}.receipt.json')
            for role in ('train', 'dev'):
                sub = folder / f'{kind}_{role}_reads_{epoch:02d}'
                receipt = load(sub / 'pass_receipt.json')
                n = receipt['actual_reads']
                scope = original['source_scope_summary']['Train' if role == 'train' else 'Development']
                assert not receipt['during_failure'] and receipt['source_manifest_sha256'] == scope['source_manifest_sha256']
                assert n['opened_files'] == receipt['expected_files'] == scope['file_count']
                assert n['delivered_bytes'] == n['reserved_bytes'] == receipt['expected_bytes'] == scope['bytes_per_pass']
                assert query(sub / 'reads.sqlite', 'SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state') == [('READ_COMPLETE', n['opened_files'], n['delivered_bytes'], n['reserved_bytes'], 0)]
                assert all(state == 'COMPLETE' for state, _ in query(sub / 'reads.sqlite', 'SELECT state,COUNT(*) FROM jobs GROUP BY state'))
                total += n['delivered_bytes']
                count += n['opened_files']
                for file in ('pass_receipt.json', 'reads.sqlite'):
                    record(sub / file, f'{name}/{role}_{epoch:02d}/{file}')
            if epoch == 9:
                groups.setdefault(str(seed), {})[kind] = {g: dict(summary=v['summary'], ids_sha256=v['ids_sha'], exact_score_table_sha256=v['exact_score_table_sha256']) for g, v in dev['groups'].items()}
                tails.setdefault(str(seed), {})[kind] = {k: tail[k] for k in ('scope', 'nominal_q32', 'independent_event_count', 'strata', 'elevation_diagnostics')}
                assert values(s) == summary['endpoints'][str(seed)][kind]
        static = out / f'{name}_static_source.sqlite'
        assert query(static, 'SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state') == [('READ_COMPLETE', 1, 312828, 312828, 0)]
        assert query(static, 'SELECT sha256 FROM file_io') == [(p['static_source_sha256'][kind],)]
        record(static, name + '/static_source.sqlite')
        assert (total + 312828, count + 1) == (budget['new_source_bytes_per_task'][index], budget['new_source_files_per_task'][index])
        weight = folder / f'{kind}_LAST_epoch_09.pt'
        record(weight, name + '/LAST_epoch_09.pt')
        assert sources[name + '/LAST_epoch_09.pt']['sha256'] == seal['checkpoint_sha256']
        elapsed = (folder / 'completion.json').stat().st_mtime - (out / f'task_{index + 1}_claim.json').stat().st_mtime
        assert 0 < elapsed <= budget['task_wall_seconds'][index]
        tasks.append(dict(model=kind, seed=seed, status=task['status'], code_commit=COMMIT, fixed_E9_sha256=seal['checkpoint_sha256'],
                          optimizer_updates=4320, new_segment_updates=new_updates, replay_updates=441 if index == 0 else 0,
                          cumulative_attempt_updates=4761 if index == 0 else 4320, inherited_epochs=6 if index == 0 else 0,
                          epochs=9, completed_at=stamp(folder / 'completion.json'), source_bytes=total + 312828,
                          source_files=count + 1, wall_seconds_mtime_proxy=elapsed, wall_seconds_cap=budget['task_wall_seconds'][index]))
    # Independently check arithmetic on the existing executor summary, without rerunning inference.
    for name, metrics in summary['groups'].items():
        for metric, result in metrics.items():
            deltas = []
            for seed in ('2029', '2030', '2031'):
                pair = summary['group_endpoints'][seed][name]
                delta = pair['B8'][metric] - pair['B7'][metric]
                close(delta, result['by_seed'][seed])
                deltas.append(delta)
            close(statistics.mean(deltas), result['mean'])
            close(statistics.stdev(deltas), result['sample_sd'])
    assert summary['groups']['all'] == summary['metrics']
    for seed in ('2030', '2031'):
        for name in groups[seed]['B7']:
            a, b = groups[seed]['B7'][name], groups[seed]['B8'][name]
            assert a['ids_sha256'] == b['ids_sha256']
            for kind in ('B7', 'B8'):
                assert values(groups[seed][kind][name]['summary']) == summary['group_endpoints'][seed][name][kind]
        for kind in ('B7', 'B8'):
            for key in ('strata', 'elevation_diagnostics'):
                assert tails[seed][kind][key] == summary['tail_endpoints'][seed][kind][key]
    for section in ('rain_strata', 'elevation'):
        for key, metrics in summary[section].items():
            for metric, result in metrics.items():
                ds = []
                for seed in ('2029', '2030', '2031'):
                    t = summary['tail_endpoints'][seed]
                    a, b = (t[k]['strata'][int(key)] if section == 'rain_strata' else t[k]['elevation_diagnostics']['bins'][key] for k in ('B7', 'B8'))
                    close(b[metric] - a[metric], result['by_seed'][seed])
                    ds.append(result['by_seed'][seed])
                close(statistics.mean(ds), result['mean'])
                close(statistics.stdev(ds), result['sample_sd'])
    elapsed = (out / 'completion.json').stat().st_mtime - (out / 'authorization_binding.json').stat().st_mtime
    assert 0 < elapsed <= budget['max_package_seconds']
    result = dict(status='VERIFIED_COMPLETE_B7_B8_THREE_SEED_FIXED_E9_TRAIN_AND_DEV', verified_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                  completed_at=stamp(out / 'completion.json'), training_commit=COMMIT, proposal_sha256=p['proposal_sha256'], data_version=p['data'],
                  endpoint='FIXED_EPOCH_9_LAST', tasks=tasks, epochs=epochs, endpoint_groups=groups, tail_diagnostics=tails, initializations=identities,
                  summary=summary, budget_closure=dict(new_updates=14400, replay_updates=441, prior_actual_updates=3321, cumulative_updates=17721,
                  new_source_bytes=sum(t['source_bytes'] for t in tasks), new_source_files=sum(t['source_files'] for t in tasks),
                  cumulative_source_bytes=budget['cumulative_source_bytes'], cumulative_source_files=budget['cumulative_source_files'],
                  wall_seconds_mtime_proxy=elapsed, wall_seconds_cap=budget['max_package_seconds'], prior_wall_seconds_charged=budget['prior_wall_seconds_ceil'],
                  cumulative_wall_seconds_proxy=elapsed + budget['prior_wall_seconds_ceil'], additional_replay=0, additional_retry=0,
                  wall_definition='File mtime intervals; not GPU compute billing'), checks=dict(new_train_dev_epochs=30, inherited_epochs_not_reaudited=6,
                  new_weather_ledgers=60, new_static_ledgers=4, actual_E9_hashes=4, paired_initializations_and_orders=True, summary_arithmetic='PASS'),
                  evaluation_script=baseline['evaluation_script'], evaluation_script_sha256=baseline['evaluation_script_sha256'], sources=sources,
                  inherited_seed2029=dict(evidence='b8_recovery_completion_20261028.json', sha256=sha(root / PUBLIC / 'b8_recovery_completion_20261028.json'),
                  replay_updates=62, independent_seeds=1), inherited_B7_2030=dict(evidence='b7_b8_multiseed_recovery_proposal_20261028.json',
                  epochs=6, saved_updates=2880, prior_attempts=3321, unsaved_updates=441, original_evidence_unchanged=True),
                  activity=dict(raw_payload_reads=0, model_inference=0, optimizer_updates=0, checkpoint_deserializations=0, actual_E9_weight_hashes=4,
                  final_2025='FROZEN_NO_ACCESS'), scientific_acceptance='COMPLETE_WITH_LIMITATIONS; mixed DTFM gains; no independent-year, causality or significance claim',
                  closeout_script_sha256=sha(Path(__file__)))
    assert result['budget_closure']['new_source_bytes'] == budget['total_source_bytes'] and result['budget_closure']['new_source_files'] == budget['total_source_files']
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert not re.search(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/Users/|/home/', text)
    with args.output.open('x', encoding='utf-8') as f:
        f.write(text)
    print(json.dumps(dict(status=result['status'], completed_at=result['completed_at'], tasks=tasks, budget=result['budget_closure'], metrics=summary['metrics']), ensure_ascii=False))


if __name__ == '__main__':
    main()
