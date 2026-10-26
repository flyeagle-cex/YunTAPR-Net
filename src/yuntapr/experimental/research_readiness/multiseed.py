"""One non-replayable B3/B4 package; reuse the frozen Stage4 engine.

Preparation reads metadata/stat only. No approval is inferred from preparation.
"""
from pathlib import Path
import json
import math
import os
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time

from ..core_innovation.stage3.planning import digest
from ..core_innovation.stage4 import POPULATION_SHA
from ..core_innovation.stage4.data import PopulationPlan, read, sha
from ..core_innovation.stage4.engine import FormalDecision, PairedExecutor, resources, write
from ..core_innovation.stage4.evaluation import paired_difference
from ..core_innovation.stage4.launch import CONFIG, ReaderFactory
from .tail_diagnostics import TailDiagnostics

TASKS = (('B3', 2030), ('B4', 2030), ('B3', 2031), ('B4', 2031))
GIB = 1024**3
BUDGET = dict(models=4, updates_per_model=4320, total_updates=17280,
              source_bytes_per_model=477571641012, total_source_bytes=1910286564048,
              source_files_per_model=142812, max_model_seconds=21600,
              max_package_seconds=86400, replay_allowance=0,
              minimum_free_bytes_per_model=24*GIB, initial_free_bytes=96*GIB)
ENTRY = 'tools/research_readiness/start_multiseed.py'


def code_hashes(root):
    # Bind executable dependencies, not historical experiment/source receipts.
    names = subprocess.check_output(['git', '-C', str(root), 'ls-files',
                                     'src/yuntapr', 'config'], text=True).splitlines()
    names += [ENTRY]
    names += ['src/yuntapr/experimental/research_readiness/multiseed.py']
    return {n: sha(root/n) for n in sorted(set(names))}


def load_inherited(path):
    wrapper = read(path)
    p = wrapper['prepared']
    body = dict(p)
    h = body.pop('preparation_sha256')
    if digest(body) != h or p['config'] != CONFIG:
        raise ValueError('Frozen seed2029 preparation identity changed')
    for role, scope in p['roles'].items():
        year = 2023 if role == 'Train' else 2024
        if (role not in ('Train', 'Development') or digest(scope['files']) != scope['source_manifest_sha256']
                or len(scope['files']) != scope['file_count']
                or sum(f['bytes'] for f in scope['files'].values()) != scope['bytes_per_pass']):
            raise ValueError('Frozen source scope changed')
        for name, item in scope['files'].items():
            expected_year = 2023 if item.get('kind') == 'static_mask' else year
            if item['year'] != expected_year or '2025' in Path(name).parts:
                raise PermissionError('Only frozen 2023/2024 source scopes allowed')
    if (9*sum(s['bytes_per_pass'] for s in p['roles'].values()) != BUDGET['source_bytes_per_model']
            or 9*sum(s['file_count'] for s in p['roles'].values()) != BUDGET['source_files_per_model']):
        raise ValueError('Per-model budget differs from frozen scope')
    return wrapper, p


