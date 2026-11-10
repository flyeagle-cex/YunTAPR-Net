"""CPU-only schedule and mocked wiring checks, without data or optimizer steps."""

import ast
import copy
from contextlib import ExitStack
import inspect
from pathlib import Path
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, mock_open, patch

from tools.research_readiness import start_independent_process as launcher
from yuntapr.experimental.core_innovation.stage4 import engine
from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.schedule import (
    COSINE9, ORIGINAL_50, schedule_identity, scheduled_lr,
)
from yuntapr.experimental.phase_b_v2_ablations.upper_quantile import MILD_PROFILE
from yuntapr.experimental.research_readiness import dynamic_training as tasks
from yuntapr.experimental.research_readiness import cosine9_training as controller
from yuntapr.experimental.research_readiness import upper_quantile_training as upper_quantile_controller
from yuntapr.training.phase_a_protocol import lr_for_update


def cosine9_proposal():
    return {
        "tasks": copy.deepcopy(controller.TASKS),
        "protocol": {
            "models": ["B7"], "loss": "E0", "lambda_q": 1.0, "seed": 2029,
            "epochs": 9, "endpoint": "FIXED_EPOCH_9", "quantile_profile": "UNIFORM",
            "schedule_profile": COSINE9,
        },
        "scientific_choices": {
            "candidate_schedule": schedule_identity(), "evaluation": controller.evaluation_contract(),
            "control_reuse": {
                "code_commit": "SYNTHETIC_CONTROL",
                "hardware_binding": {"cuda_name": "SYNTHETIC_GPU", "cuda_total_bytes": 1},
            },
        },
        "budget": {
            "models": 1, "updates_per_model": 4320, "total_updates": 4320,
            "source_bytes_per_model": 477571953840, "total_source_bytes": 477571953840,
            "source_files_per_model": 142813, "total_source_files": 142813,
            "max_model_seconds": 21600, "max_package_seconds": 21600,
            "initial_free_bytes": 24 * 1024**3, "minimum_task_free_bytes": 24 * 1024**3,
            "replay_allowance": 0, "additional_retry_allowance": 0, "checkpoint_loads": 0,
        },
        "runtime_binding": {"python_executable_sha256": "SYNTHETIC_RUNTIME"},
    }


class Cosine9ScheduleTests(unittest.TestCase):
    def test_original_profile_matches_every_update_of_the_historical_horizon(self):
        for steps in (7, 480):
            with self.subTest(steps_per_epoch=steps):
                expected = [lr_for_update(update, steps_per_epoch=steps)
                            for update in range(1, 50 * steps + 1)]
                self.assertEqual(
                    [scheduled_lr(update, steps_per_epoch=steps)
                     for update in range(1, 50 * steps + 1)], expected,
                )
                self.assertEqual(
                    [scheduled_lr(update, steps_per_epoch=steps, profile=ORIGINAL_50)
                     for update in range(1, 50 * steps + 1)], expected,
                )

    def test_nine_epoch_warmup_midpoint_endpoint_and_monotonicity(self):
        values = [scheduled_lr(update, profile=COSINE9) for update in range(1, 4321)]
        self.assertEqual(values[0], 1e-4 / 480)
        self.assertEqual(values[239], 5e-5)
        self.assertEqual(values[479], 1e-4)
        self.assertAlmostEqual(values[2399], 5.05e-5, places=18)
        self.assertEqual(values[-1], 1e-6)
        self.assertTrue(all(left < right for left, right in zip(values[:479], values[1:480])))
        self.assertTrue(all(left > right for left, right in zip(values[479:-1], values[480:])))
        self.assertEqual(values[:480], [lr_for_update(update, steps_per_epoch=480)
                                      for update in range(1, 481)])
        self.assertGreater(lr_for_update(4320, steps_per_epoch=480), 9e-5)

    def test_schedule_identity_is_exact_and_returns_independent_metadata(self):
        expected = {
            "profile": COSINE9, "horizon_epochs": 9, "warmup_epochs": 1,
            "peak_lr": 1e-4, "minimum_lr": 1e-6, "steps_per_epoch": 480,
            "total_updates": 4320, "update_index": "ONE_BASED_LR_SET_BEFORE_OPTIMIZER_STEP",
        }
        self.assertEqual(schedule_identity(), expected)
        changed = schedule_identity()
        changed["total_updates"] = 1
        self.assertEqual(schedule_identity(), expected)

    def test_invalid_updates_steps_and_unknown_profiles_are_rejected(self):
        for update in (True, False, None, "1", 1.0, -1, 0, 4321, float("nan")):
            with self.subTest(update=update), self.assertRaises(ValueError):
                scheduled_lr(update, profile=COSINE9)
        for steps in (True, False, None, "480", 480.0, -1, 0, 479, 481):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                scheduled_lr(1, steps_per_epoch=steps, profile=COSINE9)
        for profile in (None, "UNKNOWN", "cosine9", True, 9):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                scheduled_lr(1, profile=profile)

    def test_original_profile_preserves_historical_argument_rejection(self):
        for update, steps in ((True, 480), (1.0, 480), (0, 480), (24001, 480),
                              (1, True), (1, 0), (1, 480.0)):
            with self.subTest(update=update, steps=steps):
                with self.assertRaises(ValueError):
                    lr_for_update(update, steps_per_epoch=steps)
                with self.assertRaises(ValueError):
                    scheduled_lr(update, steps_per_epoch=steps, profile=ORIGINAL_50)


