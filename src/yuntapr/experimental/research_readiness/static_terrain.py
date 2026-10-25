"""B5/B6 target-grid residual candidates; no DEM production or formal launch.

Footprint, aggregation order, source vertical datum and normalization must be
reviewed separately. No interpolation, nearest fill or mask shrink occurs here.
"""
from dataclasses import dataclass
import numpy as np
import torch
from torch import nn
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.terrain import TerrainFeatures, DemWindow
from yuntapr.experimental.core_innovation.stage2 import CHANNELS, MEE_V13_KEYS

B6_CHANNELS = ('elevation_m', 'east_gradient', 'north_gradient', 'slope_degrees', 'aspect_sin', 'aspect_cos')
UNITS = ('m', 'm/m', 'm/m', 'degree', '1', '1')


@dataclass(frozen=True)
class StaticPack:
    grid: GridSpec
    values: np.ndarray
    valid: np.ndarray
    region: np.ndarray
    channels: tuple
    units: tuple
    source_sha256: str
    aggregation_rule: str


def pack_terrain(features: TerrainFeatures, *, kind, region, expected_grid,
                 source_sha256, aggregation_rule):
    expected_grid.assert_same(features.grid)
    r = np.asarray(region)
    if (kind not in ('B5', 'B6') or r.dtype != bool or r.shape != features.grid.shape
            or not r.any() or len(source_sha256) != 64
            or any(c not in '0123456789abcdef' for c in source_sha256)
            or not aggregation_rule):
        raise ValueError('Explicit terrain kind, grid, region and production provenance required')
    for mask in (features.elevation_valid, features.gradient_valid, features.aspect_valid):
        if mask.shape != r.shape or mask.dtype != bool:
            raise ValueError('Independent aligned boolean terrain masks required')
    for value in (features.elevation_m, features.east_gradient, features.north_gradient,
                  features.slope_degrees, features.aspect_degrees):
        if value.shape != r.shape:
            raise ValueError('Aligned terrain arrays required')
    required = features.elevation_valid.copy()
    if kind == 'B6':
        required &= features.gradient_valid
    if not required[r].all():
        raise ValueError('Terrain holes inside Yunnan; do not shrink the supervision mask')
    values = [features.elevation_m]
    valid = [features.elevation_valid]
    if kind == 'B6':
        angle = np.radians(np.where(features.aspect_valid, features.aspect_degrees, 0.))
        values.extend([features.east_gradient, features.north_gradient, features.slope_degrees,
                       np.where(features.aspect_valid, np.sin(angle), 0.),
                       np.where(features.aspect_valid, np.cos(angle), 0.)])
        valid.extend([features.gradient_valid]*3 + [features.aspect_valid]*2)
    v, m = np.stack(values), np.stack(valid)
    if not np.isfinite(v[m]).all():
        raise ValueError('Nonfinite valid terrain')
    return StaticPack(features.grid, np.where(m, v, 0.).astype(np.float32), m,
                      r.copy(), B6_CHANNELS[:len(values)], UNITS[:len(values)],
                      source_sha256, aggregation_rule)


def join_north_south(north: DemWindow, south: DemWindow, *, max_cells=65536):
    """Bounded halo join; refuse inconsistent shared edges, never seam-average."""
    a, b = north.grid, south.grid
    if (type(max_cells) != int or not 0 < max_cells <= 65536
            or not np.array_equal(a.lon, b.lon) or a.lat[0] <= a.lat[-1]
            or b.lat[0] <= b.lat[-1] or a.lat[-1] != b.lat[0]
            or len(a.lon)*(len(a.lat)+len(b.lat)-1) > max_cells):
        raise ValueError('Bounded aligned north-to-south grids sharing exactly one edge required')
    for tile in (north, south):
        if (tile.valid.dtype != bool or tile.valid.shape != tile.grid.shape
                or tile.elevation_m.shape != tile.grid.shape
                or not np.isfinite(tile.elevation_m[tile.valid]).all()):
            raise ValueError('Aligned finite valid DEM tiles required')
    am, bm = north.valid[-1], south.valid[0]
    if not np.array_equal(am, bm) or np.any(north.elevation_m[-1, am] != south.elevation_m[0, bm]):
        raise ValueError('Shared-edge mismatch; no inferred repair')
    return DemWindow(GridSpec(np.concatenate((a.lat, b.lat[1:])), a.lon),
                     np.concatenate((north.elevation_m, south.elevation_m[1:]), axis=0),
                     np.concatenate((north.valid, south.valid[1:]), axis=0))


