"""One bounded CLI invocation, followed by checks of its synthetic evidence."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import torch

from tools.research_readiness.probe_dtfm_gradient_release import tensor_statistics


ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "tools/research_readiness/probe_dtfm_gradient_release.py"


class DtfmGradientReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        environment = dict(os.environ, CUDA_VISIBLE_DEVICES="",
                           PYTHONDONTWRITEBYTECODE="1")
        cls.execution = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(ENTRY)],
            cwd=ROOT, env=environment, capture_output=True, text=True,
            encoding="utf-8", timeout=60, check=True,
        )
        cls.report = json.loads(cls.execution.stdout)

    def test_scope_and_closed_synthetic_update_count(self):
        report = self.report
        self.assertEqual(report["scope"], "CPU_SYNTHETIC_FUSION_GRAPH_ONLY")
        self.assertEqual(report["seed"], 20261107)
        self.assertEqual(report["input_shape"], [2, 48, 9, 9])
        self.assertEqual(report["condition_channels"], [26, 28])
        self.assertEqual(report["device"], "cpu")
        self.assertEqual(report["dtype"], "torch.float32")
        self.assertEqual(report["updates_per_arm"], 5)
        self.assertEqual(report["synthetic_optimizer_step_calls"], 10)
        self.assertEqual(report["scientific_optimizer_updates"], 0)
        self.assertEqual(report["scientific_payload_reads"], 0)
        self.assertEqual(report["optimizer"]["weight_decay"], 0)
        self.assertEqual(report["optimizer"]["kind"], "SGD")

    def test_native_zero_initialized_identity_and_parameter_counts(self):
        for model in self.report["models"].values():
            self.assertEqual(model["fusion_parameters"], 50192)
            self.assertEqual(model["steps"][0]["residual_before_update"]["nonzero"], 0)
            self.assertNotEqual(model["initial_state_sha256"], model["final_state_sha256"])
        b8 = self.report["models"]["B8"]["steps"][0]
        self.assertEqual(b8["modulation_before_update"]["gamma"]["nonzero"], 0)
        self.assertEqual(b8["modulation_before_update"]["beta"]["nonzero"], 0)

    def test_first_backward_respects_outer_zero_gate(self):
        for model in self.report["models"].values():
            first = model["steps"][0]["blocks"]
            self.assertGreater(first["fuse"]["gradient"]["nonzero"], 0)
            for block, value in first.items():
                if block != "fuse":
                    self.assertEqual(value["gradient"]["nonzero"], 0)
                    self.assertEqual(value["update_delta"]["nonzero"], 0)

    def test_release_is_observed_within_predeclared_bound(self):
        self.assertEqual(self.report["SYNTHETIC_GRADIENT_PATH_CHECK"], "PASS")
        for model in self.report["models"].values():
            self.assertEqual(len(model["steps"]), 5)
            self.assertEqual(model["verdict"], "RELEASE_OBSERVED")
            for first in model["first_nonzero_gradient_backward"].values():
                self.assertGreaterEqual(first, 1)
                self.assertLessEqual(first, 5)

    def test_all_recorded_gradients_and_updates_are_finite(self):
        for model in self.report["models"].values():
            for row in model["steps"]:
                for value in row["blocks"].values():
                    self.assertFalse(value["gradient_is_none"])
                    for field in ("gradient", "parameter_before", "update_delta"):
                        self.assertTrue(value[field]["finite"])
                        self.assertGreaterEqual(value[field]["l2"], 0)

    def test_source_of_performance_is_not_inferred(self):
        self.assertEqual(self.report["real_training_cause"], "NOT_VERIFIED")
        self.assertEqual(self.report["performance_improvement"], "NOT_VERIFIED")
        self.assertFalse(self.report["optimizer"]["scientific_AdamW_trajectory"])

    def test_statistics_reject_nonfinite_tensors(self):
        with self.assertRaises(FloatingPointError):
            tensor_statistics(torch.tensor([float("nan")]))
        with self.assertRaises(FloatingPointError):
            tensor_statistics(torch.tensor([float("inf")]))


if __name__ == "__main__":
    unittest.main()
