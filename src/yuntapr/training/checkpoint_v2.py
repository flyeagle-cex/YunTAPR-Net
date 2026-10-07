"""Completed epoch-only state transactions; provenance before state application."""
from dataclasses import asdict
from pathlib import Path
import math
import os
import torch
from yuntapr.training.phase_a_protocol import (state_digest, capture_rng, restore_rng,
    epoch_permutation, lr_for_update, ValidationSelection)
from .phase_a_audit_v2 import atomic_json, identity, read_json

STEPS = 5228
ROOTS = {
    'B0_MATCHED_V2': Path(r'F:\pytorch\Research\outputs\formal_training\b0_matched_v2_phase_a'),
    'B1_V2': Path(r'F:\pytorch\Research\outputs\formal_training\b1_v2_phase_a'),
}


def permutation_sha(epoch):
    return state_digest(epoch_permutation(epoch - 1, count=10455).tolist())


def tree_finite(value):
    if isinstance(value, torch.Tensor):
        return bool(torch.isfinite(value).all())
    if isinstance(value, dict):
        return all(tree_finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(tree_finite(v) for v in value)
    return True


def make_payload(model, optimizer, provenance, selection, train, validation, counters, diagnostics):
    epoch = selection.completed_epoch
    payload = {
        'schema': 'PAIRED_PHASE_A_V2_COMPLETED_EPOCH_v1', 'provenance': provenance,
        'completed_epoch': epoch, 'global_update': epoch * STEPS,
        'training_completed': True, 'validation_completed': True,
        'selection': asdict(selection), 'training': train, 'validation': validation,
        'counters': counters, 'counter_snapshot_boundary': 'BEFORE_CHECKPOINT_WRITE', 'diagnostics': diagnostics,
        'scheduler': {'W': STEPS, 'U': 50 * STEPS, 'last_update': epoch * STEPS,
                      'last_lr': lr_for_update(epoch * STEPS, steps_per_epoch=STEPS),
                      'next_lr': lr_for_update(epoch * STEPS + 1, steps_per_epoch=STEPS) if epoch < 50 else None},
        'completed_permutation_sha256': permutation_sha(epoch),
        'next_permutation_sha256': permutation_sha(epoch + 1),
        'model': model.state_dict(), 'optimizer': optimizer.state_dict(), 'rng': capture_rng(),
    }
    payload['state_sha256'] = {k: state_digest(payload[k]) for k in ('model', 'optimizer', 'rng', 'scheduler')}
    return payload


def validate_payload(payload, expected):
    if payload.get('schema') != 'PAIRED_PHASE_A_V2_COMPLETED_EPOCH_v1' or payload.get('provenance') != expected:
        raise ValueError('Checkpoint provenance mismatch before state application')
    ep = payload['completed_epoch']
    if type(ep) is not int or not 1 <= ep <= 50 or payload['global_update'] != ep * STEPS:
        raise ValueError('Not an epoch boundary')
    if payload['training_completed'] is not True or payload['validation_completed'] is not True:
        raise ValueError('Incomplete train/validation')
    t, v = payload['training'], payload['validation']
    if t['scenes'] != 10455 or t['steps'] != STEPS or t['N_valid'] != 10455 * 3430 or not t['exactly_once']:
        raise ValueError('Incomplete training coverage')
    if v['scenes'] != 10501 or v['forwards'] != 1313 or v['N_valid'] != 10501 * 3430:
        raise ValueError('Incomplete validation coverage')
    if not math.isfinite(v['global_val_core_loss']):
        raise ValueError('Invalid selection metric')
    s = ValidationSelection(**payload['selection'])
    if s.completed_epoch != ep or not 1 <= s.selected_checkpoint_epoch <= ep or not 0 <= s.non_improvement_count <= 8:
        raise ValueError('Invalid selection boundary')
    if not all(math.isfinite(x) for x in (s.best_checkpoint_value, s.early_stop_best)):
        raise ValueError('Invalid selection state')
    for name in ('model', 'optimizer', 'rng', 'scheduler'):
        if state_digest(payload[name]) != payload['state_sha256'][name]:
            raise ValueError('State SHA mismatch: ' + name)
    if not tree_finite(payload['model']) or not tree_finite(payload['optimizer']):
        raise FloatingPointError('Nonfinite checkpoint state')
    scheduler = payload['scheduler']
    want = {'W': STEPS, 'U': 50 * STEPS, 'last_update': ep * STEPS,
            'last_lr': lr_for_update(ep * STEPS, steps_per_epoch=STEPS),
            'next_lr': lr_for_update(ep * STEPS + 1, steps_per_epoch=STEPS) if ep < 50 else None}
    if scheduler != want or any(g['lr'] != want['last_lr'] for g in payload['optimizer']['param_groups']):
        raise ValueError('Scheduler/optimizer boundary mismatch')
    if payload['completed_permutation_sha256'] != permutation_sha(ep) or payload['next_permutation_sha256'] != permutation_sha(ep + 1):
        raise ValueError('Epoch permutation mismatch')


def verify_file(ref, expected):
    p = Path(ref['absolute_local_path'])
    if identity(p) != {k: ref[k] for k in ('absolute_local_path', 'bytes', 'sha256')}:
        raise ValueError('Checkpoint bytes/SHA mismatch before deserialization')
    payload = torch.load(p, map_location='cpu', weights_only=False)
    validate_payload(payload, expected)
    return payload


def apply_verified(ref, expected, model, optimizer):
    payload = verify_file(ref, expected)
    actual = model.state_dict()
    saved = payload['model']
    if actual.keys() != saved.keys() or any(actual[n].shape != saved[n].shape or actual[n].dtype != saved[n].dtype for n in actual):
        raise ValueError('Model keys/shapes/dtypes mismatch before application')
    current = optimizer.state_dict()['param_groups']
    supplied = payload['optimizer']['param_groups']
    def without_lr(groups):
        return [{k: v for k, v in g.items() if k != 'lr'} for g in groups]
    if without_lr(current) != without_lr(supplied):
        raise ValueError('Optimizer group mismatch before application')
    model.load_state_dict(saved, strict=True)
    optimizer.load_state_dict(payload['optimizer'])
    restore_rng(payload['rng'])
    for name, state in (('model', model.state_dict()), ('optimizer', optimizer.state_dict()), ('rng', capture_rng())):
        if state_digest(state) != payload['state_sha256'][name]:
            raise ValueError('Restored state identity mismatch: ' + name)
    return payload


class CheckpointStore:
    def __init__(self, root, public, model, run_id, *, scope='FORMAL', attempt_id=None):
        self.root, self.public = Path(root).resolve(), Path(public).resolve()
        self.model, self.run_id, self.scope = model, run_id, scope
        if scope == 'FORMAL':
            if self.root != (ROOTS[model] / run_id).resolve():
                raise PermissionError('Wrong formal checkpoint root')
        elif scope != 'TEST_FIXTURE_ONLY' or 'formal_training' in self.root.parts:
            raise PermissionError('Isolated checkpoint fixture root required')
        self.root.mkdir(parents=True, exist_ok=True); self.public.mkdir(parents=True, exist_ok=True)
        if attempt_id is not None:
            import re
            if not re.fullmatch(r'run_\d{8}T\d{6}_\d{6}Z', attempt_id):
                raise ValueError('Timestamped checkpoint attempt required')
            self.write_root = self.root / 'checkpoints' / attempt_id
            self.write_root.mkdir(parents=True, exist_ok=True)
        else:
            self.write_root = self.root

    def save(self, payload, expected, audit, selected, on_write=None):
        validate_payload(payload, expected)
        ep = payload['completed_epoch']
        file = self.write_root / f'epoch_{ep:03d}.pt'
        temp = self.write_root / f'epoch_{ep:03d}.pt.incomplete'
        if file.exists() or temp.exists():
            raise FileExistsError('Historical checkpoint/incomplete artifact is immutable')
        with temp.open('xb') as f:
            torch.save(payload, f); f.flush(); os.fsync(f.fileno())
        temp.rename(file)
        if on_write is not None: on_write()
        ref = {**identity(file), 'epoch': ep, 'model': self.model, 'run_id': self.run_id,
               'global_update': ep * STEPS, 'scope': self.scope}
        verify_file(ref, expected)
        # A crash before this marker leaves an orphan, never an automatic resume.
        proof = audit(payload, ref)
        if proof.get('status') != 'PASS':
            raise ValueError('Epoch audit failed; no LAST/BEST publication')
        marker = {'status': 'PASS', 'checkpoint': ref, 'audit': proof}
        atomic_json(self.public / f'epoch_{ep:03d}_complete.json', marker, immutable=True)
        registry_path = self.public / 'checkpoint_registry.json'
        registry = read_json(registry_path) if registry_path.exists() else {'epochs': []}
        if len(registry['epochs']) != ep - 1:
            raise ValueError('Registry is not sequential')
        registry['epochs'].append(ref); registry['LAST'] = ref
        if selected: registry['BEST'] = ref
        atomic_json(registry_path, registry)
        atomic_json(self.public / 'last_checkpoint_identity.json', ref)
        atomic_json(self.public / 'best_checkpoint_identity.json', registry['BEST'])
        return registry

    def last(self):
        registry = read_json(self.public / 'checkpoint_registry.json')
        ref = registry['LAST']
        if ref['model'] != self.model or ref['run_id'] != self.run_id or not Path(ref['absolute_local_path']).resolve().is_relative_to(self.root):
            raise ValueError('Cross-model/run resume forbidden')
        marker = read_json(self.public / f"epoch_{ref['epoch']:03d}_complete.json")
        if marker['status'] != 'PASS' or marker['checkpoint'] != ref:
            raise ValueError('LAST has no matching epoch audit marker')
        if len(registry['epochs']) != ref['epoch'] or registry['epochs'][-1] != ref:
            raise ValueError('Invalid checkpoint registry ancestry')
        return ref
