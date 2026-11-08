"""Approval-bound B7 E0/UQ_MILD_V1 pair, with no automatic continuation."""

import copy
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from ..core_innovation.stage3.planning import digest
from ..core_innovation.stage4.data import read, sha
from ..core_innovation.stage4.engine import resources, write
from ..core_innovation.stage4.evaluation import paired_difference
from ..phase_b_v2_ablations.upper_quantile import UNIFORM, MILD_PROFILE, profile_identity
from .dynamic_training import hashes as inherited_hashes, run_task, runtime_binding
from .multiseed import load_inherited, worker_creation_flags
from .static_training import validate_approval
from .upper_quantile_diagnostics import UpperQuantileTail, PHYSICAL_SCALE_MM_H


ENTRY = "tools/research_readiness/start_upper_quantile_pair.py"
TASKS = [
    {"arm": "CONTROL_E0", "model": "B7", "seed": 2029, "quantile_profile": UNIFORM},
    {"arm": "CANDIDATE_UQ_MILD", "model": "B7", "seed": 2029, "quantile_profile": MILD_PROFILE},
]
FILES = (
    ENTRY,
    "src/yuntapr/experimental/phase_b_v2_ablations/upper_quantile.py",
    "src/yuntapr/experimental/research_readiness/upper_quantile_diagnostics.py",
    "src/yuntapr/experimental/research_readiness/upper_quantile_training.py",
)
TOLERANCE = 1e-10


def code_hashes(root):
    result = inherited_hashes(root)
    result.update({name: sha(root / name) for name in FILES})
    return result


def budget(prepared):
    weather_bytes = 9 * sum(scope["bytes_per_pass"] for scope in prepared["roles"].values())
    weather_files = 9 * sum(scope["file_count"] for scope in prepared["roles"].values())
    return {
        "models": 2,
        "updates_per_model": 4320,
        "total_updates": 8640,
        "source_bytes_per_model": weather_bytes + 312828,
        "source_files_per_model": weather_files + 1,
        "total_source_bytes": 2 * (weather_bytes + 312828),
        "total_source_files": 2 * (weather_files + 1),
        "max_model_seconds": 21600,
        "max_package_seconds": 43200,
        "initial_free_bytes": 48 * 1024**3,
        "minimum_task_free_bytes": 24 * 1024**3,
        "replay_allowance": 0,
        "additional_retry_allowance": 0,
        "checkpoint_loads": 0,
    }


def evaluation_contract():
    return {
        "strong_definition": "R>20 mm/h, original valid mask",
        "required_improvements": ["strong_log_pinball", "strong_physical_pinball"],
        "lower_guardrails": ["all_log_pinball", "all_physical_pinball", "brier"],
        "higher_guardrails": ["occurrence_ap", "occurrence_auroc"],
        "physical_scale_mm_h": PHYSICAL_SCALE_MM_H,
        "scientific_deterioration_allowance": 0,
        "absolute_roundoff_tolerance": TOLERANCE,
        "endpoint": "FIXED_EPOCH_9_LAST",
        "q32_coverage": "AUXILIARY_NOT_A_SUCCESS_GATE",
        "independent_event_count": "NOT_IDENTIFIED",
        "interpretation": "ONE_SEED_REUSED_DEVELOPMENT_SCREEN_NOT_SCIENTIFIC_ACCEPTANCE",
    }


