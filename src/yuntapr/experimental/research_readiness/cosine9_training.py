"""One approval-bound cosine9 candidate against the saved, reviewed UQ E0 control."""

import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from ..core_innovation.stage3.planning import digest
from ..core_innovation.stage4.data import read, sha
from ..core_innovation.stage4.engine import resources, write
from ..phase_b_v2_ablations.schedule import COSINE9, schedule_identity, scheduled_lr
from .dynamic_training import run_task, runtime_binding
from .multiseed import load_inherited, worker_creation_flags
from .static_training import validate_approval
from .upper_quantile_diagnostics import UpperQuantileTail
from .upper_quantile_training import code_hashes as inherited_hashes
from .upper_quantile_training import evaluation_contract, pair_summary, verify_loss_receipts


ENTRY = "tools/research_readiness/start_cosine9.py"
TASKS = [{"model": "B7", "seed": 2029, "schedule_profile": COSINE9}]
FILES = (ENTRY, "src/yuntapr/experimental/phase_b_v2_ablations/schedule.py",
         "src/yuntapr/experimental/research_readiness/cosine9_training.py")
ALLOWED_SOURCE_DIFFERENCES = {
    "src/yuntapr/experimental/core_innovation/stage4/engine.py",
    "src/yuntapr/experimental/research_readiness/dynamic_training.py",
    "src/yuntapr/experimental/research_readiness/upper_quantile_training.py",
    "tools/research_readiness/start_independent_process.py",
}
CONTROL_CODE = "f43b4225fef462a31035d59a06b85f31e5b257dc"


def code_hashes(root):
    result = inherited_hashes(root)
    result.update({name: sha(Path(root) / name) for name in FILES})
    return result


def budget(prepared):
    source_bytes = 9 * sum(scope["bytes_per_pass"] for scope in prepared["roles"].values()) + 312828
    source_files = 9 * sum(scope["file_count"] for scope in prepared["roles"].values()) + 1
    if (source_bytes, source_files) != (477571953840, 142813):
        raise ValueError("Frozen one-model source scope differs")
    return {
        "models": 1, "updates_per_model": 4320, "total_updates": 4320,
        "source_bytes_per_model": source_bytes, "source_files_per_model": source_files,
        "total_source_bytes": source_bytes, "total_source_files": source_files,
        "max_model_seconds": 21600, "max_package_seconds": 21600,
        "initial_free_bytes": 24 * 1024**3, "minimum_task_free_bytes": 24 * 1024**3,
        "replay_allowance": 0, "additional_retry_allowance": 0, "checkpoint_loads": 0,
    }


