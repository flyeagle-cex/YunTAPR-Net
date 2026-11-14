"""CPU-only synthetic checks for the bounded joint-amplitude collector."""

import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

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


if __name__ == "__main__":
    unittest.main()
