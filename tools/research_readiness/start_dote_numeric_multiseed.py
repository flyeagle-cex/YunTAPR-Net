"""Only ZERO_DOTE/2030 then2031; reuse the proven numeric transform/Stage4.

This controller grants nothing. An exact new researcher decision, clean frozen
checkout and independent WMI host are required before resources or source I/O.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.dont_write_bytecode = True
TASKS = [dict(model='B7_ZERO_DOTE', seed=s) for s in (2030, 2031)]
SINGLE = 'docs/research_readiness/20261025/evidence/dote_control_proposal_20261029.json'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def choices(original):
    c = copy.deepcopy(original['scientific_choices'])
    c['initialization'].update(B6='FRESH_MATCHING_TASK_SEED_NOT_E9_FINETUNING', auxiliary_seed='MAIN_SEED_PLUS_20000',
                               static_auxiliary_seed='MAIN_SEED_PLUS_10000')
    c['numeric_control'].update(seed='PER_TASK_2030_2031', baseline='EXISTING_REAL_B7_MATCHING_SEED_FIXED_E9')
    return c


def budget(prepared):
    weather = 9 * sum(s['bytes_per_pass'] for s in prepared['roles'].values())
    files = 9 * sum(s['file_count'] for s in prepared['roles'].values())
    return dict(models=2, updates_per_model=4320, total_updates=8640,
                weather_source_bytes_per_model=weather, weather_source_files_per_model=files,
                static_source_bytes_per_model={'B7': 312828}, static_source_files_per_model=1,
                total_source_bytes_per_model={'B7': weather + 312828}, source_files_per_model=files + 1,
                total_source_bytes=2 * (weather + 312828), total_source_files=2 * (files + 1),
                dynamic_extra_raw_source_bytes=0, dynamic_formal_cache_reads=0, normalization_refits=0,
                startup_source_metadata_checks=1, startup_source_payload_bytes=0, startup_metadata_seconds_cap=15,
                max_model_seconds=21600, max_package_seconds=43200, replay_allowance=0, additional_retry_allowance=0,
                initial_free_bytes=48 * 1024**3, minimum_task_free_bytes=24 * 1024**3)


def training_configs(original):
    return {f'B7_ZERO_DOTE_s{seed}': dict(config=dict(original['protocol'],seed=seed),
            engine_model='B7',static_auxiliary_seed=seed+10000,fusion_auxiliary_seed=seed+20000)
            for seed in (2030,2031)}


def validate(a, p, v, commit):
    expected = dict(code_commit=commit, proposal_sha256=p['proposal_sha256'], tasks=TASKS,
                    scientific_choices=p['scientific_choices'], budget=p['budget'], output_root=v['output_root'])
    if a.get('approved_by_researcher') is not True or not isinstance(a.get('decision_id'), str) or not a['decision_id'].strip():
        raise PermissionError('New exact two-control researcher approval required; no old grant reuse')
    if p['execution_code_commit'] != commit or p['tasks'] != TASKS or any(a.get(k) != x for k, x in expected.items()):
        raise PermissionError('Only the exact2030 then2031 control package, code, science, budget and output')
    if a.get('approved_replay_updates') != 0 or p['budget']['replay_allowance'] != 0 or p['budget']['additional_retry_allowance'] != 0:
        raise PermissionError('No replay or retry authorized')
    if digest({k: x for k, x in p.items() if k != 'proposal_sha256'}) != p['proposal_sha256'] or v['proposal_sha256'] != p['proposal_sha256']:
        raise ValueError('Proposal content changed')
    if digest({k: x for k, x in v.items() if k != 'proposal_sha256'}) != p['private_locator_sha256']:
        raise ValueError('Private scope changed')


def checked(p, v, a, commit):
    validate(a, p, v, commit)  # Before torch, resource admission, source or output.
    if subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True).strip():
        raise PermissionError('Clean approved execution checkout required')
    for name, sha in p['code_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha:
            raise ValueError('Approved code changed: ' + name)
    for name, sha in p['inherited_evidence_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha:
            raise ValueError('Inherited evidence identity changed: ' + name)
    original = load(ROOT / SINGLE)
    if original['proposal_sha256'] != p['inherited_zero_protocol_sha256'] or choices(original) != p['scientific_choices']:
        raise ValueError('Frozen zero-control scientific definition changed')
    if training_configs(original) != p['training_configs']:
        raise ValueError('Frozen per-seed training configuration changed')
    from yuntapr.experimental.research_readiness.multiseed import load_inherited
    _, prepared = load_inherited(v['inherited'])
    if prepared['data'] != p['data'] or budget(prepared) != p['budget']:
        raise ValueError('Frozen population/source budget changed')
    for role, scope in p['source_scope_summary'].items():
        if prepared['roles'][role]['source_manifest_sha256'] != scope['source_manifest_sha256']:
            raise ValueError('Source population changed')
    for seed in (2030, 2031):
        for name, sha in p['baseline_metadata_sha256'][str(seed)].items():
            if hashlib.sha256((Path(v['real_B7'][str(seed)]) / name).read_bytes()).hexdigest() != sha:
                raise ValueError('Matching real B7 initialization/order changed')
    return prepared


def run_child(command, environment, log, timeout):
    from yuntapr.experimental.research_readiness.multiseed import worker_creation_flags
    with Path(log).open('xb') as f:
        child = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=f, stderr=subprocess.STDOUT,
                                 creationflags=worker_creation_flags())
        try:
            code = child.wait(timeout=timeout)
        except BaseException:
            if child.poll() is None:
                child.kill()
                child.wait()
            raise
    if code:
        raise RuntimeError('Control worker failed; all later tasks blocked, no retry')


def dispatch(p, v, a, commit, argv, started, invoke=run_child):
    """One serial pass; each task has fresh claim/output and a six-hour cap."""
    out = Path(v['output_root'])
    totals = [0, 0, 0]
    try:
        for index, task in enumerate(TASKS):
            remaining = p['budget']['max_package_seconds'] - (time.monotonic() - started)
            if remaining <= 0:
                raise RuntimeError('Twelve-hour package cap; no retry')
            seed = task['seed']
            claim = dict(index=index, seed=seed, controller_pid=os.getpid(), code_commit=commit, started_monotonic=time.monotonic())
            write(out / f'task_{index + 1}_claim.json', claim)
            env = dict(os.environ, PYTHONHASHSEED=str(seed), PYTHONUTF8='1', CUBLAS_WORKSPACE_CONFIG=':4096:8', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
            command = [sys.executable, '-B', str(Path(__file__).resolve()), 'worker', *argv, '--task-index', str(index)]
            invoke(command, env, out / f'B7_ZERO_DOTE_s{seed}_console.log', min(remaining, p['budget']['max_model_seconds']))
            result = load(out / f'B7_ZERO_DOTE_s{seed}_complete.json')
            if (result['status'], result['model'], result['control_id'], result['seed'], result['optimizer_updates'], result['code_commit'], result['endpoint'], result['replay']) != (
                'COMPLETE_TRAIN_AND_DEV_EVALUATION', 'B7', 'B7_ZERO_DOTE', seed, 4320, commit, 'FIXED_EPOCH_9_LAST', 0):
                raise RuntimeError('Control endpoint/identity differs')
            if (result['total_logical_source_bytes'], result['total_logical_source_files']) != (p['budget']['total_source_bytes_per_model']['B7'], p['budget']['source_files_per_model']):
                raise RuntimeError('Task source closure differs')
            totals = [x + y for x, y in zip(totals, (4320, result['total_logical_source_bytes'], result['total_logical_source_files']))]
        if totals != [p['budget']['total_updates'], p['budget']['total_source_bytes'], p['budget']['total_source_files']]:
            raise RuntimeError('Exact two-model budget closure differs')
        return totals
    except BaseException as exc:
        write(out / 'failure.json', dict(status='STOP_NO_AUTOMATIC_RETRY_OR_REPLAY', error=type(exc).__name__ + ': ' + str(exc),
                                       completed_task_updates=totals[0], completed_task_source_bytes=totals[1],
                                       partial_counts='SEE_PRESERVED_LEDGERS_INCLUDING_FAILED_TASK_NOT_ZERO'))
        raise


def summarize(out, p):
    """Saved statistics only; real-minus-zero, all three seeds, no inference."""
    from yuntapr.experimental.research_readiness.multiseed import metric_values
    real = load(ROOT / p['real_B7_completion_evidence'])
    old = load(ROOT / p['seed2029_control_completion_evidence'])
    groups = {'2029': old['endpoint_groups']}
    tails = {'2029': old['tail_diagnostics']}
    for seed in (2030, 2031):
        dev = load(out / f'B7_s{seed}/B7_development_09.json')
        groups[str(seed)] = {'B7': real['endpoint_groups'][str(seed)]['B7'], 'B7_ZERO_DOTE': {
            g: dict(summary=x['summary'], ids_sha256=x['ids_sha']) for g, x in dev['groups'].items()}}
        tail = load(out / f'B7_s{seed}/B7_tail_09.json')
        tails[str(seed)] = {'B7': real['tail_diagnostics'][str(seed)]['B7'], 'B7_ZERO_DOTE': {
            k: tail[k] for k in ('strata', 'elevation_diagnostics')}}
    endpoints, comparisons = {}, {}
    for seed, arms in groups.items():
        endpoints[seed] = {}
        for group, a in arms['B7'].items():
            b = arms['B7_ZERO_DOTE'][group]
            if a['ids_sha256'] != b['ids_sha256']:
                raise ValueError('Matched evaluation population differs')
            vals = {k: metric_values({'groups': {'all': arms[k][group]}}) for k in arms}
            endpoints[seed][group] = vals
            for metric in vals['B7']:
                delta = vals['B7'][metric] - vals['B7_ZERO_DOTE'][metric]
                comparisons.setdefault(group, {}).setdefault(metric, {})[seed] = delta
    def aggregate(metric, ds):
        direction = 'LOWER' if metric in ('brier', 'conditional_pinball', 'q32_absolute_error') else 'HIGHER' if metric in ('auroc', 'average_precision') else 'SEE_ABSOLUTE_ERROR_TO_NOMINAL'
        improves = sum(x < 0 for x in ds.values()) if direction == 'LOWER' else sum(x > 0 for x in ds.values()) if direction == 'HIGHER' else None
        return dict(by_seed=ds, mean=statistics.mean(ds.values()), sample_sd=statistics.stdev(ds.values()), improvement_direction=direction,
                    improvement_seeds=improves, negative_seeds=sum(x<0 for x in ds.values()), positive_seeds=sum(x>0 for x in ds.values()),
                    zero_seeds=sum(x==0 for x in ds.values()), direction_consistent=all(x<0 for x in ds.values()) or all(x>0 for x in ds.values()) or all(x==0 for x in ds.values()))
    layers = {}
    for section in ('strata', 'elevation'):
        ds = {}
        for seed, arms in tails.items():
            a, b = arms['B7'], arms['B7_ZERO_DOTE']
            a = a['strata'] if section == 'strata' else a['elevation_diagnostics']['bins']
            b = b['strata'] if section == 'strata' else b['elevation_diagnostics']['bins']
            for key in (range(len(a)) if section == 'strata' else a):
                if a[key]['n_rain'] != b[key]['n_rain']:
                    raise ValueError('Tail population changed')
                for metric in ('brier', 'conditional_pinball', 'q32_coverage'):
                    if metric in a[key]:
                        ds.setdefault(str(key), {}).setdefault(metric, {})[seed] = a[key][metric] - b[key][metric]
        layers[section] = {k: {m: aggregate(m, x) for m, x in ms.items()} for k, ms in ds.items()}
    group_summary = {g: {m: aggregate(m, x) for m, x in ms.items()} for g, ms in comparisons.items()}
    for group, ms in group_summary.items():
        for metric in ('q32_coverage', 'q32_signed_bias'):
            ms[metric]['improvement_direction']='CLOSER_TO_NOMINAL_0.984375_SEE_ABSOLUTE_ERROR'
            ms[metric]['improvement_seeds']=ms['q32_absolute_error']['improvement_seeds']
    write(out / 'three_seed_dote_control_summary.json', dict(seeds=[2029, 2030, 2031], difference='B7_REAL_MINUS_B7_ZERO_DOTE',
          group_endpoints=endpoints, groups=group_summary,
          tail_endpoints=tails, tail_comparisons=layers, descriptive_only=True, independent_weather_years=1, significance='NOT_CLAIMED',
          limitations=['128 zero-input weights lack loss gradients; nominal capacity is not effective capacity',
                       'Real validity masks retained; deterministic features are not new observations',
                       'Adjacent seed+epoch-1 orders overlap', 'Pixels are not independent storms',
                       'Outcome-conditioned rain-stratum coverage has no per-stratum nominal target', 'No causal uplift or final-year claim']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('execute', 'worker'))
    for flag in ('proposal', 'private-preparation', 'researcher-approval'):
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--task-index', type=int)
    args = parser.parse_args()
    p, v, a = map(load, (args.proposal, args.private_preparation, args.researcher_approval))
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    prepared = checked(p, v, a, commit)
    import start_independent_process as host
    host.require_independent(host.host_identity())
    from yuntapr.experimental.research_readiness.dynamic_training import run_task
    from yuntapr.experimental.research_readiness.dote_numeric_control import ZeroNumericDote
    from yuntapr.experimental.research_readiness.dynamic_multiseed import admit_source
    from yuntapr.experimental.core_innovation.stage4.engine import resources
    out = Path(v['output_root'])
    if args.mode == 'worker':
        if type(args.task_index) != int or args.task_index not in (0, 1):
            raise PermissionError('Only the two new seed indices')
        seed = TASKS[args.task_index]['seed']
        binding, claim = load(out / 'authorization_binding.json'), load(out / f'task_{args.task_index + 1}_claim.json')
        if binding['controller_pid'] != os.getppid() or binding['approval'] != a or claim['controller_pid'] != os.getppid() or claim['seed'] != seed or claim['index'] != args.task_index or claim['code_commit'] != commit:
            raise PermissionError('Live once-only parent binding required')
        result = run_task(ROOT, p, v, a, prepared, commit, 'B7', seed, started=claim['started_monotonic'],
                          pair_reference=Path(v['real_B7'][str(seed)]), static_name=f'B7_ZERO_DOTE_s{seed}_static_source.sqlite',
                          dynamic_transform_factory=ZeroNumericDote)
        write(out / f'B7_ZERO_DOTE_s{seed}_complete.json', dict(result, control_id='B7_ZERO_DOTE'))
        return
    started = time.monotonic()
    if out.exists():
        raise PermissionError('Consumed output; no restart, overwrite or replay')
    if shutil.disk_usage(out.parent).free < p['budget']['initial_free_bytes']:
        raise RuntimeError('Need48GiB; never delete history')
    admission = resources()
    out.mkdir(exist_ok=False)
    write(out / 'authorization_binding.json', dict(approval=a, controller_pid=os.getpid(), admission=admission, control='ZERO_NUMERIC_RETAIN_REAL_MASKS_TWO_SEEDS'))
    try:
        admit_source(prepared, out)
        argv = [x for flag in ('proposal', 'private-preparation', 'researcher-approval') for x in ('--' + flag, str(getattr(args, flag.replace('-', '_')).resolve()))]
        totals = dispatch(p, v, a, commit, argv, started)
        summarize(out, p)
        if time.monotonic() - started > p['budget']['max_package_seconds']:
            raise RuntimeError('Twelve-hour closure cap')
        write(out / 'completion.json', dict(status='COMPLETE_TWO_CONTROLS_THREE_SEED_DOTE_SUMMARY', updates=totals[0], logical_source_bytes=totals[1],
              logical_source_files=totals[2], code_commit=commit, proposal_sha256=p['proposal_sha256'], replay=0))
    except BaseException as exc:
        if not (out / 'failure.json').exists():
            write(out / 'failure.json', dict(status='STOP_NO_AUTOMATIC_RETRY_OR_REPLAY', error=type(exc).__name__ + ': ' + str(exc), partial_counts='SEE_PRESERVED_LEDGERS_NOT_ZERO'))
        raise


if __name__ == '__main__':
    main()
