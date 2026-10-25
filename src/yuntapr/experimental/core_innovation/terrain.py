"""Candidate terrain interface: WGS84 physical distances, explicit masks.

Reuses Stage 0's east/north and downslope-azimuth conventions. Distances here
are along a WGS84 parallel (east) and meridian (north), not angular degrees or
a projected square-pixel approximation. The derivative algorithm and source
mosaicking/resampling are candidates, not a replacement for the frozen SP04 map.
"""
from dataclasses import dataclass
from pathlib import Path
import math
import re
import zipfile

import numpy as np

from .grid import BilinearMap, GridSpec


WGS84_A_M = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)


@dataclass(frozen=True)
class DemWindow:
    grid: GridSpec
    elevation_m: np.ndarray
    valid: np.ndarray


@dataclass(frozen=True)
class TerrainFeatures:
    grid: GridSpec
    elevation_m: np.ndarray
    elevation_valid: np.ndarray
    east_gradient: np.ndarray
    north_gradient: np.ndarray
    gradient_valid: np.ndarray
    slope_degrees: np.ndarray
    aspect_degrees: np.ndarray
    aspect_valid: np.ndarray


def physical_spacing(grid: GridSpec) -> tuple[np.ndarray, np.ndarray]:
    """Signed adjacent distances (east [H,W-1], north [H-1,W]), in metres.

    Axis order is preserved, including descending latitude or longitude.
    Meridional arc uses 8-point Gauss-Legendre integration of the WGS84
    meridional curvature radius. Parallel arc uses N(phi)*cos(phi)*dlambda.
    Poles and longitude jumps >180 degrees are rejected, never silently wrapped.
    """
    lat, lon = np.asarray(grid.lat, float), np.asarray(grid.lon, float)
    if np.any(np.abs(lat) >= 90.0) or np.any(np.abs(np.diff(lon)) > 180.0):
        raise ValueError("Nonpolar nonwrapping geographic axes required")
    phi, lam = np.radians(lat), np.radians(lon)
    normal = WGS84_A_M / np.sqrt(1.0 - WGS84_E2 * np.sin(phi) ** 2)
    east = normal[:, None] * np.cos(phi[:, None]) * np.diff(lam)[None, :]
    nodes, weights = np.polynomial.legendre.leggauss(8)
    mid, half = (phi[1:] + phi[:-1]) / 2.0, np.diff(phi) / 2.0
    samples = mid[:, None] + half[:, None] * nodes
    radius = WGS84_A_M * (1.0 - WGS84_E2) / (1.0 - WGS84_E2 * np.sin(samples) ** 2) ** 1.5
    north = np.broadcast_to((half * (radius @ weights))[:, None], (len(lat) - 1, len(lon))).copy()
    if not np.isfinite(east).all() or not np.isfinite(north).all() or (east == 0).any() or (north == 0).any():
        raise ValueError("Nonzero finite WGS84 spacing required")
    return east, north


def terrain_features(elevation_m: np.ndarray, valid: np.ndarray, grid: GridSpec,
                     *, elevation_unit: str) -> TerrainFeatures:
    """Three-point central derivatives; all borders and invalid stencils masked.

    Inputs are [latitude,longitude] with elevation explicitly in metres. A full
    centre/east/west/north/south stencil is required for both derivatives. Read
    a one-cell halo and crop only after feature production for interior windows.
    Slope is degrees; aspect is downslope azimuth clockwise from north, with
    flat aspect undefined (NaN). Gradients are dimensionless m/m.
    """
    z, mask = np.asarray(elevation_m, float), np.asarray(valid)
    shape = (len(grid.lat), len(grid.lon))
    if elevation_unit != "m":
        raise ValueError("Explicit metre elevation required; convert before this interface")
    if z.shape != shape or min(shape) < 3 or mask.shape != shape or mask.dtype != bool:
        raise ValueError("Aligned >=3x3 elevation and independent bool mask required")
    if not np.isfinite(z[mask]).all():
        raise ValueError("Nonfinite elevation marked valid")
    east, north = physical_spacing(grid)
    stencil = (mask[1:-1, 1:-1] & mask[1:-1, :-2] & mask[1:-1, 2:]
               & mask[:-2, 1:-1] & mask[2:, 1:-1])
    gx, gn = np.full(shape, np.nan), np.full(shape, np.nan)
    with np.errstate(invalid="ignore"):
        h0, h1 = east[1:-1, :-1], east[1:-1, 1:]
        dx = ((h1 / h0) * (z[1:-1, 1:-1] - z[1:-1, :-2])
              + (h0 / h1) * (z[1:-1, 2:] - z[1:-1, 1:-1])) / (h0 + h1)
        h0, h1 = north[:-1, 1:-1], north[1:, 1:-1]
        dy = ((h1 / h0) * (z[1:-1, 1:-1] - z[:-2, 1:-1])
              + (h0 / h1) * (z[2:, 1:-1] - z[1:-1, 1:-1])) / (h0 + h1)
    gx[1:-1, 1:-1], gn[1:-1, 1:-1] = np.where(stencil, dx, np.nan), np.where(stencil, dy, np.nan)
    gradient_valid = np.zeros(shape, dtype=bool)
    gradient_valid[1:-1, 1:-1] = stencil
    magnitude = np.hypot(gx, gn)
    slope = np.degrees(np.arctan(magnitude))
    aspect_valid = gradient_valid & (magnitude > 0)
    aspect = np.where(aspect_valid, np.degrees(np.arctan2(-gx, -gn)) % 360.0, np.nan)
    return TerrainFeatures(grid, np.where(mask, z, np.nan), mask.copy(), gx, gn,
                           gradient_valid, slope, aspect, aspect_valid)


