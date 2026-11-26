"""Torch-free unit tests for the bounded Stage-4 four-model evaluation arm."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from yuntapr.experimental.research_readiness import multiseed_dev_evaluation as arm


def _sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _fake_proposal_private(tmp_path):
    private = {
        "kind": arm.KIND,
        "scope": arm.SCOPE,
        "output_root": str(tmp_path / "output"),
        "tasks": {task: {"task": task} for task in arm.TASKS},
        "scientific_files": {},
        "metadata_files": {},
        "parent_proposal": str(tmp_path / "parent.json"),
        "preparation_path": str(tmp_path / "preparation.json"),
        "static_source": str(tmp_path / "static.npz"),
        "code_root": str(tmp_path),
    }
    private["proposal_sha256"] = "0" * 64
    proposal = {
        "kind": arm.KIND,
        "scope": arm.SCOPE,
        "decision": arm.DECISION,
        "status": "READY_WAITING_EXACT_RESEARCHER_APPROVAL",
        "authorized": False,
        "final_2025_access": False,
        "tasks": list(arm.TASKS),
        "models": [
            {
                "task": arm.task_name(control, seed),
                "arm": control,
                "seed": seed,
                "model": arm.MODEL,
                "role": "Development",
                "year": 2024,
                "dynamic_control": arm.CONTROLS[control],
            }
            for control, seed in (
                ("REAL", 2030),
                ("ZERO", 2030),
                ("REAL", 2031),
                ("ZERO", 2031),
            )
        ],
        "data_scope": dict(arm.DATA_SCOPE),
        "scientific_choices": {
            "terrain_evaluation": arm.terrain_contract(),
            "arrays_retention": arm.arrays_retention_spec(),
            "q1_2029_reference": {
                "real_minus_zero": {
                    "log_pinball": arm.Q1_2029_LOG,
                    "physical_pinball_over20": arm.Q1_2029_PHYSICAL,
                },
                "n_strong": arm.Q1_2029_N_STRONG,
                "paired_population_sha256": arm.Q1_REFERENCE_DIGEST,
                "file_sha256": "9" * 64,
            },
        },
        "budget": dict(arm.BUDGET),
        "execution_code_commit": "a" * 40,
        "proposal_sha256": "1" * 64,
    }
    proposal["private_preparation_sha256"] = arm.private_seal(private)
    private["proposal_sha256"] = proposal["proposal_sha256"]
    return proposal, private


def _fake_approval(proposal, private):
    return {
        "approved_by_researcher": True,
        "authorization_scope": arm.SCOPE,
        "decision_id": arm.DECISION,
        "proposal_sha256": proposal["proposal_sha256"],
        "code_commit": proposal["execution_code_commit"],
        "tasks": list(arm.TASKS),
        "scientific_choices": proposal["scientific_choices"],
        "budget": proposal["budget"],
        "output_root": private["output_root"],
        "researcher_instruction": "synthetic unit-test instruction",
        "final_2025_access": False,
    }


def test_budget_matches_the_frozen_envelope_exactly():
    budget = arm.BUDGET
    assert 4 * 26_747_379_518 == 106_989_518_072
    assert 106_989_518_072 + 1_227_801_734 == 108_217_319_806
    assert budget["total_scientific_source_bytes"] == 108_217_319_806
    assert budget["payload_archive_reference_bytes"] == 106_989_518_072
    assert budget["metadata_archive_reference_bytes"] == 1_227_801_734
    assert budget["total_scientific_file_opens"] == 32_730
    assert budget["payload_open_instances"] == 31_812
    assert budget["metadata_open_instances"] == 918
    assert 4 * budget["per_task_payload_open_instances"] == 31_812
    assert budget["per_task_payload_open_instances"] == 7_953
    assert budget["checkpoint_loads"] == 4
    assert budget["model_inference_passes"] == 4
    assert budget["optimizer_updates"] == 0
    assert budget["retries"] == 0
    assert budget["replays"] == 0
    assert budget["maximum_seconds"] == 7_200
    assert budget["minimum_free_bytes"] == 8 * 1024**3
    assert budget["maximum_output_bytes"] == 4 * 1024**3
    assert budget["arrays_batch_count_per_model"] == 121
    assert budget["development_scenes"] == 963
    assert 121 * 8 >= 963


def test_task_table_order_arm_control_and_seed():
    assert arm.TASKS == ("REAL_s2030", "ZERO_s2030", "REAL_s2031", "ZERO_s2031")
    assert arm.SEEDS == (2030, 2031)
    assert arm.CONTROLS == {
        "REAL": "REAL_PHYSICAL_DOTE",
        "ZERO": "ZERO_NUMERIC_RETAIN_REAL_MASKS",
    }
    assert arm.PAIRS == (("REAL_s2030", "ZERO_s2030"), ("REAL_s2031", "ZERO_s2031"))
    for index, task in enumerate(arm.TASKS):
        control = arm.ARMS[index % 2]
        seed = arm.SEEDS[index // 2]
        assert task == arm.task_name(control, seed)
    assert arm.KIND == "BOUNDED_STAGE4_MULTISEED_DEV_EVALUATION"
    assert arm.SCOPE == "FOUR_MODEL_COSINE9_REAL_ZERO_DEV_MOUNTAIN_EVALUATION_V1"
    assert arm.STATUS == "COMPLETE_STAGE4_MULTISEED_DEV_EVALUATION"
    assert arm.DECISION == "DESCRIPTIVE_MULTISEED_REAL_ZERO_DEV_EVALUATION"
    assert arm.ENTRY == "tools/research_readiness/start_multiseed_dev_evaluation.py"


def test_parent_proposal_sha_mismatch_is_rejected(tmp_path):
    path = tmp_path / "parent.json"
    _write_json(path, {"kind": arm.PARENT_PROPOSAL_KIND})
    with pytest.raises(ValueError, match="file sha differs"):
        arm._validate_parent_proposal(path)


def test_artifact_bytes_and_sha_validation(tmp_path):
    path = tmp_path / "artifact.bin"
    payload = b"bounded-evaluation"
    path.write_bytes(payload)
    digest = _sha_bytes(payload)
    arm.validate_artifact(path, len(payload), digest, "synthetic")
    with pytest.raises(ValueError, match="byte size differs"):
        arm.validate_artifact(path, len(payload) + 1, digest, "synthetic")
    with pytest.raises(ValueError, match="sha256 differs"):
        arm.validate_artifact(path, len(payload), "0" * 64, "synthetic")
    with pytest.raises(FileNotFoundError):
        arm.validate_artifact(tmp_path / "missing.bin", 1, digest, "synthetic")


def test_fresh_namespace_and_fresh_output_helpers(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    namespace = root / "docs/research_readiness/.local/new_arm"
    assert arm.require_fresh_namespace(namespace, root) == namespace.resolve()
    namespace.mkdir(parents=True)
    with pytest.raises(PermissionError, match="fresh evaluation namespace"):
        arm.require_fresh_namespace(namespace, root)
    outside = tmp_path / "elsewhere/new_arm"
    with pytest.raises(PermissionError, match="must live under"):
        arm.require_fresh_namespace(outside, root)
    output = tmp_path / "output"
    assert arm.require_fresh_output(output) == output.resolve()
    output.mkdir()
    with pytest.raises(PermissionError, match="fresh evaluation output root"):
        arm.require_fresh_output(output)


def test_clean_tree_helper(tmp_path):
    repo = tmp_path / "git-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "tracked.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=unit@example.invalid",
            "-c",
            "user.name=Unit Test",
            "commit",
            "-m",
            "synthetic",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    assert arm._clean_tree(repo) is True
    (repo / "untracked.txt").write_text("dirty", encoding="utf-8")
    assert arm._clean_tree(repo) is False


def test_approval_field_rejections(tmp_path):
    proposal, private = _fake_proposal_private(tmp_path)
    approval = _fake_approval(proposal, private)
    assert arm.validate_approval(approval, proposal, private)["approved_by_researcher"] is True
    for key, value, message in (
        ("approved_by_researcher", False, "researcher approval flag"),
        ("authorization_scope", "OTHER_SCOPE", "approval scope"),
        ("decision_id", "OTHER_DECISION", "decision id"),
        ("proposal_sha256", "2" * 64, "another proposal"),
        ("code_commit", "b" * 40, "another code commit"),
        ("tasks", ["REAL_s2030"], "task table"),
        ("budget", {"x": 1}, "budget"),
        ("output_root", str(tmp_path / "other"), "output root"),
        ("researcher_instruction", " ", "researcher instruction"),
        ("final_2025_access", True, "2025"),
    ):
        broken = dict(approval)
        broken[key] = value
        with pytest.raises(PermissionError, match=message):
            arm.validate_approval(broken, proposal, private)


def test_seal_self_consistency_and_determinism():
    private = {"a": 1, "nested": {"b": [1, 2, 3]}, "proposal_sha256": "x" * 64}
    assert arm.private_seal(private) == arm.private_seal(
        dict(private, proposal_sha256="y" * 64)
    )
    assert arm.private_seal(private) != arm.private_seal({"a": 2})
    proposal = {"kind": arm.KIND, "budget": {"opens": 32730}, "proposal_sha256": "0" * 64}
    sealed = arm.proposal_seal(proposal)
    assert sealed == arm.proposal_seal(dict(proposal, proposal_sha256="1" * 64))
    assert sealed == hashlib.sha256(
        json.dumps(
            {"kind": arm.KIND, "budget": {"opens": 32730}},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def test_execution_spec_command_and_environment_exactness(tmp_path):
    root = tmp_path / "repo"
    namespace = root / "docs/research_readiness/.local/arm"
    spec = arm.execution_spec(
        root,
        {"proposal_sha256": "1" * 64, "kind": arm.KIND},
        namespace,
    )
    assert spec["kind"] == arm.KIND
    assert spec["cwd"] == str(root.resolve())
    assert spec["service_dir"] == str((namespace / "service").resolve())
    assert spec["command"] == [
        sys.executable,
        "-B",
        str((root / arm.ENTRY).resolve()),
        "execute",
        "--proposal",
        str((namespace / "PROPOSAL.json").resolve()),
        "--private-preparation",
        str((namespace / "PRIVATE_PREPARATION.json").resolve()),
        "--researcher-approval",
        str((namespace / "RESEARCHER_APPROVAL.json").resolve()),
    ]
    assert spec["environment"] == {
        "PYTHONHASHSEED": "2029",
        "PYTHONUTF8": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
    }
    assert spec["proposal_sha256"] == "1" * 64


def test_arrays_retention_spec_and_tiny_shard_roundtrip(tmp_path):
    spec = arm.arrays_retention_spec()
    assert spec["batch_count"] == 121
    assert spec["keys"] == list(arm.ARRAY_KEYS)
    assert spec["keys"] == ["scene_ids", "supervision_mask", "p", "qlog", "truth_mm_h"]
    assert spec["p_dtype"] == "float32"
    assert spec["qlog_dtype"] == "float64"
    assert spec["truth_mm_h_dtype"] == "float32"
    assert spec["supervision_mask_dtype"] == "bool"
    assert spec["per_model_bytes_reference"] == 881_894_762
    assert spec["maximum_total_bytes"] == 4 * 1024**3

    scenes = 2
    height = width = 4
    valid = scenes * height * width
    fields = {
        "scene_ids": np.asarray(["2024-01-01T00", "2024-01-01T06"], dtype="<U25"),
        "supervision_mask": np.ones((scenes, height, width), dtype=bool),
        "p": np.linspace(0.0, 1.0, valid, dtype=np.float32),
        "qlog": np.sort(
            np.random.default_rng(2029).normal(size=(valid, 32)), axis=1
        ).astype(np.float64),
        "truth_mm_h": np.linspace(0.0, 60.0, valid, dtype=np.float32),
    }
    path = tmp_path / "batch_000.npz"
    with path.open("xb") as stream:
        np.savez(stream, **fields)
    loaded = np.load(path, allow_pickle=False)
    assert set(loaded.files) == set(arm.ARRAY_KEYS)
    assert loaded["scene_ids"].dtype == np.dtype("<U25")
    assert loaded["scene_ids"].shape == (scenes,)
    assert loaded["supervision_mask"].dtype == np.dtype(bool)
    assert loaded["supervision_mask"].shape == (scenes, height, width)
    assert loaded["p"].dtype == np.dtype(np.float32)
    assert loaded["p"].shape == (valid,)
    assert loaded["qlog"].dtype == np.dtype(np.float64)
    assert loaded["qlog"].shape == (valid, 32)
    assert loaded["truth_mm_h"].dtype == np.dtype(np.float32)
    loaded.close()


def test_pair_grouping_by_seed():
    assert [pair[0] for pair in arm.PAIRS] == ["REAL_s2030", "REAL_s2031"]
    assert [pair[1] for pair in arm.PAIRS] == ["ZERO_s2030", "ZERO_s2031"]
    assert arm.SEEDS == (2030, 2031)
    for seed, pair in zip(arm.SEEDS, arm.PAIRS):
        assert all(task.endswith(f"s{seed}") for task in pair)


def _fake_terrain(value):
    groups = {}
    for elevation in (
        "elevation_lt_1000m",
        "elevation_1000_to_2000m",
        "elevation_ge_2000m",
    ):
        cells = []
        for index in range(7):
            cells.append(
                {
                    "lower_exclusive": float(index),
                    "upper_inclusive": float(index + 1),
                    "n_rain": 2,
                    "log_pinball_sum": value * 2,
                    "physical_pinball_over20_sum": value * 2,
                    "log_pinball": value,
                    "physical_pinball_over20": value,
                    "q32_covered": 1,
                }
            )
        groups[elevation] = {"n_valid": 10, "n_rain": 14, "brier_sum": 5.0, "cells": cells}
    return {
        "profile": "MOUNTAIN_TERRAIN_PAIR_V1",
        "grid_sha256": "grid",
        "paired_population_sha256": "population",
        "scenes": 2,
        "population": {"n_valid": 10, "n_rain": 14, "n_strong": 6},
        "elevation_groups": groups,
        "scene_statistics": [],
        "scientific_status": "NOT_VERIFIED",
    }


def test_paired_metrics_payload_field_whitelist():
    real = _fake_terrain(0.4)
    zero = _fake_terrain(0.5)
    proposal = {
        "proposal_sha256": "1" * 64,
        "models": [
            {"task": task, "dev_report_sha256": "d" * 64} for task in arm.TASKS
        ],
    }
    report = {"groups": {"all": {"summary": {"scenes": 2, "n_valid": 10}}}}
    payload = arm.paired_metrics_payload(
        proposal,
        "REAL_s2030",
        "ZERO_s2030",
        real,
        zero,
        report,
        report,
        {"scenes": 2},
        {"scenes": 2},
    )
    assert set(payload) == {
        "status",
        "primary_contrast",
        "cells",
        "full_population",
        "point_metrics",
        "source_sha256",
        "paired_population_sha256",
        "evaluation_contract",
        "proposal_sha256",
        "scientific_status",
    }
    assert payload["status"] == "DESCRIPTIVE_MATCHED_MOUNTAIN_EVALUATION"
    assert payload["scientific_status"] == "NOT_VERIFIED"
    assert payload["proposal_sha256"] == "1" * 64
    assert payload["source_sha256"] == {"REAL": "d" * 64, "ZERO": "d" * 64}
    assert set(payload["cells"]) == {
        "elevation_lt_1000m",
        "elevation_1000_to_2000m",
        "elevation_ge_2000m",
    }
    assert all(len(rows) == 7 for rows in payload["cells"].values())
    json.dumps(payload, allow_nan=False)


def test_q1_decision_rule_all_branches():
    reference = -0.0018427840817258874
    reproduced = arm.q1_metric_decision([-0.001, -0.002, -0.0005], reference)
    assert reproduced["same_sign_count"] == 3
    assert reproduced["mean_same_sign"] is True
    assert reproduced["decision"] == "REPRODUCED"

    two_of_three = arm.q1_metric_decision([-0.001, -0.002, 0.0005], reference)
    assert two_of_three["same_sign_count"] == 2
    assert two_of_three["three_seed_mean"] < 0
    assert two_of_three["decision"] == "REPRODUCED"

    partial = arm.q1_metric_decision([-0.001, -0.002, 0.05], reference)
    assert partial["same_sign_count"] == 2
    assert partial["mean_same_sign"] is False
    assert partial["decision"] == "PARTIAL"

    not_reproduced = arm.q1_metric_decision([0.001, 0.002, -0.0001], reference)
    assert not_reproduced["same_sign_count"] == 1
    assert not_reproduced["decision"] == "NOT_REPRODUCED"

    mixed = arm.q1_metric_decision([-0.001, 0.002, 0.003], reference)
    assert mixed["same_sign_count"] == 1
    assert mixed["decision"] == "NOT_REPRODUCED"


def _fake_completion_inputs(tmp_path):
    proposal, private = _fake_proposal_private(tmp_path)
    proposal["proposal_sha256"] = "3" * 64
    proposal["models"] = [
        {
            "task": task,
            "arm": control,
            "seed": seed,
            "model": arm.MODEL,
            "dynamic_control": arm.CONTROLS[control],
            "dev_report_sha256": "d" * 64,
            "dev_report_bytes": 1_885_112,
            "tail_report_sha256": "e" * 64,
            "tail_report_bytes": 1_521_512,
        }
        for task, control, seed in (
            ("REAL_s2030", "REAL", 2030),
            ("ZERO_s2030", "ZERO", 2030),
            ("REAL_s2031", "REAL", 2031),
            ("ZERO_s2031", "ZERO", 2031),
        )
    ]
    results = {}
    for row in proposal["models"]:
        results[row["task"]] = {
            "task": row["task"],
            "arm": row["arm"],
            "seed": row["seed"],
            "status": "COMPLETE",
            "model": arm.MODEL,
            "dynamic_control": row["dynamic_control"],
            "checkpoint_sha256": "c" * 64,
            "checkpoint_bytes": 53_906_437,
            "dev_report_sha256": row["dev_report_sha256"],
            "dev_report_bytes": row["dev_report_bytes"],
            "tail_report_sha256": row["tail_report_sha256"],
            "tail_report_bytes": row["tail_report_bytes"],
            "recomputed_report_sha256": "f" * 64,
            "point_metrics_sha256": "0" * 64,
            "terrain_metrics_sha256": "1" * 64,
            "dev_readout_sha256": "2" * 64,
            "gate": {"passed": True, "groups": {}, "absolute_tolerance": 1e-12,
                     "relative_tolerance": 1e-12},
            "saved_elevation_gate": True,
            "population": {"scenes": 963, "n_valid": 3_303_090,
                           "n_rain": 407_820, "n_strong": 717},
            "forward_calls": 121,
            "arrays_batch_count": 121,
            "arrays_bytes": 881_894_762,
            "arrays_sha256_list": ["a" * 64] * 121,
            "task_scientific_opens": 7_953,
            "task_scientific_bytes": 26_747_379_518,
        }
    paired = {
        2030: {
            "path": str(tmp_path / "paired_metrics_seed2030.json"),
            "sha256": "4" * 64,
            "status": "DESCRIPTIVE_MATCHED_MOUNTAIN_EVALUATION",
            "primary_contrast": {"status": "DIRECTIONAL_LOCAL_IMPROVEMENT", "n_strong": 178,
                                 "real_minus_zero": {"log_pinball": -0.001,
                                                     "physical_pinball_over20": -0.0005}},
            "paired_population_sha256": arm.Q1_REFERENCE_DIGEST,
        },
        2031: {
            "path": str(tmp_path / "paired_metrics_seed2031.json"),
            "sha256": "5" * 64,
            "status": "DESCRIPTIVE_MATCHED_MOUNTAIN_EVALUATION",
            "primary_contrast": {"status": "DIRECTIONAL_LOCAL_IMPROVEMENT", "n_strong": 178,
                                 "real_minus_zero": {"log_pinball": -0.002,
                                                     "physical_pinball_over20": -0.0004}},
            "paired_population_sha256": arm.Q1_REFERENCE_DIGEST,
        },
    }
    metadata = {"metadata_open_instances": 918, "metadata_reserved_bytes": 1_227_801_734}
    return proposal, private, results, paired, metadata


def test_completion_is_json_serializable_without_numpy_scalars(tmp_path):
    proposal, private, results, paired, metadata = _fake_completion_inputs(tmp_path)
    q1 = arm.q1_summary(proposal, paired)
    completion = arm._completion(
        proposal, private, "a" * 40, results, paired, q1, 1234.5, metadata
    )
    text = json.dumps(completion, allow_nan=False)
    assert isinstance(text, str)
    assert completion["status"] == arm.STATUS
    assert completion["kind"] == arm.KIND
    assert completion["scope"] == arm.SCOPE
    assert completion["decision"] == arm.DECISION
    assert completion["scientific_acceptance"] == "NOT_VERIFIED"
    assert completion["final_2025_access"] is False
    assert completion["automatic_retry"] is False
    assert completion["replay"] is False
    assert len(completion["tasks"]) == 4
    assert completion["paired_metrics"]["2030"]["status"] == (
        "DESCRIPTIVE_MATCHED_MOUNTAIN_EVALUATION"
    )
    assert completion["totals"]["optimizer_updates"] == 0
    assert completion["totals"]["checkpoint_loads"] == 4
    assert completion["totals"]["scientific_open_instances"] == 31_812
    assert completion["totals"]["total_open_instances"] == 32_730
    assert completion["totals"]["total_source_bytes"] == 108_217_319_806
    for row in completion["tasks"]:
        assert row["optimizer_updates"] == 0
        assert row["gate"]["passed"] is True
        assert isinstance(row["arrays_sha256_list"], list)


def test_gate_report_pass_and_failure():
    summary = {
        "scenes": 963,
        "n_valid": 10,
        "n_rain": 5,
        "covered": [0, 0],
        "coverage": [0.0, 0.5],
        "brier": 0.25,
        "auroc": 0.9,
        "average_precision": 0.8,
        "conditional_pinball": 0.5,
    }
    reference = {
        "scope": "2024_DEVELOPMENT_FIXED_F006_RETROSPECTIVE",
        "source_identity": {"x": 1},
        "population_ids_sha256": "p" * 64,
        "partition_sha256": "q" * 64,
        "groups": {
            "all": {
                "ids_sha": "i" * 64,
                "complete": True,
                "summary": summary,
            }
        },
    }
    actual = json.loads(json.dumps(reference))
    gate = arm.gate_report(actual, reference)
    assert gate["passed"] is True
    assert gate["groups"]["all"]["frozen_metrics"] == "PASS"
    broken = json.loads(json.dumps(reference))
    broken["groups"]["all"]["summary"]["brier"] = 0.26
    with pytest.raises(ValueError, match="brier differs"):
        arm.gate_report(broken, reference)


def test_saved_elevation_gate_pass_and_failure():
    def terrain_for(value):
        groups = {}
        for elevation in (
            "elevation_lt_1000m",
            "elevation_1000_to_2000m",
            "elevation_ge_2000m",
        ):
            groups[elevation] = {
                "n_valid": 10,
                "n_rain": 5,
                "brier_sum": 5.0,
                "cells": [{"log_pinball_sum": value * 5 / 7} for _ in range(7)],
            }
        return {
            "profile": "MOUNTAIN_TERRAIN_PAIR_V1",
            "population": {"n_strong": arm.DATA_SCOPE["n_strong"]},
            "elevation_groups": groups,
        }

    tail = {
        "elevation_diagnostics": {
            "bins": {
                elevation: {"n_valid": 10, "n_rain": 5, "brier": 0.5,
                            "conditional_pinball": 0.5}
                for elevation in (
                    "elevation_lt_1000m",
                    "elevation_1000_to_2000m",
                    "elevation_ge_2000m",
                )
            }
        }
    }
    gate = arm.saved_elevation_gate(terrain_for(0.5), tail)
    assert gate["passed"] is True
    with pytest.raises(ValueError, match="conditional pinball differs"):
        arm.saved_elevation_gate(terrain_for(0.4), tail)


def test_task_worker_rejects_an_unknown_index():
    with pytest.raises(ValueError, match="task index"):
        arm.task_worker(ROOT, {"models": []}, {}, {}, "0" * 40, 4)


def test_task_worker_rejects_a_foreign_hash_seed(monkeypatch):
    proposal = {
        "scope": arm.SCOPE,
        "models": [
            {
                "task": "REAL_s2030",
                "seed": 2030,
                "arm": "REAL",
                "dynamic_control": "REAL_PHYSICAL_DOTE",
            }
        ],
        "proposal_sha256": "0" * 64,
        "private_preparation_sha256": "1" * 64,
        "decision": arm.DECISION,
        "execution_code_commit": "2" * 40,
        "tasks": list(arm.TASKS),
    }
    monkeypatch.setenv("PYTHONHASHSEED", "2029")
    with pytest.raises(PermissionError, match="hash seed"):
        arm.task_worker(
            ROOT,
            proposal,
            {"proposal_sha256": "0" * 64},
            {"approved_by_researcher": True},
            "2" * 40,
            0,
        )


def test_task_check_accepts_a_reservation_and_enforces_the_output_cap(tmp_path):
    deadline = arm.Deadline(60)
    assert arm._task_check(tmp_path, deadline) is None
    assert arm._task_check(tmp_path, deadline, 0) is None
    with pytest.raises(MemoryError, match="output reserve"):
        arm._task_check(
            tmp_path, deadline, arm.BUDGET["maximum_output_bytes"] + 1
        )
    (tmp_path / "payload.bin").write_bytes(b"x" * 8)
    with pytest.raises(MemoryError, match="output reserve"):
        arm._task_check(tmp_path, deadline, arm.BUDGET["maximum_output_bytes"] - 1)
    assert arm._task_check(tmp_path, deadline, 1) is None
    expired = arm.Deadline(0)
    with pytest.raises(ValueError, match="time cap"):
        arm._task_check(tmp_path, expired)


def test_development_readout_uses_the_task_check_with_a_reservation(tmp_path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.research_readiness.conditional_intensity_readout import DevelopmentReadout

    identity = {
        "supervision_mask_sha256": "a" * 64,
        "n_rain": 0,
        "n_strong": 0,
    }
    ids = ("2024-01-01T00:00:00+00:00",)
    valid = np.ones((1, 1, 100, 100), dtype=np.bool_)
    region = np.ones((1, 1, 100, 100), dtype=np.bool_)
    rate = np.zeros((1, 1, 100, 100), dtype=np.float32)
    probability = np.full((1, 1, 100, 100), 0.5, dtype=np.float32)
    nodes = np.log1p(np.arange(1, 33, dtype=np.float64)).reshape(1, 32, 1, 1)
    quantiles_log = np.broadcast_to(nodes, (1, 32, 100, 100)).copy()
    deadline = arm.Deadline(60)
    folder = tmp_path / "task"
    readout = DevelopmentReadout(
        folder,
        ids,
        identity,
        lambda reserve_bytes=None: arm._task_check(tmp_path, deadline, reserve_bytes),
        valid_per_scene=10000,
    )
    readout.add(ids, rate, valid, region, probability, quantiles_log)
    summary = readout.finish("a" * 64)
    assert summary["storage"]["files"][0]["bytes"] > 0
    assert summary["n_valid"] == 10000
