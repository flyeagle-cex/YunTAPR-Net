"""Stdlib fixtures + saved-artifact checks. Never reads raw data/checkpoints."""
import argparse
import csv
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("saved_extremes", ROOT / "scripts/diagnose_saved_quantile_extremes_v1.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in args.run_id):
        raise ValueError("Invalid run identifier")
    run = ROOT / "docs/saved_quantile_extremes/runs" / args.run_id
    report = json.loads((run / m.OUTPUT_NAMES[0]).read_text(encoding="utf-8"))
    manifest = json.loads((run / m.OUTPUT_NAMES[2]).read_text(encoding="utf-8"))
    cohort = report["cohorts"]["SUCCESSFUL_UPDATES_PLUS_FAILING_FORWARD"]

    class ArtifactTests(unittest.TestCase):
        def test_input_and_generated_artifact_hashes(self):
            self.assertEqual(m.pin_inputs(), manifest["inputs_before"])
            self.assertEqual(manifest["inputs_before"], manifest["inputs_after"])
            self.assertEqual(m.digest(ROOT / report["provenance"]["generator_relative_path"]), report["provenance"]["generator_sha256"])
            for ref in manifest["artifacts"]:
                path = ROOT / ref["relative_path"]
                self.assertEqual(path.stat().st_size, ref["bytes"])
                self.assertEqual(m.digest(path), ref["sha256"])

        def test_cohort_counts_and_update_scope(self):
            self.assertEqual((cohort["n_forward_observations"], cohort["n_scene_exposures"]), (8626, 17252))
            self.assertEqual((cohort["first_update"], cohort["last_update"]), (41913, 50538))
            self.assertEqual(report["cohorts"]["SUCCESSFUL_UPDATES_ONLY"]["n_forward_observations"], 8625)
            self.assertEqual(report["cohorts"]["FAILING_FORWARD_ONLY"]["n_forward_observations"], 1)

        def test_outside_aggregate_max_proof_and_inside_unknown(self):
            self.assertFalse(report["witness"]["mask_membership"])
            self.assertTrue(all(r["exact_equality"] for r in report["outside_per_tau_max_proof"]))
            outside = cohort["regions"]["YUNNAN_OUTSIDE"]
            self.assertEqual(outside["pooled_pixel_quantile_distribution"]["max"]["value"], 721.2174966216189)
            self.assertEqual([r["value"] for r in outside["per_tau_qlog_max"]], report["witness"]["qlog_values"])
            self.assertTrue(all(r["value"] is None for r in cohort["regions"]["YUNNAN_INSIDE"]["per_tau_qlog_max"]))
            self.assertTrue(all(r["value"] is None for r in report["cohorts"]["SUCCESSFUL_UPDATES_ONLY"]["regions"]["YUNNAN_OUTSIDE"]["per_tau_qlog_max"]))

        def test_pixel_percentiles_not_replaced_by_maximum_percentiles(self):
            for item in report["cohorts"].values():
                for region in item["regions"].values():
                    for stat in ("p99", "p99_9"):
                        self.assertIsNone(region["pooled_pixel_quantile_distribution"][stat]["value"])
                        self.assertEqual(region["pooled_pixel_quantile_distribution"][stat]["status"], m.UNKNOWN)
            whole = cohort["whole_grid_maxima_supplement"]["per_forward_global_max_distribution"]
            self.assertEqual(whole["p99"], 532.9835015132659)
            self.assertEqual(whole["p99_9"], 637.9910460306833)
            self.assertIsNone(cohort["regions"]["YUNNAN_OUTSIDE"]["per_forward_region_max_distribution"]["p99"]["value"])

        def test_threshold_count_units_and_unknown_totals(self):
            for region_name, region in cohort["regions"].items():
                self.assertEqual([r["physical_threshold_mm_h"] for r in region["exceedance_counts"]], list(m.RATES))
                previous = None
                for threshold in region["exceedance_counts"]:
                    self.assertEqual(threshold["comparison"], "qlog > log1p(physical_threshold_mm_h)")
                    for name in ("pixel_tau_exposure_count", "spatial_pixel_exposure_count_any_tau"):
                        self.assertIsNone(threshold[name]["value"])
                    expected = 32 if region_name == "YUNNAN_OUTSIDE" else 0
                    self.assertEqual(threshold["pixel_tau_exposure_count"]["lower_bound"], expected)
                    self.assertEqual(threshold["spatial_pixel_exposure_count_any_tau"]["lower_bound"], int(expected > 0))
                    bounds = [v["upper_bound"] for v in threshold["per_tau_pixel_exposure_counts"]]
                    if previous is not None:
                        self.assertTrue(all(v <= prior for v, prior in zip(bounds, previous)))
                    previous = bounds

        def test_no_model_raw_checkpoint_or_2025_access(self):
            for key in ("FORWARD_CALLS", "BACKWARD_CALLS", "OPTIMIZER_STEPS", "RAW_SOURCE_OPENS", "2025_RAW_ACCESS", "CHECKPOINT_OPENS"):
                self.assertEqual(report["execution"][key], 0)
            self.assertFalse(report["execution"]["MODEL_PARAMETERS_UPDATED"])
            self.assertNotIn("torch", sys.modules)
            self.assertNotIn("netCDF4", sys.modules)
            allowed_inputs = {str((ROOT / p).resolve()) for p in m.INPUT_SHAS}
            allowed_inputs.add(str((ROOT / "scripts/diagnose_saved_quantile_extremes_v1.py").resolve()))
            allowed_outputs = {str((run / n).resolve()) for n in m.OUTPUT_NAMES}
            for event in manifest["read_write_events_before_manifest_write"]:
                self.assertIn(event["path"], allowed_outputs if event["access"] == "write" else allowed_inputs | allowed_outputs)

        def test_csv_matches_json_and_preserves_null_status(self):
            fields = ("cohort", "region", "aggregation", "statistic", "tau_ordinal", "tau", "physical_threshold_mm_h",
                      "log1p_threshold", "value", "status", "lower_bound", "upper_bound", "unit", "n_forward_observations", "reason")
            expected = [{c: "" if r.get(c) is None else str(r.get(c)) for c in fields} for r in m.csv_rows(report)]
            with (run / m.OUTPUT_NAMES[1]).open(encoding="utf-8", newline="") as handle:
                actual = list(csv.DictReader(handle))
            self.assertEqual(actual, expected)
            self.assertEqual(len(actual), 1545)
            self.assertTrue(all(r["value"] == "" for r in actual if r["status"] == m.UNKNOWN))

        def test_scope_stays_descriptive_and_incomplete(self):
            self.assertEqual(report["status"], "PARTIAL_RECOVERY_SAVED_OBSERVATIONS_ONLY")
            self.assertFalse(report["all_requested_regional_statistics_recoverable"])
            self.assertFalse(report["execution"]["numerical_or_training_rules_changed"])
            self.assertFalse(report["execution"]["historical_artifacts_modified"])
            self.assertIn("not exclusion criteria", report["definitions"]["threshold_purpose"])

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.discover(str(ROOT / "tests/saved_quantile_extremes"), pattern="test_*.py"))
    suite.addTests(loader.loadTestsFromTestCase(ArtifactTests))
    console = io.StringIO()
    result = unittest.TextTestRunner(stream=console, verbosity=2).run(suite)
    record = {"utc": datetime.now(timezone.utc).isoformat(), "scope": "STDLIB_SYNTHETIC_FIXTURES_AND_SAVED_ARTIFACTS_ONLY",
              "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              "run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
              "synthetic_unit_tests": 16, "saved_artifact_tests": 8, "successful": result.wasSuccessful(),
              "FORWARD_CALLS": 0, "BACKWARD_CALLS": 0, "OPTIMIZER_STEPS": 0, "2025_RAW_ACCESS": 0,
              "test_sources": [{"relative_path": p.relative_to(ROOT).as_posix(), "sha256": m.digest(p)} for p in
                               (Path(__file__).resolve(), ROOT / "tests/saved_quantile_extremes/test_extremes.py")],
              "console": console.getvalue()}
    m.write_json(run / "saved_observation_test_results.json", record)
    print(json.dumps({k: record[k] for k in ("passed", "run", "failures", "errors", "skipped", "successful")}))
    if not result.wasSuccessful():
        print(console.getvalue())
        raise SystemExit(1)


if __name__ == "__main__":
    main()
