"""CPU-only synthetic checks for the bounded joint-amplitude collector."""

import math
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from tools.research_readiness import start_paired_point_evaluation as runner
from tools.research_readiness.paired_joint_amplitude import (
    StrongJointAccumulator,
    pair_strong_records,
)


class JointAmplitudeTests(unittest.TestCase):
    def make_batch(self, candidate=False):
        shape = (2, 1, 2, 2)
        rate = np.zeros(shape, dtype=np.float32)
        rate[0, 0, 0, 0] = 30.0
        rate[1, 0, 1, 1] = 25.0
        # Strict >20 excludes the equality case from the strong population.
        rate[0, 0, 0, 1] = 20.0
        valid = np.ones(shape, dtype=bool)
        region = np.ones(shape, dtype=bool)
        probability = np.full(shape, 0.2, dtype=np.float32)
        base = np.linspace(0.2, math.log1p(20.0), 32, dtype=np.float64)
        q = np.broadcast_to(base[None, :, None, None], (2, 32, 2, 2)).copy()
        if candidate:
            q[:, -1, :, :] = math.log1p(21.0)
        return rate, valid, region, probability, q

    def run_arm(self, folder, arm, candidate=False, scene_ids=("2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z")):
        out = Path(folder) / f"{arm}.npz"
        acc = StrongJointAccumulator(
            scene_ids, ("2024-01-01T00:30:00Z", "2024-01-01T01:30:00Z"),
            expected_valid=8, expected_rain=3, expected_strong=2, output_path=out,
            max_batch_size=2, grid_shape=(2, 2),
        )
        rate, valid, region, probability, q = self.make_batch(candidate)
        acc.add(scene_ids, ("2024-01-01T00:30:00Z", "2024-01-01T01:30:00Z"),
                rate, valid, region, probability, q)
        summary = acc.finish(arm_id=arm, checkpoint_sha256="a" * 64, population_sha256="b" * 64)
        return out, summary

    def test_streams_only_strict_strong_population_and_pairs_exact_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            left, left_summary = self.run_arm(folder, "CONTROL_E0")
            right, _ = self.run_arm(folder, "CANDIDATE_COSINE9", candidate=True)
            paired = pair_strong_records(left, right, expected_rows=2)
            self.assertEqual(paired["n_paired"], 2)
            self.assertEqual(paired["q32_gt20_E0_only"], 0)
            self.assertEqual(paired["q32_gt20_COSINE9_only"], 2)
            self.assertEqual(left_summary["strong_probability_bins"][2]["n"], 2)
            self.assertEqual(left_summary["strong_joint_counts"]["q32_gt20_A_le20"], 0)

    def test_duplicate_or_mismatched_scene_identity_stops_pairing(self):
        with tempfile.TemporaryDirectory() as folder:
            left, _ = self.run_arm(folder, "CONTROL_E0")
            right, _ = self.run_arm(
                folder, "CANDIDATE_COSINE9", candidate=True,
                scene_ids=("2024-01-01T00:00:00Z", "2024-01-01T01:01:00Z"),
            )
            with self.assertRaises(ValueError):
                pair_strong_records(left, right, expected_rows=2)

    def test_rain_population_cannot_exceed_frozen_count_mid_stream(self):
        with tempfile.TemporaryDirectory() as folder:
            scene_ids = ("2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z")
            acc = StrongJointAccumulator(
                scene_ids, ("2024-01-01T00:30:00Z", "2024-01-01T01:30:00Z"),
                expected_valid=8, expected_rain=2, expected_strong=2,
                output_path=Path(folder) / "over-rain.npz", max_batch_size=2, grid_shape=(2, 2),
            )
            rate, valid, region, probability, q = self.make_batch()
            with self.assertRaisesRegex(ValueError, "Rainy population exceeds"):
                acc.add(scene_ids, ("2024-01-01T00:30:00Z", "2024-01-01T01:30:00Z"),
                        rate, valid, region, probability, q)

    def test_q32_strict_fp32_threshold_matches_arm_and_pair_summaries(self):
        with tempfile.TemporaryDirectory() as folder:
            scene_ids = ("2024-01-01T00:00:00Z",)
            analysis = ("2024-01-01T00:30:00Z",)
            shape = (1, 1, 1, 1)
            rate = np.full(shape, 25.0, dtype=np.float32)
            valid = region = np.ones(shape, dtype=bool)
            probability = np.full(shape, 0.5, dtype=np.float32)
            q = np.linspace(math.log1p(0.11), math.log1p(np.nextafter(20.0, np.inf)), 32, dtype=np.float64)
            q = q.reshape(1, 32, 1, 1)
            paths, summaries = [], []
            for arm in ("CONTROL_E0", "CANDIDATE_COSINE9"):
                out = Path(folder) / f"{arm}.npz"
                acc = StrongJointAccumulator(scene_ids, analysis, expected_valid=1, expected_rain=1,
                                             expected_strong=1, output_path=out, max_batch_size=1,
                                             grid_shape=(1, 1))
                acc.add(scene_ids, analysis, rate, valid, region, probability, q)
                summaries.append(acc.finish(arm_id=arm, checkpoint_sha256="a" * 64,
                                            population_sha256="b" * 64))
                paths.append(out)
            paired = pair_strong_records(*paths, expected_rows=1)
            self.assertEqual(summaries[0]["strong_joint_counts"]["q32_gt20"], 0)
            self.assertEqual(paired["q32_gt20"]["E0"], 0)
            self.assertEqual(paired["q32_gt20"]["COSINE9"], 0)
            self.assertEqual(sum(row["n"] for row in summaries[0]["strong_probability_bins"]), 1)

    def test_finalize_writes_metrics_once_after_joint_evidence_is_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder)
            checkpoint = {task: ("a" if task == runner.TASKS[0] else "b") * 64 for task in runner.TASKS}
            proposal = {"proposal_sha256": "d" * 64,
                        "models": [{"task": task, "checkpoint_sha256": checkpoint[task]}
                                   for task in runner.TASKS]}
            for task in runner.TASKS:
                arm = package / task
                arm.mkdir()
                thresholds = []
                for threshold in (0.1, 1.0, 5.0, 10.0, 20.0, 50.0):
                    positives = {0.1: 407820, 1.0: 100000, 5.0: 20000,
                                 10.0: 5000, 20.0: 717, 50.0: 0}[threshold]
                    tp = positives
                    fn = 407820 - tp if threshold == 0.1 else (717 - tp if threshold == 20.0 else 0)
                    tn = 3303090 - tp - fn
                    thresholds.append({"threshold_mm_h": threshold, "TP": tp, "FP": 0, "FN": fn, "TN": tn,
                                       "POD": 1.0 if positives else None, "FAR": 0.0, "CSI": 1.0,
                                       "Precision": 1.0, "F1": 1.0, "ETS": 1.0, "HSS": 1.0,
                                       "frequency_bias": 1.0, "truth_equal": 0, "prediction_equal": 0})
                summary = {"scenes": 963, "n_valid": 3303090, "n_rain": 407820,
                           "classification_precision": "FP32 predictions and reference rates; strict > FP32 threshold",
                           "supervision_mask_sha256": "c" * 64,
                           "methods": {name: {"continuous": {key: 0.0 for key in
                                       ("MAE", "RMSE", "MeanBias", "Pearson_CC")},
                                       "thresholds": thresholds} for name in ("A", "B", "C")}}
                (arm / "point_metrics.json").write_text(json.dumps(summary), encoding="utf-8")

                record_path = arm / "strong_joint_pixels.npz"
                scene_ids = np.asarray([f"scene-{i:04d}" for i in range(717)], dtype="U32")
                qlog = np.broadcast_to(np.linspace(math.log1p(0.11), math.log1p(25.0), 32),
                                       (717, 32)).copy()
                np.savez_compressed(record_path, scene_id=scene_ids,
                                    analysis_time=np.asarray(["2024-01-01T00:30:00Z"] * 717, dtype="U40"),
                                    pixel_index=np.zeros(717, dtype=np.int32),
                                    truth_mm_h=np.full(717, 25.0), p_occ=np.full(717, 0.2), qlog=qlog,
                                    point_A_mm_h=np.full(717, 10.0), point_B_mm_h=np.full(717, 10.0),
                                    point_C_mm_h=np.full(717, 10.0))
                # Keep ordered keys unique while using a compact synthetic fixture.
                with np.load(record_path, allow_pickle=False) as saved:
                    arrays = {name: saved[name].copy() for name in saved.files}
                arrays["pixel_index"] = np.arange(717, dtype=np.int32)
                np.savez_compressed(record_path, **arrays)
                bins = [{"index": i, "interval": f"bin-{i}", "n": 72 if i < 9 else 69,
                         "q32_ge_truth": 0, "q32_gt20": 72 if i < 9 else 69,
                         "A_gt20": 0, "B_gt20": 0, "C_gt20": 0} for i in range(10)]
                joint = {"status": "COMPLETE_ARM_STRONG_JOINT_RECORDS",
                         "checkpoint_sha256": checkpoint[task], "population_sha256": runner.POPULATION_SHA256,
                         "n_valid": 3303090, "n_strong": 717,
                         "strong_joint_counts": {"q32_gt20": 717},
                         "strong_probability_bins": bins, "record_file": record_path.name,
                         "record_bytes": record_path.stat().st_size,
                         "record_sha256": runner.sha(record_path)}
                (arm / "joint_summary.json").write_text(json.dumps(joint), encoding="utf-8")

            result = runner.finalize_pair(package, proposal)
            self.assertEqual(result["paired_joint_evidence_sha256"], runner.sha(package / "paired_joint_evidence.json"))
            self.assertTrue((package / "paired_metrics.json").is_file())


if __name__ == "__main__":
    unittest.main()
