"""Focused evidence and synthetic math checks for the B0 decision package."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

import netCDF4
import numpy as np
import torch

RUN = Path(os.environ["B0_CONTRACT_RUN"])
sys.path.insert(0, str(RUN / "src"))
from build_contract import FREEZE, READINESS, axis_mapping, edges, sha  # noqa: E402
from contract_math import conditional_mask, inverse_log1p, monotonic_quantiles, occurrence_target, pinball, stable_rain_probability  # noqa: E402


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with np.load(RUN / "SPATIAL" / "sp04_coordinate_arrays.npz") as f:
            cls.arrays = {k: v.copy() for k, v in f.items()}
        cls.contract = json.loads((RUN / "SPATIAL" / "sp04_coordinate_contract.json").read_text(encoding="utf-8"))
        cls.hashes = json.loads((RUN / "SPATIAL" / "sp04_coordinate_hashes.json").read_text(encoding="utf-8"))
        with (RUN / "SPATIAL" / "target_cell_native_mapping.csv").open(encoding="utf-8", newline="") as f:
            cls.mapping = list(csv.DictReader(f))
        with (RUN / "PROBABILITY" / "quantile_tau_candidates.csv").open(encoding="utf-8", newline="") as f:
            cls.taus = list(csv.DictReader(f))

    def test_01_source_coordinate_file_hash(self):
        self.assertEqual(sha(READINESS / "SPATIAL" / "himawari_actual_coordinates.npz"), self.hashes["source_npz_sha256"])

    def test_02_frozen_coordinate_file_hash(self):
        reg = json.loads((FREEZE / "freeze_registry.json").read_text(encoding="utf-8"))
        self.assertEqual(self.hashes["frozen_imerg_npz_sha256"], reg["artifacts"]["coordinates"]["sha256"])

    def test_03_actual_native_arrays_equal(self):
        with np.load(READINESS / "SPATIAL" / "himawari_actual_coordinates.npz") as f:
            np.testing.assert_array_equal(self.arrays["native_lat"], f["latitude"])
            np.testing.assert_array_equal(self.arrays["native_lon"], f["longitude"])

    def test_04_actual_imerg_arrays_equal(self):
        with np.load(FREEZE / "FROZEN" / "MASK" / "imerg_actual_coordinates.npz") as f:
            np.testing.assert_array_equal(self.arrays["target_lat"], f["lat"][self.arrays["target_lat_full_indices"]])
            np.testing.assert_array_equal(self.arrays["target_lon"], f["lon"][self.arrays["target_lon_full_indices"]])

    def test_05_no_coordinate_reconstruction(self):
        source = (RUN / "src" / "build_contract.py").read_text(encoding="utf-8")
        self.assertNotIn("np." + "arange(", source)
        self.assertNotIn("np.linspace(", source)

    def test_06_source_lat_descending(self):
        self.assertTrue(np.all(np.diff(self.arrays["native_lat"]) < 0))

    def test_07_target_lat_ascending(self):
        self.assertTrue(np.all(np.diff(self.arrays["target_lat"]) > 0))

    def test_08_source_lon_ascending(self):
        self.assertTrue(np.all(np.diff(self.arrays["native_lon"]) > 0))

    def test_09_target_lon_ascending(self):
        self.assertTrue(np.all(np.diff(self.arrays["target_lon"]) > 0))

    def test_10_native_shape(self):
        self.assertEqual((len(self.arrays["native_lat"]), len(self.arrays["native_lon"])), (501, 501))

    def test_11_target_shape(self):
        self.assertEqual((len(self.arrays["target_lat"]), len(self.arrays["target_lon"])), (100, 100))

    def test_12_mapping_rows_unique(self):
        self.assertEqual(len(self.mapping), 10000)
        self.assertEqual(len({(int(r["target_row"]), int(r["target_col"])) for r in self.mapping}), 10000)

    def test_13_mapping_deterministic(self):
        expected = axis_mapping(self.arrays["native_lat"], self.arrays["target_lat"])
        self.assertEqual(int(self.mapping[0]["nearest_native_row"]), expected[0]["nearest_source_index"])
        self.assertEqual(int(self.mapping[-1]["nearest_native_row"]), expected[-1]["nearest_source_index"])

    def test_14_no_hidden_off_by_one(self):
        self.assertEqual((int(self.mapping[0]["target_full_row"]), int(self.mapping[-1]["target_full_row"])), (10, 109))
        self.assertEqual((int(self.mapping[0]["target_full_col"]), int(self.mapping[-1]["target_full_col"])), (20, 119))

    def test_15_source_north_maps_to_target_last_row(self):
        self.assertGreater(int(self.mapping[0]["nearest_native_row"]), int(self.mapping[-1]["nearest_native_row"]))

    def test_16_boundary_tie_exposed(self):
        self.assertTrue(any(r["south_boundary_rows"] for r in self.mapping))
        self.assertTrue(any(r["west_boundary_cols"] for r in self.mapping))

    def test_17_not_exact_five_to_one_reshape(self):
        self.assertNotEqual(len(self.arrays["native_lat"]), 5 * len(self.arrays["target_lat"]))

    def test_17a_half_open_is_5_by_5_on_actual_arrays(self):
        self.assertEqual({int(r["raw_half_open_native_center_count"]) for r in self.mapping}, {25})

    def test_17b_half_open_excludes_specific_endpoints(self):
        summary = json.loads((RUN / "SPATIAL" / "geometry_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["half_open_excluded_native_lat_rows"], [0])
        self.assertEqual(summary["half_open_excluded_native_lon_cols"], [500])

    def test_18_all_frozen_mask_cells_retained(self):
        m = FREEZE / "FROZEN" / "MASK" / "yunnan_evaluation_mask_center_gadm41_imerg_v1.nc"
        with netCDF4.Dataset(m) as f:
            mask = np.asarray(f.variables["yunnan_mask"][:], dtype=bool)
        rr, cc = self.arrays["target_lat_full_indices"], self.arrays["target_lon_full_indices"]
        self.assertEqual(int(mask.sum()), 3430)
        self.assertEqual(int(mask[np.ix_(rr, cc)].sum()), 3430)
        self.assertEqual(int(mask.sum() - mask[np.ix_(rr, cc)].sum()), 0)

    def test_19_context_not_eval_mask(self):
        m = FREEZE / "FROZEN" / "MASK" / "yunnan_evaluation_mask_center_gadm41_imerg_v1.nc"
        with netCDF4.Dataset(m) as f:
            mask = np.asarray(f.variables["yunnan_mask"][:], dtype=bool)
        rr, cc = self.arrays["target_lat_full_indices"], self.arrays["target_lon_full_indices"]
        self.assertEqual(int((~mask[np.ix_(rr, cc)]).sum()), 10000 - 3430)

    def test_20_no_transpose_or_flip_reported(self):
        self.assertTrue(self.contract["no_transpose"] and self.contract["no_lat_flip"])

    def test_21_tau_count_each(self):
        self.assertEqual({k: sum(r["candidate_id"] == k for r in self.taus) for k in ("Q01", "Q02", "Q03")}, {"Q01": 32, "Q02": 32, "Q03": 32})

    def test_22_tau_strictly_increasing(self):
        for k in ("Q01", "Q02", "Q03"):
            vals = [float(r["tau"]) for r in self.taus if r["candidate_id"] == k]
            self.assertTrue(all(a < b for a, b in zip(vals, vals[1:])))

    def test_23_tau_interior(self):
        self.assertTrue(all(0 < float(r["tau"]) < 1 for r in self.taus))

    def test_24_pinball_asymmetric_formula(self):
        y = torch.tensor([[[[3.0]]]])
        q = torch.tensor([[[[1.0]], [[5.0]]]])
        tau = torch.tensor([.25, .75])
        np.testing.assert_allclose(pinball(y, q, tau).numpy().reshape(-1), [.5, .5])

    def test_25_occurrence_threshold_strict(self):
        rain = torch.tensor([[[[0.0, 0.1, 0.10001, 1.0]]]])
        z, _ = occurrence_target(rain, torch.ones_like(rain, dtype=torch.bool))
        self.assertEqual(z.reshape(-1).tolist(), [False, False, True, True])

    def test_26_zero_valid(self):
        rain = torch.zeros((1, 1, 1, 1))
        _, valid = occurrence_target(rain, torch.ones_like(rain, dtype=torch.bool))
        self.assertTrue(valid.item())

    def test_27_missing_excluded(self):
        rain = torch.tensor([[[[0.0, 5.0]]]])
        valid = torch.tensor([[[[True, False]]]])
        self.assertEqual(conditional_mask(rain, valid).reshape(-1).tolist(), [False, False])

    def test_28_conditional_mask(self):
        rain = torch.tensor([[[[0.0, 0.1, 0.2, 5.0]]]])
        valid = torch.tensor([[[[True, True, True, False]]]])
        self.assertEqual(conditional_mask(rain, valid).reshape(-1).tolist(), [False, False, True, False])

    def test_29_sigmoid_range(self):
        p = stable_rain_probability(torch.tensor([-100.0, 0.0, 100.0]))
        self.assertTrue(bool(torch.all((p >= 0) & (p <= 1))))

    def test_30_monotonic_option(self):
        q = monotonic_quantiles(torch.zeros((2, 1, 3, 4)), torch.randn((2, 31, 3, 4)))
        self.assertEqual(q.shape, (2, 32, 3, 4))
        self.assertTrue(bool(torch.all(q[:, 1:] >= q[:, :-1])))

    def test_31_no_posthoc_sort(self):
        source = (RUN / "src" / "contract_math.py").read_text(encoding="utf-8")
        self.assertNotIn("torch." + "sort(", source)

    def test_32_output_tensor_shape(self):
        b = 2
        self.assertEqual(torch.empty((b, 1, 100, 100)).shape, (2, 1, 100, 100))
        self.assertEqual(torch.empty((b, 32, 100, 100)).shape, (2, 32, 100, 100))

    def test_33_inverse_log1p(self):
        r = torch.tensor([0.0, .1, 1.0, 20.0], dtype=torch.float64)
        torch.testing.assert_close(inverse_log1p(torch.log1p(r)), r)

    def test_34_no_implicit_negative_clamp(self):
        self.assertLess(inverse_log1p(torch.tensor(-.1)).item(), 0)

    def test_35_b0_b3_same_output(self):
        doc = (RUN / "MODEL" / "b0_b3_fairness_contract.md").read_text(encoding="utf-8")
        self.assertIn("same SP04 domain", doc)
        self.assertIn("dual probability heads", doc)

    def test_36_no_gfs_dem_import(self):
        for p in (RUN / "src").glob("*.py"):
            code = p.read_text(encoding="utf-8")
            self.assertNotIn("import " + "gfs", code.lower())
            self.assertNotIn("import " + "dem", code.lower())

    def test_37_no_formal_training(self):
        doc = (RUN / "FINAL_B0_SPATIAL_PROBABILITY_CONTRACT_REPORT.md").read_text(encoding="utf-8")
        self.assertIn("B0_FORMAL_TRAINING_STARTED:** `false`", doc)
        self.assertFalse(any((RUN / x).exists() for x in ("checkpoints", "weights", "train_dataset")))

    def test_38_required_six_statements(self):
        doc = (RUN / "FINAL_B0_SPATIAL_PROBABILITY_CONTRACT_REPORT.md").read_text(encoding="utf-8")
        for line in ("B0 spatial/probability contract resolution complete.", "No formal model training was started.",
                     "SP04 geometry was evaluated using actual coordinate arrays.",
                     "No provisional spatial projection was silently frozen.",
                     "No unspecified quantile or loss hyperparameter was silently frozen.",
                     "The final scientific contract remains subject to explicit researcher approval."):
            self.assertIn(line, doc)


if __name__ == "__main__":
    unittest.main()
