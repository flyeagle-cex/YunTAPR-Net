"""One bounded certificate refinement of the saved unresolved Train cases."""

from collections import Counter, deque
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import linprog

from tools.research_readiness import a20_full_node_lp as lp


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_SHA = "f006b9b4a3e23f64cc33c509ceb151410bd6751aa5f640926886003c0f000065"
REPORTS_SHA = "e94319b8de514dfbce261edcb3ee4cf82259bec098b45ec788c384adc03d85ea"
MAX_BOXES = 63
LP_SECONDS = 0.25
CASE_SECONDS = 35
TOTAL_SECONDS = 300


def _budget_bounds(original, truth, active, p, lower, upper):
    padding = 1e-10 * max(1., truth, upper[-1])
    physical = np.expm1(original)
    tau = lp.TAU[active]
    residual = truth - physical[active]
    budget = np.maximum(tau * residual, (tau - 1) * residual).sum() + padding
    before_slopes = np.cumsum(tau)
    after_slopes = np.cumsum((1 - tau)[::-1])[::-1]
    lo, hi = lower.copy(), upper.copy()
    lo[active] = np.maximum(lo[active], truth - budget / before_slopes - padding)
    hi[active] = np.minimum(hi[active], truth + budget / after_slopes + padding)
    mask = np.ones(lp.NODES, dtype=bool)
    mask[active] = False
    needed = lp.NODES * (lp.TARGET - padding) / p - physical[mask].sum()
    after = np.r_[np.cumsum(hi[active][::-1])[::-1][1:], 0.]
    lo[active] = np.maximum(lo[active], (needed - after - padding) / np.arange(1, len(active) + 1))
    return np.maximum.accumulate(lo), np.minimum.accumulate(hi[::-1])[::-1]


def refine(p, original, truth, *, max_boxes=MAX_BOXES, deadline=None):
    case_end = time.monotonic() + CASE_SECONDS
    if deadline is not None:
        case_end = min(case_end, deadline)
    original = np.asarray(original, dtype=np.float64)
    active = np.flatnonzero(original[:-1] > lp.WEAK_LIMIT)
    physical = np.expm1(original)
    if not active.size or not 0 < p <= 1 or truth > 1000 or physical[-1] > 1000:
        return dict(status="UNRESOLVED", checked_boxes=0, certified_boxes=0)
    baseline = lp.pinball((truth - physical) / 20)
    _, _, _, root = lp._outer_problem(p, original, truth, active, baseline)
    lower, upper = np.asarray(root[:lp.NODES]).T
    queue = deque([(lower, upper)])
    checked = excluded = 0
    unresolved_leaf = False
    padding = 1e-12 * max(1., truth, physical[-1])
    loss_limit = Fraction.from_float(float(baseline - lp.GAIN_TOLERANCE + padding))
    while queue and checked < max_boxes and time.monotonic() < case_end:
        lo, hi = _budget_bounds(original, truth, active, p, *queue.popleft())
        checked += 1
        if np.any(lo > hi):
            excluded += 1
            continue
        cost, matrix, rhs, bounds = lp._outer_problem(
            p, original, truth, active, baseline, physical_box=(lo, hi),
        )
        # For any true candidate s=0. Making the objective care about loss
        # also gives a useful primal candidate when the original slack was zero.
        cost[lp.NODES:lp.SLACK] = 1 / lp.NODES
        cost[lp.SLACK] = 100
        matrix[-2:, lp.SLACK] = -1.
        bounds[lp.SLACK] = (0., 1024.)
        limit = min(LP_SECONDS, case_end - time.monotonic())
        if limit <= 0:
            unresolved_leaf = True
            break
        result = linprog(cost, A_ub=matrix, b_ub=rhs, bounds=bounds, method="highs",
                         options={"time_limit": limit})
        if result.success:
            lower_bound = lp.certified_lower_bound(cost, matrix, rhs, bounds,
                                                   result.ineqlin.marginals)
            if lower_bound > loss_limit:
                excluded += 1
                continue
            candidate = lp._restore_moment(original, result.x[:lp.NODES], active)
            witness = lp.verify_witness(p, original, truth, candidate)
            if witness is not None:
                return dict(status="VERIFIED_WITNESS", checked_boxes=checked, certified_boxes=excluded, **witness)
        widths = np.log1p(hi[active]) - np.log1p(lo[active])
        split = active[np.argmax((1 - lp.TAU[active]) * widths ** 2)]
        cut = lo[split] + (hi[split] - lo[split]) / 2
        if not lo[split] < cut < hi[split]:
            unresolved_leaf = True
            continue
        left, right = hi.copy(), lo.copy()
        left[split], right[split] = cut, cut
        queue.extend(((lo, left), (right, hi)))
    status = "EXCLUDED_BY_COVERED_BOXES" if not queue and not unresolved_leaf else "UNRESOLVED"
    return dict(status=status, checked_boxes=checked, certified_boxes=excluded)


