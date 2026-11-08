"""Synthetic loss, metric and dispatch checks without data or optimizer steps."""

import copy
from contextlib import ExitStack
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, mock_open, patch

import numpy as np
import torch

from tests.research_readiness.test_dynamic_loss_entry import fixture, loss_gradients
from tools.research_readiness import start_independent_process as launcher
from yuntapr.experimental.core_innovation.stage4 import engine
from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.upper_quantile import (
    MILD_PROFILE, mild_weights, profile_identity,
)
from yuntapr.experimental.research_readiness import dynamic_training
from yuntapr.experimental.research_readiness import upper_quantile_training as tasks
from yuntapr.experimental.research_readiness.upper_quantile_diagnostics import PhysicalPinball


def synthetic_proposal():
    return {
        "tasks": copy.deepcopy(tasks.TASKS),
        "protocol": {"loss": "E0", "lambda_q": 1.0, "seed": 2029, "epochs": 9, "endpoint": "FIXED_EPOCH_9"},
        "scientific_choices": {"candidate_loss": profile_identity(), "evaluation": tasks.evaluation_contract()},
        "budget": {
            "total_updates": 8640, "total_source_bytes": 955143907680, "total_source_files": 285626,
            "max_package_seconds": 43200, "max_model_seconds": 21600,
            "replay_allowance": 0, "additional_retry_allowance": 0, "initial_free_bytes": 0,
        },
        "runtime_binding": {"python_executable_sha256": "SYNTHETIC"},
    }


