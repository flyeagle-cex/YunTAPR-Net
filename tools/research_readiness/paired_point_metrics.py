"""A/B/C point scores from an existing fixed-population forward traversal.

Continuous errors use the original FP64 physical point proxies. Classification
casts both proxies and reference rates to FP32 before strict threshold tests.
This module performs no input-file reads, model construction or inference.
"""

import hashlib
import math

import numpy as np

from tools.research_readiness.supplement_occurrence_metrics_20261113 import classification_metrics


THRESHOLDS_MM_H = (0.1, 1.0, 5.0, 10.0, 20.0, 50.0)
METHODS = ("A", "B", "C")
TAU = (np.arange(32, dtype=np.float64) + 0.5) / 32


def point_candidates_log(quantiles_log, probability):
    """Retain the inherited finite-node A/B/C formulas and B endpoint rule."""
    q = np.asarray(quantiles_log, dtype=np.float64)
    p = np.asarray(probability, dtype=np.float64)
    if q.ndim != 2 or q.shape[1] != 32 or p.shape != (q.shape[0],):
        raise ValueError("Quantiles must be [pixel,32] and probability [pixel]")
    if (not np.isfinite(q).all() or not np.isfinite(p).all()
            or (p < 0).any() or (p > 1).any()
            or (q[:, 0] <= math.log1p(0.1)).any()
            or (np.diff(q, axis=1) <= 0).any()):
        raise ValueError("Finite ordered conditional quantiles and probabilities required")
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        physical = np.expm1(q)
        result = {
            "A": p * physical.mean(axis=1),
            "C": p * np.expm1(q.mean(axis=1)),
        }
        above = p >= 0.5
        u = np.zeros_like(p)
        u[above] = (p[above] - 0.5) / p[above]
        qb = np.empty_like(u)
        qb[~above] = -np.inf
        if above.any():
            uu, qa = u[above], q[above]
            index = np.clip(np.searchsorted(TAU, uu, side="right"), 1, 31)
            weight = (uu - TAU[index - 1]) / (TAU[index] - TAU[index - 1])
            rows = np.arange(qa.shape[0])
            interpolated = qa[rows, index - 1] * (1 - weight) + qa[rows, index] * weight
            qb[above] = np.where(uu < TAU[0], math.log1p(0.1), interpolated)
        result["B"] = np.zeros_like(p)
        result["B"][above] = np.expm1(qb[above])
    if any(not np.isfinite(value).all() for value in result.values()):
        raise ValueError("Physical point conversion must remain finite")
    return {name: result[name] for name in METHODS}


def _count(value, name, *, positive=False):
    if type(value) is not int or value < int(positive):
        raise ValueError(f"{name} must be a {'positive' if positive else 'nonnegative'} integer")
    return value


def _floating_array(value, name):
    array = np.asarray(value)
    if not np.issubdtype(array.dtype, np.floating):
        raise ValueError(f"{name} must have floating dtype")
    return array