class Cosine9ScopeTests(unittest.TestCase):
    def test_executor_accepts_only_single_origin_b7_e0_seed2029_uniform(self):
        accepted = engine.PairedExecutor(
            None, "SYNTHETIC", kinds=("B7",), decision=SimpleNamespace(seed=2029),
            schedule_profile=COSINE9, origin_reference={},
        )
        self.assertTrue(accepted.modified_schedule)
        self.assertFalse(accepted.modified_loss)
        self.assertEqual(accepted.loss_config, get_config("E0"))
        self.assertEqual(accepted.quantile_profile, "UNIFORM")
        rejected = [
            {"kinds": ("B8",)}, {"kinds": ("B3", "B4")}, {"kinds": ("B7", "B8")},
            {"decision": SimpleNamespace(seed=2030)}, {"decision": None},
            {"lambda_q": 2}, {"quantile_profile": MILD_PROFILE},
            {"quantile_profile": "UNKNOWN"}, {"recovery": object()},
            {"schedule_profile": "UNKNOWN"},
        ]
        for changed in rejected:
            arguments = dict(kinds=("B7",), decision=SimpleNamespace(seed=2029),
                             schedule_profile=COSINE9, origin_reference={})
            arguments.update(changed)
            with self.subTest(changed=changed), self.assertRaises(PermissionError):
                engine.PairedExecutor(None, "SYNTHETIC", **arguments)

    def test_missing_origin_is_rejected_before_resources_output_or_optimizer(self):
        decision = engine.FormalDecision("SYNTHETIC", 2029, engine.POPULATION_SHA, True, True, True)
        for reference in (None, [], "SYNTHETIC"):
            executor = engine.PairedExecutor(
                None, "SYNTHETIC", decision=decision, kinds=("B7",),
                model_factory=MagicMock(), schedule_profile=COSINE9, origin_reference=reference,
            )
            with self.subTest(reference=reference), ExitStack() as stack:
                admission = stack.enter_context(patch.object(engine, "resources"))
                mkdir = stack.enter_context(patch.object(Path, "mkdir"))
                optimizer = stack.enter_context(patch.object(engine, "new_adamw"))
                save = stack.enter_context(patch.object(engine.torch, "save"))
                readers = MagicMock()
                with self.assertRaisesRegex(PermissionError, "origin reference"):
                    executor.run(readers)
                for boundary in (admission, mkdir, optimizer, save, readers, executor.model_factory):
                    boundary.assert_not_called()

    def test_origin_full_state_and_each_of_nine_orders_are_guarded(self):
        orders = {epoch: (f"SYNTHETIC_{epoch}_A", f"SYNTHETIC_{epoch}_B")
                  for epoch in range(1, 10)}
        reference = {
            "original_model_state_sha256": "SYNTHETIC_ORIGIN",
            "epoch_order_sha256": [engine.digest(orders[epoch]) for epoch in range(1, 10)],
        }
        executor = engine.PairedExecutor(
            None, "SYNTHETIC", kinds=("B7",), decision=SimpleNamespace(seed=2029),
            schedule_profile=COSINE9, origin_reference=reference,
        )
        identity = {"B7": {"full_state_sha256": "SYNTHETIC_ORIGIN"}}
        executor.check_origin_pair(identity, orders)
        with self.assertRaisesRegex(RuntimeError, "initialization or epoch order"):
            executor.check_origin_pair({"B7": {"full_state_sha256": "DIFFERENT"}}, orders)
        for epoch in range(1, 10):
            changed = dict(orders)
            changed[epoch] = tuple(reversed(changed[epoch]))
            with self.subTest(epoch=epoch), self.assertRaisesRegex(RuntimeError, "initialization or epoch order"):
                executor.check_origin_pair(identity, changed)

    def test_original_uniform_e0_does_not_add_an_origin_requirement(self):
        executor = engine.PairedExecutor(None, "SYNTHETIC", kinds=("B7",),
                                         decision=SimpleNamespace(seed=2029))
        self.assertFalse(executor.modified_schedule)
        executor.check_origin_pair({}, {})

    def test_dynamic_scope_mismatch_rejects_before_sqlite_or_payload_boundaries(self):
        cases = [
            ({}, "B7", 2029, 1, "UNIFORM", COSINE9),
            ({"schedule_profile": COSINE9}, "B7", 2029, 1, "UNIFORM", ORIGINAL_50),
            ({"schedule_profile": ORIGINAL_50}, "B7", 2029, 1, "UNIFORM", COSINE9),
            ({"schedule_profile": COSINE9}, "B8", 2029, 1, "UNIFORM", COSINE9),
            ({"schedule_profile": COSINE9}, "B7", 2030, 1, "UNIFORM", COSINE9),
            ({"loss": "E2", "lambda_q": 2, "schedule_profile": COSINE9},
             "B7", 2029, 2, "UNIFORM", COSINE9),
            ({"quantile_profile": MILD_PROFILE, "schedule_profile": COSINE9},
             "B7", 2029, 1, MILD_PROFILE, COSINE9),
            ({"schedule_profile": "UNKNOWN"}, "B7", 2029, 1, "UNIFORM", "UNKNOWN"),
        ]
        with ExitStack() as stack:
            boundaries = [stack.enter_context(patch.object(tasks.sqlite3, "connect")),
                          stack.enter_context(patch.object(tasks, "SourceMeter")),
                          stack.enter_context(patch.object(tasks, "read")),
                          stack.enter_context(patch.object(tasks, "PopulationPlan")),
                          stack.enter_context(patch.object(tasks, "ReaderFactory"))]
            for protocol, kind, seed, weight, quantile, schedule in cases:
                with self.subTest(protocol=protocol, kind=kind, seed=seed), self.assertRaises(PermissionError):
                    tasks.run_task(
                        Path("SYNTHETIC"), {"protocol": protocol}, {}, {}, {}, "SYNTHETIC", kind, seed,
                        started=0, pair_reference=None, static_name="SYNTHETIC", lambda_q=weight,
                        quantile_profile=quantile, schedule_profile=schedule,
                    )
            for boundary in boundaries:
                boundary.assert_not_called()

    def test_mocked_task_passes_schedule_origin_and_e0_to_real_executor(self):
        population = {"population_sha256": engine.POPULATION_SHA}
        origin = {"original_model_state_sha256": "SYNTHETIC", "epoch_order_sha256": []}
        proposal = {
            "protocol": {"loss": "E0", "lambda_q": 1, "schedule_profile": COSINE9},
            "data": population, "budget": {"minimum_task_free_bytes": 0, "max_model_seconds": 1},
            "static_source_sha256": {"B7": "SYNTHETIC"},
            "scientific_choices": {
                "DOTE": {"pwat_reference_kg_m2": 1, "reference_provenance": "SYNTHETIC"},
                "modulation_limit": 0.1, "origin_reference": {"B7": origin},
            },
        }
        observed = []

        def synthetic_run(executor, readers):
            observed.append(executor)

        with ExitStack() as stack:
            stack.enter_context(patch.dict(tasks.os.environ, {"PYTHONHASHSEED": "2029"}))
            stack.enter_context(patch.object(tasks.sqlite3, "connect"))
            stack.enter_context(patch.object(tasks.shutil, "disk_usage", return_value=SimpleNamespace(free=1)))
            stack.enter_context(patch.object(tasks.time, "monotonic", return_value=0))
            stack.enter_context(patch.object(tasks, "SourceMeter"))
            stack.enter_context(patch.object(tasks, "unpack", return_value=object()))
            stack.enter_context(patch.object(tasks, "read", return_value={"scalers": "SYNTHETIC"}))
            stack.enter_context(patch.object(tasks, "PopulationPlan", return_value=SimpleNamespace(identity=population, strong_scene_ids=())))
            stack.enter_context(patch.object(tasks, "model_factory", return_value=object()))
            stack.enter_context(patch.object(tasks, "ReaderFactory"))
            write = stack.enter_context(patch.object(tasks, "write"))
            stack.enter_context(patch.object(tasks, "endpoint", return_value={"logical_source_bytes": 0, "logical_source_files": 0}))
            stack.enter_context(patch.object(engine.PairedExecutor, "run", autospec=True, side_effect=synthetic_run))
            result = tasks.run_task(
                Path("SYNTHETIC"), proposal, {"output_root": "SYNTHETIC", "terrain": "SYNTHETIC"},
                {"decision_id": "SYNTHETIC"}, {"private_inputs": {"stage3_run": "SYNTHETIC", "request": "SYNTHETIC"}},
                "SYNTHETIC", "B7", 2029, started=0, pair_reference=None, static_name="SYNTHETIC",
                dynamic_transform_factory=MagicMock(), schedule_profile=COSINE9,
            )
        self.assertEqual(len(observed), 1)
        executor = observed[0]
        self.assertEqual(executor.schedule_profile, COSINE9)
        self.assertEqual(executor.origin_reference, origin)
        self.assertEqual(executor.loss_config, get_config("E0"))
        self.assertEqual(executor.quantile_profile, "UNIFORM")
        self.assertEqual(result["schedule"], schedule_identity())
        self.assertEqual(write.call_args.args[0], Path("SYNTHETIC") / "B7_s2029" / "completion.json")
        self.assertEqual(write.call_args.args[1]["schedule"], schedule_identity())


