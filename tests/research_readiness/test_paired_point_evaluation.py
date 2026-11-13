"""CPU/std-library synthetic checks. Never opens real research inputs."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
TEST_BASE = ROOT / "docs/research_readiness/.local/paired_point_synthetic_tests"
SPEC = importlib.util.spec_from_file_location("paired_point_controller_test", ROOT / "tools/research_readiness/start_paired_point_evaluation.py")
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)


class PairedPointEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.root = TEST_BASE / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.source = self.root / "source"
        self.source.mkdir()
        self.output = self.root / "new-output"
        self.preflight = self.root / "preflight"
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.python = self.runtime / "python.exe"
        self.python.write_bytes(b"synthetic-runtime")
        self.private = dict(proposal_sha256="", output_root=str(self.output), preflight_root=str(self.preflight),
                            runtime_python=str(self.python), runtime_roots=[str(self.runtime)], source_roots=[str(self.source)],
                            metadata_files={}, scientific_files={}, tasks={})

    def tearDown(self):
        if self.root.resolve().is_relative_to(TEST_BASE.resolve()):
            shutil.rmtree(self.root)

    def file(self, name, content=b"synthetic-input"):
        path = self.source / name
        path.write_bytes(content)
        return path, dict(bytes=len(content), sha256=controller.sha(path))

    def guard(self, **kwargs):
        return controller.ReadGuard(self.private, metadata_cap=kwargs.pop("metadata_cap", 1000),
                                    metadata_opens=kwargs.pop("metadata_opens", 10), check=lambda: 10,
                                    output_roots=[self.output, self.preflight], **kwargs)

    def open_event(self, guard, path, flags=os.O_RDONLY):
        guard.active = True
        try:
            guard._event("open", (str(path), "rb", flags))
        finally:
            guard.active = False

    def grant(self):
        proposal = dict(authorization_scope=controller.SCOPE, tasks=list(controller.TASKS), budget=dict(controller.LIMITS),
                        final_2025_access=False, execution_code_commit="a" * 40, scientific_choices={"thresholds_mm_h": [20]},
                        data_scope=dict(year=2024, role="Development", scenes=963, n_valid=3303090, n_rain=407820),
                        data_identity=dict(population_sha256=controller.POPULATION_SHA256), code_sha256={},
                        runtime=dict(executable_sha256=controller.sha(self.python), python_version="0.0.0"),
                        models=[dict(task=task, model="B7", seed=2029) for task in controller.TASKS])
        proposal["private_preparation_sha256"] = controller.digest({k: v for k, v in self.private.items() if k != "proposal_sha256"})
        proposal["proposal_sha256"] = controller.digest(proposal)
        self.private["proposal_sha256"] = proposal["proposal_sha256"]
        approval = dict(approved_by_researcher=True, authorization_scope=controller.SCOPE,
                        proposal_sha256=proposal["proposal_sha256"], code_commit=proposal["execution_code_commit"],
                        tasks=proposal["tasks"], scientific_choices=proposal["scientific_choices"], budget=proposal["budget"],
                        output_root=self.private["output_root"], decision_id="SYNTHETIC_ONLY", researcher_instruction="Synthetic fixture")
        return proposal, approval

    def write_bootstrap(self):
        proposal, approval = self.grant()
        paths = [self.root / name for name in ("proposal.json", "private.json", "approval.json")]
        for path, value in zip(paths, (proposal, self.private, approval)):
            path.write_text(json.dumps(value), encoding="utf-8")
        return paths

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            controller.decode(b'{"input":1,"input":2}')

    def test_exact_grant_passes_and_modified_science_is_rejected(self):
        proposal, approval = self.grant()
        controller.validate_grant(proposal, self.private, approval)
        approval["scientific_choices"] = {"thresholds_mm_h": [10]}
        with self.assertRaises(PermissionError):
            controller.validate_grant(proposal, self.private, approval)

    def test_private_content_change_is_rejected(self):
        proposal, approval = self.grant()
        self.private["runtime_roots"].append("new-root")
        with self.assertRaises(PermissionError):
            controller.validate_grant(proposal, self.private, approval)

    def test_grant_rejects_new_year_or_task(self):
        for field, value in (("tasks", ["OTHER"]), ("final_2025_access", True)):
            proposal, approval = self.grant()
            proposal[field] = value
            with self.assertRaises(PermissionError):
                controller.validate_grant(proposal, self.private, approval)

    def test_bootstrap_is_bounded_and_counted(self):
        paths = self.write_bootstrap()
        p, v, a, identities, total = controller.bootstrap(*paths)
        self.assertEqual(total, sum(path.stat().st_size for path in paths))
        self.assertEqual(len(identities), 3)
        self.assertEqual(p["proposal_sha256"], v["proposal_sha256"])
        with mock.patch.object(controller, "BOOTSTRAP_CAP", 4):
            with self.assertRaises(PermissionError):
                controller.bootstrap(*paths)

    def test_invalid_approval_does_not_consume_preflight(self):
        paths = self.write_bootstrap()
        paths[2].write_text("{}", encoding="utf-8")
        with self.assertRaises(PermissionError):
            controller.validate_entry(*paths)
        self.assertFalse(self.preflight.exists())

    def test_only_two_preflight_claims(self):
        self.assertEqual(controller.reserve_preflight(self.preflight, "x"), 1)
        controller.write(self.preflight / "receipt_01.json", {"status": "PASS"})
        self.assertEqual(controller.reserve_preflight(self.preflight, "x"), 2)
        with self.assertRaises(PermissionError):
            controller.reserve_preflight(self.preflight, "x")

    def test_metadata_every_open_is_reserved_before_cap(self):
        path, info = self.file("plan.json", b"{}")
        self.private["metadata_files"][str(path)] = info
        guard = self.guard(metadata_cap=4, metadata_opens=2)
        self.open_event(guard, path)
        self.open_event(guard, path)
        with self.assertRaises(PermissionError):
            self.open_event(guard, path)
        record = guard.close()
        self.assertEqual((record["metadata_archive_reserved_bytes"], record["metadata_open_instances"]), (4, 2))

    def test_metadata_modified_length_rejected_before_charge(self):
        path, info = self.file("plan.json", b"{}")
        self.private["metadata_files"][str(path)] = info
        guard = self.guard()
        path.write_bytes(b"{\"x\":1}")
        with self.assertRaises(PermissionError):
            self.open_event(guard, path)
        self.assertEqual(guard.meta_opens, 0)

    def test_unknown_metadata_and_extensions_are_denied(self):
        guard = self.guard()
        for name in ("unlisted.json", "unknown.ext", "sample.npy", "sample.grib", "sample.db"):
            path, _ = self.file(name)
            with self.assertRaises(PermissionError):
                self.open_event(guard, path)
        outside = self.root / "outside.npy"
        outside.write_bytes(b"fake")
        with self.assertRaises(PermissionError):
            self.open_event(guard, outside)
        outside_json = self.root / "unlisted.json"
        outside_json.write_bytes(b"{}")
        with self.assertRaises(PermissionError):
            self.open_event(guard, outside_json)

    def test_bound_metadata_rejects_truncate_write(self):
        path, info = self.file("plan.json", b"{}")
        self.private["metadata_files"][str(path)] = info
        for flags in (os.O_WRONLY, os.O_RDWR, os.O_APPEND, os.O_TRUNC, os.O_CREAT):
            with self.assertRaises(PermissionError):
                self.open_event(self.guard(), path, flags)

    def test_sqlite_requires_readonly_uri_and_is_metered(self):
        path, info = self.file("statistics.sqlite")
        self.private["metadata_files"][str(path)] = info
        guard = self.guard()
        guard.active = True
        try:
            with self.assertRaises(PermissionError):
                guard._event("sqlite3.connect", (str(path),))
            with self.assertRaises(PermissionError):
                guard._event("sqlite3.connect", (path.as_uri().replace("file:///", "file:/") + "?mode=rw",))
            guard._event("sqlite3.connect", (path.as_uri() + "?mode=ro",))
        finally:
            guard.active = False
        self.assertEqual(guard.meta_opens, 1)

    def test_checkpoint_exact_two_opens_and_task_isolation(self):
        path, info = self.file("fixed.pt")
        self.private["scientific_files"][str(path)] = dict(info, category="checkpoint", tasks=[controller.TASKS[0]], opens_per_task=2)
        guard = self.guard(task=controller.TASKS[0])
        self.open_event(guard, path)
        self.open_event(guard, path)
        with self.assertRaises(PermissionError):
            self.open_event(guard, path)
        for task in (None, controller.TASKS[1]):
            with self.assertRaises(PermissionError):
                self.open_event(self.guard(task=task), path)
        self.assertEqual(guard.close()["payload_open_instances"], 2)

    def test_alias_and_cross_category_paths_rejected(self):
        path, info = self.file("fixed.pt")
        self.private["metadata_files"] = {str(path): info, str(path.parent / "sub" / ".." / path.name): info}
        with self.assertRaises(ValueError):
            self.guard()
        self.private["metadata_files"] = {str(path): info}
        self.private["scientific_files"] = {str(path): dict(info, category="checkpoint", tasks=[controller.TASKS[0]], opens_per_task=2)}
        with self.assertRaises(ValueError):
            self.guard()

    def test_worker_cannot_spawn_after_validation(self):
        guard = self.guard(task=controller.TASKS[0])
        guard.active, guard.block_subprocess = True, True
        try:
            for event in ("subprocess.Popen", "os.system", "os.fork", "os.posix_spawn"):
                with self.assertRaises(PermissionError):
                    guard._event(event, ())
        finally:
            guard.active = False

    def test_runtime_dependency_read_is_allowed_but_write_denied(self):
        dependency = self.runtime / "library.pyd"
        dependency.write_bytes(b"dependency")
        guard = self.guard()
        self.open_event(guard, dependency)
        with self.assertRaises(PermissionError):
            self.open_event(guard, dependency, os.O_WRONLY)

    def test_deadline_checks_earlier_clock(self):
        clock = {"mono": 100, "wall": 1000}
        deadline = controller.Deadline(10, absolute_wall=1005, monotonic=lambda: clock["mono"], wall=lambda: clock["wall"])
        self.assertEqual(deadline.remaining(), 5)
        clock["wall"] = 1006
        with self.assertRaises(TimeoutError):
            deadline.remaining()

    def test_output_cap_counts_console_files(self):
        self.output.mkdir()
        (self.output / "console.log").write_bytes(b"12345")
        check = controller.OutputLimit(self.output, 4, controller.Deadline(30))
        with self.assertRaises(MemoryError):
            check()
        self.preflight.mkdir()
        (self.preflight / "preflight.log").write_bytes(b"12345")
        check = controller.OutputLimit(self.output, 9, controller.Deadline(30), extra_roots=(self.preflight,))
        with self.assertRaises(MemoryError):
            check()

    def test_termination_wait_is_bounded(self):
        child = mock.Mock()
        child.poll.return_value = None
        controller.terminate_child(child)
        child.kill.assert_called_once()
        child.wait.assert_called_once_with(timeout=10)
        child.wait.side_effect = subprocess.TimeoutExpired("worker", 10)
        with self.assertRaises(RuntimeError):
            controller.terminate_child(child)

    def test_failed_validation_preserves_metadata_accounting(self):
        paths = self.write_bootstrap()
        with mock.patch.object(controller, "validate_bound_inputs", side_effect=ValueError("synthetic gate failure")):
            with self.assertRaises(ValueError):
                controller.validate_entry(*paths)
        failure = controller.read(self.preflight / "failure_01.json")
        self.assertEqual(failure["accounting"]["metadata_open_instances"], 3)
        self.assertGreater(failure["accounting"]["metadata_archive_reserved_bytes"], 0)
        self.assertFalse(self.output.exists())
        with self.assertRaises(PermissionError):
            controller.validate_entry(*paths)

    def test_two_successful_preflights_require_same_approval(self):
        paths = self.write_bootstrap()
        with mock.patch.object(controller, "validate_bound_inputs"):
            controller.validate_entry(*paths)
            proposal, private = controller.validate_entry(*paths)
        receipts = controller.require_preflights(private, proposal, controller.sha(paths[2]))
        self.assertEqual(len(receipts), 2)
        with self.assertRaises(PermissionError):
            controller.require_preflights(private, proposal, "x" * 64)

    def test_second_preflight_uses_first_claim_package_deadline(self):
        paths = self.write_bootstrap()
        with mock.patch.object(controller, "validate_bound_inputs"):
            controller.validate_entry(*paths)
        claim = controller.read(self.preflight / "claim_01.json")
        claim["started"] = "2000-01-01T00:00:00+00:00"
        (self.preflight / "claim_01.json").write_text(json.dumps(claim), encoding="utf-8")
        with mock.patch.object(controller, "validate_bound_inputs") as gates:
            with self.assertRaises(TimeoutError):
                controller.validate_entry(*paths)
            gates.assert_not_called()

    def prepare_mock_execution(self):
        paths = self.write_bootstrap()
        with mock.patch.object(controller, "validate_bound_inputs"):
            controller.validate_entry(*paths)
            controller.validate_entry(*paths)
        return paths

    def point_summary(self):
        rows = []
        for threshold, positive in zip((0.1, 1.0, 5.0, 10.0, 20.0, 50.0), (407820, 161347, 25661, 5516, 717, 6)):
            rows.append(dict(threshold_mm_h=threshold, TP=0, FP=0, FN=positive, TN=3303090 - positive,
                             POD=0.0, FAR=None, CSI=0.0, Precision=None, F1=0.0, ETS=0.0, HSS=0.0,
                             frequency_bias=0.0, truth_equal=0, prediction_equal=0))
        return dict(scenes=963, n_valid=3303090, n_rain=407820, supervision_mask_sha256="b" * 64,
                    classification_precision="FP32 predictions and reference rates; strict > FP32 threshold",
                    methods={method: dict(continuous=dict(MAE=1.0, RMSE=2.0, MeanBias=0.0, Pearson_CC=None),
                                           thresholds=json.loads(json.dumps(rows))) for method in ("A", "B", "C")})

    def test_execute_serial_success_uses_two_claimed_workers(self):
        paths = self.prepare_mock_execution()
        started = []
        def spawn(command, **kwargs):
            task = command[-1]
            started.append(task)
            folder = self.output / task
            folder.mkdir()
            controller.write(folder / "point_metrics.json", self.point_summary())
            accounting = dict(metadata_archive_reserved_bytes=0, metadata_open_instances=0,
                              payload_archive_reserved_bytes=controller.LIMITS["payload_archive_reference_bytes"] if task == controller.TASKS[0] else 0,
                              payload_open_instances=controller.LIMITS["payload_open_instances"] if task == controller.TASKS[0] else 0)
            controller.write(folder / "task_complete.json", dict(status="COMPLETE", task=task, accounting=accounting,
                                                                  result=dict(status="COMPLETE", synthetic=True)))
            child = mock.Mock(returncode=0)
            child.poll.return_value = 0
            return child
        with mock.patch.object(controller, "validate_bound_inputs"), mock.patch.object(controller, "require_host"), \
                mock.patch.object(controller, "resources", return_value={}), mock.patch.object(controller.sys, "executable", str(self.python)), \
                mock.patch.object(controller.subprocess, "Popen", side_effect=spawn):
            controller.execute(*paths)
        self.assertEqual(started, list(controller.TASKS))
        self.assertEqual(controller.read(self.output / "completion.json")["status"], "COMPLETE_PAIRED_POINT_EVALUATION")
        with mock.patch.object(controller, "validate_bound_inputs"), mock.patch.object(controller, "require_host"), \
                mock.patch.object(controller, "resources", return_value={}), mock.patch.object(controller.sys, "executable", str(self.python)), \
                mock.patch.object(controller.subprocess, "Popen") as launch:
            with self.assertRaises(FileExistsError):
                controller.execute(*paths)
            launch.assert_not_called()

    def test_execute_first_failure_blocks_candidate(self):
        paths = self.prepare_mock_execution()
        child = mock.Mock(returncode=1)
        child.poll.return_value = 1
        with mock.patch.object(controller, "validate_bound_inputs"), mock.patch.object(controller, "require_host"), \
                mock.patch.object(controller, "resources", return_value={}), mock.patch.object(controller.sys, "executable", str(self.python)), \
                mock.patch.object(controller.subprocess, "Popen", return_value=child) as launch:
            with self.assertRaises(RuntimeError):
                controller.execute(*paths)
        launch.assert_called_once()
        self.assertFalse((self.output / f"{controller.TASKS[1]}_claim.json").exists())
        self.assertTrue((self.output / "failure.json").is_file())

    def test_worker_rejects_changed_parent_before_source_gates(self):
        paths = self.write_bootstrap()
        self.output.mkdir()
        proposal = controller.read(paths[0])
        controller.write(self.output / "binding.json", dict(controller_pid=-1,
                         approval_sha256=controller.sha(paths[2]), proposal_sha256=proposal["proposal_sha256"],
                         code_commit=proposal["execution_code_commit"], absolute_wall_deadline=10 ** 20))
        controller.write(self.output / f"{controller.TASKS[0]}_claim.json", dict(task=controller.TASKS[0],
                         controller_pid=-1, proposal_sha256=proposal["proposal_sha256"]))
        with mock.patch.object(controller, "validate_bound_inputs") as gates:
            with self.assertRaises(PermissionError):
                controller.worker(*paths, controller.TASKS[0])
            gates.assert_not_called()
        self.assertFalse((self.output / controller.TASKS[0]).exists())

    def test_pairing_preserves_values_and_null_differences(self):
        self.output.mkdir()
        for task in controller.TASKS:
            folder = self.output / task
            folder.mkdir()
            summary = self.point_summary()
            if task == controller.TASKS[1]:
                summary["methods"]["A"]["continuous"]["MAE"] = 0.5
            controller.write(folder / "point_metrics.json", summary)
        result = controller.finalize_pair(self.output, {"proposal_sha256": "x"})
        self.assertEqual(result["differences"]["A"]["continuous"]["MAE"], -0.5)
        self.assertIsNone(result["differences"]["A"]["continuous"]["Pearson_CC"])
        self.assertIsNone(result["differences"]["A"]["thresholds"][0]["FAR"])
        self.assertTrue((self.output / "paired_metrics.json").is_file())

    def test_pairing_rejects_mask_and_contingency_population_changes(self):
        self.output.mkdir()
        for task in controller.TASKS:
            (self.output / task).mkdir()
        for mutation in ("mask", "count", "truth", "thresholds", "methods"):
            summaries = {task: self.point_summary() for task in controller.TASKS}
            candidate = summaries[controller.TASKS[1]]
            if mutation == "mask":
                candidate["supervision_mask_sha256"] = "c" * 64
            elif mutation == "count":
                candidate["methods"]["A"]["thresholds"][0]["TN"] += 1
            elif mutation == "truth":
                candidate["methods"]["A"]["thresholds"][4]["FN"] -= 1
                candidate["methods"]["A"]["thresholds"][4]["TN"] += 1
            elif mutation == "thresholds":
                candidate["methods"]["A"]["thresholds"][0]["threshold_mm_h"] = 0.2
            else:
                candidate["methods"]["D"] = candidate["methods"]["A"]
            for task, summary in summaries.items():
                (self.output / task / "point_metrics.json").write_text(json.dumps(summary), encoding="utf-8")
            with self.assertRaises(ValueError, msg=mutation):
                controller.finalize_pair(self.output, {"proposal_sha256": "x"})

    def test_source_manifest_validation_does_not_stat_weather(self):
        source = {}
        weather_bytes = 26639253112
        for index in range(7950):
            source[str(self.source / f"synthetic_weather_{index:04d}.nc")] = dict(bytes=weather_bytes - 7949 if index == 0 else 1,
                sha256="0" * 64, category="weather", tasks=list(controller.TASKS), opens_per_task=1)
        static = self.source / "synthetic_static.npz"
        source[str(static)] = dict(bytes=312828, sha256="1" * 64, category="static", tasks=list(controller.TASKS), opens_per_task=1)
        proposal = {"models": []}
        stat_sizes = {str(static): 312828}
        for task, size in zip(controller.TASKS, (53904005, 53906821)):
            checkpoint = self.source / f"{task}.pt"
            report = self.source / f"{task}.json"
            source[str(checkpoint)] = dict(bytes=size, sha256="2" * 64, category="checkpoint", tasks=[task], opens_per_task=2)
            stat_sizes[str(checkpoint)] = size
            self.private["tasks"][task] = dict(checkpoint_path=str(checkpoint), dev_report_path=str(report))
            self.private["metadata_files"][str(report)] = dict(bytes=2, sha256="3" * 64)
            proposal["models"].append(dict(task=task, checkpoint_bytes=size, checkpoint_sha256="2" * 64,
                                          dev_report_bytes=2, dev_report_sha256="3" * 64))
        self.private["scientific_files"] = source
        def stat(path, *args, **kwargs):
            if str(path) not in stat_sizes:
                raise AssertionError("Weather must not be stat'ed during metadata validation")
            return SimpleNamespace(st_size=stat_sizes[str(path)])
        with mock.patch.object(Path, "stat", stat):
            controller.validate_scientific_manifest(proposal, self.private)


if __name__ == "__main__":
    unittest.main()
