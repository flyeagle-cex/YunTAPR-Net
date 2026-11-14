"""Actual CPU Torch tensor regression through the worker's collector wiring.

No model, real research input, CUDA tensor or formal evaluation is used.
"""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import torch

from tools.research_readiness import paired_point_worker as worker

definition = importlib.util.spec_from_file_location(
    "paired_worker_fixture", Path(__file__).with_name("test_paired_point_worker.py"))
fixtures = importlib.util.module_from_spec(definition)
definition.loader.exec_module(fixtures)


class RealTensorExportTests(unittest.TestCase):
    setUp = fixtures.WorkerTests.setUp

    def test_real_bfloat16_predictions_feed_both_collectors_without_cuda(self):
        def tensor_factory(bfloat16=False):
            return torch.tensor([0.25, 0.5], device="cpu", requires_grad=True,
                                dtype=torch.bfloat16 if bfloat16 else torch.float32)

        with self.assertRaisesRegex(TypeError, "BFloat16"):
            tensor_factory(bfloat16=True).detach().cpu().numpy()

        # Substitute real CPU tensors at the autocast-output/NumPy boundary.
        with fixtures.workspace_directory() as temporary:
            folder = Path(temporary)
            runtime, proposal, private, state, _, _ = fixtures.fixture(folder, tensor_factory)
            seen = {"point": [], "joint": []}
            for name, bucket in (("PointMetricAccumulator", "point"),
                                 ("StrongJointAccumulator", "joint")):
                original = getattr(runtime, name)

                def wrapped_class(base, key):
                    class Checked(base):
                        def add(self, *args):
                            probability, quantiles = args[-2:]
                            assert isinstance(probability, np.ndarray)
                            assert isinstance(quantiles, np.ndarray)
                            assert probability.dtype == quantiles.dtype == np.float64
                            np.testing.assert_array_equal(probability, [0.25, 0.5])
                            seen[key].append(probability.copy())
                            return super().add(*args)
                    return Checked

                setattr(runtime, name, wrapped_class(original, bucket))
            with patch.object(worker, "_runtime", return_value=runtime), \
                    patch.object(torch.cuda, "_lazy_init", side_effect=AssertionError("CUDA forbidden")):
                result = worker.run_task(folder, proposal, private, "CONTROL_E0", folder / "output", lambda: None)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(len(seen["point"]), 121)
            self.assertEqual(len(seen["joint"]), 121)
            self.assertEqual(state["forwards"], state["joint"])


if __name__ == "__main__":
    unittest.main()
