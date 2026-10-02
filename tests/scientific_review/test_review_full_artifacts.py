"""Run only after a real full review; missing outputs fail, never become skips."""
import hashlib
import json
import os
from pathlib import Path
import unittest
import numpy as np
from netCDF4 import Dataset
from yuntapr.training.scientific_review import N_SCENES, N_VALID, N_RAIN, BEST_SHA, BEST_CORE, rows
from yuntapr.spatial.sp04_mapping import load_sp04


class FullReviewArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(os.environ["YUNTAPR_SCIENTIFIC_REVIEW_EVIDENCE"])
        cls.summary = json.loads((cls.out/"reinference_summary.json").read_text(encoding="utf-8"))

    def test_monthly_global_counts(self):
        data=rows(self.out/"monthly_metrics.csv")
        self.assertEqual(len(data),8)
        self.assertEqual(sum(int(r["scene_count"]) for r in data),N_SCENES)
        self.assertEqual(sum(int(r["N_valid"]) for r in data),N_VALID)
        self.assertEqual(sum(int(r["N_rain"]) for r in data),N_RAIN)

    def test_spatial_counts_and_coordinate_identity(self):
        mapping=load_sp04()
        with Dataset("scientific_review_spatial.nc", memory=(self.out/"spatial_cell_metrics.nc").read_bytes()) as nc:
            self.assertEqual(int(nc["valid_count"][:].sum()),N_VALID)
            self.assertEqual(int(nc["rainy_count"][:].sum()),N_RAIN)
            np.testing.assert_array_equal(nc["lat"][:],mapping.axes["target_lat"])
            np.testing.assert_array_equal(nc["lon"][:],mapping.axes["target_lon"])
            self.assertTrue(np.all(np.diff(nc["lat"][:])>0))
            self.assertEqual(nc["valid_count"].shape,(100,100))
            self.assertEqual(int(nc["yunnan_evaluation_mask"][:].sum()),3430)

    def test_rate_strata_reconcile(self):
        self.assertEqual(sum(int(r["pixel_count"]) for r in rows(self.out/"rainrate_stratified_metrics.csv")),N_RAIN)

    def test_probability_bins_reconcile(self):
        data=rows(self.out/"reliability_table.csv")
        self.assertEqual(sum(int(r["count"]) for r in data),N_VALID)
        self.assertEqual(sum(int(r["rainy_count"]) for r in data),N_RAIN)
        self.assertEqual(data[-1]["upper_inclusive"],"True")

    def test_quantile_coverage_exact_reproduction(self):
        self.assertTrue(self.summary["formal_reproduction"]["coverage_exact"])
        data=rows(self.out/"quantile_calibration.csv")
        self.assertEqual(len(data),32)
        for row,official in zip(data,self.summary["global"]["per_tau_conditional_coverage"]):
            self.assertEqual(float(row["conditional_coverage"]),official)
            self.assertEqual(int(row["coverage_count"])/N_RAIN,official)

    def test_official_best_core_reproduced(self):
        self.assertAlmostEqual(self.summary["global"]["global_val_core_loss"],BEST_CORE,places=12)
        self.assertTrue(all(v["pass"] for v in self.summary["formal_reproduction"].values() if isinstance(v,dict)))

    def test_best_file_exact_sha(self):
        manifest=json.loads((self.out/"review_manifest.json").read_text(encoding="utf-8"))
        path=Path(manifest["formal_best"]["absolute_local_path"])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),BEST_SHA)

    def test_no_optimizer_no_backward_no_parameter_updates(self):
        model=self.summary["runtime"]["model"]
        self.assertFalse(model["optimizer_created"])
        self.assertEqual(model["optimizer_steps"],0)
        self.assertEqual(model["backward_calls"],0)
        self.assertFalse(any(model["prohibited_attempts"].values()))
        self.assertEqual(model["model_state_sha256_before"],model["model_state_sha256_after"])

    def test_no_2025_access(self):
        self.assertEqual(self.summary["runtime"]["2025_PIXELS_READ"],0)
        self.assertEqual(self.summary["runtime"]["source_years_read"],[2024])
        ledger=Path(self.summary["runtime"]["read_ledger"]["absolute_local_path"])
        data=rows(ledger)
        self.assertEqual(len(data),N_SCENES)
        self.assertTrue(all(r["sample_id"].startswith("2024") for r in data))

    def test_numerical_counts_all_zero(self):
        self.assertFalse(any(self.summary["numeric_checks"].values()))

    def test_objective_cases_and_no_selection_change(self):
        data=rows(self.out/"case_diagnostics.csv")
        self.assertEqual(len(data),30)
        for name in set(r["rule"] for r in data):
            cases=[r for r in data if r["rule"]==name]
            self.assertEqual([int(r["rank"]) for r in cases],list(range(1,11)))
        self.assertTrue(json.loads((self.out/"review_manifest.json").read_text(encoding="utf-8"))["CHECKPOINT_SELECTION_REMAINS_EPOCH_11"])


if __name__=="__main__":
    unittest.main()