def prepare(root, parent_proposal, parent_private, output_root):
    root, output_root = Path(root), Path(output_root).resolve()
    if output_root.exists() or not output_root.parent.is_dir():
        raise PermissionError("A fresh output under an existing selected parent is required")
    inherited = read(parent_proposal)
    locations = read(parent_private)
    _, prepared = load_inherited(locations["inherited"])
    if inherited["data"] != prepared["data"]:
        raise ValueError("Inherited frozen population differs")
    static = Path(locations["terrain"]) / "B6_static.npz"
    if static.stat().st_size != 312828:
        raise ValueError("Frozen static size differs")
    caps = budget(prepared)
    if (caps["total_source_bytes"], caps["total_source_files"]) != (955143907680, 285626):
        raise ValueError("Frozen two-arm source scope differs")
    free = shutil.disk_usage(output_root.parent).free
    if free < caps["initial_free_bytes"]:
        raise RuntimeError("The proposed output volume needs48GiB free")
    old_choices = inherited["scientific_choices"]
    inherited_keys = ("DOTE", "channels", "normalization", "spatial_operator", "scales",
                      "condition_channels", "projection_width", "modulation_limit", "condition_mask", "precision")
    choices = {key: old_choices[key] for key in inherited_keys}
    choices.update(
        architecture="B7_CONCAT_DIAGNOSTIC_CARRIER_NOT_FINAL_MODEL_SELECTION",
        initialization="FRESH_SEED2029_SAME_ORIGINAL_FACTORY_BOTH_ARMS",
        candidate_loss=profile_identity(),
        evaluation=evaluation_contract(),
        only_intervention="FIXED_POSITIVE_NORMALIZED_QUANTILE_NODE_WEIGHTS",
        decision_status="PROPOSED_PENDING_RESEARCHER_SCIENTIFIC_AND_BUDGET_APPROVAL",
    )
    protocol = dict(inherited["protocol"], models=["B7"], loss="E0", lambda_q=1.0,
                    quantile_profile="EXPLICIT_PER_TASK", seed=2029)
    proposal = {
        "status": "READY_WAITING_EXACT_RESEARCHER_APPROVAL",
        "authorized": False,
        "tasks": copy.deepcopy(TASKS),
        "data": prepared["data"],
        "protocol": protocol,
        "scientific_choices": choices,
        "budget": caps,
        "runtime_binding": runtime_binding(),
        "code_sha256": code_hashes(root),
        "static_source_sha256": {"B7": inherited["static_source_sha256"]["B7"]},
        "source_scope_summary": inherited["source_scope_summary"],
        "parent_proposal_identity": {"bytes": Path(parent_proposal).stat().st_size, "sha256": sha(Path(parent_proposal))},
        "resources": {"output_volume_free_bytes": free, "RAM_GPU_admission": "INHERIT_EXISTING_REQUIRE_RESOURCES_RECHECK_AT_START"},
        "preparation_activity": {"raw_payload_opens": 0, "checkpoint_loads": 0, "optimizer_updates": 0},
    }
    proposal["proposal_sha256"] = digest(proposal)
    private = {
        "proposal_sha256": proposal["proposal_sha256"],
        "inherited": locations["inherited"],
        "inherited_file_sha256": sha(Path(locations["inherited"])),
        "terrain": locations["terrain"],
        "output_root": str(output_root),
    }
    return proposal, private


def validate_scope(proposal):
    protocol = proposal.get("protocol", {})
    if (proposal.get("tasks") != TASKS or protocol.get("loss") != "E0"
            or protocol.get("lambda_q") != 1.0 or protocol.get("seed") != 2029
            or proposal.get("scientific_choices", {}).get("candidate_loss") != profile_identity()
            or proposal["scientific_choices"].get("evaluation") != evaluation_contract()):
        raise PermissionError("Only the closed B7 E0/UQ_MILD_V1 paired protocol is allowed")


def checked(root, proposal_path, private_path, approval_path, commit):
    if not Path(approval_path).is_file():
        raise PermissionError("External researcher approval is required before any execution")
    proposal, private, approval = map(read, (proposal_path, private_path, approval_path))
    validate_scope(proposal)
    validate_approval(approval, proposal, private, commit)
    body = {key: value for key, value in proposal.items() if key != "proposal_sha256"}
    if digest(body) != proposal["proposal_sha256"] or private["proposal_sha256"] != proposal["proposal_sha256"]:
        raise ValueError("Proposal binding changed")
    if code_hashes(root) != proposal["code_sha256"] or runtime_binding() != proposal["runtime_binding"]:
        raise ValueError("Approved numerical code or runtime changed")
    if sha(Path(private["inherited"])) != private["inherited_file_sha256"]:
        raise ValueError("Inherited manifest metadata changed")
    _, prepared = load_inherited(private["inherited"])
    if prepared["data"] != proposal["data"] or budget(prepared) != proposal["budget"]:
        raise ValueError("Frozen data or exact pass budget changed")
    return proposal, private, approval, prepared