class UpperQuantileLossTests(unittest.TestCase):
    def test_fixed_mild_weights_are_positive_monotonic_and_normalized(self):
        weights = mild_weights()
        self.assertEqual(weights.dtype, torch.float64)
        self.assertEqual(weights.shape, (32,))
        self.assertTrue(bool((weights > 0).all()))
        self.assertTrue(bool((weights.diff() > 0).all()))
        self.assertEqual(weights[0].item(), 65 / 96)
        self.assertEqual(weights[-1].item(), 127 / 96)
        self.assertAlmostEqual(weights.sum().item(), 32.0, places=13)

    def test_node_gradients_change_but_occurrence_and_scientific_loss_are_preserved(self):
        model, batch, output = fixture("B7")
        _, original = engine.forward(model, batch)
        _, candidate = engine.forward(model, batch, quantile_profile=MILD_PROFILE)
        self.assertEqual(candidate.experiment_id, MILD_PROFILE)
        self.assertEqual((candidate.n_valid, candidate.n_rain), (3430, 1960))
        self.assertTrue(torch.equal(original.s_occ, candidate.s_occ))
        self.assertTrue(torch.equal(original.s_qr, candidate.s_qr))
        self.assertTrue(torch.equal(original.scientific_conditional_pinball, candidate.scientific_conditional_pinball))
        old_occurrence, old_quantile = loss_gradients(original, output)
        new_occurrence, new_quantile = loss_gradients(candidate, output)
        self.assertTrue(torch.equal(old_occurrence, new_occurrence))
        expected = old_quantile * mild_weights().reshape(1, 32, 1, 1)
        torch.testing.assert_close(new_quantile, expected, rtol=1e-12, atol=1e-16)
        self.assertFalse(torch.equal(old_quantile, new_quantile))
        expected_total = original.s_occ.double() / original.n_valid + candidate.weighted_quantile_per_valid
        torch.testing.assert_close(candidate.training_objective, expected_total, rtol=1e-15, atol=1e-15)

    def test_all_dry_has_connected_zero_quantile_gradient(self):
        model, batch, output = fixture("B7", dry=True)
        _, result = engine.forward(model, batch, quantile_profile=MILD_PROFILE)
        self.assertEqual(result.n_rain, 0)
        self.assertIsNone(result.scientific_conditional_pinball)
        self.assertEqual(result.weighted_quantile_per_valid.item(), 0)
        _, gradient = loss_gradients(result, output)
        self.assertEqual(torch.count_nonzero(gradient).item(), 0)

    def test_unknown_or_mismatched_forward_profile_rejects_before_model(self):
        for kind, profile, config in [("B8", MILD_PROFILE, get_config("E0")),
                                      ("B7", MILD_PROFILE, get_config("E2")),
                                      ("B7", "UNKNOWN", get_config("E0"))]:
            model, batch, _ = fixture(kind)
            with self.subTest(kind=kind, profile=profile), self.assertRaises(PermissionError):
                engine.forward(model, batch, quantile_profile=profile, loss_config=config)
            model.assert_not_called()

    def test_executor_closes_model_seed_recovery_and_global_weight_scope(self):
        allowed = engine.PairedExecutor(None, "SYNTHETIC", kinds=("B7",), decision=SimpleNamespace(seed=2029), quantile_profile=MILD_PROFILE)
        self.assertEqual(allowed.loss_identity, profile_identity())
        for kinds, seed, weight, recovery in [(("B8",), 2029, 1, None), (("B7",), 2030, 1, None),
                                              (("B7",), 2029, 2, None), (("B7",), 2029, 1, object())]:
            with self.subTest(kinds=kinds, seed=seed, weight=weight), self.assertRaises(PermissionError):
                engine.PairedExecutor(None, "SYNTHETIC", kinds=kinds, decision=SimpleNamespace(seed=seed),
                                      lambda_q=weight, recovery=recovery, quantile_profile=MILD_PROFILE)

    def test_candidate_origin_is_bound_to_control_initial_state_and_order(self):
        orders = {epoch: (f"SYNTHETIC_{epoch}",) for epoch in range(1, 10)}
        reference = {"original_model_state_sha256": "SYNTHETIC", "epoch_order_sha256": [engine.digest(orders[e]) for e in range(1, 10)]}
        executor = engine.PairedExecutor(None, "SYNTHETIC", kinds=("B7",), decision=SimpleNamespace(seed=2029),
                                         quantile_profile=MILD_PROFILE, origin_reference=reference)
        executor.check_origin_pair({"B7": {"full_state_sha256": "SYNTHETIC"}}, orders)
        with self.assertRaises(RuntimeError):
            executor.check_origin_pair({"B7": {"full_state_sha256": "DIFFERENT"}}, orders)
        changed = dict(orders)
        changed[9] = ("DIFFERENT",)
        with self.assertRaises(RuntimeError):
            executor.check_origin_pair({"B7": {"full_state_sha256": "SYNTHETIC"}}, changed)

    def test_task_profile_mismatch_rejects_before_source_io(self):
        with patch.object(dynamic_training.sqlite3, "connect") as connect:
            with self.assertRaises(PermissionError):
                dynamic_training.run_task(Path("SYNTHETIC"), {"protocol": {"loss": "E0", "lambda_q": 1}},
                                          {}, {}, {}, "SYNTHETIC", "B7", 2029, started=0,
                                          pair_reference=None, static_name="SYNTHETIC", quantile_profile=MILD_PROFILE)
            connect.assert_not_called()

    def test_actual_task_wiring_reaches_selected_forward_loss(self):
        model, batch, _ = fixture("B7")
        observed = []

        def synthetic_run(executor, readers):
            observed.append(engine.forward(model, batch, loss_config=executor.loss_config, quantile_profile=executor.quantile_profile)[1])

        proposal = {
            "protocol": {"loss": "E0", "lambda_q": 1, "quantile_profile": MILD_PROFILE},
            "data": batch.identity, "budget": {"minimum_task_free_bytes": 0, "max_model_seconds": 1},
            "static_source_sha256": {"B7": "SYNTHETIC"},
            "scientific_choices": {"DOTE": {"pwat_reference_kg_m2": 1, "reference_provenance": "SYNTHETIC"},
                                   "modulation_limit": 0.1, "origin_reference": {"B7": {}}},
        }
        with ExitStack() as stack:
            stack.enter_context(patch.dict(dynamic_training.os.environ, {"PYTHONHASHSEED": "2029"}))
            stack.enter_context(patch.object(dynamic_training.sqlite3, "connect"))
            stack.enter_context(patch.object(dynamic_training.shutil, "disk_usage", return_value=SimpleNamespace(free=1)))
            stack.enter_context(patch.object(dynamic_training.time, "monotonic", return_value=0))
            stack.enter_context(patch.object(dynamic_training, "SourceMeter"))
            stack.enter_context(patch.object(dynamic_training, "unpack", return_value=object()))
            stack.enter_context(patch.object(dynamic_training, "read", return_value={"scalers": "SYNTHETIC"}))
            stack.enter_context(patch.object(dynamic_training, "PopulationPlan", return_value=SimpleNamespace(identity=batch.identity, strong_scene_ids=())))
            stack.enter_context(patch.object(dynamic_training, "model_factory", return_value=object()))
            stack.enter_context(patch.object(dynamic_training, "ReaderFactory"))
            stack.enter_context(patch.object(dynamic_training, "write"))
            stack.enter_context(patch.object(dynamic_training, "endpoint", return_value={"logical_source_bytes": 0, "logical_source_files": 0}))
            stack.enter_context(patch.object(engine.PairedExecutor, "run", autospec=True, side_effect=synthetic_run))
            result = dynamic_training.run_task(
                Path("SYNTHETIC"), proposal, {"output_root": "SYNTHETIC", "terrain": "SYNTHETIC"},
                {"decision_id": "SYNTHETIC"}, {"private_inputs": {"stage3_run": "SYNTHETIC", "request": "SYNTHETIC"}},
                "SYNTHETIC", "B7", 2029, started=0, pair_reference=None, static_name="SYNTHETIC", quantile_profile=MILD_PROFILE,
                dynamic_transform_factory=MagicMock(),
            )
        self.assertEqual(observed[0].experiment_id, MILD_PROFILE)
        self.assertEqual(result["loss_arm"], MILD_PROFILE)


