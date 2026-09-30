"""Materialize the researcher-approved SP04 coordinate/index contract.

This is a freeze-time evidence builder. Runtime consumers use the versioned
CSV files in config/spatial and verify their hashes; they need no F: drive.
Only coordinate metadata and index mapping are exported, never GADM geometry,
mask cell arrays, Himawari radiances, or IMERG rain values.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import netCDF4
import numpy as np


REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "config" / "spatial"
READINESS = Path(r"F:\pytorch\Research\outputs\stage1_b0_formal_readiness_resolution\run_20260928T124313_169375Z")
FREEZE = Path(r"F:\pytorch\Research\outputs\stage0_spatial_decision_update\run_20260928T102636_513428Z")
OLD_GEOMETRY = Path(r"F:\pytorch\Research\outputs\b0_spatial_probability_contract_resolution\run_20260928T144303_935304Z")
SOURCE_H = READINESS / "SPATIAL" / "himawari_actual_coordinates.npz"
SOURCE_I = FREEZE / "FROZEN" / "MASK" / "imerg_actual_coordinates.npz"
SOURCE_MASK = FREEZE / "FROZEN" / "MASK" / "yunnan_evaluation_mask_center_gadm41_imerg_v1.nc"
PREVIOUS_MAPPING = OLD_GEOMETRY / "SPATIAL" / "target_cell_native_mapping.csv"
EXPECTED_H_SHA = "9fc06c2f0f9bbfe46acb5a5a0878d839bf29b14a73e4830b82971f19a16a9df9"
EXPECTED_I_SHA = "4bf6ce3f9722c318c5db93bb4967660e82a53c498c90f3c6bacbf95c72ed912a"
EXPECTED_MASK_SHA = "9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef"
EXPECTED_AXIS_BYTES = {
    "native_lat": "dc82ee6d54c12e796ec2b9751ef388441d22a877d4e73aa1ba4702cdada72c52",
    "native_lon": "9303bfb46b0873cf35008ab1860445af9811f05a5b60f8eb9e30aaff95d2968b",
    "target_lat": "2c12a5b12969ddc2625686eae7ca561286b467b72e56a06493fe34800fb5aa5e",
    "target_lon": "07cc72b46ff87949b32c5c265af48211a28331055ed25166d499647a2b02ad07",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inferred_edges(centers: np.ndarray) -> np.ndarray:
    """Float64 midpoints/endpoint half-steps of actual ascending float32 centers."""
    values = np.asarray(centers, dtype=np.float64)
    assert values.ndim == 1 and len(values) > 1 and np.all(np.diff(values) > 0)
    edges = np.empty(len(values) + 1, dtype=np.float64)
    edges[1:-1] = (values[:-1] + values[1:]) / 2
    edges[0] = values[0] - (values[1] - values[0]) / 2
    edges[-1] = values[-1] + (values[-1] - values[-2]) / 2
    return edges


def memberships(source: np.ndarray, edges: np.ndarray, dtype: type) -> list[list[int]]:
    """Compare arrays at an explicit common precision, never scalar-promotion default."""
    values = np.asarray(source, dtype=dtype)
    bounds = np.asarray(edges, dtype=dtype)
    return [np.flatnonzero((values >= lower) & (values < upper)).astype(int).tolist()
            for lower, upper in zip(bounds[:-1], bounds[1:])]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    assert sha(SOURCE_H) == EXPECTED_H_SHA
    assert sha(SOURCE_I) == EXPECTED_I_SHA
    assert sha(SOURCE_MASK) == EXPECTED_MASK_SHA
    with np.load(SOURCE_H) as source, np.load(SOURCE_I) as target:
        native_lat = source["latitude"].copy()
        native_lon = source["longitude"].copy()
        full_lat = target["lat"].copy()
        full_lon = target["lon"].copy()
    assert native_lat.dtype == native_lon.dtype == full_lat.dtype == full_lon.dtype == np.float32
    target_full_rows = np.flatnonzero((full_lat >= 20) & (full_lat <= 30))
    target_full_cols = np.flatnonzero((full_lon >= 97) & (full_lon <= 107))
    assert target_full_rows.tolist() == list(range(10, 110))
    assert target_full_cols.tolist() == list(range(20, 120))
    axes = {"native_lat": native_lat, "native_lon": native_lon,
            "target_lat": full_lat[target_full_rows], "target_lon": full_lon[target_full_cols]}
    for name, values in axes.items():
        assert hashlib.sha256(values.tobytes()).hexdigest() == EXPECTED_AXIS_BYTES[name]
    assert np.all(np.diff(native_lat) < 0) and np.all(np.diff(native_lon) > 0)
    assert np.all(np.diff(axes["target_lat"]) > 0) and np.all(np.diff(axes["target_lon"]) > 0)
    with netCDF4.Dataset(SOURCE_MASK) as source:
        assert np.array_equal(full_lat, source.variables["lat"][:])
        assert np.array_equal(full_lon, source.variables["lon"][:])
        mask = np.asarray(source.variables["yunnan_mask"][:], dtype=bool)
        lat_bounds = np.asarray(source.variables["lat_bounds"][10:110], dtype=np.float64)
        lon_bounds = np.asarray(source.variables["lon_bounds"][20:120], dtype=np.float64)
    assert mask.shape == (130, 140) and int(mask.sum()) == 3430
    assert int(mask[np.ix_(target_full_rows, target_full_cols)].sum()) == 3430

    target_lat_edges = inferred_edges(axes["target_lat"])
    target_lon_edges = inferred_edges(axes["target_lon"])
    # The previously audited uniform 5x5 candidate arose from float32 edge
    # comparison. Make that rounding explicit so NumPy scalar-promotion changes
    # cannot silently change the scientific index mapping.
    row_members = memberships(native_lat, target_lat_edges, np.float32)
    col_members = memberships(native_lon, target_lon_edges, np.float32)
    assert all(len(x) == 5 for x in row_members + col_members)
    assert set().union(*(set(x) for x in row_members)) == set(range(1, 501))
    assert set().union(*(set(x) for x in col_members)) == set(range(0, 500))
    # The frozen mask's ancillary bounds are *not* the approved membership
    # edges: float32 rounding makes their raw comparison yield 4/5/6 centers.
    mask_bound_row_counts = [len(x) for x in memberships(native_lat, lat_bounds[:, 0].tolist() + [lat_bounds[-1, 1]], np.float64)]
    mask_bound_col_counts = [len(x) for x in memberships(native_lon, lon_bounds[:, 0].tolist() + [lon_bounds[-1, 1]], np.float64)]
    assert sorted(set(mask_bound_row_counts)) == [4, 5, 6]
    assert sorted(set(mask_bound_col_counts)) == [4, 5, 6]

    old = {}
    with PREVIOUS_MAPPING.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            old[(int(row["target_row"]), int(row["target_col"]))] = row
    assert len(old) == 10000
    mapping_rows = []
    for row_index, rows in enumerate(row_members):
        for col_index, cols in enumerate(col_members):
            prior = old[(row_index, col_index)]
            row_text = ";".join(map(str, rows))
            col_text = ";".join(map(str, cols))
            assert row_text == prior["native_raw_half_open_rows"]
            assert col_text == prior["native_raw_half_open_cols"]
            mapping_rows.append(dict(target_row=row_index, target_col=col_index,
                                     target_full_row=int(target_full_rows[row_index]),
                                     target_full_col=int(target_full_cols[col_index]),
                                     native_source_rows=row_text, native_source_cols=col_text,
                                     native_center_count=25))
    OUT.mkdir(parents=True, exist_ok=True)
    axes_rows = []
    for name, values in axes.items():
        for index, value in enumerate(values):
            bits = int(np.asarray(value, dtype=np.float32).view(np.uint32))
            axes_rows.append(dict(axis=name, index=index, decimal_value=repr(float(value)),
                                  float32_bits=f"{bits:08x}"))
    axes_file = OUT / "sp04_coordinate_axes_v1.csv"
    map_file = OUT / "sp04_target_cell_membership_v1.csv"
    write_csv(axes_file, ["axis", "index", "decimal_value", "float32_bits"], axes_rows)
    write_csv(map_file, ["target_row", "target_col", "target_full_row", "target_full_col",
                         "native_source_rows", "native_source_cols", "native_center_count"], mapping_rows)
    manifest = {
        "contract_version": "science_contract_v1",
        "status": "FROZEN_BY_RESEARCHER",
        "coordinate_rule": "actual float32 coordinate centers; infer midpoints/endpoint half-steps in float64; explicitly round inferred edges to float32 before comparison",
        "membership_rule": "[south,north) x [west,east), compare float32 native centers against explicitly float32-rounded inferred edges",
        "edge_precision": "float32 after float64 midpoint calculation",
        "index_convention": "zero-based original native array indices; native latitude descending, target latitude ascending",
        "native_shape": [501, 501], "target_shape": [100, 100],
        "target_full_row_indices": [10, 109], "target_full_col_indices": [20, 119],
        "all_10000_cells_have_25_centers": True,
        "source_rows_used": [1, 500], "source_row_excluded_from_direct_projection": 0,
        "source_cols_used": [0, 499], "source_col_excluded_from_direct_projection": 500,
        "excluded_centers_still_in_native_convolution_context": True,
        "yunnan_evaluation_mask_true_cells": 3430,
        "mask_hash_not_payload": EXPECTED_MASK_SHA,
        "source_himawari_npz_sha256": EXPECTED_H_SHA,
        "source_imerg_npz_sha256": EXPECTED_I_SHA,
        "source_frozen_mask_nc_sha256": EXPECTED_MASK_SHA,
        "source_previous_candidate_mapping_sha256": sha(PREVIOUS_MAPPING),
        "axis_raw_float32_bytes_sha256": EXPECTED_AXIS_BYTES,
        "axes_csv_sha256": sha(axes_file), "mapping_csv_sha256": sha(map_file),
        "mask_ancillary_bounds_membership_counts": {
            "latitude": {str(n): mask_bound_row_counts.count(n) for n in (4, 5, 6)},
            "longitude": {str(n): mask_bound_col_counts.count(n) for n in (4, 5, 6)},
        },
        "mask_ancillary_bounds_note": "These ancillary mask-file bounds differ at float precision and are NOT the versioned SP04 feature-membership edges; evaluation mask remains unchanged.",
        "not_a_physical_footprint_equivalence_claim": True,
    }
    (OUT / "sp04_coordinate_manifest_v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"axes": str(axes_file), "mapping": str(map_file),
                      "mapping_sha256": manifest["mapping_csv_sha256"],
                      "mask_bound_counts": manifest["mask_ancillary_bounds_membership_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