def control_binding(root, parent_proposal, control):
    """Read saved JSON, hash relevant metadata, and stat the already-hashed checkpoint."""
    root, control = Path(root), Path(control)
    parent = read(parent_proposal)
    if digest({key: value for key, value in parent.items() if key != "proposal_sha256"}) != parent["proposal_sha256"]:
        raise ValueError("Parent proposal identity differs")
    if runtime_binding() != parent["runtime_binding"]:
        raise ValueError("The reviewed control numerical runtime differs")
    differences = sorted(name for name, expected in parent["code_sha256"].items() if sha(root / name) != expected)
    if set(differences) - ALLOWED_SOURCE_DIFFERENCES:
        raise ValueError("A non-treatment numerical dependency changed: " + str(differences))
    terminal_path = root / "docs/research_readiness/20261108_upper_quantile_pair/TERMINAL_VERIFICATION.json"
    review_path = root / "docs/research_readiness/20261108_upper_quantile_pair/TERMINAL_REVIEW_ACK.json"
    results_path = root / "docs/research_readiness/20261108_upper_quantile_pair/RESULTS.json"
    terminal, review = read(terminal_path), read(review_path)
    if terminal["engineering"] != "PASS" or review["engineering"] != "PASS" or terminal["code_commit"] != CONTROL_CODE:
        raise ValueError("Completed reviewed control is required")
    old = terminal["arms"]["CONTROL_E0"]
    names = {"completion": "completion.json", "e9_report": "B7_development_09.json", "e9_tail": "B7_tail_09.json"}
    identities = {}
    for key, name in names.items():
        path = control / name
        actual = {"bytes": path.stat().st_size, "sha256": sha(path)}
        if actual != old[key]:
            raise ValueError("Reviewed control metadata changed: " + name)
        identities[name] = actual
    completion = read(control / "completion.json")
    if (completion["code_commit"] != CONTROL_CODE or completion["optimizer_updates"] != 4320
            or completion["status"] != "COMPLETE_TRAIN_AND_DEV_EVALUATION" or completion["replay"] != 0
            or completion["total_logical_source_bytes"] != 477571953840
            or completion["total_logical_source_files"] != 142813):
        raise ValueError("Control fixed E9 closure differs")
    verify_loss_receipts(control, {"quantile_profile": "UNIFORM"})
    receipt = read(control / "B7_LAST_epoch_09.receipt.json")
    if receipt["checkpoint_sha256"] != old["e9_checkpoint"]["sha256"]:
        raise ValueError("Control checkpoint receipt differs from the prior actual hash")
    if (control / "B7_LAST_epoch_09.pt").stat().st_size != old["e9_checkpoint"]["bytes"]:
        raise ValueError("Control checkpoint size differs")
    report = read(control / "B7_development_09.json")
    if report["source_identity"] != parent["data"]:
        raise ValueError("Control data identity differs")
    for name in ("paired_initial_identity.json", "paired_orders.json", "B7_LAST_epoch_09.receipt.json"):
        identities[name] = {"bytes": (control / name).stat().st_size, "sha256": sha(control / name)}
    saved_identities = read(results_path)["input_identities"]
    if any(actual != saved_identities["CONTROL_E0/" + name] for name, actual in identities.items()):
        raise ValueError("Control metadata differs from the reviewed result identities")
    initial, orders = read(control / "paired_initial_identity.json"), read(control / "paired_orders.json")
    control_admission = read(control.parents[1] / "authorization_binding.json")["admission"]
    if initial["B7"]["full_state_sha256"] != terminal["pair_identity"]["same_B7_initial_full_state"]:
        raise ValueError("Control initial state differs")
    for epoch in range(1, 10):
        if digest(orders[str(epoch)]["ids"]) != orders[str(epoch)]["sha256"]:
            raise ValueError("Control saved epoch order is inconsistent")
    return {
        "code_commit": CONTROL_CODE, "data": parent["data"], "runtime_binding": parent["runtime_binding"],
        "metadata_files": identities, "checkpoint_identity": old["e9_checkpoint"],
        "checkpoint_evidence": "PRIOR_DIRECT_HASH_AND_REVIEWED_RECEIPT; CURRENT_SIZE_STAT_ONLY_NO_LOAD",
        "origin": {"original_model_state_sha256": initial["B7"]["full_state_sha256"],
                   "epoch_order_sha256": [orders[str(epoch)]["sha256"] for epoch in range(1, 10)]},
        "changed_inherited_dependencies": differences,
        "source_delta_review_required": True,
        "terminal_verification_sha256": sha(terminal_path), "terminal_review_ack_sha256": sha(review_path),
        "results_sha256": sha(results_path),
        "hardware_binding": {key: control_admission[key] for key in ("cuda_name", "cuda_total_bytes")},
        "environment_limit": "RECORDED_RUNTIME_AND_GPU_MATCH; HISTORICAL_DRIVER_AND_CUDNN_FINGERPRINTS_UNAVAILABLE",
    }


