"""One approval-bound ZERO_DOTE control paired with saved REAL/COSINE9."""

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
from ..phase_b_v2_ablations.schedule import COSINE9, schedule_identity
from .cosine9_training import budget, code_hashes as inherited_hashes, verify_schedule_receipts
from .dote_numeric_control import ZeroNumericDote
from .dynamic_training import run_task, runtime_binding
from .multiseed import load_inherited, worker_creation_flags
from .static_training import validate_approval
from .upper_quantile_diagnostics import UpperQuantileTail
from .upper_quantile_training import physical_mean


ENTRY = "tools/research_readiness/start_zero_cosine9.py"
TASKS = [{"model": "B7", "seed": 2029, "schedule_profile": COSINE9,
          "dynamic_control": "ZERO_NUMERIC_RETAIN_REAL_MASKS"}]
REAL_CODE = "e54ccc16f988628e2dc6c4b91f76051ae94c4629"
TERMINAL = "docs/research_readiness/20261110_cosine9/TERMINAL_VERIFICATION.json"
FILES = (ENTRY, "src/yuntapr/experimental/research_readiness/zero_cosine9_training.py",
         "src/yuntapr/experimental/research_readiness/dote_numeric_control.py")
ALLOWED_INHERITED_DIFFERENCES = {"tools/research_readiness/start_independent_process.py"}


def code_hashes(root):
    result = inherited_hashes(root)
    result.update({name: sha(Path(root) / name) for name in FILES})
    return result


def evaluation_contract():
    return {
        "direction": "REAL_MINUS_ZERO", "endpoint": "FIXED_EPOCH_9_LAST",
        "primary": "all_log_pinball",
        "desired_directions": {"all_log_pinball": "LT_ZERO", "strong_log_pinball": "LT_ZERO",
                               "strong_physical_pinball": "LE_ZERO", "weak_log_pinball": "LE_ZERO",
                               "brier": "LE_ZERO", "occurrence_ap": "GE_ZERO", "occurrence_auroc": "GE_ZERO"},
        "additional_report": ["all_physical_pinball"],
        "strong_definition": "R>20 mm/h, original valid mask",
        "weak_definition": "0.1<R<=1 mm/h, original valid mask",
        "physical_scale_mm_h": 20.0,
        "minimum_meaningful_effect": None, "allowed_deterioration": None,
        "decision_rule": "DESCRIPTIVE_SIGNED_DIFFERENCES_NO_AUTOMATIC_SCIENTIFIC_PASS",
        "terrain_mechanism": "NOT_TESTED_BY_THIS_MINIMUM_SCREEN",
        "point_metrics": "EXISTING_REAL_V4_ONLY_NO_NEW_POINT_EVALUATION",
        "scientific_acceptance": "NOT_VERIFIED", "researcher_knowledge": "NOT_ASSESSED",
    }


