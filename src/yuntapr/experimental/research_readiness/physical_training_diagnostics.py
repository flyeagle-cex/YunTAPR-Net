"""Scene sufficient statistics from the inherited Development traversal."""

import math

import numpy as np

from tools.research_readiness.paired_point_metrics import (
    METHODS, THRESHOLDS_MM_H, PointMetricAccumulator,
)
from .upper_quantile_diagnostics import PhysicalPinball, UpperQuantileTail


def _close(actual, expected, message):
    if not math.isfinite(actual) or not math.isfinite(expected) or not math.isclose(
        actual, expected, rel_tol=1e-12, abs_tol=1e-10
    ):
        raise RuntimeError(message)


class PhysicalTrainingTail(UpperQuantileTail):
    """Supplement the existing log and physical summaries without extra inference."""

    def __init__(self, pack):
        super().__init__(pack)
        self.training_scenes = []
        self.failed = self.finished = False

    def add_batch(self, output, batch):
        try:
            if self.failed or self.finished:
                raise RuntimeError("Diagnostics are failed or already finished")
            super().add_batch(output, batch)
            rate = batch.rate.detach().cpu().numpy()
            valid = batch.valid.detach().cpu().numpy()
            region = batch.region.detach().cpu().numpy()
            probability = output.rain_prob.detach().double().cpu().numpy()
            qlog = output.conditional_quantiles_log.detach().double().cpu().numpy()
            for index, sid in enumerate(batch.ids):
                selected = (valid & region)[index, 0]
                observed = rate[index, 0][selected].astype(np.float32)
                n_valid = int(selected.sum())
                n_rain = int((observed > np.float32(.1)).sum())
                # Every frozen scene has supervised pixels. An empty scene is a
                # population failure, rather than a silently excluded point record.
                points = PointMetricAccumulator(
                    [sid], expected_n_valid=n_valid, expected_n_rain=n_rain,
                    max_batch_size=1,
                )
                one = slice(index, index + 1)
                points.add([sid], rate[one], valid[one], region[one],
                           probability[one], qlog[one])
                errors = {
                    method: {name: points.errors[method][name] for name in
                             ("bias_sum", "absolute_error_sum", "squared_error_sum")}
                    for method in METHODS
                }
                point_report = points.finish()
                physical = PhysicalPinball()
                physical.add(rate[index, 0], qlog[index], selected)
                physical_report = physical.finish()
                truth = observed > np.float32(.1)
                prob = probability[index, 0][selected]
                self.training_scenes.append({
                    "sample_id": sid,
                    "n_valid": n_valid, "n_rain": n_rain,
                    "n_strong": int((observed > np.float32(20)).sum()),
                    "n_weak": int(((observed > np.float32(.1)) &
                                   (observed <= np.float32(1))).sum()),
                    "brier_sum": float(np.square(prob - truth).sum()),
                    "physical_strata": physical_report["strata"],
                    "point_error_sums": errors,
                    "point_metrics": point_report,
                })
        except BaseException:
            self.failed = True
            raise

    def finish_checked(self, report, ids):
        try:
            if self.failed or self.finished:
                raise RuntimeError("Diagnostics are failed or already finished")
            result = super().finish_checked(report, ids)
            summary = report["groups"]["all"]["summary"]
            scenes = self.training_scenes
            if tuple(row["sample_id"] for row in scenes) != tuple(ids):
                raise RuntimeError("Saved scene identities differ")
            for scene, log in zip(scenes, result["scene_sufficient_statistics"]):
                if scene["sample_id"] != log["sample_id"]:
                    raise RuntimeError("Log and physical scene identities differ")
                scene["log_strata"] = log["strata"]
                if [r["n_rain"] for r in scene["physical_strata"]] != [
                    r["n_rain"] for r in scene["log_strata"]
                ]:
                    raise RuntimeError("Scene physical and log populations differ")
                if sum(r["n_rain"] for r in scene["physical_strata"]) != scene["n_rain"]:
                    raise RuntimeError("Scene rainy counts differ")
            totals = {key: sum(row[key] for row in scenes)
                      for key in ("n_valid", "n_rain", "n_strong", "n_weak")}
            if (totals["n_valid"] != summary["n_valid"] or
                    totals["n_rain"] != summary["n_rain"]):
                raise RuntimeError("Scene counts differ from evaluator")
            for index, global_row in enumerate(result["physical_pinball"]["strata"]):
                if sum(row["physical_strata"][index]["n_rain"] for row in scenes) != global_row["n_rain"]:
                    raise RuntimeError("Scene physical-bin counts differ")
                _close(math.fsum(row["physical_strata"][index]["pinball_sum_mm_h"]
                                 for row in scenes), global_row["pinball_sum_mm_h"],
                       "Scene physical-bin sums differ")
            if (sum(row["n_rain"] for row in result["strata"][4:]) != totals["n_strong"]
                    or result["strata"][0]["n_rain"] != totals["n_weak"]):
                raise RuntimeError("Strong or weak population differs")
            totals["brier_sum"] = math.fsum(row["brier_sum"] for row in scenes)
            _close(totals["brier_sum"] / totals["n_valid"], summary["brier"],
                   "Scene Brier sums differ from evaluator")
            totals["point_error_sums"] = {
                method: {key: math.fsum(row["point_error_sums"][method][key] for row in scenes)
                         for key in ("bias_sum", "absolute_error_sum", "squared_error_sum")}
                for method in METHODS
            }
            totals["point_thresholds"] = {}
            for method in METHODS:
                matrices = []
                for index, threshold in enumerate(THRESHOLDS_MM_H):
                    table = {key: sum(row["point_metrics"]["methods"][method]["thresholds"][index][key]
                                      for row in scenes) for key in ("TP", "FP", "FN", "TN")}
                    if sum(table.values()) != totals["n_valid"]:
                        raise RuntimeError("Point threshold matrix population differs")
                    matrices.append({"threshold_mm_h": threshold, **table})
                totals["point_thresholds"][method] = matrices
            result["training_scene_statistics"] = scenes
            result["training_statistics_totals"] = totals
            result["ranking_aggregation"] = "Use frozen pooled evaluator AP/AUROC; never average scene AP/AUROC"
            self.finished = True
            return result
        except BaseException:
            self.failed = True
            raise