class PhysicalPinballTests(unittest.TestCase):
    def test_hand_calculated_physical_score_and_masks(self):
        score = PhysicalPinball()
        rate = np.array([[60.0, 0.0, np.nan]], dtype=np.float32)
        qlog = np.broadcast_to(np.log1p(np.arange(1, 33, dtype=np.float64))[:, None, None], (32, 1, 3))
        score.add(rate, qlog, np.array([[True, True, False]]))
        result = score.finish()
        self.assertEqual(result["n_rain"], 1)
        self.assertAlmostEqual(result["pinball_mm_h"], 19.0859375, places=12)
        self.assertAlmostEqual(result["normalized_pinball"], 19.0859375 / 20, places=13)
        self.assertEqual(result["strata"][-1]["n_rain"], 1)

    def test_physical_bins_follow_original_strict_lower_inclusive_upper(self):
        score = PhysicalPinball()
        rate = np.array([[0.1, 1, 5, 10, 20, 30, 50, 51]], dtype=np.float32)
        qlog = np.broadcast_to(np.linspace(0.2, 4, 32)[:, None, None], (32, 1, 8))
        score.add(rate, qlog, np.ones_like(rate, dtype=bool))
        self.assertEqual([row["n_rain"] for row in score.finish()["strata"]], [1] * 7)

    def test_physical_overflow_fails_without_clipping(self):
        score = PhysicalPinball()
        with self.assertRaises((FloatingPointError, ValueError)):
            score.add(np.array([[60]], dtype=np.float32), np.linspace(700, 731, 32)[:, None, None], np.ones((1, 1), dtype=bool))


