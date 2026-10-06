"""Stdlib synthetic tests; no model, backward, checkpoint or raw source reads."""
import csv
import importlib.util
import io
import math
from pathlib import Path
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/diagnose_saved_quantile_extremes_v1.py"
spec = importlib.util.spec_from_file_location("saved_extremes", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(update=1, qmin=0.0, maxima=None):
    values = maxima if maxima is not None else [float(i + 1) for i in range(32)]
    return {"update": update, "sample_ids": ["2023-fixture-a", "2024-fixture-b"],
            "qlog": {"min": qmin, "max": max(values)}, "qlog_per_tau_max": values}


def witness(values=None):
    return {"update": 2, "region": "YUNNAN_OUTSIDE",
            "qlog_values": values if values is not None else [float(i + 2) for i in range(32)]}


class SavedExtremesTests(unittest.TestCase):
    def test_witness_attains_global_bound_proves_region_max(self):
        self.assertEqual(module.maximum_from_witness(10., 10.)["value"], 10.)

    def test_global_max_cannot_be_assigned_to_unobserved_region(self):
        unknown = module.maximum_from_witness(10.)
        self.assertIsNone(unknown["value"])
        self.assertEqual(unknown["status"], module.UNKNOWN)
        self.assertEqual(unknown["upper_bound"], 10.)

    def test_witness_below_global_max_is_only_a_lower_bound(self):
        bound = module.maximum_from_witness(10., 7.)
        self.assertIsNone(bound["value"])
        self.assertEqual((bound["lower_bound"], bound["upper_bound"]), (7., 10.))

    def test_invalid_witness_rejected(self):
        with self.assertRaises(ValueError):
            module.maximum_from_witness(10., 11.)

    def test_linear_percentile_and_singleton(self):
        self.assertEqual(module.percentile([0., 10.], .99), 9.9)
        self.assertAlmostEqual(module.percentile([0., 10.], .999), 9.99)
        self.assertEqual(module.percentile([10.], .99), 10.)
        with self.assertRaises(ValueError):
            module.percentile([], .99)
        with self.assertRaises(ValueError):
            module.percentile([math.inf], .99)

    def test_region_pixel_percentiles_remain_unknown(self):
        result = module.describe_cohort([row(1), row(2, maxima=witness()["qlog_values"])], witness())
        outside = result["regions"]["YUNNAN_OUTSIDE"]
        self.assertEqual(outside["pooled_pixel_quantile_distribution"]["max"]["value"], 33.)
        self.assertIsNone(outside["pooled_pixel_quantile_distribution"]["p99"]["value"])
        self.assertIsNone(outside["per_forward_region_max_distribution"]["p99"]["value"])
        inside = result["regions"]["YUNNAN_INSIDE"]
        self.assertIsNone(inside["pooled_pixel_quantile_distribution"]["max"]["value"])

    def test_success_cohort_does_not_use_failure_witness(self):
        result = module.describe_cohort([row(1)], witness())
        self.assertIsNone(result["regions"]["YUNNAN_OUTSIDE"]["per_tau_qlog_max"][0]["value"])

    def test_single_forward_region_max_percentile_is_not_pixel_percentile(self):
        result = module.describe_cohort([row(2, maxima=witness()["qlog_values"])], witness())
        data = result["regions"]["YUNNAN_OUTSIDE"]
        self.assertEqual(data["per_forward_region_max_distribution"]["p99"]["value"], 33.)
        self.assertIsNone(data["pooled_pixel_quantile_distribution"]["p99"]["value"])

    def test_strict_threshold_equality_is_not_exceedance(self):
        threshold = math.log1p(10)
        counts = module.exceedance_bounds([row(maxima=[threshold] * 32)], "YUNNAN_INSIDE", 10)
        self.assertEqual(counts["pixel_tau_exposure_count"]["value"], 0)
        self.assertEqual(counts["spatial_pixel_exposure_count_any_tau"]["value"], 0)

    def test_one_outside_pixel_is_not_32_spatial_pixels(self):
        values = [9.] * 32
        known = witness(values)
        counts = module.exceedance_bounds([row(2, maxima=values)], "YUNNAN_OUTSIDE", 1000, known)
        self.assertIsNone(counts["pixel_tau_exposure_count"]["value"])
        self.assertEqual(counts["pixel_tau_exposure_count"]["lower_bound"], 32)
        self.assertEqual(counts["spatial_pixel_exposure_count_any_tau"]["lower_bound"], 1)
        self.assertEqual(counts["spatial_pixel_exposure_count_any_tau"]["upper_bound"], 2 * 6570)
        self.assertTrue(all(c["lower_bound"] == 1 for c in counts["per_tau_pixel_exposure_counts"]))

    def test_full_grid_min_proves_all_without_double_counting_witness(self):
        values = [9.] * 32
        counts = module.exceedance_bounds([row(2, qmin=8., maxima=values)], "YUNNAN_OUTSIDE", 1000, witness(values))
        self.assertEqual(counts["pixel_tau_exposure_count"]["value"], 2 * 6570 * 32)
        self.assertEqual(counts["spatial_pixel_exposure_count_any_tau"]["value"], 2 * 6570)

    def test_outside_witness_does_not_prove_inside_exceedances(self):
        values = [9.] * 32
        counts = module.exceedance_bounds([row(2, maxima=values)], "YUNNAN_INSIDE", 1000, witness(values))
        self.assertIsNone(counts["pixel_tau_exposure_count"]["value"])
        self.assertEqual(counts["pixel_tau_exposure_count"]["lower_bound"], 0)

    def test_csv_missing_is_blank_with_status_not_zero(self):
        result = {"cohorts": {"fixture": module.describe_cohort([row()])}}
        records = list(module.csv_rows(result))
        missing = next(r for r in records if r["region"] == "YUNNAN_INSIDE" and r["statistic"] == "p99")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(missing))
        writer.writeheader(); writer.writerow(missing)
        parsed = next(csv.DictReader(io.StringIO(output.getvalue())))
        self.assertEqual(parsed["value"], "")
        self.assertEqual(parsed["status"], module.UNKNOWN)

    def test_2025_identity_rejected_even_as_saved_metadata(self):
        r = row(41913)
        r.update(status="SUCCESS_EXACT_MATCH", scope="ENGINEERING_OVERFLOW_REPLAY_ONLY", actual_denominator=6860)
        r["sample_ids"] = ["2023-fixture", "2025-fixture"]
        with self.assertRaises(ValueError):
            module.validate_row(r, 0)

    def test_file_guard_denies_raw_and_checkpoint_and_old_artifact_writes(self):
        guard = module.SavedOnlyGuard([SCRIPT], [SCRIPT.parent / "new_fixture.json"])
        for path, flags in ((r"H:\raw.nc", 0), (r"F:\checkpoint.pt", 0), (SCRIPT, module.os.O_WRONLY)):
            with self.assertRaises(PermissionError):
                guard("open", (str(path), None, flags))
        guard("open", (str(SCRIPT), "r", 0))
        self.assertEqual(guard.events[0]["access"], "read")

    def test_stdlib_only_no_model_runtime_loaded(self):
        self.assertNotIn("torch", sys.modules)
        self.assertNotIn("netCDF4", sys.modules)


if __name__ == "__main__":
    unittest.main()
