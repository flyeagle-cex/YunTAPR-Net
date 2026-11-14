"""Synthetic approval, dispatch, and summary checks. No scientific payloads."""

import copy
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import mock_open, patch

import numpy as np

from tools.research_readiness import start_independent_process as launcher
from yuntapr.experimental.phase_b_v2_ablations.schedule import COSINE9, schedule_identity
from yuntapr.experimental.research_readiness import zero_cosine9_training as controller
from yuntapr.experimental.research_readiness import dote_numeric_control


def proposal():
    return {
        "tasks": copy.deepcopy(controller.TASKS),
        "protocol": {"loss": "E0", "lambda_q": 1.0, "seed": 2029, "epochs": 9,
                     "endpoint": "FIXED_EPOCH_9", "schedule_profile": COSINE9,
                     "quantile_profile": "UNIFORM", "dynamic_control": "ZERO_NUMERIC_RETAIN_REAL_MASKS"},
        "scientific_choices": {"dynamic_control": "ZERO_NUMERIC_RETAIN_REAL_MASKS",
                               "candidate_schedule": schedule_identity(),
                               "evaluation": controller.evaluation_contract(),
                               "real_reuse": {"hardware_binding": {"cuda_name": "SYNTHETIC", "cuda_total_bytes": 1}}},
        "budget": controller.budget({"roles": {"all": {"bytes_per_pass": 53063515668, "file_count": 15868}}}),
        "runtime_binding": {"python_executable_sha256": "SYNTHETIC"},
    }


def summaries():
    strata = [{"lower": lo, "upper": hi, "n_rain": 2, "conditional_pinball": 1.0}
              for lo, hi in ((0.1, 1), (1, 5), (5, 10), (10, 20), (20, 30), (30, 50), (50, None))]
    summary = {"n_valid": 28, "n_rain": 14, "conditional_pinball": 1.0,
               "brier": 0.2, "average_precision": 0.4, "auroc": 0.7,
               "q32_signed_bias": 0.0, "core_fp64": 1.2,
               "rain_strata": [{"n": 2, "conditional_pinball": 1.0} for _ in strata]}
    report = {"source_identity": {"synthetic": True}, "population_ids_sha256": "SYNTHETIC",
              "partition_sha256": "SYNTHETIC", "groups": {
                  str(i): {"ids_sha": "SYNTHETIC", "source_sha": "SYNTHETIC", "summary": copy.deepcopy(summary)}
                  for i in range(6)}}
    report["groups"]["all"] = report["groups"].pop("0")
    physical = [dict(r, pinball_sum_mm_h=40.0) for r in strata]
    tail = {"strata": strata, "physical_pinball": {"scale_mm_h": 20.0, "strata": physical}}
    return report, tail


