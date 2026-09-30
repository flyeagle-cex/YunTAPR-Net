"""Repository-self-contained checks for the researcher-approved v1 freeze.

No raw science files, GADM geometry, data splits, or training are used here.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unittest
from collections import Counter
from pathlib import Path

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config" / "science_contract_v1.yaml"
DOC = ROOT / "docs" / "scientific_freeze" / "YUNTAPR_SCIENTIFIC_FREEZE_v1.md"
SPATIAL = ROOT / "config" / "spatial"
MANIFEST = SPATIAL / "sp04_coordinate_manifest_v1.json"
AXES = SPATIAL / "sp04_coordinate_axes_v1.csv"
MAPPING = SPATIAL / "sp04_target_cell_membership_v1.csv"
OLD_FREEZE = ROOT / "stage0-b0-evidence" / "evidence" / "outputs" / "stage0_spatial_decision_update" / "run_20260928T102636_513428Z" / "freeze_registry.json"
OLD_MAP = ROOT / "stage0-b0-evidence" / "evidence" / "outputs" / "b0_spatial_probability_contract_resolution" / "run_20260928T144303_935304Z" / "SPATIAL" / "target_cell_native_mapping.csv"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def axes_from_bits(path: Path) -> dict[str, np.ndarray]:
    fields: dict[str, list[tuple[int, np.float32]]] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            bit_value = int(row["float32_bits"], 16)
            value = np.asarray([bit_value], dtype=np.uint32).view(np.float32)[0]
            assert float(value) == float(row["decimal_value"])
            fields.setdefault(row["axis"], []).append((int(row["index"]), value))
    result = {}
    for name, values in fields.items():
        assert [i for i, _ in values] == list(range(len(values)))
        result[name] = np.asarray([v for _, v in values], dtype=np.float32)
    return result


def approved_edges(target: np.ndarray) -> np.ndarray:
    values = target.astype(np.float64)
    edges = np.empty(len(values) + 1, dtype=np.float64)
    edges[1:-1] = (values[:-1] + values[1:]) / 2
    edges[0] = values[0] - (values[1] - values[0]) / 2
    edges[-1] = values[-1] + (values[-1] - values[-2]) / 2
    return edges.astype(np.float32)


def approved_membership(source: np.ndarray, target: np.ndarray) -> list[list[int]]:
    edges = approved_edges(target)
    return [np.flatnonzero((source >= lower) & (source < upper)).astype(int).tolist()
            for lower, upper in zip(edges[:-1], edges[1:])]


class ScientificFreezeV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.axes = axes_from_bits(AXES)
        with MAPPING.open(encoding="utf-8", newline="") as stream:
            cls.mapping = list(csv.DictReader(stream))

    def test_01_contract_version_and_authority(self):
        self.assertEqual(self.cfg["contract_id"], "YUNTAPR_SCIENTIFIC_FREEZE_v1")
        self.assertEqual(self.cfg["authority"], "RESEARCHER_EXPLICIT_APPROVAL_2026-09-30")

    def test_02_old_candidate_precedence_is_scoped(self):
        self.assertEqual(self.cfg["precedence"]["scope"], "decisions_1_through_7_only")
        self.assertIn("historical evidence", self.cfg["precedence"]["rule"])
        self.assertIn("NOT_YET_FROZEN", (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_03_seven_decisions_in_status_table(self):
        rows = self.cfg["decision_status"]
        self.assertEqual([r["decision_id"] for r in rows], [f"D{i}" for i in range(1, 8)])
        self.assertTrue(all(set(("name", "status", "supersedes", "remaining_numeric_parameters", "evidence")) <= set(r) for r in rows))

    def test_04_document_covers_all_decisions(self):
        for i in range(1, 8):
            self.assertRegex(self.doc, rf"## D{i} —")
        self.assertIn("| decision_id | name | status | supersedes | remaining_numeric_parameters | evidence |", self.doc)

    def test_05_time_window_and_analysis_time(self):
        t = self.cfg["time"]
        self.assertEqual(t["precipitation_window"], "[T, T+30min)")
        self.assertEqual(t["analysis_time"], "T_plus_30_minutes")
        self.assertEqual(t["imerg_converted_cf_time_role"], "native_30_min_precipitation_window_start")

    def test_06_causal_frame_and_no_future(self):
        t = self.cfg["time"]
        self.assertEqual(t["causal_constraint"], "obs_end <= analysis_time")
        self.assertEqual(t["satellite_frame_selection"], "latest_completed_frame_with_obs_end_le_analysis_time")
        self.assertFalse(t["future_frames_allowed"])
        self.assertFalse(t["nominal_time_alone_proves_causality"])

    def test_07_date_created_not_operational_proof(self):
        self.assertEqual(self.cfg["time"]["date_created_role"], "record_only_not_historical_operational_availability")
        self.assertFalse(self.cfg["time"]["historical_operational_replay_proven"])

    def test_08_v07_final_only(self):
        r = self.cfg["temporal_data_role"]
        self.assertEqual(r["supervised_product"], "IMERG_V07_Final")
        self.assertFalse(r["mixed_v07_v08_supervision_allowed"])
        self.assertFalse(r["early_or_late_substitute_for_final_allowed"])

    def test_09_october_2025_inference_only(self):
        o = self.cfg["temporal_data_role"]["october_2025"]
        self.assertFalse(o["supervised_eligible"] or o["internal_test_eligible"])
        self.assertTrue(o["inference_eligible"] and o["retain_himawari_and_gfs"])

    def test_10_observation_window_and_subset(self):
        r = self.cfg["temporal_data_role"]
        self.assertEqual(r["observation_goal"]["years"], [2023, 2024, 2025])
        self.assertEqual(r["observation_goal"]["months"], list(range(3, 11)))
        self.assertTrue(r["supervised_times_subset_of_observation_times"])

    def test_11_axes_and_mapping_file_hashes(self):
        self.assertEqual(sha(AXES), self.manifest["axes_csv_sha256"])
        self.assertEqual(sha(MAPPING), self.manifest["mapping_csv_sha256"])
        self.assertEqual(sha(MAPPING), self.cfg["spatial"]["native_to_target"]["mapping_csv_sha256"])

    def test_12_axes_bit_exact_source_hashes(self):
        for name, values in self.axes.items():
            self.assertEqual(hashlib.sha256(values.tobytes()).hexdigest(), self.manifest["axis_raw_float32_bytes_sha256"][name])

    def test_13_real_axes_shape_and_direction(self):
        self.assertEqual({k: len(v) for k, v in self.axes.items()}, {"native_lat": 501, "native_lon": 501, "target_lat": 100, "target_lon": 100})
        self.assertTrue(np.all(np.diff(self.axes["native_lat"]) < 0))
        self.assertTrue(np.all(np.diff(self.axes["target_lat"]) > 0))
        self.assertTrue(np.all(np.diff(self.axes["native_lon"]) > 0))
        self.assertTrue(np.all(np.diff(self.axes["target_lon"]) > 0))

    def test_14_no_theoretical_axis_generation_in_builder(self):
        source = (ROOT / "tools" / "scientific_freeze" / "build_sp04_spatial_v1.py").read_text(encoding="utf-8")
        self.assertNotIn("np." + "arange(", source)
        self.assertNotIn("np.linspace(", source)
        self.assertFalse(self.cfg["spatial"]["theoretical_coordinate_reconstruction_allowed"])

    def test_15_mask_hash_and_3430_cells(self):
        old = json.loads(OLD_FREEZE.read_text(encoding="utf-8"))
        expected = old["artifacts"]["primary_mask"]["sha256"]
        self.assertEqual(expected, self.manifest["mask_hash_not_payload"])
        self.assertEqual(self.cfg["spatial"]["evaluation"]["true_cell_count"], 3430)

    def test_16_target_subset_indices(self):
        self.assertEqual(self.manifest["target_full_row_indices"], [10, 109])
        self.assertEqual(self.manifest["target_full_col_indices"], [20, 119])
        self.assertEqual(self.cfg["spatial"]["imerg_target"]["shape"], [100, 100])

    def test_17_mapping_has_all_unique_target_cells(self):
        self.assertEqual(len(self.mapping), 10000)
        self.assertEqual(len({(int(x["target_row"]), int(x["target_col"])) for x in self.mapping}), 10000)

    def test_18_mapping_recomputes_from_actual_bits(self):
        rows = approved_membership(self.axes["native_lat"], self.axes["target_lat"])
        cols = approved_membership(self.axes["native_lon"], self.axes["target_lon"])
        for record in self.mapping:
            y, x = int(record["target_row"]), int(record["target_col"])
            self.assertEqual(record["native_source_rows"], ";".join(map(str, rows[y])))
            self.assertEqual(record["native_source_cols"], ";".join(map(str, cols[x])))

    def test_19_all_cells_exactly_25(self):
        self.assertEqual({int(x["native_center_count"]) for x in self.mapping}, {25})
        self.assertEqual({len(x["native_source_rows"].split(";")) for x in self.mapping}, {5})
        self.assertEqual({len(x["native_source_cols"].split(";")) for x in self.mapping}, {5})

    def test_20_endpoint_membership_and_full_encoder_context(self):
        rows = {int(v) for x in self.mapping for v in x["native_source_rows"].split(";")}
        cols = {int(v) for x in self.mapping for v in x["native_source_cols"].split(";")}
        self.assertEqual(rows, set(range(1, 501)))
        self.assertEqual(cols, set(range(0, 500)))
        self.assertTrue(self.cfg["spatial"]["native_himawari"]["retain_all_centers_for_convolution_context"])

    def test_21_source_target_lat_not_silently_flipped(self):
        self.assertEqual(self.mapping[0]["native_source_rows"], "496;497;498;499;500")
        self.assertEqual(self.mapping[-1]["native_source_rows"], "1;2;3;4;5")
        self.assertFalse(self.cfg["spatial"]["native_to_target"]["silent_flip_or_transpose_allowed"])

    def test_22_mapping_agrees_with_prior_candidate_sha(self):
        self.assertEqual(sha(OLD_MAP), self.manifest["source_previous_candidate_mapping_sha256"])

    def test_23_mask_bounds_discrepancy_disclosed(self):
        expected = {"4": 11, "5": 78, "6": 11}
        self.assertEqual(self.manifest["mask_ancillary_bounds_membership_counts"]["latitude"], expected)
        self.assertEqual(self.manifest["mask_ancillary_bounds_membership_counts"]["longitude"], expected)
        self.assertIn("ancillary", self.doc)

    def test_24_no_physical_footprint_claim_or_implicit_pool(self):
        s = self.cfg["spatial"]["native_to_target"]
        self.assertFalse(s["physical_pixel_footprint_equivalence_claimed"])
        self.assertFalse(s["implicit_reshape_allowed"] or s["bare_adaptive_pooling_allowed"])

    def test_25_phase_a_and_b_split_disjoint_from_test(self):
        s = self.cfg["split"]
        a_train = {(2023, m) for m in s["phase_a_development"]["months"]}
        a_val = {(2024, m) for m in s["phase_a_development"]["months"]}
        b_fit = {(y, m) for y in s["phase_b_final_fit"]["years"] for m in s["phase_b_final_fit"]["months"]}
        test = {(2025, m) for m in s["internal_final_test"]["months"]}
        self.assertEqual(a_train | a_val, b_fit)
        self.assertFalse(b_fit & test)
        self.assertEqual(s["internal_final_test"]["months"], list(range(3, 10)))

    def test_26_no_2025_tuning_or_random_neighbor_split(self):
        s = self.cfg["split"]
        self.assertFalse(s["internal_final_test"]["may_tune_architecture_loss_normalization_epoch_checkpoint_threshold"])
        self.assertFalse(s["adjacent_30_min_random_split_allowed"])

    def test_27_zero_valid_missing_distinct(self):
        q = self.cfg["missing_qc"]
        self.assertTrue(q["imerg_zero_is_valid_no_rain"])
        self.assertFalse(q["imerg_missing_is_zero"])
        self.assertEqual(set(q["distinct_invalid_types"]), {"NaN", "masked", "declared_fill", "declared_missing"})

    def test_28_required_missing_and_all_fill_reject(self):
        q = self.cfg["missing_qc"]
        self.assertEqual(q["required_himawari_frame_missing"], "reject_sample")
        self.assertEqual(q["b13_all_fill"], "reject_sample")

    def test_29_partial_support_uses_25_without_2025(self):
        q = self.cfg["missing_qc"]
        self.assertEqual(q["target_cell_support_fraction"], "N_valid_native_centers_divided_by_25")
        self.assertEqual(q["partial_and_support_thresholds"]["status"], "DEVELOPMENT_ESTIMATED_PARAMETER")
        self.assertIsNone(q["partial_and_support_thresholds"]["numeric_value"])
        self.assertEqual(q["partial_and_support_thresholds"]["forbidden_data_year"], 2025)

    def test_30_loss_denominator_valid_yunnan_pixels(self):
        q = self.cfg["missing_qc"]
        self.assertEqual(q["loss_denominator"], "count_valid_supervised_pixels_in_yunnan_mask")
        self.assertEqual(q["imerg_invalid_target_pixel"], "exclude_from_loss_and_metric_denominator")

    def test_31_occurrence_and_conditional_threshold_match(self):
        p = self.cfg["probability"]
        self.assertEqual(p["occurrence"]["threshold"], 0.1)
        self.assertEqual(p["occurrence"]["comparison"], "strictly_greater_than")
        self.assertEqual(p["conditional"]["definition"], "R_given_R_greater_than_0.1")

    def test_32_exact_midpoint_taus(self):
        p = self.cfg["probability"]["conditional"]
        taus = [(i - .5) / 32 for i in range(1, 33)]
        self.assertEqual((len(taus), taus[0], taus[-1]), (32, p["taus_min"], p["taus_max"]))
        self.assertTrue(all(a < b for a, b in zip(taus, taus[1:])))

    def test_33_monotonic_support_synthetic(self):
        threshold = np.log1p(.1)
        raw_base = -2.0
        increments = [-1.0, 0.0, 4.0]
        q = [threshold + np.logaddexp(0, raw_base)]
        q.extend(q[-1] + np.cumsum([np.logaddexp(0, x) for x in increments]))
        self.assertTrue(all(x > threshold for x in q))
        self.assertTrue(all(a < b for a, b in zip(q, q[1:])))
        p = self.cfg["probability"]["conditional"]
        self.assertFalse(p["silent_clamp_allowed"] or p["posthoc_sort_allowed"])

    def test_34_focal_parameters_not_preset(self):
        loss = self.cfg["probability"]["loss"]
        for name in ("focal_alpha", "focal_gamma"):
            self.assertEqual(loss[name]["status"], "DEVELOPMENT_ESTIMATED_PARAMETER")
            self.assertIsNone(loss[name]["numeric_value"])

    def test_35_ext_disabled_kd_zero(self):
        loss = self.cfg["probability"]["loss"]
        self.assertEqual(loss["core"], "L_occ_plus_L_qr")
        self.assertEqual(loss["l_kd_b0_to_b8_core"], 0)
        self.assertFalse(loss["l_ext"]["enabled_in_v1_core"])

    def test_36_diagnostic_not_physical_mean(self):
        d = self.cfg["probability"]["deterministic_diagnostic"]
        self.assertFalse(d["exact_physical_mean"])
        self.assertFalse(d["includes_0_to_0_1_drizzle_component"])
        self.assertIn("expm1", d["formula"])

    def test_37_tail_not_silent_zero(self):
        e = self.cfg["probability"]["exceedance"]
        self.assertEqual(e["beyond_quantile_support"], "NOT_ESTABLISHED")
        self.assertFalse(e["silent_zero_tail_allowed"])

    def test_38_backbone_and_projection_shapes(self):
        b = self.cfg["backbone"]
        s = self.cfg["spatial"]["native_to_target"]
        self.assertEqual(b["channels"], [48, 96, 192, 256])
        self.assertEqual(b["final_native_feature"], s["native_feature_shape"])
        self.assertEqual(b["final_target_feature"], s["target_feature_shape"])
        self.assertIn("skip", b["decoder"])

    def test_39_groupnorm_not_scientific_number(self):
        g = self.cfg["backbone"]["groupnorm_groups"]
        self.assertEqual(g["status"], "ENGINEERING_CONFIG")
        self.assertIsNone(g["numeric_value"])

    def test_40_b0_forbidden_modules_and_b0_b3_fairness(self):
        b = self.cfg["backbone"]
        self.assertTrue({"GFS", "DEM", "ERA5_Teacher", "Attention", "Transformer"} <= set(b["b0_forbidden_inputs_modules"]))
        self.assertEqual(b["b0_to_b3_difference"], "himawari_input_information_only")

    def test_41_contract_frozen_training_false_next_skeleton(self):
        e = self.cfg["execution_status"]
        self.assertEqual(e["B0_FORMAL_SCIENTIFIC_CONTRACT"], "FROZEN")
        self.assertFalse(e["B0_FORMAL_TRAINING_STARTED"])
        self.assertEqual(e["next_phase"], "FORMAL_B0_SKELETON_IMPLEMENTATION")

    def test_42_public_config_has_no_restricted_payload(self):
        self.assertFalse(list(SPATIAL.glob("*.nc")) or list(SPATIAL.glob("*.geojson")) or list(SPATIAL.glob("*.npz")))
        self.assertFalse(self.cfg["spatial"]["evaluation"]["mask_payload_in_public_repo"])


if __name__ == "__main__":
    unittest.main()
