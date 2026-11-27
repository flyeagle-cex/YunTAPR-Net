"""2025 B4/B7/B8 final-test inference adapter (catalogue-gated, default denied).

This module is the only place that would orchestrate a real 2025 final test.  It
is deliberately inert unless *two* explicit researcher authorization objects are
supplied: a frozen final-test authority and a separate payload-access authority.
Neither object exists in the repository.  All public entry points deny by
default, and no code path in this module lists, stats or opens a 2025 raw path on
its own initiative.

The adapter never trains, tunes, selects, recalibrates or refits.  It performs a
single read-only pass over a caller-supplied, catalogue-frozen population with
the twelve fixed epoch-9 checkpoints and records paired descriptive metrics only.

Design invariants
-----------------
* Planning/population/catalogue artefacts are produced by the sibling modules.
  This module consumes them; it never derives a population by scanning storage.
* Checkpoint identity is bound by SHA-256 and byte size, and every payload is
  additionally checked for the frozen epoch, update count, seed, population and
  model family before any tensor is produced.
* B7_REAL and B7_ZERO_DOTE are the same network with the same weights; only the
  numeric DOTE control changes.  The primary comparison is descriptive.
* A numerical violation stops the run.  Nothing is repaired, clipped or
  re-selected (``STOP_NO_REPAIR``).
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
import torch

from yuntapr.experimental.core_innovation import gfs
from yuntapr.experimental.core_innovation.multispectral import (
    TrainNormalization,
)
from yuntapr.experimental.core_innovation.stage2 import CHANNELS, MEE_V13_KEYS
from yuntapr.experimental.core_innovation.stage2.environment import (
    V13_UNITS,
    EnvironmentScaler,
    prepare_mee,
)
from yuntapr.experimental.core_innovation.stage2.models import SpectralCandidate
from yuntapr.experimental.research_readiness import final_test_2025_catalogue as catalogue
from yuntapr.experimental.research_readiness import final_test_2025_manifest as manifest
from yuntapr.experimental.research_readiness import final_test_2025_planning as planning
from yuntapr.experimental.research_readiness import final_test_2025_readers as readers
from yuntapr.experimental.research_readiness.dote_numeric_control import ZeroNumericDote
from yuntapr.experimental.research_readiness.dynamic_terrain import (
    DoteDefinition,
    DynamicTerrainModel,
    PhysicalDote,
    paired_fusion_candidates,
)
from yuntapr.experimental.research_readiness.static_training import (
    StaticTrainingModel,
    unpack as unpack_static,
)
from yuntapr.models.quantile_v2.outputs import materialize_physical
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.phase_a_validation import GlobalValidationAccumulator

REPO_ROOT = Path(__file__).resolve().parents[4]

VERSION = 'v1'
SCOPE = 'B4_B7_B8_2025_FINAL_TEST_ONLY'
MODELS = ('B4', 'B7', 'B8', 'B7_ZERO_DOTE')
SEEDS = (2029, 2030, 2031)
FAMILY = {'B4': 'B4', 'B7': 'B7_REAL', 'B8': 'B8', 'B7_ZERO_DOTE': 'B7_ZERO_DOTE'}

# Frozen identities of the inherited 2023/2024 inputs.  These are checked only
# when a real authority is executed; synthetic adapter tests never open them.
FROZEN_POPULATION_SHA = '2f2cc75cfb6c209fd8195d3419207216c5c3f2a4fc8315b40a1d77cc537dedb8'
FROZEN_TRAIN_STATISTICS_SHA = '53ab2f07aabb02e66ad237452447a35e0e2896278eae9d2da179336c06fea980'
FROZEN_STATIC_PACK_SHA = '788572b1e82ba388d6ddcd6b1f8a987af818f44cdde9d5d613db5d35af5281bd'
FROZEN_YUNNAN_MASK_SHA = '9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef'
FROZEN_B13_NORMALIZATION_SHA = '656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31'

PARAMETER_COUNTS = {'B4': 4_355_986, 'B7': 4_411_058, 'B8': 4_411_058, 'B7_ZERO_DOTE': 4_411_058}

#: The single co-primary comparison and the three frozen secondary comparisons.
COMPARISONS = (
    ('PRIMARY_B7_REAL_MINUS_B7_ZERO_DOTE', 'PRIMARY', 'B7', 'B7_ZERO_DOTE'),
    ('SECONDARY_B8_MINUS_B7_REAL', 'SECONDARY', 'B8', 'B7'),
    ('SECONDARY_B7_REAL_MINUS_B4', 'SECONDARY', 'B7', 'B4'),
    ('SECONDARY_B8_MINUS_B4', 'SECONDARY', 'B8', 'B4'),
)
CO_PRIMARY_METRICS = ('Brier', 'conditional_mean_pinball')
COMPARISON_METRICS = (
    'Brier', 'conditional_mean_pinball', 'AUROC', 'Average_Precision',
    'q32_signed_bias', 'q32_absolute_error', 'mean_absolute_coverage_error',
)

FINAL_METRICS = (
    'global_core_loss', 'occurrence_loss', 'quantile_loss', 'Brier', 'AUROC',
    'Average_Precision', 'conditional_mean_pinball', 'per_tau_pinball',
    '32_tau_conditional_coverage', 'coverage_error', 'crossing_count',
    'nonfinite_count', 'support_violation_count',
)

_TOP_KEYS = (
    'version', 'AUTHORIZED_BY', 'scope', 'FINAL_TEST_2025_AUTHORIZED',
    'FINAL_TEST_2025_EXECUTED', 'protocol', 'implementation', 'catalogue',
    'population', 'freeze', 'checkpoints', 'frozen_inputs', 'dote', 'inference',
    'output_root', 'created_utc',
)
_ENTRY_KEYS = ('path', 'sha256')
_FROZEN_INPUT_KEYS = ('statistics', 'static_pack', 'static_receipt', 'yunnan_mask')
_DOTE_KEYS = (
    'pwat_reference_kg_m2', 'reference_provenance', 'moisture_basis',
    'velocity_reference_m_s',
)
_INFERENCE_KEYS = ('device', 'seed', 'threads', 'scenes_per_batch')
_CHECKPOINT_KEYS = ('model', 'seed', 'path', 'sha256', 'bytes')
_HEX = catalogue.SHA


def _utc(value: Any) -> datetime:
    return planning.utc(value)


def _iso(value: datetime | None = None) -> str:
    moment = value or datetime.now(timezone.utc)
    return moment.replace(microsecond=0).isoformat()


def _exact_keys(value: Any, keys: Sequence[str], label: str) -> None:
    if not isinstance(value, dict) or tuple(value) != tuple(keys):
        raise ValueError(f'{label} must use the exact ordered key set')


def _hex(value: Any, label: str) -> str:
    if not isinstance(value, str) or _HEX.fullmatch(value) is None:
        raise ValueError(f'{label} must be a lowercase 64-hex SHA-256')
    return value


def _entry(value: Any, label: str) -> tuple[Path, str]:
    _exact_keys(value, _ENTRY_KEYS, label)
    path = Path(value['path'])
    if not path.is_absolute():
        raise ValueError(f'{label}.path must be absolute')
    return path, _hex(value['sha256'], f'{label}.sha256')


def sha256_file(path: str | os.PathLike[str], *, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while True:
            block = stream.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _verified_bytes(path: str | os.PathLike[str], *, sha256: str,
                    expected_bytes: int | None = None, max_bytes: int = 64 << 20) -> bytes:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f'Bound file is missing: {target}')
    size = target.stat().st_size
    if size > max_bytes:
        raise ValueError(f'Bound file exceeds size cap: {target}')
    if expected_bytes is not None and size != int(expected_bytes):
        raise ValueError(f'Bound file byte size mismatch: {target}')
    raw = target.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError(f'Bound file SHA-256 mismatch: {target}')
    return raw


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _forbidden(path: Path) -> bool:
    text = str(path).replace('\\', '/').lower()
    return any(text == prefix or text.startswith(prefix + '/') for prefix in (
        'h:/葵花202303_202510', 'f:/云南极端降水数据', 'f:/pytorch'))


# --------------------------------------------------------------------------- #
# Authorization
# --------------------------------------------------------------------------- #
class FinalTest2025Authority:
    """Strict loader/binder for the separate post-freeze final-test authority."""

    def __init__(self, value: Mapping[str, Any], sha256: str):
        _exact_keys(value, _TOP_KEYS, 'final-test authority')
        if value['version'] != VERSION:
            raise ValueError(f'Unsupported final-test authority version: {value["version"]!r}')
        if value['AUTHORIZED_BY'] != 'RESEARCHER':
            raise PermissionError('Only an explicit researcher authority can execute a final test')
        if value['scope'] != SCOPE:
            raise ValueError('Final-test authority scope mismatch')
        if value['FINAL_TEST_2025_AUTHORIZED'] is not True:
            raise PermissionError('FINAL_TEST_2025_AUTHORIZED must be true')
        if value['FINAL_TEST_2025_EXECUTED'] is not False:
            raise PermissionError('A single-use authority must be unexecuted')
        self.protocol_path, self.protocol_sha256 = _entry(value['protocol'], 'protocol')
        implementation = value['implementation']
        _exact_keys(implementation, ('files', 'sha256'), 'implementation')
        files = []
        for item in implementation['files']:
            files.append(_entry(item, 'implementation.files[]'))
        if not files:
            raise ValueError('At least one implementation file must be bound')
        if manifest.canonical_sha([{'path': str(p), 'sha256': s} for p, s in files]) != _hex(
                implementation['sha256'], 'implementation.sha256'):
            raise ValueError('Implementation digest does not match the bound file list')
        self.implementation_files = tuple(files)
        self.catalogue_path, self.catalogue_sha256 = _entry(value['catalogue'], 'catalogue')
        self.population_path, self.population_sha256_file = _entry(
            value['population'], 'population')
        self.freeze_path, self.freeze_sha256 = _entry(value['freeze'], 'freeze')
        checkpoints = value['checkpoints']
        if not isinstance(checkpoints, list) or len(checkpoints) != len(catalogue.CHECKPOINTS):
            raise ValueError('Exactly twelve checkpoint bindings are required')
        records: dict[tuple[str, int], dict[str, Any]] = {}
        for item in checkpoints:
            _exact_keys(item, _CHECKPOINT_KEYS, 'checkpoints[]')
            model, seed = item['model'], item['seed']
            if model not in MODELS or type(seed) is not int or seed not in SEEDS:
                raise ValueError('Checkpoint model/seed outside the frozen catalogue')
            if (model, seed) in records:
                raise ValueError('Duplicate checkpoint model/seed binding')
            path = Path(item['path'])
            if not path.is_absolute():
                raise ValueError('checkpoint path must be absolute')
            sha = _hex(item['sha256'], 'checkpoint sha256')
            known = catalogue.CHECKPOINTS[(model, seed)]
            if sha != known['sha256']:
                raise ValueError('Checkpoint SHA differs from the frozen checkpoint catalogue')
            if known['bytes'] is not None and item['bytes'] != known['bytes']:
                raise ValueError('Checkpoint byte size differs from the audit evidence')
            if type(item['bytes']) is not int or item['bytes'] <= 0:
                raise ValueError('Positive checkpoint byte size required')
            records[(model, seed)] = {'model': model, 'seed': seed, 'path': path,
                                      'sha256': sha, 'bytes': item['bytes']}
        if set(records) != set(catalogue.CHECKPOINTS):
            raise ValueError('Checkpoint bindings must cover B4/B7/B8/B7_ZERO_DOTE x three seeds')
        self.checkpoints = MappingProxyType(records)

        frozen = value['frozen_inputs']
        _exact_keys(frozen, _FROZEN_INPUT_KEYS, 'frozen_inputs')
        self.frozen_inputs = MappingProxyType({
            key: _entry(frozen[key], f'frozen_inputs.{key}') for key in _FROZEN_INPUT_KEYS})

        dote = value['dote']
        _exact_keys(dote, _DOTE_KEYS, 'dote')
        self.dote_definition = DoteDefinition(
            pwat_reference_kg_m2=float(dote['pwat_reference_kg_m2']),
            reference_provenance=str(dote['reference_provenance']),
            moisture_basis=str(dote['moisture_basis']),
            velocity_reference_m_s=float(dote['velocity_reference_m_s']))
        inference = value['inference']
        _exact_keys(inference, _INFERENCE_KEYS, 'inference')
        if inference['device'] not in ('cuda', 'cpu'):
            raise ValueError('inference.device must be cuda or cpu')
        if inference['scenes_per_batch'] != 1:
            raise ValueError('Exactly one scene per bounded read batch is frozen')
        if type(inference['seed']) is not int or type(inference['threads']) is not int:
            raise ValueError('inference seed/threads must be integers')
        self.inference = MappingProxyType(dict(inference))
        output_root = Path(value['output_root'])
        if not output_root.is_absolute():
            raise ValueError('output_root must be absolute')
        self.output_root = output_root
        self.created_utc = _utc(value['created_utc'])
        self.sha256 = _hex(sha256, 'authority SHA')
        self.document = MappingProxyType(dict(value))

    @classmethod
    def load(cls, path: str | os.PathLike[str], expected_sha256: str | None = None) -> 'FinalTest2025Authority':
        target = Path(path)
        raw = target.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError('Final-test authority SHA-256 mismatch')
        value = json.loads(raw.decode('utf-8'))
        return cls(value, digest)

    def require_final(self) -> None:
        if self.document['FINAL_TEST_2025_AUTHORIZED'] is not True:
            raise PermissionError('Final-test execution is not authorized')

    def require_catalogue(self) -> None:
        raise PermissionError('This authority permits only one final read-only inference pass')

    def checkpoint_records(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.checkpoints[(model, seed)] for model in MODELS for seed in SEEDS)


def authorize_final_test(*args: Any, **kwargs: Any) -> None:
    """No code can mint a researcher authority; only the researcher can sign one."""
    raise PermissionError('Final-test authority must come from the researcher; the adapter cannot create it')


def authorize_payload(*args: Any, **kwargs: Any) -> None:
    raise PermissionError('2025 payload access requires a separate explicit payload authority')


# --------------------------------------------------------------------------- #
# Frozen inherited inputs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FrozenInputs:
    statistics: Mapping[str, Any]
    spectral: Mapping[str, TrainNormalization]
    environment: Mapping[str, EnvironmentScaler]
    pack: Any
    terrain_scalers: Mapping[str, Any]
    mask: np.ndarray
    mapping: Any
    grid: gfs.GridSpec
    dote: Any
    definition: DoteDefinition | None


def spectral_population_id(channel: str, population_sha256: str) -> str:
    """B13 keeps the frozen pre-phase-B normalization identity; six channels use Train."""
    _hex(population_sha256, 'Train statistics population SHA')
    return FROZEN_B13_NORMALIZATION_SHA if channel == 'B13' else population_sha256


def frozen_statistics_sha(authority: FinalTest2025Authority) -> str:
    """SHA-256 of the frozen Train statistics bound by a parsed authority."""
    return authority.frozen_inputs['statistics'][1]


def load_frozen_inputs(authority: FinalTest2025Authority, *,
                       require_canonical: bool = True) -> FrozenInputs:
    """Load the frozen 2023-Train scalers, static B6 pack and Yunnan mask."""
    stats_path, stats_sha = authority.frozen_inputs['statistics']
    if require_canonical and stats_sha != FROZEN_TRAIN_STATISTICS_SHA:
        raise PermissionError('Only the frozen 2023 Train statistics SHA may be used')
    statistics = json.loads(_verified_bytes(stats_path, sha256=stats_sha).decode('utf-8'))
    if not isinstance(statistics, dict):
        raise ValueError('Train statistics document must be an object')
    if statistics.get('fit_role') != 'Train' or tuple(statistics.get('fit_years', ())) != (2023,):
        raise PermissionError('Normalization must come from 2023 Train only')
    if statistics.get('ddof') != 0 or statistics.get('B13_refitted') is not False:
        raise ValueError('Frozen population-variance normalization with B13_refitted=false required')
    population = statistics.get('population_sha256')
    if require_canonical and population != FROZEN_POPULATION_SHA:
        raise PermissionError('Train statistics population differs from the frozen population')
    if not isinstance(population, str) or _HEX.fullmatch(population) is None:
        raise ValueError('Train statistics must bind a 64-hex population SHA')
    if tuple(statistics.get('spectral_order', ())) != CHANNELS:
        raise ValueError('Frozen seven-channel spectral order required')
    if tuple(statistics.get('environment_order', ())) != MEE_V13_KEYS:
        raise ValueError('Frozen MEE v1.3 environment order required')
    if statistics.get('adapter_status') != '13_CHANNEL_MODEL_ADAPTER_PENDING_RESEARCHER_APPROVAL':
        raise ValueError('Train statistics do not carry the frozen 13-channel adapter status')

    raw_spectral = statistics.get('spectral_scalers')
    if not isinstance(raw_spectral, dict) or set(raw_spectral) != set(CHANNELS):
        raise ValueError('Exactly the seven frozen spectral scalers are required')
    spectral: dict[str, TrainNormalization] = {}
    for channel in CHANNELS:
        entry = raw_spectral[channel]
        if not isinstance(entry, dict):
            raise ValueError('Spectral scaler entry must be an object')
        item = TrainNormalization(
            channel=entry['channel'], mean=float(entry['mean']), std=float(entry['std']),
            unit=entry['unit'], fit_years=tuple(entry['fit_years']),
            fit_role=entry['fit_role'], ddof=entry['ddof'],
            population_id=entry['population_id'])
        if item.channel != channel or item.population_id != spectral_population_id(
                channel, population):
            raise ValueError('Spectral scaler channel/population binding differs')
        spectral[channel] = item

    raw_environment = statistics.get('environment_scalers')
    if not isinstance(raw_environment, dict) or set(raw_environment) != set(MEE_V13_KEYS):
        raise ValueError('Exactly the thirteen frozen environment scalers are required')
    environment: dict[str, EnvironmentScaler] = {}
    for index, key in enumerate(MEE_V13_KEYS):
        entry = raw_environment[key]
        if not isinstance(entry, dict):
            raise ValueError('Environment scaler entry must be an object')
        environment[key] = EnvironmentScaler(
            key=key, mean=float(entry['mean']), std=float(entry['std']),
            unit=V13_UNITS[index], fit_years=(2023,), fit_role='Train',
            population_id=population)

    pack_path, pack_sha = authority.frozen_inputs['static_pack']
    if require_canonical and pack_sha != FROZEN_STATIC_PACK_SHA:
        raise PermissionError('Only the frozen B6 static pack may be used')
    receipt_path, receipt_sha = authority.frozen_inputs['static_receipt']
    receipt = json.loads(_verified_bytes(receipt_path, sha256=receipt_sha).decode('utf-8'))
    pack = unpack_static(_verified_bytes(pack_path, sha256=pack_sha), 'B6', receipt)
    terrain_scalers = receipt.get('scalers', {}).get('B6')
    if not isinstance(terrain_scalers, dict):
        raise ValueError('Static receipt must bind a B6 terrain scaler block')

    mask_path, mask_sha = authority.frozen_inputs['yunnan_mask']
    if require_canonical and mask_sha != FROZEN_YUNNAN_MASK_SHA:
        raise PermissionError('Only the frozen Yunnan mask may be used')
    raw_mask = _verified_bytes(mask_path, sha256=mask_sha, max_bytes=4 << 20)
    from netCDF4 import Dataset  # noqa: PLC0415 - optional heavy dependency
    with Dataset('frozen_yunnan_mask.nc', mode='r', memory=raw_mask) as ds:
        ds.set_auto_maskandscale(False)
        mask = np.asarray(ds['yunnan_mask'][:], dtype=bool)
    if mask.shape != (130, 140) or int(mask.sum()) != 3430:
        raise ValueError('Frozen Yunnan mask shape/count mismatch')
    target_mask = mask[10:110, 20:120]
    if not np.array_equal(target_mask, np.asarray(pack.region)):
        raise ValueError('Yunnan mask differs from the frozen static region')

    mapping = load_sp04(REPO_ROOT)
    grid = gfs.GridSpec(np.asarray(mapping.axes['target_lat'], dtype='float32'),
                        np.asarray(mapping.axes['target_lon'], dtype='float32'))
    return FrozenInputs(statistics=statistics, spectral=spectral, environment=environment,
                        pack=pack, terrain_scalers=terrain_scalers, mask=target_mask,
                        mapping=mapping, grid=grid, dote=None,
                        definition=authority.dote_definition)


# --------------------------------------------------------------------------- #
# Model construction and checkpoint loading
# --------------------------------------------------------------------------- #
def _build_b4(*, root: Path) -> SpectralCandidate:
    return SpectralCandidate('B4', numerics=CandidateNumerics(1e-4, 1e-4),
                             mee_width=16, mee_keys=MEE_V13_KEYS, root=root)


def build_model(kind: str, frozen: FrozenInputs, *, root: Path = REPO_ROOT,
                seed: int = 2026) -> torch.nn.Module:
    """Construct one frozen architecture without touching any optimizer."""
    if kind not in MODELS:
        raise ValueError('Unknown frozen model family')
    b4 = _build_b4(root=Path(root))
    if kind == 'B4':
        return b4
    b6 = StaticTrainingModel(copy.deepcopy(b4), frozen.pack, frozen.terrain_scalers,
                             kind='B6', width=16)
    with torch.random.fork_rng(devices=[]):
        torch.set_rng_state(torch.Generator().manual_seed(int(seed) + 20000).get_state())
        left, right = paired_fusion_candidates(
            feature_channels=[48], gfs_channels=[26], terrain_channels=[28],
            projection_width=16, modulation_limit=.1)
    right.fuse.load_state_dict(left.fuse.state_dict())
    fusion = right if kind == 'B8' else left
    return DynamicTerrainModel(copy.deepcopy(b6), fusion,
                               'B7' if kind == 'B7_ZERO_DOTE' else kind)


def _load_checkpoint_payload(record: Mapping[str, Any]) -> Mapping[str, Any]:
    import warnings
    path = Path(record['path'])
    size = path.stat().st_size
    if size != record['bytes']:
        raise ValueError(f'Checkpoint byte size mismatch: {path.name}')
    if sha256_file(path) != record['sha256']:
        raise ValueError(f'Checkpoint SHA-256 mismatch: {path.name}')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        payload = torch.load(path, map_location='cpu', weights_only=False)
    if not isinstance(payload, dict):
        raise ValueError('Checkpoint payload must be a mapping')
    for key in ('model', 'epoch', 'updates', 'identity'):
        if key not in payload:
            raise ValueError(f'Checkpoint payload missing {key}')
    return payload


def load_final_model(record: Mapping[str, Any], frozen: FrozenInputs, *,
                     require_canonical: bool = True, root: Path = REPO_ROOT) -> torch.nn.Module:
    """Verify one audited checkpoint and return the fixed eval-mode network."""
    kind, seed = record['model'], int(record['seed'])
    payload = _load_checkpoint_payload(record)
    identity = payload['identity']
    if not isinstance(identity, dict):
        raise ValueError('Checkpoint identity must be a mapping')
    decision = identity.get('decision', {})
    data = identity.get('data', {})
    if int(payload['epoch']) != 9 or int(payload['updates']) != 4320:
        raise ValueError('Only the frozen epoch-9 / 4320-update endpoint is allowed')
    if int(decision.get('seed', -1)) != seed:
        raise ValueError('Checkpoint seed differs from the bound catalogue')
    expected_model = 'B7' if kind == 'B7_ZERO_DOTE' else kind
    if identity.get('model') != expected_model:
        raise ValueError('Checkpoint model family differs from the bound catalogue')
    population = data.get('population_sha256')
    if population is not None and population != FROZEN_POPULATION_SHA:
        raise ValueError('Checkpoint population differs from the frozen 2023/2024 population')
    if require_canonical and population != FROZEN_POPULATION_SHA:
        raise PermissionError('Checkpoint does not bind the frozen population')
    model = build_model(kind, frozen, root=root, seed=seed)
    state = payload['model']
    if not isinstance(state, dict):
        raise ValueError('Checkpoint model state must be a state_dict mapping')
    model.load_state_dict(state, strict=True)
    count = sum(parameter.numel() for parameter in model.parameters())
    if count != PARAMETER_COUNTS[kind]:
        raise ValueError(f'Loaded parameter count {count} differs from audited '
                         f'{PARAMETER_COUNTS[kind]}')
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return model


# --------------------------------------------------------------------------- #
# Scene tensors
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SceneInputs:
    sample_id: str
    analysis_time: str
    x: torch.Tensor
    native_valid: torch.Tensor
    environment: torch.Tensor
    environment_valid: torch.Tensor
    dynamic_real: torch.Tensor
    dynamic_zero: torch.Tensor
    dynamic_valid: torch.Tensor
    rate: torch.Tensor
    valid: torch.Tensor
    region: torch.Tensor


def _as_tensor(array: Any, dtype: torch.dtype) -> torch.Tensor:
    return torch.as_tensor(np.asarray(array), dtype=dtype)


def build_scene_inputs(payload: Mapping[str, Any], frozen: FrozenInputs, *,
                       device: str | torch.device = 'cpu') -> SceneInputs:
    """Turn one bounded read payload into the exact B4/B7/B8 input tensors."""
    scene = payload['scene']
    planning.validate_scene(scene)
    analysis = planning.utc(scene['analysis_time'])
    satellite = payload['satellite']
    frames = tuple(satellite['frames'])
    if len(frames) != 6:
        raise ValueError('Exactly six satellite frames are required')
    values = np.asarray(satellite['values'], dtype=np.float32)
    if values.shape != (6, 7, 501, 501):
        raise ValueError('Satellite tensor shape mismatch')
    if not all(bool(frame['full_valid']) for frame in frames):
        raise ValueError('Missing satellite pixels are forbidden under reject policy')
    masks = np.ones(values.shape, dtype=bool)
    native = gfs.GridSpec(np.asarray(satellite['native_lat'], dtype='float32'),
                          np.asarray(satellite['native_lon'], dtype='float32'))
    target = payload['target']
    frozen.mapping.assert_axes(np.asarray(satellite['native_lat'], dtype='float32'),
                               np.asarray(satellite['native_lon'], dtype='float32'),
                               np.asarray(target['target_lat'], dtype='float32'),
                               np.asarray(target['target_lon'], dtype='float32'))
    batch = readers.prepare_multispectral_2025(
        values[None], masks[None], source_channels=CHANNELS, selected_channels=CHANNELS,
        units={channel: 'K' for channel in CHANNELS}, normalization=frozen.spectral,
        nominal_times=[[planning.utc(frame['nominal']) for frame in frames]],
        obs_start_times=[[planning.utc(frame['obs_start']) for frame in frames]],
        obs_end_times=[[planning.utc(frame['obs_end']) for frame in frames]],
        analysis_times=[analysis],
        expected_offsets_before_analysis_minutes=planning.SATELLITE_OFFSETS_MINUTES,
        source_grid=native, expected_grid=native, missing_policy='reject')
    x, native_valid = batch.flatten_time_channels()
    if x.shape != (1, 42, 501, 501) or native_valid.dtype != bool:
        raise ValueError('Flattened multispectral tensor contract mismatch')
    if not bool(native_valid.all()) or not bool(np.isfinite(x).all()):
        raise FloatingPointError('STOP: nonfinite or missing normalized satellite input')

    environment = payload['environment']
    env_frame = environment['environment']
    env_values, env_valid, keys = prepare_mee(
        env_frame, target_grid=frozen.grid, scalers=frozen.environment, keys=MEE_V13_KEYS)
    if tuple(keys) != MEE_V13_KEYS or env_values.shape != (13, 100, 100):
        raise ValueError('Prepared MEE environment contract mismatch')

    if frozen.dote is None:
        if frozen.definition is None:
            raise ValueError('A frozen DOTE definition is required')
        physical = PhysicalDote(frozen.pack, frozen.definition)
    else:  # pragma: no cover - only used by synthetic adapter tests
        physical = frozen.dote
    dynamic, dynamic_valid = physical(env_frame)
    if dynamic.shape != (8, 100, 100) or dynamic_valid.shape != dynamic.shape:
        raise ValueError('DOTE tensor contract mismatch')
    definition = frozen.definition if frozen.definition is not None else getattr(physical, 'definition', None)
    if definition is None:
        raise ValueError('A frozen DOTE definition is required for the numeric control')
    zero_values, zero_valid = ZeroNumericDote(frozen.pack, definition)(env_frame)
    if not np.array_equal(zero_valid, dynamic_valid) or bool(np.any(zero_values != 0)):
        raise ValueError('Numeric ZERO_DOTE control must preserve validity and zero values')

    rate = np.asarray(target['rate'], dtype=np.float64)
    valid = np.asarray(target['valid'], dtype=bool)
    region = np.asarray(frozen.mask, dtype=bool)
    if rate.shape != (100, 100) or valid.shape != rate.shape or region.shape != rate.shape:
        raise ValueError('Target/region tensor shape mismatch')
    if int((valid & region).sum()) <= 0:
        raise ValueError('Scene has no valid Yunnan supervision pixel')
    if not np.isfinite(rate[valid]).all() or (rate[valid] < 0).any():
        raise FloatingPointError('STOP: nonfinite/negative target rate')

    target_device = torch.device(device)
    rate_t = _as_tensor(rate, torch.float64)[None, None]
    valid_t = _as_tensor(valid, torch.bool)[None, None]
    region_t = _as_tensor(region, torch.bool)[None, None]
    return SceneInputs(
        sample_id=scene['sample_id'], analysis_time=scene['analysis_time'],
        x=_as_tensor(x, torch.float32).to(target_device),
        native_valid=_as_tensor(native_valid, torch.bool).to(target_device),
        environment=_as_tensor(env_values, torch.float32)[None].to(target_device),
        environment_valid=_as_tensor(env_valid, torch.bool)[None].to(target_device),
        dynamic_real=_as_tensor(dynamic, torch.float32)[None].to(target_device),
        dynamic_zero=torch.zeros_like(_as_tensor(dynamic, torch.float32)[None]).to(target_device),
        dynamic_valid=_as_tensor(dynamic_valid, torch.bool)[None].to(target_device),
        rate=rate_t.to(target_device), valid=valid_t.to(target_device),
        region=region_t.to(target_device))


def infer_scene(model: torch.nn.Module, kind: str, inputs: SceneInputs,
                frozen: FrozenInputs) -> Any:
    """One no-grad forward for the bound model family."""
    common = dict(channel_order=CHANNELS, environment=inputs.environment,
                  environment_valid=inputs.environment_valid,
                  environment_grid=frozen.grid, environment_keys=MEE_V13_KEYS)
    if kind == 'B4':
        output = model(inputs.x, inputs.native_valid, **common)
    else:
        dynamic = inputs.dynamic_zero if kind == 'B7_ZERO_DOTE' else inputs.dynamic_real
        output = model(inputs.x, inputs.native_valid, dynamic=dynamic,
                       dynamic_valid=inputs.dynamic_valid, dynamic_grid=frozen.grid,
                       **common)
    physical = materialize_physical(output)
    output.conditional_quantiles_physical = physical.conditional_quantiles_physical
    output.threshold_censored_mean = physical.threshold_censored_mean
    return output


def forward_scene(model: torch.nn.Module, kind: str, inputs: SceneInputs,
                  frozen: FrozenInputs, device: torch.device) -> Any:
    """One inference-mode forward under the protocol's CUDA BF16 autocast."""
    with torch.autocast(device_type=device.type, dtype=torch.bfloat16,
                        enabled=device.type == 'cuda'):
        return infer_scene(model, kind, inputs, frozen)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