def real_binding(root, parent_path, real):
    """Validate saved JSON identities without opening any checkpoint or source payload."""
    root, real = Path(root), Path(real)
    parent, terminal = read(parent_path), read(root / TERMINAL)
    if digest({k: v for k, v in parent.items() if k != "proposal_sha256"}) != parent["proposal_sha256"]:
        raise ValueError("Parent proposal identity differs")
    differences = sorted(name for name, expected in parent["code_sha256"].items()
                         if sha(root / name) != expected)
    if set(differences) - ALLOWED_INHERITED_DIFFERENCES:
        raise ValueError("An inherited numerical dependency changed: " + str(differences))
    if terminal["engineering"] != "PASS" or terminal["code_commit"] != REAL_CODE:
        raise ValueError("Completed REAL/COSINE9 evidence is required")
    names = ("completion.json", "B7_development_09.json", "B7_tail_09.json",
             "paired_initial_identity.json", "paired_orders.json", "B7_LAST_epoch_09.receipt.json")
    identities = {}
    for name in names:
        actual = {"bytes": (real / name).stat().st_size, "sha256": sha(real / name)}
        if actual != terminal["input_identities"]["CANDIDATE_COSINE9/" + name]:
            raise ValueError("Saved REAL metadata changed: " + name)
        identities[name] = actual
    completion = read(real / "completion.json")
    if (completion["code_commit"] != REAL_CODE or completion["optimizer_updates"] != 4320
            or completion["replay"] != 0 or completion["schedule"] != schedule_identity()
            or completion["total_logical_source_bytes"] != 477571953840
            or completion["total_logical_source_files"] != 142813):
        raise ValueError("Saved REAL closure differs")
    if read(real / "B7_development_09.json")["source_identity"] != parent["data"]:
        raise ValueError("Saved REAL population differs")
    initial, orders = read(real / "paired_initial_identity.json"), read(real / "paired_orders.json")
    if initial["B7"]["full_state_sha256"] != terminal["initial_full_state"]:
        raise ValueError("Saved REAL initialization differs")
    for epoch in range(1, 10):
        if digest(orders[str(epoch)]["ids"]) != orders[str(epoch)]["sha256"]:
            raise ValueError("Saved REAL sample order is inconsistent")
    if read(real / "B7_LAST_epoch_09.receipt.json")["checkpoint_sha256"] != terminal["new_E9_checkpoint"]["sha256"]:
        raise ValueError("Saved REAL checkpoint receipt differs")
    admission = read(real.parent / "authorization_binding.json")["admission"]
    return {
        "code_commit": REAL_CODE, "metadata_files": identities,
        "checkpoint_identity": terminal["new_E9_checkpoint"],
        "checkpoint_evidence": "INHERITED_ACTUAL_HASH_AND_RECEIPT_NO_CURRENT_PAYLOAD_READ",
        "terminal_sha256": sha(root / TERMINAL),
        "changed_inherited_dependencies": differences,
        "origin": {"original_model_state_sha256": initial["B7"]["full_state_sha256"],
                   "epoch_order_sha256": [orders[str(e)]["sha256"] for e in range(1, 10)]},
        "hardware_binding": {k: admission[k] for k in ("cuda_name", "cuda_total_bytes")},
        "environment_limit": "RECORDED_RUNTIME_GPU_MATCH_HISTORICAL_DRIVER_CUDNN_UNAVAILABLE",
    }


def prepare(root, parent_path, parent_private, real, output_root):
    root, output_root = Path(root), Path(output_root).resolve()
    if output_root.exists() or not output_root.parent.is_dir():
        raise PermissionError("A fresh output under an existing parent is required")
    parent, locations = read(parent_path), read(parent_private)
    if locations["proposal_sha256"] != parent["proposal_sha256"]:
        raise ValueError("Parent public/private identities differ")
    if sha(Path(locations["inherited"])) != locations["inherited_file_sha256"]:
        raise ValueError("Frozen manifest wrapper changed")
    _, prepared = load_inherited(locations["inherited"])
    if prepared["data"] != parent["data"] or runtime_binding() != parent["runtime_binding"]:
        raise ValueError("Inherited data or runtime differs")
    binding = real_binding(root, parent_path, real)
    choices = copy.deepcopy(parent["scientific_choices"])
    choices.pop("control_reuse")
    choices.update(
        only_intervention="ZERO_EIGHT_DOTE_NUMBERS_RETAIN_REAL_MASKS_UNDER_COSINE9",
        dynamic_control="ZERO_NUMERIC_RETAIN_REAL_MASKS", real_masks_retained=True,
        structurally_zero_loss_gradient_weights=128, effective_capacity_equivalence="NOT_ESTABLISHED",
        origin_reference={"B7": binding["origin"]}, real_reuse=binding,
        evaluation=evaluation_contract(), decision_status="PROPOSED_PENDING_EXACT_RESEARCHER_APPROVAL",
    )
    caps, admission = budget(prepared), resources()
    if any(admission[k] != v for k, v in binding["hardware_binding"].items()):
        raise ValueError("Saved REAL GPU identity differs")
    free = shutil.disk_usage(output_root.parent).free
    if free < caps["initial_free_bytes"]:
        raise RuntimeError("24GiB free storage is required")
    proposal = {
        "status": "READY_WAITING_EXACT_RESEARCHER_APPROVAL", "authorized": False,
        "tasks": copy.deepcopy(TASKS), "data": parent["data"],
        "protocol": dict(parent["protocol"], dynamic_control="ZERO_NUMERIC_RETAIN_REAL_MASKS"),
        "scientific_choices": choices, "budget": caps, "runtime_binding": runtime_binding(),
        "code_sha256": code_hashes(root), "static_source_sha256": parent["static_source_sha256"],
        "source_scope_summary": parent["source_scope_summary"],
        "parent_proposal_identity": {"bytes": Path(parent_path).stat().st_size, "sha256": sha(parent_path)},
        "resources": {"output_volume_free_bytes": free, "admission": admission},
        "preparation_activity": {"raw_payload_opens": 0, "static_payload_opens": 0,
                                 "checkpoint_loads": 0, "optimizer_updates": 0},
    }
    proposal["proposal_sha256"] = digest(proposal)
    private = {k: locations[k] for k in ("inherited", "inherited_file_sha256", "terrain")}
    private.update(proposal_sha256=proposal["proposal_sha256"], output_root=str(output_root),
                   real=str(Path(real).resolve()), parent_proposal=str(Path(parent_path).resolve()))
    return proposal, private


