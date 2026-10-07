"""Version-isolated paired Phase-A runner. Scientific approval is not execution authority."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import gc
import json
import math
import os
import re
import subprocess
import time
import traceback
import torch
from torch.utils.data import DataLoader
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.data import dataset_b1 as data
from yuntapr.data.staging import BoundedEnglishStaging
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.models.quantile_v2.models import B0MatchedV2, B1V2
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.phase_a_protocol import (seed_reproducibility, state_digest, parameter_groups,
    capture_rng, epoch_permutation, lr_for_update, ValidationSelection)
from .phase_a_audit_v2 import (digest, identity, read_json, atomic_json, append_event,
    Counters, SourceFirewall, source_key, reconcile_io)
from .checkpoint_v2 import ROOTS, STEPS, CheckpointStore, make_payload, apply_verified, tree_finite
from .phase_a_validation_v2 import LogDomainValidation
from .upper_tail_v2 import UpperTailDiagnostics

BASELINE = 'd049f7ab7b8a382f47a5fe54384ea9416a22cde9'
PROTOCOL = 'config/science_v2/phase_a_protocol_frozen_v1.json'
PROTOCOL_SHA = 'a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be'
HEAD = 'config/science_v2/quantile_head_v2_frozen_v1.json'
HEAD_SHA = '3a865a6e4ab180f61d7ab6e2f684ab6b814bfe6b2e59a34d127ddf1d772fc97e'
KINDS = {'B0_MATCHED_V2': 'B0_MATCHED', 'B1_V2': 'B1'}
FACTORIES = {'B0_MATCHED_V2': B0MatchedV2, 'B1_V2': B1V2}


def run_id():
    return datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ')


def git(*args, root=REPO_ROOT):
    return subprocess.check_output(['git', '-c', 'core.longpaths=true', *args], cwd=root).decode('utf-8').strip()


def code_identity(root=REPO_ROOT):
    paths = list((root / 'src/yuntapr').rglob('*.py'))
    paths += list((root / 'scripts/paired_phase_a_v2').glob('*'))
    paths += [root / 'scripts/run_paired_phase_a_v2.py']
    paths += list((root / 'tests/formal_phase_a_v2').glob('*.py'))
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(paths) if p.is_file()}


def assert_environment():
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError('CUDA BF16 required; no CPU/precision fallback')
    if not torch.are_deterministic_algorithms_enabled() or torch.backends.cudnn.benchmark or torch.backends.cuda.matmul.allow_tf32 or torch.backends.cudnn.allow_tf32:
        raise RuntimeError('Frozen determinism/TF32 settings failed')


@dataclass
class Contract:
    protocol: dict
    records: dict
    frames: dict
    code: dict
    root: Path

    @classmethod
    def load(cls, root=REPO_ROOT):
        root = Path(root)
        if digest(root / PROTOCOL) != PROTOCOL_SHA or digest(root / HEAD) != HEAD_SHA:
            raise ValueError('Scientific Freeze v2 bytes changed')
        protocol = read_json(root / PROTOCOL)
        for name, ref in protocol['identity'].items():
            if name == 'yunnan_mask': continue  # static payload checked only in an authorized I/O scope
            p = Path(ref['path']); p = p if p.is_absolute() else root / p
            if digest(p) != ref['sha256']: raise ValueError('Frozen identity changed: ' + name)
        records = {(kind, year): data.load_records(old, year, root) for kind, old in KINDS.items() for year in (2023, 2024)}
        keys = ('sample_id', 'window_start', 'analysis_time', 'imerg_day_path', 'imerg_index', 'imerg_sha256', 'target_valid_yunnan_cells')
        for year in (2023, 2024):
            a, b = records['B0_MATCHED_V2', year], records['B1_V2', year]
            if [[r[k] for k in keys] for r in a] != [[r[k] for k in keys] for r in b]:
                raise ValueError('Paired sample/target identities differ')
            if any(x['expected_nominal'] != y['slot_5_nominal'] for x, y in zip(a, b)):
                raise ValueError('Latest slot differs')
        frames = data.load_frames(root)
        for rows in records.values():
            for row in rows:
                times = [row[f'slot_{i}_nominal'] for i in range(6)] if 'slot_0_nominal' in row else [row['expected_nominal']]
                for nominal in times: data.check_frame(frames[nominal], row['analysis_time'])
        return cls(protocol, records, frames, code_identity(root), root)

    def sources(self):
        sources = {}
        def add(path, sha, year, month, size=None):
            p = str(Path(path).resolve()); item = {'sha256': sha, 'year': year, 'month': month, 'expected_bytes': size}
            if p in sources and sources[p] != item: raise ValueError('Conflicting frozen source identities')
            sources[p] = item
        for year in (2023, 2024):
            for row in self.records['B1_V2', year]:
                t = data.allowed_time(row['window_start'])
                p = data.guard_source(row['imerg_day_path'], 'IMERG')
                add(p, row['imerg_sha256'], year, t.month)
                for i in range(6):
                    fr = self.frames[row[f'slot_{i}_nominal']]
                    t = data.allowed_time(fr['nominal'])
                    p = data.guard_source(data.H_ROOT / fr['relative_path'], 'B13')
                    add(p, fr['source_sha256'], year, t.month, int(fr['source_bytes']))
        return sources

    def unchanged(self):
        if digest(self.root / PROTOCOL) != PROTOCOL_SHA or digest(self.root / HEAD) != HEAD_SHA or code_identity(self.root) != self.code:
            raise ValueError('Execution code or config changed during run')


def paired_initialization(contract):
    numerics = CandidateNumerics(epsilon_w=1e-4, epsilon_span=1e-4)
    seed_reproducibility(); anchor = B0MatchedV2(numerics=numerics, root=contract.root)
    seed_reproducibility(); temporal = B1V2(numerics=numerics, root=contract.root)
    a, b = anchor.state_dict(), temporal.state_dict()
    if a.keys() != b.keys(): raise ValueError('Unapproved parameter names')
    different = {n for n in a if a[n].shape != b[n].shape}
    if different != {'backbone.enc0.conv1.weight', 'backbone.enc0.skip.weight'}:
        raise ValueError('Unapproved input differences')
    before = {n: state_digest(b[n]) for n in different}
    with torch.no_grad():
        for n in a:
            if n not in different:
                if a[n].dtype != b[n].dtype: raise ValueError('Paired dtype mismatch')
                b[n].copy_(a[n])
    if before != {n: state_digest(b[n]) for n in different} or not all(torch.equal(a[n], b[n]) for n in a if n not in different):
        raise ValueError('Paired initialization mismatch')
    models = {'B0_MATCHED_V2': anchor, 'B1_V2': temporal}
    counts = {k: parameter_groups(m, check_counts=False)[1]['counts'] for k, m in models.items()}
    if counts != contract.protocol['architecture']['parameters']: raise ValueError('V2 parameter counts changed')
    proof = {'seed': 2026, 'independent_reseed': True, 'native_b1_input_sha256': before,
             'shared_tensor_sha256': {n: state_digest(a[n]) for n in a if n not in different},
             'models': {k: state_digest(m.state_dict()) for k, m in models.items()}, 'parameter_counts': counts,
             'post_pair_rng_sha256': state_digest(capture_rng()),
             'historical_checkpoint_loaded': False, 'native_zero_skip_preserved': bool((b['backbone.enc0.skip.weight'] == 0).all())}
    return models, proof


def optimizer_for(model, kind, contract):
    groups, evidence = parameter_groups(model, check_counts=False)
    if evidence['counts'] != contract.protocol['architecture']['parameters'][kind]:
        raise ValueError('Optimizer grouping count mismatch')
    optimizer = torch.optim.AdamW(groups, lr=1e-4, betas=(.9, .999), eps=1e-8,
        amsgrad=False, maximize=False, capturable=False, differentiable=False, foreach=False, fused=False)
    return optimizer, evidence


def forward_loss(model, batch, counters, phase):
    counters.FORWARD_CALLS += 1
    if phase == 'TRAIN': counters.TRAIN_FORWARDS += 1
    elif phase == 'VALIDATION': counters.VALIDATION_FORWARDS += 1
    else: raise ValueError('Invalid phase')
    with torch.autocast(batch.x_b13.device.type, dtype=torch.bfloat16):
        out = model(batch.x_b13, batch.b13_valid_mask)
        loss = b0_core_loss(out, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask,
                           focal_alpha=.5, focal_gamma=2., quantile_axis_reduction='mean')
    if loss.batch_skipped or loss.valid_supervised_count != len(batch.sample_ids) * 3430 or not torch.isfinite(loss.total):
        raise FloatingPointError('Loss/denominator invariant failed; no batch skip')
    if not torch.isfinite(out.rain_prob).all() or not ((out.rain_prob >= 0) & (out.rain_prob <= 1)).all():
        raise FloatingPointError('Occurrence support failed')
    return out, loss


def update(model, optimizer, batch, u, counters, observer=None, journal=None):
    optimizer.zero_grad(set_to_none=True)
    lr = lr_for_update(u, steps_per_epoch=STEPS)
    for group in optimizer.param_groups: group['lr'] = lr
    if journal: append_event(journal, 'FORWARD_START', update=u, sample_ids=batch.sample_ids)
    out, loss = forward_loss(model, batch, counters, 'TRAIN')
    observation = observer.observe(out.conditional_quantiles_log, batch.sample_ids) if observer else None
    counters.BACKWARD_CALLS += 1
    if journal: append_event(journal, 'BACKWARD_CALL', update=u)
    loss.total.backward()
    if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):
        raise FloatingPointError('V2_GRADIENT_NONFINITE_OR_MISSING')
    pre = torch.nn.utils.clip_grad_norm_(model.parameters(), 5., error_if_nonfinite=True)
    post = torch.sqrt(sum(p.grad.detach().double().square().sum() for p in model.parameters()))
    if not torch.isfinite(post) or post > 5.00001: raise FloatingPointError('Gradient clipping invariant')
    counters.OPTIMIZER_STEP_ATTEMPTS += 1
    if journal: append_event(journal, 'OPTIMIZER_STEP_ATTEMPT', update=u)
    from paired_phase_a_v2.execution_ops import optimizer_step
    optimizer_step(optimizer, counters.scope)
    counters.OPTIMIZER_STEPS += 1
    if not tree_finite(model.state_dict()) or not tree_finite(optimizer.state_dict()):
        raise FloatingPointError('V2_POST_STEP_NONFINITE')
    result = {'update': u, 'LR': lr, 'loss': float(loss.total.detach()),
              'L_occ': float(loss.occurrence.detach()), 'L_qr': float(loss.conditional_quantile.detach()),
              'actual_denominator': loss.valid_supervised_count,
              'pre_clip_norm': float(pre), 'post_clip_norm': float(post), 'clipped': bool(pre > 5),
              'sample_ids': batch.sample_ids, 'indices': batch.indices}
    if journal: append_event(journal, 'OPTIMIZER_STEP_COMPLETED', **result)
    return result, observation


class VerifiedStaging(BoundedEnglishStaging):
    def __init__(self, root, firewall):
        super().__init__(root, 734003200, True, True); self.firewall = firewall

    @contextmanager
    def local(self, source):
        self.firewall.check(source)
        with super().local(source) as local:
            self.firewall.register_copy(local, source)
            try: yield local
            finally: self.firewall.active_staging.pop(source_key(local), None)


class GuardedDataset(data.TemporalDataset):
    def __init__(self, *args, sources, io_root, **kwargs):
        super().__init__(*args, **kwargs)
        self.sources, self.io_root = sources, str(io_root)
        self.firewall_context = None

    def set_worker(self, suffix):
        firewall = SourceFirewall(self.sources, Path(self.io_root) / f'raw_access_worker_{os.getpid()}.jsonl')
        self.firewall_context = firewall.installed(); self.firewall_context.__enter__()
        self.staging = VerifiedStaging(self.stage_base / suffix, firewall)


def datasets(contract, kind, stage, io_root, sources):
    mapping = load_sp04(contract.root)
    ref = contract.protocol['identity']['yunnan_mask']
    mask = read_frozen_yunnan_mask(Path(ref['path']), mapping)
    return {y: GuardedDataset(KINDS[kind], contract.records[kind, y], contract.frames, mapping, mask,
                             stage / str(y), root=contract.root, sources=sources, io_root=io_root) for y in (2023, 2024)}, mask


@contextmanager
def loader_items(loader):
    iterator = iter(loader)
    try: yield iterator
    finally:
        if hasattr(iterator, '_shutdown_workers'): iterator._shutdown_workers()


def loader(dataset, *, order=None, validation=False):
    kwargs = dict(num_workers=2, pin_memory=False, persistent_workers=False, prefetch_factor=1,
                  worker_init_fn=data.worker_init, collate_fn=data.collate)
    if validation: return DataLoader(dataset, batch_size=8, shuffle=False, drop_last=False, **kwargs)
    return DataLoader(dataset, batch_sampler=[order[i:i+2] for i in range(0, len(order), 2)], **kwargs)


def authorize(path, expected_sha, contract, *, resume=False):
    p = Path(path).resolve()
    if p.suffix != '.json' or SourceFirewall.is_raw(p) or 'formal_training' in p.parts:
        raise PermissionError('Repository authorization JSON required before source/model access')
    if digest(p) != expected_sha: raise PermissionError('Authorization SHA mismatch')
    value = read_json(p)
    required = {'scope': 'FORMAL_PAIRED_PHASE_A_V2', 'FORMAL_TRAINING_AUTHORIZED': True,
                'V2_PHASE_A_AUTHORIZED': True, 'V2_PHASE_B_AUTHORIZED': False,
                '2025_RAW_ACCESS': False, 'protocol_sha256': PROTOCOL_SHA, 'head_sha256': HEAD_SHA,
                'code_sha256': contract.code, 'normalization_sha256': data.SCALER_SHA,
                'checkpoint_roots': {k: str(v) for k, v in ROOTS.items()}, 'models': list(KINDS)}
    if any(value.get(k) != v for k, v in required.items()) or not value.get('researcher_approval_reference'):
        raise PermissionError('Separate v2 model-specific formal execution approval required')
    if git('status', '--porcelain', '--untracked-files=normal'):
        raise PermissionError('Formal execution requires a clean dedicated checkout')
    publication_repo = Path(value['publication_repository']).resolve()
    if not p.is_relative_to(publication_repo) or git('rev-parse', '--show-toplevel', root=publication_repo).replace('\\','/').casefold() != str(publication_repo).replace('\\','/').casefold():
        raise PermissionError('Authorization must belong to the designated publication repository')
    if value.get('execution_commit') != git('rev-parse', 'HEAD'):
        raise PermissionError('Execution checkout must be pinned to the approved implementation commit')
    subprocess.run(['git', 'merge-base', '--is-ancestor', BASELINE, value['execution_commit']], cwd=contract.root, check=True)
    for kind in KINDS:
        if not re.fullmatch(r'run_\d{8}T\d{6}_\d{6}Z', value.get('run_ids', {}).get(kind, '')):
            raise ValueError('Unique UTC formal run IDs required')
    gate_path = Path(value['preflight_path']).resolve()
    if not gate_path.is_relative_to(publication_repo) or digest(gate_path) != value['preflight_sha256']:
        raise PermissionError('Preflight identity mismatch')
    gate = read_json(gate_path)
    if gate.get('status') != 'PASS' or gate.get('code_sha256') != contract.code or gate.get('FORMAL_OPTIMIZER_STEPS') != 0 or gate.get('2025_RAW_ACCESS') != 0:
        raise PermissionError('Preflight not complete or does not bind current code')
    if not gate.get('all_regression_tests_passed') or not gate.get('new_runner_tests_passed'):
        raise PermissionError('Required tests missing')
    if resume and (value.get('resume_authorized') is not True or not value.get('resume_LAST_sha256')):
        raise PermissionError('Explicit LAST-bound recovery authorization required')
    if resume:
        origin_path = Path(value['origin_authorization_path']).resolve()
        if not origin_path.is_relative_to(publication_repo) or digest(origin_path) != value['origin_authorization_sha256']:
            raise PermissionError('Resume origin approval SHA mismatch')
        origin = read_json(origin_path)
        for key in required:
            if origin.get(key) != value.get(key): raise PermissionError('Resume changed frozen authority: ' + key)
        if origin.get('run_ids') != value['run_ids'] or origin.get('pair_id') != value['pair_id']:
            raise PermissionError('Resume changed run ancestry')
    else:
        value['origin_authorization_sha256'] = expected_sha
    return value, gate


def progress(public, **values):
    path = Path(public) / 'progress.json'
    prior = read_json(path) if path.exists() else {}
    atomic_json(path, {**prior, 'pid': os.getpid(), 'updated_ns': time.time_ns(), **values})


def epoch_audit(payload, ref):
    t, v = payload['training'], payload['validation']
    if t['steps'] != STEPS or t['scenes'] != 10455 or t['N_valid'] != 35860650 or not t['exactly_once']:
        raise ValueError('Epoch training audit failed')
    if v['scenes'] != 10501 or v['forwards'] != 1313 or v['N_valid'] != 36018430:
        raise ValueError('Epoch validation audit failed')
    if payload['diagnostics']['TRAIN']['forwards'] != STEPS or payload['diagnostics']['VALIDATION']['forwards'] != 1313:
        raise ValueError('Diagnostic coverage failed')
    return {'status': 'PASS', 'completed_epoch': payload['completed_epoch'], 'checkpoint_sha256': ref['sha256'],
            '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0}


def train_one(kind, contract, auth, gate, pair_public, *, resume=False):
    """Called only after authorize(); never invoked by engineering preflight."""
    rid = auth['run_ids'][kind]; local = ROOTS[kind] / rid
    public = Path(pair_public) / kind
    if not resume and (public.exists() or local.exists()): raise FileExistsError('Formal output already exists')
    public.mkdir(parents=True, exist_ok=resume); local.mkdir(parents=True, exist_ok=resume)
    attempt = local / 'audit' / run_id(); attempt.mkdir(parents=True, exist_ok=False)
    counters = Counters('FORMAL'); selection = ValidationSelection(); history = []
    stage = data.STAGE_ROOT / ('v2_' + rid + '_' + attempt.name)
    sources = contract.sources()
    firewall = SourceFirewall(sources, attempt / 'raw_access_parent.jsonl', mask_path=contract.protocol['identity']['yunnan_mask']['path'])
    store = CheckpointStore(local, public, kind, rid, attempt_id=attempt.name)
    current = {'epoch': 0, 'step': 0}; retained_epoch = 0
    try:
        with firewall.installed():
            seed_reproducibility(); assert_environment()
            models, initial = paired_initialization(contract)
            if initial != gate['paired_initialization']: raise ValueError('Fresh paired identity changed')
            model = models.pop(kind).cuda(); del models; gc.collect()
            if state_digest(model.state_dict()) != initial['models'][kind]: raise ValueError('GPU transfer changed initialization')
            optimizer, groups = optimizer_for(model, kind, contract)
            provenance = {'model': kind, 'run_id': rid, 'pair_id': auth['pair_id'], 'protocol_sha256': PROTOCOL_SHA,
                          'head_sha256': HEAD_SHA, 'normalization_sha256': data.SCALER_SHA,
                          'code_sha256': contract.code, 'initialization': initial, 'optimizer_groups': groups,
                          'execution_commit': auth['execution_commit'], 'origin_authorization_sha256': auth['origin_authorization_sha256'],
                          'identity': contract.protocol['identity'], 'environment': gate['environment']}
            if resume:
                ref = store.last()
                if ref['sha256'] != auth['resume_LAST_sha256']: raise ValueError('Resume authorization binds another LAST')
                payload = apply_verified(ref, provenance, model, optimizer)
                selection = ValidationSelection(**payload['selection'])
                retained_epoch = selection.completed_epoch
                history = read_json(public / 'training_validation_history.json')
                if len(history) != selection.completed_epoch: raise ValueError('Resume history boundary mismatch')
                atomic_json(attempt / 'resume_identity.json', {'LAST': ref, 'verified_state_sha256': payload['state_sha256'],
                            'retained_updates': selection.completed_epoch * STEPS, 'half_epoch_reused': False}, immutable=True)
                if selection.non_improvement_count >= 8 or selection.completed_epoch >= 50:
                    raise PermissionError('Already terminated run cannot gain further updates')
                del payload
            atomic_json(attempt / 'provenance.json', provenance, immutable=True)
            sets, mask = datasets(contract, kind, stage, attempt, sources)
            previous_raw_opens = 0
            for ep in range(selection.completed_epoch + 1, 51):
                contract.unchanged()
                from paired_phase_a_v2.preflight import disk_gate, environment
                if environment() != gate['environment']: raise ValueError('Runtime environment drift')
                disk_gate(gate['checkpoint_bytes_budget'], gate['log_bytes_per_epoch_budget'])
                current = {'epoch': ep, 'step': 0}
                ep_dir = attempt / f'epoch_{ep:03d}'; ep_dir.mkdir()
                train_diag = UpperTailDiagnostics(mask, 'TRAIN', ep_dir / 'train_diagnostics.jsonl')
                val_diag = UpperTailDiagnostics(mask, 'VALIDATION', ep_dir / 'validation_diagnostics.jsonl')
                order = epoch_permutation(ep - 1, count=10455).tolist(); seen = []
                socc = sqr = 0.; denom = 0; start = time.monotonic(); model.train()
                worker_pids = set(); source_exposures = 0
                with loader_items(loader(sets[2023], order=order)) as batches:
                    for step, items in enumerate(batches, 1):
                        current = {'epoch': ep, 'step': step}
                        worker_pids.update(item['worker_pid'] for item in items)
                        source_exposures += sum(len(item['staging']) for item in items)
                        batch = data.make_batch(items)
                        current['sample_ids'] = batch.sample_ids
                        if batch.indices != order[(step-1)*2:step*2]: raise ValueError('Unexpected sample order')
                        metrics, observation = update(model, optimizer, batch, (ep-1)*STEPS+step, counters, train_diag, ep_dir / 'steps.jsonl')
                        seen.extend(batch.indices); n = metrics['actual_denominator']; denom += n
                        socc += metrics['L_occ'] * n; sqr += metrics['L_qr'] * n
                        progress(public, status='RUNNING', phase='TRAIN', model=kind, **current, LR=metrics['LR'],
                                 train_loss=(socc+sqr)/denom, gradient_norm=metrics['pre_clip_norm'],
                                 post_clip_norm=metrics['post_clip_norm'], BEST_epoch=selection.selected_checkpoint_epoch,
                                 patience=selection.non_improvement_count, ETA_seconds=(time.monotonic()-start)/step*(STEPS-step),
                                 gpu_memory_allocated=torch.cuda.memory_allocated(), diagnostics=observation, counters=counters.snapshot())
                        del items, batch
                if seen != order or len(set(seen)) != 10455: raise ValueError('Incomplete exactly-once coverage')
                train = {'scenes': len(seen), 'steps': STEPS, 'N_valid': denom, 'exactly_once': True,
                         'ordered_sample_ids_sha256': state_digest([contract.records[kind, 2023][i]['sample_id'] for i in seen]),
                         'global_core_loss': (socc+sqr)/denom, 'S_occ': socc, 'S_qr': sqr}
                acc = LogDomainValidation(); val_seen = []; model.eval(); validation_started = time.monotonic()
                with torch.inference_mode(), loader_items(loader(sets[2024], validation=True)) as batches:
                    for step, items in enumerate(batches, 1):
                        worker_pids.update(item['worker_pid'] for item in items)
                        source_exposures += sum(len(item['staging']) for item in items)
                        batch = data.make_batch(items)
                        append_event(ep_dir / 'validation_calls.jsonl', 'VALIDATION_FORWARD_START', step=step, sample_ids=batch.sample_ids)
                        out, _ = forward_loss(model, batch, counters, 'VALIDATION')
                        acc.add(out, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask)
                        observation = val_diag.observe(out.conditional_quantiles_log, batch.sample_ids)
                        val_seen.extend(batch.indices)
                        progress(public, status='RUNNING', phase='VALIDATION', model=kind, epoch=ep, step=step,
                                 validation_core_loss=acc.report()['global_val_core_loss'], diagnostics=observation,
                                 counters=counters.snapshot(), gpu_memory_allocated=torch.cuda.memory_allocated(),
                                 ETA_seconds=(time.monotonic()-validation_started)/step*(1313-step))
                        del batch, out, items
                if val_seen != list(range(10501)): raise ValueError('Validation fixed order incomplete')
                validation = acc.report(); decision = selection.update(ep, validation['global_val_core_loss'])
                diagnostics = {'TRAIN': train_diag.report(), 'VALIDATION': val_diag.report()}
                atomic_json(ep_dir / 'diagnostics.json', diagnostics, immutable=True)
                from .upper_tail_v2 import save_csv
                save_csv(ep_dir / 'diagnostics.csv', diagnostics)
                io_proof = reconcile_io(attempt)
                if io_proof['DENIED_ATTEMPTS']: raise PermissionError('Forbidden access attempt in formal execution')
                if any(not (attempt / f'raw_access_worker_{pid}.jsonl').exists() for pid in worker_pids):
                    raise ValueError('Worker source audit log missing; zero access cannot be asserted')
                if io_proof['RAW_SOURCE_OPENS'] - previous_raw_opens != 2 * source_exposures:
                    raise ValueError('Raw copy/hash open counts do not reconcile to staging exposures')
                previous_raw_opens = io_proof['RAW_SOURCE_OPENS']
                payload = make_payload(model, optimizer, provenance, selection, train, validation, counters.snapshot(), diagnostics)
                def checkpoint_written(): counters.CHECKPOINT_WRITES += 1
                registry = store.save(payload, provenance, epoch_audit, decision['checkpoint_selected'], checkpoint_written)
                retained_epoch = ep
                row = {'epoch': ep, 'training': train, 'validation': validation, 'selection': asdict(selection),
                       'decision': decision, 'diagnostics': diagnostics, 'checkpoint': registry['LAST'],
                       'counters_this_attempt': counters.snapshot(), 'io': io_proof,
                       'local_epoch_artifacts': [identity(p) for p in sorted(ep_dir.iterdir()) if p.is_file()]}
                atomic_json(public / f'epoch_{ep:03d}_report.json', row, immutable=True)
                history.append(row); atomic_json(public / 'training_validation_history.json', history)
                atomic_json(public / f'publish_epoch_{ep:03d}.json', {'status': 'PENDING', 'report': identity(public / f'epoch_{ep:03d}_report.json')}, immutable=True)
                progress(public, status='EPOCH_COMPLETE', model=kind, epoch=ep, step=STEPS,
                         BEST_epoch=selection.selected_checkpoint_epoch, patience=selection.non_improvement_count,
                         validation_core_loss=validation['global_val_core_loss'], diagnostics=diagnostics, counters=counters.snapshot())
                del payload, train_diag, val_diag
                if decision['stop']: break
            reason = 'EARLY_STOP_PATIENCE_8' if selection.non_improvement_count >= 8 else 'MAX_EPOCH_50'
            best_es_epoch = 1
            for row in history:
                if row['decision']['early_stop_improvement']: best_es_epoch = row['epoch']
            final = {'status': 'COMPLETE', 'model': kind, 'termination_reason': reason,
                     'completed_epoch': selection.completed_epoch, 'best_checkpoint_epoch': selection.selected_checkpoint_epoch,
                     'best_es_epoch': best_es_epoch, 'best_es_value': selection.early_stop_best,
                     'final_early_stop_counter': selection.non_improvement_count, 'patience': 8, 'min_delta': 1e-4,
                     'retained_trajectory_updates': selection.completed_epoch*STEPS, 'counters_this_attempt': counters.snapshot(),
                     '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'io': reconcile_io(attempt)}
            atomic_json(attempt / 'attempt_counters.json', counters.snapshot(), immutable=True)
            final['all_attempt_reconciliation'] = reconcile_attempts(local, retained_epoch)
            atomic_json(public / 'final_report.json', final, immutable=True); progress(public, **final)
    except BaseException as exc:
        failure = {'status': 'FAILED_STOP', 'error': repr(exc), 'traceback': traceback.format_exc(), **current,
                   'counters_this_attempt': counters.snapshot(), 'retained_completed_epoch': retained_epoch,
                   'uncheckpointed_updates_are_not_resumable': True, 'automatic_resume': False,
                   '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0}
        atomic_json(attempt / 'failure.json', failure, immutable=True); progress(public, **failure)
        if not (attempt / 'attempt_counters.json').exists():
            atomic_json(attempt / 'attempt_counters.json', counters.snapshot(), immutable=True)
        raise


def reconcile_attempts(local, completed_epoch):
    attempts=[]; lower=upper=0
    for attempt in sorted((Path(local)/'audit').glob('run_*')):
        count_file=attempt/'attempt_counters.json'
        if count_file.exists():
            counter=read_json(count_file);lo=hi=counter['OPTIMIZER_STEPS'];certainty='EXACT_PROCESS_COUNTER'
        else:
            tried=done=0; malformed=0
            for log in attempt.glob('epoch_*/steps.jsonl'):
                with log.open(encoding='utf-8') as stream:
                    for line in stream:
                        try:event=json.loads(line)
                        except json.JSONDecodeError:malformed+=1;continue
                        tried+=event['event']=='OPTIMIZER_STEP_ATTEMPT'
                        done+=event['event']=='OPTIMIZER_STEP_COMPLETED'
            lo=done;hi=tried+malformed;certainty='JOURNAL_BOUNDS_UNCLEAN_EXIT'
        lower+=lo;upper+=hi
        attempts.append({'attempt':attempt.name,'updates_lower_bound':lo,'updates_upper_bound':hi,'certainty':certainty})
    retained=completed_epoch*STEPS
    if lower<retained:raise ValueError('Attempt accounting cannot support retained trajectory')
    return {'retained_trajectory_updates':retained,'all_attempt_updates_lower_bound':lower,
            'all_attempt_updates_upper_bound':upper,'discarded_updates_lower_bound':lower-retained,
            'discarded_updates_upper_bound':upper-retained,'attempts':attempts,'half_epoch_state_reused':False}
