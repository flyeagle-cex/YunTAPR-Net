"""Bounded sidecar export; no model, original-data reader, or scientific selection.

The approved worker supplies already-computed arrays. This module never imports
torch and cannot launch inference. Incomplete chunks/ledgers are preserved.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.research_readiness.extreme_diagnostic_candidates import (
    exceedance_bounds, brier_bounds, auroc_bounds,
)


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 ** 2), b""):
            result.update(block)
    return result.hexdigest()


def _date(value, year):
    from datetime import datetime, timezone
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Explicit timezone required")
    stamp = stamp.astimezone(timezone.utc)
    if stamp.year != year:
        raise PermissionError("Only the approved year is accepted")
    return stamp


class JointCollector:
    """Collect complete scene/pixel keys, joint outputs and fixed diagnostics.

    No feature mask removes supervision. A partial run can never be sealed.
    Thresholds and point estimates are supplied by the exact approved package.
    """
    def __init__(self, folder, ids, analyses, *, pixels_per_scene=3430,
                 point_function, check_limits, reference_context=None):
        self.folder = Path(folder)
        if len(ids) != len(analyses) or len(set(ids)) != len(ids) or not ids:
            raise ValueError("Unique aligned scene identity required")
        self.ids, self.analyses = tuple(ids), tuple(map(str, analyses))
        for sid, analysis in zip(self.ids, self.analyses):
            start, end = _date(sid, 2024), _date(analysis, 2024)
            if (end - start).total_seconds() != 1800 or end.hour not in (0, 6, 12, 18):
                raise ValueError("Frozen half-hour/four-UTC alignment required")
        if type(pixels_per_scene) is not int or pixels_per_scene <= 0:
            raise ValueError("Positive supervised population required")
        self.n_pixel = pixels_per_scene
        self.point_function, self.check = point_function, check_limits
        self.reference_context = None if reference_context is None else Path(reference_context)
        self.folder.mkdir(exist_ok=False)
        self.position = 0
        self.chunks = []
        self.thresholds = (5., 10., 20., 50.)
        self.intervals = {r: [] for r in self.thresholds}
        self.covered = np.zeros(32, dtype=np.int64)
        self.n_rain = 0
        self.shortfall = 0.
        self.errors, self.boundaries, self.groups = {}, {}, {}
        self.contingency = {}
        self.group_hashes = {}
        self.scene_peaks = []
        self.finished = False
        self.poisoned = False

    def _journal(self, value):
        with (self.folder / "chunks.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, allow_nan=False) + "\n")
            stream.flush()

    def add(self, ids, analyses, rate, valid, region, probability, quantiles_log,
            *, context=None):
        if self.poisoned or self.finished:
            raise PermissionError("Failed or sealed collector cannot continue")
        try:
            return self._add(ids, analyses, rate, valid, region, probability, quantiles_log, context=context)
        except BaseException:
            self.poisoned = True
            raise

    def _add(self, ids, analyses, rate, valid, region, probability, quantiles_log,
             *, context=None):
        self.check()
        if self.finished or not ids:
            raise PermissionError("Collector sealed or empty batch")
        stop = self.position + len(ids)
        if (tuple(ids) != self.ids[self.position:stop]
                or tuple(map(str, analyses)) != self.analyses[self.position:stop]):
            raise ValueError("Scene order, duplicates or analysis alignment changed")
        y = np.asarray(rate)
        v, rg = np.asarray(valid), np.asarray(region)
        p, q = np.asarray(probability), np.asarray(quantiles_log)
        batch = len(ids)
        if (y.ndim != 4 or y.shape[:2] != (batch, 1)
                or v.shape != y.shape or rg.shape != y.shape
                or v.dtype != bool or rg.dtype != bool or p.shape != y.shape
                or q.shape != (batch, 32, *y.shape[-2:]) or q.dtype != np.float64):
            raise ValueError("Exact independent supervision/output shapes required")
        if y.dtype != np.float32 or p.dtype != np.float32:
            raise ValueError("FP32 labels and exact FP32 carriers of already-computed occurrence probabilities required")
        masks = (v & rg).reshape(batch, -1)
        if any(int(m.sum()) != self.n_pixel for m in masks):
            raise ValueError("Supervision count changed; no silent subset")
        indices = np.stack([np.flatnonzero(m) for m in masks]).astype(np.int32)
        yl = y.reshape(batch, -1)
        pl = p.reshape(batch, -1)
        ql = q.transpose(0, 2, 3, 1).reshape(batch, -1, 32)
        rows = np.arange(batch)[:, None]
        kept_y, kept_p, kept_q = yl[rows, indices], pl[rows, indices], ql[rows, indices]
        if (not np.isfinite(kept_y).all() or (kept_y < 0).any()
                or not np.isfinite(kept_p).all() or (kept_p < 0).any() or (kept_p > 1).any()
                or not np.isfinite(kept_q).all() or (np.diff(kept_q, axis=-1) <= 0).any()
                or (kept_q[..., 0] <= math.log1p(.1)).any()):
            raise ValueError("Nonfinite, invalid probability or quantile support")
        values = dict(scene_id=np.asarray(ids), analysis_time=np.asarray(tuple(map(str, analyses))),
                      pixel_index=indices, rate=kept_y, occurrence_probability=kept_p,
                      conditional_quantiles_log=kept_q)
        number = len(self.chunks)
        if context is not None:
            for name, array in context.items():
                if not name.isidentifier() or name in values:
                    raise ValueError("Explicit noncolliding context names required")
                array = np.asarray(array)
                if array.dtype.kind not in "biuf" or array.shape[0] != batch:
                    raise ValueError("Numeric context with an explicit scene axis required")
                if array.shape[-2:] != y.shape[-2:]:
                    raise ValueError("Context grid must equal the supervision grid")
                extra = int(np.prod(array.shape[1:-2])) or 1
                flat = array.reshape(batch, extra, -1).transpose(0, 2, 1)
                kept = flat[rows, indices]
                if array.dtype.kind == "f" and not np.isfinite(kept).all():
                    raise ValueError("Use explicit zero plus validity for unavailable context")
                values[name] = kept
        elif self.reference_context is not None:
            ref_path = self.reference_context / f"chunk_{number:04d}.npz"
            with np.load(ref_path, allow_pickle=False) as saved:
                if (not np.array_equal(saved["scene_id"], values["scene_id"])
                        or not np.array_equal(saved["analysis_time"], values["analysis_time"])
                        or not np.array_equal(saved["pixel_index"], indices)
                        or not np.array_equal(saved["rate"], kept_y)):
                    raise ValueError("Cross-model context join is not the same population")
                for name in saved.files:
                    if name not in values:
                        values[name] = saved[name].copy()

        self._diagnostics(values)
        filename = f"chunk_{number:04d}.npz"
        path = self.folder / filename
        self.check(sum(a.nbytes for a in values.values()) + 65536)
        self._journal(dict(chunk=number, state="INTENT", first_scene=self.position, scenes=batch))
        with path.open("xb") as stream:
            np.savez(stream, **values)
        record = dict(chunk=number, state="COMPLETE", filename=filename,
                      scenes=batch, pixel_times=int(kept_y.size), bytes=path.stat().st_size,
                      sha256=file_sha(path), first_scene=self.position)
        self._journal(record)
        self.chunks.append(record)
        self.position = stop
        self.check()

    def _diagnostics(self, data):
        y = data["rate"].reshape(-1)
        p = data["occurrence_probability"].reshape(-1).astype(np.float64)
        q = data["conditional_quantiles_log"].reshape(-1, 32)
        rainy = y > np.float32(.1)
        z = np.log1p(y.astype(np.float64))
        self.n_rain += int(rainy.sum())
        self.covered += (z[rainy, None] <= q[rainy]).sum(axis=0)
        self.shortfall += float(np.maximum(z[rainy] - q[rainy, -1], 0).sum())
        tau = (np.arange(32) + .5) / 32
        delta = z[:, None] - q
        pin = np.maximum(delta * tau, delta * (tau - 1)).mean(axis=1)
        point = self.point_function(q, p)
        if set(point) != {"A", "B", "C"} or any(not np.isfinite(x).all() for x in point.values()):
            raise ValueError("Frozen point methods changed or physical conversion overflowed")
        for threshold in self.thresholds:
            bound = exceedance_bounds(p, q, threshold)
            self.intervals[threshold].append((y > np.float32(threshold), bound.lower, bound.upper))
            self.boundaries.setdefault(str(threshold), dict(truth_equal=0, prediction_equal={k: 0 for k in point}))
            entry = self.boundaries[str(threshold)]
            entry["truth_equal"] += int((y == np.float32(threshold)).sum())
            for key, value in point.items():
                entry["prediction_equal"][key] += int((value.astype(np.float32) == np.float32(threshold)).sum())
                truth = y > np.float32(threshold)
                prediction = value.astype(np.float32) > np.float32(threshold)
                table = self.contingency.setdefault(key + "/" + str(threshold), dict(TP=0, FP=0, FN=0, TN=0))
                for field, mask in (("TP", prediction & truth), ("FP", prediction & ~truth),
                                    ("FN", ~prediction & truth), ("TN", ~prediction & ~truth)):
                    table[field] += int(mask.sum())
        groups = {"all": np.ones(y.size, dtype=bool), "gt20": y > np.float32(20), "gt50": y > np.float32(50)}
        for lo, hi in zip((.1, 1., 5., 10., 20., 30., 50.), (1., 5., 10., 20., 30., 50., float("inf"))):
            groups[f"rain_{lo}_{hi}"] = (y > np.float32(lo)) & (y <= np.float32(hi))
        for hour in (0, 6, 12, 18):
            hours = np.repeat([_date(t, 2024).hour for t in data["analysis_time"]], self.n_pixel)
            groups[f"UTC_{hour:02d}"] = hours == hour
        if "elevation_m" in data:
            elevation = data["elevation_m"].reshape(-1)
            groups.update(elevation_lt_1000=elevation < 1000,
                          elevation_1000_2000=(elevation >= 1000) & (elevation < 2000),
                          elevation_ge_2000=elevation >= 2000)
        if "dynamic_values" in data and "dynamic_valid" in data:
            dynamic = data["dynamic_values"].reshape(-1, 8)
            dynamic_valid = data["dynamic_valid"].reshape(-1, 8)
            for column, level in [(0, 850), (1, 700)]:
                for relation, cond in [("windward", dynamic[:, column] > 0),
                                       ("leeward", dynamic[:, column] < 0),
                                       ("zero", dynamic[:, column] == 0)]:
                    groups[f"O{level}_{relation}"] = dynamic_valid[:, column] & cond
            groups["pressure_850_available"] = dynamic_valid[:, 0]
            groups["pressure_700_only"] = ~dynamic_valid[:, 0] & dynamic_valid[:, 1]
            if "pwat_kg_m2" in data and "pwat_valid" in data:
                water, water_valid = data["pwat_kg_m2"].reshape(-1), data["pwat_valid"].reshape(-1)
                groups["pwat_below_train_reference"] = water_valid & (water < 31.85768219039871)
                groups["pwat_ge_train_reference"] = water_valid & (water >= 31.85768219039871)
                for wind in ("windward", "leeward"):
                    for water_group in ("below", "ge"):
                        groups[f"O700_{wind}__pwat_{water_group}"] = (
                            groups[f"O700_{wind}"] & groups[f"pwat_{water_group}_train_reference"])
        for name, mask in list(groups.items()):
            if name.startswith(("UTC_", "elevation_", "O", "pwat_", "pressure_")):
                groups["gt20__" + name] = mask & (y > np.float32(20))
                groups["gt50__" + name] = mask & (y > np.float32(50))
        for scene, sid in enumerate(data["scene_id"]):
            start, stop = scene * self.n_pixel, (scene + 1) * self.n_pixel
            actual = y[start:stop]
            true_pos = int(np.argmax(actual))
            for key, value in point.items():
                pred = value[start:stop]
                pred_pos = int(np.argmax(pred))
                self.scene_peaks.append(dict(scene_id=str(sid), method=key,
                    truth_peak_mm_h=float(actual[true_pos]), prediction_at_truth_peak_mm_h=float(pred[true_pos]),
                    prediction_peak_mm_h=float(pred[pred_pos]),
                    truth_peak_pixel_index=int(data["pixel_index"][scene, true_pos]),
                    prediction_peak_pixel_index=int(data["pixel_index"][scene, pred_pos]),
                    truth_peak_ties=int((actual == actual[true_pos]).sum()),
                    prediction_peak_ties=int((pred == pred[pred_pos]).sum()),
                    tie_policy="first frozen sorted pixel index; no skill-dependent matching"))
        for name, mask in groups.items():
            identity = self.group_hashes.setdefault(name, hashlib.sha256())
            identity.update(np.asarray([mask.size], dtype='<i8').tobytes())
            identity.update(np.packbits(mask).tobytes())
            row = self.groups.setdefault(name, dict(n=0, n_rain=0, n_gt20=0, pinball_sum=0.,
                                                    q32_covered=0, brier_occurrence_sum=0.))
            wet = mask & rainy
            row["n"] += int(mask.sum()); row["n_rain"] += int(wet.sum())
            row["n_gt20"] += int((mask & (y > np.float32(20))).sum())
            row["pinball_sum"] += float(pin[wet].sum())
            row["q32_covered"] += int((z[wet] <= q[wet, -1]).sum())
            row["brier_occurrence_sum"] += float(((p[mask] - rainy[mask]) ** 2).sum())
            for key, value in point.items():
                entry = self.errors.setdefault(name + "/" + key, dict(n=0, abs_sum=0., squared_sum=0., bias_sum=0.))
                error = value[mask] - y[mask].astype(np.float64)
                entry["n"] += int(error.size); entry["abs_sum"] += float(np.abs(error).sum())
                entry["squared_sum"] += float((error ** 2).sum()); entry["bias_sum"] += float(error.sum())

    def finish(self):
        if self.poisoned or self.finished:
            raise PermissionError("Failed or sealed collector cannot be sealed again")
        try:
            return self._finish()
        except BaseException:
            self.poisoned = True
            raise

    def _finish(self):
        self.check()
        if self.finished or self.position != len(self.ids):
            raise PermissionError("Incomplete or already sealed joint export")
        probability = {}
        for threshold, parts in self.intervals.items():
            truth, lower, upper = [np.concatenate([v[i] for v in parts]) for i in range(3)]
            probability[str(threshold)] = dict(n=int(truth.size), positive=int(truth.sum()),
                brier_bounds=brier_bounds(truth, lower, upper), auroc_bounds=auroc_bounds(truth, lower, upper),
                probability_interval_mean_width=float((upper - lower).mean()),
                AP="NOT_POINT_IDENTIFIED", probability_0_5_certain_negative=int((upper < .5).sum()),
                probability_0_5_certain_positive=int((lower >= .5).sum()),
                probability_0_5_unresolved=int(((lower < .5) & (upper >= .5)).sum()))
        for entry in self.errors.values():
            n = entry["n"]
            entry.update(MAE=None if not n else entry["abs_sum"] / n,
                         RMSE=None if not n else math.sqrt(entry["squared_sum"] / n),
                         Bias=None if not n else entry["bias_sum"] / n)
        for name, entry in self.groups.items():
            n, wet = entry["n"], entry["n_rain"]
            entry.update(conditional_pinball=None if not wet else entry["pinball_sum"] / wet,
                         q32_coverage=None if not wet else entry["q32_covered"] / wet,
                         occurrence_brier=None if not n else entry["brier_occurrence_sum"] / n,
                         group_mask_sha256=self.group_hashes[name].hexdigest())
        for entry in self.contingency.values():
            tp, fp, fn = entry['TP'], entry['FP'], entry['FN']
            entry.update(CSI=None if not tp + fp + fn else tp / (tp + fp + fn),
                         POD=None if not tp + fn else tp / (tp + fn),
                         FAR=None if not tp + fp else fp / (tp + fp),
                         Precision=None if not tp + fp else tp / (tp + fp))
        result = dict(status="COMPLETE_JOINT_EXPORT_PENDING_FROZEN_GATE_ACCEPTANCE",
                      scenes=self.position, n_valid=self.position * self.n_pixel, n_rain=self.n_rain,
                      conditional_coverage=[None if not self.n_rain else int(c) / self.n_rain for c in self.covered],
                      q32_shortfall_log_sum=self.shortfall, probability=probability,
                      point_errors=self.errors, boundary_counts=self.boundaries,
                      point_contingency=self.contingency,
                      groups=self.groups, scene_peaks=self.scene_peaks,
                      chunks=self.chunks, independent_events="NOT_IDENTIFIED")
        write_new(self.folder / "joint_summary.json", result)
        self.finished = True
        return result
