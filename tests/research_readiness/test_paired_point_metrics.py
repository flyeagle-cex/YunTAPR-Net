"""CPU synthetic checks for fixed-population A/B/C physical point scores."""

import math
import unittest

import numpy as np

from tools.research_readiness.paired_point_metrics import (
    METHODS, TAU, THRESHOLDS_MM_H, PointMetricAccumulator, point_candidates_log,
)


def batch(n=4, *, rate=None, probability=None):
    y = np.array([0.0, 0.1, 5.0, 25.0] if rate is None else rate, dtype=np.float64)
    p = np.array([0.2, 0.5, 0.8, 1.0] if probability is None else probability, dtype=np.float64)
    q = np.log1p(np.linspace(0.2, 60.0, 32))[None, :, None, None]
    return {
        "rate": y.reshape(n, 1, 1, 1),
        "probability": p.reshape(n, 1, 1, 1),
        "valid": np.ones((n, 1, 1, 1), dtype=bool),
        "region": np.ones((n, 1, 1, 1), dtype=bool),
        "quantiles_log": np.broadcast_to(q, (n, 32, 1, 1)).copy(),
    }


class PointFormulaTests(unittest.TestCase):
    def test_inherited_abc_formulas_and_median_endpoints(self):
        p = np.array([0.0, 0.49, 0.5, 0.501, 0.8, 1.0])
        q = np.broadcast_to(np.log1p(np.linspace(0.2, 60.0, 32)), (len(p), 32)).copy()
        points = point_candidates_log(q, p)
        np.testing.assert_array_equal(points["A"], p * np.expm1(q).mean(axis=1))
        np.testing.assert_array_equal(points["C"], p * np.expm1(q.mean(axis=1)))
        reference = []
        for probability, quantiles in zip(p, q):
            if probability < 0.5:
                reference.append(0.0)
            else:
                u = (probability - 0.5) / probability
                reference.append(math.expm1(math.log1p(0.1) if u < TAU[0]
                                           else np.interp(u, TAU, quantiles)))
        np.testing.assert_allclose(points["B"], reference, rtol=1e-15, atol=1e-15)
        self.assertEqual(set(points), set(METHODS))

    def test_probability_and_order_validation(self):
        q = np.broadcast_to(np.linspace(0.2, 1.0, 32), (2, 32)).copy()
        for probability in ([np.nan, 0.5], [-0.1, 0.5], [1.1, 0.5]):
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                point_candidates_log(q, probability)
        q[0, 2] = q[0, 1]
        with self.assertRaises(ValueError):
            point_candidates_log(q, [0.5, 0.5])


