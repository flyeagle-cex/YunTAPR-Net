"""Physical-rain quantile scores from the existing Development forward pass."""

import math

import numpy as np

from .dynamic_training import TerrainTail
from .tail_diagnostics import TailDiagnostics


PHYSICAL_SCALE_MM_H = 20.0


class PhysicalPinball:
    def __init__(self):
        self.counts = [0] * 7
        self.sums = [0.0] * 7

    def add(self, rate, quantiles_log, valid):
        rate = np.asarray(rate, dtype=np.float32)
        quantiles_log = np.asarray(quantiles_log, dtype=np.float64)
        valid = np.asarray(valid)
        if valid.dtype != bool or valid.shape != rate.shape or quantiles_log.shape != (32, *rate.shape):
            raise ValueError("Physical score target, mask and 32-node shapes differ")
        if not np.isfinite(rate[valid]).all() or (rate[valid] < 0).any():
            raise ValueError("Invalid physical reference")
        selected = valid & (rate > np.float32(0.1))
        qlog = quantiles_log[:, selected]
        if not np.isfinite(qlog).all() or (qlog < 0).any() or (np.diff(qlog, axis=0) <= 0).any():
            raise ValueError("Finite positive ordered physical quantiles required")
        with np.errstate(over="raise", invalid="raise"):
            physical = np.expm1(qlog)
            errors = rate[selected].astype(np.float64)[None] - physical
            tau = ((np.arange(32, dtype=np.float64) + 0.5) / 32)[:, None]
            per_pixel = np.maximum(tau * errors, (tau - 1.0) * errors).mean(axis=0)
        if not np.isfinite(per_pixel).all():
            raise ValueError("Physical score overflow; no clipping or silent exclusion")
        observed = rate[selected]
        for index, (lower, upper) in enumerate(zip(TailDiagnostics.EDGES, TailDiagnostics.EDGES[1:])):
            mask = (observed > np.float32(lower)) & (observed <= np.float32(upper))
            self.counts[index] += int(mask.sum())
            self.sums[index] += float(per_pixel[mask].sum())

    def finish(self):
        rows = []
        for index, (lower, upper) in enumerate(zip(TailDiagnostics.EDGES, TailDiagnostics.EDGES[1:])):
            count = self.counts[index]
            total = self.sums[index]
            rows.append({
                "lower": lower,
                "upper": None if math.isinf(upper) else upper,
                "n_rain": count,
                "pinball_sum_mm_h": total,
                "pinball_mm_h": total / count if count else None,
                "normalized_pinball": total / (PHYSICAL_SCALE_MM_H * count) if count else None,
            })
        count = sum(self.counts)
        total = math.fsum(self.sums)
        return {
            "scope": "UNWEIGHTED_32_NODE_PHYSICAL_PINBALL_EXISTING_DEV_PASS",
            "scale_mm_h": PHYSICAL_SCALE_MM_H,
            "n_rain": count,
            "pinball_sum_mm_h": total,
            "pinball_mm_h": total / count if count else None,
            "normalized_pinball": total / (PHYSICAL_SCALE_MM_H * count) if count else None,
            "strata": rows,
        }


class UpperQuantileTail(TerrainTail):
    def __init__(self, pack):
        super().__init__(pack)
        self.physical = PhysicalPinball()

    def add_batch(self, output, batch):
        super().add_batch(output, batch)
        valid = (batch.valid & batch.region).detach().cpu().numpy()[:, 0]
        rate = batch.rate.detach().cpu().numpy()[:, 0]
        qlog = output.conditional_quantiles_log.detach().double().cpu().numpy()
        for index in range(len(batch.ids)):
            self.physical.add(rate[index], qlog[index], valid[index])

    def finish_checked(self, report, ids):
        result = super().finish_checked(report, ids)
        physical = self.physical.finish()
        if [row["n_rain"] for row in physical["strata"]] != [row["n_rain"] for row in result["strata"]]:
            raise RuntimeError("Physical and original log scores have different rainy populations")
        result["physical_pinball"] = physical
        return result
