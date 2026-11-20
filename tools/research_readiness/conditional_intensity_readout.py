"""Save aligned Development predictions and summarize finite-node bounds."""

import hashlib
import math
from pathlib import Path

import numpy as np

from tools.research_readiness.extreme_diagnostic_candidates import exceedance_bounds


RAIN_EDGES = (0.1, 1., 5., 10., 20., 30., 50., math.inf)
WIDTH_EDGES = np.linspace(0., 1 / 32, 33)
TAU = (np.arange(32, dtype=np.float64) + .5) / 32
GRID = (100, 100)


class DevelopmentReadout:
    def __init__(self, folder, ids, identity, check, *, valid_per_scene=3430):
        self.folder = Path(folder)
        self.ids = tuple(ids)
        self.identity = identity
        self.check = check
        self.valid_per_scene = valid_per_scene
        self.position = 0
        self.shards = []
        self.lower_sum = self.upper_sum = 0.
        self.width_counts = np.zeros(32, dtype=np.int64)
        self.above_counts = np.zeros(33, dtype=np.int64)
        self.covered = np.zeros((7, 32), dtype=np.int64)
        self.rain_counts = np.zeros(7, dtype=np.int64)
        self.loss_sums = np.zeros(7)
        check()
        self.folder.mkdir(exist_ok=False)

    def add(self, ids, rate, valid, region, probability, quantiles_log):
        ids = tuple(ids)
        n = len(ids)
        if not 1 <= n <= 8 or ids != self.ids[self.position:self.position + n]:
            raise ValueError("Readout batch does not match frozen scene order")
        shape = (n, 1, *GRID)
        if (any(v.shape != shape for v in (rate, valid, region, probability))
                or valid.dtype != np.bool_ or region.dtype != np.bool_
                or quantiles_log.shape != (n, 32, *GRID)
                or rate.dtype != np.float32 or quantiles_log.dtype != np.float64):
            raise ValueError("Readout expects the frozen batch shapes and native FP32/FP64 rates/quantiles")
        mask = (valid & region)[:, 0]
        if not (mask.sum(axis=(1, 2)) == self.valid_per_scene).all():
            raise ValueError("Readout supervision population changed")
        truth = rate[:, 0][mask]
        raw_p = probability[:, 0][mask]
        p = raw_p.astype(np.float32)
        qlog = quantiles_log.transpose(0, 2, 3, 1)[mask]
        if not np.array_equal(p, raw_p) or not np.isfinite(truth).all() or (truth < 0).any():
            raise ValueError("Readout requires lossless p conversion and finite nonnegative labels")
        bounds = exceedance_bounds(p, qlog, 20.)
        widths = bounds.upper - bounds.lower
        width_counts = np.histogram(widths, bins=WIDTH_EDGES)[0]
        if int(width_counts.sum()) != p.size:
            raise ValueError("Finite-node widths exceed the declared histogram support")
        self.width_counts += width_counts
        self.lower_sum += bounds.lower.sum()
        self.upper_sum += bounds.upper.sum()
        self.above_counts += np.bincount(
            (qlog > math.log1p(20.)).sum(axis=1), minlength=33,
        )
        for i, (low, high) in enumerate(zip(RAIN_EDGES, RAIN_EDGES[1:])):
            take = (truth > np.float32(low)) & (truth <= np.float32(high))
            delta = np.log1p(truth[take].astype(np.float64))[:, None] - qlog[take]
            self.rain_counts[i] += int(take.sum())
            self.covered[i] += (delta <= 0).sum(axis=0)
            self.loss_sums[i] += np.maximum(delta * TAU, delta * (TAU - 1)).mean(axis=1).sum()
        # mask.nonzero() in C order maps the flattened arrays back to scene, row and column.
        fields = dict(scene_ids=np.asarray(ids), supervision_mask=mask,
                      p=p, qlog=qlog, truth_mm_h=truth)
        reserve = sum(v.nbytes for v in fields.values()) + 16384
        self.check(reserve)
        path = self.folder / f"batch_{len(self.shards):03d}.npz"
        with path.open("xb") as stream:
            np.savez(stream, **fields)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                self.check()
                digest.update(chunk)
        self.shards.append(dict(file=path.name, scene_start=self.position, scenes=n,
                                n_valid=int(p.size), bytes=path.stat().st_size,
                                sha256=digest.hexdigest()))
        self.position += n

    def finish(self, mask_sha256):
        if self.position != len(self.ids) or mask_sha256 != self.identity["supervision_mask_sha256"]:
            raise ValueError("Readout incomplete or different from the frozen supervision mask")
        n_valid = len(self.ids) * self.valid_per_scene
        n_rain = int(self.rain_counts.sum())
        n_strong = int(self.rain_counts[4:].sum())
        if (n_rain, n_strong) != (self.identity["n_rain"], self.identity["n_strong"]):
            raise ValueError("Readout label population differs from the inherited counts")
        bins = [
            dict(lower_exclusive_mm_h=low, upper_inclusive_mm_h=high if math.isfinite(high) else None,
                 n_rain=int(count), covered_by_node=covered.tolist(),
                 log_pinball_sum=float(loss),
                 conditional_log_pinball=float(loss / count) if count else None)
            for low, high, count, covered, loss in zip(
                RAIN_EDGES, RAIN_EDGES[1:], self.rain_counts, self.covered, self.loss_sums)
        ]
        mean_lower, mean_upper = self.lower_sum / n_valid, self.upper_sum / n_valid
        return dict(
            identity=self.identity, n_valid=n_valid, n_rain=n_rain, n_strong=n_strong,
            storage=dict(folder=self.folder.name, files=self.shards, p="float32",
                         qlog="float64 log1p(mm/h)", truth_mm_h="float32", supervision_mask="bool",
                         join="mask.nonzero() in C order maps each prediction to scene_ids, row, column"),
            threshold_mm_h=20, mean_lower=mean_lower, mean_upper=mean_upper,
            mean_width=mean_upper - mean_lower, width_histogram_edges=WIDTH_EDGES.tolist(),
            width_histogram_counts=self.width_counts.tolist(),
            quantile_nodes_above20_counts=self.above_counts.tolist(),
            tau=TAU.tolist(), wet_covered_by_node=self.covered.sum(axis=0).tolist(),
            conditional_bins=bins, interpretation="CONSERVATIVE_CLOSED_NOT_ENDPOINT_ATTAINABILITY",
        )
