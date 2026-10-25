"""Minimal DOTE candidate: wind/terrain diagnostic, not true vertical velocity.

No learned module, humidity weighting, level integration, scaling or scientific
default is selected here. Researcher approval is needed for a formal definition.
"""
from dataclasses import dataclass
import numpy as np

from .grid import GridSpec
from .terrain import TerrainFeatures


@dataclass(frozen=True)
class DoteProxy:
    grid: GridSpec
    orographic_proxy_m_s: np.ndarray
    valid: np.ndarray
    above_ground: np.ndarray
    pressure_pa: np.ndarray
    scientific_status: str = "CANDIDATE_DIAGNOSTIC_NOT_VERTICAL_VELOCITY"


def pressure_to_pa(values: np.ndarray, *, unit: str) -> np.ndarray:
    """Only explicit Pa/hPa; no guessing from numeric magnitude."""
    if unit not in ("Pa", "hPa"):
        raise ValueError("Pressure unit must be explicitly Pa or hPa")
    return np.asarray(values, dtype=float) * (100.0 if unit == "hPa" else 1.0)


def above_ground_mask(pressure_levels: np.ndarray, surface_pressure: np.ndarray,
                      *, pressure_unit: str, surface_pressure_unit: str,
                      surface_valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return [...,level,row,col] p_level < p_surface, plus level Pa values.

    Equal pressure is at the ground and excluded. Unknown/nonpositive surface
    pressure is masked; invalid levels raise. No hydrostatic height or pressure
    interpolation is inferred. Surface pressure must share wind's target grid.
    """
    levels = pressure_to_pa(pressure_levels, unit=pressure_unit)
    surface = pressure_to_pa(surface_pressure, unit=surface_pressure_unit)
    valid = np.asarray(surface_valid)
    if levels.ndim != 1 or levels.size == 0 or not np.isfinite(levels).all() or (levels <= 0).any():
        raise ValueError("Finite positive 1D pressure levels required")
    if len(np.unique(levels)) != len(levels):
        raise ValueError("Duplicate pressure levels are ambiguous")
    if surface.ndim < 2 or valid.shape != surface.shape or valid.dtype != bool:
        raise ValueError("Surface pressure [...,row,col] with independent bool validity required")
    surface_good = valid & np.isfinite(surface) & (surface > 0)
    expanded_levels = levels.reshape((1,) * (surface.ndim - 2) + (len(levels), 1, 1))
    above = ((expanded_levels < np.expand_dims(surface, -3))
             & np.expand_dims(surface_good, -3))
    return above, levels


def dote_proxy(terrain: TerrainFeatures, u_east: np.ndarray, v_north: np.ndarray,
               wind_valid: np.ndarray, pressure_levels: np.ndarray,
               surface_pressure: np.ndarray, surface_valid: np.ndarray, *,
               wind_grid: GridSpec, wind_unit: str, pressure_unit: str, surface_pressure_unit: str,
               pressure_valid: np.ndarray | None = None) -> DoteProxy:
    """O=u*dh/dx+v*dh/dnorth in m/s on an already aligned terrain/wind grid.

    Winds [ ...,level,row,col ] are east/north components, never speed/direction.
    The caller must map winds and pressure to terrain.grid before invocation;
    no implicit broadcasting over sample or pressure-level dimensions is allowed.
    Invalid output is NaN, with an independent bool mask for downstream modules.
    """
    if not isinstance(terrain, TerrainFeatures) or wind_unit != "m/s":
        raise ValueError("TerrainFeatures and explicit m/s vector wind required")
    terrain.grid.assert_same(wind_grid)
    u, v, valid = np.asarray(u_east, float), np.asarray(v_north, float), np.asarray(wind_valid)
    shape = (len(terrain.grid.lat), len(terrain.grid.lon))
    if u.ndim < 3 or u.shape != v.shape or u.shape[-2:] != shape or valid.shape != u.shape or valid.dtype != bool:
        raise ValueError("Aligned [...,level,row,col] wind arrays and bool mask required")
    surface_shape = u.shape[:-3] + u.shape[-2:]
    if np.shape(surface_pressure) != surface_shape or np.shape(surface_valid) != surface_shape:
        raise ValueError("Explicit sample-aligned surface pressure/mask required")
    above, levels = above_ground_mask(pressure_levels, surface_pressure,
                                      pressure_unit=pressure_unit,
                                      surface_pressure_unit=surface_pressure_unit,
                                      surface_valid=surface_valid)
    if above.shape != u.shape:
        raise ValueError("Pressure-level count differs from wind level axis")
    good = valid & above & terrain.gradient_valid & np.isfinite(u) & np.isfinite(v)
    if pressure_valid is not None:
        supplied = np.asarray(pressure_valid)
        if supplied.shape != u.shape or supplied.dtype != bool:
            raise ValueError("Pressure validity must be an aligned bool mask")
        good &= supplied
    with np.errstate(invalid="ignore", over="ignore"):
        result = u * terrain.east_gradient + v * terrain.north_gradient
    good &= np.isfinite(result)
    return DoteProxy(terrain.grid, np.where(good, result, np.nan), good, above, levels)