class FinalTest2025Accumulator:
    """Undivided float64 numerators plus the B0 v1.1 coverage/support diagnostics."""

    def __init__(self) -> None:
        self._base = GlobalValidationAccumulator()
        self.support_violations = 0
        self.scenes = 0
        self._scene_rows: list[dict[str, Any]] = []

    def add(self, output: Any, inputs: SceneInputs) -> None:
        valid = inputs.valid & inputs.region
        if not bool(valid.any()):
            raise ValueError('Validation scene has no valid supervised cell')
        logq = output.conditional_quantiles_log
        if logq.dtype != torch.float64 or logq.shape[1] != 32:
            raise ValueError('FP64 [B,32,H,W] conditional quantiles required')
        q1 = logq[:, :1].movedim(1, -1).squeeze(-1)
        support = int((q1[valid.squeeze(1)] <= math.log1p(.1)).sum())
        self.support_violations += support
        if support:
            raise FloatingPointError('STOP: conditional q1 support violation; no repair')
        crossing = int((logq[:, 1:] <= logq[:, :-1]).sum())
        if crossing:
            raise FloatingPointError('STOP: strict conditional quantile crossing; no repair')
        self.scenes += 1
        self._base.add(output, inputs.rate, inputs.valid, inputs.region)
        self._scene_rows.append({'sample_id': inputs.sample_id,
                                 'N_valid': int(valid.sum()),
                                 'N_rain': int((inputs.rate[valid] > .1).sum())})

    def report(self) -> dict[str, Any]:
        base = self._base.report()
        coverage = np.asarray(base['per_tau_conditional_coverage'], dtype=np.float64)
        tau = (np.arange(1, 33, dtype=np.float64) - .5) / 32
        error = coverage - tau
        q32_bias = float(coverage[-1] - 31.5 / 32)
        return {
            'global_core_loss': base['global_val_core_loss'],
            'occurrence_loss': base['global_L_occ'],
            'quantile_loss': base['global_core_L_qr'],
            'Brier': base['Brier_Score'],
            'AUROC': base['AUROC'],
            'Average_Precision': base['Average_Precision'],
            'conditional_mean_pinball': base['conditional_mean_pinball'],
            'per_tau_pinball': base['per_tau_pinball'],
            '32_tau_conditional_coverage': base['per_tau_conditional_coverage'],
            'coverage_error': {
                'signed': error.tolist(),
                'absolute': np.abs(error).tolist(),
                'mean_absolute': float(np.abs(error).mean()),
            },
            'mean_absolute_coverage_error': float(np.abs(error).mean()),
            'q32_signed_bias': q32_bias,
            'q32_absolute_error': abs(q32_bias),
            'crossing_count': base['strict_crossing_count'],
            'nonfinite_count': base['nonfinite_count'],
            'support_violation_count': self.support_violations,
            'N_valid': base['N_valid'],
            'N_rain': base['N_rain'],
            'prevalence': base['prevalence'],
            'S_occ': base['S_occ'],
            'S_qr': base['S_qr'],
            'coverage_convention': base['coverage_convention'],
            'AUROC_convention': base.get('AUROC_convention'),
            'AP_convention': base.get('AP_convention'),
            'POD': base['POD'], 'FAR': base['FAR'], 'CSI': base['CSI'],
            'DIAGNOSTIC_PROXY_METRIC': base['DIAGNOSTIC_PROXY_METRIC'],
            'numeric_dtype': 'float64',
            'threshold_status': 'THRESHOLD_NOT_FROZEN',
            'scenes': self.scenes,
        }

    def scene_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._scene_rows)


