"""Stage-4 package A: four-model COSINE9 REAL/ZERO fixed-E9 Dev evaluation.

This module is the bounded, approval-gated evaluation arm described by
``docs/research_readiness/20261121_stage45_observation_feasibility/``
``STAGE45_STEP4_EVALUATION_PREREGISTRATION_V1.md`` (A package).  It is
deliberately torch-free at import time: the numerical runtime is imported
lazily inside :func:`execute` so the deterministic preparation helpers and
the unit tests can run under a plain CPython interpreter.

The arm only evaluates already frozen epoch-9 LAST checkpoints.  It never
trains, never updates an optimizer, never retries and never replays a failed
task.  All results are descriptive and carry ``scientific_status``
``NOT_VERIFIED``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KIND = "BOUNDED_STAGE4_MULTISEED_DEV_EVALUATION"
SCOPE = "FOUR_MODEL_COSINE9_REAL_ZERO_DEV_MOUNTAIN_EVALUATION_V1"
STATUS = "COMPLETE_STAGE4_MULTISEED_DEV_EVALUATION"
DECISION = "DESCRIPTIVE_MULTISEED_REAL_ZERO_DEV_EVALUATION"
ENTRY = "tools/research_readiness/start_multiseed_dev_evaluation.py"
MODULE = "yuntapr.experimental.research_readiness.multiseed_dev_evaluation"

MODEL = "B7"
ARMS = ("REAL", "ZERO")
SEEDS = (2030, 2031)
CONTROLS = {
    "REAL": "REAL_PHYSICAL_DOTE",
    "ZERO": "ZERO_NUMERIC_RETAIN_REAL_MASKS",
}


def task_name(arm, seed):
    return f"{arm}_s{int(seed)}"


#: Required task order: REAL@2030, ZERO@2030, REAL@2031, ZERO@2031.
TASKS = tuple(task_name(arm, seed) for seed in SEEDS for arm in ARMS)

PAIRS = tuple((task_name("REAL", seed), task_name("ZERO", seed)) for seed in SEEDS)

MIB = 1024 * 1024
GIB = 1024 * MIB

#: Frozen budget envelope copied from the pre-registration.  These numbers are
#: caps, not measurements: ``execute`` records the measured totals separately.
BUDGET = {
    "kind": KIND,
    "model": MODEL,
    "tasks": 4,
    "total_scientific_file_opens": 32730,
    "total_scientific_source_bytes": 108217319806,
    "payload_open_instances": 31812,
    "payload_archive_reference_bytes": 106989518072,
    "metadata_open_instances": 918,
    "metadata_archive_reference_bytes": 1227801734,
    "per_task_payload_open_instances": 7953,
    "per_task_payload_reference_bytes": 26747379518,
    "per_task_metadata_open_instances": 459,
    "per_task_metadata_reference_bytes": 306950433,
    "development_files": 7950,
    "development_bytes": 26639253112,
    "development_opens_per_task": 7950,
    "static_bytes": 312828,
    "static_opens_per_task": 1,
    "checkpoint_opens_per_task": 2,
    "checkpoint_loads": 4,
    "model_inference_passes": 4,
    "forward_batches_per_model": 121,
    "optimizer_updates": 0,
    "retrains": 0,
    "refits": 0,
    "retries": 0,
    "replays": 0,
    "maximum_seconds": 7200,
    "minimum_free_bytes": 8 * GIB,
    "maximum_output_bytes": 4 * GIB,
    "development_scenes": 963,
    "development_batches": 121,
    "validation_batch": 8,
    "arrays_batch_count_per_model": 121,
}

#: Frozen per-task checkpoint reservation used by the pre-registered envelope.
#: The four real files are 53,906,4xx-53,906,8xx B; their package total is
#: still below ``total_scientific_source_bytes``.
CHECKPOINT_REFERENCE_BYTES = 53906789

#: Closed 2024 Development population inherited by every arm.
DATA_SCOPE = {
    "role": "Development",
    "year": 2024,
    "scenes": 963,
    "n_valid": 3303090,
    "n_rain": 407820,
    "n_strong": 717,
    "population_ids_sha256": (
        "916302412bf024942aadeefe969d12c74452481ef24dedc30b1262b24609cf76"
    ),
    "partition_sha256": (
        "01b95f12d26a3f6f4ff05620414cdae66c5cec23bd2808b0af2de40e4615291c"
    ),
    "supervision_mask_sha256": (
        "70368bec3149e998922d565dab83347ba33f465df481a03ac3f90b85f1286d4b"
    ),
}

PARENT_PROPOSAL_SHA256 = (
    "cd5948b67e07ce7231d4502e73613bbe8bdb6cc3c90b63f97299ae7da0f7c6b2"
)
PARENT_PROPOSAL_FILE_SHA256 = (
    "0648beb61b64cf99110e10edf7dd17f343bbe5ce8844b01c9ad297a8e5216a43"
)
PARENT_PROPOSAL_KIND = "BOUNDED_TRAIN_COSINE9_MULTISEED_TERRAIN"
PARENT_PACKAGE_STATUS = "COMPLETE_FOUR_TASK_COSINE9_REAL_ZERO_MULTISEED"

STATIC_TERRAIN_PATH = Path(
    r"F:\pytorch\Research\YunTAPR_static_terrain_candidate_20261027_v1"
)
STATIC_SOURCE_NAME = "b6_static.npz"
STATIC_SOURCE_BYTES = 312828
STATIC_SOURCE_SHA256 = (
    "788572b1e82ba388d6ddcd6b1f8a987af818f44cdde9d5d613db5d35af5281bd"
)
STATIC_RECEIPT_NAME = "production_receipt.json"

FINAL_2025_ACCESS = False
SOURCE_VOLUME = Path(r"H:\葵花202303_202510")

Q1_REFERENCE_RELATIVE = (
    "docs/research_readiness/.local/mountain_pair_evaluation_v1/paired_metrics.json"
)
Q1_REFERENCE_DIGEST = "056ae0d9168dd572383543e652b4f49462b868643d19d6dab0babc1ec21a18ba"
Q1_2029_LOG = -0.0018427840817258874
Q1_2029_PHYSICAL = -0.0006961972905197065
Q1_2029_N_STRONG = 178

FROZEN_GROUP_KEYS = (
    "all",
    "analysis_UTC_00",
    "analysis_UTC_06",
    "analysis_UTC_12",
    "analysis_UTC_18",
    "scene_max_ge20",
)
FROZEN_METRIC_TOLERANCE = 1e-12

ARRAY_KEYS = ("scene_ids", "supervision_mask", "p", "qlog", "truth_mm_h")
ARRAY_SHARD_PATTERN = "batch_{index:03d}.npz"
ARRAY_SCENES_PER_SHARD = 8
ARRAY_SHARDS_PER_MODEL = 121
ARRAY_BYTES_REFERENCE_PER_MODEL = 881894762

PRIVATE_ROOT = Path("docs/research_readiness/.local")


def arrays_retention_spec():
    return {
        "folder": "arrays/{arm}_s{seed}",
        "shard_pattern": ARRAY_SHARD_PATTERN,
        "batch_count": ARRAY_SHARDS_PER_MODEL,
        "scenes_per_shard": ARRAY_SCENES_PER_SHARD,
        "keys": list(ARRAY_KEYS),
        "scene_ids_dtype": "<U25",
        "supervision_mask_dtype": "bool",
        "p_dtype": "float32",
        "qlog_dtype": "float64",
        "truth_mm_h_dtype": "float32",
        "per_model_bytes_reference": ARRAY_BYTES_REFERENCE_PER_MODEL,
        "maximum_total_bytes": BUDGET["maximum_output_bytes"],
        "provenance": "docs/research_readiness/.local/b_readout_prepare_20261120_v2",
        "scientific_status": "NOT_VERIFIED",
    }


def terrain_contract():
    """The frozen ``MOUNTAIN_TERRAIN_PAIR_V1`` contract, imported lazily."""

    from tools.research_readiness.mountain_pair_metrics import CONTRACT

    return CONTRACT


# ---------------------------------------------------------------------------
# Deterministic primitives
# ---------------------------------------------------------------------------


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def digest(value):
    """Canonical JSON digest used for every proposal/private self seal."""

    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def write(path, value):
    path = Path(path)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def private_seal(private):
    return digest({key: value for key, value in private.items() if key != "proposal_sha256"})


def proposal_seal(proposal):
    return digest({key: value for key, value in proposal.items() if key != "proposal_sha256"})


def _require(condition, message, kind=ValueError):
    if not condition:
        raise kind(message)


def _absolute(path):
    return Path(os.path.abspath(os.fsdecode(path)))


def _git(root, *arguments, text=True):
    import subprocess

    return subprocess.check_output(
        ["git", "-C", str(root), *arguments], text=text, stderr=subprocess.STDOUT
    ).strip()


def _git_head(root):
    return _git(root, "rev-parse", "HEAD")


def _clean_tree(root):
    return _git(root, "status", "--porcelain") == ""


def _free_bytes(path):
    path = Path(path)
    while not path.exists():
        if path.parent == path:
            raise FileNotFoundError(f"No existing ancestor for {path}")
        path = path.parent
    return shutil.disk_usage(path).free


def runtime_binding():
    """Identity of the interpreter that may execute this arm (rain-basics)."""

    import numpy
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required to bind the evaluation runtime")
    device = torch.cuda.current_device()
    properties = torch.cuda.get_device_properties(device)
    version = sys.version_info
    return {
        "python_version": f"{version.major}.{version.minor}.{version.micro}",
        "python_executable_sha256": sha(Path(sys.executable).resolve()),
        "torch_version": torch.__version__,
        "cuda_build": torch.version.cuda,
        "numpy_version": numpy.__version__,
        "gpu_name": properties.name,
        "gpu_total_bytes": int(properties.total_memory),
    }


def code_hashes(root):
    root = Path(root)
    paths = list((root / "src").rglob("*.py"))
    for relative in (
        ENTRY,
        "tools/research_readiness/start_independent_process.py",
        "tools/research_readiness/mountain_pair_metrics.py",
        "tools/research_readiness/paired_point_metrics.py",
        "tools/research_readiness/conditional_intensity_readout.py",
        "tools/research_readiness/extreme_diagnostic_candidates.py",
    ):
        candidate = root / relative
        if candidate.is_file():
            paths.append(candidate)
    hashes = {}
    for path in sorted(set(paths)):
        hashes[path.relative_to(root).as_posix()] = sha(path)
    return hashes


def execution_spec(root, proposal, namespace):
    root = Path(root)
    namespace = Path(namespace)
    return {
        "kind": KIND,
        "cwd": str(root.resolve()),
        "service_dir": str((namespace / "service").resolve()),
        "command": [
            str(Path(sys.executable).resolve()),
            "-B",
            str((root / ENTRY).resolve()),
            "execute",
            "--proposal",
            str((namespace / "PROPOSAL.json").resolve()),
            "--private-preparation",
            str((namespace / "PRIVATE_PREPARATION.json").resolve()),
            "--researcher-approval",
            str((namespace / "RESEARCHER_APPROVAL.json").resolve()),
        ],
        "environment": {
            "PYTHONHASHSEED": "2029",
            "PYTHONUTF8": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
        },
        "proposal_sha256": proposal["proposal_sha256"],
    }


# ---------------------------------------------------------------------------
# Artifact validators (shared by prepare, checked and the unit tests)
# ---------------------------------------------------------------------------


def artifact_identity(path):
    path = Path(path)
    _require(path.is_file(), f"Missing frozen artifact: {path}", FileNotFoundError)
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def validate_artifact(path, expected_bytes, expected_sha256, label):
    path = Path(path)
    _require(path.is_file(), f"{label} is missing: {path}", FileNotFoundError)
    observed_bytes = path.stat().st_size
    _require(
        observed_bytes == int(expected_bytes),
        f"{label} byte size differs: {observed_bytes} != {expected_bytes}",
    )
    observed_sha = sha(path)
    _require(
        observed_sha == str(expected_sha256).lower(),
        f"{label} sha256 differs: {observed_sha} != {expected_sha256}",
    )
    return {"bytes": observed_bytes, "sha256": observed_sha}


def require_fresh_namespace(namespace, root):
    namespace = _absolute(namespace)
    private = (_absolute(root) / PRIVATE_ROOT).resolve()
    try:
        namespace.resolve().relative_to(private)
    except ValueError as error:
        raise PermissionError(
            f"The evaluation namespace must live under {private}"
        ) from error
    if namespace.exists():
        raise PermissionError("A fresh evaluation namespace is required")
    return namespace


def require_fresh_output(output_root):
    output_root = _absolute(output_root)
    if output_root.exists():
        raise PermissionError("A fresh evaluation output root is required")
    if not output_root.parent.is_dir():
        raise PermissionError("The evaluation output parent must already exist")
    return output_root


def validate_approval(approval, proposal, private, commit=None):
    """Field-level researcher approval gate (same shape as the 2029 arm)."""

    _require(isinstance(approval, dict), "The researcher approval must be an object", PermissionError)
    if approval.get("approved_by_researcher") is not True:
        raise PermissionError("The researcher approval flag is absent")
    if approval.get("authorization_scope") != proposal["scope"]:
        raise PermissionError("The approval scope differs from the proposal")
    if approval.get("decision_id") != proposal["decision"]:
        raise PermissionError("The approval decision id differs from the proposal")
    if approval.get("proposal_sha256") != proposal["proposal_sha256"]:
        raise PermissionError("The approval binds another proposal")
    if str(approval.get("code_commit", "")).lower() != str(
        proposal.get("execution_code_commit", "")
    ).lower():
        raise PermissionError("The approval binds another code commit")
    if commit is not None and str(commit).lower() != str(approval["code_commit"]).lower():
        raise PermissionError("The checked-out commit differs from the approval")
    if list(approval.get("tasks", ())) != list(TASKS):
        raise PermissionError("The approval task table differs from the proposal")
    if approval.get("scientific_choices") != proposal["scientific_choices"]:
        raise PermissionError("The approval scientific choices differ from the proposal")
    if approval.get("budget") != proposal["budget"]:
        raise PermissionError("The approval budget differs from the proposal")
    if str(approval.get("output_root", "")) != str(private["output_root"]):
        raise PermissionError("The approval output root differs from the private plan")
    if not isinstance(approval.get("researcher_instruction"), str) or not approval[
        "researcher_instruction"
    ].strip():
        raise PermissionError("The approval is not tied to a researcher instruction")
    if approval.get("final_2025_access") is not False:
        raise PermissionError("The approval must keep the 2025 final test sealed")
    return {"approved_by_researcher": True, "code_commit": approval["code_commit"]}


# ---------------------------------------------------------------------------
# Preparation
# ---------------------------------------------------------------------------


def _validate_parent_proposal(parent_path):
    parent_path = Path(parent_path)
    parent = read(parent_path)
    file_sha = sha(parent_path)
    _require(
        file_sha == PARENT_PROPOSAL_FILE_SHA256,
        f"The inherited V4 proposal file sha differs: {file_sha}",
    )
    canonical = proposal_seal(parent)
    _require(
        canonical == PARENT_PROPOSAL_SHA256,
        f"The inherited V4 proposal canonical sha differs: {canonical}",
    )
    _require(parent.get("kind") == PARENT_PROPOSAL_KIND, "The inherited kind differs")
    _require(
        parent.get("authorization_scope")
        == "FOUR_TASK_COSINE9_REAL_ZERO_SEED2030_2031",
        "The inherited authorization scope differs",
    )
    _require(parent.get("final_2025_access") is False, "The inherited proposal does not seal 2025")
    inherited_tasks = [(row["arm"], int(row["seed"])) for row in parent["tasks"]]
    _require(
        inherited_tasks == [("REAL", 2030), ("ZERO", 2030), ("REAL", 2031), ("ZERO", 2031)],
        "The inherited V4 task table differs",
    )
    return parent, file_sha


def _validate_parent_private(parent_private, parent_proposal, parent_sha):
    parent_private = read(parent_private)
    _require(
        parent_private.get("proposal_sha256") == parent_sha,
        "The inherited private preparation points at another proposal",
    )
    inherited_path = Path(parent_private["inherited"])
    inherited_sha = sha(inherited_path)
    _require(
        inherited_sha == parent_private["inherited_file_sha256"],
        "The inherited B2 preparation changed",
    )
    wrapper = read(inherited_path)
    prepared = wrapper.get("prepared")
    _require(isinstance(prepared, dict), "The inherited preparation has no prepared block")
    _require(
        prepared.get("data") == parent_proposal["data_identity"],
        "The inherited data identity differs from the V4 proposal",
    )
    role = prepared["roles"]["Development"]
    _require(
        int(role["file_count"]) == BUDGET["development_files"]
        and int(role["bytes_per_pass"]) == BUDGET["development_bytes"],
        "The inherited Development source scope differs",
    )
    ids = tuple(role["ids"])
    _require(len(ids) == DATA_SCOPE["scenes"], "The inherited Development scene count differs")
    _require(all(str(scene).startswith("2024-") for scene in ids), "Development ids are not 2024")
    _require(len(set(ids)) == len(ids), "Duplicate Development ids")
    return parent_private, wrapper, prepared, ids


def _validate_package(package_root, parent_proposal):
    package_root = Path(package_root)
    completion_path = package_root / "completion.json"
    completion = read(completion_path)
    completion_sha = sha(completion_path)
    _require(completion.get("status") == PARENT_PACKAGE_STATUS, "The V4 package is not complete")
    _require(completion.get("kind") == PARENT_PROPOSAL_KIND, "The V4 package kind differs")
    totals = completion.get("totals", {})
    _require(
        (totals.get("tasks_completed"), totals.get("updates"),
         totals.get("source_bytes"), totals.get("source_files"))
        == (4, 17280, 1910287815360, 571252),
        "The V4 package totals differ",
    )
    _require(completion.get("automatic_retry") is False, "The V4 package used automatic retry")
    _require(completion.get("replay") is False, "The V4 package used replay")
    pairing = completion.get("pairing", {})
    for seed in SEEDS:
        block = pairing.get(str(seed), {})
        _require(
            block.get("pairing") == "IDENTICAL_SEED_DRIVEN_ORIGINAL_STATE_AND_EPOCH_ORDER",
            f"The V4 seed {seed} pairing differs",
        )
        _require(
            block.get("real_source_bytes") == 477571953840
            and block.get("zero_source_bytes") == 477571953840,
            f"The V4 seed {seed} paired source bytes differ",
        )
    by_key = {(row["arm"], int(row["seed"])): row for row in completion["tasks"]}
    _require(len(by_key) == 4, "The V4 completion does not hold four tasks")
    return completion_path, completion, completion_sha, by_key


def _task_folder(package_root, arm, seed):
    return Path(package_root) / f"{arm}_s{seed}" / f"B7_s{seed}"


def _validate_task(arm, seed, folder, completion_task, parent_proposal):
    folder = Path(folder)
    checkpoint = folder / "B7_LAST_epoch_09.pt"
    receipt_path = folder / "B7_LAST_epoch_09.receipt.json"
    dev_report = folder / "B7_development_09.json"
    tail_report = folder / "B7_tail_09.json"
    task_completion_path = folder / "completion.json"
    task_receipt_path = folder / "task_receipt.json"

    for path in (checkpoint, receipt_path, dev_report, tail_report,
                 task_completion_path, task_receipt_path):
        _require(path.is_file(), f"Missing V4 task artifact: {path}", FileNotFoundError)

    receipt = read(receipt_path)
    _require(receipt.get("model") == MODEL, "The checkpoint receipt model differs")
    _require(int(receipt.get("epoch")) == 9, "The checkpoint receipt epoch differs")
    _require(int(receipt.get("updates")) == 4320, "The checkpoint receipt updates differ")
    _require(
        receipt.get("population_sha256") == parent_proposal["data_identity"]["population_sha256"],
        "The checkpoint receipt population differs",
    )
    checkpoint_bytes = checkpoint.stat().st_size
    checkpoint_sha = sha(checkpoint)
    _require(
        checkpoint_sha == receipt.get("checkpoint_sha256"),
        "The checkpoint differs from its receipt",
    )
    task_completion = read(task_completion_path)
    _require(
        task_completion.get("status") == "COMPLETE_TRAIN_AND_DEV_EVALUATION",
        "The V4 task completion status differs",
    )
    _require(int(task_completion.get("epochs")) == 9, "The V4 task epochs differ")
    _require(int(task_completion.get("optimizer_updates")) == 4320, "The V4 updates differ")
    _require(task_completion.get("replay") == 0, "The V4 task used replay")
    _require(task_completion.get("endpoint") == "FIXED_EPOCH_9_LAST", "The V4 endpoint differs")
    saved = task_completion["checkpoints"][-1]
    _require(int(saved["epoch"]) == 9, "The saved checkpoint list does not end at epoch 9")
    _require(
        saved["checkpoint_sha256"] == checkpoint_sha,
        "The checkpoint differs from the V4 task completion list",
    )

    task_receipt = read(task_receipt_path)
    _require(task_receipt.get("arm") == arm, "The V4 task receipt arm differs")
    _require(int(task_receipt.get("seed")) == int(seed), "The V4 task receipt seed differs")
    _require(
        task_receipt.get("dynamic_control") == CONTROLS[arm],
        "The V4 task receipt dynamic control differs",
    )
    _require(
        task_receipt.get("initial_full_state_sha256")
        == completion_task.get("initial_full_state_sha256"),
        "The V4 seed-pair initial state differs",
    )
    _require(task_receipt.get("replay") == 0, "The V4 task receipt replay differs")
    _require(
        task_receipt.get("automatic_retry") is False,
        "The V4 task receipt automatic retry differs",
    )

    dev = read(dev_report)
    tail = read(tail_report)
    _require(
        dev.get("population_ids_sha256") == DATA_SCOPE["population_ids_sha256"],
        "The Dev report population identity differs",
    )
    _require(
        dev.get("partition_sha256") == DATA_SCOPE["partition_sha256"],
        "The Dev report partition identity differs",
    )
    summary = dev["groups"]["all"]["summary"]
    _require(int(summary["scenes"]) == DATA_SCOPE["scenes"], "The Dev report scenes differ")
    _require(int(summary["n_valid"]) == DATA_SCOPE["n_valid"], "The Dev report n_valid differs")
    _require(int(summary["n_rain"]) == DATA_SCOPE["n_rain"], "The Dev report n_rain differs")
    _require(
        tail.get("elevation_diagnostics", {}).get("bins") is not None,
        "The tail report holds no elevation diagnostics",
    )

    return {
        "task": task_name(arm, seed),
        "arm": arm,
        "model": MODEL,
        "seed": int(seed),
        "dynamic_control": CONTROLS[arm],
        "role": "Development",
        "year": 2024,
        "epochs": 9,
        "updates": 4320,
        "endpoint": "FIXED_EPOCH_9_LAST",
        "checkpoint_path": str(checkpoint),
        "checkpoint_bytes": checkpoint_bytes,
        "checkpoint_sha256": checkpoint_sha,
        "dev_report_path": str(dev_report),
        "dev_report_bytes": dev_report.stat().st_size,
        "dev_report_sha256": sha(dev_report),
        "tail_report_path": str(tail_report),
        "tail_report_bytes": tail_report.stat().st_size,
        "tail_report_sha256": sha(tail_report),
        "task_completion_path": str(task_completion_path),
        "task_completion_sha256": sha(task_completion_path),
        "task_receipt_path": str(task_receipt_path),
        "task_receipt_sha256": sha(task_receipt_path),
    }


def _scientific_manifest(tasks, prepared, static_source, static_sha, static_bytes):
    role = prepared["roles"]["Development"]
    manifest = {}
    for path, meta in role["files"].items():
        key = str(path)
        manifest[key] = {
            "bytes": int(meta["bytes"]),
            "sha256": str(meta["sha"]).lower(),
            "category": "weather",
            "tasks": list(TASKS),
            "opens_per_task": 1,
        }
    _require(len(manifest) == BUDGET["development_files"], "The weather manifest file count differs")
    manifest[str(static_source)] = {
        "bytes": static_bytes,
        "sha256": static_sha,
        "category": "static",
        "tasks": list(TASKS),
        "opens_per_task": 1,
    }
    for row in tasks:
        manifest[row["checkpoint_path"]] = {
            "bytes": CHECKPOINT_REFERENCE_BYTES,
            "sha256": row["checkpoint_sha256"],
            "category": "checkpoint",
            "tasks": [row["task"]],
            "opens_per_task": 2,
        }
    opens = sum(
        len(entry["tasks"]) * int(entry["opens_per_task"]) for entry in manifest.values()
    )
    bytes_total = sum(
        int(entry["bytes"]) * len(entry["tasks"]) * int(entry["opens_per_task"])
        for entry in manifest.values()
    )
    _require(
        opens == BUDGET["payload_open_instances"],
        "The scientific open total differs from the frozen payload envelope",
    )
    _require(
        bytes_total == BUDGET["payload_archive_reference_bytes"],
        "The scientific source bytes exceed the frozen payload envelope",
    )
    return manifest, opens, bytes_total


def _metadata_manifest(paths):
    manifest = {}
    for path in sorted({str(Path(p)) for p in paths}):
        if Path(path).is_file():
            manifest[path] = {"bytes": Path(path).stat().st_size, "sha256": sha(Path(path))}
    return manifest


def _q1_reference(root):
    path = Path(root) / Q1_REFERENCE_RELATIVE
    _require(path.is_file(), "The frozen 2029 paired metrics reference is missing", FileNotFoundError)
    value = read(path)
    _require(
        value.get("evaluation_contract", {}).get("profile") == "MOUNTAIN_TERRAIN_PAIR_V1",
        "The 2029 reference contract differs",
    )
    contrast = value["primary_contrast"]
    _require(
        contrast["real_minus_zero"]["log_pinball"] == Q1_2029_LOG
        and contrast["real_minus_zero"]["physical_pinball_over20"] == Q1_2029_PHYSICAL
        and int(contrast["n_strong"]) == Q1_2029_N_STRONG,
        "The 2029 primary contrast values differ",
    )
    _require(
        value.get("paired_population_sha256") == Q1_REFERENCE_DIGEST,
        "The 2029 paired population digest differs",
    )
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "file_sha256": sha(path),
        "paired_population_sha256": Q1_REFERENCE_DIGEST,
        "proposal_sha256": value.get("proposal_sha256"),
        "status": value.get("status"),
        "n_strong": Q1_2029_N_STRONG,
        "real_minus_zero": {
            "log_pinball": Q1_2029_LOG,
            "physical_pinball_over20": Q1_2029_PHYSICAL,
        },
        "scientific_status": "NOT_VERIFIED",
    }


def prepare(
    root,
    parent_proposal,
    parent_private,
    package_root,
    output_root,
    *,
    runtime=None,
    head=None,
    service_dir=None,
    runtime_python=None,
):
    """Build the deterministic public proposal and private preparation."""

    root = Path(root).resolve()
    parent_proposal = Path(parent_proposal).resolve()
    parent_private = Path(parent_private).resolve()
    package_root = Path(package_root).resolve()
    output_root = _absolute(output_root)
    if output_root.exists():
        raise PermissionError("A fresh evaluation output root is required")
    if not output_root.parent.is_dir():
        raise PermissionError("The evaluation output parent must already exist")
    if not Path(parent_private).is_file():
        raise FileNotFoundError(f"Missing parent private preparation: {parent_private}")

    parent, parent_file_sha = _validate_parent_proposal(parent_proposal)
    parent_private_value, wrapper, prepared, ids = _validate_parent_private(
        parent_private, parent, PARENT_PROPOSAL_SHA256
    )
    completion_path, completion, completion_sha, completion_tasks = _validate_package(
        package_root, parent
    )

    rows = []
    private_tasks = {}
    for arm, seed in ((row["arm"], int(row["seed"])) for row in parent["tasks"]):
        folder = _task_folder(package_root, arm, seed)
        row = _validate_task(
            arm, seed, folder, completion_tasks[(arm, seed)], parent
        )
        rows.append(row)
        private_tasks[row["task"]] = row
    _require(
        tuple(row["task"] for row in rows) == TASKS,
        "The frozen V4 task order differs",
    )

    terrain = Path(parent_private_value["terrain"])
    static_source = terrain / STATIC_SOURCE_NAME
    static_receipt = terrain / STATIC_RECEIPT_NAME
    validate_artifact(
        static_source, STATIC_SOURCE_BYTES, STATIC_SOURCE_SHA256, "B6 static source"
    )
    _require(static_receipt.is_file(), "The static terrain receipt is missing", FileNotFoundError)

    scientific, scientific_opens, scientific_bytes = _scientific_manifest(
        rows, prepared, static_source, STATIC_SOURCE_SHA256, STATIC_SOURCE_BYTES
    )
    metadata_paths = [
        parent_proposal,
        parent_private,
        Path(parent_private_value["inherited"]),
        completion_path,
        static_receipt,
        Path(prepared["private_inputs"]["request"]),
        Path(prepared["private_inputs"]["stage3_run"]) / "populations.json",
        Path(prepared["private_inputs"]["stage3_run"]) / "train_statistics.json",
        Path(prepared["private_inputs"]["stage3_run"]) / "statistics.sqlite",
    ]
    for row in rows:
        metadata_paths.extend(
            [
                Path(row["dev_report_path"]),
                Path(row["tail_report_path"]),
                Path(row["task_completion_path"]),
                Path(row["task_receipt_path"]),
                Path(row["checkpoint_path"]).with_suffix(".receipt.json"),
            ]
        )
    metadata = _metadata_manifest(metadata_paths)
    _require(
        len(metadata) <= BUDGET["metadata_open_instances"],
        "The metadata manifest exceeds the frozen open budget",
    )
    metadata_bytes = sum(entry["bytes"] for entry in metadata.values())
    _require(
        metadata_bytes <= BUDGET["metadata_archive_reference_bytes"],
        "The metadata manifest exceeds the frozen byte budget",
    )

    resolved_runtime = runtime if runtime is not None else runtime_binding()
    _require(
        resolved_runtime.get("python_executable_sha256")
        == "0562f573871cb16a2fb8de16e3d486e3dfd74bb83c7e87db265561917d05ad1a",
        "The preparation interpreter is not the approved rain-basics python",
    )
    code_commit = head if head is not None else _git_head(root)
    reviewed_code = code_hashes(root)

    private = {
        "kind": KIND,
        "scope": SCOPE,
        "code_root": str(root),
        "output_root": str(output_root),
        "parent_proposal": str(parent_proposal),
        "parent_proposal_sha256": PARENT_PROPOSAL_SHA256,
        "parent_private": str(parent_private),
        "parent_package_root": str(package_root),
        "preparation_path": str(Path(parent_private_value["inherited"])),
        "service_dir": str(Path(service_dir).resolve()) if service_dir is not None else None,
        "runtime_python": str(
            Path(runtime_python).resolve() if runtime_python is not None else Path(sys.executable).resolve()
        ),
        "prepared_private_inputs": dict(prepared["private_inputs"]),
        "static_source": str(static_source),
        "static_receipt": str(static_receipt),
        "static_sha256": STATIC_SOURCE_SHA256,
        "tasks": private_tasks,
        "task_payload_caps": {
            row["task"]: max(
                BUDGET["per_task_payload_reference_bytes"],
                BUDGET["development_bytes"]
                + BUDGET["static_bytes"]
                + 2 * int(row["checkpoint_bytes"]),
            )
            for row in rows
        },
        "scientific_files": scientific,
        "metadata_files": metadata,
        "q1_reference": _q1_reference(root),
        "execution_commit": code_commit,
    }
    private["proposal_sha256"] = None

    proposal = {
        "kind": KIND,
        "scope": SCOPE,
        "decision": DECISION,
        "status": "READY_WAITING_EXACT_RESEARCHER_APPROVAL",
        "authorized": False,
        "authorization_scope": SCOPE,
        "final_2025_access": FINAL_2025_ACCESS,
        "final_2025_status": "SEALED_NOT_ACCESSED",
        "scientific_status": "NOT_VERIFIED",
        "tasks": [row["task"] for row in rows],
        "models": [
            {
                "task": row["task"],
                "arm": row["arm"],
                "model": MODEL,
                "seed": row["seed"],
                "role": row["role"],
                "year": row["year"],
                "epochs": row["epochs"],
                "updates": row["updates"],
                "endpoint": row["endpoint"],
                "dynamic_control": row["dynamic_control"],
                "checkpoint_path": row["checkpoint_path"],
                "checkpoint_bytes": row["checkpoint_bytes"],
                "checkpoint_sha256": row["checkpoint_sha256"],
                "dev_report_path": row["dev_report_path"],
                "dev_report_bytes": row["dev_report_bytes"],
                "dev_report_sha256": row["dev_report_sha256"],
                "tail_report_path": row["tail_report_path"],
                "tail_report_bytes": row["tail_report_bytes"],
                "tail_report_sha256": row["tail_report_sha256"],
            }
            for row in rows
        ],
        "data_scope": dict(DATA_SCOPE),
        "data_identity": dict(parent["data_identity"]),
        "protocol": {
            "models": [MODEL],
            "arms": list(ARMS),
            "seeds": list(SEEDS),
            "role": "Development",
            "year": 2024,
            "endpoint": "FIXED_EPOCH_9_LAST",
            "best_selection": False,
            "validation_batch": 8,
            "inference": "ONE_FIXED_E9_PASS_PER_MODEL_NO_TRAINING",
            "optimizer_updates": 0,
            "retries": 0,
            "replays": 0,
            "dynamic_control": {
                "REAL": CONTROLS["REAL"],
                "ZERO": CONTROLS["ZERO"],
            },
            "task_order": list(TASKS),
        },
        "scientific_choices": {
            "DOTE": dict(parent["scientific_choices"]["DOTE"]),
            "modulation_limit": parent["scientific_choices"]["modulation_limit"],
            "terrain_evaluation": terrain_contract(),
            "arrays_retention": arrays_retention_spec(),
            "frozen_metric_gate": {
                "reference": "B7_development_09.json groups",
                "groups": list(FROZEN_GROUP_KEYS),
                "absolute_tolerance": FROZEN_METRIC_TOLERANCE,
                "relative_tolerance": FROZEN_METRIC_TOLERANCE,
            },
            "saved_elevation_gate": {
                "reference": "B7_tail_09.json elevation_diagnostics.bins",
                "absolute_tolerance": FROZEN_METRIC_TOLERANCE,
            },
            "pairing": "REAL_PHYSICAL_DOTE_MINUS_ZERO_NUMERIC_RETAIN_REAL_MASKS",
            "primary_population": "elevation_ge_2000m_AND_float32_R_strictly_gt20",
            "primary_metrics": ["log_pinball", "physical_pinball_over20"],
            "q1_2029_reference": _q1_reference(root),
            "occurrence_event": "float32 rate > float32(0.1)",
            "scientific_status": "NOT_VERIFIED",
        },
        "budget": dict(BUDGET),
        "runtime_binding": dict(resolved_runtime),
        "parent_proposal_identity": {
            "path": str(parent_proposal),
            "bytes": parent_proposal.stat().st_size,
            "file_sha256": parent_file_sha,
            "proposal_sha256": PARENT_PROPOSAL_SHA256,
        },
        "parent_package_identity": {
            "root": str(package_root),
            "completion_path": str(completion_path),
            "completion_bytes": completion_path.stat().st_size,
            "completion_sha256": completion_sha,
            "status": completion["status"],
            "kind": completion["kind"],
            "code_commit": completion["code_commit"],
            "pairing": {
                str(seed): completion["pairing"][str(seed)]["pairing"] for seed in SEEDS
            },
        },
        "static_source_sha256": STATIC_SOURCE_SHA256,
        "code_sha256": reviewed_code,
        "source_scope_summary": {
            "development_files": BUDGET["development_files"],
            "development_bytes": BUDGET["development_bytes"],
            "scientific_open_instances": scientific_opens,
            "scientific_reference_bytes": scientific_bytes,
            "arrays_bytes_reference": ARRAY_BYTES_REFERENCE_PER_MODEL * len(TASKS),
        },
        "execution_code_commit": code_commit,
        "execution_code_commit_status": "BOUND_BY_RESEARCHER_APPROVAL",
        "private_preparation_sha256": None,
        "automatic_retry": False,
        "replay": False,
    }
    proposal["private_preparation_sha256"] = private_seal(private)
    proposal["proposal_sha256"] = proposal_seal(proposal)
    private["proposal_sha256"] = proposal["proposal_sha256"]
    return proposal, private


def validate_scope(proposal):
    _require(proposal.get("kind") == KIND, "The proposal kind differs")
    _require(proposal.get("scope") == SCOPE, "The proposal scope differs")
    _require(proposal.get("decision") == DECISION, "The proposal decision differs")
    _require(
        proposal.get("status") == "READY_WAITING_EXACT_RESEARCHER_APPROVAL",
        "The proposal status differs",
    )
    _require(proposal.get("authorized") is False, "The proposal must stay unauthorized")
    _require(proposal.get("final_2025_access") is False, "The proposal must seal 2025")
    _require(tuple(proposal.get("tasks", ())) == TASKS, "The proposal task table differs")
    _require(proposal.get("budget") == BUDGET, "The proposal budget differs")
    _require(proposal.get("data_scope") == DATA_SCOPE, "The proposal data scope differs")
    choices = proposal.get("scientific_choices", {})
    _require(
        choices.get("terrain_evaluation") == terrain_contract(),
        "The proposal terrain contract differs",
    )
    _require(
        choices.get("arrays_retention") == arrays_retention_spec(),
        "The proposal array retention differs",
    )
    for row in proposal.get("models", ()):
        arm = row["arm"]
        _require(
            row["dynamic_control"] == CONTROLS[arm],
            f"The proposal dynamic control differs for {row['task']}",
        )
        _require(row["model"] == MODEL, "The proposal model differs")
        _require(row["role"] == "Development" and row["year"] == 2024, "The proposal role differs")
    return proposal


def validate_entry(proposal, private, approval, commit=None):
    """Consistency gate shared by the CLI and the independent supervisor."""

    validate_scope(proposal)
    _require(
        proposal_seal(proposal) == proposal.get("proposal_sha256"),
        "The proposal self digest differs",
    )
    _require(
        private.get("proposal_sha256") == proposal["proposal_sha256"],
        "The private preparation points at another proposal",
    )
    _require(
        private_seal(private) == proposal["private_preparation_sha256"],
        "The private preparation seal differs",
    )
    validate_approval(approval, proposal, private, commit=commit)
    require_fresh_output(private["output_root"])
    _require(
        tuple(private.get("tasks", {})) == TASKS,
        "The private task table differs",
    )
    for row in proposal["models"]:
        task_private = private["tasks"][row["task"]]
        for key in ("checkpoint", "dev_report", "tail_report"):
            validate_artifact(
                task_private[f"{key}_path"],
                task_private[f"{key}_bytes"],
                task_private[f"{key}_sha256"],
                f"{row['task']} {key}",
            )
    validate_artifact(
        private["static_source"],
        STATIC_SOURCE_BYTES,
        STATIC_SOURCE_SHA256,
        "B6 static source",
    )
    _require(
        not Path(private["output_root"]).exists(),
        "The evaluation output root already exists",
        PermissionError,
    )
    return True


def checked(root, proposal, private, approval, commit):
    """Revalidate every frozen identity before the first real read."""

    root = Path(root)
    validate_scope(proposal)
    _require(
        proposal_seal(proposal) == proposal["proposal_sha256"],
        "The proposal self digest differs",
    )
    _require(
        private.get("proposal_sha256") == proposal["proposal_sha256"],
        "The private preparation points at another proposal",
    )
    _require(
        private_seal(private) == proposal["private_preparation_sha256"],
        "The private preparation seal differs",
    )
    _require(
        code_hashes(root) == proposal["code_sha256"],
        "The reviewed code tree changed",
    )
    _require(
        runtime_binding() == proposal["runtime_binding"],
        "The approved Torch/CUDA/NumPy/GPU runtime identity differs",
    )
    head = _git_head(root)
    _require(head.lower() == str(commit).lower(), "HEAD differs from the approved commit")
    _require(head.lower() == str(proposal["execution_code_commit"]).lower(),
             "HEAD differs from the proposal commit")
    _require(_clean_tree(root), "The fixed execution worktree must be clean", PermissionError)
    validate_artifact(
        proposal["parent_proposal_identity"]["path"],
        proposal["parent_proposal_identity"]["bytes"],
        proposal["parent_proposal_identity"]["file_sha256"],
        "Parent V4 proposal",
    )
    parent = read(proposal["parent_proposal_identity"]["path"])
    _require(
        proposal_seal(parent) == PARENT_PROPOSAL_SHA256,
        "The parent V4 proposal canonical sha differs",
    )
    _require(
        sha(Path(private["parent_proposal"])) == proposal["parent_proposal_identity"]["file_sha256"],
        "The parent V4 proposal file changed",
    )
    _require(
        sha(Path(private["preparation_path"]))
        == read(private["parent_private"])["inherited_file_sha256"],
        "The inherited preparation changed",
    )
    completion_path = Path(proposal["parent_package_identity"]["completion_path"])
    _require(
        sha(completion_path) == proposal["parent_package_identity"]["completion_sha256"],
        "The V4 package completion changed",
    )
    _require(
        read(completion_path).get("status") == PARENT_PACKAGE_STATUS,
        "The V4 package is no longer complete",
    )
    validate_artifact(private["static_source"], STATIC_SOURCE_BYTES, STATIC_SOURCE_SHA256,
                      "B6 static source")
    for row in proposal["models"]:
        task_private = private["tasks"][row["task"]]
        for key in ("checkpoint", "dev_report", "tail_report"):
            validate_artifact(
                task_private[f"{key}_path"],
                task_private[f"{key}_bytes"],
                task_private[f"{key}_sha256"],
                f"{row['task']} {key}",
            )
    _require(
        Path(private["output_root"]).exists() is False,
        "The evaluation output root already exists",
        PermissionError,
    )
    validate_approval(approval, proposal, private, commit=commit)
    return head


# ---------------------------------------------------------------------------
# Frozen metric gates
# ---------------------------------------------------------------------------


def _isclose(left, right, tolerance=FROZEN_METRIC_TOLERANCE):
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return math.isclose(
        float(left), float(right), rel_tol=tolerance, abs_tol=tolerance
    )


def gate_report(actual, reference):
    """Compare one recomputed Dev report with its frozen ``B7_development_09``."""

    for key in ("scope", "source_identity", "population_ids_sha256", "partition_sha256"):
        _require(
            actual.get(key) == reference.get(key),
            f"Recomputed report identity differs for {key}",
        )
    groups = reference.get("groups", {})
    _require(
        tuple(actual.get("groups", {})) == tuple(groups),
        "Recomputed report groups differ from the frozen report",
    )
    result = {}
    for name, saved in groups.items():
        new = actual["groups"][name]
        _require(new.get("ids_sha") == saved.get("ids_sha"), f"{name} ids differ")
        _require(new.get("complete") is True, f"{name} is incomplete")
        _require(
            int(new["summary"]["scenes"]) == int(saved["summary"]["scenes"]),
            f"{name} scene count differs",
        )
        _require(
            int(new["summary"]["n_valid"]) == int(saved["summary"]["n_valid"]),
            f"{name} n_valid differs",
        )
        _require(
            int(new["summary"]["n_rain"]) == int(saved["summary"]["n_rain"]),
            f"{name} n_rain differs",
        )
        _require(
            int(new["summary"]["covered"][-1]) == int(saved["summary"]["covered"][-1]),
            f"{name} covered count differs",
        )
        for metric in ("brier", "auroc", "average_precision", "conditional_pinball"):
            _require(
                _isclose(new["summary"].get(metric), saved["summary"].get(metric)),
                f"{name} {metric} differs",
            )
        _require(
            _isclose(new["summary"]["coverage"][-1], saved["summary"]["coverage"][-1]),
            f"{name} coverage differs",
        )
        result[name] = {
            "identity": "PASS",
            "counts": "PASS",
            "frozen_metrics": "PASS",
        }
    return {
        "passed": True,
        "groups": result,
        "absolute_tolerance": FROZEN_METRIC_TOLERANCE,
        "relative_tolerance": FROZEN_METRIC_TOLERANCE,
    }


def saved_elevation_gate(terrain, tail):
    """Reproduce the saved ``tail_report_09`` elevation diagnostics bins."""

    _require(
        terrain.get("profile") == "MOUNTAIN_TERRAIN_PAIR_V1",
        "The recomputed terrain profile differs",
    )
    _require(
        int(terrain["population"]["n_strong"]) == DATA_SCOPE["n_strong"],
        "The recomputed strong-rain population differs",
    )
    bins = tail["elevation_diagnostics"]["bins"]
    coverage = {}
    for name, recomputed in terrain["elevation_groups"].items():
        saved = bins.get(name)
        _require(saved is not None, f"Saved elevation bin is missing: {name}")
        _require(
            int(recomputed["n_valid"]) == int(saved["n_valid"]),
            f"{name} n_valid differs from the tail report",
        )
        _require(
            int(recomputed["n_rain"]) == int(saved["n_rain"]),
            f"{name} n_rain differs from the tail report",
        )
        _require(
            _isclose(
                recomputed["brier_sum"] / int(recomputed["n_valid"]),
                saved["brier"],
            ),
            f"{name} brier differs from the tail report",
        )
        _require(
            _isclose(
                math.fsum(
                    float(cell["log_pinball_sum"]) for cell in recomputed["cells"]
                )
                / int(recomputed["n_rain"]),
                saved["conditional_pinball"],
            ),
            f"{name} conditional pinball differs from the tail report",
        )
        coverage[name] = "PASS"
    return {
        "passed": True,
        "bins": coverage,
        "absolute_tolerance": FROZEN_METRIC_TOLERANCE,
        "relative_tolerance": FROZEN_METRIC_TOLERANCE,
    }


# ---------------------------------------------------------------------------
# Bounded scientific reader
# ---------------------------------------------------------------------------


class ReadMeter:
    """Small explicit meter for the static/checkpoint/metadata reads.

    The 7,950 development weather opens are metered by the Stage-4
    ``SourceMeter`` inside :class:`ReaderFactory`; this meter covers the
    non-weather files that the arm opens itself.
    """

    def __init__(self, maximum_bytes, maximum_opens):
        self.maximum_bytes = int(maximum_bytes)
        self.maximum_opens = int(maximum_opens)
        self.bytes = 0
        self.opens = 0

    def take(self, size, label):
        self.bytes += int(size)
        self.opens += 1
        if self.bytes > self.maximum_bytes:
            raise MemoryError(f"The bounded read meter exceeded its bytes at {label}")
        if self.opens > self.maximum_opens:
            raise MemoryError(f"The bounded read meter exceeded its opens at {label}")


def _read_bytes(path, meter):
    raw = Path(path).read_bytes()
    meter.take(len(raw), str(path))
    return raw


def _read_json(path, meter):
    raw = _read_bytes(path, meter)
    return json.loads(raw.decode("utf-8"))


def _checkpoint_identity(path, expected_bytes, expected_sha256, check):
    path = Path(path)
    digest_value = hashlib.sha256()
    delivered = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            check()
            delivered += len(chunk)
            digest_value.update(chunk)
    _require(
        delivered == int(expected_bytes),
        f"Checkpoint bytes differ: {delivered} != {expected_bytes}",
    )
    observed = digest_value.hexdigest()
    _require(
        observed == str(expected_sha256).lower(),
        f"Checkpoint sha differs: {observed} != {expected_sha256}",
    )
    return delivered, observed


def _initialize_runtime(output, expected, *, create=True, hash_seed=2029):
    output = Path(output)
    if create:
        output.mkdir(parents=True, exist_ok=False)
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = str(output)
    tempfile.tempdir = str(output)
    os.environ["TORCHINDUCTOR_CACHE_DIR"] = str(output / "inductor")

    runtime = _runtime()

    observed = {
        "torch_version": runtime.torch.__version__,
        "cuda_build": runtime.torch.version.cuda,
        "numpy_version": runtime.numpy.__version__,
        "gpu_name": runtime.torch.cuda.get_device_properties(0).name,
        "gpu_total_bytes": int(runtime.torch.cuda.get_device_properties(0).total_memory),
    }
    for key, value in observed.items():
        _require(
            expected.get(key) == value,
            f"Approved runtime identity differs for {key}: {value} != {expected.get(key)}",
        )

    runtime.torch.set_grad_enabled(False)

    def _forbid(*_arguments, **_keywords):
        raise PermissionError("Optimizer construction is forbidden in a bounded evaluation")

    runtime.torch.optim.Optimizer.__init__ = _forbid
    runtime.torch.set_num_threads(1)
    runtime.seed_all(int(hash_seed))
    return runtime, observed


def _runtime():
    """Imports the real Stage-4 stack only when an execution is requested."""

    import types

    import numpy
    import torch

    from yuntapr.experimental.core_innovation.stage3.planning import digest as population_digest
    from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan
    from yuntapr.experimental.core_innovation.stage4.engine import forward, seed_all
    from yuntapr.experimental.core_innovation.stage4.evaluation import Evaluation
    from yuntapr.experimental.core_innovation.stage4.launch import ReaderFactory
    from yuntapr.experimental.research_readiness.dote_numeric_control import ZeroNumericDote
    from yuntapr.experimental.research_readiness.dynamic_terrain import (
        DoteDefinition,
        PhysicalDote,
        model_factory,
    )
    from yuntapr.experimental.research_readiness.static_training import unpack
    from tools.research_readiness.conditional_intensity_readout import DevelopmentReadout
    from tools.research_readiness.mountain_pair_metrics import MountainAccumulator
    from tools.research_readiness.paired_point_metrics import PointMetricAccumulator

    module = types.SimpleNamespace(
        numpy=numpy,
        torch=torch,
        digest=population_digest,
        PopulationPlan=PopulationPlan,
        forward=forward,
        seed_all=seed_all,
        Evaluation=Evaluation,
        ReaderFactory=ReaderFactory,
        DoteDefinition=DoteDefinition,
        PhysicalDote=PhysicalDote,
        ZeroNumericDote=ZeroNumericDote,
        model_factory=model_factory,
        unpack=unpack,
        DevelopmentReadout=DevelopmentReadout,
        MountainAccumulator=MountainAccumulator,
        PointMetricAccumulator=PointMetricAccumulator,
    )
    return module


def _transform(runtime, pack, definition, control):
    if control == CONTROLS["REAL"]:
        return runtime.PhysicalDote(pack, definition)
    if control == CONTROLS["ZERO"]:
        return runtime.ZeroNumericDote(pack, definition)
    raise ValueError(f"Unknown dynamic control: {control}")


def _write_task_outputs(folder, report, point_metrics, terrain, readout):
    write(folder / "recomputed_report.json", report)
    write(folder / "point_metrics.json", point_metrics)
    write(folder / "terrain_metrics.json", terrain)
    write(folder / "dev_readout.json", readout)
    for name in ("recomputed_report.json", "point_metrics.json",
                 "terrain_metrics.json", "dev_readout.json"):
        _require((folder / name).is_file(), f"Missing recomputed output {name}")


def _task_check(output, deadline, reserve_bytes=None):
    """Enforce the time and bounded-output caps during one frozen task pass."""

    _require(deadline.remaining() > 0, "The package time cap was reached")
    if reserve_bytes is not None:
        _require(
            _output_bytes(output) + int(reserve_bytes) <= BUDGET["maximum_output_bytes"],
            "The bounded output reserve was exceeded during the task",
            MemoryError,
        )


def run_task(root, proposal, private, task, output, runtime, deadline, metadata_meter):
    """One fixed epoch-9 Development pass for one frozen model."""

    root = Path(root)
    output = Path(output)
    row = next(
        (item for item in proposal["models"] if item["task"] == task), None
    )
    _require(row is not None, f"Unknown task: {task}")
    task_private = private["tasks"][task]
    folder = output / task
    _require(not folder.exists(), f"The task output already exists: {folder}")
    folder.mkdir(parents=False)

    def check(reserve_bytes=None):
        _task_check(output, deadline, reserve_bytes)

    check()
    dev_report = _read_json(task_private["dev_report_path"], metadata_meter)
    tail_report = _read_json(task_private["tail_report_path"], metadata_meter)
    _read_json(task_private["task_completion_path"], metadata_meter)
    _read_json(task_private["task_receipt_path"], metadata_meter)
    _require(
        int(dev_report["groups"]["all"]["summary"]["n_valid"]) == DATA_SCOPE["n_valid"],
        "The saved Dev report population differs",
    )

    scientific = ReadMeter(
        private["task_payload_caps"][task],
        BUDGET["per_task_payload_open_instances"],
    )
    static_raw = _read_bytes(private["static_source"], scientific)
    static_receipt = _read_json(private["static_receipt"], metadata_meter)
    pack = runtime.unpack(static_raw, "B6", static_receipt)

    prepared = _read_json(private["preparation_path"], metadata_meter)["prepared"]
    plan = runtime.PopulationPlan(
        prepared["private_inputs"]["stage3_run"],
        prepared["private_inputs"]["request"],
        root=root,
    )
    ids = tuple(plan.ids("Development"))
    _require(len(ids) == DATA_SCOPE["scenes"], "The Development scene count differs")
    _require(
        runtime.digest(ids) == DATA_SCOPE["population_ids_sha256"],
        "The Development population digest differs",
    )
    _require(plan.identity == proposal["data_identity"], "The population identity differs")

    transform = _transform(
        runtime,
        pack,
        runtime.DoteDefinition(**proposal["scientific_choices"]["DOTE"]),
        row["dynamic_control"],
    )
    diagnostics = runtime.MountainAccumulator(pack, ids)
    arrays_root = output / "arrays"
    arrays_root.mkdir(exist_ok=True)
    arrays_folder = arrays_root / task
    readout = runtime.DevelopmentReadout(
        arrays_folder, ids, dict(DATA_SCOPE), check
    )
    evaluator = runtime.Evaluation(
        ids,
        tuple(plan.rows["Development"][scene]["analysis_time"] for scene in ids),
        plan.identity,
        folder / "evaluation",
        strong_scene_ids=plan.strong_scene_ids,
    )
    accumulator = runtime.PointMetricAccumulator(
        ids,
        expected_n_valid=DATA_SCOPE["n_valid"],
        expected_n_rain=DATA_SCOPE["n_rain"],
    )

    models = runtime.model_factory(
        pack,
        static_receipt["scalers"],
        modulation_limit=proposal["scientific_choices"]["modulation_limit"],
    )(row["seed"], root)
    model = models.pop(MODEL)
    del models

    _checkpoint_identity(
        task_private["checkpoint_path"],
        task_private["checkpoint_bytes"],
        task_private["checkpoint_sha256"],
        check,
    )
    scientific.take(task_private["checkpoint_bytes"], "checkpoint hash")
    payload = runtime.torch.load(
        task_private["checkpoint_path"], map_location="cpu", weights_only=False
    )
    scientific.take(task_private["checkpoint_bytes"], "checkpoint load")
    _require(isinstance(payload, dict) and "model" in payload, "Checkpoint payload differs")
    model.load_state_dict(payload["model"], strict=True)
    del payload
    model = model.to("cuda").eval()

    factory = runtime.ReaderFactory(
        plan,
        prepared,
        proposal["decision"],
        allowed_models=(MODEL,),
        dynamic_transform=transform,
    )
    reader = factory("Development", 9, ids, folder / "B7_development_09_reads")
    forward_calls = 0
    meter_totals = None
    report = None
    try:
        for position in range(0, len(ids), BUDGET["validation_batch"]):
            check()
            batch = reader.batch("Development", ids[position:position + BUDGET["validation_batch"]])
            batch = batch.to("cuda")
            with runtime.torch.autocast("cuda", dtype=runtime.torch.bfloat16):
                prediction, _ = runtime.forward(model, batch)
            evaluator.add(prediction, batch)
            arrays = (
                batch.ids,
                batch.rate.detach().cpu().numpy(),
                batch.valid.detach().cpu().numpy(),
                batch.region.detach().cpu().numpy(),
                prediction.rain_prob.detach().double().cpu().numpy(),
                prediction.conditional_quantiles_log.detach().double().cpu().numpy(),
            )
            accumulator.add(*arrays)
            diagnostics.add_batch(prediction, batch)
            readout.add(*arrays)
            forward_calls += 1
            check()
        report = evaluator.finish()
        point_metrics = accumulator.finish()
        terrain = diagnostics.finish(report)
        readout_summary = readout.finish(DATA_SCOPE["supervision_mask_sha256"])
        meter_totals = reader.reader.meter.totals()
    finally:
        evaluator.close()
        reader.close()

    _require(
        point_metrics["supervision_mask_sha256"]
        == DATA_SCOPE["supervision_mask_sha256"],
        "The recomputed supervision mask differs",
    )
    _require(
        (int(terrain["population"]["n_valid"]), int(terrain["population"]["n_rain"]))
        == (DATA_SCOPE["n_valid"], DATA_SCOPE["n_rain"]),
        "The recomputed terrain population differs",
    )
    _require(
        int(terrain["population"]["n_strong"]) == DATA_SCOPE["n_strong"],
        "The recomputed strong-rain population differs",
    )
    expected = {
        "opened_files": BUDGET["development_opens_per_task"],
        "delivered_bytes": BUDGET["development_bytes"],
        "reserved_bytes": BUDGET["development_bytes"],
        "states": {"READ_COMPLETE": BUDGET["development_opens_per_task"]},
    }
    _require(meter_totals == expected, f"The development read meter differs: {meter_totals}")
    _require(forward_calls == BUDGET["forward_batches_per_model"], "The forward batch count differs")

    gate = gate_report(report, dev_report)
    elevation = saved_elevation_gate(terrain, tail_report)
    terrain = dict(terrain)
    terrain["terrain_population_sha256"] = terrain["paired_population_sha256"]
    terrain["saved_elevation_gate"] = elevation
    point_metrics = dict(point_metrics)
    readout_summary = dict(readout_summary)

    _write_task_outputs(folder, report, point_metrics, terrain, readout_summary)

    task_scientific = {
        "opens": int(meter_totals["opened_files"]) + 3,
        "bytes": int(meter_totals["delivered_bytes"])
        + BUDGET["static_bytes"]
        + 2 * int(task_private["checkpoint_bytes"]),
    }
    arrays = readout_summary["storage"]["files"]
    arrays_bytes = sum(int(shard["bytes"]) for shard in arrays)
    _require(len(arrays) == BUDGET["arrays_batch_count_per_model"], "The array shard count differs")
    result = {
        "task": task,
        "status": "COMPLETE",
        "model": MODEL,
        "arm": row["arm"],
        "seed": int(row["seed"]),
        "dynamic_control": row["dynamic_control"],
        "checkpoint_bytes": int(task_private["checkpoint_bytes"]),
        "checkpoint_sha256": task_private["checkpoint_sha256"],
        "dev_report_bytes": int(task_private["dev_report_bytes"]),
        "dev_report_sha256": task_private["dev_report_sha256"],
        "tail_report_bytes": int(task_private["tail_report_bytes"]),
        "tail_report_sha256": task_private["tail_report_sha256"],
        "gate": gate,
        "saved_elevation_gate": elevation["passed"],
        "population": {
            "scenes": int(terrain["scenes"]),
            "n_valid": int(terrain["population"]["n_valid"]),
            "n_rain": int(terrain["population"]["n_rain"]),
            "n_strong": int(terrain["population"]["n_strong"]),
        },
        "meter_totals": meter_totals,
        "forward_calls": forward_calls,
        "model_inference_passes": 1,
        "optimizer_updates": 0,
        "arrays_batch_count": len(arrays),
        "arrays_bytes": arrays_bytes,
        "arrays_sha256_list": [str(shard["sha256"]) for shard in arrays],
        "task_scientific_opens": task_scientific["opens"],
        "task_scientific_bytes": task_scientific["bytes"],
        "recomputed_report_sha256": sha(folder / "recomputed_report.json"),
        "point_metrics_sha256": sha(folder / "point_metrics.json"),
        "terrain_metrics_sha256": sha(folder / "terrain_metrics.json"),
        "dev_readout_sha256": sha(folder / "dev_readout.json"),
        "scientific_status": "NOT_VERIFIED",
        "researcher_knowledge": "NOT_ASSESSED",
    }
    write(folder / "task_result.json", result)
    return result


# ---------------------------------------------------------------------------
# Paired description and Q1 decision
# ---------------------------------------------------------------------------


def _terrain_elevations():
    from tools.research_readiness.mountain_pair_metrics import ELEVATIONS

    return ELEVATIONS


def _pair_cells(real, zero):
    cells = {}
    for name in _terrain_elevations():
        real_group = real["elevation_groups"][name]
        zero_group = zero["elevation_groups"][name]
        rows = []
        for left, right in zip(real_group["cells"], zero_group["cells"]):
            count = int(left["n_rain"])
            _require(count == int(right["n_rain"]), f"Paired n_rain differs in {name}")
            if count == 0:
                rows.append(
                    {
                        "n_rain": 0,
                        "lower_exclusive": left["lower_exclusive"],
                        "upper_inclusive": left["upper_inclusive"],
                        "real_log_pinball": None,
                        "zero_log_pinball": None,
                        "real_physical_pinball_over20": None,
                        "zero_physical_pinball_over20": None,
                    }
                )
            else:
                rows.append(
                    {
                        "n_rain": count,
                        "lower_exclusive": left["lower_exclusive"],
                        "upper_inclusive": left["upper_inclusive"],
                        "real_log_pinball": left["log_pinball"],
                        "zero_log_pinball": right["log_pinball"],
                        "real_physical_pinball_over20": left["physical_pinball_over20"],
                        "zero_physical_pinball_over20": right["physical_pinball_over20"],
                    }
                )
        cells[name] = rows
    return cells


def paired_metrics_payload(
    proposal,
    real_task,
    zero_task,
    real_terrain,
    zero_terrain,
    real_report,
    zero_report,
    real_points,
    zero_points,
):
    """Build the public ``MOUNTAIN_TERRAIN_PAIR_V1`` description for one seed."""

    from tools.research_readiness.mountain_pair_metrics import (
        CONTRACT,
        primary_contrast,
    )

    _require(
        real_terrain["paired_population_sha256"]
        == zero_terrain["paired_population_sha256"],
        "The paired terrain population digest differs",
    )
    return {
        "status": "DESCRIPTIVE_MATCHED_MOUNTAIN_EVALUATION",
        "primary_contrast": primary_contrast(real_terrain, zero_terrain),
        "cells": _pair_cells(real_terrain, zero_terrain),
        "full_population": {
            "REAL": real_report["groups"]["all"]["summary"],
            "ZERO": zero_report["groups"]["all"]["summary"],
        },
        "point_metrics": {"REAL": real_points, "ZERO": zero_points},
        "source_sha256": {
            "REAL": proposal["models"][TASKS.index(real_task)]["dev_report_sha256"],
            "ZERO": proposal["models"][TASKS.index(zero_task)]["dev_report_sha256"],
        },
        "paired_population_sha256": real_terrain["paired_population_sha256"],
        "evaluation_contract": CONTRACT,
        "proposal_sha256": proposal["proposal_sha256"],
        "scientific_status": "NOT_VERIFIED",
    }


def finalize_pair(output, proposal, task_pairs, seed):
    """Write one ``MOUNTAIN_TERRAIN_PAIR_V1`` paired description for a seed."""

    output = Path(output)
    real_task, zero_task = task_pairs
    real_folder = output / real_task
    zero_folder = output / zero_task
    paired = paired_metrics_payload(
        proposal,
        real_task,
        zero_task,
        read(real_folder / "terrain_metrics.json"),
        read(zero_folder / "terrain_metrics.json"),
        read(real_folder / "recomputed_report.json"),
        read(zero_folder / "recomputed_report.json"),
        read(real_folder / "point_metrics.json"),
        read(zero_folder / "point_metrics.json"),
    )
    path = output / f"paired_metrics_seed{seed}.json"
    write(path, paired)
    return {
        "path": str(path),
        "sha256": sha(path),
        "status": paired["status"],
        "primary_contrast": paired["primary_contrast"],
        "paired_population_sha256": paired["paired_population_sha256"],
    }


def _sign(value):
    value = float(value)
    if value < 0:
        return -1
    if value > 0:
        return 1
    return 0


def q1_metric_decision(values, reference):
    """Apply the pre-registered 2-of-3 sign rule to one primary metric."""

    values = [float(value) for value in values]
    _require(len(values) == 3, "Q1 needs the 2029, 2030 and 2031 seeds")
    direction = _sign(reference)
    _require(direction != 0, "The 2029 Q1 reference is exactly zero")
    count = sum(1 for value in values if _sign(value) == direction)
    mean = math.fsum(values) / len(values)
    mean_same = _sign(mean) == direction
    if count >= 2 and mean_same:
        decision = "REPRODUCED"
    elif count >= 2 or mean_same:
        decision = "PARTIAL"
    else:
        decision = "NOT_REPRODUCED"
    return {
        "values": values,
        "signs": [_sign(value) for value in values],
        "same_sign_count": count,
        "three_seed_mean": mean,
        "mean_same_sign": mean_same,
        "reference_sign": direction,
        "decision": decision,
    }


def q1_summary(proposal, paired_by_seed):
    reference = proposal["scientific_choices"]["q1_2029_reference"]
    reference_values = reference["real_minus_zero"]
    per_metric = {}
    for metric in ("log_pinball", "physical_pinball_over20"):
        values = [float(reference_values[metric])]
        n_strong = [int(reference["n_strong"])]
        for seed in SEEDS:
            contrast = paired_by_seed[seed]["primary_contrast"]
            values.append(float(contrast["real_minus_zero"][metric]))
            n_strong.append(int(contrast["n_strong"]))
        per_metric[metric] = q1_metric_decision(values, reference_values[metric])
        per_metric[metric]["n_strong"] = n_strong
    decisions = [per_metric[metric]["decision"] for metric in per_metric]
    if all(decision == "REPRODUCED" for decision in decisions):
        overall = "TERRAIN_MECHANISM_REPRODUCED"
    elif all(decision == "NOT_REPRODUCED" for decision in decisions):
        overall = "TERRAIN_MECHANISM_NOT_REPRODUCED"
    else:
        overall = "PARTIAL_DESCRIPTIVE_SIGNAL"
    return {
        "status": overall,
        "decision": overall,
        "seeds": [2029, *SEEDS],
        "per_metric": per_metric,
        "primary_population": "elevation_ge_2000m_AND_float32_R_strictly_gt20",
        "reference_2029": {
            "n_strong": int(reference["n_strong"]),
            "real_minus_zero": {
                "log_pinball": float(reference_values["log_pinball"]),
                "physical_pinball_over20": float(reference_values["physical_pinball_over20"]),
            },
            "paired_population_sha256": reference["paired_population_sha256"],
            "file_sha256": reference["file_sha256"],
        },
        "overall_rule": (
            "REPRODUCED iff >=2 of 3 seeds share the 2029 sign and the 3-seed mean "
            "shares it; PARTIAL otherwise when one condition holds; NOT_REPRODUCED "
            "when neither holds"
        ),
        "final_2025_access": False,
        "scientific_status": "NOT_VERIFIED",
    }


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


class Deadline:
    def __init__(self, seconds):
        self.started = time.monotonic()
        self.seconds = int(seconds)

    def remaining(self):
        return self.seconds - (time.monotonic() - self.started)

    def elapsed(self):
        return time.monotonic() - self.started


def _output_bytes(root):
    root = Path(root)
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _metadata_totals(private, approval_path, proposal_path):
    """Reserve the frozen per-seed-pair metadata envelope for two pairs.

    The 2029 mountain evaluation accounted 459 metadata opens and 306,950,433
    bytes for one REAL/ZERO seed pair.  Package A contains two independent seed
    pairs, so the frozen reserve is exactly twice that quantity.  The explicit
    manifest is validated against the reserve but the reserve, not the manifest
    length, is what the execution budget accounts.
    """

    entries = list(private["metadata_files"].values())
    control = [Path(path) for path in (proposal_path, approval_path) if path is not None]
    manifest_opens = len(entries) + len(control)
    manifest_bytes = sum(int(entry["bytes"]) for entry in entries)
    manifest_bytes += sum(path.stat().st_size for path in control if path.is_file())
    reserve_opens = 2 * int(BUDGET["per_task_metadata_open_instances"])
    reserve_bytes = 2 * int(BUDGET["per_task_metadata_reference_bytes"])
    _require(
        manifest_opens <= reserve_opens,
        "The explicit metadata manifest exceeds the per-pair open reserve",
    )
    _require(
        manifest_bytes <= reserve_bytes,
        "The explicit metadata manifest exceeds the per-pair byte reserve",
    )
    return {
        "metadata_open_instances": reserve_opens,
        "metadata_reserved_bytes": reserve_bytes,
        "metadata_manifest_files": len(entries),
        "metadata_manifest_bytes": manifest_bytes,
    }


def _completion(proposal, private, commit, results, paired, q1, elapsed, metadata):
    tasks = []
    for row in proposal["models"]:
        result = results[row["task"]]
        tasks.append(
            {
                "task": result["task"],
                "arm": result["arm"],
                "seed": result["seed"],
                "status": result["status"],
                "model": result["model"],
                "dynamic_control": result["dynamic_control"],
                "checkpoint_sha256": result["checkpoint_sha256"],
                "checkpoint_bytes": result["checkpoint_bytes"],
                "checkpoint_loads": 1,
                "dev_report_sha256": result["dev_report_sha256"],
                "dev_report_bytes": result["dev_report_bytes"],
                "tail_report_sha256": result["tail_report_sha256"],
                "tail_report_bytes": result["tail_report_bytes"],
                "recomputed_report_sha256": result["recomputed_report_sha256"],
                "point_metrics_sha256": result["point_metrics_sha256"],
                "terrain_metrics_sha256": result["terrain_metrics_sha256"],
                "dev_readout_sha256": result["dev_readout_sha256"],
                "gate": result["gate"],
                "saved_elevation_gate": result["saved_elevation_gate"],
                "population": result["population"],
                "forward_calls": result["forward_calls"],
                "model_inference_passes": 1,
                "optimizer_updates": 0,
                "arrays_batch_count": result["arrays_batch_count"],
                "arrays_bytes": result["arrays_bytes"],
                "arrays_sha256_list": result["arrays_sha256_list"],
                "scientific_status": "NOT_VERIFIED",
            }
        )
    scientific_opens = sum(result["task_scientific_opens"] for result in results.values())
    scientific_bytes = sum(result["task_scientific_bytes"] for result in results.values())
    forward_calls = sum(result["forward_calls"] for result in results.values())
    arrays_bytes = sum(result["arrays_bytes"] for result in results.values())
    _require(
        scientific_opens <= BUDGET["payload_open_instances"],
        "The executed scientific open total exceeds the frozen payload envelope",
    )
    _require(
        scientific_opens + metadata["metadata_open_instances"]
        <= BUDGET["total_scientific_file_opens"],
        "The executed scientific plus metadata opens exceed the frozen budget",
    )
    _require(
        scientific_bytes + metadata["metadata_reserved_bytes"]
        <= BUDGET["total_scientific_source_bytes"],
        "The executed scientific source bytes exceed the frozen budget",
    )
    pairing = {}
    for seed in SEEDS:
        real_task, zero_task = PAIRS[SEEDS.index(seed)]
        pairing[str(seed)] = {
            "real": real_task,
            "zero": zero_task,
            "real_checkpoint_sha256": results[real_task]["checkpoint_sha256"],
            "zero_checkpoint_sha256": results[zero_task]["checkpoint_sha256"],
            "paired_population_sha256": paired[seed]["paired_population_sha256"],
            "primary_contrast_status": paired[seed]["primary_contrast"]["status"],
        }
    return {
        "status": STATUS,
        "kind": KIND,
        "scope": SCOPE,
        "decision": DECISION,
        "proposal_sha256": proposal["proposal_sha256"],
        "code_commit": commit,
        "tasks": tasks,
        "pairing": pairing,
        "paired_metrics": {
            str(seed): {
                "path": paired[seed]["path"],
                "sha256": paired[seed]["sha256"],
                "status": paired[seed]["status"],
            }
            for seed in SEEDS
        },
        "q1_summary": q1,
        "totals": {
            "scientific_open_instances": scientific_opens,
            "scientific_source_bytes": scientific_bytes,
            "metadata_open_instances": metadata["metadata_open_instances"],
            "metadata_reserved_bytes": metadata["metadata_reserved_bytes"],
            "total_open_instances": scientific_opens
            + metadata["metadata_open_instances"],
            "total_source_bytes": scientific_bytes
            + metadata["metadata_reserved_bytes"],
            "checkpoint_loads": len(results),
            "model_inference_passes": len(results),
            "forward_calls": forward_calls,
            "optimizer_updates": 0,
            "arrays_batch_count": sum(
                result["arrays_batch_count"] for result in results.values()
            ),
            "arrays_bytes": arrays_bytes,
        },
        "budget": dict(BUDGET),
        "scientific_acceptance": "NOT_VERIFIED",
        "scientific_status": "NOT_VERIFIED",
        "final_2025_access": False,
        "automatic_retry": False,
        "replay": False,
        "elapsed_seconds": float(elapsed),
        "access_2025": False,
    }


def execute(
    root,
    proposal,
    private,
    approval,
    commit,
    *,
    proposal_path=None,
    private_path=None,
    approval_path=None,
):
    """The approval-bound, single-attempt four-model evaluation."""

    _require(
        proposal_path is not None and private_path is not None and approval_path is not None,
        "The live proposal, preparation and approval paths are required",
        PermissionError,
    )
    root = Path(root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from tools.research_readiness.start_independent_process import (
        host_identity,
        require_independent,
    )

    require_independent(host_identity())
    head = checked(root, proposal, private, approval, commit)
    output_root = Path(private["output_root"])
    _require(
        _free_bytes(output_root.parent) >= BUDGET["minimum_free_bytes"],
        "The output volume has less than the frozen minimum free bytes",
        PermissionError,
    )
    _require(
        SOURCE_VOLUME.is_dir(),
        "The approved H:\\葵花202303_202510 source volume is missing",
        PermissionError,
    )
    output_root.mkdir(parents=False)
    started = time.monotonic()
    deadline = Deadline(BUDGET["maximum_seconds"])
    metadata = _metadata_totals(
        private,
        approval.get("path"),
        None,
    )
    _require(
        metadata["metadata_reserved_bytes"] <= BUDGET["metadata_archive_reference_bytes"],
        "The metadata plan exceeds the frozen budget",
    )
    write(
        output_root / "authorization_binding.json",
        {
            "kind": KIND,
            "proposal_sha256": proposal["proposal_sha256"],
            "code_commit": commit,
            "controller_pid": os.getpid(),
            "tasks": list(TASKS),
            "approval": {
                "approved_by_researcher": bool(approval.get("approved_by_researcher")),
                "decision_id": approval.get("decision_id"),
                "code_commit": approval.get("code_commit"),
                "output_root": approval.get("output_root"),
            },
            "automatic_retry": False,
            "replay": False,
            "scientific_status": "NOT_VERIFIED",
        },
    )

    runtime, runtime_identity = _initialize_runtime(
        output_root / "runtime", proposal["runtime_binding"]
    )
    results = {}
    try:
        for index, row in enumerate(proposal["models"]):
            _require(
                deadline.remaining() > 0,
                "The package time cap was reached; no later task may start",
                RuntimeError,
            )
            _require(
                _output_bytes(output_root) <= BUDGET["maximum_output_bytes"],
                "The bounded output reserve was exceeded before the task",
                MemoryError,
            )
            _require(
                _free_bytes(output_root.parent) >= BUDGET["minimum_free_bytes"],
                "The output volume dropped below the frozen minimum free bytes",
                PermissionError,
            )
            claim_path = output_root / f"task_{index + 1}_claim.json"
            write(
                claim_path,
                {
                    "index": index,
                    "arm": row["arm"],
                    "seed": row["seed"],
                    "task": row["task"],
                    "controller_pid": os.getpid(),
                    "controller_commit": head,
                    "started_monotonic": time.monotonic(),
                    "automatic_retry": False,
                },
            )
            claim = read(claim_path)
            _require(
                int(claim["controller_pid"]) == os.getpid(),
                "The live task claim differs from this controller",
                PermissionError,
            )
            _require(
                claim.get("task") == row["task"] and claim.get("seed") == row["seed"],
                "The live task claim differs from the proposal",
                PermissionError,
            )
            command = [
                sys.executable,
                "-B",
                str((root / ENTRY).resolve()),
                "worker",
                "--task-index",
                str(index),
                "--proposal",
                str(Path(proposal_path).resolve()),
                "--private-preparation",
                str(Path(private_path).resolve()),
                "--researcher-approval",
                str(Path(approval_path).resolve()),
                "--seconds-cap",
                str(max(1, int(math.floor(deadline.remaining())))),
            ]
            environment = dict(os.environ)
            environment["PYTHONHASHSEED"] = str(row["seed"])
            completed = subprocess.run(command, cwd=str(root), env=environment)
            _require(
                completed.returncode == 0,
                f"The frozen per-seed worker failed for {row['task']}",
                RuntimeError,
            )
            result = read(output_root / row["task"] / "task_result.json")
            _require(
                result.get("task") == row["task"] and result.get("status") == "COMPLETE",
                "The frozen per-seed worker did not publish a complete task result",
                RuntimeError,
            )
            results[row["task"]] = result
            _require(
                _output_bytes(output_root) <= BUDGET["maximum_output_bytes"],
                "The bounded output reserve was exceeded after the task",
                MemoryError,
            )
        paired = {}
        for seed in SEEDS:
            paired[seed] = finalize_pair(
                output_root, proposal, PAIRS[SEEDS.index(seed)], seed
            )
        q1 = q1_summary(proposal, paired)
        completion = _completion(
            proposal,
            private,
            commit,
            results,
            paired,
            q1,
            deadline.elapsed(),
            metadata,
        )
        write(output_root / "completion.json", completion)
        return completion
    except BaseException as error:
        failure = output_root / "failure.json"
        if not failure.exists():
            write(
                failure,
                {
                    "status": "STOP_NO_RETRY",
                    "kind": KIND,
                    "proposal_sha256": proposal.get("proposal_sha256"),
                    "code_commit": commit,
                    "error": type(error).__name__ + ": " + str(error),
                    "completed_tasks": list(results),
                    "automatic_retry": False,
                    "replay": False,
                    "scientific_acceptance": "NOT_VERIFIED",
                    "scientific_status": "NOT_VERIFIED",
                    "final_2025_access": False,
                },
            )
        raise


# ---------------------------------------------------------------------------
# Per-seed worker process
# ---------------------------------------------------------------------------


def _task_row(proposal, index):
    index = int(index)
    _require(0 <= index < len(TASKS), f"Invalid frozen task index: {index}")
    task = TASKS[index]
    row = next((item for item in proposal["models"] if item["task"] == task), None)
    _require(row is not None, "The frozen proposal does not contain the task")
    return task, row


def task_worker(
    root,
    proposal,
    private,
    approval,
    commit,
    index,
    *,
    seconds_cap=None,
    proposal_path=None,
    private_path=None,
    approval_path=None,
):
    """Run exactly one frozen task inside its own per-seed process.

    The parent controller starts each task with ``PYTHONHASHSEED`` fixed at the
    task seed, because the frozen Dev pass that this arm recomputes was produced
    under that interpreter hash seed.  The worker therefore re-validates the
    live claim instead of the "fresh output root" precondition used by the
    parent controller.
    """

    root = Path(root).resolve()
    task, row = _task_row(proposal, index)
    _require(
        os.environ.get("PYTHONHASHSEED") == str(row["seed"]),
        "The worker hash seed differs from the frozen task seed",
        PermissionError,
    )
    validate_scope(proposal)
    _require(
        proposal_seal(proposal) == proposal["proposal_sha256"],
        "The frozen proposal seal differs",
        PermissionError,
    )
    _require(
        private.get("proposal_sha256") == proposal["proposal_sha256"],
        "The private preparation is not bound to the frozen proposal",
        PermissionError,
    )
    _require(
        private_seal(private) == proposal["private_preparation_sha256"],
        "The private preparation seal differs",
        PermissionError,
    )
    head = _git_head(root)
    _require(
        str(head).lower() == str(commit).lower(),
        "The worker commit differs from the approved commit",
        PermissionError,
    )
    _require(
        str(head).lower() == str(proposal["execution_code_commit"]).lower(),
        "The worker commit differs from the frozen proposal",
        PermissionError,
    )
    _require(
        _clean_tree(root),
        "The fixed execution worktree must be clean",
        PermissionError,
    )
    validate_approval(approval, proposal, private, commit=commit)
    for label, path in (
        ("proposal", proposal_path),
        ("private preparation", private_path),
        ("researcher approval", approval_path),
    ):
        _require(
            path is not None and Path(path).is_file(),
            f"The live worker {label} path is missing",
            PermissionError,
        )
    namespace = Path(private["service_dir"]).resolve().parent
    _require(
        Path(approval_path).resolve().parent == namespace,
        "The worker approval is outside the frozen namespace",
        PermissionError,
    )
    output_root = Path(private["output_root"])
    _require(
        output_root.is_dir(),
        "The parent evaluation output is missing",
        PermissionError,
    )
    binding = read(output_root / "authorization_binding.json")
    _require(
        binding.get("kind") == KIND,
        "The authorization binding kind differs",
        PermissionError,
    )
    _require(
        binding.get("proposal_sha256") == proposal["proposal_sha256"],
        "The authorization binding proposal differs",
        PermissionError,
    )
    _require(
        binding.get("code_commit") == commit,
        "The authorization binding commit differs",
        PermissionError,
    )
    _require(
        int(binding.get("controller_pid")) == os.getppid(),
        "The authorization binding controller is not the live parent",
        PermissionError,
    )
    claim = read(output_root / f"task_{int(index) + 1}_claim.json")
    _require(
        int(claim.get("index")) == int(index),
        "The live task claim index differs",
        PermissionError,
    )
    _require(
        claim.get("task") == task and int(claim.get("seed")) == int(row["seed"]),
        "The live task claim differs from the frozen task",
        PermissionError,
    )
    _require(
        int(claim.get("controller_pid")) == os.getppid(),
        "The live task claim controller is not the live parent",
        PermissionError,
    )
    runtime, _ = _initialize_runtime(
        output_root / "runtime",
        proposal["runtime_binding"],
        create=False,
        hash_seed=row["seed"],
    )
    deadline = Deadline(
        float(seconds_cap)
        if seconds_cap is not None
        else float(BUDGET["maximum_seconds"])
    )
    metadata_meter = ReadMeter(
        BUDGET["metadata_archive_reference_bytes"],
        BUDGET["metadata_open_instances"],
    )
    result = run_task(
        root,
        proposal,
        private,
        task,
        output_root,
        runtime,
        deadline,
        metadata_meter,
    )
    print(
        json.dumps(
            {
                "task": task,
                "status": result["status"],
                "forward_calls": result["forward_calls"],
                "seed": result["seed"],
            },
            indent=2,
        )
    )
    return result
