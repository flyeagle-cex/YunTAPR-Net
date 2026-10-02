"""Boundary and safety behavior of the read-only review, independent of raw data."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np
import torch
from yuntapr.training.scientific_review import (InferenceOnlyGuard, probability_bin,
    probability_summary, guard_identity, diagnostic_rules, ReviewAccumulator, numerical_counts, TAU)


class ReviewUnits(unittest.TestCase):
    def test_probability_edges_and_one(self):
        p = np.r_[0., np.arange(1, 10)/10, 1.]
        np.testing.assert_array_equal(probability_bin(p), [0,1,2,3,4,5,6,7,8,9,9])
        for values in ([np.nan], [-.001], [1.001]):
            with self.assertRaises(ValueError):
                probability_bin(values)

    def test_weighted_percentiles_reproduce_expanded_population(self):
        frequencies = {0.: 2, .125: 1, .5: 7, 1.: 2}
        expanded = np.array([key for key, n in frequencies.items() for _ in range(n)])
        summary = probability_summary(frequencies)
        self.assertAlmostEqual(summary["mean"], expanded.mean(), places=15)
        self.assertAlmostEqual(summary["std"], expanded.std(ddof=0), places=15)
        for percent in (1,5,25,50,75,95,99):
            self.assertEqual(summary["median" if percent == 50 else "p"+str(percent)], np.percentile(expanded, percent, method="linear"))

    def test_2025_rejected_before_any_reader(self):
        bad = {"role": "Validation", "year": 2025, "window_start": "2025-07-01T00:00:00+00:00"}
        with self.assertRaisesRegex(ValueError, "only frozen 2024"):
            guard_identity(bad)  # no path keys: proof of rejection before path/read access

    def test_path_escape_rejected(self):
        for relative, imerg in ((r"..\202507\evil.nc", r"F:\云南极端降水数据\raw\IMERG\2024\a.nc"),
                (r"202407\a.nc", r"F:\云南极端降水数据\raw\IMERG\2025\a.nc")):
            bad = {"role": "Validation", "year": 2024, "window_start": "2024-07-01T00:00:00+00:00",
                "b13_relative_path": relative, "imerg_day_path": imerg}
            with self.assertRaises(ValueError):
                guard_identity(bad)

    def test_optimizer_creation_is_blocked(self):
        with InferenceOnlyGuard() as guard:
            with self.assertRaisesRegex(RuntimeError, "optimizer_creation"):
                torch.optim.AdamW([torch.nn.Parameter(torch.ones(1))])
        self.assertEqual(guard.attempts["optimizer_creation"], 1)

    def test_optimizer_step_and_backward_blocked_without_optimizer(self):
        with InferenceOnlyGuard() as guard:
            with self.assertRaisesRegex(RuntimeError, "optimizer_step"):
                torch.optim.AdamW.step(None)
            with self.assertRaisesRegex(RuntimeError, "backward"):
                torch.ones(1, requires_grad=True).backward()
            with self.assertRaisesRegex(RuntimeError, "backward"):
                torch.autograd.backward(torch.ones(1))
        self.assertEqual(guard.attempts["optimizer_step"], 1)
        self.assertEqual(guard.attempts["backward"], 2)

    def test_support_crossings_and_nonfinite_are_separate(self):
        q = torch.arange(1,33,dtype=torch.float64).reshape(1,32,1,1)/10
        output = SimpleNamespace(conditional_quantiles_log=q, conditional_quantiles_physical=torch.expm1(q))
        self.assertFalse(any(numerical_counts(output).values()))
        output.conditional_quantiles_log = q.clone()
        output.conditional_quantiles_log[:,0] = .09
        self.assertEqual(numerical_counts(output)["q1_support_violation"], 1)
        output.conditional_quantiles_physical[:,3] = output.conditional_quantiles_physical[:,2]
        self.assertEqual(numerical_counts(output)["qphysical_crossing_count"], 1)
        output.conditional_quantiles_log[:,8] = float("nan")
        self.assertEqual(numerical_counts(output)["nonfinite_qlog"], 1)

    def test_known_population_aggregation_and_float32_threshold(self):
        shape = (1,1,100,100)
        target = torch.zeros(shape, dtype=torch.float32)
        target[0,0,0,:4] = torch.tensor([0., .1, 1., 20.],dtype=torch.float32)
        valid = torch.zeros(shape, dtype=torch.bool)
        valid[0,0,0,:4] = True
        p = torch.full(shape, .25, dtype=torch.float64)
        q = torch.arange(1,33,dtype=torch.float64)[None,:,None,None].expand(1,32,100,100)/10
        physical = torch.expm1(q)
        output = SimpleNamespace(rain_logit=torch.logit(p), rain_prob=p,
            conditional_quantiles_log=q, conditional_quantiles_physical=physical)
        batch = SimpleNamespace(y_imerg=target, imerg_valid_mask=valid, yunnan_eval_mask=valid)
        sample = SimpleNamespace(sample_id="fixture", imerg_window_start=datetime(2024,3,1,tzinfo=timezone.utc),
            analysis_time=datetime(2024,3,1,0,30,tzinfo=timezone.utc))
        axes = {"target_lat":np.linspace(20,30,100), "target_lon":np.linspace(97,107,100)} # synthetic test coordinates only
        accumulator = ReviewAccumulator(axes, diagnostic_rules())
        accumulator.add(output,batch,[sample],[{"index":0}])
        self.assertEqual(accumulator.global_acc.n_valid,4)
        self.assertEqual(accumulator.global_acc.n_rain,2) # float32 .1 excluded before promotion
        self.assertEqual(int(accumulator.spatial["valid_count"].sum()),4)
        self.assertEqual(int(accumulator.spatial["rainy_count"].sum()),2)
        self.assertEqual(int(accumulator.bins[:,0].sum()),4)
        self.assertEqual(int(accumulator.rate[:,0].sum()),2)
        self.assertEqual(accumulator.rate[0,0],1)
        self.assertEqual(accumulator.rate[3,0],1) # 20 belongs to (10,20]
        expected = ((np.array([1.,20.])[:,None]) <= np.expm1(np.arange(1,33)[None,:]/10)).sum(0)
        np.testing.assert_array_equal(accumulator.global_acc.coverage,expected)
        maps = accumulator.spatial_metrics(valid[0,0].numpy())
        self.assertTrue(np.isnan(maps["conditional_pinball"]).all())
        self.assertEqual(accumulator.global_acc.n_rain,2) # display rule changes no counts
        cases = sorted(accumulator.heaps["HIGHEST_TRUE_RAIN_RATE"], key=lambda e:e[:3], reverse=True)
        self.assertEqual(cases[0][-1]["IMERG_rate_mm_h"],20)


if __name__ == "__main__":
    unittest.main()
