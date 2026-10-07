"""Read and verify published actual-coordinate SP04 membership artifacts."""
from dataclasses import dataclass
import csv
import json
from pathlib import Path
import struct
import numpy as np
import torch
from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256


@dataclass(frozen=True)
class SP04Mapping:
    axes: dict[str, np.ndarray]
    indices: torch.Tensor  # [10000,25] native row-major indices
    manifest: dict

    def assert_axes(self, native_lat, native_lon, target_lat, target_lon) -> None:
        for name, actual in (("native_lat", native_lat), ("native_lon", native_lon), ("target_lat", target_lat), ("target_lon", target_lon)):
            actual = np.asarray(actual)
            if actual.dtype != np.dtype("float32") or actual.shape != self.axes[name].shape or not np.array_equal(actual.view("uint32"), self.axes[name].view("uint32")):
                raise ValueError(f"{name}: observed coordinate array differs from frozen actual float32 axis; no flip/transpose/reconstruction")


def load_sp04(root: Path = REPO_ROOT) -> SP04Mapping:
    science, engineering = load_contract(root)
    spatial = root / "config/spatial"
    if sha256(spatial / "sp04_coordinate_manifest_v1.json") != engineering["sp04_manifest_sha256"]:
        raise ValueError("SP04 manifest SHA256 differs from pinned version")
    manifest = json.loads((spatial / "sp04_coordinate_manifest_v1.json").read_text(encoding="utf-8"))
    axes_path = spatial / "sp04_coordinate_axes_v1.csv"
    mapping_path = spatial / "sp04_target_cell_membership_v1.csv"
    if sha256(axes_path) != manifest["axes_csv_sha256"] or sha256(mapping_path) != manifest["mapping_csv_sha256"]:
        raise ValueError("SP04 artifact SHA256 mismatch")
    if manifest["mapping_csv_sha256"] != science["spatial"]["native_to_target"]["mapping_csv_sha256"]:
        raise ValueError("SP04 mapping differs from science contract")
    buckets: dict[str, list[float]] = {k: [] for k in ("native_lat", "native_lon", "target_lat", "target_lon")}
    with axes_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            name = row["axis"]
            if name not in buckets or int(row["index"]) != len(buckets[name]):
                raise ValueError("SP04 axis ordering mismatch")
            value = np.float32(row["decimal_value"])
            if struct.pack(">f", float(value)).hex() != row["float32_bits"].lower():
                raise ValueError("SP04 axis float32 bits mismatch")
            buckets[name].append(value)
    axes = {k: np.asarray(v, dtype="float32") for k, v in buckets.items()}
    for name, axis in axes.items():
        if sha256_bytes(axis.tobytes()) != manifest["axis_raw_float32_bytes_sha256"][name]:
            raise ValueError(f"SP04 {name} raw bytes mismatch")
    if tuple(map(len, (axes["native_lat"], axes["native_lon"], axes["target_lat"], axes["target_lon"]))) != (501, 501, 100, 100):
        raise ValueError("SP04 axes shape mismatch")
    if not (np.all(np.diff(axes["native_lat"]) < 0) and np.all(np.diff(axes["native_lon"]) > 0) and np.all(np.diff(axes["target_lat"]) > 0) and np.all(np.diff(axes["target_lon"]) > 0)):
        raise ValueError("SP04 coordinate direction mismatch")
    indices = []
    with mapping_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            flat = len(indices)
            if (int(row["target_row"]), int(row["target_col"])) != divmod(flat, 100):
                raise ValueError("SP04 target order mismatch")
            if (int(row["target_full_row"]), int(row["target_full_col"])) != (10 + flat // 100, 20 + flat % 100):
                raise ValueError("SP04 full grid target indices mismatch")
            rows = [int(x) for x in row["native_source_rows"].split(";")]
            cols = [int(x) for x in row["native_source_cols"].split(";")]
            if len(rows) * len(cols) != 25 or int(row["native_center_count"]) != 25 or any(r < 1 or r > 500 for r in rows) or any(c < 0 or c > 499 for c in cols):
                raise ValueError("SP04 membership count/bounds mismatch")
            indices.append([r * 501 + c for r in rows for c in cols])
    if len(indices) != 10000 or len(set(i for cell in indices for i in cell)) != 250000:
        raise ValueError("SP04 coverage is not one-to-one over 250000 native centers")
    return SP04Mapping(axes, torch.tensor(indices, dtype=torch.long), manifest)


def sha256_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()
