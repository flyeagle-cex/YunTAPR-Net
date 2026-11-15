"""Artificial CPU checks for mountain cells, grant boundaries and worker hooks."""
import argparse
import copy
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from tools.research_readiness.mountain_pair_metrics import MountainAccumulator, CONTRACT, ELEVATIONS, primary_contrast
from tools.research_readiness import start_mountain_pair_evaluation as entry
from tools.research_readiness.prepare_paired_point_evaluation import canonical_task_bindings


def fixture(rate=None, perfect_mountain=False):
    rate = np.array([[.1, 20., 21.], [1., 30., 40.]], np.float32) if rate is None else np.asarray(rate, np.float32)
    fields = rate[None, None]
    mask = np.ones_like(fields, bool)
    nodes = np.broadcast_to(np.log1p(np.arange(1, 33, dtype=np.float64))[None, :, None, None], (1, 32, 2, 3)).copy()
    if perfect_mountain:
        nodes[0, :, :, 2] = np.log1p(rate[:, 2][None, :] + np.linspace(-.05, .05, 32)[:, None])
    return fields, mask, mask.copy(), np.full_like(fields, .6, dtype=np.float64), nodes


def report(args):
    rate, valid, region, p, q = args
    mask = (valid & region)[:, 0]
    wet = mask & (rate[:, 0] > np.float32(.1))
    y = rate[:, 0][wet].astype(np.float64)
    nodes = np.moveaxis(q, 1, -1)[wet]
    tau = ((np.arange(32) + .5) / 32)[None]
    error = np.log1p(y)[:, None] - nodes
    return {'groups': {'all': {'summary': dict(n_valid=int(mask.sum()), n_rain=int(wet.sum()),
            conditional_pinball=float(np.maximum(tau * error, (tau - 1) * error).mean(1).mean()),
            brier=float(np.square(p[:, 0][mask] - (rate[:, 0][mask] > np.float32(.1))).mean()),
            covered=[int((nodes[:, -1] >= np.log1p(y)).sum())])}}}


def pack():
    return SimpleNamespace(grid=SimpleNamespace(identity='ARTIFICIAL_GRID'),
        values=np.array([[[500., 1500., 2500.], [500., 1500., 2500.]]]),
        valid=np.ones((1, 2, 3), bool), region=np.ones((2, 3), bool))


def accumulated(args, terrain=None):
    acc = MountainAccumulator(terrain or pack(), ['2024-SYNTHETIC'])
    acc.add(['2024-SYNTHETIC'], *args)
    return acc.finish(report(args))


def grant_fixture():
    runner = entry.gate
    private = dict(output_root=str(ROOT / 'docs/research_readiness/.local/ARTIFICIAL_OUTPUT'),
                   preflight_root=str(ROOT / 'docs/research_readiness/.local/ARTIFICIAL_PREFLIGHT'),
                   metadata_files={}, scientific_files={})
    proposal = dict(authorization_scope=entry.SCOPE, tasks=list(entry.TASKS), budget=copy.deepcopy(entry.LIMITS),
                    final_2025_access=False, execution_code_commit='ARTIFICIAL',
                    private_preparation_sha256=runner.digest(private),
                    scientific_choices=copy.deepcopy(dict(entry.INHERITED_CHOICES, terrain_evaluation=CONTRACT)),
                    data_scope=dict(year=2024, role='Development', scenes=963, n_valid=3303090, n_rain=407820),
                    data_identity=dict(population_sha256=runner.POPULATION_SHA256),
                    models=[dict(task=task, model='B7', seed=2029, endpoint='FIXED_EPOCH_9_LAST',
                                 dynamic_control=control, checkpoint_bytes=size, checkpoint_sha256=sha)
                            for task, (control, size, sha) in zip(entry.TASKS, entry.MODEL_BINDINGS)])
    return proposal, private


