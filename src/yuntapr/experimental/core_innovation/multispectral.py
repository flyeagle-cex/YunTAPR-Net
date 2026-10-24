"""B2/B3 common input preparation candidate; no model/channel choice is frozen.

Decoded Kelvin arrays and independent masks are supplied by the caller. This
module neither reads raw satellite files nor fits normalization. It inherits
D1/D3/D5/D8 and the B1 six-slot validation rules without declaring B2/B3 arms.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from collections.abc import Mapping, Sequence

import numpy as np

from .grid import GridSpec


def _channels(names):
    result = tuple(names)
    # This adapter handles brightness temperature only. Visible/NIR radiance or
    # reflectance needs its own unit/statistics contract, never a Kelvin scaler.
    allowed = {f'B{i:02d}' for i in range(7, 17)}
    if not result or len(set(result)) != len(result) or any(name not in allowed for name in result):
        raise ValueError('Unique explicit Kelvin thermal Himawari channels B07..B16 required')
    return result


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Timezone-aware observed/analysis datetime required')
    value = value.astimezone(timezone.utc)
    if value.year not in (2023, 2024) or value.month not in range(3, 11):
        raise ValueError('This development interface permits only March-October 2023/2024; 2025 sealed')
    return value


@dataclass(frozen=True)
class TrainNormalization:
    """Caller-provided per-channel Phase-A Train statistics, shared across slots."""
    channel: str
    mean: float
    std: float
    unit: str
    fit_years: tuple[int, ...]
    fit_role: str
    ddof: int
    population_id: str

    def __post_init__(self):
        _channels((self.channel,))
        object.__setattr__(self, 'fit_years', tuple(self.fit_years))
        if self.unit != 'K' or not math.isfinite(self.mean) or not math.isfinite(self.std) or self.std <= 0:
            raise ValueError('Explicit finite Kelvin mean and positive Kelvin standard deviation required')
        if self.fit_years != (2023,) or self.fit_role != 'Train' or self.ddof != 0:
            raise ValueError('Phase-A normalization must use only 2023 Train, population variance ddof=0')
        if not isinstance(self.population_id, str) or not self.population_id.strip():
            raise ValueError('Normalization population provenance required; no implicit B13 reuse')

    @classmethod
    def from_b1_artifact(cls, artifact: Mapping, *, artifact_sha256: str):
        """Explicit adapter for the existing frozen shared B13 JSON, no file I/O.

        The caller must compare the JSON bytes to its pinned registry hash before
        passing this mapping. No constants are silently reused for other bands.
        """
        if len(artifact_sha256) != 64 or any(c not in '0123456789abcdef' for c in artifact_sha256):
            raise ValueError('Pinned lowercase SHA256 identity required')
        if artifact.get('ready') is not True or artifact.get('status') != 'TRAIN_ONLY_FITTED_FROZEN':
            raise ValueError('Frozen ready B1 artifact required')
        if artifact.get('all_six_slots_share_identical_scaler') is not True:
            raise ValueError('B1 artifact must declare a scaler shared over the six slots')
        return cls('B13', artifact['mean_K'], artifact['std_K'], 'K',
                   tuple(artifact['fit_years']), artifact['fit_role'], artifact['ddof'], artifact_sha256)


@dataclass(frozen=True)
class MultispectralBatch:
    values: np.ndarray
    valid: np.ndarray
    channels: tuple[str, ...]
    offsets_before_analysis_minutes: tuple[int, ...]
    grid: GridSpec
    missing_policy: str
    historical_operational_availability_proven: bool = False

    def flatten_time_channels(self):
        """Explicit [B,T,C,H,W] -> [B,T*C,H,W], time-major/channel-minor."""
        batch, time, channels, height, width = self.values.shape
        shape = (batch, time * channels, height, width)
        return self.values.reshape(shape), self.valid.reshape(shape)


def prepare_multispectral(values, source_valid, *, source_channels: Sequence[str],
                          selected_channels: Sequence[str], units: Mapping[str, str],
                          normalization: Mapping[str, TrainNormalization],
                          nominal_times: Sequence[Sequence[datetime]],
                          obs_start_times: Sequence[Sequence[datetime]],
                          obs_end_times: Sequence[Sequence[datetime]],
                          analysis_times: Sequence[datetime],
                          expected_offsets_before_analysis_minutes: Sequence[int],
                          source_grid: GridSpec, expected_grid: GridSpec,
                          missing_policy: str) -> MultispectralBatch:
    """Validate explicit channels, causal history, grid and Train-only scalers.

    missing_policy is either 'reject' or explicitly 'masked_neutral'. The latter
    emits normalized zero at invalid positions AND an independent validity mask;
    callers must supply a compatible mask-aware backbone before scientific use.
    Required channels/frames are never substituted, reordered or interpolated.
    date_created is not accepted as evidence of historical operational release.
    No SP04 pooling occurs here: native feature projection remains downstream.
    """
    channels, selected = _channels(source_channels), _channels(selected_channels)
    if any(channel not in channels for channel in selected):
        raise ValueError('Required channel unavailable; no substitution')
    if not isinstance(source_grid, GridSpec) or not isinstance(expected_grid, GridSpec):
        raise TypeError('Explicit source and expected coordinate grids required')
    expected_grid.assert_same(source_grid)
    if source_grid.lat[0] <= source_grid.lat[-1] or source_grid.lon[0] >= source_grid.lon[-1]:
        raise ValueError('Frozen Himawari native row axis must descend north-to-south; longitude ascend')
    x, valid = np.asarray(values), np.asarray(source_valid)
    if x.ndim != 5 or any(size <= 0 for size in x.shape) or x.dtype.kind != 'f':
        raise ValueError('Decoded floating values [B,T,C,H,W] required')
    if valid.dtype != bool or valid.shape != x.shape:
        raise ValueError('Independent bool validity mask must have identical [B,T,C,H,W] shape')
    if x.shape[2] != len(channels) or x.shape[-2:] != source_grid.shape:
        raise ValueError('Channel/spatial shape does not match explicit metadata')
    offsets = tuple(expected_offsets_before_analysis_minutes)
    if len(offsets) != x.shape[1] or any(type(offset) is not int or offset < 0 for offset in offsets):
        raise ValueError('One explicit nonnegative integer nominal offset required for every time slot')
    if any(a <= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError('Expected offsets must descend strictly: oldest-to-latest time slots')
    if missing_policy not in ('reject', 'masked_neutral'):
        raise ValueError('Explicit missing_policy reject or masked_neutral required')
    if len(analysis_times) != x.shape[0] or any(len(times) != x.shape[0] for times in (nominal_times, obs_start_times, obs_end_times)):
        raise ValueError('Temporal metadata batch size mismatch')
    for batch in range(x.shape[0]):
        analysis = _utc(analysis_times[batch])
        if any(len(times[batch]) != x.shape[1] for times in (nominal_times, obs_start_times, obs_end_times)):
            raise ValueError('Every declared history frame needs nominal/start/end metadata')
        previous_end = None
        for slot, offset in enumerate(offsets):
            nominal = _utc(nominal_times[batch][slot])
            start, end = _utc(obs_start_times[batch][slot]), _utc(obs_end_times[batch][slot])
            if nominal != analysis - timedelta(minutes=offset):
                raise ValueError('Nominal history does not match explicit offsets; no reorder or fallback')
            if start > end or end > analysis or (previous_end is not None and end <= previous_end):
                raise ValueError('Actual observation intervals must be ordered and completed by analysis time')
            previous_end = end
    indices = [channels.index(channel) for channel in selected]
    x, valid = x[:, :, indices, :, :], valid[:, :, indices, :, :].copy()
    if not np.all(np.isfinite(x) | ~valid):
        raise ValueError('Nonfinite observation marked valid; propagate missing mask explicitly')
    if missing_policy == 'reject' and not valid.all():
        raise ValueError('Required channel/frame has missing pixels under reject policy')
    normalized = np.zeros(x.shape, dtype=np.float32)
    for index, channel in enumerate(selected):
        stats = normalization.get(channel)
        if not isinstance(stats, TrainNormalization) or stats.channel != channel or units.get(channel) != stats.unit:
            raise ValueError('Every selected channel needs matching explicit Kelvin Train statistics')
        safe = np.where(valid[:, :, index], x[:, :, index], stats.mean)
        transformed = (safe.astype(np.float64) - stats.mean) / stats.std
        with np.errstate(over='ignore', invalid='ignore'):
            normalized[:, :, index] = transformed.astype(np.float32)
    if not np.isfinite(normalized).all():
        raise FloatingPointError('Nonfinite normalized multispectral tensor')
    return MultispectralBatch(normalized, valid, selected, offsets, source_grid, missing_policy)
