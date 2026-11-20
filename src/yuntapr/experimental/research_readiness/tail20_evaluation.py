"""Compute the frozen TAIL20 gates in the existing E9 Development forward."""

import hashlib
import math

import numpy as np

from tools.research_readiness.conditional_tail_gate import POPULATION, PROTOCOL, evaluate
from tools.research_readiness.mountain_pair_metrics import MountainAccumulator


class Tail20Observer:
    def __init__(self, pack, ids, baseline):
        self.terrain = MountainAccumulator(pack, ids)
        self.baseline = baseline
        self.mask_sha = hashlib.sha256()
        self.n_weak = 0
        self.weak_log_sum = 0.
        self.q32_tp = self.q32_fp = self.point_tp = self.point_fp = 0
        self.taus = (np.arange(32, dtype=np.float64) + .5) / 32

    def add_batch(self, output, batch):
        rate = batch.rate.detach().cpu().numpy()
        valid = batch.valid.detach().cpu().numpy()
        region = batch.region.detach().cpu().numpy()
        p = output.rain_prob.detach().double().cpu().numpy()
        qlog = output.conditional_quantiles_log.detach().double().cpu().numpy()
        self.terrain.add(batch.ids, rate, valid, region, p, qlog)
        mask = (valid & region)[:, 0]
        for sid, selection in zip(batch.ids, mask):
            name = sid.encode("utf-8")
            self.mask_sha.update(len(name).to_bytes(4, "big") + name)
            self.mask_sha.update(np.asarray(selection.shape, dtype="<i8").tobytes())
            self.mask_sha.update(selection.tobytes(order="C"))
        truth = rate[:, 0][mask]
        q = qlog.transpose(0, 2, 3, 1)[mask]
        strong = truth > np.float32(20)
        supported = q[:, -1] > math.log1p(20)
        with np.errstate(over="raise", invalid="raise"):
            point = (p[:, 0][mask] * np.expm1(q).mean(axis=1)).astype(np.float32) > np.float32(20)
        self.q32_tp += int((supported & strong).sum())
        self.q32_fp += int((supported & ~strong).sum())
        self.point_tp += int((point & strong).sum())
        self.point_fp += int((point & ~strong).sum())
        weak = (truth > np.float32(.1)) & (truth <= np.float32(1))
        self.n_weak += int(weak.sum())
        delta = np.log1p(truth[weak].astype(np.float64))[:, None] - q[weak]
        self.weak_log_sum += float(np.maximum(delta * self.taus, delta * (self.taus - 1)).mean(axis=1).sum())

    def finish(self, report):
        terrain = self.terrain.finish(report)
        population = dict(terrain["population"], scenes=terrain["scenes"], n_weak=self.n_weak)
        if population != POPULATION:
            raise ValueError("Unexpected fixed Development cohort counts")
        strong_cells = [row for group in terrain["elevation_groups"].values()
                        for row in group["cells"][4:] if row["n_rain"]]
        values = report["groups"]["all"]["summary"]
        candidate = dict(
            protocol=PROTOCOL, population=population, final_2025_access=False,
            identity=dict(
                population_ids_sha256=report["population_ids_sha256"],
                partition_sha256=report["partition_sha256"],
                supervision_mask_sha256=self.mask_sha.hexdigest(),
                paired_truth_mask_terrain_sha256=terrain["paired_population_sha256"],
            ),
            metrics=dict(
                strong_physical_pinball_over20=math.fsum(
                    r["physical_pinball_over20"] * r["n_rain"] for r in strong_cells
                ) / population["n_strong"],
                q32_support_tp=self.q32_tp, q32_support_fp=self.q32_fp,
                point_a_tp=self.point_tp, point_a_fp=self.point_fp,
                weak_log_pinball=self.weak_log_sum / self.n_weak,
                occurrence_brier=values["brier"], occurrence_ap=values["average_precision"],
                occurrence_auroc=values["auroc"],
            ),
        )
        return dict(candidate=candidate, comparison=evaluate(self.baseline, candidate))
