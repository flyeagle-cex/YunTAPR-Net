"""Reproduce the eight artificial CPU checks without reading scientific inputs.

Run from the repository root with the existing research interpreter:
    F:/conda_envs/rain-basics/python.exe -B tools/research_readiness/check_physical_training_diagnostics.py

Results go to stdout. The historical DIAGNOSTICS_CHECK.json is preserved.
"""

import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import numpy as np
import torch

from tools.research_readiness.paired_point_metrics import PointMetricAccumulator
from yuntapr.experimental.research_readiness.physical_training_diagnostics import PhysicalTrainingTail


def main():
    checks = {}
    y = np.array([0, .5, 2, 6, 11, 21, 31, 51], np.float32).reshape(2, 4)
    rate = np.stack([y, y]).reshape(2, 1, 2, 4)
    valid = np.ones_like(rate, dtype=bool)
    valid[1, 0, 0, 0] = False
    region = np.ones_like(valid)
    q = np.broadcast_to(
        np.log1p(np.linspace(.2, 40, 32))[:, None, None], (32, 2, 4)
    ).copy()
    qs = np.stack([q, q])
    p = np.full_like(rate, .625)
    ids = ["2024-06-01T00:00:00", "2024-06-02T00:00:00"]
    pack = SimpleNamespace(
        values=np.array([[[500, 1500, 2500, 500], [1500, 2500, 500, 1500]]]),
        valid=np.ones((1, 2, 4), bool), region=np.ones((2, 4), bool),
    )
    batch = SimpleNamespace(
        ids=ids, rate=torch.tensor(rate), valid=torch.tensor(valid), region=torch.tensor(region),
    )
    output = SimpleNamespace(
        rain_prob=torch.tensor(p).to(torch.bfloat16),
        conditional_quantiles_log=torch.tensor(qs),
    )
    selected = (valid & region)[:, 0]
    yy = rate[:, 0][selected].astype(np.float64)
    qq = qs.transpose(0, 2, 3, 1)[selected]
    rain = yy > np.float32(.1)
    tau = (np.arange(32) + .5) / 32
    error = np.log1p(yy[rain, None]) - qq[rain]
    log = float(np.maximum(tau * error, (tau - 1) * error).mean(1).mean())
    coverage = (np.log1p(yy[rain, None]) <= qq[rain]).mean(0).tolist()
    report = {"groups": {"all": {"summary": {
        "n_valid": int(selected.sum()), "n_rain": int(rain.sum()),
        "conditional_pinball": log, "coverage": coverage,
        "brier": float(np.square(.625 - rain).mean()),
    }}}}
    tail = PhysicalTrainingTail(pack)
    tail.add_batch(output, batch)
    result = tail.finish_checked(report, ids)
    checks["two_scene_complete_finish"] = True
    rows = result["training_scene_statistics"]
    totals = result["training_statistics_totals"]
    assert len(rows) == 2 and [row["n_valid"] for row in rows] == [8, 7]
    assert totals["n_rain"] == 14 and totals["n_strong"] == 6 and totals["n_weak"] == 2
    checks["scene_population_masks_strong_weak"] = True
    physical_error = yy[rain, None] - np.expm1(qq[rain])
    expected = float(np.maximum(tau * physical_error, (tau - 1) * physical_error).mean(1).sum())
    assert math.isclose(
        sum(row["pinball_sum_mm_h"] for row in result["physical_pinball"]["strata"]),
        expected, abs_tol=1e-10,
    )
    assert all(len(row["physical_strata"]) == 7 and len(row["log_strata"]) == 7 for row in rows)
    checks["seven_bin_physical_log_and_direct_loss"] = True
    whole = PointMetricAccumulator(ids, expected_n_valid=15, expected_n_rain=14)
    whole.add(ids, rate, valid, region, p.astype(float), qs)
    whole_report = whole.finish()
    for method in ("A", "B", "C"):
        for key in ("bias_sum", "absolute_error_sum", "squared_error_sum"):
            assert math.isclose(
                totals["point_error_sums"][method][key], whole.errors[method][key],
                rel_tol=1e-12, abs_tol=1e-10,
            )
        for index, row in enumerate(totals["point_thresholds"][method]):
            assert all(
                row[key] == whole_report["methods"][method]["thresholds"][index][key]
                for key in ("TP", "FP", "FN", "TN")
            )
    checks["scene_ABC_sums_and_thresholds_match_pooled_accumulator"] = True
    for label, mutate in [
        ("physical_total_corruption", lambda t: t.training_scenes[0]["physical_strata"][0].update(pinball_sum_mm_h=100)),
        ("scene_count_corruption", lambda t: t.training_scenes[0].update(n_valid=99)),
    ]:
        corrupted = PhysicalTrainingTail(pack)
        corrupted.add_batch(output, batch)
        mutate(corrupted)
        try:
            corrupted.finish_checked(report, ids)
        except RuntimeError:
            checks[label + "_rejected"] = True
        else:
            raise AssertionError(label)
    reordered = PhysicalTrainingTail(pack)
    reordered.add_batch(output, batch)
    try:
        reordered.finish_checked(report, list(reversed(ids)))
    except RuntimeError:
        checks["scene_reordering_rejected"] = True
    else:
        raise AssertionError("reordering")
    try:
        tail.add_batch(output, batch)
    except RuntimeError:
        checks["finished_reuse_rejected"] = True
    else:
        raise AssertionError("reuse")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
