"""Stream necessary bounds for one positive, sign-gated physical amplitude shift."""

import math

import numpy as np

from tools.research_readiness.rh700_amplitude_feasibility import (
    POINT_ROUNDING_BOUNDARY,
    TAU,
    THRESHOLD,
)


MAX_STRONG = 484
TAIL_THRESHOLD_LOG = math.log1p(float(THRESHOLD))
ROUNDING_MARGIN = 128 * np.finfo(np.float64).eps


def _finite(value):
    return value if math.isfinite(value) else None


class _Minimum:
    """Nominal minimum and conservative envelopes over all finite row bounds."""

    def __init__(self):
        self.nominal = self.low = self.high = math.inf

    def add(self, estimates, radii):
        finite = np.isfinite(estimates)
        if finite.any():
            self.nominal = min(self.nominal, float(estimates[finite].min()))
            self.low = min(self.low, float((estimates[finite] - radii[finite]).min()))
            self.high = min(self.high, float((estimates[finite] + radii[finite]).min()))

    def crosses_point(self, score, probability):
        with np.errstate(over="ignore", divide="ignore"):
            delta = (POINT_ROUNDING_BOUNDARY - score) / probability
            radius = (ROUNDING_MARGIN * POINT_ROUNDING_BOUNDARY) / probability
        self.add(delta, radius)


def _analytic_change(delta, knots, active_fraction):
    """Population mean physical Pinball/20 change for all moving strong nodes."""
    if delta == 0.0:
        return 0.0
    # Sum(tau)=16 per row. The loss change per node is
    # (1-tau)*delta - clip(truth-node, 0, delta).
    with np.errstate(over="ignore"):
        scale_free = 0.5 - np.clip(knots / delta, 0.0, 1.0)
    return float(scale_free.mean() * (delta / 20.0) * active_fraction)


