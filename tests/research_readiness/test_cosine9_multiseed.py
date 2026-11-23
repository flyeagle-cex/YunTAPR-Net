"""Synthetic four-task COSINE9 REAL/ZERO package checks; no payloads or training."""

import copy
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import mock_open, patch
import sys

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from yuntapr.experimental.phase_b_v2_ablations.schedule import COSINE9, schedule_identity
from yuntapr.experimental.research_readiness import cosine9_multiseed as controller
from yuntapr.experimental.research_readiness import dote_numeric_control
from yuntapr.experimental.research_readiness import dynamic_terrain

definition = importlib.util.spec_from_file_location(
    "independent_host", ROOT / "tools/research_readiness/start_independent_process.py")
launcher = importlib.util.module_from_spec(definition)
definition.loader.exec_module(launcher)


def caps():
    return controller.budget({"roles": {"all": {"bytes_per_pass": 53063515668, "file_count": 15868}}})


def origins():
    return {f"B7@{seed}": {"original_model_state_sha256": f"ORIGIN-{seed}",
                           "epoch_order_sha256": [f"ORDER-{seed}-{epoch}" for epoch in range(1, 10)]}
            for seed in (2030, 2031)}


def proposal():
    reference = origins()
    return {
        "kind": controller.KIND,
        "authorization_scope": controller.SCOPE,
        "authorized": False,
        "final_2025_access": False,
        "tasks": copy.deepcopy(controller.TASKS),
        "protocol": {"loss": "E0", "lambda_q": 1.0, "quantile_profile": "UNIFORM",
                     "schedule_profile": COSINE9, "epochs": 9, "updates_per_epoch": 480,
                     "updates_per_model": 4320, "total_updates": 17280, "paired_attempt_cap": 17280,
                     "replay_allowance": 0, "endpoint": "FIXED_EPOCH_9_LAST", "BEST_selection": False,
                     "seed_scope": "PER_TASK_2030_2031", "arms": ["REAL", "ZERO"], "models": ["B7"]},
        "scientific_choices": {
            "candidate_schedule": schedule_identity(),
            "dynamic_control": "ZERO_NUMERIC_RETAIN_REAL_MASKS",
            "real_masks_retained": True,
            "structurally_zero_loss_gradient_weights": 128,
            "origin_reference": dict({"B7": reference["B7@2030"]}, **reference),
        },
        "proposal_sha256": "SYNTHETIC",
        "budget": caps(),
        "runtime_binding": {"python_executable_sha256": "SYNTHETIC"},
        "execution_code_commit": None,
    }


def task_results():
    return [dict(arm=task["arm"], model="B7", seed=task["seed"],
                 status="COMPLETE_TRAIN_AND_DEV_EVALUATION", epochs=9,
                 updates=4320, source_bytes=477571953840, source_files=142813,
                 initial_full_state_sha256=f"ORIGIN-{task['seed']}",
                 epoch_order_sha256=list(origins()[f"B7@{task['seed']}"]["epoch_order_sha256"]),
                 folder=f"SYNTHETIC/{task['arm']}_s{task['seed']}")
            for task in controller.TASKS]