class Cosine9EngineCodeChainTests(unittest.TestCase):
    def test_real_loop_selects_lr_profile_before_optimizer_step_and_checks_origin_first(self):
        tree = ast.parse(textwrap.dedent(inspect.getsource(engine.PairedExecutor.run)))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        schedule_calls = [node for node in calls if isinstance(node.func, ast.Name)
                          and node.func.id == "scheduled_lr"]
        self.assertEqual(len(schedule_calls), 2)
        for call in schedule_calls:
            profile = next(keyword.value for keyword in call.keywords if keyword.arg == "profile")
            self.assertEqual(ast.unparse(profile), "self.schedule_profile")
        update_lr = next(call for call in schedule_calls if ast.unparse(call.args[0]) == "u + 1")
        self.assertEqual(ast.unparse(next(keyword.value for keyword in update_lr.keywords
                                         if keyword.arg == "steps_per_epoch")), "STEPS")
        optimizer_step = next(call for call in calls if ast.unparse(call.func) == "optimizer.step")
        optimizer_creation = next(call for call in calls if ast.unparse(call.func) == "new_adamw")
        origin_check = next(call for call in calls if ast.unparse(call.func) == "self.check_origin_pair")
        self.assertLess(update_lr.lineno, optimizer_step.lineno)
        self.assertLess(origin_check.lineno, optimizer_creation.lineno)

    def test_actual_metadata_branches_bind_training_checkpoint_and_receipt(self):
        tree = ast.parse(textwrap.dedent(inspect.getsource(engine.PairedExecutor.run)))
        blocks = sorted([node for node in ast.walk(tree) if isinstance(node, ast.If)
                         and ast.unparse(node.test) == "self.modified_schedule"], key=lambda node: node.lineno)
        self.assertEqual(len(blocks), 4)
        # Execute only the four metadata branches, never the training loop.
        fragment = compile(ast.Module(body=copy.deepcopy(blocks), type_ignores=[]), "<synthetic_schedule_metadata>", "exec")
        for modified in (False, True):
            with self.subTest(modified=modified):
                origin = {"original_model_state_sha256": "SYNTHETIC"}
                legacy_scheduler = {"completed": 4320, "steps_per_epoch": 480, "original_horizon": 24000}
                namespace = {
                    "__builtins__": {"dict": dict}, "schedule_identity": schedule_identity, "scheduled_lr": scheduled_lr,
                    "self": SimpleNamespace(modified_schedule=modified, origin_reference=origin,
                                            schedule_profile=COSINE9 if modified else ORIGINAL_50),
                    "identity": {}, "training": {}, "payload": {"identity": {}, "scheduler": dict(legacy_scheduler)},
                    "receipt": {}, "u": 4320, "STEPS": 480, "epoch": 9, "lr": 1e-6,
                }
                exec(fragment, namespace)
                if modified:
                    for name in ("identity", "training", "receipt"):
                        self.assertEqual(namespace[name]["schedule"], schedule_identity())
                    self.assertEqual(namespace["identity"]["origin_reference"], origin)
                    self.assertEqual(namespace["payload"]["identity"], {"schedule": schedule_identity(), "origin_reference": origin})
                    self.assertEqual(namespace["payload"]["scheduler"], {
                        "completed": 4320, "steps_per_epoch": 480, "horizon": 4320, "profile": COSINE9,
                    })
                    self.assertEqual(namespace["training"]["first_lr"], scheduled_lr(3841, profile=COSINE9))
                    self.assertEqual(namespace["training"]["last_lr"], 1e-6)
                else:
                    self.assertEqual(namespace["identity"], {})
                    self.assertEqual(namespace["training"], {})
                    self.assertEqual(namespace["receipt"], {})
                    self.assertEqual(namespace["payload"], {"identity": {}, "scheduler": legacy_scheduler})


