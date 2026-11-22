"""Bound strong-rain physical Pinball along one fixed weak-preserving line."""

import math

import numpy as np

from tools.research_readiness.a20_fixed_endpoint_bounds import (
    THRESHOLD, pinball, point, weak_preserving_vertex,
)


def crossing_amplitude(probability, original, truth, *, tolerance=1e-10, max_intervals=4095):
    """Find a strict crossing with improvement, certify the tolerance, or remain unresolved."""
    original = np.asarray(original, dtype=np.float64)
    if (original.shape != (32,) or not np.isfinite(original).all()
            or (original < 0).any() or (np.diff(original) <= 0).any()
            or not 0 <= probability <= 1 or not math.isfinite(truth) or truth <= THRESHOLD
            or not math.isfinite(tolerance) or tolerance <= 0
            or type(max_intervals) is not int or max_intervals < 1):
        raise ValueError("Expected ordered log nodes and a finite strong-rain truth")
    if point(probability, original) > THRESHOLD:
        raise ValueError("The baseline must be below or equal to the point threshold")
    vertex = weak_preserving_vertex(original)
    if point(probability, vertex) <= THRESHOLD:
        return {"status": "NO_CROSSING"}
    direction = vertex - original
    baseline = pinball((truth - np.expm1(original)) / 20)

    # Convex A and a non-crossing baseline imply one boundary on this segment.
    # Use its lower bracket so a bound includes every strictly crossing alpha.
    low, high = 0.0, 1.0
    for _ in range(44):
        middle = (low + high) / 2
        if point(probability, original + middle * direction) > THRESHOLD:
            high = middle
        else:
            low = middle

    work = [(low, 1.0)]
    for checked in range(1, max_intervals + 1):
        left, right = work.pop()
        qa, qb = np.expm1(original + left * direction), np.expm1(original + right * direction)
        closest = np.clip(truth, np.minimum(qa, qb), np.maximum(qa, qb))
        # Each physical node is monotone in alpha. Minimizing each Pinball
        # term independently gives a lower bound for a shared alpha.
        lower_delta = float(pinball((truth - closest) / 20) - baseline)
        if lower_delta < -tolerance:
            alpha = (left + right) / 2
            log_nodes = original + alpha * direction
            delta = float(pinball((truth - np.expm1(log_nodes)) / 20) - baseline)
            score = point(probability, log_nodes)
            if delta < -tolerance and score > THRESHOLD and (np.diff(log_nodes) > 0).all():
                return {"status": "AMPLITUDE_WITNESS", "alpha": alpha, "point_a": score,
                        "physical_pinball_delta": delta, "intervals": checked}
            if alpha == left or alpha == right:
                break
            work.extend(((alpha, right), (left, alpha)))
        if not work:
            return {"status": "NO_GAIN_BEYOND_TOLERANCE", "tolerance": tolerance, "intervals": checked}
    return {"status": "UNRESOLVED", "intervals": checked}


def synthetic_preflight():
    p = 0.9375
    nodes = np.log1p(np.r_[5., np.linspace(19.5, 22.5, 29), 23., 40.])
    positive = crossing_amplitude(p, nodes, 35.)
    assert positive["status"] == "AMPLITUDE_WITNESS"
    assert positive["point_a"] > THRESHOLD and positive["physical_pinball_delta"] < 0
    bounded = crossing_amplitude(p, nodes, 20.01)
    assert bounded["status"] == "NO_GAIN_BEYOND_TOLERANCE"
    assert crossing_amplitude(.1, nodes, 35.)["status"] == "NO_CROSSING"
    assert crossing_amplitude(p, nodes, 22., max_intervals=1)["status"] == "UNRESOLVED"
    assert crossing_amplitude(p, nodes, 22.)["status"] == "AMPLITUDE_WITNESS"
    vertex = weak_preserving_vertex(nodes)
    adjusted = nodes + positive["alpha"] * (vertex - nodes)
    assert adjusted[-1] == nodes[-1] and (np.diff(adjusted) > 0).all()
    for weak in (.11, .5, 1.):
        assert math.isclose(pinball(np.log1p(weak) - adjusted), pinball(np.log1p(weak) - nodes),
                            rel_tol=0., abs_tol=1e-12)
    print("PASS: strict amplitude witness, loss lower bound, no crossing, unresolved budget, weak-loss invariance")


if __name__ == "__main__":
    synthetic_preflight()