def prepare(root, parent_proposal, parent_private, control, output_root):
    root, output_root = Path(root), Path(output_root).resolve()
    if output_root.exists() or not output_root.parent.is_dir():
        raise PermissionError("A fresh output under the selected existing parent is required")
    parent, locations = read(parent_proposal), read(parent_private)
    if locations["proposal_sha256"] != parent["proposal_sha256"]:
        raise ValueError("Parent public/private binding differs")
    if sha(Path(locations["inherited"])) != locations["inherited_file_sha256"]:
        raise ValueError("Frozen manifest wrapper changed")
    _, prepared = load_inherited(locations["inherited"])
    binding = control_binding(root, parent_proposal, control)
    if prepared["data"] != parent["data"] or parent["protocol"].get("loss") != "E0":
        raise ValueError("Frozen E0 population differs")
    caps = budget(prepared)
    admission = resources()
    if any(admission[key] != value for key, value in binding["hardware_binding"].items()):
        raise ValueError("The saved control GPU identity differs")
    free = shutil.disk_usage(output_root.parent).free
    if free < caps["initial_free_bytes"]:
        raise RuntimeError("A new single-model output requires24GiB free")
    keys = ("DOTE", "channels", "normalization", "spatial_operator", "scales", "condition_channels",
            "projection_width", "modulation_limit", "condition_mask", "precision", "architecture")
    choices = {key: copy.deepcopy(parent["scientific_choices"][key]) for key in keys}
    choices.update(
        only_intervention="COSINE_HORIZON_50_TO_9_EPOCHS",
        initialization="FRESH_ORIGINAL_FACTORY_MATCH_SAVED_CONTROL_NO_CHECKPOINT_LOAD",
        candidate_schedule=schedule_identity(), evaluation=evaluation_contract(),
        origin_reference={"B7": binding["origin"]}, control_reuse=binding,
        decision_status="PROPOSED_PENDING_EXACT_RESEARCHER_BUDGET_APPROVAL",
    )
    proposal = {
        "status": "READY_WAITING_EXACT_RESEARCHER_APPROVAL", "authorized": False,
        "tasks": copy.deepcopy(TASKS), "data": prepared["data"],
        "protocol": dict(parent["protocol"], models=["B7"], loss="E0", lambda_q=1.0,
                         quantile_profile="UNIFORM", schedule_profile=COSINE9, seed=2029),
        "scientific_choices": choices, "budget": caps, "runtime_binding": runtime_binding(),
        "code_sha256": code_hashes(root), "static_source_sha256": parent["static_source_sha256"],
        "source_scope_summary": parent["source_scope_summary"],
        "parent_proposal_identity": {"bytes": Path(parent_proposal).stat().st_size, "sha256": sha(Path(parent_proposal))},
        "preparation_activity": {"raw_payload_opens": 0, "checkpoint_loads": 0, "optimizer_updates": 0},
        "resources": {"output_volume_free_bytes": free, "admission": admission,
                      "RAM_GPU_admission": "INHERIT_AND_RECHECK_EXISTING_MINIMUM_AT_START"},
    }
    proposal["proposal_sha256"] = digest(proposal)
    private = {
        "proposal_sha256": proposal["proposal_sha256"], "inherited": locations["inherited"],
        "inherited_file_sha256": locations["inherited_file_sha256"], "terrain": locations["terrain"],
        "output_root": str(output_root), "control": str(Path(control).resolve()),
        "parent_proposal": str(Path(parent_proposal).resolve()),
    }
    return proposal, private


def validate_scope(proposal):
    protocol = proposal.get("protocol", {})
    if (proposal.get("tasks") != TASKS or protocol.get("loss") != "E0" or protocol.get("lambda_q") != 1.0
            or protocol.get("seed") != 2029 or protocol.get("epochs") != 9
            or protocol.get("endpoint") != "FIXED_EPOCH_9" or protocol.get("quantile_profile") != "UNIFORM"
            or protocol.get("schedule_profile") != COSINE9
            or proposal.get("scientific_choices", {}).get("candidate_schedule") != schedule_identity()
            or proposal["scientific_choices"].get("evaluation") != evaluation_contract()):
        raise PermissionError("Only the single B7 uniform E0 seed2029 cosine9 candidate is allowed")


def checked(root, proposal_path, private_path, approval_path, commit):
    if not Path(approval_path).is_file():
        raise PermissionError("External researcher approval is required before execution")
    proposal, private, approval = map(read, (proposal_path, private_path, approval_path))
    validate_scope(proposal)
    validate_approval(approval, proposal, private, commit)
    if digest({key: value for key, value in proposal.items() if key != "proposal_sha256"}) != proposal["proposal_sha256"]:
        raise ValueError("Proposal digest differs")
    if private["proposal_sha256"] != proposal["proposal_sha256"] or code_hashes(root) != proposal["code_sha256"]:
        raise ValueError("Approved code or private binding differs")
    if runtime_binding() != proposal["runtime_binding"] or sha(Path(private["inherited"])) != private["inherited_file_sha256"]:
        raise ValueError("Runtime or frozen manifest wrapper differs")
    if sha(Path(private["parent_proposal"])) != proposal["parent_proposal_identity"]["sha256"]:
        raise ValueError("Parent proposal changed")
    if control_binding(root, private["parent_proposal"], private["control"]) != proposal["scientific_choices"]["control_reuse"]:
        raise ValueError("Bound control identity changed")
    _, prepared = load_inherited(private["inherited"])
    if prepared["data"] != proposal["data"] or budget(prepared) != proposal["budget"]:
        raise ValueError("Frozen population or exact budget differs")
    return proposal, private, approval, prepared


def worker(root, proposal_path, private_path, approval_path, commit):
    started = time.monotonic()
    proposal, private, approval, prepared = checked(root, proposal_path, private_path, approval_path, commit)
    package = Path(private["output_root"])
    binding, claim = read(package / "authorization_binding.json"), read(package / "task_1_claim.json")
    if (binding["controller_pid"] != os.getppid() or binding["approval"] != approval
            or claim != {"index": 0, "controller_pid": os.getppid(), "code_commit": commit}):
        raise PermissionError("A live once-only parent claim is required")
    return run_task(
        root, proposal, private, approval, prepared, commit, "B7", 2029,
        started=started, pair_reference=Path(private["control"]), static_name="B7_static_source.sqlite",
        quantile_profile="UNIFORM", lambda_q=1.0, schedule_profile=COSINE9, tail_factory=UpperQuantileTail,
    )