class ZeroCosine9Tests(unittest.TestCase):
    def test_manifest_budget_is_one_model_and_rejects_drift(self):
        caps = proposal()["budget"]
        self.assertEqual((caps["total_updates"], caps["total_source_bytes"], caps["total_source_files"]),
                         (4320, 477571953840, 142813))
        self.assertEqual((caps["replay_allowance"], caps["additional_retry_allowance"], caps["checkpoint_loads"]), (0, 0, 0))
        with self.assertRaises(ValueError):
            controller.budget({"roles": {"all": {"bytes_per_pass": 1, "file_count": 1}}})

    def test_only_explicit_zero_cosine9_scope_is_admitted(self):
        controller.validate_scope(proposal())
        changes = [("seed", 2030), ("loss", "E2"), ("lambda_q", 2), ("epochs", 10),
                   ("schedule_profile", "ORIGINAL_50"), ("quantile_profile", "UQ_MILD_V1"),
                   ("dynamic_control", "REAL"), ("endpoint", "BEST")]
        for key, value in changes:
            changed = proposal()
            changed["protocol"][key] = value
            with self.subTest(key=key), self.assertRaises(PermissionError):
                controller.validate_scope(changed)
        for value in ([], [{"model": "B8", "seed": 2029}], controller.TASKS * 2):
            changed = proposal()
            changed["tasks"] = value
            with self.assertRaises(PermissionError):
                controller.validate_scope(changed)

    def test_controller_contract_has_no_scientific_pass_or_arbitrary_effect_threshold(self):
        contract = controller.evaluation_contract()
        self.assertEqual(contract["primary"], "all_log_pinball")
        self.assertIsNone(contract["minimum_meaningful_effect"])
        self.assertEqual(contract["scientific_acceptance"], "NOT_VERIFIED")
        changed = proposal()
        changed["scientific_choices"]["evaluation"]["minimum_meaningful_effect"] = 0.01
        with self.assertRaises(PermissionError):
            controller.validate_scope(changed)

    def test_missing_approval_rejects_before_metadata_and_task(self):
        with patch.object(Path, "is_file", return_value=False), patch.object(controller, "read") as read, \
                patch.object(controller, "run_task") as run, self.assertRaises(PermissionError):
            controller.checked(Path("SYNTHETIC"), "p", "v", "missing", "SYNTHETIC")
        read.assert_not_called()
        run.assert_not_called()

    def test_old_grant_and_changed_output_are_rejected(self):
        p = proposal()
        p["proposal_sha256"] = "SYNTHETIC_PROPOSAL"
        private = {"output_root": "SYNTHETIC_NEW"}
        approval = dict(approved_by_researcher=True, decision_id="SYNTHETIC", code_commit="SYNTHETIC",
                        proposal_sha256=p["proposal_sha256"], tasks=p["tasks"],
                        scientific_choices=p["scientific_choices"], budget=p["budget"], output_root=private["output_root"])
        controller.validate_approval(approval, p, private, "SYNTHETIC")
        for field in ("code_commit", "proposal_sha256", "tasks", "scientific_choices", "budget", "output_root"):
            changed = dict(approval, **{field: "OLD_OR_CHANGED"})
            with self.subTest(field=field), self.assertRaises(PermissionError):
                controller.validate_approval(changed, p, private, "SYNTHETIC")

    def test_launcher_preserves_cosine9_caps_and_requires_control_identity(self):
        with patch.object(launcher, "sha", return_value="SYNTHETIC"):
            launcher.validate_zero_cosine9_scope(proposal(), Path("SYNTHETIC"))
            changed = proposal()
            changed["tasks"] = [{"model": "B7", "seed": 2029, "schedule_profile": COSINE9}]
            with self.assertRaises(PermissionError):
                launcher.validate_zero_cosine9_scope(changed, Path("SYNTHETIC"))
            for key in proposal()["budget"]:
                changed = proposal()
                changed["budget"][key] += 1
                with self.subTest(key=key), self.assertRaises(PermissionError):
                    launcher.validate_zero_cosine9_scope(changed, Path("SYNTHETIC"))

    def test_zero_transform_zeros_only_numbers_and_preserves_actual_masks(self):
        numbers = np.ones((8, 100, 100), dtype=np.float32)
        valid = np.ones_like(numbers, dtype=bool)
        valid[2, 0, 0] = False
        numbers[2, 0, 0] = np.nan
        with patch.object(dote_numeric_control, "PhysicalDote") as physical:
            physical.return_value.return_value = numbers, valid
            values, mask = dote_numeric_control.ZeroNumericDote(None, None)("SYNTHETIC")
        self.assertFalse(values.any())
        np.testing.assert_array_equal(mask, valid)
        self.assertIsNot(mask, valid)
        self.assertTrue(np.isnan(numbers[2, 0, 0]))

    def test_worker_passes_zero_transform_and_saved_real_pair_to_existing_task(self):
        p, private, approval = proposal(), {"output_root": "SYNTHETIC_NEW", "real": "SYNTHETIC_REAL"}, {}
        def metadata(path):
            if path.name == "authorization_binding.json":
                return {"controller_pid": 123, "approval": approval, "started_monotonic": 10.0}
            return {"index": 0, "controller_pid": 123, "code_commit": "SYNTHETIC"}
        with patch.object(controller, "checked", return_value=(p, private, approval, {})), \
                patch.object(controller, "read", side_effect=metadata), \
                patch.object(controller.os, "getppid", return_value=123), \
                patch.object(controller, "run_task", return_value={"synthetic": True}) as run:
            controller.worker(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
        args, kwargs = run.call_args
        self.assertEqual(args[-2:], ("B7", 2029))
        self.assertIs(kwargs["dynamic_transform_factory"], dote_numeric_control.ZeroNumericDote)
        self.assertIs(kwargs["tail_factory"], controller.UpperQuantileTail)
        self.assertEqual(kwargs["pair_reference"], Path(private["real"]))
        self.assertEqual((kwargs["lambda_q"], kwargs["quantile_profile"], kwargs["schedule_profile"]), (1.0, "UNIFORM", COSINE9))
        self.assertEqual(kwargs["started"], 10.0)

    def test_summary_direction_relative_values_and_no_screen_gate(self):
        report, tail = summaries()
        real_report = copy.deepcopy(report)
        real_report["groups"]["all"]["summary"]["conditional_pinball"] = 0.8
        def metadata(path):
            if "tail" in path.name:
                return copy.deepcopy(tail)
            return copy.deepcopy(real_report if path.parent.name == "REAL" else report)
        with patch.object(controller, "read", side_effect=metadata):
            result = controller.descriptive_comparison(Path("REAL"), Path("ZERO"))
        self.assertAlmostEqual(result["real_minus_zero"]["all_log_pinball"], -0.2)
        self.assertAlmostEqual(result["relative_to_zero_percent"]["all_log_pinball"], -20.0)
        self.assertEqual(len(result["six_group_real_minus_zero"]), 6)
        self.assertNotIn("screen_passed", result)
        self.assertEqual(result["scientific_acceptance"], "NOT_VERIFIED")

    def test_summary_rejects_population_mask_and_strata_mismatch(self):
        for mismatch in ("population", "source", "wet", "strata", "scale"):
            report, tail = summaries()
            real_report, real_tail = copy.deepcopy(report), copy.deepcopy(tail)
            if mismatch == "population":
                real_report["population_ids_sha256"] = "DIFFERENT"
            elif mismatch == "source":
                real_report["groups"]["all"]["source_sha"] = "DIFFERENT"
            elif mismatch == "wet":
                real_report["groups"]["all"]["summary"]["n_rain"] += 1
            elif mismatch == "strata":
                real_tail["strata"][0]["n_rain"] += 1
            else:
                real_tail["physical_pinball"]["scale_mm_h"] = 1.0
            def metadata(path):
                selected = (real_report, real_tail) if path.parent.name == "REAL" else (report, tail)
                return selected[1] if "tail" in path.name else selected[0]
            with self.subTest(mismatch=mismatch), patch.object(controller, "read", side_effect=metadata), self.assertRaises(ValueError):
                controller.descriptive_comparison(Path("REAL"), Path("ZERO"))

    def test_consumed_output_refuses_without_worker_launch(self):
        private = {"output_root": "SYNTHETIC_EXISTS"}
        with patch.object(controller, "checked", return_value=(proposal(), private, {}, {})), \
                patch.object(Path, "exists", return_value=True), \
                patch.object(controller.subprocess, "Popen") as launch, self.assertRaises(PermissionError):
            controller.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
        launch.assert_not_called()

    def test_controller_success_failure_and_timeout_never_retry(self):
        valid = {"status": "COMPLETE_TRAIN_AND_DEV_EVALUATION", "code_commit": "SYNTHETIC",
                 "optimizer_updates": 4320, "replay": 0, "schedule": schedule_identity(),
                 "total_logical_source_bytes": 477571953840, "total_logical_source_files": 142813}
        for outcome in ("success", "worker_failure", "timeout", "wrong_closure"):
            p, private = proposal(), {"output_root": "SYNTHETIC_NEW", "real": "SYNTHETIC_REAL"}
            result = dict(valid, optimizer_updates=4319) if outcome == "wrong_closure" else valid
            with self.subTest(outcome=outcome), ExitStack() as stack:
                stack.enter_context(patch.object(controller, "checked", return_value=(p, private, {}, {"roles": {"all": {"files": {"SYNTHETIC": {}}}}})))
                stack.enter_context(patch.object(Path, "exists", return_value=False))
                stack.enter_context(patch.object(Path, "is_dir", return_value=True))
                stack.enter_context(patch.object(Path, "mkdir"))
                stack.enter_context(patch.object(Path, "open", mock_open()))
                stack.enter_context(patch.object(controller.shutil, "disk_usage", return_value=SimpleNamespace(free=24 * 1024**3)))
                stack.enter_context(patch.object(controller.time, "monotonic", return_value=0))
                stack.enter_context(patch.object(controller, "resources", return_value={"cuda_name": "SYNTHETIC", "cuda_total_bytes": 1}))
                stack.enter_context(patch.object(controller, "read", return_value=result))
                write = stack.enter_context(patch.object(controller, "write"))
                verify = stack.enter_context(patch.object(controller, "verify_schedule_receipts"))
                compare = stack.enter_context(patch.object(controller, "descriptive_comparison", return_value={"synthetic": True}))
                launch = stack.enter_context(patch.object(controller.subprocess, "Popen"))
                child = launch.return_value
                child.wait.return_value = 1 if outcome == "worker_failure" else 0
                if outcome == "timeout":
                    child.wait.side_effect = [controller.subprocess.TimeoutExpired("SYNTHETIC", 21600), 0]
                if outcome == "success":
                    controller.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
                    verify.assert_called_once()
                    compare.assert_called_once()
                    self.assertEqual(write.call_args.args[0].name, "completion.json")
                else:
                    with self.assertRaises(RuntimeError):
                        controller.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
                    compare.assert_not_called()
                    self.assertEqual(write.call_args.args[0].name, "failure.json")
                launch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