def prepare(root, inherited_path, output_root):
    """No raw payload opens, normalization refit, checkpoint load or updates."""
    root, inherited_path, output_root = map(Path, (root, inherited_path, output_root))
    wrapper, p = load_inherited(inherited_path)
    if output_root.exists() or not output_root.parent.is_dir():
        raise PermissionError('New output root under an existing researcher-selected parent required')
    plan = PopulationPlan(p['private_inputs']['stage3_run'], p['private_inputs']['request'], root=root)
    if plan.identity != p['data']:
        raise ValueError('Frozen metadata/data identity changed')
    historical = Path(wrapper['historical_b3_run'])
    historical_reports = {k: read(historical/f'{k}_development_09.json') for k in ('B3', 'B4')}
    paired_difference(historical_reports['B3'], historical_reports['B4'])
    if historical_reports['B3']['source_identity'] != p['data']:
        raise ValueError('Historical endpoint population differs')
    files = {}
    for scope in p['roles'].values():
        for name, item in scope['files'].items():
            if name in files and files[name] != item:
                raise ValueError('Conflicting source metadata')
            files[name] = item
    bad = sum(not Path(n).is_file() or Path(n).stat().st_size != f['bytes'] for n, f in files.items())
    if bad:
        raise RuntimeError(f'{bad} missing/size-changed frozen sources; payload not opened')
    admission = resources()
    free = shutil.disk_usage(output_root.parent).free
    if free < BUDGET['initial_free_bytes']:
        raise RuntimeError('Output volume needs >=96GiB free for four retained models')
    roles = {r: {k: s[k] for k in ('file_count', 'bytes_per_pass', 'source_manifest_sha256')}
             for r, s in p['roles'].items()}
    public = dict(status='READY_WAITING_RESEARCHER_AUTHORIZATION', tasks=[dict(model=m, seed=s) for m, s in TASKS],
                  config={k: v for k, v in CONFIG.items() if k not in ('seed', 'models')},
                  data=p['data'], scopes=roles, budget=BUDGET, code_sha256=code_hashes(root),
                  inherited_preparation_sha256=p['preparation_sha256'],
                  historical_endpoint_sha256={f'{k}_development_09.json': sha(historical/f'{k}_development_09.json') for k in ('B3', 'B4')},
                  additive_tail_diagnostics='SAME_DEV_PASS_NO_EXTRA_INFERENCE',
                  resources=dict(admission, output_volume_free_bytes=free,
                                 output_root='PRIVATE_RESEARCHER_SELECTED_NEW_DIRECTORY'),
                  source_metadata=dict(unique_files=len(files), missing_or_size_changed=bad,
                                       check='EXISTENCE_AND_SIZE_ONLY_NOT_PAYLOAD_HASH_REVALIDATION'),
                  raw_payload_opens=0, optimizer_updates=0, checkpoint_loads=0, authorized=False)
    public['proposal_sha256'] = digest(public)
    private = dict(proposal_sha256=public['proposal_sha256'], inherited_path=str(inherited_path.resolve()),
                   inherited_file_sha256=sha(inherited_path), output_root=str(output_root.resolve()),
                   historical_pair=wrapper['historical_b3_run'])
    return public, private


def validate_approval(approval, proposal, private, commit):
    expected = dict(approved_by_researcher=True, proposal_sha256=proposal['proposal_sha256'],
                    code_commit=commit, tasks=[dict(model=m, seed=s) for m, s in TASKS],
                    budget=BUDGET, output_root=private['output_root'])
    if any(approval.get(k) != v for k, v in expected.items()):
        raise PermissionError('Exact researcher approval of this four-model package/code/storage/budget required')
    if not isinstance(approval.get('decision_id'), str) or not approval['decision_id'].strip():
        raise PermissionError('Explicit researcher decision identifier required')


def checked_inputs(root, proposal_path, private_path, approval_path, commit):
    proposal, private, approval = map(read, (proposal_path, private_path, approval_path))
    body = dict(proposal)
    if digest({k: v for k, v in body.items() if k != 'proposal_sha256'}) != proposal['proposal_sha256']:
        raise ValueError('Proposal digest differs')
    validate_approval(approval, proposal, private, commit)
    if private['proposal_sha256'] != proposal['proposal_sha256'] or sha(private['inherited_path']) != private['inherited_file_sha256']:
        raise ValueError('Private preparation changed')
    if code_hashes(root) != proposal['code_sha256']:
        raise ValueError('Reviewed code changed')
    wrapper, p = load_inherited(private['inherited_path'])
    if p['preparation_sha256'] != proposal['inherited_preparation_sha256'] or p['data'] != proposal['data']:
        raise ValueError('Inherited frozen identity changed')
    if any(sha(Path(private['historical_pair'])/name) != h for name,h in proposal['historical_endpoint_sha256'].items()):
        raise ValueError('Historical seed2029 endpoint metadata changed')
    return proposal, private, approval, p