class Cosine9ControllerTests(unittest.TestCase):
    def test_missing_approval_blocks_all_metadata_admission_and_launch_boundaries(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(Path, "is_file", return_value=False))
            boundaries = [stack.enter_context(patch.object(controller, name))
                          for name in ("read", "code_hashes", "runtime_binding", "load_inherited",
                                       "control_binding", "resources", "run_task", "write")]
            launch = stack.enter_context(patch.object(controller.subprocess, "Popen"))
            with self.assertRaisesRegex(PermissionError, "approval"):
                controller.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
            for boundary in boundaries + [launch]:
                boundary.assert_not_called()

    def test_closed_scope_rejects_changed_model_seed_loss_quantiles_and_horizon(self):
        controller.validate_scope(cosine9_proposal())
        changes = [
            ("task", "model", "B8"), ("task", "seed", 2030),
            ("task", "schedule_profile", ORIGINAL_50),
            ("protocol", "loss", "E1"), ("protocol", "loss", "E2"),
            ("protocol", "lambda_q", 2), ("protocol", "seed", 2030),
            ("protocol", "quantile_profile", MILD_PROFILE),
            ("protocol", "schedule_profile", ORIGINAL_50), ("protocol", "epochs", 50),
            ("protocol", "endpoint", "BEST"), ("candidate_schedule", "horizon_epochs", 50),
            ("candidate_schedule", "warmup_epochs", 2), ("candidate_schedule", "total_updates", 4800),
        ]
        for section, key, value in changes:
            proposal = cosine9_proposal()
            if section == "task":
                proposal["tasks"][0][key] = value
            elif section == "candidate_schedule":
                proposal["scientific_choices"][section][key] = value
            else:
                proposal[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(PermissionError):
                controller.validate_scope(proposal)

    def test_launcher_requires_each_exact_single_model_budget_field_and_runtime(self):
        proposal = cosine9_proposal()
        with patch.object(launcher, "sha", return_value="SYNTHETIC_RUNTIME"):
            launcher.validate_cosine9_scope(proposal, Path("SYNTHETIC"))
            for key, value in proposal["budget"].items():
                changed = copy.deepcopy(proposal)
                changed["budget"][key] = value + 1
                with self.subTest(key=key), self.assertRaises(PermissionError):
                    launcher.validate_cosine9_scope(changed, Path("SYNTHETIC"))
            changed = copy.deepcopy(proposal)
            changed["tasks"].append(copy.deepcopy(changed["tasks"][0]))
            with self.assertRaises(PermissionError):
                launcher.validate_cosine9_scope(changed, Path("SYNTHETIC"))
        with patch.object(launcher, "sha", return_value="DIFFERENT"), self.assertRaises(PermissionError):
            launcher.validate_cosine9_scope(proposal, Path("SYNTHETIC"))

    def test_launcher_source_preflight_fails_before_launch_claim_or_process_creation(self):
        namespace = launcher.PRIVATE / "SYNTHETIC_COSINE9_AGENT"
        specification = namespace / "spec.json"
        proposal = cosine9_proposal()
        proposal["proposal_sha256"] = "SYNTHETIC_DIGEST"
        private = {"output_root": str(namespace / "output"), "inherited": str(namespace / "inherited.json")}
        approval = {
            "approved_by_researcher": True, "decision_id": "SYNTHETIC", "code_commit": "SYNTHETIC",
            "output_root": private["output_root"],
            **{key: proposal[key] for key in ("proposal_sha256", "tasks", "budget", "scientific_choices")},
        }
        spec = {
            "kind": "APPROVAL_BOUND_EXECUTION", "service_dir": str(namespace / "service"),
            "cwd": str(launcher.ROOT),
            "command": [str(namespace / "python.exe"), "-B", str(launcher.ROOT / controller.ENTRY), "execute",
                        "--proposal", str(namespace / "proposal.json"),
                        "--private-preparation", str(namespace / "private.json"),
                        "--researcher-approval", str(namespace / "approval.json")],
        }
        for missing in ("empty_volumes", "volume", "root"):
            frozen = {"roles": {} if missing == "empty_volumes" else {"Train": {"files": [r"H:\SYNTHETIC\source.bin"]}}}
            records = {specification: spec, namespace / "proposal.json": proposal,
                       namespace / "private.json": private, namespace / "approval.json": approval,
                       namespace / "inherited.json": {"prepared": frozen}}

            def directory_exists(path):
                if missing == "volume" and path == Path("H:/"):
                    return False
                if missing == "root" and path == Path("H:/葵花202303_202510"):
                    return False
                return True

            with self.subTest(missing=missing), ExitStack() as stack:
                stack.enter_context(patch.object(launcher, "read", side_effect=lambda path: records[Path(path)]))
                stack.enter_context(patch.object(launcher, "sha", return_value="SYNTHETIC_RUNTIME"))
                stack.enter_context(patch.object(Path, "is_file", return_value=True))
                stack.enter_context(patch.object(Path, "is_dir", autospec=True, side_effect=directory_exists))
                stack.enter_context(patch.object(Path, "exists", return_value=False))
                stack.enter_context(patch.object(Path, "open", side_effect=AssertionError("No payload reads")))
                write = stack.enter_context(patch.object(launcher, "write"))
                create = stack.enter_context(patch.object(launcher.subprocess, "run"))
                git = stack.enter_context(patch.object(launcher.subprocess, "check_output"))
                with self.assertRaisesRegex(RuntimeError, "no launch claim or target created"):
                    launcher.spawn(specification)
                write.assert_not_called()
                create.assert_not_called()
                git.assert_not_called()

    def test_gpu_mismatch_rejects_before_output_claim_or_worker(self):
        proposal = cosine9_proposal()
        for key, value in (("cuda_name", "DIFFERENT_GPU"), ("cuda_total_bytes", 2)):
            admission = {"cuda_name": "SYNTHETIC_GPU", "cuda_total_bytes": 1}
            admission[key] = value
            with self.subTest(key=key), ExitStack() as stack:
                stack.enter_context(patch.object(controller, "checked", return_value=(proposal, {"output_root": "SYNTHETIC"}, {}, {"roles": {}})))
                stack.enter_context(patch.object(Path, "exists", return_value=False))
                stack.enter_context(patch.object(controller.shutil, "disk_usage", return_value=SimpleNamespace(free=24 * 1024**3)))
                stack.enter_context(patch.object(controller, "resources", return_value=admission))
                mkdir = stack.enter_context(patch.object(Path, "mkdir"))
                write = stack.enter_context(patch.object(controller, "write"))
                launch = stack.enter_context(patch.object(controller.subprocess, "Popen"))
                with self.assertRaisesRegex(ValueError, "GPU identity differs"):
                    controller.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
                for boundary in (mkdir, write, launch):
                    boundary.assert_not_called()

    def test_worker_passes_control_origin_uniform_e0_schedule_and_physical_tail(self):
        proposal = cosine9_proposal()
        origin = {"original_model_state_sha256": "SYNTHETIC_ORIGIN", "epoch_order_sha256": []}
        proposal["scientific_choices"]["origin_reference"] = {"B7": origin}
        private = {"output_root": "SYNTHETIC_PACKAGE", "control": "SYNTHETIC_CONTROL"}
        approval, prepared = {"decision_id": "SYNTHETIC"}, {"data": "SYNTHETIC"}

        def metadata(path):
            if path.name == "authorization_binding.json":
                return {"controller_pid": controller.os.getppid(), "approval": approval}
            self.assertEqual(path.name, "task_1_claim.json")
            return {"index": 0, "controller_pid": controller.os.getppid(), "code_commit": "SYNTHETIC"}

        with patch.object(controller, "checked", return_value=(proposal, private, approval, prepared)), \
                patch.object(controller, "read", side_effect=metadata), \
                patch.object(controller, "run_task", return_value={"synthetic": True}) as run:
            self.assertEqual(controller.worker(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC"), {"synthetic": True})
        args, kwargs = run.call_args
        self.assertEqual(args[1]["scientific_choices"]["origin_reference"]["B7"], origin)
        self.assertEqual(args[-2:], ("B7", 2029))
        self.assertEqual(kwargs["pair_reference"], Path(private["control"]))
        self.assertEqual(kwargs["schedule_profile"], COSINE9)
        self.assertEqual(kwargs["quantile_profile"], "UNIFORM")
        self.assertEqual(kwargs["lambda_q"], 1.0)
        self.assertIs(kwargs["tail_factory"], controller.UpperQuantileTail)

    def test_every_epoch_schedule_and_boundary_lr_are_verified(self):
        def metadata(path):
            epoch = int(path.name.split("_")[-1].split(".")[0])
            if "_train_" in path.name:
                return {"loss_arm": "E0", "schedule": schedule_identity(),
                        "first_lr": scheduled_lr((epoch - 1) * 480 + 1, profile=COSINE9),
                        "last_lr": scheduled_lr(epoch * 480, profile=COSINE9)}
            return {"schedule": schedule_identity()}

        with patch.object(controller, "read", side_effect=metadata) as read, \
                patch.object(upper_quantile_controller, "read", read):
            controller.verify_schedule_receipts(Path("SYNTHETIC"))
            self.assertEqual(read.call_count, 36)
        for epoch in range(1, 10):
            for field in ("first_lr", "last_lr", "training_schedule", "receipt_schedule"):
                def changed_metadata(path):
                    result = metadata(path)
                    selected = int(path.name.split("_")[-1].split(".")[0]) == epoch
                    training = "_train_" in path.name
                    if selected and training and field in ("first_lr", "last_lr"):
                        result[field] += 1e-12
                    elif selected and ((training and field == "training_schedule")
                                       or (not training and field == "receipt_schedule")):
                        result["schedule"]["profile"] = ORIGINAL_50
                    return result

                with self.subTest(epoch=epoch, field=field), \
                        patch.object(controller, "read", side_effect=changed_metadata) as read, \
                        patch.object(upper_quantile_controller, "read", read), \
                        self.assertRaisesRegex(ValueError, "schedule differs"):
                    controller.verify_schedule_receipts(Path("SYNTHETIC"))

    def test_controller_mocked_one_worker_closes_once_and_mismatches_stop_without_retry(self):
        valid_result = {
            "status": "COMPLETE_TRAIN_AND_DEV_EVALUATION", "code_commit": "SYNTHETIC",
            "optimizer_updates": 4320, "replay": 0, "total_logical_source_bytes": 477571953840,
            "total_logical_source_files": 142813, "schedule": schedule_identity(),
        }
        mismatches = [None, ("status", "INCOMPLETE"), ("code_commit", "DIFFERENT"),
                      ("optimizer_updates", 4319), ("replay", 1),
                      ("total_logical_source_bytes", 477571953841),
                      ("total_logical_source_files", 142814), ("schedule", {})]
        for changed in mismatches:
            result = copy.deepcopy(valid_result)
            if changed is not None:
                result[changed[0]] = changed[1]
            proposal = cosine9_proposal()
            private = {"output_root": "SYNTHETIC_PACKAGE", "control": "SYNTHETIC_CONTROL"}
            with self.subTest(changed=changed), ExitStack() as stack:
                stack.enter_context(patch.object(controller, "checked", return_value=(proposal, private, {}, {"roles": {}})))
                stack.enter_context(patch.object(Path, "exists", return_value=False))
                stack.enter_context(patch.object(Path, "mkdir"))
                stack.enter_context(patch.object(Path, "open", mock_open()))
                stack.enter_context(patch.object(controller.shutil, "disk_usage", return_value=SimpleNamespace(free=24 * 1024**3)))
                stack.enter_context(patch.object(controller.time, "monotonic", return_value=0))
                stack.enter_context(patch.object(controller, "resources", return_value={
                    "cuda_name": "SYNTHETIC_GPU", "cuda_total_bytes": 1,
                }))
                stack.enter_context(patch.object(controller, "worker_creation_flags", return_value=0))
                stack.enter_context(patch.object(controller, "read", return_value=result))
                write = stack.enter_context(patch.object(controller, "write"))
                verify = stack.enter_context(patch.object(controller, "verify_schedule_receipts"))
                summary = stack.enter_context(patch.object(controller, "pair_summary", return_value={"screen_passed": False}))
                launch = stack.enter_context(patch.object(controller.subprocess, "Popen"))
                launch.return_value.wait.return_value = 0
                if changed is None:
                    controller.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
                    verify.assert_called_once_with(Path(private["output_root"]) / "B7_s2029")
                    self.assertEqual(summary.call_args.kwargs["arm_folders"]["CONTROL_E0"], Path(private["control"]))
                    self.assertEqual(write.call_args.args[0].name, "completion.json")
                    self.assertEqual(write.call_args.args[1]["schedule"], schedule_identity())
                else:
                    with self.assertRaisesRegex(RuntimeError, "closure differs"):
                        controller.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
                    verify.assert_not_called()
                    summary.assert_not_called()
                    self.assertEqual(write.call_args.args[0].name, "failure.json")
                    self.assertEqual(write.call_args.args[1]["status"], "STOP_NO_AUTOMATIC_RETRY")
                launch.assert_called_once()
                command = launch.call_args.args[0]
                self.assertEqual(command[1], "-B")
                self.assertEqual(command[3], "worker")
                self.assertNotIn("--task-index", command)


if __name__ == "__main__":
    unittest.main()
