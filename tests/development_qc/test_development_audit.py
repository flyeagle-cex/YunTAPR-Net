"""Audit semantics: expected slots, explicit fallback and frozen-index support."""
from datetime import datetime, timedelta, timezone
import unittest
import numpy as np

from yuntapr.data.development_audit import (centikelvin_bins, classify_pair,
    expected_latest_slot, expected_month_slots, nominal_from_name, support_counts, zone_masks)
from scripts.finalize_development_qc import candidate_impact, histogram_statistics, pair_all, quantile_stress
from scripts.real_multisample_qc_smoke import select_examples


class DevelopmentAuditTests(unittest.TestCase):
    def test_ten_minute_month_schedule_and_name(self):
        slots = expected_month_slots(2024, 3)
        self.assertEqual(len(slots), 31 * 144)
        self.assertEqual(slots[0], datetime(2024, 3, 1, tzinfo=timezone.utc))
        self.assertEqual(slots[-1], datetime(2024, 3, 31, 23, 50, tzinfo=timezone.utc))
        from pathlib import Path
        self.assertEqual(nominal_from_name(Path("NC_H09_20240301_0020_R21_FLDK.06001_06001.nc")),
                         slots[2])
        self.assertEqual(expected_latest_slot(slots[3]), slots[2])

    def test_missing_expected_slot_is_never_silent(self):
        analysis = datetime(2023, 3, 1, 0, 30, tzinfo=timezone.utc)
        older = {"status": "READABLE", "obs_end": (analysis - timedelta(minutes=10)).isoformat()}
        self.assertEqual(classify_pair(None, older, analysis),
                         "EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS")
        self.assertEqual(classify_pair(None, None, analysis), "NO_CAUSAL_FRAME")
        expected = {"status": "READABLE", "valid_count": 10,
                    "obs_start": (analysis - timedelta(minutes=10)).isoformat(),
                    "obs_end": (analysis - timedelta(seconds=1)).isoformat()}
        self.assertEqual(classify_pair(expected, older, analysis), "EXPECTED_LATEST_SLOT_AVAILABLE")
        expected["obs_end"] = (analysis + timedelta(seconds=1)).isoformat()
        self.assertEqual(classify_pair(expected, older, analysis), "TIME_METADATA_ERROR")

    def test_support_and_disjoint_zones(self):
        valid = np.ones((501, 501), dtype=bool)
        valid[0, 0] = False
        indices = np.zeros((10000, 25), dtype=np.int64)
        indices[0, 0] = 1
        self.assertEqual(int(support_counts(valid, indices)[0]), 1)
        zones = zone_masks()
        self.assertEqual(sum(int(z[0, 0]) for z in zones.values()), 1)
        self.assertEqual(sum(int(z[250, 250]) for z in zones.values()), 1)
        self.assertEqual(sum(int(z.sum()) for z in zones.values()), 501 * 501)

    def test_centikelvin_bins(self):
        np.testing.assert_array_equal(centikelvin_bins(np.array([273.15, 290.01], dtype=np.float32)),
                                      np.array([27315, 29001]))

    def test_weighted_histogram_median_and_precision_stress(self):
        hist = np.zeros(65536, dtype=np.int64)
        hist[20000] = 2
        hist[30000] = 2
        stats = histogram_statistics(hist)
        self.assertEqual(stats["mean_K"], 250)
        self.assertEqual(stats["median_K"], 250)
        self.assertEqual(stats["std_K"], 50)
        stress = quantile_stress()
        self.assertTrue(stress["QUANTILE_NUMERICAL_STABILITY_DECISION_REQUIRED"])
        self.assertTrue(all(c["finite"] and c["gradient_finite"] for c in stress["cases"]))

    def test_pairing_records_older_causal_instead_of_silent_success(self):
        from pathlib import Path
        start = datetime(2023, 3, 1, tzinfo=timezone.utc)
        frames = [{"nominal": (start + timedelta(minutes=10)).isoformat(),
                   "relative_path": "older.nc", "status": "FULL_VALID",
                   "obs_start": (start + timedelta(minutes=10)).isoformat(),
                   "obs_end": (start + timedelta(minutes=19)).isoformat(),
                   "date_created": "", "valid_count": "251001"},
                  {"nominal": (start + timedelta(minutes=20)).isoformat(),
                   "relative_path": "", "status": "MISSING",
                   "obs_start": "", "obs_end": "", "date_created": "", "valid_count": ""}]
        target = [{"month": "202303", "window_start": start.isoformat(),
                   "analysis_time": (start + timedelta(minutes=30)).isoformat(),
                   "status": "VALID_TARGET_SLOT", "day_path": "imerg.nc", "index": "0",
                   "valid_yunnan_count": "3430", "zero_yunnan_count": "1",
                   "rain_yunnan_count": "2", "max_yunnan_mmhr": "3"}]
        pairs, diagnostics = pair_all(frames, target, Path("H:/fixture"))
        self.assertEqual(pairs[0]["pair_status"],
                         "EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS")
        self.assertEqual(pairs[0]["selected_b13_relative_path"], "older.nc")
        self.assertEqual(diagnostics["inverted_interval_frames"], 0)

    def test_smoke_selection_covers_both_years_and_partial(self):
        pairs = [{"month": "202303", "window_start": "2023-03-01T00:00:00+00:00",
                  "pair_status": "EXPECTED_LATEST_SLOT_AVAILABLE",
                  "selected_b13_relative_path": "dry.nc", "imerg_rain_yunnan_count": "0",
                  "imerg_zero_yunnan_count": "3430", "imerg_max_yunnan_mmhr": "0"},
                 {"month": "202403", "window_start": "2024-03-01T00:00:00+00:00",
                  "pair_status": "EXPECTED_LATEST_SLOT_AVAILABLE",
                  "selected_b13_relative_path": "rain.nc", "imerg_rain_yunnan_count": "20",
                  "imerg_zero_yunnan_count": "2", "imerg_max_yunnan_mmhr": "25"}]
        frames = [{"relative_path": "dry.nc", "status": "FULL_VALID"},
                  {"relative_path": "rain.nc", "status": "PARTIAL"}]
        selected, available, unavailable = select_examples(pairs, frames)
        self.assertEqual(len(selected), 2)
        self.assertIn("PARTIAL_B13", available)
        self.assertFalse(unavailable)

    def test_qc_impact_uses_paired_supervised_windows_only(self):
        frames = [{"relative_path": "exact.nc", "status": "PARTIAL", "valid_count": "251000",
                   "yunnan_25": "3429", "yunnan_24": "3430", "yunnan_23": "3430",
                   "yunnan_positive": "3430"},
                  {"relative_path": "unpaired.nc", "status": "FULL_VALID", "valid_count": "251001",
                   "yunnan_25": "3430", "yunnan_24": "3430", "yunnan_23": "3430",
                   "yunnan_positive": "3430"}]
        pairs = [{"month": "202303", "pair_status": "EXPECTED_LATEST_SLOT_AVAILABLE",
                  "selected_b13_relative_path": "exact.nc", "imerg_valid_yunnan_count": "3430",
                  "imerg_max_yunnan_mmhr": "0", "imerg_rain_yunnan_count": "0"},
                 {"month": "202303", "pair_status": "EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS",
                  "selected_b13_relative_path": "unpaired.nc", "imerg_valid_yunnan_count": "3430",
                  "imerg_max_yunnan_mmhr": "1", "imerg_rain_yunnan_count": "1"}]
        aggregate = [r for r in candidate_impact(frames, pairs) if r["month"] == "ALL_DEVELOPMENT"]
        by_name = {r["candidate"]: r for r in aggregate}
        self.assertEqual(by_name["A_SCENE_100_PERCENT"]["baseline_usable_scenes"], 1)
        self.assertEqual(by_name["A_SCENE_100_PERCENT"]["retained_yunnan_pixels"], 0)
        self.assertEqual(by_name["B_CELL_25_OF_25"]["retained_yunnan_pixels"], 3429)


if __name__ == "__main__":
    unittest.main()
