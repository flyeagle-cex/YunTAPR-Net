"""Unit tests for the torch-free bounded candidate manifest collector."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from tools.research_readiness import stage45_candidate_manifest as manifest
from tools.research_readiness.a20_fixed_endpoint_bounds import (
    pinball,
    strict_hit,
    weak_preserving_vertex,
)


SID = "2023-03-01T05:30:00Z"


def scene():
    p = np.zeros((100, 100), dtype=np.float64)
    baseline = np.log1p(np.linspace(0.1, 5.0, 32))
    qlog = np.broadcast_to(baseline[:, None, None], (32, 100, 100)).copy()
    truth = np.full((100, 100), 5.0, dtype=np.float32)
    valid = np.ones((100, 100), dtype=bool)
    region = np.zeros((100, 100), dtype=bool)
    region.ravel()[:manifest.SUPERVISION_PIXELS_PER_SCENE] = True
    return p, qlog, truth, valid, region


def set_pixel(p, qlog, truth, row, column, probability, maximum, truth_rate):
    p[row, column] = probability
    qlog[:, row, column] = np.log1p(np.linspace(0.1, maximum, 32))
    truth[row, column] = np.float32(truth_rate)


class CandidateManifestTests(unittest.TestCase):
    def test_candidate_rule_is_strict(self):
        p, qlog, truth, valid, region = scene()
        set_pixel(p, qlog, truth, 0, 1, 1.0, 20.0, 5.0)   # p*q32 == 20
        set_pixel(p, qlog, truth, 0, 2, 0.4, 50.0, 5.0)   # p*q32 == 20
        set_pixel(p, qlog, truth, 0, 3, 0.5, 30.0, 5.0)   # p*q32 == 15
        collector = manifest.CandidateManifest()
        collector.update(p, qlog, truth, valid, region, SID)
        self.assertEqual(collector.rows, [])
        with tempfile.TemporaryDirectory() as tmp:
            stats = collector.finish(Path(tmp))
            with np.load(Path(tmp) / manifest.OUTPUT_NAME) as arrays:
                self.assertEqual(arrays["scene_id"].shape, (0,))
                self.assertEqual(arrays["nodes_log"].shape, (0, manifest.NODES))
                self.assertEqual(arrays["delta"].dtype, np.float64)
                self.assertEqual(arrays["reachable"].dtype, np.bool_)
        self.assertEqual(stats["evaluated_scenes"], 1)
        self.assertEqual(stats["evaluated_supervised_pixels"], manifest.SUPERVISION_PIXELS_PER_SCENE)
        self.assertEqual(stats["evaluated_strong_pixels"], 0)
        self.assertEqual(stats["candidate_rows"], 0)
        self.assertTrue(stats["retained_rows_bounded"])

    def test_reachable_candidate_records_strict_crossing_and_negative_delta(self):
        p, qlog, truth, valid, region = scene()
        set_pixel(p, qlog, truth, 0, 0, 1.0, 30.0, 50.0)
        collector = manifest.CandidateManifest()
        collector.update(p, qlog, truth, valid, region, SID)
        self.assertEqual(len(collector.rows), 1)
        row = collector.rows[0]
        nodes = np.expm1(qlog[:, 0, 0])
        self.assertEqual((row.scene_id, row.row), (SID, 0))
        self.assertEqual(row.q32, 30.0)
        self.assertEqual(row.a0, float(np.float32(nodes.mean())))
        self.assertEqual(row.mean_intensity, float(nodes.mean()))
        self.assertTrue(row.strong)
        self.assertTrue(row.all_nodes_below_truth)
        self.assertTrue(row.reachable)
        self.assertFalse(row.already_crossed)
        self.assertGreater(row.a_after, 20.0)
        self.assertLess(row.delta, 0.0)

        vertex = weak_preserving_vertex(qlog[:, 0, 0])
        matched = strict_hit(1.0, qlog[:, 0, 0], vertex)
        expected = (
            pinball((50.0 - np.expm1(matched)) / 20.0)
            - pinball((50.0 - nodes) / 20.0)
        )
        self.assertAlmostEqual(row.delta, float(expected), places=12)

        with tempfile.TemporaryDirectory() as tmp:
            stats = collector.finish(Path(tmp))
            with np.load(Path(tmp) / manifest.OUTPUT_NAME) as stored:
                arrays = {name: stored[name] for name in stored.files}
        self.assertEqual(stats["candidate_rows"], 1)
        self.assertEqual(stats["reachable_rows"], 1)
        self.assertEqual(stats["improving_rows"], 1)
        self.assertEqual(stats["all_nodes_below_truth_rows"], 1)
        self.assertEqual(stats["all_nodes_below_truth_strong_rows"], 1)
        self.assertEqual(int(arrays["row"][0]), 0)
        self.assertEqual(str(arrays["scene_id"][0]), SID)
        self.assertEqual(int(arrays["reachable"][0]), 1)
        np.testing.assert_array_equal(arrays["nodes_log"][0], qlog[:, 0, 0])

    def test_unreachable_vertex_records_ceiling_and_nan_delta(self):
        p, qlog, truth, valid, region = scene()
        set_pixel(p, qlog, truth, 0, 0, 1.0, 25.0, 5.0)
        collector = manifest.CandidateManifest()
        collector.update(p, qlog, truth, valid, region, SID)
        row = collector.rows[0]
        self.assertFalse(row.reachable)
        self.assertFalse(row.already_crossed)
        self.assertLess(row.a_after, 20.0)
        self.assertTrue(np.isnan(row.delta))
        with tempfile.TemporaryDirectory() as tmp:
            stats = collector.finish(Path(tmp))
        self.assertEqual(stats["unreachable_rows"], 1)
        self.assertEqual(stats["unreachable_with_ceiling_rows"], 1)
        self.assertEqual(stats["numerical_failure_rows"], 0)
        self.assertEqual(stats["improving_rows"], 0)

    def test_arithmetic_error_from_strict_hit_is_recorded_not_reachable(self):
        p, qlog, truth, valid, region = scene()
        set_pixel(p, qlog, truth, 0, 0, 1.0, 30.0, 5.0)
        collector = manifest.CandidateManifest()
        with patch.object(manifest, "strict_hit", side_effect=ArithmeticError("synthetic crossing failure")):
            collector.update(p, qlog, truth, valid, region, SID)
        row = collector.rows[0]
        self.assertFalse(row.reachable)
        self.assertGreater(row.a_after, 20.0)
        self.assertTrue(np.isnan(row.delta))

    def test_malformed_inputs_are_rejected(self):
        p, qlog, truth, valid, region = scene()
        cases = [
            ("wrong qlog shape", p, qlog[:31], truth, valid, region),
            ("wrong field shape", p[:, :99], qlog, truth, valid, region),
        ]
        for name, *arguments in cases:
            with self.subTest(name=name), self.assertRaises(ValueError):
                manifest.CandidateManifest().update(*arguments, SID)

        p, qlog, truth, valid, region = scene()
        short = region.copy()
        short.ravel()[manifest.SUPERVISION_PIXELS_PER_SCENE - 1] = False
        with self.assertRaises(ValueError):
            manifest.CandidateManifest().update(p, qlog, truth, valid, short, SID)

        p, qlog, truth, valid, region = scene()
        qlog[:, 0, 0] = np.log1p(np.linspace(30.0, 0.1, 32))
        with self.assertRaises(ValueError):
            manifest.CandidateManifest().update(p, qlog, truth, valid, region, SID)

        p, qlog, truth, valid, region = scene()
        with self.assertRaises(ValueError):
            manifest.CandidateManifest().update(p, qlog, truth.astype(np.float64), valid, region, SID)

        p, qlog, truth, valid, region = scene()
        p[0, 0] = 1.5
        with self.assertRaises(ValueError):
            manifest.CandidateManifest().update(p, qlog, truth, valid, region, SID)

        p, qlog, truth, valid, region = scene()
        truth[0, 0] = np.float32(-1.0)
        with self.assertRaises(ValueError):
            manifest.CandidateManifest().update(p, qlog, truth, valid, region, SID)

        p, qlog, truth, valid, region = scene()
        p[0, 0] = np.nan
        with self.assertRaises(ValueError):
            manifest.CandidateManifest().update(p, qlog, truth, valid, region, SID)

        p, qlog, truth, valid, region = scene()
        collector = manifest.CandidateManifest()
        with self.assertRaises(ValueError):
            collector.update(p, qlog, truth, valid, region, "2025-03-01T05:30:00Z")
        self.assertEqual(collector.rows, [])
        self.assertEqual(collector.scenes, set())
        collector.update(p, qlog, truth, valid, region, SID)
        with self.assertRaises(ValueError):
            collector.update(p, qlog, truth, valid, region, SID)

    def test_row_cap_accepts_20000_then_rejects_the_20001st(self):
        high = np.log1p(np.linspace(25.0, 40.0, 32))
        collector = manifest.CandidateManifest()
        for day in range(1, 6):
            p, qlog, truth, valid, region = scene()
            p[:] = 1.0
            qlog[:] = high[:, None, None]
            collector.update(p, qlog, truth, valid, region, f"2023-03-{day:02d}T00:00:00Z")
        self.assertEqual(len(collector.rows), 5 * manifest.SUPERVISION_PIXELS_PER_SCENE)

        p, qlog, truth, valid, region = scene()
        p.ravel()[:2850] = 1.0
        qlog[:] = high[:, None, None]
        collector.update(p, qlog, truth, valid, region, "2023-03-06T00:00:00Z")
        self.assertEqual(len(collector.rows), manifest.MAX_CANDIDATE_ROWS)

        p, qlog, truth, valid, region = scene()
        p[0, 0] = 1.0
        qlog[:] = high[:, None, None]
        with self.assertRaisesRegex(ValueError, "row cap"):
            collector.update(p, qlog, truth, valid, region, "2023-03-07T00:00:00Z")
        self.assertEqual(len(collector.rows), manifest.MAX_CANDIDATE_ROWS)


if __name__ == "__main__":
    unittest.main()
