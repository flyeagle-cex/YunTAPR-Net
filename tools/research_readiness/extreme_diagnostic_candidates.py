"""Synthetic-only preparation of partially identified exceedance diagnostics.

These are proposed diagnostic methods, not a researcher-frozen evaluation
protocol. No model, data reader, training entry point, or tail extrapolation is
provided. Bounds describe distributions compatible with model quantiles; they
are not confidence intervals or guarantees about real precipitation risk.
"""
from dataclasses import dataclass
import math

import numpy as np


METHOD_STATUS = "CANDIDATE_SYNTHETIC_VERIFIED_NOT_RESEARCHER_FROZEN"


@dataclass(frozen=True)
class Bounds:
    lower: np.ndarray
    upper: np.ndarray


def _intervals(lower, upper):
    lo, hi = np.asarray(lower, dtype=np.float64), np.asarray(upper, dtype=np.float64)
    if (lo.ndim != 1 or not lo.size or lo.shape != hi.shape
            or not np.isfinite(lo).all() or not np.isfinite(hi).all()
            or (lo < 0).any() or (hi > 1).any() or (lo > hi).any()):
        raise ValueError("Nonempty aligned finite probability intervals required")
    return lo, hi


def _labels(labels, shape):
    y = np.asarray(labels)
    if y.shape != shape or y.dtype != np.bool_:
        raise ValueError("Explicit boolean labels on the same population required")
    return y


def exceedance_bounds(probability, quantiles_log, threshold_mm_h):
    """Bounds for P(R > r), r >= .1, without choosing a tail distribution.

    Layout is [pixel_time, 32]. Inputs must already have the frozen supervision
    mask applied. A missing feature mask must never remove supervision here.
    At q_i == log1p(r), F(r) >= tau_i; strict exceedance is preserved.
    """
    p = np.asarray(probability, dtype=np.float64)
    q = np.asarray(quantiles_log, dtype=np.float64)
    if (isinstance(threshold_mm_h, (bool, np.bool_))
            or not isinstance(threshold_mm_h, (int, float))
            or not math.isfinite(threshold_mm_h) or threshold_mm_h < .1):
        raise ValueError("Explicit finite threshold at least .1 mm/h required")
    _intervals(p, p)
    if (q.shape != (p.size, 32) or not np.isfinite(q).all()
            or (q[:, 0] <= math.log1p(.1)).any()
            or (np.diff(q, axis=1) <= 0).any()):
        raise ValueError("Finite strictly ordered 32 conditional log quantiles required")
    if threshold_mm_h == .1:
        return Bounds(p.copy(), p.copy())
    tau = (np.arange(32, dtype=np.float64) + .5) / 32
    z = math.log1p(threshold_mm_h)
    f_lower = np.max(np.where(q <= z, tau, 0.), axis=1)
    f_upper = np.min(np.where(q > z, tau, 1.), axis=1)
    return Bounds(p * (1 - f_upper), p * (1 - f_lower))


def brier_bounds(labels, lower, upper):
    """Conservative full-population Brier bounds; no support-subset deletion."""
    lo, hi = _intervals(lower, upper)
    y = _labels(labels, lo.shape)
    best = np.where(y, (1 - hi) ** 2, lo ** 2)
    worst = np.where(y, (1 - lo) ** 2, hi ** 2)
    return float(best.mean()), float(worst.mean())


def auroc_bounds(labels, lower, upper):
    """Tie-aware ranking bounds in O(N log N), without a pixel-pair matrix.

    Each positive lower score is compared with negative upper scores for the
    lower bound; the converse supplies the upper bound. A single-class sample
    has undefined AUROC and returns None, never zero.
    """
    lo, hi = _intervals(lower, upper)
    y = _labels(labels, lo.shape)
    n_positive, n_negative = int(y.sum()), int((~y).sum())
    if not n_positive or not n_negative:
        return None

    def rank_sum(positive, negative):
        ordered = np.sort(negative)
        less = np.searchsorted(ordered, positive, side="left")
        less_equal = np.searchsorted(ordered, positive, side="right")
        return float((less.astype(np.float64) + .5 * (less_equal - less)).sum())

    denominator = n_positive * n_negative
    return (rank_sum(lo[y], hi[~y]) / denominator,
            rank_sum(hi[y], lo[~y]) / denominator)


def decision_identification(lower, upper, probability_cutoff):
    """Use the declared rule P(R>r) >= cutoff; unresolved decisions stay explicit."""
    lo, hi = _intervals(lower, upper)
    if (isinstance(probability_cutoff, (bool, np.bool_))
            or not isinstance(probability_cutoff, (int, float))
            or not math.isfinite(probability_cutoff) or not 0 < probability_cutoff <= 1):
        raise ValueError("Explicit probability cutoff in (0,1] required")
    positive = lo >= probability_cutoff
    negative = hi < probability_cutoff
    return dict(guaranteed_positive=positive, guaranteed_negative=negative,
                unresolved=~(positive | negative))