def validate_scope(proposal):
    p, choices = proposal.get("protocol", {}), proposal.get("scientific_choices", {})
    if (proposal.get("tasks") != TASKS or p.get("loss") != "E0" or p.get("lambda_q") != 1.0
            or p.get("seed") != 2029 or p.get("epochs") != 9 or p.get("endpoint") != "FIXED_EPOCH_9"
            or p.get("schedule_profile") != COSINE9 or p.get("quantile_profile") != "UNIFORM"
            or p.get("dynamic_control") != "ZERO_NUMERIC_RETAIN_REAL_MASKS"
            or choices.get("dynamic_control") != "ZERO_NUMERIC_RETAIN_REAL_MASKS"
            or choices.get("candidate_schedule") != schedule_identity()
            or choices.get("evaluation") != evaluation_contract()):
        raise PermissionError("Only the single ZERO_DOTE/2029 uniform E0 COSINE9 task is supported")


def checked(root, proposal_path, private_path, approval_path, commit):
    if not Path(approval_path).is_file():
        raise PermissionError("New exact researcher approval is required")
    proposal, private, approval = map(read, (proposal_path, private_path, approval_path))
    validate_scope(proposal)
    validate_approval(approval, proposal, private, commit)
    if digest({k: v for k, v in proposal.items() if k != "proposal_sha256"}) != proposal["proposal_sha256"]:
        raise ValueError("Proposal digest differs")
    if private["proposal_sha256"] != proposal["proposal_sha256"] or code_hashes(root) != proposal["code_sha256"]:
        raise ValueError("Approved code or private binding differs")
    if runtime_binding() != proposal["runtime_binding"] or sha(Path(private["inherited"])) != private["inherited_file_sha256"]:
        raise ValueError("Runtime or frozen manifest wrapper differs")
    if sha(Path(private["parent_proposal"])) != proposal["parent_proposal_identity"]["sha256"]:
        raise ValueError("Parent proposal changed")
    if real_binding(root, private["parent_proposal"], private["real"]) != proposal["scientific_choices"]["real_reuse"]:
        raise ValueError("Bound REAL evidence changed")
    _, prepared = load_inherited(private["inherited"])
    if prepared["data"] != proposal["data"] or budget(prepared) != proposal["budget"]:
        raise ValueError("Frozen population or exact budget differs")
    return proposal, private, approval, prepared