def paired_descriptions(metrics_by: Mapping[tuple[str, int], Mapping[str, Any]]) -> dict[str, Any]:
    """Equal-weight three-seed paired descriptive differences; no inference."""
    pairs: dict[str, Any] = {}
    for label, tier, left, right in COMPARISONS:
        per_metric: dict[str, Any] = {}
        for metric in COMPARISON_METRICS:
            differences = []
            null_seeds = 0
            for seed in SEEDS:
                left_value = metrics_by[(left, seed)].get(metric)
                right_value = metrics_by[(right, seed)].get(metric)
                if (isinstance(left_value, (int, float)) and isinstance(right_value, (int, float))
                        and math.isfinite(float(left_value)) and math.isfinite(float(right_value))):
                    differences.append(float(left_value) - float(right_value))
                else:
                    null_seeds += 1
            per_metric[metric] = {
                'direction': f'{FAMILY[left]}_MINUS_{FAMILY[right]}',
                'per_seed': differences,
                'n_seeds': len(differences),
                'null_seeds': null_seeds,
                'mean': (sum(differences) / len(differences)) if differences else None,
                'inference': 'PAIRED_DESCRIPTIVE_ONLY_NO_INFERENCE',
            }
        pairs[label] = {'tier': tier, 'left': FAMILY[left], 'right': FAMILY[right],
                        'metrics': per_metric}
    return {
        'primary_comparison': 'B7_REAL_MINUS_B7_ZERO_DOTE',
        'co_primary_metrics': list(CO_PRIMARY_METRICS),
        'secondary_comparisons': ['B8_MINUS_B7_REAL', 'B7_REAL_MINUS_B4', 'B8_MINUS_B4'],
        'weighting': 'equal weight across the three frozen seeds; paired within seed',
        'inference_status': 'NOT_FROZEN; DESCRIPTIVE ONLY; NO SIGNIFICANCE VERDICT',
        'pairs': pairs,
    }


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #
def _expected_from_catalogue(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    expected: dict[str, dict[str, Any]] = {}
    for row in rows:
        for slot in range(6):
            path = row[f'slot_{slot:02d}_relative_path']
            expected[path] = {'sha256': row[f'slot_{slot:02d}_sha256'],
                              'bytes': row[f'slot_{slot:02d}_bytes']}
        for modality, path_key, sha_key, bytes_key in (
                ('gfs', 'gfs_main_relative_path', 'gfs_main_sha256', 'gfs_main_bytes'),
                ('gfs', 'gfs_thermo_relative_path', 'gfs_thermo_sha256', 'gfs_thermo_bytes'),
                ('imerg', 'imerg_day_relative_path', 'imerg_sha256', 'imerg_bytes')):
            expected[row[path_key]] = {'sha256': row[sha_key], 'bytes': row[bytes_key]}
    return expected


def validate_scene_population(population: Mapping[str, Any], expected_count: int | None = None) -> list[dict[str, Any]]:
    scenes = list(population['scene_records'])
    if not scenes:
        raise ValueError('Frozen population is empty')
    if expected_count is not None and len(scenes) != expected_count:
        raise ValueError('Frozen population count mismatch')
    if [scene['candidate_index'] for scene in scenes] != list(range(len(scenes))):
        raise ValueError('Population candidate_index is not contiguous')
    ids = [scene['sample_id'] for scene in scenes]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate population sample_id')
    return scenes


def freeze_completed_utc(freeze: Mapping[str, Any]) -> datetime:
    """Parse the freeze record's completion clock (sub-minute precision retained)."""
    if not isinstance(freeze, Mapping) or 'created_utc' not in freeze:
        raise ValueError('Freeze record must carry created_utc')
    return planning.parse_utc(freeze['created_utc'])


def validate_freeze_population_binding(freeze: Mapping[str, Any],
                                       population: Mapping[str, Any],
                                       population_file_sha256: str) -> str:
    """Bind the population manifest file and identity to the freeze record."""
    _hex(population_file_sha256, 'population file SHA')
    frozen_population = freeze.get('population')
    if not isinstance(frozen_population, Mapping) or 'sha256' not in frozen_population:
        raise ValueError('Freeze record must bind the population file SHA')
    if frozen_population['sha256'] != population_file_sha256:
        raise PermissionError('Freeze record population SHA differs from the authorized file')
    if population.get('fixture_only') is not False:
        raise PermissionError('Only a real frozen population can be executed')
    identity = population.get('identity')
    frozen_identity = freeze.get('identity')
    if not isinstance(identity, Mapping) or not isinstance(frozen_identity, Mapping):
        raise ValueError('Freeze and population must both bind a population identity')
    if dict(identity) != dict(frozen_identity):
        raise ValueError('Population identity differs from the frozen catalogue identity')
    identity_sha = manifest.identity_sha256(identity)
    if not isinstance(identity_sha, str) or _HEX.fullmatch(identity_sha) is None:
        raise ValueError('Frozen population identity SHA must be 64-hex')
    return identity_sha


def select_eligible_scenes(population: Mapping[str, Any],
                           rows: Sequence[Mapping[str, Any]],
                           expected_count: Any) -> list[dict[str, Any]]:
    """Return only catalogue-eligible scenes, preserving frozen population order."""
    if type(expected_count) is not int or expected_count <= 0:
        raise ValueError('Frozen eligible count must be a positive integer')
    scenes = validate_scene_population(population)
    eligible: set[str] = set()
    for row in rows:
        flag = row.get('eligible')
        if type(flag) is not bool:
            raise ValueError('Catalogue eligible flag must be a boolean')
        if flag:
            eligible.add(row['sample_id'])
    if len(eligible) != expected_count:
        raise ValueError('Catalogue eligible count differs from the frozen freeze record')
    population_ids = {scene['sample_id'] for scene in scenes}
    if eligible - population_ids:
        raise ValueError('Eligible catalogue samples are missing from the frozen population')
    selected = [scene for scene in scenes if scene['sample_id'] in eligible]
    if len(selected) != expected_count:
        raise ValueError('Eligible population scene count differs from the frozen freeze record')
    for scene in selected:
        planning.validate_scene(scene)
    return selected


def dry_run(authority_path: str | os.PathLike[str], authority_sha256: str | None = None) -> dict[str, Any]:
    """Inspect the authorization and frozen bindings without any payload read."""
    authority = FinalTest2025Authority.load(authority_path, authority_sha256)
    authority.require_final()
    return {
        'status': 'DRY_RUN_AUTHORIZED_NO_PAYLOAD_IO',
        'scope': authority.document['scope'],
        'models': [{'model': model, 'seed': seed,
                   'sha256': authority.checkpoints[(model, seed)]['sha256'],
                   'bytes': authority.checkpoints[(model, seed)]['bytes']}
                   for model in MODELS for seed in SEEDS],
        'checkpoint_bytes_total': sum(int(authority.checkpoints[(model, seed)]['bytes'])
                                     for model in MODELS for seed in SEEDS),
        'output_root': str(authority.output_root),
        'inference': dict(authority.inference),
        'payload_access': 'NOT_REQUESTED_NOT_OPENED',
    }


def execute(authority_path: str | os.PathLike[str], authority_sha256: str | None,
            payload_authorization_path: str | os.PathLike[str],
            payload_authorization_sha256: str, *, output_dir: str | os.PathLike[str],
            progress: Any = None) -> dict[str, Any]:
    """The single authorized 2025 final-test pass.  Not executable in this phase."""
    authority = FinalTest2025Authority.load(authority_path, authority_sha256)
    authority.require_final()
    payload_authorization = readers.PayloadAuthorization2025.load(
        payload_authorization_path, payload_authorization_sha256)
    payload_authorization.require_payload()
    access = readers.PayloadAccess2025(payload_authorization)

    document = authority.document
    catalogue_path = Path(document['catalogue']['path'])
    population_path = Path(document['population']['path'])
    freeze_path = Path(document['freeze']['path'])
    for path, binding_sha, label in (
            (catalogue_path, authority.catalogue_sha256, 'catalogue'),
            (population_path, authority.population_sha256_file, 'population'),
            (freeze_path, authority.freeze_sha256, 'freeze'),
            (authority.protocol_path, authority.protocol_sha256, 'protocol')):
        if sha256_file(path) != binding_sha:
            raise ValueError(f'{label} file SHA differs from the authority binding')
    catalogue.verify_catalogue_bundle_readonly(catalogue_path, population_path, freeze_path)
    freeze = json.loads(freeze_path.read_bytes().decode('utf-8'))
    if freeze.get('status') != 'CATALOGUE_FROZEN' or freeze.get('fixture_only') is not False:
        raise PermissionError('Only a real frozen catalogue can be executed')
    if authority.created_utc < freeze_completed_utc(freeze):
        raise PermissionError('Final-test authority must not precede the catalogue freeze')

    rows = catalogue.read_csv(catalogue_path)
    catalogue.validate_catalogue(rows)
    population = manifest.read_population(population_path)
    validate_freeze_population_binding(freeze, population, authority.population_sha256_file)
    canonical_population = population.get('population_sha256')
    if not isinstance(canonical_population, str) or _HEX.fullmatch(canonical_population) is None:
        raise ValueError('Frozen population must bind a 64-hex canonical population SHA')
    scenes = select_eligible_scenes(population, rows, freeze.get('eligible_count'))
    pins = _expected_from_catalogue(rows)
    frozen = load_frozen_inputs(authority)
    if frozen_statistics_sha(authority) != FROZEN_TRAIN_STATISTICS_SHA:
        raise PermissionError('Frozen train statistics binding mismatch')

    output = Path(output_dir)
    if _forbidden(output) or not output.is_absolute():
        raise PermissionError('Output directory must be a new absolute non-payload path')
    if output.parent.resolve() != authority.output_root.resolve():
        raise PermissionError('Output directory must be a fresh child of the bound output_root')
    output.mkdir(parents=False, exist_ok=False)
    ledger_path = output / 'runtime_ledger.jsonl'
    created = _iso()
    started = time.time()
    try:
        models = {}
        for record in authority.checkpoint_records():
            models[(record['model'], int(record['seed']))] = load_final_model(record, frozen)
        device = torch.device(authority.inference['device'])
        if device.type == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA is required by the bound authority but unavailable')
        for model in models.values():
            model.to(device)
        torch.set_num_threads(int(authority.inference['threads']))
        torch.manual_seed(int(authority.inference['seed']))
        accumulators = {(model, seed): FinalTest2025Accumulator()
                        for model in MODELS for seed in SEEDS}
        with ledger_path.open('x', encoding='utf-8') as ledger, torch.inference_mode():
            for scene in scenes:
                payload = readers.read_scene_payload(access, scene, expected=pins)
                inputs = build_scene_inputs(payload, frozen, device=device)
                for key, model in models.items():
                    result = forward_scene(model, key[0], inputs, frozen, device)
                    accumulators[key].add(result, inputs)
                ledger.write(json.dumps({
                    'sample_id': inputs.sample_id, 'analysis_time': inputs.analysis_time,
                    'opened': access.opened, 'bytes_read': access.bytes_read,
                    'sha256_read': access.sha256_read,
                    'scene_N_valid': int((inputs.valid & inputs.region).sum()),
                }, sort_keys=True) + '\n')
                if progress is not None:
                    progress(scene['candidate_index'], len(scenes))

        metrics_by: dict[tuple[str, int], Mapping[str, Any]] = {}
        for (model, seed), accumulator in accumulators.items():
            report = accumulator.report()
            metrics_by[(model, seed)] = report
            target = output / 'metrics' / f'{model}_{seed}.json'
            target.parent.mkdir(exist_ok=True)
            body = {
                'version': VERSION, 'scope': SCOPE, 'model': model,
                'family': FAMILY[model], 'seed': seed,
                'checkpoint_sha256': authority.checkpoints[(model, seed)]['sha256'],
                'checkpoint_bytes': authority.checkpoints[(model, seed)]['bytes'],
                'population_sha256': canonical_population,
                'identity_sha256': manifest.identity_sha256(population['identity']),
                'metrics': report,
                'metrics_note': 'PRIMARY/METRIC DEFINITIONS FOLLOW B0 V1.1; INFERENCE NOT FROZEN',
                'created_utc': created,
            }
            target.write_text(json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + '\n',
                              encoding='utf-8')
        comparisons = paired_descriptions(metrics_by)
        (output / 'comparisons.json').write_text(
            json.dumps(comparisons, indent=2, sort_keys=True, allow_nan=False) + '\n',
            encoding='utf-8')
        run_manifest = {
            'version': VERSION, 'scope': SCOPE,
            'authority_sha256': authority.sha256,
            'protocol': {'path': str(authority.protocol_path),
                         'sha256': authority.protocol_sha256},
            'implementation': {'files': [{'path': str(p), 'sha256': s}
                                         for p, s in authority.implementation_files],
                               'sha256': authority.document['implementation']['sha256']},
            'catalogue_sha256': authority.catalogue_sha256,
            'population_file_sha256': authority.population_sha256_file,
            'population_sha256': canonical_population,
            'freeze_sha256': authority.freeze_sha256,
            'frozen_inputs': {key: {'path': str(path), 'sha256': sha}
                              for key, (path, sha) in authority.frozen_inputs.items()},
            'b13_normalization_sha256': FROZEN_B13_NORMALIZATION_SHA,
            'dote': dict(authority.document['dote']),
            'checkpoints': [{'model': model, 'seed': seed,
                             'sha256': authority.checkpoints[(model, seed)]['sha256'],
                             'bytes': authority.checkpoints[(model, seed)]['bytes']}
                            for model in MODELS for seed in SEEDS],
            'inference': dict(authority.inference),
            'scenes': len(scenes), 'models': len(models),
            'elapsed_seconds': round(time.time() - started, 1),
            'MODEL_PARAMETERS_UPDATED': False, 'OPTIMIZER_STEPS': 0, 'BACKWARD_CALLS': 0,
            'SELECTION': 'FINAL_ONLY_NO_SELECTION',
            'created_utc': created,
        }
        (output / 'run_manifest.json').write_text(
            json.dumps(run_manifest, indent=2, sort_keys=True, allow_nan=False) + '\n',
            encoding='utf-8')
        status = {
            'status': 'COMPLETED', 'scope': SCOPE, 'created_utc': created,
            'scenes': len(scenes), 'models': len(models),
            'payload_opens': access.opened, 'bytes_read': access.bytes_read,
            'sha256_read': access.sha256_read,
            'MODEL_PARAMETERS_UPDATED': False, 'OPTIMIZER_STEPS': 0,
            'BACKWARD_CALLS': 0, 'SELECTION': 'FINAL_ONLY_NO_SELECTION',
            'STOP_NO_REPAIR_APPLIED': True,
        }
        (output / 'final_status.json').write_text(
            json.dumps(status, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
        return status
    except BaseException as error:  # noqa: BLE001 - failure receipt must survive
        failure = {
            'status': 'STOP_REQUIRED', 'scope': SCOPE,
            'error_type': type(error).__name__, 'error': str(error),
            'payload_opens': access.opened, 'bytes_read': access.bytes_read,
            'created_utc': _iso(),
        }
        (output / 'failure.json').write_text(
            json.dumps(failure, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
        raise


__all__ = [
    'COMPARISONS', 'CO_PRIMARY_METRICS', 'FINAL_METRICS', 'FAMILY', 'MODELS', 'SEEDS',
    'FinalTest2025Accumulator', 'FinalTest2025Authority', 'FrozenInputs', 'SceneInputs',
    'authorize_final_test', 'authorize_payload', 'build_model', 'build_scene_inputs',
    'dry_run', 'execute', 'freeze_completed_utc', 'infer_scene', 'load_final_model',
    'load_frozen_inputs', 'paired_descriptions', 'select_eligible_scenes', 'sha256_file',
    'spectral_population_id', 'validate_freeze_population_binding', 'validate_scene_population', 'VERSION', 'SCOPE',
]