class UpperQuantileDispatchTests(unittest.TestCase):
    def test_scope_closes_profile_and_evaluation_contract(self):
        proposal = synthetic_proposal()
        tasks.validate_scope(proposal)
        for key, value in [("weight_rule", "2*tau"), ("lambda_q", 2.0)]:
            changed = copy.deepcopy(proposal)
            changed["scientific_choices"]["candidate_loss"][key] = value
            with self.assertRaises(PermissionError):
                tasks.validate_scope(changed)

    def test_missing_approval_precedes_source_runtime_and_output(self):
        with patch.object(Path, "is_file", return_value=False), patch.object(tasks, "resources") as admission, \
                patch.object(tasks, "read") as read, patch.object(tasks, "run_task") as run:
            with self.assertRaises(PermissionError):
                tasks.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
            admission.assert_not_called()
            read.assert_not_called()
            run.assert_not_called()

    def test_launcher_rejects_other_profiles_and_runtime(self):
        proposal = synthetic_proposal()
        with patch.object(launcher, "sha", return_value="SYNTHETIC"):
            launcher.validate_upper_quantile_scope(proposal, Path("SYNTHETIC"))
            changed = copy.deepcopy(proposal)
            changed["tasks"][1]["quantile_profile"] = "UNKNOWN"
            with self.assertRaises(PermissionError):
                launcher.validate_upper_quantile_scope(changed, Path("SYNTHETIC"))
        with patch.object(launcher, "sha", return_value="DIFFERENT"), self.assertRaises(PermissionError):
            launcher.validate_upper_quantile_scope(proposal, Path("SYNTHETIC"))

    def test_controller_blocks_second_arm_after_first_failure(self):
        proposal = synthetic_proposal()
        with ExitStack() as stack:
            stack.enter_context(patch.object(Path, "exists", return_value=False))
            stack.enter_context(patch.object(Path, "mkdir"))
            stack.enter_context(patch.object(Path, "open", mock_open()))
            stack.enter_context(patch.object(tasks, "checked", return_value=(proposal, {"output_root": "SYNTHETIC"}, {}, {})))
            stack.enter_context(patch.object(tasks.time, "monotonic", return_value=0))
            stack.enter_context(patch.object(tasks.shutil, "disk_usage", return_value=SimpleNamespace(free=1)))
            stack.enter_context(patch.object(tasks, "resources", return_value={}))
            stack.enter_context(patch.object(tasks, "write"))
            launch = stack.enter_context(patch.object(tasks.subprocess, "Popen"))
            launch.return_value.wait.return_value = 1
            with self.assertRaisesRegex(RuntimeError, "remaining tasks blocked"):
                tasks.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
            launch.assert_called_once()
            self.assertEqual(launch.call_args.args[0][-2:], ["--task-index", "0"])

    def test_worker_binds_task_profile_folder_and_control_origin(self):
        approval = {"decision_id": "SYNTHETIC"}
        private = {"output_root": "SYNTHETIC"}
        for index, task in enumerate(tasks.TASKS):
            def metadata(path):
                if path.name == "authorization_binding.json":
                    return {"approval": approval, "controller_pid": os.getppid()}
                if path.name.startswith("task_"):
                    return {"index": index, "controller_pid": os.getppid(), "code_commit": "SYNTHETIC"}
                if path.name == "completion.json":
                    return {"status": "COMPLETE_TRAIN_AND_DEV_EVALUATION", "code_commit": "SYNTHETIC"}
                if path.name == "paired_initial_identity.json":
                    return {"B7": {"full_state_sha256": "SYNTHETIC_ORIGIN"}}
                return {str(epoch): {"sha256": f"SYNTHETIC_{epoch}"} for epoch in range(1, 10)}

            with self.subTest(index=index), patch.object(tasks, "checked", return_value=(synthetic_proposal(), private, approval, {})), \
                    patch.object(tasks, "read", side_effect=metadata), patch.object(Path, "mkdir"), patch.object(tasks, "run_task") as run:
                tasks.worker(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC", index)
                args, kwargs = run.call_args
                self.assertEqual(args[1]["protocol"]["quantile_profile"], task["quantile_profile"])
                self.assertEqual(Path(args[2]["output_root"]).name, task["arm"])
                self.assertEqual(kwargs["quantile_profile"], task["quantile_profile"])
                if index == 1:
                    self.assertEqual(args[1]["scientific_choices"]["origin_reference"]["B7"]["original_model_state_sha256"], "SYNTHETIC_ORIGIN")
                    self.assertEqual(kwargs["pair_reference"], Path("SYNTHETIC") / "CONTROL_E0/B7_s2029")
                else:
                    self.assertIsNone(kwargs["pair_reference"])


def summary_fixture(physical_candidate=0.9):
    reports, tails = {}, {}
    edges = [0.1, 1, 5, 10, 20, 30, 50, None]
    for index, task in enumerate(tasks.TASKS):
        value = 1.0 if index == 0 else 0.9
        summary = {
            "n_valid": 10, "n_rain": 7, "conditional_pinball": value, "brier": value / 10,
            "average_precision": 0.6 + index / 10, "auroc": 0.8 + index / 20,
            "q32_signed_bias": 0.0, "core_fp64": value,
            "rain_strata": [{"n": 1, "conditional_pinball": value}],
        }
        reports[task["arm"]] = {
            "source_identity": "SYNTHETIC", "population_ids_sha256": "SYNTHETIC", "partition_sha256": "SYNTHETIC",
            "groups": {"all": {"ids_sha": "SYNTHETIC", "source_sha": "SYNTHETIC", "summary": summary}},
        }
        rows = [{"lower": edges[i], "upper": edges[i + 1], "n_rain": 1, "conditional_pinball": value} for i in range(7)]
        physical_value = 1.0 if index == 0 else physical_candidate
        physical_rows = [dict(row, pinball_sum_mm_h=20 * physical_value) for row in rows]
        tails[task["arm"]] = {"strata": rows, "physical_pinball": {"scale_mm_h": 20.0, "strata": physical_rows}}

    def metadata(path):
        arm = path.parent.parent.name
        return reports[arm] if "development" in path.name else tails[arm]

    return metadata


class UpperQuantileScreenTests(unittest.TestCase):
    def test_receipts_bind_every_epoch_to_the_actual_arm(self):
        for task in tasks.TASKS:
            def metadata(path):
                if task["quantile_profile"] == "UNIFORM":
                    return {"loss_arm": "E0"} if "_train_" in path.name else {}
                return {"loss_arm": MILD_PROFILE, "loss_config": profile_identity()}
            with patch.object(tasks, "read", side_effect=metadata) as read:
                tasks.verify_loss_receipts(Path("SYNTHETIC"), task)
                self.assertEqual(read.call_count, 18)
                self.assertEqual(read.call_args_list[0].args[0].name, "B7_train_01.json")
                self.assertEqual(read.call_args_list[-1].args[0].name, "B7_LAST_epoch_09.receipt.json")
        with patch.object(tasks, "read", return_value={"loss_arm": "E0"}), self.assertRaises(ValueError):
            tasks.verify_loss_receipts(Path("SYNTHETIC"), tasks.TASKS[1])

    def test_all_seven_gates_can_pass_without_scientific_acceptance(self):
        with patch.object(tasks, "read", side_effect=summary_fixture()):
            result = tasks.pair_summary(Path("SYNTHETIC"))
        self.assertTrue(result["screen_passed"])
        self.assertEqual(len(result["development_screen_gates"]), 7)
        self.assertEqual(result["scientific_acceptance"], "NOT_VERIFIED")

    def test_physical_degradation_fails_even_when_log_loss_improves(self):
        with patch.object(tasks, "read", side_effect=summary_fixture(physical_candidate=1.1)):
            result = tasks.pair_summary(Path("SYNTHETIC"))
        self.assertFalse(result["screen_passed"])
        self.assertTrue(result["development_screen_gates"]["strong_log_pinball"])
        self.assertFalse(result["development_screen_gates"]["strong_physical_pinball"])
        self.assertFalse(result["development_screen_gates"]["all_physical_pinball"])


if __name__ == "__main__":
    unittest.main()