def project_terrain(features: TerrainFeatures, mapping: BilinearMap) -> TerrainFeatures:
    """Optional candidate point mapping after computing native physical gradients.

    Does not implement a production footprint aggregation or SP04's 25-cell
    reduction. East/north gradients are mapped as components; slope/aspect are
    derived from the mapped vector, so azimuths never average across 0/360 as
    ordinary scalars. Missing required neighbours stay invalid. The caller must
    explicitly supply the proposed mapping and its exact source/target grids.
    """
    features.grid.assert_same(mapping.source)
    elevation, elevation_valid = mapping.apply(features.elevation_m, features.elevation_valid)
    east, east_valid = mapping.apply(features.east_gradient, features.gradient_valid)
    north, north_valid = mapping.apply(features.north_gradient, features.gradient_valid)
    valid = east_valid & north_valid
    magnitude = np.hypot(east, north)
    aspect_valid = valid & (magnitude > 0)
    aspect = np.where(aspect_valid, np.degrees(np.arctan2(-east, -north)) % 360.0, np.nan)
    return TerrainFeatures(mapping.target, elevation, elevation_valid, east, north, valid,
                           np.degrees(np.arctan(magnitude)), aspect, aspect_valid)


def read_dem_window(path: str | Path, *, row_start: int, col_start: int,
                    height: int, width: int, elevation_unit: str,
                    max_cells: int = 65536) -> DemWindow:
    """Bounded native SRTM HGT / one-HGT zip read, no mosaicking or resampling.

    Supports standard 1201/3601 square big-endian int16 tiles and -32768 no-data.
    Filename georeferencing is the same GDAL SRTMHGT convention reused by Stage
    0: first row is northern edge, columns go east. Duplicate tile edge samples
    are retained. Elevation metres are an explicit caller contract; the HGT
    format alone does not establish the source's vertical datum.

    A compressed stream may decompress the prefix up to the requested row,
    bounded by the maximum standard tile size (25,934,402 bytes). It never reads
    unrelated members or a whole mosaic. Window output is capped by max_cells.
    """
    if elevation_unit != "m":
        raise ValueError("Explicit metre elevation contract required")
    numbers = (row_start, col_start, height, width, max_cells)
    if any(type(x) is not int for x in numbers) or min(row_start, col_start) < 0 or min(height, width, max_cells) < 1:
        raise ValueError("Nonnegative integer origin and positive integer window limits required")
    if height * width > max_cells or min(height, width) < 2:
        raise ValueError("Window must fit max_cells and have at least two centres per axis")
    source = Path(path)
    archive = None
    if source.name.lower().endswith(".zip"):
        archive = zipfile.ZipFile(source, "r")
        try:
            entries = [info for info in archive.infolist() if info.filename.lower().endswith(".hgt")]
            if len(entries) != 1:
                raise ValueError("Exactly one HGT member required")
            entry = entries[0]
            member, byte_count = Path(entry.filename).name, entry.file_size
            _hgt_shape(member, byte_count, row_start, col_start, height, width)
            handle = archive.open(entry, "r")
        except BaseException:
            archive.close()
            raise
    else:
        member, byte_count = source.name, source.stat().st_size
        _hgt_shape(member, byte_count, row_start, col_start, height, width)
        handle = source.open("rb")
    try:
        size, south, west = _hgt_shape(member, byte_count, row_start, col_start, height, width)
        elevation = np.empty((height, width), dtype=float)
        for r in range(height):
            handle.seek(((row_start + r) * size + col_start) * 2)
            block = handle.read(width * 2)
            if len(block) != width * 2:
                raise ValueError("Truncated HGT window")
            elevation[r] = np.frombuffer(block, dtype=">i2")
    finally:
        handle.close()
        if archive is not None:
            archive.close()
    lat = south + 1.0 - (row_start + np.arange(height)) / (size - 1)
    lon = west + (col_start + np.arange(width)) / (size - 1)
    valid = elevation != -32768
    return DemWindow(GridSpec(lat, lon), np.where(valid, elevation, np.nan), valid)


def _hgt_shape(member: str, byte_count: int, row: int, col: int,
               height: int, width: int) -> tuple[int, float, float]:
    match = re.fullmatch(r"([NS])(\d{2})([EW])(\d{3})(?:\.SRTMGL[13])?\.hgt", member, re.IGNORECASE)
    size = math.isqrt(byte_count // 2)
    if match is None or size not in (1201, 3601) or byte_count != size * size * 2:
        raise ValueError("Standard named 1201/3601 HGT tile required")
    if row + height > size or col + width > size:
        raise ValueError("HGT window is outside the tile")
    ns, lat, ew, lon = match.groups()
    south = float(lat) * (1 if ns.upper() == "N" else -1)
    west = float(lon) * (1 if ew.upper() == "E" else -1)
    if not -90 <= south < 90 or not -180 <= west < 180:
        raise ValueError("HGT filename outside geographic bounds")
    return size, south, west
