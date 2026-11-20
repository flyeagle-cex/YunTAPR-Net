"""Bind and run only the stopped TAIL20 E8-to-E9 replay."""

import argparse
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tools.research_readiness.start_tail20_aux import (
    BASE, BASELINE, TASKS, clean_commit, code_hashes as origin_code_hashes, matched_guard_hashes,
    reserve_disk, verify_admission,
)
from tools.research_readiness.start_independent_process import host_identity, require_independent
from yuntapr.experimental.core_innovation.stage3.planning import digest
from yuntapr.experimental.core_innovation.stage4.data import read, sha
from yuntapr.experimental.core_innovation.stage4.engine import write
from yuntapr.experimental.core_innovation.stage4.recovery import Tail20E8Resume, query
from yuntapr.experimental.phase_b_v2_ablations.schedule import COSINE9, schedule_identity
from yuntapr.experimental.phase_b_v2_ablations.tail20_aux import TAIL20_PROFILE, profile_identity
from yuntapr.experimental.research_readiness.dynamic_training import run_task, runtime_binding
from yuntapr.experimental.research_readiness.multiseed import load_inherited
from yuntapr.experimental.research_readiness.static_training import validate_approval
from yuntapr.experimental.research_readiness.tail20_evaluation import Tail20Observer

ENTRY = "tools/research_readiness/start_tail20_recovery.py"
DOCS = BASE + "20261119_conditional_intensity_diagnostic/"
ORIGINAL = DOCS + "TAIL20_EXECUTION_PROPOSAL.json"
STOP = DOCS + "TAIL20_STOP_RECEIPT.json"
SCOPE = "TAIL20_AUX_V1_E8_TO_E9_REPLAY"
MAX_SECONDS = 4500
STOPPED_TASK = "B7_s2029"
CHECKPOINT = "B7_LAST_epoch_08.pt"
CHANGED = {
    "src/yuntapr/experimental/core_innovation/stage4/engine.py",
    "src/yuntapr/experimental/core_innovation/stage4/recovery.py",
    "src/yuntapr/experimental/research_readiness/dynamic_training.py",
    "tools/research_readiness/start_independent_process.py",
}
PINS = (
    "paired_initial_identity.json", "paired_orders.json", "B7_train_09.json", "updates.sqlite",
    *(f"B7_development_{n:02d}.json" for n in range(1, 9)),
    *(f"B7_LAST_epoch_{n:02d}.receipt.json" for n in range(1, 9)),
)


def without_digest(doc):
    return {key: value for key, value in doc.items() if key != "proposal_sha256"}


def code_hashes():
    return origin_code_hashes() | {name: sha(ROOT / name) for name in {*CHANGED, ENTRY, ORIGINAL, STOP}}


def budget(prepared, stop, original_budget):
    scope = prepared["roles"]
    weather_bytes = sum(scope[role]["bytes_per_pass"] for role in ("Train", "Development"))
    weather_files = sum(scope[role]["file_count"] for role in ("Train", "Development"))
    source_bytes, source_files = weather_bytes + 312828, weather_files + 1
    if (source_bytes, source_files) != (53063828496, 15869):
        raise ValueError("Unexpected fixed E9 replay source scope")
    reserve = original_budget["minimum_task_free_bytes"]
    return dict(
        models=1, updates_per_model=480, total_updates=480, replay_allowance=480,
        effective_updates=4320, source_bytes_per_model=source_bytes, source_files_per_model=source_files,
        total_source_bytes=source_bytes, total_source_files=source_files, initial_free_bytes=reserve,
        minimum_task_free_bytes=reserve, max_model_seconds=MAX_SECONDS, max_package_seconds=MAX_SECONDS,
        checkpoint_rehashes=1, checkpoint_loads=1, development_passes=1, additional_retry_allowance=0,
        cumulative_updates=stop["returned_updates"] + 480,
        cumulative_source_bytes=stop["source_reserved_bytes"] + source_bytes,
        cumulative_source_files=stop["source_opened_files"] + source_files,
        cumulative_wall_budget_seconds=stop["wall_budget_seconds"] + MAX_SECONDS,
    )


