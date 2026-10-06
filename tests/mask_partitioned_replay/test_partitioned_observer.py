"""TEST_FIXTURE_ONLY: synthetic tensors/models, no formal checkpoint updates."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src"), str(ROOT / "tests/quantile_overflow_autopsy")]
import gc
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import torch
from mask_partitioned_replay_v1.observer import Observer, partition_statistics
from mask_partitioned_replay_v1 import common as c
from mask_partitioned_replay_v1.summary import cohort, validate_row
from yuntapr.models.probability_heads import ProbabilityHeads
import test_observation as original_fixture


def mask():
    value = torch.zeros((100, 100), dtype=torch.bool)
    value.flatten()[:3430] = True
    return value


def qlog(batch=2):
    return torch.zeros((batch, 32, 100, 100), dtype=torch.float64)


def observe(value):
    return partition_statistics(value, mask(), [f"SYNTHETIC_SCENE_{b}" for b in range(value.shape[0])])


class PartitionedObserverTests(unittest.TestCase):
    def test_native_argmax_coordinates_and_sample_identity(self):
        q = qlog(); q[1, 30, 10, 7] = 12.; q[0, 31, 99, 3] = 15.
        parts = observe(q)
        a, b = parts[c.REGIONS[0]]["argmax"], parts[c.REGIONS[1]]["argmax"]
        self.assertEqual((a["batch_index"], a["tau_ordinal"], a["row"], a["column"]), (1, 31, 10, 7))
        self.assertEqual(a["sample_id"], "SYNTHETIC_SCENE_1")
        self.assertEqual((b["batch_index"], b["tau_ordinal"], b["row"], b["column"]), (0, 32, 99, 3))
        self.assertEqual(b["qlog_value"], 15.)

    def test_tie_identity_first_native_position(self):
        parts = observe(qlog())
        self.assertEqual((parts[c.REGIONS[0]]["argmax"]["row"], parts[c.REGIONS[0]]["argmax"]["column"]), (0, 0))
        self.assertEqual((parts[c.REGIONS[1]]["argmax"]["row"], parts[c.REGIONS[1]]["argmax"]["column"]), (34, 30))

    def test_pixel_tau_vs_any_tau_and_strict_threshold(self):
        q = qlog(); t = math.log1p(10)
        q[0, 0, 1, 1] = t; q[0, 1, 1, 1] = t + 1e-10
        q[1, 1, 90, 1] = t + 1e-10; q[1, 2, 90, 1] = t + 1e-10
        parts = observe(q)
        inside, outside = [parts[r]["threshold_exceedance_counts"][0] for r in c.REGIONS]
        self.assertEqual((inside["scene_pixel_tau_exposure"], inside["scene_pixel_any_tau_exposure"]), (1, 1))
        self.assertEqual((outside["scene_pixel_tau_exposure"], outside["scene_pixel_any_tau_exposure"]), (2, 1))
        self.assertEqual(outside["per_tau_scene_pixel_exposure"][1:3], [1, 1])

    def test_fp64_risk_each_region_and_exact_boundary(self):
        q = qlog(); q[0, 31, 10, 7] = c.FP64_BOUNDARY; q[1, 31, 99, 3] = c.FP64_BOUNDARY + 1.
        parts = observe(q)
        self.assertFalse(parts[c.REGIONS[0]]["FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED"])
        self.assertTrue(parts[c.REGIONS[1]]["FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED"])
        q[0, 31, 10, 7] += 1.
        self.assertTrue(observe(q)[c.REGIONS[0]]["FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED"])

    def test_observer_readonly_tensor_gradient_and_rng(self):
        q = qlog().requires_grad_(True); before = q.detach().clone(); rng = torch.get_rng_state().clone()
        observe(q)
        self.assertTrue(torch.equal(q, before)); self.assertIsNone(q.grad)
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))

    def test_partition_exhausts_grid_and_exposure_denominators(self):
        parts = observe(qlog())
        self.assertEqual(sum(p["cells_per_scene"] for p in parts.values()), 10000)
        self.assertEqual(sum(p["scene_pixel_tau_exposures"] for p in parts.values()), 2 * 32 * 10000)

    def test_per_tau_lower_median_convention(self):
        q = qlog(1); q.reshape(1, 32, -1)[:, :, :1715] = 4.
        self.assertEqual(observe(q)[c.REGIONS[0]]["per_tau_qlog_median"], [0.] * 32)

    def test_wrong_shape_dtype_mask_and_nonfinite_rejected(self):
        for value in (torch.zeros((1, 32, 100, 100)), torch.zeros((1, 32, 100, 99), dtype=torch.float64)):
            with self.assertRaises(ValueError): partition_statistics(value, mask(), ["fixture"])
        with self.assertRaises(ValueError): partition_statistics(qlog(1), ~mask(), ["fixture"])
        value = qlog(1); value[0, 0, 0, 0] = math.nan
        with self.assertRaises(ValueError): observe(value)

    def test_cohort_distributions_and_threshold_totals(self):
        rows = []
        for update, value in enumerate((4., 8.)):
            q = qlog(); q[0, 31, 10, 7] = value
            parts = observe(q)
            rows.append({"scope": c.SCOPE, "update": update, "sample_ids": ["SYNTHETIC_SCENE_0", "SYNTHETIC_SCENE_1"],
                         "captured_before_expm1": True, "mask_partitioned": parts})
            validate_row(rows[-1])
        output = cohort(rows)["regions"][c.REGIONS[0]]
        self.assertEqual(output["per_forward_max_distribution"]["median"], 6.)
        self.assertEqual(output["threshold_exceedance_totals"][0]["scene_pixel_tau_exposure"], 2)
        self.assertEqual(output["threshold_exceedance_totals"][0]["scene_pixel_any_tau_exposure"], 2)

    def test_validation_rejects_conflated_pixel_counts(self):
        row = {"scope": c.SCOPE, "update": 1, "sample_ids": ["SYNTHETIC_SCENE_0", "SYNTHETIC_SCENE_1"],
               "captured_before_expm1": True, "mask_partitioned": observe(qlog())}
        row["mask_partitioned"][c.REGIONS[0]]["threshold_exceedance_counts"][0]["scene_pixel_tau_exposure"] = 1
        with self.assertRaises(ValueError): validate_row(row)

    def test_checkpoint_hash_reads_allow_pinned_earlier_checkpoints(self):
        paths = [ROOT / f"SYNTHETIC_epoch_{i}.pt" for i in range(1, 5)]
        c.checkpoint_byte_read_policy(paths[0], False, paths)
        with self.assertRaises(PermissionError): c.checkpoint_byte_read_policy(paths[0], True, paths)
        with self.assertRaises(PermissionError): c.checkpoint_byte_read_policy(ROOT / "other.pt", False, paths)

    def test_only_last_checkpoint_can_be_deserialized(self):
        last = ROOT / "SYNTHETIC_epoch_4.pt"
        c.checkpoint_deserialization_policy(last, last)
        with self.assertRaises(PermissionError): c.checkpoint_deserialization_policy(ROOT / "SYNTHETIC_epoch_1.pt", last)
        with self.assertRaises(PermissionError): c.checkpoint_deserialization_policy(object(), last)

    def test_union_must_exactly_match_previous_autopsy(self):
        parts = observe(qlog()); actual = {"mask_partitioned": parts, "sample_ids": ["a", "b"], "update": 1}
        previous = {"sample_ids": ["a", "b"], "update": 1, "qlog_per_tau_max": [0.] * 32, "qlog": {"min": 0., "max": 0.}}
        c.check_partition_union(previous, actual)
        previous["qlog_per_tau_max"][0] = 1e-20
        with self.assertRaises(ValueError): c.check_partition_union(previous, actual)

    def test_original_expm1_called_once_and_original_overflow_raised(self):
        class FixtureModel(torch.nn.Module):
            def __init__(self):
                super().__init__(); self.projection = torch.nn.Identity()
                self.backbone = torch.nn.Module(); self.backbone.dec0 = torch.nn.Linear(1, 1)
                self.heads = ProbabilityHeads(48, .1, epsilon_mono=6e-8, accumulation_dtype=torch.float64)
            def forward(self, x): return self.heads(self.projection(x))
        model = FixtureModel(); optimizer = torch.optim.AdamW(model.parameters())
        with torch.no_grad(): model.heads.quantile.weight.zero_(); model.heads.quantile.bias.fill_(23.)
        batch = SimpleNamespace(yunnan_eval_mask=mask()[None, None], sample_ids=["SYNTHETIC_SCENE_0"])
        item = {"sample_id": "SYNTHETIC_SCENE_0", "index": 0, "frames": [], "target_sha256": "FIXTURE", "normalization_sha256": "FIXTURE"}
        observer = Observer(model, mask()); observer.begin(batch, [item], [], optimizer, 50538)
        original = torch.expm1; calls = []
        def delegate(q, *args, **kwargs):
            self.assertTrue(observer.current["captured_before_expm1"])
            self.assertTrue(observer.failure["inside_any_qlog_above_fp64_boundary"])
            calls.append(True); return original(q, *args, **kwargs)
        with patch.object(torch, "expm1", delegate), observer.installed():
            with self.assertRaisesRegex(FloatingPointError, "QUANTILE_PHYSICAL_OVERFLOW"):
                model(torch.ones((1, 48, 100, 100)))
        self.assertEqual(calls, [True]); observer.release()
        del observer, optimizer, model; gc.collect()

    def test_cuda_frozen_update_output_loss_grad_model_optimizer_rng_bit_exact(self):
        # Reuse the existing actual CUDA two-update fixture, changing only its
        # observer factory. Its model/output/optimizer/grad/RNG hashes are exact.
        with patch.object(original_fixture, "Observer", lambda model: Observer(model, mask())):
            original_fixture.test_cuda_two_update_frozen_path_bit_exact_with_observer()
