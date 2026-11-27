"""Unit tests for the frozen Stage-4 multi-seed candidate reproduction module."""

from __future__ import annotations

import io
import json
import math
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from yuntapr.experimental.research_readiness import (  # noqa: E402
    multiseed_candidate_reproduction as arm,
)

SCENE_A = "2024-01-01T00:00:00+00:00"
SCENE_B = "2024-01-01T00:10:00+00:00"


def _nodes(top=40.0, bottom=0.05):
    return np.linspace(bottom, top, arm.NODES)


def _qlog(nodes):
    return np.log1p(np.asarray(nodes, dtype=np.float64))


def _population(rows):
    """Build the gate-level population view directly from row fixtures."""
    p = np.asarray([row["p"] for row in rows], dtype=np.float32)
    truth = np.asarray([row["truth"] for row in rows], dtype=np.float32)
    qlog = np.stack([_qlog(row["nodes"]) for row in rows]).astype(np.float64)
    physical = np.expm1(qlog)
    q32 = physical[:, -1]
    a0 = np.float32(p.astype(np.float64) * physical.mean(axis=1))
    strong = truth > arm.THRESHOLD
    weak = (truth > arm.RAIN_THRESHOLD) & (truth <= arm.WEAK_UPPER)
    rain = truth > arm.RAIN_THRESHOLD
    candidate = [index for index in range(len(rows)) if p[index] * q32[index] > 20.0]
    s1_rows = [index for index, row in enumerate(rows) if row.get("s1")]
    s1_meta = [
        {
            "scene_index": 0 if row < 2 else 1,
            "row": row,
            "y": row,
            "x": row,
            "global_row": row,
        }
        for row in s1_rows
    ]
    s1_scene_ids = []
    for meta in s1_meta:
        scene = SCENE_A if meta["scene_index"] == 0 else SCENE_B
        if scene not in s1_scene_ids:
            s1_scene_ids.append(scene)
    return {
        "scene_ids": [SCENE_A, SCENE_B],
        "p": p,
        "truth": truth,
        "q32": q32,
        "a0": a0,
        "strong": strong,
        "weak": weak,
        "rain": rain,
        "candidate_rows": np.asarray(candidate, dtype=np.int64),
        "candidate_scene_ids": s1_scene_ids,
        "candidate_strong": strong[candidate],
        "s1_rows": np.asarray(s1_rows, dtype=np.int64),
        "s1_meta": s1_meta,
        "s1_scene_ids": s1_scene_ids,
        "s1_index": {int(row): index for index, row in enumerate(s1_rows)},
        "s1_qlog": qlog[s1_rows] if s1_rows else np.empty((0, arm.NODES)),
        "strong_qlog": qlog[strong],
        "weak_qlog": qlog[weak],
    }


def _shard_bytes(scenes=2):
    mask = np.zeros((scenes, 100, 100), dtype=bool)
    for index in range(scenes):
        mask[index].reshape(-1)[:3430] = True
    rows = scenes * 3430
    p = np.full(rows, 0.1, dtype=np.float32)
    truth = np.full(rows, 0.05, dtype=np.float32)
    qlog = np.tile(_qlog(np.linspace(0.001, 2.0, arm.NODES)), (rows, 1)).astype(
        np.float64
    )
    special = 57
    p[special] = np.float32(0.9)
    truth[special] = np.float32(60.0)
    qlog[special] = _qlog(np.linspace(0.05, 40.0, arm.NODES))
    ids = np.asarray([SCENE_A, SCENE_B][:scenes], dtype="<U25")
    stream = io.BytesIO()
    np.savez(
        stream,
        scene_ids=ids,
        supervision_mask=mask,
        p=p,
        qlog=qlog,
        truth_mm_h=truth,
    )
    return stream.getvalue(), special


