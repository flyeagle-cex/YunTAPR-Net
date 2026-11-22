"""Prepare and execute the exact A20 negative-coverage E5 continuation."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tools.research_readiness.start_independent_process import host_identity, require_independent
from tools.research_readiness.start_tail20_aux import (
    BASELINE, COVERAGE_ARM, COVERAGE_DIR, clean_commit, code_hashes, point_completion,
    reserve_disk, verify_admission,
)
from yuntapr.experimental.core_innovation.stage3.planning import digest
from yuntapr.experimental.core_innovation.stage4.data import read, sha
from yuntapr.experimental.core_innovation.stage4.recovery import CoverageE5Resume, query, write
from yuntapr.experimental.phase_b_v2_ablations.schedule import COSINE9, schedule_identity
from yuntapr.experimental.research_readiness.dynamic_training import run_task, runtime_binding
from yuntapr.experimental.research_readiness.multiseed import load_inherited
from yuntapr.experimental.research_readiness.static_training import validate_approval
from yuntapr.experimental.research_readiness.tail20_evaluation import Tail20Observer

ORIGIN_NAME = "A20_NEG_COVERAGE_EXECUTION_PROPOSAL.json"
ORIGIN_SHA = "787217dfedacf75dc6bdc21996446d2779d6ea30c96222a7bd331d74f670c10c"
CHECKPOINT_SHA = "f5f40426cdb6cafd515691df0cab49cc3077e1cd7de6dfbb372f9aedba925d77"
CHECKPOINT_BYTES = 53904709
KIND = "BOUNDED_A20_COVERAGE_E5_RECOVERY"
SCOPE = "A20_NEG_COVERAGE_V1_E5_TO_E9_RECOVERY"
ENTRY = "tools/research_readiness/start_a20_coverage_recovery.py"
MAX_SECONDS = 14400
CHANGED = {
    "src/yuntapr/experimental/core_innovation/stage4/engine.py",
    "src/yuntapr/experimental/core_innovation/stage4/recovery.py",
    "src/yuntapr/experimental/research_readiness/dynamic_training.py",
    "tools/research_readiness/start_tail20_aux.py",
    "tools/research_readiness/start_independent_process.py",
}
ENV = dict(PYTHONHASHSEED="2029", CUBLAS_WORKSPACE_CONFIG=":4096:8", OMP_NUM_THREADS="1",
           MKL_NUM_THREADS="1", PYTHONUTF8="1")


def unsigned(document):
    return {name: value for name, value in document.items() if name != "proposal_sha256"}


def stopped_parent(original_private):
    origin = read(ROOT / COVERAGE_DIR / ORIGIN_NAME)
    old = read(original_private)
    if (origin["proposal_sha256"] != ORIGIN_SHA or digest(unsigned(origin)) != ORIGIN_SHA
            or old["proposal_sha256"] != ORIGIN_SHA
            or digest(unsigned(old)) != origin["private_preparation_sha256"]):
        raise ValueError("Original A20 coverage proposal or private binding differs")
    output, service = Path(old["output_root"]), Path(old["service_dir"])
    parent = output / "B7_s2029"
    pause = read(service / "MANUAL_PAUSE.json")
    launch = read(service / "target_launch.json")
    if (pause["status"] != "SUSPENDED" or pause["proposal_sha256"] != ORIGIN_SHA
            or not pause["timer_continues"] or pause["worker_pid"] != launch["pid"]
            or pause["supervisor_pid"] != launch["supervisor_pid"]
            or datetime.now().astimezone() < datetime.fromisoformat(pause["latest_supervisor_deadline"])
            or (output / "completion.json").exists() or (parent / "B7_LAST_epoch_06.pt").exists()
            or (parent / "B7_train_06.json").exists()):
        raise ValueError("Expected the stopped, unsealed E6 segment after manual pause")
    if query(parent / "updates.sqlite", "SELECT model,state,count(*),min(u),max(u) FROM updates GROUP BY model,state") != [
        ("B7", "RETURNED", CoverageE5Resume.prior_updates, 1, CoverageE5Resume.prior_updates)
    ]:
        raise ValueError("Stopped update ledger differs")
    path = parent / "B7_LAST_epoch_05.pt"
    checkpoint = read(path.with_suffix(".receipt.json"))
    if (path.stat().st_size != CHECKPOINT_BYTES or checkpoint["checkpoint_sha256"] != CHECKPOINT_SHA
            or checkpoint["code_commit"] != origin["execution_code_commit"]
            or checkpoint["epoch"] != 5 or checkpoint["updates"] != 2400):
        raise ValueError("E5 checkpoint metadata differs")
    return origin, old, parent, pause


def source_accounting(parent):
    ledgers = [parent.parent / "B7_static_source.sqlite", *[
        parent / f"B7_{role}_reads_{epoch:02d}" / "reads.sqlite"
        for epoch in range(1, 6) for role in ("train", "dev")
    ], parent / "B7_train_reads_06" / "reads.sqlite"]
    reserved = opened = 0
    pins = {}
    for path in ledgers:
        rows = query(path, "SELECT count(*),coalesce(sum(expected_bytes),0) FROM file_io")
        count, size = rows[0]
        reserved += size
        opened += count
        pins[path.relative_to(parent.parent).as_posix()] = sha(path)
    return reserved, opened, pins


def bind(original_private, output, service, commit):
    origin, old, parent, pause = stopped_parent(original_private)
    hashes = code_hashes(COVERAGE_ARM)
    if any(hashes.get(name) != expected for name, expected in origin["code_sha256"].items() if name not in CHANGED):
        raise ValueError("Unchanged scientific files differ from the archived candidate")
    hashes.update({name: sha(ROOT / name) for name in CHANGED | {ENTRY}})
    if sha(old["inherited"]) != old["inherited_file_sha256"] or runtime_binding() != origin["runtime_binding"]:
        raise ValueError("Inherited input or numerical runtime differs")
    _, prepared = load_inherited(old["inherited"])
    if prepared["data"] != origin["data"]:
        raise ValueError("The frozen population differs")
    for name, identity in origin["scientific_choices"]["control_reuse"]["metadata_files"].items():
        path = Path(old["control"]) / name
        if path.stat().st_size != identity["bytes"] or sha(path) != identity["sha256"]:
            raise ValueError("Matched control evidence differs")
    state = CoverageE5Resume
    rounds = 9 - state.inherited_epochs
    represented = state.effective_updates - state.inherited_updates
    weather = tuple(prepared["roles"][key] for key in ("Train", "Development"))
    source_bytes = rounds * sum(role["bytes_per_pass"] for role in weather) + 312828
    source_files = rounds * sum(role["file_count"] for role in weather) + 1
    if (source_bytes, source_files) != (212254375500, 63473):
        raise ValueError("The exact four-round source scope differs")
    prior_bytes, prior_files, ledger_pins = source_accounting(parent)
    caps = dict(
        models=1, total_updates=represented, effective_updates=state.effective_updates,
        replay_allowance=state.replay_updates, additional_retry_allowance=0,
        total_source_bytes=source_bytes, total_source_files=source_files,
        max_model_seconds=MAX_SECONDS, max_package_seconds=MAX_SECONDS,
        checkpoint_loads=1, checkpoint_rehashes=1, inherited_checkpoint_bytes=CHECKPOINT_BYTES,
        development_passes=rounds, extra_development_passes=0,
        initial_free_bytes=origin["budget"]["initial_free_bytes"],
        minimum_task_free_bytes=origin["budget"]["minimum_task_free_bytes"],
        cumulative_updates=state.prior_updates + represented,
        cumulative_source_bytes=prior_bytes + source_bytes, cumulative_source_files=prior_files + source_files,
        cumulative_wall_budget_seconds=origin["budget"]["max_package_seconds"] + MAX_SECONDS,
    )
    reserve_disk(output, caps)
    runtime_handover = dict(
        checkpoint_epoch=state.inherited_epochs, checkpoint_updates=state.inherited_updates,
        checkpoint_sha256=CHECKPOINT_SHA, replay_first_update=state.inherited_updates + 1,
        replay_last_update=state.prior_updates, last_update=state.effective_updates,
        parent_proposal_sha256=ORIGIN_SHA, parent_execution_commit=origin["execution_code_commit"],
        prior_reserved_source_bytes=prior_bytes, prior_opened_source_files=prior_files,
        paused_at=pause["paused_at"], previous_wall_deadline=pause["latest_supervisor_deadline"],
    )
    private = dict(unsigned(old), original_private=str(original_private), output_root=str(output),
                   service_dir=str(service), stopped_task=str(parent))
    proposal = dict(
        status="READY_WAITING_EXACT_RECOVERY_APPROVAL", authorized=False, authorization_scope=SCOPE,
        execution_code_commit=commit, tasks=origin["tasks"], protocol=origin["protocol"], data=origin["data"],
        static_source_sha256=origin["static_source_sha256"], source_scope_summary=origin["source_scope_summary"],
        scientific_choices=dict(origin["scientific_choices"], recovery=runtime_handover),
        budget=caps, runtime_binding=origin["runtime_binding"], code_sha256=hashes, final_2025_access=False,
        prior_source_ledger_pins=ledger_pins,
        pause_receipt_sha256=sha(Path(old["service_dir"]) / "MANUAL_PAUSE.json"),
        parent_pins={name: sha(parent / name) for name in (*state.required_parent_files(), "updates.sqlite")},
        private_preparation_sha256=digest(private),
    )
    return proposal, private, prepared


def prepare(original, output, service, commit):
    if not service.is_dir() or any(service.iterdir()):
        raise PermissionError("A fresh independent service directory is required")
    p, v, _ = bind(original, output, service, commit)
    verify_admission(p["scientific_choices"]["control_reuse"])
    p["proposal_sha256"] = digest(p)
    v["proposal_sha256"] = p["proposal_sha256"]
    return p, v


def execute(p, v, approval, commit):
    started = time.monotonic()
    require_independent(host_identity())
    validate_approval(approval, p, v, commit)
    if (approval.get("approved_replay_updates") != CoverageE5Resume.replay_updates
            or digest(unsigned(p)) != p["proposal_sha256"] or v["proposal_sha256"] != p["proposal_sha256"]
            or any(os.environ.get(key) != value for key, value in ENV.items())):
        raise PermissionError("Exact recovery grant and numerical runtime required")
    output, service = Path(v["output_root"]), Path(v["service_dir"])
    current, private, prepared = bind(Path(v["original_private"]), output, service, commit)
    if current != unsigned(p) or private != unsigned(v):
        raise PermissionError("The prepared recovery contract has changed")
    launch, claim = (read(service / name) for name in ("target_launch.json", "independent_launch_claim.json"))
    if ((launch["pid"], launch["supervisor_pid"]) != (os.getpid(), os.getppid())
            or launch["kind"] != KIND or launch["spec_sha256"] != claim["spec_sha256"]
            or launch["automatic_retry"] is not False or claim["automatic_retry"] is not False):
        raise PermissionError("A live one-shot recovery supervisor is required")
    volumes = {Path(name).anchor for scope in prepared["roles"].values() for name in scope["files"]}
    if not volumes or any(not Path(volume).is_dir() for volume in volumes):
        raise RuntimeError("A frozen source volume is unavailable")
    admission = verify_admission(p["scientific_choices"]["control_reuse"])
    state = CoverageE5Resume(
        parent=v["stopped_task"], decision_id=approval["decision_id"], data_identity=p["data"],
        checkpoint_sha256=CHECKPOINT_SHA, parent_pins=p["parent_pins"],
        parent_code_commit=p["scientific_choices"]["recovery"]["parent_execution_commit"],
    )
    baseline = read(ROOT / BASELINE)
    output.mkdir(exist_ok=False)
    try:
        write(output / "authorization_binding.json", dict(
            approval=approval, code_commit=commit, controller_pid=os.getpid(), admission=admission))
        result = run_task(
            ROOT, p, v, approval, prepared, commit, "B7", 2029, started=started,
            pair_reference=Path(v["control"]), static_name="B7_static_source.sqlite",
            quantile_profile=COVERAGE_ARM.profile, schedule_profile=COSINE9, recovery=state,
            final_dev_observer_factory=lambda pack, ids: Tail20Observer(pack, ids, baseline, report_point_rank=True),
        )
        caps = p["budget"]
        expected = dict(optimizer_updates=caps["effective_updates"], segment_updates=caps["total_updates"],
                        replay=caps["replay_allowance"], cumulative_attempts=caps["cumulative_updates"],
                        total_logical_source_bytes=caps["total_source_bytes"],
                        total_logical_source_files=caps["total_source_files"], code_commit=commit,
                        schedule=schedule_identity(), status="COMPLETE_TRAIN_AND_DEV_EVALUATION")
        if any(result.get(key) != value for key, value in expected.items()):
            raise RuntimeError("Recovered A20 endpoint or source totals differ")
        folder = output / "B7_s2029"
        gate = read(folder / "B7_tail20_gate_09.json")
        point = point_completion(folder, gate, p, arm=COVERAGE_ARM, inherited=state)
        write(output / "completion.json", dict(
            **expected, **point, source_bytes=caps["total_source_bytes"], source_files=caps["total_source_files"],
            execution_code_commit=commit, proposal_sha256=p["proposal_sha256"], gate=gate, automatic_retry=False,
            checkpoint_sha256=result["checkpoint"]["checkpoint_sha256"], inherited_epochs=state.inherited_epochs,
        ))
    except BaseException as error:
        write(output / "failure.json", dict(status="STOP_NO_AUTOMATIC_RETRY",
                                           error_type=type(error).__name__, details=str(error)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    prep, launch = sub.add_parser("prepare"), sub.add_parser("execute")
    for command in (prep, launch):
        command.add_argument("--proposal", type=Path, required=True)
        command.add_argument("--private-preparation", type=Path, required=True)
    for arg in ("original-private", "output-root", "service-dir"):
        prep.add_argument("--" + arg, type=Path, required=True)
    launch.add_argument("--researcher-approval", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        original = args.original_private.resolve()
        local = original.parent.parent
        paths = (args.proposal, args.private_preparation, args.output_root, args.service_dir)
        if local.name != ".local" or any(not path.resolve().is_relative_to(local)
                                        or path.resolve().is_relative_to(original.parent) for path in paths):
            raise PermissionError("Use a fresh recovery namespace in .local")
        if args.proposal.exists() or args.private_preparation.exists():
            raise FileExistsError("Use fresh proposal and binding paths")
        p, v = prepare(original, args.output_root.resolve(), args.service_dir.resolve(), clean_commit())
        write(args.proposal, p)
        write(args.private_preparation, v)
        return
    if not args.researcher_approval.is_file():
        raise PermissionError("Separate exact researcher approval is required")
    execute(read(args.proposal), read(args.private_preparation), read(args.researcher_approval), clean_commit())


if __name__ == "__main__":
    main()
