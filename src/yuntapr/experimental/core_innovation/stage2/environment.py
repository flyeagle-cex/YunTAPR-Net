"""Explicit Train-only MEE scaling adapter; does not fit real-data statistics."""
from dataclasses import dataclass
import numpy as np
from . import MEE_KEYS, MEE_V13_KEYS

UNITS = ('kg m-2', 'J/kg', 'K', 'K', '%', '%', 'm/s', 'm/s', 'm/s', 'm/s', 'Pa')
V13_UNITS = (*UNITS, 'K', '%')


@dataclass(frozen=True)
class EnvironmentScaler:
    key: str
    mean: float
    std: float
    unit: str
    fit_years: tuple[int, ...]
    fit_role: str
    population_id: str

    def __post_init__(self):
        if (self.key not in MEE_V13_KEYS or self.unit != V13_UNITS[MEE_V13_KEYS.index(self.key)]
            or tuple(self.fit_years) != (2023,) or self.fit_role != 'Train' or not self.population_id
            or not np.isfinite(self.mean) or not np.isfinite(self.std) or self.std <= 0):
            raise ValueError('Explicit matching units and finite 2023 Train-only environment scaler required')


def prepare_mee(frame, *, target_grid, scalers, keys=MEE_KEYS):
    """Caller chooses/fits frozen scalers; outputs neutral values + separate masks.

    The spatial mapping remains the explicit bilinear candidate. This adapter
    neither adopts a GFS source nor supplies historical publication evidence.
    """
    keys=tuple(keys)
    if keys not in (MEE_KEYS,MEE_V13_KEYS) or set(frame.fields) != set(keys) or set(scalers) != set(keys):
        raise ValueError('Only the explicit eleven/thirteen candidate channels allowed')
    if len({s.population_id for s in scalers.values()}) != 1:
        raise ValueError('Environment scalers must use one declared Train population')
    mapped = frame.on_grid(target_grid, operator='bilinear_point_candidate')
    x, valid = mapped.stack(keys); out = np.zeros_like(x, dtype=np.float32)
    for i, key in enumerate(keys):
        s = scalers[key]
        if not isinstance(s, EnvironmentScaler) or s.key != key or mapped.fields[key].unit != s.unit:
            raise ValueError('Scaler/channel/physical unit mismatch')
        out[i] = ((np.where(valid[i], x[i], s.mean)-s.mean)/s.std).astype(np.float32)
    if not np.isfinite(out).all(): raise FloatingPointError('MEE normalized overflow')
    return out, valid, keys