def bind(proposal, private):
    proposal = copy.deepcopy(proposal)
    proposal['proposal_sha256'] = entry.gate.digest(proposal)
    private = dict(private, proposal_sha256=proposal['proposal_sha256'])
    approval = dict(approved_by_researcher=True, authorization_scope=entry.SCOPE,
                    proposal_sha256=proposal['proposal_sha256'], code_commit=proposal['execution_code_commit'],
                    tasks=proposal['tasks'], scientific_choices=proposal['scientific_choices'],
                    budget=proposal['budget'], output_root=private['output_root'],
                    decision_id='ARTIFICIAL_NOT_AN_ACTUAL_APPROVAL', researcher_instruction='ARTIFICIAL_CHECK_ONLY')
    return proposal, private, approval


def integration_checks(checks, real, zero):
    """Exercise real entry/finalizer control flow with artificial IO boundaries."""
    from tools.research_readiness import paired_point_worker as shared
    spec = importlib.util.spec_from_file_location('mountain_worker_fixture', ROOT / 'tests/research_readiness/test_paired_point_worker.py')
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    with fixtures.workspace_directory() as temporary, patch.dict(fixtures.os.environ), patch.object(tempfile, 'tempdir', tempfile.tempdir):
        folder = Path(temporary)
        runtime, p, v, state, actual, _ = fixtures.fixture(folder)
        reference = runtime.read('report')
        groups = ('all', 'analysis_UTC_00', 'analysis_UTC_06', 'analysis_UTC_12', 'analysis_UTC_18', 'scene_max_ge20')
        for name in groups[1:]:
            reference['groups'][name] = copy.deepcopy(reference['groups']['all'])
            actual['groups'][name] = copy.deepcopy(actual['groups']['all'])
        calls = []

        class Diagnostic:
            def __init__(self, terrain, ids):
                assert terrain == 'SYNTHETIC_PACK' and len(ids) == 963

            def add_batch(self, prediction, batch):
                calls.append(batch.ids)

            def finish(self, report):
                assert report is actual
                return real

        treatments = []
        def transform(terrain, definition):
            treatments.append(terrain)
            return 'SYNTHETIC_TRANSFORM'
        with patch.object(shared, '_runtime', return_value=runtime):
            result = shared.run_task(folder, p, v, 'CONTROL_E0', folder / 'output', lambda: None,
                                     diagnostics_factory=Diagnostic, transform_factory=transform, include_joint=False)
        assert calls == state['forwards'] and len(calls) == 121
        assert treatments == ['SYNTHETIC_PACK'] and state['joint'] == []
        assert result['terrain_population_sha256'] == real['paired_population_sha256']
        assert set(result['gate']['groups']) == set(groups)
        assert not (folder / 'output/strong_joint_pixels.npz').exists()
        for name in groups:
            changed = copy.deepcopy(actual)
            changed['groups'][name]['summary']['brier'] += .01
            try:
                shared._gate_report(changed, reference)
            except ValueError:
                continue
            raise AssertionError('Frozen gate accepted changed group ' + name)
    checks['shared_worker_diagnostic_hook_121_single_forwards_and_no_joint_export'] = True
    checks['all_six_frozen_groups_pass_and_each_group_rejects_drift'] = True

    gate = entry.gate
    accounting = dict(metadata_archive_reserved_bytes=0, metadata_open_instances=0,
                      payload_archive_reserved_bytes=0, payload_open_instances=0)
    class Guard:
        active = False
        def install(self):
            self.active = True
        def close(self):
            self.active = False
            return dict(accounting)

    with fixtures.workspace_directory() as temporary:
        folder = Path(temporary)
        p, v = grant_fixture()
        v.update(output_root=str(folder / 'package'), preflight_root=str(folder / 'preflight'), runtime_python=sys.executable)
        p['private_preparation_sha256'] = gate.digest(v)
        p, v, a = bind(p, v)
        paths = [folder / name for name in ('synthetic_proposal.json', 'synthetic_private.json', 'synthetic_approval.json')]
        for path, value in zip(paths, (p, v, a)):
            gate.write(path, value)
        commands = []
        package = Path(v['output_root'])

        class Child:
            def __init__(self, command, **kwargs):
                commands.append(command)
                assert Path(command[2]) == gate.ENTRY_PATH and command[3] == 'worker'
                task = command[-1]
                output = package / task
                output.mkdir()
                terrain = real if task == entry.TASKS[0] else zero
                gate.write(output / 'terrain_metrics.json', terrain)
                gate.write(output / 'recomputed_report.json', report(fixture()))
                gate.write(output / 'point_metrics.json', {'artificial_fixture': True})
                cost = dict(accounting, payload_archive_reserved_bytes=26639253112 + 312828 + 2 * p['models'][entry.TASKS.index(task)]['checkpoint_bytes'], payload_open_instances=7953)
                gate.write(output / 'task_complete.json', dict(status='COMPLETE', task=task, accounting=cost, result={'task': task, 'status': 'COMPLETE'}))
                self.returncode = 0
            def poll(self):
                return self.returncode

        with ExitStack() as stack:
            for name, replacement in (
                ('guard_for', lambda *args: Guard()),
                ('validate_bound_inputs', lambda *args: None),
                ('require_host', lambda: None),
                ('resources', lambda *args: {'artificial_resource_admission': True}),
            ):
                stack.enter_context(patch.object(gate, name, replacement))
            stack.enter_context(patch.object(gate.subprocess, 'Popen', Child))
            entry.validate_entry(*paths)
            entry.validate_entry(*paths)
            gate.execute(*paths)
        complete = gate.read(package / 'completion.json')
        paired = gate.read(package / 'paired_metrics.json')
        assert len(commands) == 2 and [c[-1] for c in commands] == list(entry.TASKS)
        assert complete['status'] == gate.COMPLETION_STATUS
        assert complete['paired_metrics_sha256'] == gate.sha(package / 'paired_metrics.json')
        assert paired['primary_contrast'] == primary_contrast(real, zero)
        assert len(paired['cells']) == 3 and all(len(rows) == 7 for rows in paired['cells'].values())
        assert paired['scientific_status'] == 'NOT_VERIFIED'
        assert not (package / 'failure.json').exists()
    checks['new_entry_two_preflights_serial_dispatch_and_actual_finalizer'] = True
    checks['finalizer_all_21_cells_contrast_and_completion_sha'] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    checks = {}
    real_args, zero_args = fixture(perfect_mountain=True), fixture()
    real, zero = accumulated(real_args), accumulated(zero_args)
    assert real['population'] == dict(n_valid=6, n_rain=5, n_strong=3)
    assert sum(c['n_rain'] for g in real['elevation_groups'].values() for c in g['cells']) == 5
    assert primary_contrast(real, zero)['status'] == 'DIRECTIONAL_LOCAL_IMPROVEMENT'
    assert primary_contrast(zero, real)['status'] == 'DIRECTIONAL_LOCAL_DEGRADATION'
    assert primary_contrast(real, zero)['n_strong'] == 2
    checks['strict_fp32_threshold_and_all_three_by_seven_cells'] = True
    checks['paired_local_improvement_and_degradation_directions'] = True
    assert primary_contrast(real, real)['status'] == 'MIXED_OR_WITHIN_ROUNDOFF'
    empty_args = fixture([[.1, 20, 1], [1, 30, 2]])
    empty = accumulated(empty_args)
    assert primary_contrast(empty, empty)['status'] == 'NOT_ESTIMABLE'
    checks['ties_and_empty_primary_are_explicit'] = True

    def rejected(name, action, exceptions=(ValueError, RuntimeError, PermissionError, FloatingPointError)):
        try:
            action()
        except exceptions:
            checks[name] = True
        else:
            raise AssertionError(name + ' accepted')

    changed = fixture()
    changed[0][0, 0, 0, 2] = 22.
    rejected('mismatched_truth_identity', lambda: primary_contrast(real, accumulated(changed)))
    changed_pack = pack()
    changed_pack.values[0, 0, 2] = 1500.
    rejected('mismatched_elevation_membership', lambda: primary_contrast(real, accumulated(zero_args, changed_pack)))
    acc = MountainAccumulator(pack(), ['2024-SYNTHETIC'])
    rejected('wrong_scene_order', lambda: acc.add(['2024-WRONG'], *fixture()))
    rejected('failed_accumulator_cannot_continue', lambda: acc.add(['2024-SYNTHETIC'], *fixture()))
    acc = MountainAccumulator(pack(), ['2024-SYNTHETIC'])
    rejected('incomplete_accumulator', lambda: acc.finish(report(fixture())))
    args_bad = list(fixture())
    args_bad[-1][:] = np.inf
    rejected('nonfinite_quantiles', lambda: accumulated(args_bad))
    acc = MountainAccumulator(pack(), ['2024-SYNTHETIC'])
    acc.add(['2024-SYNTHETIC'], *fixture())
    wrong = report(fixture())
    wrong['groups']['all']['summary']['conditional_pinball'] += 1.
    rejected('global_frozen_metric_reconciliation', lambda: acc.finish(wrong))

    proposal, private = grant_fixture()
    entry.validate_grant(*bind(proposal, private))
    checks['exact_mountain_policy_grant_schema'] = True
    for name, mutation in (
        ('reject_budget_drift', lambda p: p['budget'].update(retries=1)),
        ('reject_checkpoint_treatment_drift', lambda p: p['models'][1].update(dynamic_control='REAL_PHYSICAL_DOTE')),
        ('reject_contract_drift', lambda p: p['scientific_choices']['terrain_evaluation'].update(roundoff_tolerance=.1)),
        ('reject_physical_definition_drift', lambda p: p['scientific_choices']['DOTE'].update(moisture_basis='signed_O')),
        ('reject_seed_drift', lambda p: p['models'][0].update(seed=2030)),
    ):
        candidate = copy.deepcopy(proposal)
        mutation(candidate)
        rejected(name, lambda candidate=candidate: entry.validate_grant(*bind(candidate, private)))
    rejected('missing_real_approval_before_any_dispatch', lambda: entry.gate.bootstrap(
        ROOT / 'NO_PROPOSAL', ROOT / 'NO_PRIVATE', ROOT / 'NO_RESEARCHER_APPROVAL'))
    assert entry.gate.ENTRY_PATH.name == 'start_mountain_pair_evaluation.py'
    assert entry.gate.WORKER_PATH.endswith('mountain_pair_worker.py')
    from tools.research_readiness import start_paired_point_evaluation as legacy
    assert legacy.SCOPE != entry.SCOPE and legacy.TASKS == ('CONTROL_E0', 'CANDIDATE_COSINE9')
    checks['new_entry_worker_hooks_and_legacy_module_isolation'] = True
    assert entry.LIMITS['payload_archive_reference_bytes'] == 2 * 26639253112 + 2 * 312828 + 2 * (53906821 + 53906757)
    assert entry.LIMITS['total_metadata_cap_bytes'] == 3 * 80 * 1024**2 + 2 * 256 * 1024**2
    assert entry.LIMITS['total_source_cap_bytes'] == entry.LIMITS['payload_archive_reference_bytes'] + entry.LIMITS['total_metadata_cap_bytes']
    checks['exact_payload_and_metadata_budget_sums'] = True
    with tempfile.TemporaryDirectory() as name:
        folder = Path(name)
        checkpoint, report_path, tail = [str((folder / f).resolve()) for f in ('weights.pt', 'dev.json', 'tail.json')]
        binding = canonical_task_bindings({'REAL': dict(checkpoint_path=checkpoint, dev_report_path=report_path, tail_report_path=tail)},
                                          {checkpoint: {}}, {report_path: {}, tail: {}})
        assert binding['REAL']['tail_report_path'] == tail
    checks['canonical_tail_metadata_binding_retained'] = True
    from tools.research_readiness import mountain_pair_worker, paired_point_worker
    from yuntapr.experimental.core_innovation.gfs import EnvironmentFrame, Field, ForecastIdentity
    from yuntapr.experimental.core_innovation.grid import GridSpec
    from yuntapr.experimental.research_readiness.static_terrain import StaticPack, B6_CHANNELS, UNITS
    from yuntapr.experimental.research_readiness.dynamic_terrain import DoteDefinition
    from datetime import datetime, timedelta, timezone
    grid = GridSpec(np.linspace(24, 25, 100), np.linspace(100, 101, 100))
    values = np.zeros((6, 100, 100), np.float32)
    values[0], values[1], values[5] = 1500., .1, 1.
    values[0, :, :33], values[0, :, 66:] = 500., 2500.
    terrain = StaticPack(grid, values, np.ones_like(values, bool), np.ones((100, 100), bool), B6_CHANNELS, UNITS, 'a' * 64, 'ARTIFICIAL')
    mask = np.ones((100, 100), bool)
    fields = {axis + str(level): Field(np.full(mask.shape, speed), mask, axis, 'm/s', level * 100.)
              for level in (850, 700) for axis, speed in (('u', 3.), ('v', 2.))}
    fields.update(ps=Field(np.full(mask.shape, 100000.), mask, 'surface_pressure', 'Pa', None),
                  pwat=Field(np.full(mask.shape, 40.), mask, 'precipitable_water', 'kg m-2', None))
    stamp = datetime(2024, 5, 1, 6, tzinfo=timezone.utc)
    frame = EnvironmentFrame(ForecastIdentity(stamp - timedelta(hours=6), timedelta(hours=6), stamp), grid, fields, 'retrospective', ())
    weather = np.full((1, 1, 100, 100), .5, np.float32)
    weather.reshape(-1)[:717] = 25.
    synthetic = (weather, np.ones_like(weather, bool), np.ones_like(weather, bool), np.full(weather.shape, .6),
                 np.broadcast_to(np.log1p(np.arange(1, 33))[None, :, None, None], (1, 32, 100, 100)))
    acc = MountainAccumulator(terrain, ['2024-SYNTHETIC'])
    acc.add(['2024-SYNTHETIC'], *synthetic)
    terrain_report = acc.finish(report(synthetic))
    old_bins = {name: dict(n_valid=g['n_valid'], n_rain=g['n_rain'],
                           brier=g['brier_sum'] / g['n_valid'],
                           conditional_pinball=sum(c['log_pinball_sum'] for c in g['cells']) / g['n_rain'])
                for name, g in terrain_report['elevation_groups'].items()}
    transforms = {}
    with tempfile.TemporaryDirectory() as name:
        folder = Path(name)
        tail = folder / 'tail.json'
        tail.write_text(json.dumps({'elevation_diagnostics': {'bins': old_bins}}), encoding='utf-8')
        def forward_only_stub(root, p, v, task, output, check, **options):
            assert options['include_joint'] is False and options['diagnostics_factory'] is MountainAccumulator
            transforms[task] = options['transform_factory'](terrain, DoteDefinition(40., 'ARTIFICIAL'))(frame)
            (Path(output) / 'terrain_metrics.json').write_text(json.dumps(terrain_report), encoding='utf-8')
            return {'status': 'COMPLETE'}
        with patch.object(paired_point_worker, 'run_task', side_effect=forward_only_stub):
            for task in entry.TASKS:
                p, _ = grant_fixture()
                result = mountain_pair_worker.run_task(ROOT, p, {'tasks': {task: {'tail_report_path': str(tail)}}}, task, folder, lambda: None)
                assert result['saved_elevation_gate'] == 'PASS'
        real_values, real_mask = transforms[entry.TASKS[0]]
        zero_values, zero_mask = transforms[entry.TASKS[1]]
        assert np.any(real_values != 0) and not np.any(zero_values)
        np.testing.assert_array_equal(real_mask, zero_mask)
    checks['worker_real_zero_treatment_and_unchanged_real_masks'] = True
    checks['worker_terrain_hook_and_saved_elevation_gate'] = True
    integration_checks(checks, real, zero)
    result = dict(status='PASS_ARTIFICIAL_CPU_MOUNTAIN_PREPARATION', checks=checks, checks_passed=len(checks),
                  real_source_reads=0, checkpoint_reads=0, real_model_forwards=0, optimizer_updates=0,
                  real_approval_created=False, scientific_status='NOT_VERIFIED')
    with args.receipt.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'checks_passed': len(checks)}))


if __name__ == '__main__':
    main()