class BatchTail(TailDiagnostics):
    """Same supervision mask; supplementary statistics never feed the loss."""
    def add_batch(self, output, batch):
        valid = (batch.valid & batch.region).detach().cpu().numpy()[:, 0]
        y = batch.rate.detach().cpu().numpy()[:, 0]
        q = output.conditional_quantiles_log.detach().double().cpu().numpy()
        for i, sid in enumerate(batch.ids):
            self.add(sid, y[i], q[i], valid[i])

    def finish_checked(self, report, ids):
        result = self.finish()
        summary = report['groups']['all']['summary']
        n = sum(s['n_rain'] for s in result['strata'])
        covered = sum(s['q32_covered'] for s in result['strata'])
        pin = sum(s['n_rain']*(s['conditional_pinball'] or 0) for s in result['strata'])
        if (tuple(r['sample_id'] for r in self.rows) != tuple(ids) or n != summary['n_rain']
                or not math.isclose(covered/n, summary['coverage'][-1], abs_tol=1e-12)
                or not math.isclose(pin/n, summary['conditional_pinball'], abs_tol=1e-10)):
            raise RuntimeError('Additive tail statistics differ from frozen evaluator')
        return result


def endpoint(folder, kind, seed, commit):
    """Completion is allowed only after all 9 Train/Dev/LAST and 18 read seals."""
    folder = Path(folder)
    db = sqlite3.connect((folder/'updates.sqlite').resolve().as_uri()+'?mode=ro', uri=True)
    try:
        rows = db.execute('SELECT model,state,count(*),min(u),max(u) FROM updates GROUP BY model,state').fetchall()
    finally:
        db.close()
    if rows != [(kind, 'RETURNED', 4320, 1, 4320)]:
        raise RuntimeError('Incomplete/uncertain update ledger')
    total_bytes = total_files = 0
    checkpoints = []
    for e in range(1, 10):
        training = read(folder/f'{kind}_train_{e:02d}.json')
        dev = read(folder/f'{kind}_development_{e:02d}.json')
        receipt = read(folder/f'{kind}_LAST_epoch_{e:02d}.receipt.json')
        checkpoint = folder/f'{kind}_LAST_epoch_{e:02d}.pt'
        if (training['updates'] != 480*e or receipt['model'] != kind or receipt['epoch'] != e
                or receipt['updates'] != 480*e or receipt['code_commit'] != commit
                or receipt['validation_receipt_sha256'] != digest(dev)
                or receipt['population_sha256'] != POPULATION_SHA
                or not checkpoint.is_file() or sha(checkpoint) != receipt['checkpoint_sha256']):
            raise RuntimeError('Train/Dev/checkpoint seal differs')
        read(folder/f'{kind}_tail_{e:02d}.json')
        checkpoints.append(receipt)
        for role in ('train', 'dev'):
            r = read(folder/f'{kind}_{role}_reads_{e:02d}'/'pass_receipt.json')
            a = r['actual_reads']
            if (r['during_failure'] or a['opened_files'] != r['expected_files']
                    or a['delivered_bytes'] != r['expected_bytes']
                    or a['states'] != {'READ_COMPLETE': r['expected_files']}):
                raise RuntimeError('Unsealed/partial source pass')
            total_bytes += a['delivered_bytes']
            total_files += a['opened_files']
    if total_bytes != BUDGET['source_bytes_per_model'] or total_files != BUDGET['source_files_per_model']:
        raise RuntimeError('Source totals differ from exact approved per-model allowance')
    return dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION', model=kind, seed=seed, epochs=9,
                optimizer_updates=4320, logical_source_bytes=total_bytes, logical_source_files=total_files,
                replay=0, code_commit=commit, endpoint='FIXED_EPOCH_9_LAST', checkpoints=checkpoints)


