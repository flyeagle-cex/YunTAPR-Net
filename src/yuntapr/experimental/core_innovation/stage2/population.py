"""Strict seven-band reader, joint eligibility and exposure-weighted Train moments.

No raw-directory scan, inferred missing band, automatic scaler fit or population
freeze. Evidence entries must come from actual per-frame seven-band decoding.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
import numpy as np
from ..grid import GridSpec
from ..gfs import parse_utc, utc
from ..multispectral import TrainNormalization
from yuntapr.data.himawari_b13 import decode_b13, _cf_time
from . import CHANNELS, OFFSETS
from .coupling import TargetBinding


def read_seven_band(path, *, nominal, mapping, max_bytes=8*1024**2):
    """One bounded file, frozen native axes, same raw FP32 decoding as B13.

    No precipitation file is opened. Caller supplies an explicitly selected path.
    Converted date_created is provenance, never historical publication proof.
    """
    from netCDF4 import Dataset
    nominal = parse_utc(nominal) if isinstance(nominal, str) else nominal
    nominal = utc(nominal)
    if nominal.tzinfo is None or nominal.year not in (2023, 2024) or not 3 <= nominal.month <= 10:
        raise PermissionError('Authorized 2023/2024 date required before I/O')
    p = Path(path)
    token = nominal.strftime('%Y%m%d_%H%M')
    if token not in p.name or '2025' in p.parts or not re.fullmatch(r'NC_H\d{2}_\d{8}_\d{4}_R\d{2}_FLDK\.06001_06001\.nc', p.name):
        raise PermissionError('Explicit source identity required')
    resolved = p.resolve(strict=True)
    if resolved.name != p.name or '2025' in resolved.parts:
        raise PermissionError('Resolved source differs')
    before = resolved.stat()
    if not 0 < before.st_size <= max_bytes <= 8*1024**2:
        raise ValueError('Small per-file byte cap required')
    with resolved.open('rb') as f:
        raw = f.read(max_bytes+1)
    after = resolved.stat()
    if len(raw) != before.st_size or len(raw) > max_bytes or (before.st_ino, before.st_mtime_ns, before.st_size) != (after.st_ino, after.st_mtime_ns, after.st_size):
        raise IOError('Source changed during read')
    values, masks = [], []
    with Dataset('bounded_seven_band.nc', mode='r', memory=raw) as ds:
        ds.set_auto_maskandscale(False)
        mapping.assert_axes(np.asarray(ds['latitude'][:]), np.asarray(ds['longitude'][:]),
                            mapping.axes['target_lat'], mapping.axes['target_lon'])
        for channel in CHANNELS:
            name = 'tbb_'+channel[1:]
            if name not in ds.variables:
                raise ValueError('Required band missing: '+channel)
            var = ds[name]
            if var.dimensions != ('latitude', 'longitude') or var.shape != (501, 501) or var.units != 'K':
                raise ValueError('Band grid/units mismatch: '+channel)
            x, valid = decode_b13(np.asarray(var[:]), {k: var.getncattr(k) for k in var.ncattrs()})
            values.append(x); masks.append(valid)
        start, end = _cf_time(ds, 'start_time'), _cf_time(ds, 'end_time')
        created = getattr(ds, 'date_created', None)
    return np.stack(values), np.stack(masks), {
        'nominal': nominal.isoformat(), 'obs_start': start.isoformat(), 'obs_end': end.isoformat(),
        'source_sha256': hashlib.sha256(raw).hexdigest(), 'bytes_read': len(raw),
        'channels': list(CHANNELS), 'full_valid': [bool(m.all()) for m in masks],
        'units': ['K']*7, 'date_created': created, 'historical_release_established': False,
        'native_grid_id': GridSpec(mapping.axes['native_lat'], mapping.axes['native_lon']).identity}


def joint_population(records, frame_evidence, *, native_grid_id):
    """Intersection within inherited B1 population, with explicit failure ledger.

    Missing seven-band evidence is unverified, not a pass. Scene IDs retain the
    inherited targets. Does not claim to discover all possible B3 scenes.
    """
    accepted, rejected, seen = [], {}, set()
    for row in records:
        sid = row['sample_id']
        if sid in seen:
            raise ValueError('Duplicate scene identity')
        seen.add(sid)
        analysis = parse_utc(row['analysis_time']); start = parse_utc(row['window_start'])
        if any(t.year not in (2023, 2024) or not 3 <= t.month <= 10 for t in (start, analysis)):
            raise PermissionError('Authorized 2023/2024 population required before evidence join')
        if sid != row['window_start'] or row['role'] != ('Train' if start.year == 2023 else 'Validation'):
            raise ValueError('Inherited scene identity/role changed')
        failures, frames, nominal = [], [], []
        for i, offset in enumerate(OFFSETS):
            key = row[f'slot_{i}_nominal']; nominal.append(parse_utc(key))
            evidence = frame_evidence.get(key)
            if evidence is None:
                failures.append(f'SLOT_{i}_SEVEN_BAND_UNVERIFIED'); continue
            if (tuple(evidence['channels']) != CHANNELS or evidence['full_valid'] != [True]*7
                or evidence['units'] != ['K']*7 or evidence['native_grid_id'] != native_grid_id
                or not re.fullmatch('[0-9a-f]{64}', evidence['source_sha256'])
                or parse_utc(evidence['nominal']) != nominal[-1]):
                failures.append(f'SLOT_{i}_JOINT_VALIDITY_REJECT'); continue
            frames.append(evidence)
        if not failures:
            try:
                TargetBinding(start, analysis, tuple(nominal),
                              tuple(parse_utc(f['obs_start']) for f in frames),
                              tuple(parse_utc(f['obs_end']) for f in frames))
            except (ValueError, PermissionError) as exc:
                failures.append(str(exc))
        if failures:
            rejected[sid] = failures
        else:
            accepted.append(sid)
    digest = hashlib.sha256(json.dumps(sorted(accepted), separators=(',', ':')).encode()).hexdigest()
    return {'accepted_ids': accepted, 'rejected': rejected, 'population_sha256': digest,
            'inherited_B1_candidates': len(seen), 'same_population_as_B1': len(accepted) == len(seen),
            'joint_evidence_complete': len(accepted) == len(seen) and bool(accepted),
            'formal_ready': False,
            'scope': 'B1_INTERSECTION_CANDIDATE_NOT_A_NEW_POPULATION_FREEZE'}


def prepare_b3_scene(row, values, valid, evidence, *, normalization, native_grid):
    """Connect six actual decoded frames to the inherited normalization adapter.

    No file I/O, no fitting and no temporal substitution. The caller must retain
    the source-bound frame evidence and use the same population for B3/B4.
    """
    from ..multispectral import prepare_multispectral
    if len(evidence) != 6:
        raise ValueError('Exactly six actual seven-band frame receipts required')
    if tuple(r['nominal'] for r in evidence) != tuple(row[f'slot_{i}_nominal'] for i in range(6)):
        raise ValueError('Values and receipts must preserve inherited slot order')
    frames = {r['nominal']: r for r in evidence}
    population = joint_population([row], frames, native_grid_id=native_grid.identity)
    if not population['joint_evidence_complete']:
        raise ValueError('B3 scene lacks joint seven-channel evidence')
    ordered = [frames[row[f'slot_{i}_nominal']] for i in range(6)]
    return prepare_multispectral(np.asarray(values)[None], np.asarray(valid)[None],
        source_channels=CHANNELS, selected_channels=CHANNELS, units={c: 'K' for c in CHANNELS},
        normalization=normalization, nominal_times=[[parse_utc(r['nominal']) for r in ordered]],
        obs_start_times=[[parse_utc(r['obs_start']) for r in ordered]],
        obs_end_times=[[parse_utc(r['obs_end']) for r in ordered]], analysis_times=[parse_utc(row['analysis_time'])],
        expected_offsets_before_analysis_minutes=OFFSETS, source_grid=native_grid,
        expected_grid=native_grid, missing_policy='reject')


class TrainMoments:
    """Streaming six-slot exposure weighting; caller supplies each scene once.

    Full native valid pixels only, ddof=0, six new channels. No B13 refit. A
    partial run cannot export formal scalers: declared expected IDs must match.
    """
    def __init__(self, expected_scene_ids, *, population_id):
        ids = tuple(expected_scene_ids)
        if not ids or len(set(ids)) != len(ids) or not population_id:
            raise ValueError('Nonempty explicit unique Train population required')
        if any(parse_utc(s).year != 2023 or not 3 <= parse_utc(s).month <= 10 for s in ids):
            raise PermissionError('2023 Train only')
        self.expected = set(ids); self.population_id = population_id; self.seen = set()
        self.n = 0; self.mean = np.zeros(6); self.m2 = np.zeros(6)

    def update(self, sample_id, values, valid, *, channels, role):
        if sample_id not in self.expected or sample_id in self.seen or role != 'Train':
            raise ValueError('Only once per declared 2023 Train scene')
        x, mask = np.asarray(values), np.asarray(valid)
        if tuple(channels) != CHANNELS or x.ndim != 4 or x.shape[:2] != (6, 7) or mask.shape != x.shape or mask.dtype != bool or not mask.all() or not np.isfinite(x).all():
            raise ValueError('Six full-valid seven-channel scene slots required')
        selected = x[:, [0, 1, 2, 3, 5, 6]].transpose(1, 0, 2, 3).reshape(6, -1).astype(np.float64)
        count = selected.shape[1]; mean = selected.mean(1); m2 = ((selected-mean[:, None])**2).sum(1)
        delta = mean-self.mean; total = self.n+count
        self.m2 += m2+delta**2*(self.n*count/total)
        self.mean += delta*(count/total); self.n = total; self.seen.add(sample_id)

    def finish(self, *, frozen_b13):
        if self.seen != self.expected:
            raise ValueError('Incomplete declared Train population; no formal scalers')
        if not isinstance(frozen_b13, TrainNormalization) or frozen_b13.channel != 'B13':
            raise ValueError('Frozen B13 scaler adapter required')
        new = [c for c in CHANNELS if c != 'B13']
        result = {c: TrainNormalization(c, float(m), float(np.sqrt(v/self.n)), 'K',
                                       (2023,), 'Train', 0, self.population_id)
                  for c, m, v in zip(new, self.mean, self.m2)}
        return {**result, 'B13': frozen_b13}
