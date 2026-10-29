"""Seal only the approved zero-numeric DOTE control; no model/raw-data reads.

The original B7 is inherited from its immutable public closeout. Only the new
control's receipts, ledgers and one E9 weight hash are inspected.
"""
import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from close_static_pair import canonical, close, load, query, sha, stamp, values

COMMIT = '0c91ff0f36d5cce3f4516d38663482650f61b03a'
PROPOSAL = 'd7604c03d38585deca056994b119128cd2b6c2c7cbc50451a491e38b5cd4ea75'
CONTROL = 'B7_ZERO_DOTE'
PUBLIC = Path('docs/research_readiness/20261025/evidence')


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
    folder = out / 'B7_s2029'
    p = load(root / PUBLIC / 'dote_control_proposal_20261029.json')
    baseline_file = root / PUBLIC / 'b7_b8_terminal_20261028.json'
    baseline = load(baseline_file)
    assert canonical({k: v for k, v in p.items() if k != 'proposal_sha256'}) == private['proposal_sha256'] == PROPOSAL
    binding = load(out / 'authorization_binding.json')
    approval = binding['approval']
    assert approval['approved_by_researcher'] is True and approval['code_commit'] == binding['code_commit'] == COMMIT
    assert approval['proposal_sha256'] == PROPOSAL and approval['budget'] == p['budget']
    assert approval['scientific_choices'] == p['scientific_choices'] and approval['tasks'] == p['tasks']
    assert approval['approved_replay_updates'] == 0 and binding['control'] == 'ZERO_NUMERIC_RETAIN_REAL_MASKS'
    assert subprocess.check_output(['git', '-C', str(args.frozen_code), 'rev-parse', 'HEAD'], text=True).strip() == COMMIT
    assert not subprocess.check_output(['git', '-C', str(args.frozen_code), 'status', '--porcelain'], text=True).strip()
    for file, digest in p['code_sha256'].items():
        assert sha(args.frozen_code / file) == digest, file
    assert not (out / 'failure.json').exists() and not (folder / 'failure.json').exists()
    terminal = load(out / 'completion.json')
    task = load(folder / 'completion.json')
    assert terminal == dict(task, control_id=CONTROL, proposal_sha256=PROPOSAL)
    assert load(out / 'control_task_complete.json') == dict(task, control_id=CONTROL)
    assert (task['status'], task['model'], task['seed'], task['epochs'], task['optimizer_updates'], task['replay'], task['code_commit'], task['endpoint']) == (
        'COMPLETE_TRAIN_AND_DEV_EVALUATION', 'B7', 2029, 9, 4320, 0, COMMIT, 'FIXED_EPOCH_9_LAST')
    assert query(folder / 'updates.sqlite', 'SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state') == [('B7', 'RETURNED', 4320, 1, 4320)]
    sources = {}

    def record(path, alias):
        sources[alias] = dict(sha256=sha(path), bytes=path.stat().st_size, visibility='LOCAL_ONLY')

    for name in ('authorization_binding.json', 'completion.json', 'control_task_complete.json', 'source_admission.json'):
        record(out / name, 'CONTROL_PACKAGE/' + name)
    for name in ('updates.sqlite', 'completion.json', 'paired_orders.json', 'paired_initial_identity.json'):
        record(folder / name, CONTROL + '/' + name)
    orders = load(folder / 'paired_orders.json')
    initial = load(folder / 'paired_initial_identity.json')
    for name, digest in p['baseline_metadata_sha256'].items():
        assert sha(folder / name) == digest, name
    assert initial == baseline['initializations']['B7'] and initial['B7'] == p['initial_B7_full_state']
    inherited_task = next(t for t in baseline['tasks'] if t['model'] == 'B7')
    assert inherited_task['fixed_E9_sha256'] == p['baseline_E9_sha256']
    assert inherited_task['code_commit'] == p['baseline_execution_commit']
    epochs, groups, tails = [], {}, {}
    weather_bytes = weather_files = 0
    reference = baseline['endpoint_groups']['B7']
    for epoch in range(1, 10):
        train = load(folder / f'B7_train_{epoch:02d}.json')
        dev = load(folder / f'B7_development_{epoch:02d}.json')
        seal = load(folder / f'B7_LAST_epoch_{epoch:02d}.receipt.json')
        tail = load(folder / f'B7_tail_{epoch:02d}.json')
        assert (train['scenes'], train['batches'], train['updates'], train['loss_arm']) == (959, 480, epoch * 480, 'E0')
        assert train['train_order_sha256'] == orders[str(epoch)]['sha256'] == canonical(orders[str(epoch)]['ids'])
        assert seal == task['checkpoints'][epoch - 1] and seal['code_commit'] == COMMIT
        assert seal['validation_receipt_sha256'] == canonical(dev)
        assert seal['population_sha256'] == p['data']['population_sha256'] and dev['source_identity'] == p['data']
        assert set(dev['groups']) == set(reference)
        # The inherited fixed partitions carry their own ordered population IDs.
        for group, item in dev['groups'].items():
            assert item['ids_sha'] == reference[group]['ids_sha256']
            for count in ('scenes', 'n_valid', 'n_rain'):
                assert item['summary'][count] == reference[group]['summary'][count]
        s = dev['groups']['all']['summary']
        assert (s['scenes'], s['n_valid'], s['n_rain']) == (963, 3303090, 407820)
        assert len(s['tau']) == 32 and s['tau'][-1] == .984375
        close(s['brier_sum'] / s['n_valid'], s['brier'])
        close(s['s_qr'] / s['n_rain'], s['conditional_pinball'])
        close(s['covered'][-1] / s['n_rain'], s['coverage'][-1])
        assert len(tail['scene_sufficient_statistics']) == 963 and tail['nominal_q32'] == .984375
        assert sum(t['n_rain'] for t in tail['strata']) == s['n_rain']
        assert sum(t['q32_covered'] for t in tail['strata']) == s['covered'][-1]
        close(sum(t['n_rain'] * t['conditional_pinball'] for t in tail['strata']) / s['n_rain'], s['conditional_pinball'])
        bins = tail['elevation_diagnostics']['bins']
        assert sum(b['n_valid'] for b in bins.values()) == s['n_valid']
        assert sum(b['n_rain'] for b in bins.values()) == s['n_rain']
        close(sum(b['brier_sum'] for b in bins.values()), s['brier_sum'])
        epochs.append(dict(model=CONTROL, seed=2029, epoch=epoch, train=train,
                           development=s, checkpoint=seal, elevation_diagnostics=tail['elevation_diagnostics']))
        for name in ('train', 'development', 'tail'):
            record(folder / f'B7_{name}_{epoch:02d}.json', f'{CONTROL}/{name}_{epoch:02d}.json')
        record(folder / f'B7_LAST_epoch_{epoch:02d}.receipt.json', f'{CONTROL}/LAST_epoch_{epoch:02d}.receipt.json')
        assert (folder / f'B7_LAST_epoch_{epoch:02d}.pt').stat().st_size > 0
        for role in ('train', 'dev'):
            sub = folder / f'B7_{role}_reads_{epoch:02d}'
            receipt = load(sub / 'pass_receipt.json')
            n = receipt['actual_reads']
            scope = p['source_scope_summary']['Train' if role == 'train' else 'Development']
            assert not receipt['during_failure'] and receipt['source_manifest_sha256'] == scope['source_manifest_sha256']
            assert n['opened_files'] == receipt['expected_files'] == scope['file_count']
            assert n['delivered_bytes'] == n['reserved_bytes'] == receipt['expected_bytes'] == scope['bytes_per_pass']
            assert query(sub / 'reads.sqlite', 'SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state') == [('READ_COMPLETE', n['opened_files'], n['delivered_bytes'], n['reserved_bytes'], 0)]
            assert all(state == 'COMPLETE' for state, _ in query(sub / 'reads.sqlite', 'SELECT state,COUNT(*) FROM jobs GROUP BY state'))
            for name in ('pass_receipt.json', 'reads.sqlite'):
                record(sub / name, f'{CONTROL}/{role}_{epoch:02d}/{name}')
            weather_bytes += n['delivered_bytes']
            weather_files += n['opened_files']
        if epoch == 9:
            groups = {g: dict(summary=v['summary'], ids_sha256=v['ids_sha'], exact_score_table_sha256=v['exact_score_table_sha256']) for g, v in dev['groups'].items()}
            tails = {k: tail[k] for k in ('scope', 'nominal_q32', 'independent_event_count', 'strata', 'elevation_diagnostics')}
    assert (weather_bytes, weather_files) == (task['logical_source_bytes'], task['logical_source_files']) == (477571641012, 142812)
    static = out / 'B7_ZERO_DOTE_static_source.sqlite'
    assert query(static, 'SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state') == [('READ_COMPLETE', 1, 312828, 312828, 0)]
    assert query(static, 'SELECT state,COUNT(*) FROM jobs GROUP BY state') == [('COMPLETE', 1)]
    assert query(static, 'SELECT sha256 FROM file_io') == [(p['static_source_sha256']['B7'],)]
    record(static, CONTROL + '/static_source.sqlite')
    assert (task['total_logical_source_bytes'], task['total_logical_source_files']) == (477571953840, 142813)
    weight = folder / 'B7_LAST_epoch_09.pt'
    record(weight, CONTROL + '/LAST_epoch_09.pt')
    assert sources[CONTROL + '/LAST_epoch_09.pt']['sha256'] == seal['checkpoint_sha256']
    elapsed = (out / 'completion.json').stat().st_mtime - (out / 'authorization_binding.json').stat().st_mtime
    assert 0 < elapsed <= p['budget']['max_package_seconds']
    headline = {'B7': values(reference['all']['summary']), CONTROL: values(groups['all']['summary'])}
    group_deltas = {g: {k: values(reference[g]['summary'])[k] - values(item['summary'])[k] for k in headline['B7']} for g, item in groups.items()}
    tail_pairs = {}
    for section in ('strata', 'elevation'):
        a = baseline['tail_diagnostics']['B7']['strata'] if section == 'strata' else baseline['tail_diagnostics']['B7']['elevation_diagnostics']['bins']
        b = tails['strata'] if section == 'strata' else tails['elevation_diagnostics']['bins']
        keys = range(len(a)) if section == 'strata' else a.keys()
        tail_pairs[section] = {}
        for key in keys:
            for count in ('n_rain', 'n_valid'):
                if count in a[key]: assert a[key][count] == b[key][count]
            ms = [k for k in ('brier', 'conditional_pinball', 'q32_coverage') if k in a[key] and k in b[key]]
            tail_pairs[section][str(key)] = dict(B7=a[key], B7_ZERO_DOTE=b[key], B7_minus_B7_ZERO_DOTE={k: a[key][k] - b[key][k] for k in ms})
    result = dict(status='VERIFIED_COMPLETE_DOTE_NUMERIC_CONTROL_TRAIN_AND_DEV', model=CONTROL, seed=2029,
                  verified_at=datetime.now(timezone(timedelta(hours=8))).isoformat(), completed_at=stamp(out / 'completion.json'),
                  training_commit=COMMIT, proposal_sha256=PROPOSAL, data_version=p['data'], protocol=p['protocol'],
                  scientific_choices=p['scientific_choices'], endpoint='FIXED_EPOCH_9_LAST', endpoint_sha256=seal['checkpoint_sha256'],
                  epochs=epochs, endpoint_groups={'B7': reference, CONTROL: groups},
                  tail_diagnostics={'B7': baseline['tail_diagnostics']['B7'], CONTROL: tails}, initialization=initial,
                  summary=dict(values=headline, difference_direction='B7_REAL_MINUS_B7_ZERO_DOTE', group_deltas=group_deltas, tail_pairs=tail_pairs),
                  budget_closure=dict(optimizer_updates=4320, replay_updates=0, additional_retry=0, weather_bytes=weather_bytes,
                  weather_files=weather_files, static_bytes=312828, static_files=1, total_source_bytes=477571953840,
                  total_source_files=142813, wall_seconds_mtime_proxy=elapsed, wall_seconds_cap=21600,
                  wall_definition='Completion minus authorization-binding file mtime; not exact GPU billing'),
                  checks=dict(new_train_epochs=9, new_dev_epochs=9, new_weather_ledgers=18, new_static_ledgers=1, actual_E9_hashes=1,
                  initial_full_state_matches_B7=True, all_nine_orders_match_B7=True, all_groups_same_population=True),
                  evaluation_script=baseline['evaluation_script'], evaluation_script_sha256=baseline['evaluation_script_sha256'],
                  code_sha256=p['code_sha256'], sources=sources,
                  inherited_B7=dict(evidence=str(PUBLIC / baseline_file.name).replace('\\', '/'), sha256=sha(baseline_file),
                  execution_commit=p['baseline_execution_commit'], E9_sha256=p['baseline_E9_sha256'], reaudited=False),
                  closeout_activity=dict(raw_weather_reads=0, checkpoint_deserializations=0, model_inference=0, optimizer_updates=0,
                  weight_files_hashed=1, historical_checks_repeated=False, final_2025='FROZEN_NO_ACCESS'),
                  scientific_acceptance='COMPLETE_WITH_LIMITATIONS_SINGLE_SEED_NUMERIC_REPRESENTATION_ONLY',
                  limitations=['One seed, same Dev year; not independent storm replication or final generalization',
                  '128 zero-input projection weights lack loss gradients; equal nominal parameters is not equal effective capacity',
                  'Actual validity-mask information remains; DOTE is deterministic from existing GFS/DEM',
                  'Performance contrasts cannot demonstrate causal orographic uplift; no significance claim'],
                  closeout_script_sha256=sha(__file__))
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert not re.search(r'[A-Za-z]:[\\/]|/Users/|/home/', text)
    args.output.write_text(text, encoding='utf-8')
    print(json.dumps(dict(status=result['status'], completed_at=result['completed_at'], budget=result['budget_closure'],
                          E9_sha256=result['endpoint_sha256'], values=headline, real_minus_zero=group_deltas['all']), ensure_ascii=False))


if __name__ == '__main__':
    main()