def worker(root, proposal_path, private_path, approval_path, commit):
    proposal, private, approval, prepared = checked(root, proposal_path, private_path, approval_path, commit)
    package = Path(private["output_root"])
    binding, claim = read(package / "authorization_binding.json"), read(package / "task_1_claim.json")
    if (binding["controller_pid"] != os.getppid() or binding["approval"] != approval
            or claim != {"index": 0, "controller_pid": os.getppid(), "code_commit": commit}):
        raise PermissionError("A live once-only parent claim is required")
    return run_task(
        root, proposal, private, approval, prepared, commit, "B7", 2029,
        started=binding["started_monotonic"], pair_reference=Path(private["real"]),
        static_name="ZERO_DOTE_static_source.sqlite", dynamic_transform_factory=ZeroNumericDote,
        quantile_profile="UNIFORM", lambda_q=1.0, schedule_profile=COSINE9, tail_factory=UpperQuantileTail,
    )


def descriptive_comparison(real, zero):
    """Read saved summaries and report REAL minus ZERO, without importing S9 gates."""
    reports, tails, values = {}, {}, {}
    for arm, folder in (("REAL", real), ("ZERO", zero)):
        reports[arm] = read(Path(folder) / "B7_development_09.json")
        tails[arm] = read(Path(folder) / "B7_tail_09.json")
        summary, tail = reports[arm]["groups"]["all"]["summary"], tails[arm]
        bins = [(r["lower"], r["upper"], r["n_rain"]) for r in tail["strata"]]
        physical = tail["physical_pinball"]
        if (physical["scale_mm_h"] != 20.0 or sum(r[2] for r in bins) != summary["n_rain"]
                or bins != [(r["lower"], r["upper"], r["n_rain"]) for r in physical["strata"]]
                or [r[:2] for r in bins] != [(0.1, 1), (1, 5), (5, 10), (10, 20),
                                             (20, 30), (30, 50), (50, None)]):
            raise ValueError("Saved rainfall strata or physical score populations differ")
        count = sum(r["n_rain"] for r in tail["strata"][4:])
        if count <= 0:
            raise ValueError("No strong-rain diagnostic population")
        values[arm] = {
            "all_log_pinball": summary["conditional_pinball"],
            "all_physical_pinball": physical_mean(physical["strata"]),
            "strong_log_pinball": math.fsum(r["conditional_pinball"] * r["n_rain"]
                                            for r in tail["strata"][4:]) / count,
            "strong_physical_pinball": physical_mean(physical["strata"][4:]),
            "brier": summary["brier"], "occurrence_ap": summary["average_precision"],
            "occurrence_auroc": summary["auroc"], "weak_log_pinball": tail["strata"][0]["conditional_pinball"],
        }
        if not all(math.isfinite(v) for v in values[arm].values()):
            raise ValueError("Required descriptive metrics must be finite")
    paired = paired_difference(reports["ZERO"], reports["REAL"])
    for group, real_group in reports["REAL"]["groups"].items():
        zero_group = reports["ZERO"]["groups"][group]
        if real_group["source_sha"] != zero_group["source_sha"] or real_group["summary"]["n_rain"] != zero_group["summary"]["n_rain"]:
            raise ValueError("Paired source or wet population differs")
    if [(r["lower"], r["upper"], r["n_rain"]) for r in tails["REAL"]["strata"]] != [
            (r["lower"], r["upper"], r["n_rain"]) for r in tails["ZERO"]["strata"]]:
        raise ValueError("Paired rainfall strata differ")
    differences = {k: values["REAL"][k] - values["ZERO"][k] for k in values["REAL"]}
    relative = {k: 100.0 * differences[k] / values["ZERO"][k] if values["ZERO"][k] else None
                for k in differences}
    for group in paired["groups"].values():
        group["rain_strata_conditional_pinball_real_minus_zero"] = group.pop("rain_strata_conditional_pinball_B4_minus_B3")
    return {
        "values": values, "real_minus_zero": differences, "relative_to_zero_percent": relative,
        "relative_denominator_zero": "NULL_UNDEFINED", "six_group_real_minus_zero": paired["groups"],
        "rainfall_strata": {k: tails[k]["strata"] for k in ("REAL", "ZERO")},
        "physical_rainfall_strata": {k: tails[k]["physical_pinball"]["strata"] for k in ("REAL", "ZERO")},
        "evaluation_contract": evaluation_contract(), "scientific_acceptance": "NOT_VERIFIED",
        "researcher_knowledge": "NOT_ASSESSED", "independent_event_count": "NOT_IDENTIFIED",
    }