class AccumulatorTests(unittest.TestCase):
    def make(self, *, ids=("s0", "s1", "s2", "s3"), n_valid=4, n_rain=2):
        return PointMetricAccumulator(ids, expected_n_valid=n_valid, expected_n_rain=n_rain)

    def test_all_metrics_match_direct_synthetic_counts_and_errors(self):
        values = batch()
        accumulator = self.make()
        accumulator.add(("s0", "s1", "s2", "s3"), **values)
        result = accumulator.finish()
        self.assertEqual((result["scenes"], result["n_valid"], result["n_rain"]), (4, 4, 2))
        y = values["rate"].reshape(-1)
        points = point_candidates_log(values["quantiles_log"].reshape(4, 32),
                                      values["probability"].reshape(-1))
        for method, prediction in points.items():
            continuous = result["methods"][method]["continuous"]
            self.assertAlmostEqual(continuous["MAE"], np.abs(prediction - y).mean())
            self.assertAlmostEqual(continuous["RMSE"], np.sqrt(np.square(prediction - y).mean()))
            self.assertAlmostEqual(continuous["MeanBias"], (prediction - y).mean())
            self.assertAlmostEqual(continuous["Pearson_CC"], np.corrcoef(y, prediction)[0, 1])
            for threshold, row in zip(THRESHOLDS_MM_H, result["methods"][method]["thresholds"]):
                truth = y.astype(np.float32) > np.float32(threshold)
                forecast = prediction.astype(np.float32) > np.float32(threshold)
                tp, fp, fn, tn = (int(mask.sum()) for mask in (
                    truth & forecast, ~truth & forecast, truth & ~forecast, ~truth & ~forecast))
                self.assertEqual([row[k] for k in ("TP", "FP", "FN", "TN")], [tp, fp, fn, tn])
                self.assertEqual(row["truth_equal"], int((y.astype(np.float32) == np.float32(threshold)).sum()))
                self.assertEqual(row["prediction_equal"], int((prediction.astype(np.float32) == np.float32(threshold)).sum()))
                divide = lambda a, b: a / b if b else None
                expected = {"POD": divide(tp, tp + fn), "FAR": divide(fp, tp + fp),
                            "CSI": divide(tp, tp + fp + fn), "Precision": divide(tp, tp + fp),
                            "F1": divide(2 * tp, 2 * tp + fp + fn),
                            "ETS": divide(tp * 4 - (tp + fp) * (tp + fn),
                                          (tp + fp + fn) * 4 - (tp + fp) * (tp + fn)),
                            "HSS": divide(2 * (tp * tn - fp * fn),
                                          (tp + fn) * (fn + tn) + (tp + fp) * (fp + tn)),
                            "frequency_bias": divide(tp + fp, tp + fn)}
                for metric, expected_value in expected.items():
                    self.assertEqual(row[metric], expected_value)

    def test_partitioning_does_not_change_population_or_scores(self):
        values = batch()
        full = self.make()
        full.add(("s0", "s1", "s2", "s3"), **values)
        split = self.make()
        for index in range(4):
            split.add((f"s{index}",), **{k: v[index:index + 1] for k, v in values.items()})
        a, b = full.finish(), split.finish()
        self.assertEqual(a["supervision_mask_sha256"], b["supervision_mask_sha256"])
        for method in METHODS:
            self.assertEqual(a["methods"][method]["thresholds"], b["methods"][method]["thresholds"])
            for metric in ("MAE", "RMSE", "MeanBias", "Pearson_CC"):
                self.assertAlmostEqual(a["methods"][method]["continuous"][metric],
                                       b["methods"][method]["continuous"][metric], places=12)

    def test_fp32_classification_boundary_preserves_fp64_continuous_error(self):
        values = batch(n=1, rate=[0.1], probability=[0.5])
        accumulator = self.make(ids=("s0",), n_valid=1, n_rain=0)
        accumulator.add(("s0",), **values)
        result = accumulator.finish()
        row = result["methods"]["B"]["thresholds"][0]
        self.assertEqual((row["TP"], row["FP"], row["FN"], row["TN"]), (0, 0, 0, 1))
        self.assertEqual((row["truth_equal"], row["prediction_equal"]), (1, 1))
        self.assertIsNone(row["FAR"])
        self.assertIsNone(result["methods"]["B"]["continuous"]["Pearson_CC"])

    def test_selected_mask_and_empty_scene(self):
        values = batch()
        values["valid"][0] = False
        values["region"][1] = False
        values["rate"][0] = np.nan
        accumulator = self.make(n_valid=2)
        accumulator.add(("s0", "s1", "s2", "s3"), **values)
        self.assertEqual(accumulator.finish()["n_valid"], 2)

    def test_fp64_above_threshold_collapses_to_fp32_equality(self):
        values = batch(n=1, rate=[6.0], probability=[1.0])
        center = math.log1p(5.0 + 1e-8)
        values["quantiles_log"][:] = np.linspace(center - 0.1, center + 0.1, 32)[None, :, None, None]
        prediction = point_candidates_log(values["quantiles_log"].reshape(1, 32), [1.0])["B"][0]
        self.assertGreater(prediction, 5.0)
        self.assertEqual(np.float32(prediction), np.float32(5.0))
        accumulator = self.make(ids=("s0",), n_valid=1, n_rain=1)
        accumulator.add(("s0",), **values)
        result = accumulator.finish()["methods"]["B"]
        row = next(row for row in result["thresholds"] if row["threshold_mm_h"] == 5.0)
        self.assertEqual((row["TP"], row["FN"], row["prediction_equal"]), (0, 1, 1))
        self.assertEqual(result["continuous"]["MeanBias"], prediction - 6.0)

    def test_constant_reference_or_prediction_has_undefined_correlation(self):
        for rate, probability in (([1.0] * 3, [0.2, 0.5, 0.8]),
                                  ([1.0, 2.0, 3.0], [0.0] * 3)):
            with self.subTest(rate=rate, probability=probability):
                accumulator = self.make(ids=("s0", "s1", "s2"), n_valid=3, n_rain=3)
                accumulator.add(("s0", "s1", "s2"), **batch(n=3, rate=rate, probability=probability))
                for result in accumulator.finish()["methods"].values():
                    self.assertIsNone(result["continuous"]["Pearson_CC"])

    def test_duplicate_or_wrong_scene_order_poison(self):
        accumulator = self.make()
        with self.assertRaises(ValueError):
            accumulator.add(("s1", "s0", "s2", "s3"), **batch())
        self.assertTrue(accumulator.poisoned)
        with self.assertRaises(RuntimeError):
            accumulator.add(("s0", "s1", "s2", "s3"), **batch())

    def test_incomplete_finish_poison(self):
        accumulator = self.make()
        with self.assertRaises(ValueError):
            accumulator.finish()
        with self.assertRaises(RuntimeError):
            accumulator.finish()

    def test_finish_once_and_add_after_finish_refused(self):
        accumulator = self.make()
        accumulator.add(("s0", "s1", "s2", "s3"), **batch())
        accumulator.finish()
        with self.assertRaises(RuntimeError):
            accumulator.finish()
        with self.assertRaises(RuntimeError):
            accumulator.add(("s0",), **batch(n=1, rate=[0.0], probability=[0.0]))

    def test_population_mismatch_poison(self):
        for n_valid, n_rain in ((3, 2), (4, 1), (5, 2), (4, 3)):
            with self.subTest(n_valid=n_valid, n_rain=n_rain):
                accumulator = self.make(n_valid=n_valid, n_rain=n_rain)
                with self.assertRaises(ValueError):
                    accumulator.add(("s0", "s1", "s2", "s3"), **batch())
                    accumulator.finish()
                self.assertTrue(accumulator.poisoned)

    def test_invalid_numeric_values_poison(self):
        invalid = [("rate", -1.0), ("rate", np.nan), ("probability", -0.1),
                   ("probability", 1.1), ("probability", np.nan), ("quantiles_log", np.inf)]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                values = batch()
                values[field].flat[0] = value
                accumulator = self.make()
                with self.assertRaises(ValueError):
                    accumulator.add(("s0", "s1", "s2", "s3"), **values)
                self.assertTrue(accumulator.poisoned)

    def test_nonmonotone_quantiles_poison(self):
        values = batch()
        values["quantiles_log"][:, 1] = values["quantiles_log"][:, 0]
        accumulator = self.make()
        with self.assertRaises(ValueError):
            accumulator.add(("s0", "s1", "s2", "s3"), **values)
        self.assertTrue(accumulator.poisoned)

    def test_shape_dtype_and_region_broadcast_rejected(self):
        for field, replacement in (("valid", np.ones((4, 1, 1, 1), dtype=np.int8)),
                                   ("region", np.ones((1, 1, 1, 1), dtype=bool)),
                                   ("rate", np.zeros((4, 1, 1, 1), dtype=np.int64)),
                                   ("probability", np.zeros((4, 1, 1))),
                                   ("quantiles_log", np.ones((4, 31, 1, 1)))):
            with self.subTest(field=field):
                values = batch()
                values[field] = replacement
                accumulator = self.make()
                with self.assertRaises(ValueError):
                    accumulator.add(("s0", "s1", "s2", "s3"), **values)
                self.assertTrue(accumulator.poisoned)

    def test_fp32_overflow_poison(self):
        values = batch()
        values["quantiles_log"][:] = np.linspace(100.0, 101.0, 32)[None, :, None, None]
        accumulator = self.make()
        with self.assertRaises((ValueError, FloatingPointError)):
            accumulator.add(("s0", "s1", "s2", "s3"), **values)
        self.assertTrue(accumulator.poisoned)

    def test_constructor_counts_and_duplicate_ids(self):
        for args in ((["s0", "s0"], 1, 0), (["s0"], True, 0),
                     (["s0"], 1, 2), ([], 1, 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                PointMetricAccumulator(args[0], expected_n_valid=args[1], expected_n_rain=args[2])


if __name__ == "__main__":
    unittest.main()