class Cosine9MultiseedTests(unittest.TestCase):
    def test_tasks_are_the_four_ordered_real_zero_seed_pairs(self):
        self.assertEqual([dict(task) for task in controller.TASKS], [
            {"arm": "REAL", "model": "B7", "seed": 2030, "schedule_profile": COSINE9},
            {"arm": "ZERO", "model": "B7", "seed": 2030, "schedule_profile": COSINE9},
            {"arm": "REAL", "model": "B7", "seed": 2031, "schedule_profile": COSINE9},
            {"arm": "ZERO", "model": "B7", "seed": 2031, "schedule_profile": COSINE9},
        ])
        for task in controller.TASKS:
            self.assertEqual(sorted(task), ["arm", "model", "schedule_profile", "seed"])
        self.assertEqual((controller.SEEDS, controller.ARMS), ((2030, 2031), ("REAL", "ZERO")))
        self.assertEqual(controller.KIND, "BOUNDED_TRAIN_COSINE9_MULTISEED_TERRAIN")

    def test_package_budget_is_four_single_task_envelopes(self):
        envelope = caps()
        self.assertEqual((envelope["models"], envelope["updates_per_model"], envelope["total_updates"]),
                         (4, 4320, 17280))
        self.assertEqual((envelope["source_bytes_per_model"], envelope["total_source_bytes"]),
                         (477571953840, 1910287815360))
        self.assertEqual((envelope["source_files_per_model"], envelope["total_source_files"]), (142813, 571252))
        self.assertEqual((envelope["max_model_seconds"], envelope["max_package_seconds"]), (21600, 86400))
        self.assertEqual((envelope["initial_free_bytes"], envelope["minimum_task_free_bytes"]),
                         (48 * 1024 ** 3, 24 * 1024 ** 3))
        self.assertEqual((envelope["replay_allowance"], envelope["additional_retry_allowance"],
                          envelope["checkpoint_loads"]), (0, 0, 0))
        for roles in ({"all": {"bytes_per_pass": 1, "file_count": 1}},
                      {"all": {"bytes_per_pass": 53063515668, "file_count": 15869}}):
            with self.subTest(roles=roles), self.assertRaises(ValueError):
                controller.budget({"roles": roles})

    def test_real_and_zero_of_one_seed_share_state_and_epoch_order(self):
        pairing = controller.pairing_summary(task_results())
        self.assertEqual(sorted(pairing), ["2030", "2031"])
        for seed in ("2030", "2031"):
            self.assertEqual(pairing[seed]["initial_full_state_sha256"], "ORIGIN-" + seed)
            self.assertEqual(len(pairing[seed]["epoch_order_sha256"]), 9)
            self.assertEqual(pairing[seed]["pairing"], "IDENTICAL_SEED_DRIVEN_ORIGINAL_STATE_AND_EPOCH_ORDER")
        changed = task_results()
        changed[1]["initial_full_state_sha256"] = "OTHER"
        with self.assertRaises(RuntimeError):
            controller.pairing_summary(changed)
        changed = task_results()
        changed[3]["epoch_order_sha256"][0] = "OTHER"
        with self.assertRaises(RuntimeError):
            controller.pairing_summary(changed)
        with self.assertRaises(RuntimeError):
            controller.pairing_summary(task_results()[:2])

    def test_scope_admits_only_the_exact_four_task_envelope(self):
        controller.validate_scope(proposal())
        for key, value in (("loss", "E2"), ("lambda_q", 2.0), ("quantile_profile", "UQ_MILD_V1"),
                           ("schedule_profile", "ORIGINAL_COSINE50"), ("epochs", 10),
                           ("endpoint", "FIXED_EPOCH_9"), ("seed_scope", "SEED_2029"),
                           ("total_updates", 4320), ("paired_attempt_cap", 8640), ("replay_allowance", 1)):
            changed = proposal()
            changed["protocol"][key] = value
            with self.subTest(key=key), self.assertRaises(PermissionError):
                controller.validate_scope(changed)
        for changed in (
            dict(proposal(), authorized=True),
            dict(proposal(), final_2025_access=True),
            dict(proposal(), kind="BOUNDED_TRAIN_COSINE9"),
            dict(proposal(), authorization_scope="SINGLE_TASK"),
            dict(proposal(), execution_code_commit="short"),
            dict(proposal(), tasks=copy.deepcopy(controller.TASKS[:2])),
            dict(proposal(), tasks=copy.deepcopy(controller.TASKS)[::-1]),
        ):
            with self.assertRaises(PermissionError):
                controller.validate_scope(changed)
        for mutate in (lambda p: p["scientific_choices"]["origin_reference"].pop("B7@2031"),
                       lambda p: p["scientific_choices"].__setitem__("dynamic_control", "REAL"),
                       lambda p: p["scientific_choices"].__setitem__("real_masks_retained", False),
                       lambda p: p["scientific_choices"].__setitem__("structurally_zero_loss_gradient_weights", 0),
                       lambda p: p["scientific_choices"].__setitem__("candidate_schedule", {}),
                       lambda p: p["scientific_choices"]["origin_reference"]["B7@2030"].__setitem__(
                           "epoch_order_sha256", ["ORDER"])):
            changed = proposal()
            mutate(changed)
            with self.assertRaises(PermissionError):
                controller.validate_scope(changed)
        missing_arm = proposal()
        missing_arm["tasks"] = [task for task in missing_arm["tasks"] if task["arm"] == "REAL"]
        with self.assertRaises(PermissionError):
            controller.validate_scope(missing_arm)

    def test_approval_must_match_the_private_seal_and_proposal(self):
        p = proposal()
        p["proposal_sha256"] = "SYNTHETIC_PROPOSAL"
        private = {"output_root": "SYNTHETIC_NEW"}
        approval = dict(approved_by_researcher=True, decision_id="SYNTHETIC", code_commit="SYNTHETIC",
                        proposal_sha256=p["proposal_sha256"], tasks=p["tasks"], budget=p["budget"],
                        scientific_choices=p["scientific_choices"], output_root=private["output_root"])
        controller.validate_approval(approval, p, private, "SYNTHETIC")
        for field in ("code_commit", "proposal_sha256", "tasks", "budget", "scientific_choices", "output_root"):
            with self.subTest(field=field), self.assertRaises(PermissionError):
                controller.validate_approval(dict(approval, **{field: "OLD_OR_CHANGED"}), p, private, "SYNTHETIC")
        with self.assertRaises(PermissionError):
            controller.validate_approval(dict(approval, decision_id=""), p, private, "SYNTHETIC")

    def test_private_seal_covers_every_field_but_the_proposal_pointer(self):
        private = dict(output_root="SYNTHETIC", real="SYNTHETIC_REAL", seeds=origins())
        seal = controller.private_seal(private)
        self.assertEqual(seal, controller.private_seal(dict(private, proposal_sha256="ANY")))
        self.assertNotEqual(seal, controller.private_seal(dict(private, real="OTHER")))
        self.assertEqual(len(seal), 64)

    def test_missing_approval_rejects_before_any_metadata_or_task(self):
        with patch.object(Path, "is_file", return_value=False), \
                patch.object(controller, "read") as read, \
                patch.object(controller, "run_task") as run, self.assertRaises(PermissionError):
            controller.checked(Path("SYNTHETIC"), "p", "v", "missing", "SYNTHETIC")
        read.assert_not_called()
        run.assert_not_called()

    def test_launcher_admits_and_rejects_the_four_task_scope(self):
        with patch.object(launcher, "sha", return_value="SYNTHETIC"):
            launcher.validate_cosine9_multiseed_scope(proposal(), Path("SYNTHETIC"))
            for changed in (dict(proposal(), kind="BOUNDED_TRAIN_COSINE9"),
                            dict(proposal(), authorization_scope="SINGLE_TASK"),
                            dict(proposal(), tasks=copy.deepcopy(controller.TASKS)[::-1]),
                            dict(proposal(), runtime_binding={"python_executable_sha256": "OTHER"})):
                with self.assertRaises(PermissionError):
                    launcher.validate_cosine9_multiseed_scope(changed, Path("SYNTHETIC"))
            for mutate in (lambda p: p["scientific_choices"]["origin_reference"].pop("B7@2030"),
                           lambda p: p["scientific_choices"].__setitem__("dynamic_control", "REAL"),
                           lambda p: p["scientific_choices"].__setitem__("real_masks_retained", False),
                           lambda p: p["scientific_choices"].__setitem__("structurally_zero_loss_gradient_weights", 1),
                           lambda p: p["protocol"].__setitem__("endpoint", "FIXED_EPOCH_9"),
                           lambda p: p["protocol"].__setitem__("seed_scope", "SEED_2029")):
                changed = proposal()
                mutate(changed)
                with self.assertRaises(PermissionError):
                    launcher.validate_cosine9_multiseed_scope(changed, Path("SYNTHETIC"))
            for key in caps():
                changed = proposal()
                changed["budget"][key] += 1
                with self.subTest(key=key), self.assertRaises(PermissionError):
                    launcher.validate_cosine9_multiseed_scope(changed, Path("SYNTHETIC"))

    def test_launcher_spec_accepts_the_clean_bound_checkout_and_rejects_a_dirty_one(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            service = root / "service"
            service.mkdir()
            relative = "tools/research_readiness/start_cosine9_multiseed.py"
            entry = root / relative
            entry.parent.mkdir(parents=True)
            entry.touch()
            runtime = root / "test_python.exe"
            runtime.touch()
            inherited = root / "inherited.json"
            inherited.write_text(json.dumps({"prepared": {"roles": {"Train": {"files": {"SYNTHETIC": {}}}}}}),
                                 encoding="utf-8")
            proposal_path, private_path, grant_path = (root / name for name in
                                                       ("proposal.json", "private.json", "grant.json"))
            configuration = root / "spec.json"
            p = proposal()
            p["runtime_binding"]["python_executable_sha256"] = launcher.sha(runtime)
            private = dict(proposal_sha256="SYNTHETIC", output_root=str(root / "output"),
                           service_dir=str(service), runtime_python=str(runtime),
                           inherited=str(inherited), seeds=origins())
            spec = dict(kind=controller.KIND, cwd=str(root), service_dir=str(service),
                        environment=dict(PYTHONHASHSEED="2030", PYTHONUTF8="1", OMP_NUM_THREADS="1",
                                         MKL_NUM_THREADS="1", CUBLAS_WORKSPACE_CONFIG=":4096:8"),
                        command=[str(runtime), "-B", str(entry), "execute",
                                 "--proposal", str(proposal_path),
                                 "--private-preparation", str(private_path),
                                 "--researcher-approval", str(grant_path)])
            launcher.write(configuration, spec)
            launcher.write(proposal_path, p)
            launcher.write(private_path, private)
            grant = dict(p, approved_by_researcher=True, decision_id="fixture",
                         code_commit="synthetic", output_root=private["output_root"])
            launcher.write(grant_path, grant)
            with patch.object(launcher, "PRIVATE", root), \
                    patch.object(Path, "is_dir", return_value=True), \
                    patch.object(launcher.subprocess, "check_output", side_effect=["synthetic", ""]):
                self.assertEqual(launcher.validate_spec(configuration), (spec, service))
                grant["authorization_scope"] = "SOME_OTHER_SCOPE"
                grant_path.write_text(json.dumps(grant), encoding="utf-8")
                with self.assertRaises(PermissionError):
                    launcher.validate_spec(configuration)
                grant["authorization_scope"] = p["authorization_scope"]
                grant["budget"] = dict(p["budget"], models=3)
                grant_path.write_text(json.dumps(grant), encoding="utf-8")
                with self.assertRaises(PermissionError):
                    launcher.validate_spec(configuration)

    def test_supervisor_uses_the_87000_second_package_timeout(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            service = Path(tmp)
            configuration = service / "spec.json"
            fixture = dict(kind=controller.KIND, command=["synthetic"], cwd=tmp)
            launcher.write(configuration, fixture)
            launcher.write(service / "independent_launch_claim.json", dict(spec_sha256=launcher.sha(configuration)))
            with patch.object(launcher, "validate_spec", return_value=(fixture, service)), \
                    patch.object(launcher, "host_identity",
                                 return_value=dict(in_any_job=False, package_status=15700)), \
                    patch.object(launcher.subprocess, "Popen") as popen:
                process = popen.return_value
                process.pid = 123
                process.wait.return_value = 0
                self.assertEqual(launcher.supervise(configuration), 0)
                process.wait.assert_called_once_with(timeout=87000)

    def test_execute_runs_four_tasks_serially_and_seals_the_completion(self):
        p, private, approval = proposal(), {"output_root": "SYNTHETIC_NEW"}, {}
        prepared = {"roles": {"Train": {"files": {"SYNTHETIC": {}}}}}
        spawn = []
        written = {}
        with ExitStack() as stack:
            stack.enter_context(patch.object(controller, "checked",
                                            return_value=(p, private, approval, prepared)))
            stack.enter_context(patch.object(Path, "exists", return_value=False))
            stack.enter_context(patch.object(Path, "is_dir", return_value=True))
            stack.enter_context(patch.object(Path, "mkdir"))
            stack.enter_context(patch.object(controller.shutil, "disk_usage",
                                             return_value=SimpleNamespace(free=48 * 1024 ** 3)))
            stack.enter_context(patch.object(controller.time, "monotonic", return_value=0))
            stack.enter_context(patch.object(controller, "resources", return_value={"scope": "SYNTHETIC"}))
            stack.enter_context(patch.object(controller, "read", return_value={"metadata_files": {"x": {}}}))
            stack.enter_context(patch.object(controller, "spawn_worker"))
            stack.enter_context(patch.object(controller, "task_completion", side_effect=task_results()))
            stack.enter_context(patch.object(controller, "write",
                                             side_effect=lambda path, value: written.__setitem__(Path(path).name, value)))
            completion = controller.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
        self.assertEqual(completion["status"], "COMPLETE_FOUR_TASK_COSINE9_REAL_ZERO_MULTISEED")
        self.assertEqual(completion["totals"], dict(tasks_completed=4, updates=17280,
                                                    source_bytes=1910287815360, source_files=571252))
        self.assertEqual(sorted(completion["pairing"]), ["2030", "2031"])
        self.assertEqual((completion["automatic_retry"], completion["replay"]), (False, False))
        self.assertEqual(completion["scientific_acceptance"], "NOT_VERIFIED")
        json.dumps(completion, allow_nan=False)
        self.assertEqual(written["completion.json"]["totals"]["updates"], 17280)
        self.assertEqual(written["authorization_binding.json"]["controller_pid"], controller.os.getpid())
        self.assertEqual(len(completion["tasks"]), 4)

    def test_first_failure_stops_every_later_task_and_writes_a_failure(self):
        p, private, approval = proposal(), {"output_root": "SYNTHETIC_NEW"}, {}
        prepared = {"roles": {"Train": {"files": {"SYNTHETIC": {}}}}}
        calls, written = [], {}
        results = task_results()
        def complete(folder, arm, seed, commit, envelope, origin):
            calls.append((arm, seed))
            if len(calls) == 2:
                raise RuntimeError("synthetic stop")
            return results[len(calls) - 1]
        with ExitStack() as stack:
            stack.enter_context(patch.object(controller, "checked",
                                            return_value=(p, private, approval, prepared)))
            stack.enter_context(patch.object(Path, "exists", return_value=False))
            stack.enter_context(patch.object(Path, "is_dir", return_value=True))
            stack.enter_context(patch.object(Path, "mkdir"))
            stack.enter_context(patch.object(controller.shutil, "disk_usage",
                                             return_value=SimpleNamespace(free=48 * 1024 ** 3)))
            stack.enter_context(patch.object(controller.time, "monotonic", return_value=0))
            stack.enter_context(patch.object(controller, "resources", return_value={"scope": "SYNTHETIC"}))
            stack.enter_context(patch.object(controller, "read", return_value={"metadata_files": {"x": {}}}))
            stack.enter_context(patch.object(controller, "spawn_worker"))
            stack.enter_context(patch.object(controller, "task_completion", side_effect=complete))
            stack.enter_context(patch.object(controller, "write",
                                             side_effect=lambda path, value: written.__setitem__(Path(path).name, value)))
            with self.assertRaises(RuntimeError):
                controller.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
        self.assertEqual(calls, [("REAL", 2030), ("ZERO", 2030)])
        self.assertNotIn("completion.json", written)
        self.assertEqual(written["failure.json"]["status"], "STOP_NO_AUTOMATIC_RETRY_OR_REPLAY")
        self.assertEqual((written["failure.json"]["completed_tasks"], written["failure.json"]["completed_updates"]),
                         (1, 4320))
        self.assertEqual((written["failure.json"]["automatic_retry"], written["failure.json"]["replay"]), (False, False))

    def test_dispatch_bound_its_worker_timeout_to_the_remaining_package_time(self):
        p, private = proposal(), {"output_root": "SYNTHETIC_NEW"}
        spawn, written = [], {}
        with ExitStack() as stack:
            stack.enter_context(patch.object(Path, "mkdir"))
            stack.enter_context(patch.object(controller.time, "monotonic", return_value=0))
            stack.enter_context(patch.object(controller, "task_completion", side_effect=task_results()))
            stack.enter_context(patch.object(controller, "write",
                                             side_effect=lambda path, value: written.__setitem__(Path(path).name, value)))
            stack.enter_context(patch.object(controller, "spawn_worker",
                                             side_effect=lambda *a, **k: spawn.append((a, k))))
            controller.dispatch(Path("SYNTHETIC"), p, private, {}, "SYNTHETIC", proposal_path="p",
                                private_path="v", approval_path="a")
        self.assertEqual(len(spawn), 4)
        for args, kwargs in spawn:
            self.assertEqual(args[3], 21600)
            self.assertEqual(kwargs["cwd"], Path("SYNTHETIC"))
            index = int(args[0][args[0].index("--task-index") + 1])
            self.assertEqual(args[1]["PYTHONHASHSEED"], str(controller.TASKS[index]["seed"]))
            self.assertEqual(args[1]["PYTHONHASHSEED"], str(controller.SEEDS[index // 2]))
        claimed = sorted(name for name in written if name.startswith("task_") and name.endswith("_claim.json"))
        self.assertEqual(len(claimed), 4)

    def test_worker_binds_both_claims_and_the_zero_pair_reference(self):
        p, private, approval = proposal(), {"output_root": "SYNTHETIC_NEW"}, {}
        def metadata(path):
            if path.name == "authorization_binding.json":
                return {"controller_pid": 123, "approval": approval}
            if path.name == "paired_initial_identity.json":
                return {"B7": {"full_state_sha256": "ORIGIN-2030"}}
            return {"index": 1, "arm": "ZERO", "model": "B7", "seed": 2030, "controller_pid": 123,
                    "code_commit": "SYNTHETIC", "started_monotonic": 10.0}
        with patch.object(controller, "checked", return_value=(p, private, approval, {})), \
                patch.object(controller, "read", side_effect=metadata), \
                patch.object(controller.os, "getppid", return_value=123), \
                patch.object(controller, "write") as write, \
                patch.object(controller, "run_task",
                             return_value=dict(status="COMPLETE_TRAIN_AND_DEV_EVALUATION",
                                               optimizer_updates=4320,
                                               total_logical_source_bytes=477571953840,
                                               total_logical_source_files=142813)) as run:
            controller.worker(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC", 1)
        args, kwargs = run.call_args
        self.assertEqual(args[-2:], ("B7", 2030))
        self.assertIs(kwargs["dynamic_transform_factory"], dote_numeric_control.ZeroNumericDote)
        self.assertEqual(kwargs["pair_reference"], Path("SYNTHETIC_NEW/REAL_s2030/B7_s2030"))
        self.assertEqual((kwargs["quantile_profile"], kwargs["lambda_q"], kwargs["schedule_profile"]),
                         ("UNIFORM", 1.0, COSINE9))
        self.assertEqual((kwargs["cosine9_seeds"], kwargs["started"]), (controller.SEEDS, 10.0))
        self.assertEqual(kwargs["origin_reference"], origins()["B7@2030"])
        self.assertEqual(kwargs["static_name"], "ZERO_static_source.sqlite")
        self.assertEqual(write.call_args.args[0].name, "task_receipt.json")
        with patch.object(controller, "checked") as checked:
            with self.assertRaises(PermissionError):
                controller.worker(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC", 4)
        checked.assert_not_called()

    def test_real_worker_has_no_pair_reference_and_uses_the_physical_dote(self):
        p, private, approval = proposal(), {"output_root": "SYNTHETIC_NEW"}, {}
        def metadata(path):
            if path.name == "authorization_binding.json":
                return {"controller_pid": 123, "approval": approval}
            if path.name == "paired_initial_identity.json":
                return {"B7": {"full_state_sha256": "ORIGIN-2031"}}
            return {"index": 2, "arm": "REAL", "model": "B7", "seed": 2031, "controller_pid": 123,
                    "code_commit": "SYNTHETIC", "started_monotonic": 20.0}
        with patch.object(controller, "checked", return_value=(p, private, approval, {})), \
                patch.object(controller, "read", side_effect=metadata), \
                patch.object(controller.os, "getppid", return_value=123), \
                patch.object(controller, "write"), \
                patch.object(controller, "run_task", return_value=dict(
                    status="COMPLETE_TRAIN_AND_DEV_EVALUATION", optimizer_updates=4320,
                    total_logical_source_bytes=477571953840, total_logical_source_files=142813)) as run:
            controller.worker(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC", 2)
        self.assertIsNone(run.call_args.kwargs["pair_reference"])
        self.assertIs(run.call_args.kwargs["dynamic_transform_factory"], dynamic_terrain.PhysicalDote)

    def test_success_path_refuses_a_consumed_output_without_a_worker(self):
        private = {"output_root": "SYNTHETIC_EXISTS"}
        with patch.object(controller, "checked", return_value=(proposal(), private, {}, {})), \
                patch.object(Path, "exists", return_value=True), \
                patch.object(controller.subprocess, "Popen") as launch, self.assertRaises(PermissionError):
            controller.execute(Path("SYNTHETIC"), "p", "v", "a", "SYNTHETIC")
        launch.assert_not_called()

    def test_completion_requires_the_budgeted_counts(self):
        envelope = caps()
        origin = origins()["B7@2030"]
        valid = {"status": "COMPLETE_TRAIN_AND_DEV_EVALUATION", "model": "B7", "seed": 2030, "epochs": 9,
                 "optimizer_updates": 4320, "replay": 0, "code_commit": "SYNTHETIC",
                 "endpoint": "FIXED_EPOCH_9_LAST", "schedule": schedule_identity(),
                 "total_logical_source_bytes": 477571953840, "total_logical_source_files": 142813}
        initial = {"B7": {"full_state_sha256": origin["original_model_state_sha256"]}}
        orders = {str(epoch): {"sha256": origin["epoch_order_sha256"][epoch - 1],
                               "ids": ["SYNTHETIC"]} for epoch in range(1, 10)}
        def metadata(path):
            if path.name == "completion.json":
                return dict(valid)
            if path.name == "paired_initial_identity.json":
                return initial
            if path.name == "paired_orders.json":
                return orders
            return {}
        with patch.object(controller, "read", side_effect=metadata), \
                patch.object(controller, "verify_schedule_receipts") as verify:
            result = controller.task_completion(Path("SYNTHETIC"), "REAL", 2030, "SYNTHETIC", envelope, origin)
        verify.assert_called_once()
        self.assertEqual((result["updates"], result["source_bytes"]), (4320, 477571953840))
        for path in ("completion", "initial", "orders"):
            def broken(name, selected=path):
                value = copy.deepcopy(metadata(Path("completion.json" if selected == "completion"
                                                    else "paired_initial_identity.json" if selected == "initial"
                                                    else "paired_orders.json")))
                if selected == "completion":
                    value["status"] = "PARTIAL"
                elif selected == "initial":
                    value["B7"]["full_state_sha256"] = "OTHER"
                else:
                    value["3"]["sha256"] = "OTHER"
                return value
            with self.subTest(path=path), patch.object(controller, "read", side_effect=broken), \
                    patch.object(controller, "verify_schedule_receipts"), self.assertRaises(RuntimeError):
                controller.task_completion(Path("SYNTHETIC"), "REAL", 2030, "SYNTHETIC", envelope, origin)


    def test_execution_spec_binds_the_deterministic_execute_command(self):
        root = Path("C:/ROOT")
        namespace = root / "docs/research_readiness/.local/ns"
        spec = controller.execution_spec(root, {"proposal_sha256": "SYNTHETIC_SHA"}, namespace)
        self.assertEqual(spec["kind"], controller.KIND)
        self.assertEqual(Path(spec["cwd"]), root.resolve())
        self.assertEqual(Path(spec["service_dir"]), (namespace / "service").resolve())
        self.assertEqual(spec["command"][1], "-B")
        self.assertEqual(Path(spec["command"][2]), (root / controller.ENTRY).resolve())
        self.assertEqual(spec["command"][3], "execute")
        self.assertEqual(spec["command"][4::2],
                         ["--proposal", "--private-preparation", "--researcher-approval"])
        self.assertEqual(Path(spec["command"][5]), (namespace / "PROPOSAL.json").resolve())
        self.assertEqual(Path(spec["command"][7]), (namespace / "PRIVATE_PREPARATION.json").resolve())
        self.assertEqual(Path(spec["command"][9]), (namespace / "RESEARCHER_APPROVAL.json").resolve())
        self.assertEqual(spec["environment"]["PYTHONHASHSEED"], str(controller.SEEDS[0]))
        self.assertEqual(spec["environment"]["CUBLAS_WORKSPACE_CONFIG"], ":4096:8")
        self.assertEqual(spec["proposal_sha256"], "SYNTHETIC_SHA")


if __name__ == "__main__":
    unittest.main()