def verify_schedule_receipts(folder):
    verify_loss_receipts(folder, {"quantile_profile": "UNIFORM"})
    for epoch in range(1, 10):
        training = read(Path(folder) / f"B7_train_{epoch:02d}.json")
        receipt = read(Path(folder) / f"B7_LAST_epoch_{epoch:02d}.receipt.json")
        if (training.get("schedule") != schedule_identity() or receipt.get("schedule") != schedule_identity()
                or training.get("first_lr") != scheduled_lr((epoch - 1) * 480 + 1, profile=COSINE9)
                or training.get("last_lr") != scheduled_lr(epoch * 480, profile=COSINE9)):
            raise ValueError("Per-epoch candidate schedule differs")


def execute(root, proposal_path, private_path, approval_path, commit):
    started = time.monotonic()
    proposal, private, approval, prepared = checked(root, proposal_path, private_path, approval_path, commit)
    package = Path(private["output_root"])
    if package.exists():
        raise PermissionError("Approval consumed/output exists; no restart")
    if shutil.disk_usage(package.parent).free < proposal["budget"]["initial_free_bytes"]:
        raise RuntimeError("Initial24GiB reserve required")
    source_volumes = {Path(name).anchor for scope in prepared["roles"].values() for name in scope["files"]}
    if any(not Path(volume).is_dir() for volume in source_volumes):
        raise RuntimeError("A frozen source volume is unavailable; no payload opened or package created")
    admission = resources()
    if any(admission[key] != value for key, value in proposal["scientific_choices"]["control_reuse"]["hardware_binding"].items()):
        raise ValueError("The saved control GPU identity differs")
    package.mkdir()
    write(package / "authorization_binding.json", {"approval": approval, "controller_pid": os.getpid(), "admission": admission})
    active = None
    try:
        write(package / "task_1_claim.json", {"index": 0, "controller_pid": os.getpid(), "code_commit": commit})
        command = [sys.executable, "-B", str(Path(root) / ENTRY), "worker", "--proposal", str(proposal_path),
                   "--private-preparation", str(private_path), "--researcher-approval", str(approval_path)]
        environment = dict(os.environ, PYTHONHASHSEED="2029", CUBLAS_WORKSPACE_CONFIG=":4096:8",
                           OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUTF8="1")
        with (package / "B7_console.log").open("xb") as stream:
            active = subprocess.Popen(command, cwd=root, env=environment, stdout=stream,
                                      stderr=subprocess.STDOUT, creationflags=worker_creation_flags())
            remaining = proposal["budget"]["max_package_seconds"] - (time.monotonic() - started)
            try:
                result_code = active.wait(timeout=max(0, remaining))
            except subprocess.TimeoutExpired:
                active.kill()
                active.wait()
                raise RuntimeError("Six-hour deadline reached; no retry")
        active = None
        if result_code:
            raise RuntimeError("Candidate failed; no automatic retry")
        folder = package / "B7_s2029"
        result = read(folder / "completion.json")
        if (result["status"] != "COMPLETE_TRAIN_AND_DEV_EVALUATION" or result["code_commit"] != commit
                or result["optimizer_updates"] != 4320 or result["replay"] != 0
                or result["total_logical_source_bytes"] != proposal["budget"]["total_source_bytes"]
                or result["total_logical_source_files"] != proposal["budget"]["total_source_files"]
                or result.get("schedule") != schedule_identity()):
            raise RuntimeError("Exact candidate closure differs")
        verify_schedule_receipts(folder)
        summary = pair_summary(package, arm_folders={"CONTROL_E0": Path(private["control"]), "CANDIDATE_COSINE9": folder})
        summary["control_reuse"] = proposal["scientific_choices"]["control_reuse"]
        write(package / "paired_schedule_summary.json", summary)
        if time.monotonic() - started > proposal["budget"]["max_package_seconds"]:
            raise RuntimeError("Closure exceeded the six-hour cap")
        write(package / "completion.json", {"status": "COMPLETE_TRAIN_AND_DEV_EVALUATION", "code_commit": commit,
              "updates": 4320, "source_bytes": result["total_logical_source_bytes"],
              "source_files": result["total_logical_source_files"], "schedule": schedule_identity()})
    except BaseException as error:
        if active is not None and active.poll() is None:
            active.kill()
            active.wait()
        write(package / "failure.json", {"status": "STOP_NO_AUTOMATIC_RETRY", "error": type(error).__name__ + ": " + str(error)})
        raise