def execute(root, proposal_path, private_path, approval_path, commit):
    started = time.monotonic()
    proposal, private, approval, prepared = checked(root, proposal_path, private_path, approval_path, commit)
    package = Path(private["output_root"])
    if package.exists():
        raise PermissionError("Approval consumed/output exists")
    if shutil.disk_usage(package.parent).free < proposal["budget"]["initial_free_bytes"]:
        raise RuntimeError("Initial24GiB reserve required")
    volumes = {Path(name).anchor for scope in prepared["roles"].values() for name in scope["files"]}
    if not volumes or any(not Path(volume).is_dir() for volume in volumes):
        raise RuntimeError("A frozen source volume is unavailable")
    admission = resources()
    if any(admission[k] != v for k, v in proposal["scientific_choices"]["real_reuse"]["hardware_binding"].items()):
        raise ValueError("Saved REAL GPU identity differs")
    package.mkdir()
    active = None
    try:
        write(package / "authorization_binding.json", {
            "approval": approval, "controller_pid": os.getpid(), "admission": admission,
            "started_monotonic": started, "dynamic_control": "ZERO_NUMERIC_RETAIN_REAL_MASKS",
        })
        write(package / "task_1_claim.json", {"index": 0, "controller_pid": os.getpid(), "code_commit": commit})
        command = [sys.executable, "-B", str(Path(root) / ENTRY), "worker", "--proposal", str(proposal_path),
                   "--private-preparation", str(private_path), "--researcher-approval", str(approval_path)]
        environment = dict(os.environ, PYTHONHASHSEED="2029", CUBLAS_WORKSPACE_CONFIG=":4096:8",
                           OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUTF8="1")
        with (package / "ZERO_DOTE_console.log").open("xb") as stream:
            active = subprocess.Popen(command, cwd=root, env=environment, stdout=stream,
                                      stderr=subprocess.STDOUT, creationflags=worker_creation_flags())
            try:
                rc = active.wait(timeout=max(0, proposal["budget"]["max_package_seconds"] - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                active.kill()
                active.wait()
                raise RuntimeError("Six-hour deadline reached")
        active = None
        if rc:
            raise RuntimeError("ZERO_DOTE worker failed")
        folder = package / "B7_s2029"
        result = read(folder / "completion.json")
        if (result["status"] != "COMPLETE_TRAIN_AND_DEV_EVALUATION" or result["code_commit"] != commit
                or result["optimizer_updates"] != 4320 or result["replay"] != 0
                or result["total_logical_source_bytes"] != proposal["budget"]["total_source_bytes"]
                or result["total_logical_source_files"] != proposal["budget"]["total_source_files"]
                or result.get("schedule") != schedule_identity()):
            raise RuntimeError("Exact ZERO_DOTE closure differs")
        verify_schedule_receipts(folder)
        comparison = descriptive_comparison(Path(private["real"]), folder)
        write(package / "real_zero_descriptive_comparison.json", comparison)
        if time.monotonic() - started > proposal["budget"]["max_package_seconds"]:
            raise RuntimeError("Closure exceeded the six-hour cap")
        write(package / "completion.json", {"status": "COMPLETE_TRAIN_AND_DEV_EVALUATION",
              "code_commit": commit, "updates": 4320, "dynamic_control": "ZERO_NUMERIC_RETAIN_REAL_MASKS",
              "source_bytes": result["total_logical_source_bytes"], "source_files": result["total_logical_source_files"],
              "schedule": schedule_identity(), "scientific_acceptance": "NOT_VERIFIED"})
    except BaseException as error:
        if active is not None and active.poll() is None:
            active.kill()
            active.wait()
        write(package / "failure.json", {"status": "STOP_NO_AUTOMATIC_RETRY", "error": type(error).__name__ + ": " + str(error)})
        raise