def stopped_parent(original_private):
    original, stop, old = read(ROOT / ORIGINAL), read(ROOT / STOP), read(original_private)
    if (digest(without_digest(original)) != original["proposal_sha256"]
            or old["proposal_sha256"] != original["proposal_sha256"]
            or digest(without_digest(old)) != original["private_preparation_sha256"]
            or original["proposal_sha256"] != stop["parent_proposal_sha256"]
            or original["execution_code_commit"] != stop["parent_execution_commit"]):
        raise ValueError("Original TAIL20 approval identity changed")
    parent = Path(old["output_root"]) / STOPPED_TASK
    service = Path(old["service_dir"])
    failed = read(service / "independent_failure.json")
    if (not failed["error"].startswith("TimeoutExpired:")
            or not failed["error"].endswith("timed out after 21600 seconds")
            or failed["automatic_retry"] is not False
            or (service / "target_exit.json").exists()
            or (parent.parent / "completion.json").exists()
            or any((parent / name).exists() for name in
                   ("B7_LAST_epoch_09.pt", "B7_development_09.json", "B7_tail20_gate_09.json"))):
        raise ValueError("Exact stopped TAIL20 state required")
    if query(parent / "updates.sqlite", "SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state") != [
        ("B7", "RETURNED", 4320, 1, 4320)
    ]:
        raise ValueError("Stopped optimizer ledger differs")
    checkpoint = parent / CHECKPOINT
    seal = read(checkpoint.with_suffix(".receipt.json"))
    if (checkpoint.stat().st_size != stop["checkpoint_bytes"]
            or (seal["epoch"], seal["updates"], seal["checkpoint_sha256"], seal["code_commit"])
            != (8, 3840, stop["checkpoint_sha256"], original["execution_code_commit"])
            or seal["loss_config"] != profile_identity() or seal["schedule"] != schedule_identity()):
        raise ValueError("Exact E8 checkpoint metadata required")
    return original, stop, old, parent


def bind(original_private, output, service):
    original, stop, old, parent = stopped_parent(original_private)
    hashes = code_hashes()
    if any(hashes.get(name) != value for name, value in original["code_sha256"].items() if name not in CHANGED):
        raise ValueError("Unmodified scientific dependencies differ")
    if (sha(old["inherited"]) != old["inherited_file_sha256"]
            or original["scientific_choices"]["post_control_input_guard_sha256"] != matched_guard_hashes()
            or runtime_binding() != original["runtime_binding"]):
        raise ValueError("Inherited inputs, guard code or runtime changed")
    _, prepared = load_inherited(old["inherited"])
    if prepared["data"] != original["data"]:
        raise ValueError("Train or Development population changed")
    caps = budget(prepared, stop, original["budget"])
    reserve_disk(output, caps)
    replay = dict(model="B7", seed=2029, parent_execution_commit=original["execution_code_commit"],
                  checkpoint_epoch=8, checkpoint_updates=3840, checkpoint_sha256=stop["checkpoint_sha256"],
                  first_update=3841, last_update=4320, original_e9_train_digest=digest(read(parent / "B7_train_09.json")),
                  train_reproducibility="EXACT_CANONICAL_SUMMARY", checkpoint_before_development=True)
    private = dict(old, original_private=str(original_private), output_root=str(output), service_dir=str(service),
                   stopped_task=str(parent))
    private.pop("proposal_sha256")
    proposal = dict(
        status="READY_WAITING_EXACT_REPLAY_APPROVAL", authorized=False, authorization_scope=SCOPE,
        tasks=TASKS, protocol=original["protocol"], data=original["data"],
        static_source_sha256=original["static_source_sha256"],
        scientific_choices=dict(original["scientific_choices"], recovery=replay),
        budget=caps, runtime_binding=original["runtime_binding"], code_sha256=hashes,
        parent_pins={name: sha(parent / name) for name in PINS},
        supervisor_stop_sha256=sha(Path(old["service_dir"]) / "independent_failure.json"),
        original_private_sha256=sha(original_private), private_preparation_sha256=digest(private),
        final_2025_access=False,
    )
    return proposal, private, prepared


def prepare(original_private, output, service, commit):
    if not service.is_dir() or any(service.iterdir()):
        raise PermissionError("An empty fixed service namespace is required")
    p, v, _ = bind(original_private, output, service)
    verify_admission(p["scientific_choices"]["control_reuse"])
    p["execution_code_commit"] = commit
    p["proposal_sha256"] = digest(p)
    v["proposal_sha256"] = p["proposal_sha256"]
    return p, v


def checked(p, v, approval, commit):
    validate_approval(approval, p, v, commit)
    if (p.get("authorization_scope") != SCOPE or p.get("authorized") is not False
            or approval.get("approved_replay_updates") != 480 or p.get("execution_code_commit") != commit
            or digest(without_digest(p)) != p["proposal_sha256"] or v["proposal_sha256"] != p["proposal_sha256"]):
        raise PermissionError("A new exact 480-update recovery grant is required")
    current, private, prepared = bind(Path(v["original_private"]), Path(v["output_root"]), Path(v["service_dir"]))
    current["execution_code_commit"] = commit
    if current != without_digest(p) or private != without_digest(v):
        raise ValueError("The bound recovery inputs or budget changed")
    for filename, identity in p["scientific_choices"]["control_reuse"]["metadata_files"].items():
        file = Path(v["control"]) / filename
        if file.stat().st_size != identity["bytes"] or sha(file) != identity["sha256"]:
            raise ValueError("Matched control metadata changed")
    return prepared