def fit_static_train_scalers(pack, *, fit_role, fit_years, train_region, population_sha256):
    # A static pixel is counted once, not once per training scene.
    if (fit_role != 'Train' or tuple(fit_years) != (2023,)
            or not np.array_equal(train_region, pack.region) or len(population_sha256) != 64):
        raise ValueError('2023 Train spatial support and pinned population required')
    scales = []
    for value, valid in zip(pack.values, pack.valid):
        a = value[valid & pack.region].astype(np.float64)
        if not len(a):
            raise ValueError('No valid training support for terrain channel')
        mean, std = float(a.mean()), float(a.std())
        scales.append(dict(mean=mean, std=std if std > 0 else 1., n_unique_pixels=len(a),
                           constant_channel=std == 0))
    return dict(channels=list(pack.channels), scales=scales, fit_role='Train', fit_years=[2023],
                population_sha256=population_sha256, source_sha256=pack.source_sha256,
                grid_sha256=pack.grid.identity, aggregation_rule=pack.aggregation_rule)


class StaticAdapter(nn.Module):
    def __init__(self, pack, scalers, *, width):
        super().__init__()
        if (type(width) != int or width < 1 or scalers['channels'] != list(pack.channels)
                or scalers['fit_role'] != 'Train' or scalers['fit_years'] != [2023]
                or scalers['source_sha256'] != pack.source_sha256
                or scalers['grid_sha256'] != pack.grid.identity
                or scalers['aggregation_rule'] != pack.aggregation_rule
                or len(scalers['scales']) != len(pack.channels)):
            raise ValueError('Explicit width and matching Train-only terrain statistics required')
        z = np.empty_like(pack.values)
        for i, s in enumerate(scalers['scales']):
            if not np.isfinite([s['mean'], s['std']]).all() or s['std'] <= 0:
                raise ValueError('Finite positive static scaler required')
            z[i] = np.where(pack.valid[i], (pack.values[i]-s['mean'])/s['std'], 0.)
        self.grid = pack.grid
        self.channels = pack.channels
        self.register_buffer('values', torch.from_numpy(z[None].copy()))
        self.register_buffer('valid', torch.from_numpy(pack.valid[None].copy()))
        self.register_buffer('region', torch.from_numpy(pack.region[None, None].copy()))
        self.encoder = nn.Sequential(nn.Conv2d(2*len(pack.channels), width, 3, padding=1), nn.GELU(),
                                     nn.Conv2d(width, width, 3, padding=1), nn.GELU())
        self.output = nn.Conv2d(width, 48, 1)
        nn.init.zeros_(self.output.weight)
        nn.init.zeros_(self.output.bias)

    def forward(self, batch_size):
        if type(batch_size) != int or batch_size < 1:
            raise ValueError('Positive batch size required')
        inputs = torch.cat((self.values, self.valid.to(self.values.dtype)), 1)
        addition = self.output(self.encoder(inputs))
        return torch.where(self.region, addition, 0.).expand(batch_size, -1, -1, -1)


class StaticTerrainCandidate(nn.Module):
    """Attach only to a fresh B4; shared weights can be checked exactly."""
    def __init__(self, b4, pack, scalers, *, kind, width):
        super().__init__()
        expected = ('elevation_m',) if kind == 'B5' else B6_CHANNELS if kind == 'B6' else None
        if b4.kind != 'B4' or pack.channels != expected or b4.mee.keys != MEE_V13_KEYS:
            raise ValueError('Fresh MEE13 B4 and explicit B5/B6 channel selection required')
        b4.grid.assert_same(pack.grid)
        self.base = b4
        self.static = StaticAdapter(pack, scalers, width=width)
        self.kind = kind

    def forward(self, x, valid, *, channel_order, environment, environment_valid,
                environment_grid, environment_keys):
        b = self.base
        b.grid.assert_same(environment_grid)
        if (tuple(channel_order) != CHANNELS or x.shape[1:] != (42, 501, 501)
                or valid.shape != x.shape or valid.dtype != torch.bool
                or valid.device != x.device or not valid.all() or not torch.isfinite(x).all()
                or environment.shape != (len(x), 13, 100, 100)):
            raise ValueError('Inherited strict B4 input contract required')
        target = b.projection(b.backbone(x))
        addition, used = b.mee(environment, environment_valid, keys=environment_keys)
        out = b.heads(target + addition + self.static(len(x)))
        out.target_feature_shape = tuple(target.shape)
        out.target_support_fraction = b.projection.support_fraction(valid.all(1, keepdim=True))
        out.environment_used = used
        return out
