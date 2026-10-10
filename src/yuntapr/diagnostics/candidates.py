"""Unapproved event/terrain candidate mathematics, exercised on synthetic arrays.

No file I/O, predictions, frozen masks, or scientific defaults enter these APIs.
Connected components are descriptive objects, not proof of independent storms.
"""
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class EventRule:
    threshold_mm_h: float
    spatial_connectivity: int
    temporal_radius_cells: int
    cadence_minutes: float

    def __post_init__(self) -> None:
        for v in (self.threshold_mm_h, self.cadence_minutes):
            if isinstance(v, bool) or not math.isfinite(v) or v <= 0:
                raise ValueError("Explicit positive finite threshold/cadence required")
        if type(self.spatial_connectivity) is not int or self.spatial_connectivity not in (4, 8):
            raise ValueError("Connectivity must be exactly 4 or 8")
        if type(self.temporal_radius_cells) is not int or self.temporal_radius_cells < 0:
            raise ValueError("Explicit nonnegative integer temporal radius required")


def event_components(truth: np.ndarray, valid: np.ndarray, times_minutes: np.ndarray,
                     *, rule: EventRule) -> list[dict]:
    """Link same-time neighbors and consecutive observed slots only.

    Temporal links use Chebyshev distance <= the explicit candidate radius.
    Missing time slots are never bridged. Splits/merges belong to one graph
    component. Bounds and missing neighbors flag possible observational censoring.
    """
    y = np.asarray(truth, dtype=float)
    v = np.asarray(valid)
    t = np.asarray(times_minutes, dtype=float)
    if not isinstance(rule, EventRule) or y.ndim != 3 or v.shape != y.shape or v.dtype != bool:
        raise ValueError("[time,row,column] truth and independent bool validity required")
    if any(n == 0 for n in y.shape) or t.shape != (len(y),) or not np.isfinite(t).all() or (np.diff(t) <= 0).any():
        raise ValueError("Nonempty arrays and strictly increasing finite times required")
    if not np.isfinite(y[v]).all() or (y[v] < 0).any():
        raise ValueError("Valid reference rates must be finite nonnegative")
    active = v & (y > rule.threshold_mm_h)
    pending = set(map(tuple, np.argwhere(active)))
    spatial = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
               if (dr or dc) and (rule.spatial_connectivity == 8 or abs(dr) + abs(dc) == 1)]
    temporal = [(dr, dc) for dr in range(-rule.temporal_radius_cells, rule.temporal_radius_cells + 1)
                for dc in range(-rule.temporal_radius_cells, rule.temporal_radius_cells + 1)]
    events = []
    while pending:
        seed = min(pending)
        pending.remove(seed)
        stack, members, censored = [seed], [], False
        while stack:
            z = stack.pop()
            members.append(z)
            k, r, c = z
            neighbors = [(k, r + dr, c + dc) for dr, dc in spatial]
            for dt in (-1, 1):
                kk = k + dt
                if not 0 <= kk < len(t):
                    censored = True
                    continue
                if not math.isclose(abs(t[kk] - t[k]), rule.cadence_minutes, rel_tol=0, abs_tol=1e-9):
                    censored = True
                    continue
                neighbors.extend((kk, r + dr, c + dc) for dr, dc in temporal)
            for nb in neighbors:
                kk, rr, cc = nb
                if not (0 <= rr < y.shape[1] and 0 <= cc < y.shape[2]):
                    censored = True
                    continue
                if not v[nb]:
                    censored = True
                if nb in pending:
                    pending.remove(nb)
                    stack.append(nb)
        members.sort()
        idx = tuple(np.array(members).T)
        slots = sorted({m[0] for m in members})
        events.append({"candidate_id": len(events) + 1, "members": members,
                       "exposures": len(members), "unique_cells": len({m[1:] for m in members}),
                       "observed_slots": len(slots), "start_minutes": float(t[slots[0]]),
                       "end_minutes": float(t[slots[-1]] + rule.cadence_minutes),
                       "peak_reference_mm_h": float(y[idx].max()), "censored": censored,
                       "scientific_status": "RESEARCHER_DECISION_REQUIRED",
                       "independence_established": False})
    return events


