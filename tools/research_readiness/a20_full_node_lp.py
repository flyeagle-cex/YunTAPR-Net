"""Bound full-node amplitude feasibility and verify the original constraints."""

from fractions import Fraction
import json
import math

import numpy as np
from scipy.optimize import linprog

from tools.research_readiness.a20_fixed_endpoint_bounds import (
    TAU, THRESHOLD, WEAK_LIMIT, pinball, point, weak_preserving_vertex,
)


NODES = 32
SLACK = 2 * NODES
TARGET = float(THRESHOLD) + float(np.spacing(THRESHOLD)) / 2
GAIN_TOLERANCE = 1e-10
MOMENT_TOLERANCE = 1e-12
SOLVER_SECONDS = 2


def certified_lower_bound(objective, matrix, rhs, bounds, multipliers):
    """Check a box-constrained LP dual bound using exact binary-float fractions."""
    if not np.isfinite(multipliers).all():
        raise ValueError("Finite dual multipliers required")
    exact = Fraction.from_float
    dual = [(i, exact(float(y))) for i, y in enumerate(multipliers) if y < 0]
    result = sum(y * exact(float(rhs[i])) for i, y in dual)
    for j, (lower, upper) in enumerate(bounds):
        reduced = exact(float(objective[j])) - sum(y * exact(float(matrix[i, j])) for i, y in dual)
        result += reduced * exact(float(lower if reduced >= 0 else upper))
    return result


def _moment_box(original, active, padding):
    # For fixed z_i, precedence bounds its earlier nodes above by z_i and
    # its later nodes below by z_i. The frozen moment then bounds z_i.
    weights = 1 - TAU[active]
    moment = float(weights @ original[active])
    through = np.cumsum(weights)
    following = np.cumsum(weights[::-1])[::-1]
    before = np.r_[0., through[:-1]]
    after = np.r_[following[1:], 0.]
    lower = np.maximum(WEAK_LIMIT, (moment - after * original[-1] - padding) / through)
    upper = np.minimum(original[-1], (moment - before * WEAK_LIMIT + padding) / following)
    return lower, upper


def _outer_problem(p, original, truth, active, baseline, *, tighten=True, physical_box=None):
    physical = np.expm1(original)
    upper = float(physical[-1])
    padding = 1e-12 * max(1., truth, upper)
    bounds = [(float(x), float(x)) for x in physical]
    lower_physical = np.ones(active.size)
    upper_physical = np.full(active.size, upper)
    if active.size and tighten:
        lower, higher = _moment_box(original, active, padding)
        lower_physical = np.maximum(1., np.expm1(lower) - padding)
        upper_physical = np.minimum(upper, np.expm1(higher) + padding)
    if physical_box is not None:
        lower_physical, upper_physical = (limit[active] for limit in physical_box)
    for i, left, right in zip(active, lower_physical, upper_physical):
        bounds[i] = (float(left), float(right))
    bounds.extend([(0., max(truth, upper) / 20)] * NODES)
    bounds.append((0., TARGET + baseline + 1.))
    matrix, rhs = [], []

    def add(terms, limit):
        row = np.zeros(SLACK + 1)
        for column, coefficient in terms:
            row[column] = coefficient
        matrix.append(row)
        rhs.append(float(limit))

    for i, tau in enumerate(TAU):
        if i + 1 < NODES:
            add(((i, 1.), (i + 1, -1.)), 0.)
        add(((i, -tau / 20), (NODES + i, -1.)), -(tau / 20) * truth + padding)
        add(((i, (1 - tau) / 20), (NODES + i, -1.)), ((1 - tau) / 20) * truth + padding)
    add([*((i, -p / NODES) for i in range(NODES)), (SLACK, -1.)], -TARGET + padding)
    add([*((NODES + i, 1 / NODES) for i in range(NODES)), (SLACK, -1.)],
        baseline - GAIN_TOLERANCE + padding)

    if active.size:
        weights = 1 - TAU[active]
        moment = float(weights @ original[active])
        width = upper_physical - lower_physical
        slopes = np.divide(np.log1p(width / (1 + lower_physical)), width,
                           out=1 / (1 + lower_physical), where=width > 0)
        intercepts = np.log1p(lower_physical) - slopes * lower_physical
        add(zip(active, weights * slopes), moment - float(weights @ intercepts) + padding)
        tangent_slopes = 1 / (1 + physical[active])
        tangent_intercepts = original[active] - tangent_slopes * physical[active]
        add(zip(active, -weights * tangent_slopes), float(weights @ tangent_intercepts) - moment + padding)
    objective = np.zeros(SLACK + 1)
    objective[SLACK] = 1.
    return objective, np.asarray(matrix), np.asarray(rhs), bounds


def _restore_moment(original, candidate, active):
    """Give the relaxed point one deterministic repair in the original log space."""
    repaired = original.copy()
    if not active.size:
        return repaired
    weights = 1 - TAU[active]
    target_moment = float(weights @ original[active])
    values = np.sort(np.log1p(np.clip(candidate[active], 1., np.expm1(original[-1]))))
    low, high = float(WEAK_LIMIT - values[-1]), float(original[-1] - values[0])
    for _ in range(64):
        middle = (low + high) / 2
        if weights @ np.clip(values + middle, WEAK_LIMIT, original[-1]) < target_moment:
            low = middle
        else:
            high = middle
    restored = np.clip(values + (low + high) / 2, WEAK_LIMIT, original[-1])
    # Both terms obey the same moment, so this small inward move restores order.
    repaired[active] = 0.999999 * restored + 0.000001 * original[active]
    return repaired