def worker(root, proposal_path, private_path, approval_path, commit, index):
    started = time.monotonic()
    proposal, private, approval, prepared = checked(root, proposal_path, private_path, approval_path, commit)
    if type(index) is not int or not 0 <= index < len(TASKS):
        raise PermissionError("Only one of the two declared task indices is allowed")
    package = Path(private["output_root"])
    binding = read(package / "authorization_binding.json")
    claim = read(package / f"task_{index + 1}_claim.json")
    expected_claim = {"index": index, "controller_pid": os.getppid(), "code_commit": commit}
    if binding["controller_pid"] != os.getppid() or binding["approval"] != approval or claim != expected_claim:
        raise PermissionError("A live once-only controller claim is required")
    task = TASKS[index]
    task_proposal = copy.deepcopy(proposal)
    task_proposal["protocol"]["quantile_profile"] = task["quantile_profile"]
    reference = None
    if index == 1:
        reference = package / TASKS[0]["arm"] / "B7_s2029"
        completion = read(reference / "completion.json")
        if completion["status"] != "COMPLETE_TRAIN_AND_DEV_EVALUATION" or completion["code_commit"] != commit:
            raise PermissionError("A complete paired E0 control is required")
        origin = read(reference / "paired_initial_identity.json")["B7"]["full_state_sha256"]
        orders = read(reference / "paired_orders.json")
        task_proposal["scientific_choices"]["origin_reference"] = {
            "B7": {"original_model_state_sha256": origin, "epoch_order_sha256": [orders[str(epoch)]["sha256"] for epoch in range(1, 10)]}
        }
    arm_root = package / task["arm"]
    arm_root.mkdir(exist_ok=False)
    task_private = dict(private, output_root=str(arm_root))
    return run_task(
        root, task_proposal, task_private, approval, prepared, commit, "B7", 2029,
        started=started, pair_reference=reference, static_name="B7_static_source.sqlite",
        lambda_q=1.0, quantile_profile=task["quantile_profile"], tail_factory=UpperQuantileTail,
    )


def physical_mean(rows):
    count = sum(row["n_rain"] for row in rows)
    if count <= 0:
        raise ValueError("A declared physical-score population is empty")
    return math.fsum(row["pinball_sum_mm_h"] for row in rows) / (PHYSICAL_SCALE_MM_H * count)


def verify_loss_receipts(folder, task):
    expected_arm = "E0" if task["quantile_profile"] == UNIFORM else MILD_PROFILE
    for epoch in range(1, 10):
        training = read(Path(folder) / f"B7_train_{epoch:02d}.json")
        receipt = read(Path(folder) / f"B7_LAST_epoch_{epoch:02d}.receipt.json")
        if training["loss_arm"] != expected_arm:
            raise ValueError("Per-epoch training loss identity differs")
        if expected_arm == MILD_PROFILE and (
            training.get("loss_config") != profile_identity()
            or receipt.get("loss_config") != profile_identity()
        ):
            raise ValueError("Per-epoch upper-quantile profile identity differs")
        if expected_arm == "E0" and "loss_config" in receipt:
            raise ValueError("Control receipt unexpectedly declares a modified loss")


def pair_summary(output):
    reports, tails, values = {}, {}, {}
    for task in TASKS:
        arm = task["arm"]
        folder = Path(output) / arm / "B7_s2029"
        reports[arm] = read(folder / "B7_development_09.json")
        tails[arm] = read(folder / "B7_tail_09.json")
        summary = reports[arm]["groups"]["all"]["summary"]
        strong = tails[arm]["strata"][4:]
        count = sum(row["n_rain"] for row in strong)
        if count <= 0:
            raise ValueError("No strong-rain diagnostic population")
        physical = tails[arm]["physical_pinball"]
        if physical["scale_mm_h"] != PHYSICAL_SCALE_MM_H:
            raise ValueError("Physical evaluation scale changed")
        expected_bins = [(row["lower"], row["upper"], row["n_rain"]) for row in tails[arm]["strata"]]
        actual_bins = [(row["lower"], row["upper"], row["n_rain"]) for row in physical["strata"]]
        if actual_bins != expected_bins or sum(row["n_rain"] for row in physical["strata"]) != summary["n_rain"]:
            raise ValueError("Physical and log diagnostic populations differ")
        values[arm] = {
            "all_log_pinball": summary["conditional_pinball"],
            "all_physical_pinball": physical_mean(physical["strata"]),
            "strong_log_pinball": math.fsum(row["conditional_pinball"] * row["n_rain"] for row in strong) / count,
            "strong_physical_pinball": physical_mean(physical["strata"][4:]),
            "brier": summary["brier"],
            "occurrence_ap": summary["average_precision"],
            "occurrence_auroc": summary["auroc"],
        }
        if not all(math.isfinite(value) for value in values[arm].values()):
            raise ValueError("A required screen metric is not finite")
    control, candidate = (task["arm"] for task in TASKS)
    paired_difference(reports[control], reports[candidate])
    for group, baseline in reports[control]["groups"].items():
        actual = reports[candidate]["groups"][group]
        if (baseline["source_sha"] != actual["source_sha"]
                or baseline["summary"]["n_rain"] != actual["summary"]["n_rain"]):
            raise ValueError("Paired source or wet population differs")
    if [(row["lower"], row["upper"], row["n_rain"]) for row in tails[control]["strata"]] != [
        (row["lower"], row["upper"], row["n_rain"]) for row in tails[candidate]["strata"]
    ]:
        raise ValueError("Paired rain strata differ")
    differences = {key: values[candidate][key] - values[control][key] for key in values[control]}
    contract = evaluation_contract()
    gates = {key: differences[key] < -TOLERANCE for key in contract["required_improvements"]}
    gates.update({key: differences[key] <= TOLERANCE for key in contract["lower_guardrails"]})
    gates.update({key: differences[key] >= -TOLERANCE for key in contract["higher_guardrails"]})
    return {
        "values": values,
        "candidate_minus_control": differences,
        "development_screen_gates": gates,
        "screen_passed": all(gates.values()),
        "evaluation_contract": contract,
        "scientific_acceptance": "NOT_VERIFIED",
        "researcher_knowledge": "NOT_ASSESSED",
        "interpretation": "SINGLE_SEED_REUSED_DEV_NO_SIGNIFICANCE_OR_FINAL_MODEL_CLAIM",
    }


