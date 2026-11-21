"""Approval-bound, single-pass REAL/COSINE9 Development readout."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tools.research_readiness import start_paired_point_evaluation as shared


TASK = "REAL_COSINE9"
SCOPE = "REAL_COSINE9_FULL_DEV_READOUT_V1"
BUDGET = dict(
    payload_archive_reference_bytes=26_747_379_582, payload_open_instances=7_953,
    payload_cap_bytes=28_000_000_000, payload_open_cap=8100,
    metadata_cap_bytes=250_000_000, metadata_open_cap=160,
    total_source_cap_bytes=28_250_000_000, maximum_seconds=7200,
    output_storage_cap_bytes=2 * 1024**3, minimum_free_bytes=8 * 1024**3,
    minimum_host_available_bytes=8 * 1024**3, minimum_gpu_free_mib=5120,
    forward_batches=121, checkpoint_hashes=1, checkpoint_loads=1,
    optimizer_updates=0, retries=0, replay=0,
)
CHECKPOINT = "1c9b5f8c595935674f6952da6b239a50e26ca4eb4d90a217ab5593866d5b319e"
READOUT_IDENTITY = dict(
    population_ids_sha256="916302412bf024942aadeefe969d12c74452481ef24dedc30b1262b24609cf76",
    partition_sha256="01b95f12d26a3f6f4ff05620414cdae66c5cec23bd2808b0af2de40e4615291c",
    supervision_mask_sha256="70368bec3149e998922d565dab83347ba33f465df481a03ac3f90b85f1286d4b",
    n_rain=407820, n_strong=717,
)
DATA_SCOPE = dict(year=2024, role="Development", scenes=963, n_valid=3303090, n_rain=407820)
DATA_MANIFEST = "6bd5a8102929f3c3432753a4d6fb33e7e3ea69482c88abf13eabd729e26981de"
LAUNCH_KIND = "BOUNDED_CONDITIONAL_INTENSITY_READOUT"


def validate_grant(proposal, private, approval):
    if (proposal.get("authorization_scope") != SCOPE or proposal.get("tasks") != [TASK]
            or proposal.get("budget") != BUDGET or proposal.get("final_2025_access") is not False
            or proposal.get("readout_identity") != READOUT_IDENTITY
            or proposal.get("data_scope") != DATA_SCOPE
            or proposal["data_identity"].get("population_sha256") != shared.POPULATION_SHA256
            or proposal["data_identity"]["candidate_manifest_sha256"]["Development"] != DATA_MANIFEST):
        raise PermissionError("Expected the one frozen 2024 Development readout scope")
    models = proposal.get("models", [])
    if len(models) != 1 or any(models[0].get(k) != v for k, v in dict(
            task=TASK, model="B7", seed=2029, endpoint="FIXED_EPOCH_9_LAST",
            checkpoint_bytes=53_906_821, checkpoint_sha256=CHECKPOINT,
            dynamic_control="REAL_PHYSICAL_DOTE").items()):
        raise PermissionError("Expected exactly the REAL/COSINE9 fixed E9 checkpoint")
    proposal_sha = proposal.get("proposal_sha256")
    if shared.digest({k: v for k, v in proposal.items() if k != "proposal_sha256"}) != proposal_sha:
        raise PermissionError("Readout proposal hash changed")
    if (private.get("proposal_sha256") != proposal_sha
            or shared.digest({k: v for k, v in private.items() if k != "proposal_sha256"})
            != proposal.get("private_preparation_sha256")):
        raise PermissionError("Private readout binding changed")
    expected = dict(approved_by_researcher=True, authorization_scope=SCOPE,
                    proposal_sha256=proposal_sha, code_commit=proposal["execution_code_commit"],
                    tasks=[TASK], budget=BUDGET, output_root=private["output_root"])
    if (any(approval.get(k) != v for k, v in expected.items())
            or not str(approval.get("decision_id", "")).strip()
            or not str(approval.get("researcher_instruction", "")).strip()):
        raise PermissionError("This exact B readout requires separate researcher approval")
    output = Path(private["output_root"]).resolve()
    for name in ("metadata_files", "scientific_files"):
        if any(Path(p).resolve().is_relative_to(output) for p in private[name]):
            raise PermissionError("Readout output overlaps an input")
    if output.exists():
        raise PermissionError("Readout output namespace has already been consumed")


def load_grant(proposal, private, approval):
    return shared.bootstrap(proposal, private, approval, validate=validate_grant)


def execute(proposal_path, private_path, approval_path):
    deadline = shared.Deadline(BUDGET["maximum_seconds"])
    p, v, _, bootstrap, initial = load_grant(proposal_path, private_path, approval_path)
    if Path(sys.executable).resolve() != Path(v["runtime_python"]).resolve():
        raise PermissionError("Use the bound native Python runtime")
    shared.require_host()
    output = Path(v["output_root"])
    guard = shared.ReadGuard(
        v, task=TASK, metadata_cap=BUDGET["metadata_cap_bytes"],
        metadata_opens=BUDGET["metadata_open_cap"], check=deadline.remaining,
        output_roots=(output,), bootstrap=bootstrap, initial_bytes=initial, initial_opens=3,
    )
    # The exclusive output claim also consumes the attempt if a gate later fails.
    output.mkdir(exist_ok=False)
    guard.install()
    try:
        shared.validate_bound_inputs(p, v, worker=True, tasks=(TASK,), limits=BUDGET)
        shared.resources(output, limits=BUDGET)
        guard.block_subprocess = True
        check = shared.OutputLimit(output, BUDGET["output_storage_cap_bytes"], deadline,
                                   extra_roots=(v["service_dir"],))
        from tools.research_readiness.conditional_intensity_readout import DevelopmentReadout
        from tools.research_readiness.paired_point_worker import run_task

        def factory(_pack, ids, reference):
            for name in ("population_ids_sha256", "partition_sha256"):
                if reference[name] != READOUT_IDENTITY[name]:
                    raise ValueError(f"Frozen Development report has a different {name}")
            return DevelopmentReadout(output / "arrays", ids, dict(
                **READOUT_IDENTITY, checkpoint_sha256=CHECKPOINT, proposal_sha256=p["proposal_sha256"],
                code_commit=p["execution_code_commit"], population_sha256=p["data_identity"]["population_sha256"],
            ), check)

        result = run_task(ROOT, p, v, TASK, output, check, include_joint=False, readout_factory=factory)
        if result["forward_calls"] != BUDGET["forward_batches"]:
            raise RuntimeError("Unexpected number of forward batches")
        accounting = guard.close()
        if (accounting["payload_archive_reserved_bytes"], accounting["payload_open_instances"]) != (
                BUDGET["payload_archive_reference_bytes"], BUDGET["payload_open_instances"]):
            raise RuntimeError("Readout payload reservations differ from the approved pass")
        check()
        shared.write(output / "completion.json", dict(
            status="COMPLETE_SINGLE_ARM_READOUT", proposal_sha256=p["proposal_sha256"],
            accounting={k: value for k, value in accounting.items() if k != "reservations"},
            result=result, optimizer_updates=0, automatic_retry=False, finished=shared.now()))
    except BaseException as error:
        accounting = guard.close()
        shared.write(output / "failure.json", dict(
            status="STOP_NO_RETRY", error_type=type(error).__name__, details=str(error),
            accounting={k: value for k, value in accounting.items() if k != "reservations"},
            finished=shared.now()))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["execute"])
    for flag in ("proposal", "private-preparation", "researcher-approval"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    execute(args.proposal, args.private_preparation, args.researcher_approval)