def terrain_fields(elevation_m: np.ndarray, valid: np.ndarray, *, dx_m: float,
                   dy_m: float, relief_radius_cells: int) -> dict[str, np.ndarray]:
    """North-up metric grid: columns east, rows south; central differences.

    Aspect is downslope azimuth clockwise from north; flat terrain has NaN aspect.
    Relief requires a complete valid square window. Border derivatives are NaN.
    This is a synthetic stencil reference, not a geospatial resampling pipeline.
    """
    z, v = np.asarray(elevation_m, dtype=float), np.asarray(valid)
    if z.ndim != 2 or min(z.shape) < 3 or v.shape != z.shape or v.dtype != bool:
        raise ValueError("At least 3x3 elevation and independent bool validity required")
    if not np.isfinite(z[v]).all():
        raise ValueError("Nonfinite valid elevation")
    for spacing in (dx_m, dy_m):
        if isinstance(spacing, bool) or not math.isfinite(spacing) or spacing <= 0:
            raise ValueError("Explicit finite positive metric spacing required")
    if type(relief_radius_cells) is not int or relief_radius_cells < 1:
        raise ValueError("Explicit positive integer relief radius required")
    gx, gn, relief = [np.full(z.shape, np.nan) for _ in range(3)]
    stencil = v[1:-1, 1:-1] & v[1:-1, :-2] & v[1:-1, 2:] & v[:-2, 1:-1] & v[2:, 1:-1]
    gx[1:-1, 1:-1] = np.where(stencil, (z[1:-1, 2:] - z[1:-1, :-2]) / (2 * dx_m), np.nan)
    gn[1:-1, 1:-1] = np.where(stencil, (z[:-2, 1:-1] - z[2:, 1:-1]) / (2 * dy_m), np.nan)
    slope = np.degrees(np.arctan(np.hypot(gx, gn)))
    aspect = np.degrees(np.arctan2(-gx, -gn)) % 360
    aspect[np.hypot(gx, gn) == 0] = np.nan
    rad = relief_radius_cells
    for r in range(rad, len(z) - rad):
        for c in range(rad, z.shape[1] - rad):
            window = np.s_[r-rad:r+rad+1, c-rad:c+rad+1]
            if v[window].all():
                relief[r, c] = np.ptp(z[window])
    return {"east_gradient": gx, "north_gradient": gn, "slope_degrees": slope,
            "aspect_degrees": aspect, "relief_m": relief}


def wind_upslope_proxy(fields: dict[str, np.ndarray], *, u_east_m_s: np.ndarray,
                       v_north_m_s: np.ndarray) -> np.ndarray:
    """u*dz/dx + v*dz/dnorth, m/s; diagnostic proxy, no actual ascent claim."""
    u, v = np.asarray(u_east_m_s, dtype=float), np.asarray(v_north_m_s, dtype=float)
    shape = fields["east_gradient"].shape
    if u.shape != shape or v.shape != shape:
        raise ValueError("Aligned explicit wind arrays required")
    return u * fields["east_gradient"] + v * fields["north_gradient"]


def fixed_strata(values: np.ndarray, valid: np.ndarray, *, internal_edges: tuple[float, ...]) -> np.ndarray:
    """Predeclared [left,right) strata; -1 for invalid/nonfinite cells."""
    x, v, edges = np.asarray(values, dtype=float), np.asarray(valid), np.asarray(internal_edges, dtype=float)
    if v.shape != x.shape or v.dtype != bool or edges.ndim != 1 or not np.isfinite(edges).all() or (np.diff(edges) <= 0).any():
        raise ValueError("Bool mask and finite strictly increasing edges required")
    result = np.full(x.shape, -1, dtype=np.int64)
    good = v & np.isfinite(x)
    result[good] = np.searchsorted(edges, x[good], side="right")
    return result


def require_same_grid(source_x: np.ndarray, source_y: np.ndarray, target_x: np.ndarray,
                      target_y: np.ndarray, *, absolute_tolerance: float) -> None:
    """Reject misaligned cell-center axes; coordinates must already share a CRS.

    Synthetic registration check only. CRS, datum, bounds, cell areas and frozen
    target manifest must be independently bound before any real DEM aggregation.
    """
    if isinstance(absolute_tolerance, bool) or not math.isfinite(absolute_tolerance) or absolute_tolerance < 0:
        raise ValueError("Explicit finite nonnegative coordinate tolerance required")
    for source, target in ((source_x, target_x), (source_y, target_y)):
        a, b = np.asarray(source, float), np.asarray(target, float)
        if a.ndim != 1 or len(a) < 2 or a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
            raise ValueError("Finite matching 1D cell-center axes required")
        da, db = np.diff(a), np.diff(b)
        if not ((da > 0).all() or (da < 0).all()) or not ((db > 0).all() or (db < 0).all()):
            raise ValueError("Strict monotonic axes required")
        if not np.allclose(a, b, rtol=0, atol=absolute_tolerance):
            raise ValueError("Cell-center grid mismatch; never silently flip or resample")
