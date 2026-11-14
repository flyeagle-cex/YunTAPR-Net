"""Bounded same-pixel strong-rain records for the E0/COSINE9 diagnostic.

This module only consumes arrays already produced by an authorized caller. It
does not read scientific files, load models, or launch inference. Each arm
retains only strict FP32 R>20 pixel-times while accumulating fixed-population
counts in memory. The two arm files can be paired by their explicit scene,
time, and flattened grid identity.
"""

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from tools.research_readiness.paired_point_metrics import point_candidates_log


THRESHOLD_MM_H = np.float32(20.0)
RECORD_FIELDS = (
    "scene_id", "analysis_time", "pixel_index", "truth_mm_h", "p_occ",
    "qlog", "point_A_mm_h", "point_B_mm_h", "point_C_mm_h",
)


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class StrongJointAccumulator:
    """Stream full-population summaries and retain exact R>20 joint rows."""

    def __init__(self, scene_ids, analyses, *, expected_valid, expected_rain, expected_strong,
                 output_path, max_batch_size=8, grid_shape=(100, 100), check_output=None):
        self.scene_ids = tuple(scene_ids)
        self.analyses = tuple(map(str, analyses))
        self.output_path = Path(output_path)
        if (not self.scene_ids or len(self.scene_ids) != len(self.analyses)
                or len(set(self.scene_ids)) != len(self.scene_ids)
                or any(type(sid) is not str or not sid for sid in self.scene_ids)):
            raise ValueError("Unique ordered scene IDs and aligned analysis times required")
        self.expected_valid = self._positive_int(expected_valid, "expected_valid")
        self.expected_rain = self._positive_int(expected_rain, "expected_rain")
        self.expected_strong = self._positive_int(expected_strong, "expected_strong")
        self.max_batch_size = self._positive_int(max_batch_size, "max_batch_size")
        if (len(grid_shape) != 2 or any(type(v) is not int or v <= 0 for v in grid_shape)):
            raise ValueError("Positive fixed grid shape required")
        self.grid_shape = tuple(grid_shape)
        self.check_output = check_output
        if self.output_path.exists():
            raise FileExistsError("Joint record output must be new")
        self.position = self.n_valid = self.n_rain = self.n_strong = 0
        self.records = {name: [] for name in RECORD_FIELDS}
        self.joint_counts = {
            "q32_ge_truth": 0,
            "q32_gt20": 0,
            "A_gt20": 0,
            "B_gt20": 0,
            "C_gt20": 0,
            "q32_gt20_A_le20": 0,
            "q32_gt20_B_le20": 0,
            "q32_gt20_C_le20": 0,
        }
        self.strong_probability_bins = np.zeros((10, 6), dtype=np.int64)
        self.poisoned = self.finished = False

    @staticmethod
    def _positive_int(value, name):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value

    def add(self, scene_ids, analyses, rate, valid, region, probability, quantiles_log):
        try:
            if self.poisoned or self.finished:
                raise RuntimeError("Accumulator is failed or already finished")
            ids, stamps = tuple(scene_ids), tuple(map(str, analyses))
            n = len(ids)
            stop = self.position + n
            if (not 1 <= n <= self.max_batch_size
                    or ids != self.scene_ids[self.position:stop]
                    or stamps != self.analyses[self.position:stop]):
                raise ValueError("Batch scene/time order differs from the frozen population")
            y, p, q = np.asarray(rate), np.asarray(probability), np.asarray(quantiles_log)
            v, rg = np.asarray(valid), np.asarray(region)
            expected = (n, 1, *self.grid_shape)
            if (y.shape != expected or p.shape != expected or v.shape != expected
                    or rg.shape != expected or q.shape != (n, 32, *self.grid_shape)
                    or y.dtype.kind != "f" or p.dtype.kind != "f" or q.dtype.kind != "f"
                    or v.dtype != np.bool_ or rg.dtype != np.bool_):
                raise ValueError("Exact fixed-grid batch and prediction shapes required")
            if (not np.isfinite(y).all() or (y < 0).any()
                    or not np.isfinite(p).all() or (p < 0).any() or (p > 1).any()
                    or not np.isfinite(q).all()):
                raise ValueError("Selected model/reference arrays must be finite and in range")
            selected = (v & rg)[:, 0].reshape(n, -1)
            y_flat = y[:, 0].reshape(n, -1).astype(np.float64)
            p_flat = p[:, 0].reshape(n, -1).astype(np.float64)
            q_flat = q.transpose(0, 2, 3, 1).reshape(n, -1, 32).astype(np.float64)
            if ((np.diff(q_flat, axis=-1) <= 0).any()
                    or (q_flat[..., 0] <= math.log1p(0.1)).any()):
                raise ValueError("Frozen finite strictly ordered 32-node support required")
            points = point_candidates_log(q_flat.reshape(-1, 32), p_flat.reshape(-1))
            points = {key: value.reshape(n, -1) for key, value in points.items()}
            y32, point32 = y_flat.astype(np.float32), {
                key: value.astype(np.float32) for key, value in points.items()
            }
            strong_masks = selected & (y32 > THRESHOLD_MM_H)
            batch_valid = int(selected.sum())
            batch_rain = int((selected & (y32 > np.float32(0.1))).sum())
            batch_strong = int(strong_masks.sum())
            if self.n_valid + batch_valid > self.expected_valid:
                raise ValueError("Valid population exceeds frozen limit")
            if self.n_rain + batch_rain > self.expected_rain:
                raise ValueError("Rainy population exceeds frozen limit")
            if self.n_strong + batch_strong > self.expected_strong:
                raise ValueError("Strong-rain population exceeds frozen limit")

            q32_physical = np.expm1(q_flat[..., -1])
            q32_physical32 = q32_physical.astype(np.float32)
            q32_ge_truth = q_flat[..., -1] >= np.log1p(y_flat)
            probability_bin = np.searchsorted(np.arange(1, 10, dtype=np.float64) / 10, p_flat, side="right")
            q32_gt20_mask = q32_physical32 > THRESHOLD_MM_H
            for name, condition in (
                ("q32_ge_truth", q32_ge_truth),
                ("q32_gt20", q32_gt20_mask),
                ("A_gt20", point32["A"] > THRESHOLD_MM_H),
                ("B_gt20", point32["B"] > THRESHOLD_MM_H),
                ("C_gt20", point32["C"] > THRESHOLD_MM_H),
            ):
                self.joint_counts[name] += int((strong_masks & condition).sum())
            for method in ("A", "B", "C"):
                self.joint_counts[f"q32_gt20_{method}_le20"] += int(
                    (strong_masks & q32_gt20_mask & (point32[method] <= THRESHOLD_MM_H)).sum()
                )
            for bin_id in range(10):
                in_bin = strong_masks & (probability_bin == bin_id)
                self.strong_probability_bins[bin_id] += np.asarray((
                    int(in_bin.sum()),
                    int((in_bin & q32_ge_truth).sum()),
                    int((in_bin & q32_gt20_mask).sum()),
                    int((in_bin & (point32["A"] > THRESHOLD_MM_H)).sum()),
                    int((in_bin & (point32["B"] > THRESHOLD_MM_H)).sum()),
                    int((in_bin & (point32["C"] > THRESHOLD_MM_H)).sum()),
                ), dtype=np.int64)

            for i, sid in enumerate(ids):
                keep = np.flatnonzero(strong_masks[i])
                if keep.size:
                    self.records["scene_id"].extend([sid] * int(keep.size))
                    self.records["analysis_time"].extend([stamps[i]] * int(keep.size))
                    self.records["pixel_index"].extend(keep.tolist())
                    self.records["truth_mm_h"].extend(y_flat[i, keep].tolist())
                    self.records["p_occ"].extend(p_flat[i, keep].tolist())
                    self.records["qlog"].extend(q_flat[i, keep].tolist())
                    for method in ("A", "B", "C"):
                        self.records[f"point_{method}_mm_h"].extend(points[method][i, keep].tolist())
            self.position, self.n_valid = stop, self.n_valid + batch_valid
            self.n_rain += batch_rain
            self.n_strong += batch_strong
        except BaseException:
            self.poisoned = True
            raise

    def finish(self, *, arm_id, checkpoint_sha256, population_sha256):
        try:
            if self.poisoned or self.finished:
                raise RuntimeError("Accumulator is failed or already finished")
            if (self.position != len(self.scene_ids) or self.n_valid != self.expected_valid
                    or self.n_rain != self.expected_rain
                    or self.n_strong != self.expected_strong):
                raise ValueError("Complete scene and frozen pixel populations required")
            if (arm_id not in ("CONTROL_E0", "CANDIDATE_COSINE9")
                    or len(checkpoint_sha256) != 64 or len(population_sha256) != 64):
                raise ValueError("Exact arm and SHA-bound identities required")
            arrays = {
                "scene_id": np.asarray(self.records["scene_id"], dtype="U32"),
                "analysis_time": np.asarray(self.records["analysis_time"], dtype="U40"),
                "pixel_index": np.asarray(self.records["pixel_index"], dtype=np.int32),
                "truth_mm_h": np.asarray(self.records["truth_mm_h"], dtype=np.float64),
                "p_occ": np.asarray(self.records["p_occ"], dtype=np.float64),
                "qlog": np.asarray(self.records["qlog"], dtype=np.float64).reshape(-1, 32),
                "point_A_mm_h": np.asarray(self.records["point_A_mm_h"], dtype=np.float64),
                "point_B_mm_h": np.asarray(self.records["point_B_mm_h"], dtype=np.float64),
                "point_C_mm_h": np.asarray(self.records["point_C_mm_h"], dtype=np.float64),
            }
            if arrays["scene_id"].size != self.expected_strong:
                raise ValueError("Strong-pixel record count differs from the frozen population")
            if self.check_output is not None:
                self.check_output(reserve=sum(array.nbytes for array in arrays.values()) + 1024 * 1024)
            with self.output_path.open("xb") as stream:
                np.savez_compressed(stream, **arrays)
            self.finished = True
            return {
                "status": "COMPLETE_ARM_STRONG_JOINT_RECORDS",
                "arm_id": arm_id,
                "population_sha256": population_sha256,
                "checkpoint_sha256": checkpoint_sha256,
                "scene_count": len(self.scene_ids),
                "n_valid": self.n_valid,
                "n_rain": self.n_rain,
                "n_strong": self.n_strong,
                "strong_joint_counts": dict(self.joint_counts),
                "strong_probability_bins": [
                    dict(index=index, interval=f"[{index / 10:.1f},{(index + 1) / 10:.1f})" if index < 9 else "[0.9,1.0]",
                         n=int(row[0]), q32_ge_truth=int(row[1]), q32_gt20=int(row[2]),
                         A_gt20=int(row[3]), B_gt20=int(row[4]), C_gt20=int(row[5]))
                    for index, row in enumerate(self.strong_probability_bins)
                ],
                "record_file": self.output_path.name,
                "record_bytes": self.output_path.stat().st_size,
                "record_sha256": _sha256(self.output_path),
                "identity_key": ["scene_id", "analysis_time", "pixel_index"],
                "grid_shape": list(self.grid_shape),
            }
        except BaseException:
            self.poisoned = True
            raise


