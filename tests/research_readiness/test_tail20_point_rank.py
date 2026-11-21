"""Synthetic E9 observer checks for optional strong-rain reporting."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import torch

from yuntapr.experimental.research_readiness import tail20_evaluation


class Tail20PointRankTests(unittest.TestCase):
    def observe(self, elevation, with_ranking):
        ids = ("synthetic-1", "synthetic-2")
        rate = np.array([[[[30, 20, 31, 1]]], [[[5, 25, 0, 1]]]], dtype=np.float32)
        valid = np.ones_like(rate, dtype=bool)
        valid[0, 0, 0, 3] = False
        region = np.ones_like(valid)
        probability = np.full(rate.shape, 0.5, dtype=np.float64)
        expected_a = np.array([[[[24, 20, 19, 100]]], [[[23, 20, 12, 5]]]], dtype=np.float64)
        qlog = np.log1p(2 * expected_a + (np.arange(32)[None, :, None, None] - 15.5) / 50)
        pack = SimpleNamespace(
            grid=SimpleNamespace(identity="SYNTHETIC"),
            values=np.array([[elevation]]),
            valid=np.ones((1, 1, 4), dtype=bool),
            region=region[0, 0],
        )
        observer = tail20_evaluation.Tail20Observer(pack, ids, {}, report_point_rank=with_ranking)
        for index, sid in enumerate(ids):
            selected = slice(index, index + 1)
            output = SimpleNamespace(rain_prob=torch.from_numpy(probability[selected]),
                                     conditional_quantiles_log=torch.from_numpy(qlog[selected]))
            batch = SimpleNamespace(ids=(sid,), rate=torch.from_numpy(rate[selected]),
                                    valid=torch.from_numpy(valid[selected]), region=torch.from_numpy(region[selected]))
            observer.add_batch(output, batch)

        wet = (rate[:, 0] > np.float32(.1)) & valid[:, 0]
        nodes = qlog.transpose(0, 2, 3, 1)[wet]
        truth = rate[:, 0][wet].astype(np.float64)
        taus = (np.arange(32, dtype=np.float64) + .5) / 32
        log_error = np.log1p(truth)[:, None] - nodes
        summary = dict(n_valid=7, n_rain=6, brier=.25, average_precision=.5, auroc=.5,
                       conditional_pinball=float(np.maximum(taus * log_error, (taus - 1) * log_error).mean()),
                       covered=[int((nodes[:, -1] >= np.log1p(truth)).sum())])
        report = dict(groups=dict(all=dict(summary=summary)), population_ids_sha256="SCENES",
                      partition_sha256="PARTITION")
        synthetic_population = dict(scenes=2, n_valid=7, n_rain=6, n_strong=3, n_weak=1)
        with patch.object(tail20_evaluation, "POPULATION", synthetic_population), patch.object(
            tail20_evaluation, "evaluate", return_value={"status": "SYNTHETIC"}
        ):
            result = observer.finish(report)

        high_strong = (rate[:, 0] > 20) & valid[:, 0] & (pack.values[0] >= 2000)
        high_truth = rate[:, 0][high_strong]
        high_nodes = qlog.transpose(0, 2, 3, 1)[high_strong]
        physical_error = (high_truth[:, None] - np.expm1(high_nodes)) / 20
        expected_loss = (float(np.maximum(taus * physical_error, (taus - 1) * physical_error).mean())
                         if high_strong.any() else None)
        return result, expected_loss

    def test_optional_reporting_preserves_joint_gate_and_uses_fixed_threshold(self):
        elevation = [2000, 2100, 1999, 2600]
        legacy, _ = self.observe(elevation, False)
        augmented, expected_loss = self.observe(elevation, True)
        result = augmented.pop("point_rank_report")
        self.assertEqual(legacy, augmented)
        all_pixels = result["all"]
        high = result["elevation_ge_2000m"]
        self.assertAlmostEqual(all_pixels["ap20"], .7)
        self.assertEqual(all_pixels["point_a"], dict(tp=1, fp=1, fn=2, pod=1 / 3))
        self.assertEqual(all_pixels["strong_physical_pinball_over20"],
                         legacy["candidate"]["metrics"]["strong_physical_pinball_over20"])
        self.assertAlmostEqual(high["ap20"], .75)
        self.assertEqual((high["n_strong"], high["n_non_strong"]), (2, 3))
        self.assertEqual(high["point_a"], dict(tp=1, fp=1, fn=1, pod=.5))
        self.assertAlmostEqual(high["strong_physical_pinball_over20"], expected_loss)

    def test_high_group_without_strong_truth_has_no_estimated_ap_pod_or_amplitude(self):
        result, _ = self.observe([1900, 1500, 1900, 2600], True)
        high = result["point_rank_report"]["elevation_ge_2000m"]
        self.assertEqual((high["n_strong"], high["n_non_strong"]), (0, 1))
        self.assertEqual(high["point_a"], dict(tp=0, fp=0, fn=0, pod=None))
        self.assertIsNone(high["ap20"])
        self.assertIsNone(high["strong_physical_pinball_over20"])