class CandidateReproductionTests(unittest.TestCase):
    def test_frozen_budget_constants_are_exact(self):
        self.assertEqual(arm.KIND, "BOUNDED_STAGE4_MULTISEED_CANDIDATE_REPRODUCTION")
        self.assertEqual(
            arm.SCOPE, "FOUR_MODEL_COSINE9_REAL_ZERO_CANDIDATE_REPRODUCTION_V1"
        )
        self.assertEqual(
            arm.STATUS, "COMPLETE_STAGE4_MULTISEED_CANDIDATE_REPRODUCTION"
        )
        self.assertEqual(
            arm.TASKS, ("REAL_s2030", "ZERO_s2030", "REAL_s2031", "ZERO_s2031")
        )
        budget = arm.BUDGET
        self.assertEqual(budget["total_scientific_file_opens"], 907)
        self.assertEqual(budget["total_scientific_source_bytes"], 5_410_034_087)
        self.assertEqual(budget["scientific_file_opens"], 904)
        self.assertEqual(budget["scientific_source_bytes"], 5_402_764_976)
        self.assertEqual(budget["arrays_open_instances"], 484)
        self.assertEqual(budget["arrays_reference_bytes"], 3_527_579_048)
        self.assertEqual(budget["satellite_open_instances"], 420)
        self.assertEqual(budget["satellite_reference_bytes"], 1_875_185_928)
        self.assertEqual(budget["metadata_open_instances"], 3)
        self.assertEqual(budget["metadata_reference_bytes"], 7_269_111)
        self.assertEqual(budget["maximum_seconds"], 1800)
        self.assertEqual(budget["minimum_free_bytes"], 8 * 1024**3)
        self.assertEqual(budget["maximum_scientific_file_opens"], 3700)
        self.assertEqual(budget["maximum_scientific_source_bytes"], 18_000_000_000)
        self.assertEqual(budget["checkpoint_loads"], 0)
        self.assertEqual(budget["model_inference_passes"], 0)
        self.assertEqual(budget["optimizer_updates"], 0)
        self.assertEqual(budget["retries"], 0)
        self.assertEqual(budget["replays"], 0)
        self.assertEqual(budget["per_task"]["REAL_s2030"]["satellite_opens"], 78)
        self.assertEqual(budget["per_task"]["ZERO_s2030"]["satellite_bytes"], 288_604_839)
        self.assertEqual(budget["per_task"]["REAL_s2031"]["satellite_opens"], 132)
        self.assertEqual(budget["per_task"]["ZERO_s2031"]["satellite_bytes"], 644_432_923)
        self.assertEqual(
            arm.DATA_SCOPE["supervision_mask_sha256"],
            "70368bec3149e998922d565dab83347ba33f465df481a03ac3f90b85f1286d4b",
        )
        self.assertEqual(arm.EXPECTED["REAL_s2031"]["counts"]["s1_rows"], 143)
        self.assertAlmostEqual(
            arm.EXPECTED["ZERO_s2031"]["metrics"]["strong_physical_pinball_over20"],
            0.5011434163139744,
            places=15,
        )

    def test_execution_spec_command_and_environment(self):
        namespace = ROOT / "docs/research_readiness/.local/synthetic_namespace"
        spec = arm.execution_spec(ROOT, {"proposal_sha256": "a" * 64}, namespace)
        self.assertEqual(spec["kind"], arm.KIND)
        self.assertEqual(spec["cwd"], str(ROOT.resolve()))
        self.assertEqual(spec["proposal_sha256"], "a" * 64)
        self.assertEqual(spec["service_dir"], str((namespace / "service").resolve()))
        self.assertEqual(
            spec["environment"],
            {
                "PYTHONHASHSEED": "2029",
                "PYTHONUTF8": "1",
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
            },
        )
        command = spec["command"]
        self.assertEqual(len(command), 10)
        self.assertEqual(command[1], "-B")
        self.assertEqual(Path(command[0]).name.lower(), Path(sys.executable).name.lower())
        self.assertEqual(
            Path(command[2]),
            (ROOT / "tools/research_readiness/start_multiseed_candidate_reproduction.py").resolve(),
        )
        self.assertEqual(command[3], "execute")
        self.assertEqual(
            command[4::2],
            ["--proposal", "--private-preparation", "--researcher-approval"],
        )
        for value in command[5::2]:
            self.assertTrue(Path(value).is_absolute())

    def test_array_loading_enumerates_s1_rows_and_scene_extraction(self):
        content, special = _shard_bytes()
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / "batch_000.npz").write_bytes(content)
            entries = [
                {
                    "file": "batch_000.npz",
                    "bytes": len(content),
                    "sha256": arm.sha256_bytes(content),
                }
            ]
            population = arm.load_task(
                entries, directory, lambda path, size, digest: content
            )
        counts = arm.baseline_counts(population)
        self.assertEqual(counts["scenes"], 2)
        self.assertEqual(counts["n_valid"], 6860)
        self.assertEqual(counts["n_rain"], 1)
        self.assertEqual(counts["n_strong"], 1)
        self.assertEqual(counts["n_weak"], 0)
        self.assertEqual(counts["s1_rows"], 1)
        self.assertEqual(counts["s1_scenes"], 1)
        self.assertEqual(population["s1_scene_ids"], [SCENE_A])
        meta = population["s1_meta"][0]
        self.assertEqual(meta["row"], special)
        self.assertEqual((meta["y"], meta["x"]), (special // 100, special % 100))
        self.assertEqual(int(population["s1_rows"][0]), special)
        self.assertGreater(float(population["q32"][special]), 20.0)
        self.assertGreaterEqual(float(population["a0"][special]), arm.A0_THRESHOLD)

    def test_split_min_selection_boundary(self):
        population = _population(
            [
                {"truth": 60.0, "p": 0.6, "nodes": _nodes(), "s1": True},
            ]
        )
        self.assertEqual(
            arm.selected_rows(population, {0: arm.SPLIT_THRESHOLD - 1e-6}), []
        )
        self.assertEqual(
            arm.selected_rows(population, {0: arm.SPLIT_THRESHOLD}), [0]
        )
        with self.assertRaisesRegex(ValueError, "lacks split_min"):
            arm.selected_rows(population, {})

    def test_blend_action_feasible_and_infeasible(self):
        nodes = _nodes()
        record, reason = arm.apply_action(nodes, 0.6)
        self.assertIsNone(reason)
        self.assertGreaterEqual(record["new_a"], 20.01 - 1e-6)
        self.assertTrue(0.0 < record["fraction"] < 1.0)
        self.assertTrue(np.all(np.diff(record["nodes"]) > 0))

        descending = np.linspace(100.0, 25.0, arm.NODES)
        record, reason = arm.apply_action(descending, 0.9)
        self.assertIsNone(record)
        self.assertEqual(reason, "BLEND_DENOMINATOR_NOT_POSITIVE")

        record, reason = arm.apply_action(_nodes(), 0.05)
        self.assertIsNone(record)
        self.assertIn(
            reason,
            (
                "BLEND_FRACTION_OUTSIDE_OPEN_UNIT_INTERVAL",
                "NEW_A_NOT_STRICTLY_ABOVE_20",
                "NODES_NOT_STRICTLY_INCREASING",
            ),
        )

    def test_per_task_gates_pass_for_improving_strong_selection(self):
        population = _population(
            [
                {"truth": 60.0, "p": 0.6, "nodes": _nodes(), "s1": True},
                {"truth": 2.0, "p": 0.3, "nodes": _nodes(30.0, 0.01)},
                {"truth": 0.5, "p": 0.2, "nodes": _nodes(10.0, 0.01)},
                {"truth": 0.0, "p": 0.1, "nodes": _nodes(5.0, 0.001)},
            ]
        )
        result = arm.evaluate_task("REAL_s2030", population, {0: 5.0})
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["failing_gates"], [])
        self.assertEqual(result["selection"]["selected_rows"], 1)
        self.assertEqual(result["selection"]["weak_rows_selected"], 0)
        self.assertEqual(result["selection"]["nonstrong_rows_selected"], 0)
        self.assertLess(
            result["candidate_metrics"]["strong_physical_pinball_over20"],
            result["baseline_metrics"]["strong_physical_pinball_over20"],
        )
        self.assertGreater(result["candidate_metrics"]["point_a_tp"], 0)
        for gate in result["gates"][6:]:
            self.assertEqual(gate["status"], "BY_CONSTRUCTION_EQUAL")
        json.dumps(result, allow_nan=False)

    def test_per_task_gates_fail_for_nonstrong_selection(self):
        population = _population(
            [
                {"truth": 10.0, "p": 0.6, "nodes": _nodes(), "s1": True},
                {"truth": 2.0, "p": 0.3, "nodes": _nodes(30.0, 0.01)},
                {"truth": 0.5, "p": 0.2, "nodes": _nodes(10.0, 0.01)},
                {"truth": 60.0, "p": 0.1, "nodes": _nodes(5.0, 0.001)},
            ]
        )
        result = arm.evaluate_task("ZERO_s2030", population, {0: 5.0})
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn(
            "strong_physical_pinball_over20",
            [gate["name"] for gate in result["gates"] if not gate["passed"]],
        )
        self.assertEqual(result["selection"]["nonstrong_rows_selected"], 1)
        self.assertIn("nonstrong_rows_selected", result["failing_gates"])

    def test_per_task_gates_fail_for_infeasible_action(self):
        population = _population(
            [
                {
                    "truth": 60.0,
                    "p": 0.9,
                    "nodes": np.linspace(100.0, 25.0, arm.NODES),
                    "s1": True,
                },
                {"truth": 0.5, "p": 0.2, "nodes": _nodes(10.0, 0.01)},
            ]
        )
        result = arm.evaluate_task("REAL_s2031", population, {0: 5.0})
        self.assertEqual(result["decision"], "FAIL")
        self.assertEqual(result["selection"]["infeasible_rows"], 1)
        self.assertEqual(result["selection"]["feasible_rows"], 0)
        self.assertEqual(result["infeasible_rows"][0]["infeasible_reason"], "BLEND_DENOMINATOR_NOT_POSITIVE")

    def test_q2_aggregation_branches(self):
        def result(task, decision):
            baseline = {
                "strong_physical_pinball_over20": 0.5,
                "q32_support_tp": 1,
                "q32_support_fp": 0,
                "point_a_tp": 0,
                "point_a_fp": 0,
                "weak_log_pinball": 0.1,
                "occurrence_brier": 0.1,
                "occurrence_ap": 0.5,
                "occurrence_auroc": 0.8,
            }
            candidate = dict(baseline)
            candidate["strong_physical_pinball_over20"] = (
                0.49 if decision == "PASS" else 0.51
            )
            candidate["point_a_tp"] = 1 if decision == "PASS" else 0
            return {
                "task": task,
                "arm": task.split("_s")[0],
                "seed": int(task.split("_s")[1]),
                "decision": decision,
                "failing_gates": [] if decision == "PASS" else ["gate1"],
                "selection": {
                    "selected_rows": 1,
                    "feasible_rows": 1,
                    "infeasible_rows": 0,
                    "strong_rows_selected": 1,
                    "weak_rows_selected": 0,
                    "nonstrong_rows_selected": 0,
                },
                "baseline_metrics": baseline,
                "candidate_metrics": candidate,
            }

        self.assertEqual(
            arm.q2_summary(
                {task: result(task, "PASS") for task in arm.REAL_TASKS}
            )["decision"],
            "CANDIDATE_REPRODUCED_ACROSS_SEEDS",
        )
        self.assertEqual(
            arm.q2_summary(
                {
                    "REAL_s2030": result("REAL_s2030", "PASS"),
                    "REAL_s2031": result("REAL_s2031", "FAIL"),
                }
            )["decision"],
            "PARTIAL",
        )
        self.assertEqual(
            arm.q2_summary(
                {task: result(task, "FAIL") for task in arm.REAL_TASKS}
            )["decision"],
            "NOT_REPRODUCED",
        )
        summary = arm.q2_summary(
            {task: result(task, "PASS") for task in arm.REAL_TASKS},
            {"sha256": "b" * 64},
        )
        self.assertEqual(summary["seed2029_reference"]["sha256"], "b" * 64)
        json.dumps(summary, allow_nan=False)

    def test_q3_descriptive_and_attribution_warning(self):
        def result(task, delta):
            baseline = {
                "strong_physical_pinball_over20": 0.5,
                "q32_support_tp": 1,
                "q32_support_fp": 0,
                "point_a_tp": 0,
                "point_a_fp": 0,
                "weak_log_pinball": 0.1,
                "occurrence_brier": 0.1,
                "occurrence_ap": 0.5,
                "occurrence_auroc": 0.8,
            }
            candidate = dict(baseline)
            candidate["strong_physical_pinball_over20"] = 0.5 + delta
            candidate["point_a_tp"] = 1 if delta < 0 else 0
            return {
                "task": task,
                "arm": "ZERO",
                "seed": int(task.split("_s")[1]),
                "decision": "PASS" if delta < 0 else "FAIL",
                "failing_gates": [],
                "selection": {
                    "selected_rows": 1,
                    "feasible_rows": 1,
                    "infeasible_rows": 0,
                    "strong_rows_selected": 1,
                    "weak_rows_selected": 0,
                    "nonstrong_rows_selected": 0,
                },
                "baseline_metrics": baseline,
                "candidate_metrics": candidate,
            }

        warning = arm.q3_summary(
            {task: result(task, -0.01) for task in arm.ZERO_TASKS}
        )
        self.assertTrue(warning["attribution_warning"])
        self.assertEqual(warning["decision"], "DESCRIPTIVE_ONLY")
        self.assertEqual(sorted(warning["attribution_warning_tasks"]), sorted(arm.ZERO_TASKS))
        clean = arm.q3_summary(
            {task: result(task, 0.01) for task in arm.ZERO_TASKS}
        )
        self.assertFalse(clean["attribution_warning"])
        self.assertIsNone(clean["warning"])
        json.dumps(warning, allow_nan=False)

    def test_results_are_json_native_without_numpy_scalars(self):
        population = _population(
            [
                {"truth": 60.0, "p": 0.6, "nodes": _nodes(), "s1": True},
                {"truth": 0.5, "p": 0.2, "nodes": _nodes(10.0, 0.01)},
            ]
        )
        result = arm.evaluate_task("REAL_s2030", population, {0: 5.0})
        text = json.dumps(result, allow_nan=False)
        self.assertEqual(json.loads(text), result)

        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertIsInstance(key, str)
                    walk(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    walk(item)
            else:
                self.assertFalse(type(value).__module__.startswith("numpy"), type(value))
                self.assertNotIsInstance(value, np.generic)

        walk(result)

    def test_validate_approval_rejects_every_binding_mutation(self):
        proposal = {
            "kind": arm.KIND,
            "scope": arm.SCOPE,
            "authorization_scope": arm.SCOPE,
            "decision": arm.DECISION,
            "proposal_sha256": "a" * 64,
            "execution_code_commit": "b" * 40,
            "tasks": list(arm.TASKS),
            "scientific_choices": {"rule": "frozen"},
            "budget": {"maximum_seconds": 1800},
        }
        with TemporaryDirectory() as folder:
            private = {"output_root": str(Path(folder) / "output")}
        approval = {
            "approved_by_researcher": True,
            "authorization_scope": arm.SCOPE,
            "decision_id": arm.DECISION,
            "proposal_sha256": "a" * 64,
            "code_commit": "b" * 40,
            "tasks": list(arm.TASKS),
            "scientific_choices": {"rule": "frozen"},
            "budget": {"maximum_seconds": 1800},
            "output_root": private["output_root"],
            "researcher_instruction": "approved by the researcher",
            "final_2025_access": False,
        }
        self.assertTrue(arm.validate_approval(approval, proposal, private))
        mutations = {
            "approved_by_researcher": False,
            "authorization_scope": "OTHER",
            "decision_id": "OTHER",
            "proposal_sha256": "c" * 64,
            "code_commit": "d" * 40,
            "tasks": ["REAL_s2030"],
            "scientific_choices": {"rule": "changed"},
            "budget": {"maximum_seconds": 900},
            "output_root": str(Path(private["output_root"]).parent / "other"),
            "researcher_instruction": "",
            "final_2025_access": True,
        }
        for key, value in mutations.items():
            mutated = dict(approval)
            mutated[key] = value
            with self.assertRaises(PermissionError, msg=key):
                arm.validate_approval(mutated, proposal, private)
        with self.assertRaises(PermissionError):
            arm.validate_approval(approval, proposal, private, commit="e" * 40)

    def test_fresh_namespace_and_output_helpers(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "root"
            root.mkdir()
            output = Path(folder) / "output"
            self.assertEqual(arm.require_fresh_output(output), output.resolve())
            output.mkdir()
            with self.assertRaisesRegex(PermissionError, "must not exist"):
                arm.require_fresh_output(output)
            namespace = root / arm.PRIVATE_ROOT / "candidate_reproduction_20261127"
            self.assertEqual(arm.require_fresh_namespace(namespace, root), namespace.resolve())
            namespace.mkdir(parents=True)
            with self.assertRaisesRegex(PermissionError, "Fresh private service namespace"):
                arm.require_fresh_namespace(namespace, root)
            outside = root / "outside"
            with self.assertRaisesRegex(PermissionError, "must live under"):
                arm.require_fresh_namespace(outside, root)

    def test_terrain_results_validator_accepts_recorded_shape(self):
        data = {
            "status": "COMPLETE_FOUR_TASK_COSINE9_REAL_ZERO_MULTISEED",
            "automatic_retry": False,
            "replay": False,
            "tasks": [
                {
                    "arm": task.split("_s")[0],
                    "seed": int(task.split("_s")[1]),
                    "updates": 4320,
                    "source_bytes": 477_571_953_840,
                    "last_epoch_09_checkpoint_sha256": arm.CHECKPOINTS[task]["sha256"],
                    "last_epoch_09_checkpoint_bytes": arm.CHECKPOINTS[task]["bytes"],
                }
                for task in arm.TASKS
            ],
        }
        by_task = arm._validate_terrain_results(data)
        self.assertEqual(set(by_task), set(arm.TASKS))
        data["tasks"][0]["updates"] = 1
        with self.assertRaises(ValueError):
            arm._validate_terrain_results(data)


if __name__ == "__main__":
    unittest.main()