def synthetic_preflight():
    physical = np.r_[np.linspace(.01, .99, 29), 22., 50., 640.]
    p = 19.999 * 32 / physical.sum()
    original = np.log1p(physical)
    known = original.copy()
    known[29:31] += [-.01, (5 / 3) * .01]
    assert lp.verify_witness(p, original, 80., known) is not None
    assert lp.solve(p, original, 30.)["status"] == "UNRESOLVED"
    exclusion = refine(p, original, 30.)
    witness = refine(p, original, 80.)
    assert exclusion["status"] == "EXCLUDED_BY_COVERED_BOXES", exclusion
    assert witness["status"] == "VERIFIED_WITNESS", witness
    assert refine(p, original, 30., max_boxes=1)["status"] == "UNRESOLVED"
    return dict(excluded_boxes=exclusion["checked_boxes"], witness_boxes=witness["checked_boxes"])


def _read_pinned(path, length_limit, expected):
    with path.open("rb") as stream:
        raw = stream.read(length_limit + 1)
    if len(raw) > length_limit or sha256(raw).hexdigest() != expected:
        raise ValueError("Frozen local refinement input differs")
    return json.loads(raw), len(raw)


def run_once():
    run = ROOT / "docs/research_readiness/.local/a20_train_full_node_lp_20261122_v1"
    prior = run / "output"
    destination = run / "offline_refinement_v1"
    destination.mkdir(exist_ok=False)
    began = time.monotonic()
    cases, archive_bytes = _read_pinned(prior / "private_full_node_inputs.json", 16384, ARCHIVE_SHA)
    reports, report_bytes = _read_pinned(prior / "private_full_node_results.json", 65536, REPORTS_SHA)
    targets = {report["case_sha256"] for report in reports if report["status"] == "UNRESOLVED"}
    original_counts = Counter(report["status"] for report in reports)
    if original_counts != {"UNRESOLVED": 7, "EXCLUDED_BY_OUTER_BOUND": 3}:
        raise ValueError("Original case dispositions differ")
    selected = [case for case in cases if case["case_sha256"] in targets]
    if len(selected) != 7 or {case["case_sha256"] for case in selected} != targets:
        raise ValueError("Expected the seven original unresolved case keys")
    final = []
    for case in selected:
        result = refine(case["p"], case["qlog"], case["truth_fp32"], deadline=began + TOTAL_SECONDS)
        final.append(dict(case_sha256=case["case_sha256"], time_block=case["time_block"], **result))
    with (destination / "private_results.json").open("x", encoding="utf-8") as stream:
        json.dump(final, stream, indent=2, allow_nan=False)
    counts = Counter(report["status"] for report in final)
    summary = dict(status="COMPLETE_ONE_OFFLINE_REFINEMENT", inherited_exclusions=3,
                   original_unresolved=7, new_outcomes=dict(counts),
                   combined_exclusions=3 + counts["EXCLUDED_BY_COVERED_BOXES"],
                   total_witnesses=counts["VERIFIED_WITNESS"], total_unresolved=counts["UNRESOLVED"],
                   witness_blocks=len({r["time_block"] for r in final if r["status"] == "VERIFIED_WITNESS"}),
                   boxes_checked=sum(r["checked_boxes"] for r in final),
                   boxes_certified=sum(r["certified_boxes"] for r in final),
                   archive_sha256=ARCHIVE_SHA, original_case_reports_sha256=REPORTS_SHA,
                   local_input_bytes=archive_bytes + report_bytes, local_input_opens=2,
                   seconds=round(time.monotonic() - began, 6), scientific_source_reads=0, forwards=0,
                   optimizer_updates=0, gate_fits=0, final_2025_access=False, study_acceptance="NOT_VERIFIED")
    with (destination / "completion.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, allow_nan=False)
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-approved-offline", action="store_true")
    args = parser.parse_args()
    result = run_once() if args.run_approved_offline else synthetic_preflight()
    print(json.dumps(result, indent=2, allow_nan=False))
