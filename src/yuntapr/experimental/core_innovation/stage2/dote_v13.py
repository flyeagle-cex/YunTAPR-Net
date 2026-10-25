"""V1.3 O/W/L/M candidates, retaining explicit scientific alternatives."""
from dataclasses import dataclass
import numpy as np
from ..dote import DoteProxy
from ..terrain import TerrainFeatures, physical_spacing
from ..grid import GridSpec


@dataclass(frozen=True)
class DynamicTerrainCandidate:
    grid: GridSpec
    O: np.ndarray
    W: np.ndarray
    L: np.ndarray
    M: np.ndarray
    valid: np.ndarray
    moisture_valid: np.ndarray
    pressure_pa: np.ndarray
    definition: dict

    def stack(self):
        """Identical explicit B7/B8 payload: O850,O700,W850,W700,L850,L700,M850,M700."""
        values = np.concatenate((self.O, self.W, self.L, self.M), axis=-3)
        masks = np.concatenate((self.valid, self.valid, self.valid, self.moisture_valid), axis=-3)
        return values, masks, ('O850', 'O700', 'W850', 'W700', 'L850', 'L700', 'M850', 'M700')


def complete_dote(proxy: DoteProxy, pwat, pwat_valid, *, pwat_grid, pwat_unit,
                  pwat_reference_kg_m2, reference_provenance, moisture_basis):
    """W=max(O,0), L=max(-O,0); M=(PWAT/reference)*(O or W).

    Reference must be explicit positive physical scale or approved Train-only
    scale. No clipping, z-score, humidity substitution or hidden fitting.
    """
    proxy.grid.assert_same(pwat_grid)
    if tuple(proxy.pressure_pa) != (85000., 70000.):
        raise ValueError('Explicit 850/700 hPa order required')
    if pwat_unit not in ('kg/m2', 'kg m-2') or not np.isfinite(pwat_reference_kg_m2) or pwat_reference_kg_m2 <= 0 or not reference_provenance:
        raise ValueError('Explicit positive PWAT reference and provenance required')
    if moisture_basis not in ('signed_O', 'windward_W'):
        raise ValueError('Researcher must choose signed_O or windward_W candidate')
    p, pm = np.asarray(pwat, float), np.asarray(pwat_valid)
    expected = proxy.orographic_proxy_m_s.shape
    if p.shape != expected[:-3]+expected[-2:] or pm.shape != p.shape or pm.dtype != bool:
        raise ValueError('PWAT sample/grid shape must agree, no hidden broadcast')
    if not np.isfinite(p[pm]).all() or (p[pm] < 0).any():
        raise ValueError('Nonfinite/negative valid PWAT')
    O = proxy.orographic_proxy_m_s.copy(); W = np.maximum(O, 0.); L = np.maximum(-O, 0.)
    mvalid = proxy.valid & np.expand_dims(pm, -3)
    basis = O if moisture_basis == 'signed_O' else W
    with np.errstate(invalid='ignore', over='ignore'):
        M = basis*np.expand_dims(np.where(pm, p/pwat_reference_kg_m2, 0.), -3)
    if not np.isfinite(M[mvalid]).all():
        raise FloatingPointError('Moisture candidate overflow')
    return DynamicTerrainCandidate(proxy.grid, O, W, L, np.where(mvalid, M, np.nan),
        proxy.valid.copy(), mvalid, proxy.pressure_pa.copy(),
        {'status': 'CANDIDATE_NOT_VALIDATED_VERTICAL_VELOCITY', 'W': 'max(O,0)', 'L': 'max(-O,0)',
         'M_basis': moisture_basis, 'PWAT_reference_kg_m2': float(pwat_reference_kg_m2),
         'reference_provenance': reference_provenance})


def aggregate_native_terrain(features: TerrainFeatures, target: GridSpec, *,
                             footprint_degrees, boundary_rule):
    """Area-weight native metric gradient components within explicit footprints.

    Footprints are rectangles centred on target axes. Area weights use WGS84
    native-centre quadrature, not exact fractional cell-overlap integration.
    Gradients precede aggregation; angles are recomputed.
    A full valid stencil and complete footprint coverage are required. Caller
    supplies one-cell derivative halo; tile edges are never treated as flat.
    No rescaling of gradient by footprint size and no angular-gradient shortcut.
    """
    if boundary_rule != 'require_complete_native_stencils':
        raise ValueError('Only explicit complete-support candidate implemented')
    if not np.isfinite(footprint_degrees) or footprint_degrees <= 0:
        raise ValueError('Explicit footprint width in degrees required')
    source = features.grid; east, north = physical_spacing(source)
    dx = np.empty(source.shape); dy = np.empty(source.shape)
    dx[:, 1:-1] = (abs(east[:, :-1])+abs(east[:, 1:]))/2
    dx[:, 0] = abs(east[:, 0]); dx[:, -1] = abs(east[:, -1])
    dy[1:-1] = (abs(north[:-1])+abs(north[1:]))/2
    dy[0] = abs(north[0]); dy[-1] = abs(north[-1])
    area = dx*dy; half = footprint_degrees/2
    arrays = [np.full(target.shape, np.nan) for _ in range(3)]
    good = np.zeros(target.shape, bool)
    # Complete centre coverage also requires gradient halo (strictly interior).
    for i, lat in enumerate(target.lat):
        rr = np.flatnonzero((source.lat >= lat-half) & (source.lat < lat+half))
        for j, lon in enumerate(target.lon):
            cc = np.flatnonzero((source.lon >= lon-half) & (source.lon < lon+half))
            if (not len(rr) or not len(cc) or lat-half < min(source.lat) or lat+half > max(source.lat)
                or lon-half < min(source.lon) or lon+half > max(source.lon)):
                continue
            ix = np.ix_(rr, cc)
            if not (features.gradient_valid[ix] & features.elevation_valid[ix]).all():
                continue
            w = area[ix]; w = w/w.sum()
            for out, src in zip(arrays, (features.elevation_m, features.east_gradient, features.north_gradient)):
                out[i, j] = np.sum(src[ix]*w)
            good[i, j] = True
    elevation, gx, gn = arrays; mag = np.hypot(gx, gn); av = good & (mag > 0)
    aspect = np.where(av, np.degrees(np.arctan2(-gx, -gn)) % 360., np.nan)
    return TerrainFeatures(target, elevation, good.copy(), gx, gn, good,
                           np.degrees(np.arctan(mag)), aspect, av)