def execute(root, proposal_path, private_path, approval_path, commit):
    started = time.monotonic()
    proposal, private, approval, _ = checked(root, proposal_path, private_path, approval_path, commit)
    package = Path(private["output_root"])
    if package.exists():
        raise PermissionError("Output already exists; approval consumed, no restart")
    if shutil.disk_usage(package.parent).free < proposal["budget"]["initial_free_bytes"]:
        raise RuntimeError("Initial48GiB reserve required")
    admission = resources()
    package.mkdir()
    write(package / "authorization_binding.json", {"approval": approval, "controller_pid": os.getpid(), "admission": admission})
    active = None
    totals = {"updates": 0, "source_bytes": 0, "source_files": 0}
    try:
        for index, task in enumerate(TASKS):
            remaining = proposal["budget"]["max_package_seconds"] - (time.monotonic() - started)
            if remaining <= 0:
                raise RuntimeError("Package12h cap reached")
            write(package / f"task_{index + 1}_claim.json", {"index": index, "controller_pid": os.getpid(), "code_commit": commit})
            command = [sys.executable, "-B", str(root / ENTRY), "worker", "--proposal", str(proposal_path),
                       "--private-preparation", str(private_path), "--researcher-approval", str(approval_path), "--task-index", str(index)]
            environment = dict(os.environ, PYTHONHASHSEED="2029", CUBLAS_WORKSPACE_CONFIG=":4096:8",
                               OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUTF8="1")
            with (package / (task["arm"] + "_console.log")).open("xb") as stream:
                active = subprocess.Popen(command, cwd=root, env=environment, stdout=stream,
                                          stderr=subprocess.STDOUT, creationflags=worker_creation_flags())
                try:
                    result_code = active.wait(timeout=min(remaining, proposal["budget"]["max_model_seconds"]))
                except subprocess.TimeoutExpired:
                    active.kill()
                    active.wait()
                    raise RuntimeError("Task deadline reached; no retry")
            active = None
            if result_code:
                raise RuntimeError("Task failed; remaining tasks blocked")
            result = read(package / task["arm"] / "B7_s2029/completion.json")
            if (result["status"] != "COMPLETE_TRAIN_AND_DEV_EVALUATION" or result["code_commit"] != commit
                    or result["optimizer_updates"] != 4320 or result["replay"] != 0
                    or result["total_logical_source_bytes"] != proposal["budget"]["source_bytes_per_model"]
                    or result["total_logical_source_files"] != proposal["budget"]["source_files_per_model"]):
                raise RuntimeError("Exact task closure differs")
            verify_loss_receipts(package / task["arm"] / "B7_s2029", task)
            totals["updates"] += result["optimizer_updates"]
            totals["source_bytes"] += result["total_logical_source_bytes"]
            totals["source_files"] += result["total_logical_source_files"]
        if totals != {"updates": 8640, "source_bytes": proposal["budget"]["total_source_bytes"], "source_files": proposal["budget"]["total_source_files"]}:
            raise RuntimeError("Exact package closure differs")
        write(package / "paired_loss_summary.json", pair_summary(package))
        if time.monotonic() - started > proposal["budget"]["max_package_seconds"]:
            raise RuntimeError("Closure exceeded package12h cap")
        write(package / "completion.json", {"status": "COMPLETE_TRAIN_AND_DEV_EVALUATION", "code_commit": commit, **totals})
    except BaseException as error:
        if active is not None and active.poll() is None:
            active.kill()
            active.wait()
        write(package / "failure.json", {"status": "STOP_NO_AUTOMATIC_RETRY", "error": type(error).__name__ + ": " + str(error)})
        raise