def run_worker(root, proposal_path, private_path, approval_path, commit, index):
    start = time.monotonic()
    proposal, private, approval, p = checked_inputs(root, proposal_path, private_path, approval_path, commit)
    if type(index) is not int or not 0 <= index < 4:
        raise PermissionError('Unlisted task')
    package = Path(private['output_root'])
    binding = read(package/'authorization_binding.json')
    claim = read(package/f'task_{index+1}_claim.json')
    if (binding['approval'] != approval or binding['controller_pid'] != os.getppid()
            or claim != dict(index=index, controller_pid=os.getppid(), code_commit=commit)):
        raise PermissionError('Worker must be started once by the approved live serial controller')
    kind, seed = TASKS[index]
    if os.environ.get('PYTHONHASHSEED') != str(seed):
        raise PermissionError('Worker hash seed must be set before process startup')
    if shutil.disk_usage(package).free < BUDGET['minimum_free_bytes_per_model']:
        raise RuntimeError('Output volume below24GiB; no cleanup or fallback')
    plan = PopulationPlan(p['private_inputs']['stage3_run'], p['private_inputs']['request'], root=root)
    if plan.identity != proposal['data']:
        raise ValueError('Frozen population/statistics changed')
    def deadline():
        if time.monotonic()-start > BUDGET['max_model_seconds']:
            raise RuntimeError('Per-model6h limit reached; no automatic replay')
    decision = FormalDecision(approval['decision_id'], seed, POPULATION_SHA, True, True, True)
    folder = package/f'{kind}_s{seed}'
    factory = ReaderFactory(plan, p, approval['decision_id'])
    PairedExecutor(plan, folder, decision=decision, kinds=(kind,), deadline=deadline,
                   tail_factory=BatchTail, code_commit=commit,
                   pair_reference=package/f'B3_s{seed}' if kind=='B4' else None).run(factory)
    result = endpoint(folder, kind, seed, commit)
    deadline()
    write(folder/'completion.json', result)
    return result


def metric_values(report):
    s = report['groups']['all']['summary']
    return {**{k: s[k] for k in ('brier', 'auroc', 'average_precision', 'conditional_pinball')},
            'q32_coverage': s['coverage'][-1], 'q32_signed_bias': s['coverage'][-1]-.984375,
            'q32_absolute_error': abs(s['coverage'][-1]-.984375)}


def aggregate_pairs(pairs):
    if set(pairs) != {2029, 2030, 2031}:
        raise ValueError('Exactly all three completed independent seeds required')
    result = {}
    for metric in next(iter(pairs.values())):
        values = [pairs[s][metric] for s in (2029, 2030, 2031)]
        result[metric] = dict(B4_minus_B3_by_seed=dict(zip(('2029', '2030', '2031'), values)),
                              mean=statistics.mean(values), sample_sd=statistics.stdev(values),
                              favorable_direction='negative' if metric in ('brier', 'conditional_pinball', 'q32_absolute_error') else
                              'positive_for_undercoverage_only' if metric.startswith('q32') else 'positive')
    return dict(seeds=[2029, 2030, 2031], metrics=result, descriptive_only=True,
                independent_weather_years=1, significance='NOT_CLAIMED')