class AmplitudeBounds:
    """Only strong rows are retained, and only in memory for the convex check."""

    def __init__(self):
        self.strong = self.nonstrong = 0
        self.gated_strong = self.gated_nonstrong = 0
        self.baseline_a_tp = self.baseline_a_fp = 0
        self.baseline_q32_tp = self.baseline_q32_fp = 0
        self._fixed_strong_hits = 0
        self._moving_strong_can_cross = False
        self._hit = _Minimum()
        self._point_stop = _Minimum()
        self._tail_stop = _Minimum()
        self._nodes = np.empty((MAX_STRONG, len(TAU)))
        self._probabilities = np.empty(MAX_STRONG)
        self._truth = np.empty(MAX_STRONG)

    def update(self, probability, qlog, truth, mfc700, mfc_valid):
        probability, qlog, truth, mfc700, mfc_valid = map(
            np.asarray, (probability, qlog, truth, mfc700, mfc_valid)
        )
        if (truth.ndim != 1 or truth.dtype != np.float32
                or any(v.shape != truth.shape for v in (probability, mfc700, mfc_valid))
                or qlog.shape != (truth.size, len(TAU)) or qlog.dtype != np.float64
                or mfc_valid.dtype != np.bool_ or not np.isfinite(mfc700[mfc_valid]).all()
                or not all(np.isfinite(v).all() for v in (probability, truth, qlog))
                or np.any((probability < 0) | (probability > 1)) or np.any(truth < 0)
                or np.any(qlog < 0) or np.any(qlog[:, 1:] <= qlog[:, :-1])):
            raise ValueError("Expected aligned supervised rain, probability, ordered nodes and signed MFC masks")

        strong = truth > THRESHOLD
        nstrong = int(strong.sum())
        if self.strong + nstrong > MAX_STRONG:
            raise ValueError("The frozen Train strong-population cap was exceeded")
        nonstrong = ~strong
        gate = mfc_valid & (mfc700 > 0)
        with np.errstate(over="raise", invalid="raise"):
            nodes = np.expm1(qlog)
            score = probability * (nodes / len(TAU)).sum(axis=1)
        with np.errstate(over="ignore"):
            a_hit = score.astype(np.float32) > THRESHOLD
        tail_hit = qlog[:, -1] > TAIL_THRESHOLD_LOG

        moving_strong = gate & strong
        point_rising = gate & (probability > 0) & ~a_hit
        hit_needed = strong & point_rising
        point_protected = nonstrong & point_rising
        tail_protected = nonstrong & gate & ~tail_hit
        self._hit.crosses_point(score[hit_needed], probability[hit_needed])
        self._point_stop.crosses_point(score[point_protected], probability[point_protected])
        tail_deltas = float(THRESHOLD) - nodes[tail_protected, -1]
        self._tail_stop.add(tail_deltas, np.full(tail_deltas.shape, ROUNDING_MARGIN * THRESHOLD))
        self._moving_strong_can_cross |= bool(hit_needed.any())

        end = self.gated_strong + int(moving_strong.sum())
        span = slice(self.gated_strong, end)
        self._nodes[span] = nodes[moving_strong]
        self._probabilities[span] = probability[moving_strong]
        self._truth[span] = truth[moving_strong]
        self.strong += nstrong
        self.nonstrong += truth.size - nstrong
        self.gated_nonstrong += int((gate & nonstrong).sum())
        self.gated_strong = end
        self.baseline_a_tp += int((strong & a_hit).sum())
        self.baseline_a_fp += int((nonstrong & a_hit).sum())
        self.baseline_q32_tp += int((strong & tail_hit).sum())
        self.baseline_q32_fp += int((nonstrong & tail_hit).sum())
        self._fixed_strong_hits += int((strong & ~gate & a_hit).sum())

    def finish(self):
        first = 0.0 if self.baseline_a_tp else max(0.0, self._hit.nominal)
        upper = min(self._point_stop.nominal, self._tail_stop.nominal)
        report = dict(
            decision="NUMERICAL_BOUNDARY_UNRESOLVED",
            first_hit_lower_open_mm_h=_finite(first),
            nonstrong_point_upper_inclusive_mm_h=_finite(self._point_stop.nominal),
            nonstrong_q32_upper_inclusive_mm_h=_finite(self._tail_stop.nominal),
            nonstrong_upper_inclusive_mm_h=_finite(upper),
            baseline_a_tp=self.baseline_a_tp, baseline_a_fp=self.baseline_a_fp,
            baseline_q32_tp=self.baseline_q32_tp, baseline_q32_fp=self.baseline_q32_fp,
            strong=self.strong, nonstrong=self.nonstrong,
            gated_strong=self.gated_strong, gated_nonstrong=self.gated_nonstrong,
            local_joint_witness_verified=False,
            strong_physical_pinball_delta_at_witness=None,
            a_tp_at_witness=None,
            weak_guard_checked=False,
            coefficient_fits=0,
        )
        if not math.isfinite(first):
            if not self._moving_strong_can_cross:
                report["decision"] = "STOP_NO_POTENTIAL_STRONG_HIT"
            return report

        # A definite stop needs disjoint outer bounds; a witness must instead
        # satisfy the conservative inner bounds. An exact midpoint rounds down.
        low = 0.0 if self.baseline_a_tp else max(0.0, self._hit.low)
        outer_upper = min(self._point_stop.high, self._tail_stop.high)
        if low > outer_upper:
            report["decision"] = "STOP_NEGATIVE_CEILING"
            return report

        nodes = self._nodes[:self.gated_strong]
        truth = self._truth[:self.gated_strong, None]
        knots = truth - nodes
        if not knots.size or (knots <= 0).sum() >= knots.size // 2:
            # The right derivative at zero is nonnegative; convexity then
            # makes every positive shift non-improving, including a flat segment.
            report["decision"] = "STOP_NO_STRONG_PINBALL_IMPROVEMENT"
            return report
        active_fraction = self.gated_strong / self.strong
        k = knots.size // 2 - 1
        minimizer = float(np.partition(knots.ravel(), k)[k])
        outer_delta = min(max(minimizer, low), outer_upper)
        change = _analytic_change(outer_delta, knots, active_fraction)
        if change > ROUNDING_MARGIN * max(1.0, outer_delta / 20.0):
            report["decision"] = "STOP_NO_STRONG_PINBALL_IMPROVEMENT"
            return report

        safe_lower = 0.0 if self.baseline_a_tp else self._hit.high
        safe_lower = math.nextafter(max(0.0, safe_lower), math.inf)
        safe_upper = min(self._point_stop.low, self._tail_stop.low)
        delta = min(max(minimizer, safe_lower), safe_upper)
        if (not math.isfinite(delta) or delta < safe_lower or delta <= 0.0
                or _analytic_change(delta, knots, active_fraction) >= -ROUNDING_MARGIN * max(1.0, delta / 20.0)):
            return report

        # This verifies one local mathematical witness, not a chosen coefficient.
        # Reapply the frozen log/physical readout on every moving strong row.
        try:
            with np.errstate(over="raise", invalid="raise"):
                moved_log = np.log1p(nodes + delta)
                moved = np.expm1(moved_log)
                if np.any(moved_log[:, 1:] <= moved_log[:, :-1]):
                    return report
                p = self._probabilities[:self.gated_strong]
                moved_point = p * (moved / len(TAU)).sum(axis=1)
                error_before = knots / 20.0
                error_after = (truth - moved) / 20.0
                loss_before = np.maximum(TAU * error_before, (TAU - 1.0) * error_before)
                loss_after = np.maximum(TAU * error_after, (TAU - 1.0) * error_after)
                actual_change = float((loss_after - loss_before).mean() * active_fraction)
        except FloatingPointError:
            return report
        with np.errstate(over="ignore"):
            true_hits = self._fixed_strong_hits + int((moved_point.astype(np.float32) > THRESHOLD).sum())
        if true_hits and actual_change < -ROUNDING_MARGIN * max(1.0, delta / 20.0):
            report.update(
                decision="LOCAL_JOINT_NECESSARY_CONDITIONS_NOT_EXCLUDED",
                local_joint_witness_verified=True,
                strong_physical_pinball_delta_at_witness=actual_change,
                a_tp_at_witness=true_hits,
            )
        return report