def pair_strong_records(control_path, candidate_path, *, expected_rows=717):
    """Verify exact strong-pixel overlap and describe E0-to-COSINE9 changes."""
    with np.load(control_path, allow_pickle=False) as left, np.load(candidate_path, allow_pickle=False) as right:
        if set(left.files) != set(RECORD_FIELDS) or set(right.files) != set(RECORD_FIELDS):
            raise ValueError("Unexpected or missing saved joint-record fields")
        keys_left = list(zip(left["scene_id"].tolist(), left["analysis_time"].tolist(), left["pixel_index"].tolist()))
        keys_right = list(zip(right["scene_id"].tolist(), right["analysis_time"].tolist(), right["pixel_index"].tolist()))
        if len(keys_left) != expected_rows or len(keys_right) != expected_rows:
            raise ValueError("Both arms must contain the exact frozen strong-pixel count")
        if len(set(keys_left)) != expected_rows or len(set(keys_right)) != expected_rows:
            raise ValueError("Duplicate strong-pixel identity")
        if keys_left != keys_right:
            raise ValueError("E0 and COSINE9 strong-pixel identity order differs")
        for name in ("truth_mm_h",):
            if not np.array_equal(left[name], right[name]):
                raise ValueError("Paired arms have different reference values")
        # Threshold decisions use the same strict FP32 contract as the point metrics.
        q32_left = np.expm1(left["qlog"][:, -1]).astype(np.float32)
        q32_right = np.expm1(right["qlog"][:, -1]).astype(np.float32)
        p_delta = right["p_occ"] - left["p_occ"]
        qlog_delta = right["qlog"] - left["qlog"]
        return {
            "status": "PAIRED_STRONG_PIXEL_RECORDS",
            "n_paired": len(keys_left),
            "q32_ge_truth": {
                "E0": int((left["qlog"][:, -1] >= np.log1p(left["truth_mm_h"])).sum()),
                "COSINE9": int((right["qlog"][:, -1] >= np.log1p(right["truth_mm_h"])).sum()),
            },
            "q32_gt20": {
                "E0": int((q32_left > THRESHOLD_MM_H).sum()),
                "COSINE9": int((q32_right > THRESHOLD_MM_H).sum()),
            },
            "q32_gt20_intersection": int(((q32_left > THRESHOLD_MM_H) & (q32_right > THRESHOLD_MM_H)).sum()),
            "q32_gt20_E0_only": int(((q32_left > THRESHOLD_MM_H) & (q32_right <= THRESHOLD_MM_H)).sum()),
            "q32_gt20_COSINE9_only": int(((q32_left <= THRESHOLD_MM_H) & (q32_right > THRESHOLD_MM_H)).sum()),
            "mean_p_occ_change_COSINE9_minus_E0": float(p_delta.mean()),
            "mean_q32_physical_change_mm_h_COSINE9_minus_E0": float((q32_right - q32_left).mean()),
            "mean_qlog_node_changes_COSINE9_minus_E0": qlog_delta.mean(axis=0).tolist(),
            "point_changes_COSINE9_minus_E0": {
                name: float((right[f"point_{name}_mm_h"] - left[f"point_{name}_mm_h"]).mean())
                for name in ("A", "B", "C")
            },
        }