def run_package(root, proposal_path, private_path, approval_path, commit):
    start = time.monotonic()
    proposal, private, approval, p = checked_inputs(root, proposal_path, private_path, approval_path, commit)
    package = Path(private['output_root'])
    if package.exists():
        raise PermissionError('Approval consumed/output exists; no retry, resume or replay')
    if shutil.disk_usage(package.parent).free < BUDGET['initial_free_bytes']:
        raise RuntimeError('Initial output space below96GiB')
    admission = resources()
    package.mkdir(exist_ok=False)
    write(package/'authorization_binding.json', dict(approval=approval, controller_pid=os.getpid(),
                                                   admission=admission, proposal_sha256=proposal['proposal_sha256']))
    total_updates = total_bytes = 0
    active = None
    try:
        for index, (kind, seed) in enumerate(TASKS):
            remaining = BUDGET['max_package_seconds']-(time.monotonic()-start)
            if remaining <= 0:
                raise RuntimeError('24h package deadline reached')
            write(package/f'task_{index+1}_claim.json', dict(index=index, controller_pid=os.getpid(), code_commit=commit))
            env = dict(os.environ, PYTHONHASHSEED=str(seed), CUBLAS_WORKSPACE_CONFIG=':4096:8',
                       OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONUTF8='1')
            command = [sys.executable, '-B', str(root/ENTRY), 'worker', '--proposal', str(proposal_path),
                       '--private-preparation', str(private_path), '--researcher-approval', str(approval_path),
                       '--task-index', str(index)]
            with (package/f'{kind}_s{seed}_console.log').open('xb') as log:
                active = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    rc = active.wait(timeout=min(BUDGET['max_model_seconds'], remaining))
                except subprocess.TimeoutExpired:
                    active.kill(); active.wait()
                    raise RuntimeError('Hard wall-time limit; worker stopped without replay')
            active = None
            if rc != 0:
                raise RuntimeError(f'{kind} seed{seed} stopped with exit{rc}; dependent tasks NOT_STARTED')
            r = read(package/f'{kind}_s{seed}'/'completion.json')
            if (r['status'] != 'COMPLETE_TRAIN_AND_DEV_EVALUATION' or r['code_commit'] != commit
                    or r['optimizer_updates'] != 4320 or r['logical_source_bytes'] != BUDGET['source_bytes_per_model']):
                raise RuntimeError('Worker completion/budget seal differs')
            total_updates += r['optimizer_updates']; total_bytes += r['logical_source_bytes']
            if kind == 'B4':
                a, b = (package/f'{k}_s{seed}' for k in ('B3', 'B4'))
                for name in ('paired_initial_identity.json', 'paired_orders.json'):
                    if read(a/name) != read(b/name):
                        raise RuntimeError('Within-seed initialization or sample order differs')
                write(package/f'paired_difference_s{seed}.json', paired_difference(
                    read(a/'B3_development_09.json'), read(b/'B4_development_09.json')))
        if total_updates != BUDGET['total_updates'] or total_bytes != BUDGET['total_source_bytes']:
            raise RuntimeError('Package exact budget closure differs')
        pairs = {}
        endpoints = {}
        for seed in (2029, 2030, 2031):
            base = Path(private['historical_pair']) if seed == 2029 else package
            reports = {kind: read((base if seed == 2029 else base/f'{kind}_s{seed}')/f'{kind}_development_09.json') for kind in ('B3', 'B4')}
            paired_difference(reports['B3'], reports['B4'])
            endpoints[str(seed)] = {k: metric_values(r) for k, r in reports.items()}
            pairs[seed] = {k: endpoints[str(seed)]['B4'][k]-endpoints[str(seed)]['B3'][k]
                           for k in endpoints[str(seed)]['B3']}
        summary = aggregate_pairs(pairs)
        write(package/'three_seed_summary.json', dict(**summary, endpoints=endpoints))
        if time.monotonic()-start > BUDGET['max_package_seconds']:
            raise RuntimeError('24h limit exceeded at closure')
        result = dict(status='COMPLETE_FOUR_MODELS_THREE_SEED_SUMMARY', optimizer_updates=total_updates,
                      logical_source_bytes=total_bytes, replay=0, code_commit=commit)
        write(package/'completion.json', result)
        return result
    except BaseException as exc:
        if active is not None and active.poll() is None:
            active.kill(); active.wait()
        write(package/'failure.json', dict(status='STOP_NO_AUTOMATIC_RETRY',
              error=type(exc).__name__+': '+str(exc), completed_updates=total_updates,
              completed_source_bytes=total_bytes,
              partial_task_counters='SEE_PRESERVED_TASK_LEDGERS; NOT_COUNTED_AS_ZERO'))
        raise