def verify_witness(p, original, truth, candidate):
    active = np.flatnonzero(original[:-1] > WEAK_LIMIT)
    frozen = np.ones(NODES, dtype=bool)
    frozen[active] = False
    if (candidate.shape != original.shape or not np.isfinite(candidate).all()
            or not np.array_equal(candidate[frozen], original[frozen])
            or np.any(np.diff(candidate) <= 0) or np.any(candidate[active] < WEAK_LIMIT)):
        return None
    moment_error = float((1 - TAU[active]) @ (candidate[active] - original[active]))
    delta = float(pinball((truth - np.expm1(candidate)) / 20)
                  - pinball((truth - np.expm1(original)) / 20))
    score = point(p, candidate)
    if (abs(moment_error) <= MOMENT_TOLERANCE and score > THRESHOLD
            and math.isfinite(delta) and delta < -GAIN_TOLERANCE):
        return dict(point_a=score, physical_pinball_delta=delta, weak_moment_error=moment_error,
                    witness_log_nodes=candidate.tolist())
    return None


def solve(p, original, truth, *, tighten=True):
    original = np.asarray(original, dtype=np.float64)
    if (original.shape != (NODES,) or not np.isfinite(original).all() or np.any(original < 0)
            or np.any(np.diff(original) <= 0) or not 0 <= p <= 1
            or not math.isfinite(truth) or truth > 1000 or np.float32(truth) <= THRESHOLD):
        raise ValueError("Expected finite synthetic ordered quantiles and strong rain")
    with np.errstate(over="raise", invalid="raise"):
        if np.expm1(original[-1]) > 1000 or point(p, original) > THRESHOLD:
            raise ValueError("Expected bounded synthetic nodes and no baseline crossing")
        baseline = pinball((truth - np.expm1(original)) / 20)
    active = np.flatnonzero(original[:-1] > WEAK_LIMIT)
    objective, matrix, rhs, bounds = _outer_problem(p, original, truth, active, baseline, tighten=tighten)
    result = linprog(objective, A_ub=matrix, b_ub=rhs, bounds=bounds, method="highs",
                     options={"time_limit": SOLVER_SECONDS})
    if not result.success:
        return dict(status="UNRESOLVED", reason="NO_CHECKABLE_DUAL_OR_PRIMAL")
    dual = result.ineqlin.marginals
    lower = certified_lower_bound(objective, matrix, rhs, bounds, dual)
    if lower > 0:
        return dict(status="EXCLUDED_BY_OUTER_BOUND", slack_lower_bound=float(lower),
                    dual={str(i): float(y) for i, y in enumerate(dual) if y < 0})
    for candidate in (np.log1p(result.x[:NODES]),
                      _restore_moment(original, result.x[:NODES], active)):
        witness = verify_witness(p, original, truth, candidate)
        if witness is not None:
            return dict(status="VERIFIED_WITNESS", **witness)
    return dict(status="UNRESOLVED", reason="OUTER_SOLUTION_FAILS_ORIGINAL_CONSTRAINTS",
                relaxed_slack=float(result.fun))


def synthetic_preflight():
    nodes = np.log1p(np.r_[5., np.linspace(19.5, 22.5, 29), 23., 40.])
    witness = solve(0.9375, nodes, 60.)
    no_gain = np.log1p(np.r_[np.linspace(0.01, 0.99, 29), 22., 27., 565.])
    no_gain_truth = float(np.float32(20.01))
    crossing_ceiling = point(1., weak_preserving_vertex(no_gain))
    exclusion = solve(1., no_gain, no_gain_truth)
    exclusion["crossing_only_ceiling"] = crossing_ceiling
    one_free = np.log1p(np.r_[np.linspace(0.01, 0.99, 30), 115., 500.])
    false_positive = solve(1., one_free, 600., tighten=False)
    tightened = solve(1., one_free, 600.)
    assert witness["status"] == "VERIFIED_WITNESS", witness
    assert crossing_ceiling > THRESHOLD and exclusion["status"] == "EXCLUDED_BY_OUTER_BOUND", exclusion
    assert false_positive["status"] == "UNRESOLVED" and false_positive["relaxed_slack"] < 1e-8, false_positive
    assert tightened["status"] == "EXCLUDED_BY_OUTER_BOUND", tightened
    assert np.float32(TARGET) == THRESHOLD and np.float32(np.nextafter(TARGET, np.inf)) > THRESHOLD
    objective, matrix, rhs, bounds = _outer_problem(
        1., no_gain, no_gain_truth, np.flatnonzero(no_gain[:-1] > WEAK_LIMIT),
        pinball((no_gain_truth - np.expm1(no_gain)) / 20),
    )
    dual = np.zeros_like(rhs)
    for index, value in exclusion["dual"].items():
        dual[int(index)] = value
    assert certified_lower_bound(objective, matrix, rhs, bounds, dual) > 0
    return dict(synthetic_cases=dict(witness=witness, exclusion=exclusion, relaxation_false_positive=false_positive,
                                     tightened_exclusion=tightened),
                float32_midpoint=TARGET, gain_tolerance=GAIN_TOLERANCE, moment_tolerance=MOMENT_TOLERANCE,
                scientific_source_reads=0, gate_fits=0, optimizer_updates=0, final_2025_access=False)


if __name__ == "__main__":
    print(json.dumps(synthetic_preflight(), indent=2, allow_nan=False))