def execute(p, v, approval, commit):
    started = time.monotonic()
    require_independent(host_identity())
    prepared = checked(p, v, approval, commit)
    volumes = {Path(name).anchor for scope in prepared["roles"].values() for name in scope["files"]}
    if not volumes or any(not Path(volume).is_dir() for volume in volumes):
        raise RuntimeError("A frozen source volume is unavailable")
    for key, value in {"PYTHONHASHSEED": "2029", "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
                       "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}.items():
        if os.environ.get(key) != value:
            raise PermissionError("Frozen replay environment differs")
    admission = verify_admission(p["scientific_choices"]["control_reuse"])
    replay = p["scientific_choices"]["recovery"]
    state = Tail20E8Resume(
        parent=Path(v["stopped_task"]), decision_id=approval["decision_id"], data_identity=p["data"],
        checkpoint_sha256=replay["checkpoint_sha256"], train_sha256=replay["original_e9_train_digest"],
        parent_pins=p["parent_pins"], parent_code_commit=replay["parent_execution_commit"],
    )
    package = Path(v["output_root"])
    baseline = read(ROOT / BASELINE)
    package.mkdir(exist_ok=False)
    try:
        write(package / "authorization_binding.json", dict(
            approval=approval, code_commit=commit, controller_pid=os.getpid(), admission=admission))
        result = run_task(
            ROOT, p, v, approval, prepared, commit, "B7", 2029, started=started,
            pair_reference=Path(v["control"]), static_name="B7_static_source.sqlite",
            quantile_profile=TAIL20_PROFILE, schedule_profile=COSINE9, recovery=state,
            final_dev_observer_factory=lambda pack, ids: Tail20Observer(pack, ids, baseline),
        )
        caps = p["budget"]
        if (result["status"] != "COMPLETE_TRAIN_AND_DEV_EVALUATION" or result["code_commit"] != commit
                or result["optimizer_updates"] != caps["effective_updates"]
                or result["segment_updates"] != caps["total_updates"] or result["replay"] != caps["replay_allowance"]
                or result["total_logical_source_bytes"] != caps["total_source_bytes"]
                or result["total_logical_source_files"] != caps["total_source_files"]
                or result["schedule"] != schedule_identity()):
            raise RuntimeError("TAIL20 replay endpoint differs from the bound run")
        folder = package / STOPPED_TASK
        checkpoint = read(folder / "B7_LAST_epoch_09.receipt.json")
        write(package / "completion.json", dict(
            status="COMPLETE_TRAIN_AND_DEV_EVALUATION", execution_code_commit=commit,
            proposal_sha256=p["proposal_sha256"], checkpoint_sha256=checkpoint["checkpoint_sha256"],
            optimizer_updates=result["optimizer_updates"], segment_updates=result["segment_updates"],
            replayed_updates=result["replay"], source_bytes=result["total_logical_source_bytes"],
            source_files=result["total_logical_source_files"], gate=read(folder / "B7_tail20_gate_09.json"),
            automatic_retry=False, final_2025_access=False,
        ))
    except BaseException as error:
        write(package / "failure.json", dict(status="STOP_NO_AUTOMATIC_RETRY",
              error_type=type(error).__name__, details=str(error)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    prep, launch = sub.add_parser("prepare"), sub.add_parser("execute")
    for child in (prep, launch):
        child.add_argument("--proposal", type=Path, required=True)
        child.add_argument("--private-preparation", type=Path, required=True)
    for name in ("original-private", "output-root", "service-dir"):
        prep.add_argument("--" + name, type=Path, required=True)
    launch.add_argument("--researcher-approval", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        original = args.original_private.resolve()
        local = original.parent.parent
        new_paths = (args.private_preparation, args.output_root, args.service_dir)
        if local.name != ".local" or any(
                not path.resolve().is_relative_to(local) or path.resolve().is_relative_to(original.parent)
                for path in new_paths):
            raise PermissionError("Use a fresh namespace beside the original under .local")
        if args.proposal.exists() or args.private_preparation.exists():
            raise FileExistsError("Use fresh proposal and binding files")
        p, v = prepare(original, args.output_root.resolve(), args.service_dir.resolve(), clean_commit())
        write(args.proposal, p)
        write(args.private_preparation, v)
    else:
        if not args.researcher_approval.is_file():
            raise PermissionError("Separate exact researcher approval is required")
        execute(read(args.proposal), read(args.private_preparation), read(args.researcher_approval), clean_commit())


if __name__ == "__main__":
    main()
