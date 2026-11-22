"""Analytic necessary bounds for a uniform RH700-weighted physical shift."""

import math

import numpy as np


THRESHOLD = np.float32(20.)
# 20 is the even FP32 endpoint. An exactly halfway value still rounds to 20.
POINT_ROUNDING_BOUNDARY = (float(THRESHOLD) + float(np.nextafter(THRESHOLD, np.float32(np.inf)))) / 2
TAU = (np.arange(32, dtype=np.float64) + .5) / 32


def shift_gate(qlog, humidity, valid):
    if (qlog.dtype != np.float64 or qlog.shape != (humidity.size, 32)
            or humidity.ndim != 1 or valid.shape != humidity.shape or valid.dtype != bool
            or not np.isfinite(qlog).all() or np.any(qlog < 0) or np.any(np.diff(qlog, axis=1) <= 0)
            or not np.isfinite(humidity[valid]).all()):
        raise ValueError("Ordered FP64 nodes and valid RH700 values required")
    low_q32 = qlog[:, -1] <= math.log1p(20.)
    return np.where(valid & low_q32, np.clip(humidity / 100., 0, 1), 0.)


def required_interval(p, qlog, truth, humidity, valid):
    """Compute an open lower and closed upper bound before numerical recheck."""
    gate = shift_gate(qlog, humidity, valid)
    if (p.shape != gate.shape or truth.shape != gate.shape or truth.dtype != np.float32
            or not np.isfinite(p).all() or np.any((p < 0) | (p > 1))
            or not np.isfinite(truth).all() or np.any(truth < 0)):
        raise ValueError("Aligned probabilities and FP32 reference rain rates required")
    with np.errstate(over="raise", invalid="raise"):
        physical = np.expm1(qlog)
    mean = physical.mean(axis=1)
    a = p * mean
    grad = p * gate
    strong = truth > THRESHOLD
    if np.any(a.astype(np.float32) > THRESHOLD):
        raise ValueError("Expected a frozen zero-hit, zero-false-positive baseline")
    rising = grad > 0
    first_hit = (POINT_ROUNDING_BOUNDARY - a[strong & rising]) / grad[strong & rising]
    point_stop = (POINT_ROUNDING_BOUNDARY - a[~strong & rising]) / grad[~strong & rising]
    tail_stop = (20. - physical[~strong & (gate > 0), -1]) / gate[~strong & (gate > 0)]
    bounds = dict(first_hit=max(0., float(first_hit.min())) if first_hit.size else None,
                  point_stop=float(point_stop.min()) if point_stop.size else None,
                  tail_stop=float(tail_stop.min()) if tail_stop.size else None)
    ceilings = [bounds[key] for key in ("point_stop", "tail_stop") if bounds[key] is not None]
    upper = min(ceilings, default=None)
    lower = bounds["first_hit"]
    return dict(**bounds, upper=upper, analytically_nonempty=lower is not None and (upper is None or lower < upper))


def measure(delta, p, qlog, truth, humidity, valid):
    """Recompute the frozen scores for a single specified synthetic shift."""
    gate = shift_gate(qlog, humidity, valid)
    if not math.isfinite(delta) or delta <= 0:
        raise ValueError("One positive physical shift is required")
    with np.errstate(over="raise", invalid="raise"):
        start = np.expm1(qlog)
        nodes = start + delta * gate[:, None]
        qlog_after = np.log1p(nodes)
        point = (p * nodes.mean(axis=1)).astype(np.float32)
    strong = truth > THRESHOLD
    weak = (truth > np.float32(.1)) & (truth <= np.float32(1.))
    hit = point > THRESHOLD

    def pinball(errors):
        return np.maximum(TAU * errors, (TAU - 1.) * errors).mean()

    physical_gain = None
    if strong.any():
        y = truth[strong, None].astype(np.float64)
        physical_gain = float(pinball((y - nodes[strong]) / 20.) - pinball((y - start[strong]) / 20.))
    weak_change = None
    if weak.any():
        y = np.log1p(truth[weak, None].astype(np.float64))
        weak_change = float(pinball(y - qlog_after[weak]) - pinball(y - qlog[weak]))
    return dict(true_hits=int((strong & hit).sum()), false_hits=int((~strong & hit).sum()),
                additional_q32_false_support=int((~strong & (qlog[:, -1] <= math.log1p(20.))
                                                   & (qlog_after[:, -1] > math.log1p(20.))).sum()),
                physical_strong_pinball_delta=physical_gain, weak_log_pinball_delta=weak_change)