class PointMetricAccumulator:
    def __init__(self, scene_ids, *, expected_n_valid, expected_n_rain, max_batch_size=8):
        self.scene_ids = tuple(scene_ids)
        if (not self.scene_ids or any(type(sid) is not str or not sid for sid in self.scene_ids)
                or len(set(self.scene_ids)) != len(self.scene_ids)):
            raise ValueError("Explicit unique nonempty scene IDs required")
        self.expected_n_valid = _count(expected_n_valid, "expected_n_valid", positive=True)
        self.expected_n_rain = _count(expected_n_rain, "expected_n_rain")
        self.max_batch_size = _count(max_batch_size, "max_batch_size", positive=True)
        if self.expected_n_rain > self.expected_n_valid:
            raise ValueError("Expected rainy population exceeds valid population")
        self.position = self.n_valid = self.n_rain = 0
        self.poisoned = self.finished = False
        self.y_mean = self.y_m2 = 0.0
        self.mask_digest = hashlib.sha256()
        self.tables = {
            method: [{"TP": 0, "FP": 0, "FN": 0, "TN": 0,
                      "truth_equal": 0, "prediction_equal": 0} for _ in THRESHOLDS_MM_H]
            for method in METHODS
        }
        self.errors = {
            method: {"absolute_error_sum": 0.0, "squared_error_sum": 0.0, "bias_sum": 0.0,
                     "prediction_mean": 0.0, "prediction_m2": 0.0, "cross_deviation": 0.0}
            for method in METHODS
        }

    def _require_open(self):
        if self.poisoned or self.finished:
            raise RuntimeError("Accumulator is failed or already finished")

    def add(self, scene_ids, rate, valid, region, probability, quantiles_log):
        try:
            self._require_open()
            ids = tuple(scene_ids)
            batch_size = len(ids)
            if (not 1 <= batch_size <= self.max_batch_size
                    or ids != self.scene_ids[self.position:self.position + batch_size]):
                raise ValueError("Batch IDs differ from the declared complete scene order")
            rate = _floating_array(rate, "rate")
            probability = _floating_array(probability, "probability")
            quantiles_log = _floating_array(quantiles_log, "quantiles_log")
            valid, region = np.asarray(valid), np.asarray(region)
            if (rate.ndim != 4 or rate.shape[:2] != (batch_size, 1)
                    or not 1 <= rate.shape[2] * rate.shape[3] <= 10000
                    or probability.shape != rate.shape or valid.shape != rate.shape
                    or region.shape != rate.shape or valid.dtype != bool or region.dtype != bool
                    or quantiles_log.shape != (batch_size, 32, *rate.shape[2:])):
                raise ValueError("Exact batch, channel, spatial and boolean-mask shapes required")
            if (not np.isfinite(probability).all() or (probability < 0).any()
                    or (probability > 1).any() or not np.isfinite(quantiles_log).all()
                    or (quantiles_log[:, 0] <= math.log1p(0.1)).any()
                    or (np.diff(quantiles_log, axis=1) <= 0).any()):
                raise ValueError("Model output must contain finite probabilities and ordered quantiles")
            selected = (valid & region)[:, 0]
            y = rate[:, 0][selected].astype(np.float64)
            p = probability[:, 0][selected].astype(np.float64)
            q = quantiles_log.transpose(0, 2, 3, 1)[selected].astype(np.float64)
            if not np.isfinite(y).all() or (y < 0).any():
                raise ValueError("Selected reference rates must be finite and nonnegative")
            points = point_candidates_log(q, p)
            with np.errstate(over="raise", invalid="raise"):
                y32 = y.astype(np.float32)
                points32 = {method: value.astype(np.float32) for method, value in points.items()}
            if not np.isfinite(y32).all() or any(not np.isfinite(v).all() for v in points32.values()):
                raise ValueError("FP32 classification conversion must remain finite")
            rainy = int((y32 > np.float32(0.1)).sum())
            if (self.n_valid + y.size > self.expected_n_valid
                    or self.n_rain + rainy > self.expected_n_rain):
                raise ValueError("Batch exceeds the declared valid or rainy population")
            self._add_values(y, y32, points, points32)
            for index, sid in enumerate(ids):
                encoded = sid.encode("utf-8")
                self.mask_digest.update(len(encoded).to_bytes(4, "big") + encoded)
                self.mask_digest.update(np.asarray(selected[index].shape, dtype="<i8").tobytes())
                self.mask_digest.update(selected[index].tobytes(order="C"))
            self.position += batch_size
            self.n_rain += rainy
        except BaseException:
            self.poisoned = True
            raise

    def _add_values(self, y, y32, points, points32):
        n = int(y.size)
        if not n:
            return
        total = self.n_valid + n
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            y_mean = float(y.mean())
            centered_y = y - y_mean
            y_m2 = float(np.square(centered_y).sum())
            y_delta = y_mean - self.y_mean
            merge_weight = self.n_valid * n / total
            for method in METHODS:
                prediction = points[method]
                error = prediction - y
                state = self.errors[method]
                prediction_mean = float(prediction.mean())
                centered_prediction = prediction - prediction_mean
                prediction_delta = prediction_mean - state["prediction_mean"]
                state["absolute_error_sum"] += float(np.abs(error).sum())
                state["squared_error_sum"] += float(np.square(error).sum())
                state["bias_sum"] += float(error.sum())
                state["prediction_m2"] += float(np.square(centered_prediction).sum()) + prediction_delta**2 * merge_weight
                state["cross_deviation"] += float((centered_y * centered_prediction).sum()) + y_delta * prediction_delta * merge_weight
                state["prediction_mean"] += prediction_delta * n / total
                for index, threshold in enumerate(THRESHOLDS_MM_H):
                    truth = y32 > np.float32(threshold)
                    predicted = points32[method] > np.float32(threshold)
                    table = self.tables[method][index]
                    table["TP"] += int((truth & predicted).sum())
                    table["FP"] += int((~truth & predicted).sum())
                    table["FN"] += int((truth & ~predicted).sum())
                    table["TN"] += int((~truth & ~predicted).sum())
                    table["truth_equal"] += int((y32 == np.float32(threshold)).sum())
                    table["prediction_equal"] += int((points32[method] == np.float32(threshold)).sum())
            self.y_mean += y_delta * n / total
            self.y_m2 += y_m2 + y_delta**2 * merge_weight
        if (not math.isfinite(self.y_mean) or not math.isfinite(self.y_m2)
                or any(not math.isfinite(value) for state in self.errors.values() for value in state.values())):
            raise ValueError("Accumulated physical-error statistics must remain finite")
        self.n_valid = total

    def finish(self):
        try:
            self._require_open()
            if (self.position != len(self.scene_ids) or self.n_valid != self.expected_n_valid
                    or self.n_rain != self.expected_n_rain):
                raise ValueError("Complete declared scene and pixel populations required")
            methods = {}
            for method in METHODS:
                state = self.errors[method]
                correlation = None
                if self.y_m2 > 0 and state["prediction_m2"] > 0:
                    correlation = (state["cross_deviation"] / math.sqrt(self.y_m2)
                                   / math.sqrt(state["prediction_m2"]))
                    if not math.isfinite(correlation) or abs(correlation) > 1 + 1e-12:
                        raise ValueError("Invalid Pearson correlation")
                    correlation = max(-1.0, min(1.0, correlation))
                continuous = {
                    "MAE": state["absolute_error_sum"] / self.n_valid,
                    "RMSE": math.sqrt(state["squared_error_sum"] / self.n_valid),
                    "MeanBias": state["bias_sum"] / self.n_valid,
                    "Pearson_CC": correlation,
                    "units": "mm/h for MAE, RMSE and MeanBias; dimensionless Pearson_CC",
                    "zero_denominator": ["Pearson_CC"] if correlation is None else [],
                }
                rows = []
                for threshold, table in zip(THRESHOLDS_MM_H, self.tables[method]):
                    if sum(table[key] for key in ("TP", "FP", "FN", "TN")) != self.n_valid:
                        raise ValueError("Contingency table does not cover the valid population")
                    metrics = classification_metrics(table)
                    rows.append({"threshold_mm_h": threshold, **table, **metrics,
                                 "zero_denominator": [key for key, value in metrics.items() if value is None]})
                methods[method] = {"continuous": continuous, "thresholds": rows}
            result = {
                "scenes": self.position,
                "n_scenes": self.position,
                "n_valid": self.n_valid,
                "n_rain": self.n_rain,
                "supervision_mask_sha256": self.mask_digest.hexdigest(),
                "methods": methods,
                "continuous_precision": "FP64 original physical point proxies and reference rates",
                "classification_precision": "FP32 predictions and reference rates; strict > FP32 threshold",
                "population_unit": "PIXEL_TIMES",
                "point_method_status": "INHERITED_FINITE_NODE_PROXIES",
            }
            self.finished = True
            return result
        except BaseException:
            self.poisoned = True
            raise
