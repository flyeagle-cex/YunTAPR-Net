"""Run one approved A20 Development readout paired to sealed COSINE9 scores."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tools.research_readiness import start_conditional_intensity_readout as baseline
from tools.research_readiness import start_paired_point_evaluation as shared


ENTRY = "tools/research_readiness/start_a20_point_rank.py"
TASK = "A20_BISIDE_FIXED_E9"
SCOPE = "A20_E9_POINT_RANK_MATCHED_SAVED_COSINE9_V1"
LAUNCH_KIND = "BOUNDED_A20_POINT_RANK"
A20_SHA = "3a081d737779bc861cede8d5109529ae7eaee05081a828cf74d1f5da3524e361"
A20_BYTES = 53_905_413
B_BYTES = 881_894_762
B_SHARDS = 121
DATA_SCOPE = baseline.DATA_SCOPE
CONTRACT = dict(
    scenes=963, n_valid=3303090, n_strong=717, high_n_strong=178,
    saved_control_bytes=B_BYTES, supervision_mask_sha256=baseline.READOUT_IDENTITY["supervision_mask_sha256"],
    fixed_a_counts={"COSINE9": {"tp": 0, "fp": 0}, "A20": {"tp": 627, "fp": 177098}},
    score="FP32_P_TIMES_FP64_MEAN32_EXPM1", primary="AP20",
)
BUDGET = dict(
    **(baseline.BUDGET | dict(payload_archive_reference_bytes=27_629_271_528, payload_open_instances=8074,
                              payload_cap_bytes=27_629_271_528, payload_open_cap=8074,
                              metadata_cap_bytes=300_000_000, metadata_open_cap=200,
                              total_source_cap_bytes=27_929_271_528, output_storage_cap_bytes=1024**3)),
    saved_control_files=B_SHARDS, saved_control_bytes=B_BYTES,
)


def validate_grant(proposal, private, approval):
    if (proposal.get("authorization_scope") != SCOPE or proposal.get("tasks") != [TASK]
            or proposal.get("budget") != BUDGET or proposal.get("ranking_contract") != CONTRACT
            or proposal.get("data_scope") != DATA_SCOPE or proposal.get("final_2025_access") is not False
            or proposal["data_identity"].get("population_sha256") != shared.POPULATION_SHA256
            or proposal["data_identity"]["candidate_manifest_sha256"]["Development"] != baseline.DATA_MANIFEST):
        raise PermissionError("Expected one exact 2024 A20 Dev rank readout")
    models = proposal.get("models", [])
    if len(models) != 1 or any(models[0].get(key) != value for key, value in dict(
            task=TASK, model="B7", seed=2029, endpoint="FIXED_EPOCH_9_LAST", checkpoint_bytes=A20_BYTES,
            checkpoint_sha256=A20_SHA, dynamic_control="REAL_PHYSICAL_DOTE").items()):
        raise PermissionError("Only the fixed A20 LAST E9 checkpoint is admitted")
    identity = proposal["proposal_sha256"]
    if (shared.digest({k: v for k, v in proposal.items() if k != "proposal_sha256"}) != identity
            or private.get("proposal_sha256") != identity
            or shared.digest({k: v for k, v in private.items() if k != "proposal_sha256"})
            != proposal["private_preparation_sha256"]):
        raise PermissionError("Proposal or private binding changed")
    expected = dict(approved_by_researcher=True, authorization_scope=SCOPE, proposal_sha256=identity,
                    code_commit=proposal["execution_code_commit"], tasks=[TASK], budget=BUDGET,
                    output_root=private["output_root"])
    if (any(approval.get(k) != v for k, v in expected.items())
            or not str(approval.get("decision_id", "")).strip()
            or not str(approval.get("researcher_instruction", "")).strip()):
        raise PermissionError("A separate exact researcher grant is required for A20 ranking")
    output = Path(private["output_root"]).resolve()
    if output.exists() or any(Path(path).resolve().is_relative_to(output)
                              for group in ("metadata_files", "scientific_files") for path in private[group]):
        raise PermissionError("Use a fresh output namespace separate from all sources")


def control_shards(completion, expected_proposal, expected_control_checkpoint):
    if (completion["status"] != "COMPLETE_SINGLE_ARM_READOUT"
            or completion["proposal_sha256"] != expected_proposal
            or completion["result"]["checkpoint_sha256"] != expected_control_checkpoint):
        raise PermissionError("Only the completed fixed COSINE9 readout is admitted")
    saved = completion["result"]["full_dev_readout"]
    files = saved["storage"]["files"]
    if len(files) != B_SHARDS or sum(x["bytes"] for x in files) != B_BYTES:
        raise ValueError("Frozen COSINE9 archive count or byte total differs")
    position = 0
    for i, item in enumerate(files):
        if (item["file"] != f"batch_{i:03d}.npz" or item["scene_start"] != position
                or item["scenes"] != min(8, 963 - position) or item["n_valid"] != 3430 * item["scenes"]
                or not 0 < item["bytes"] <= 16 * 1024**2 or len(item["sha256"]) != 64):
            raise ValueError("Frozen COSINE9 shard identity differs")
        position += item["scenes"]
    if position != 963:
        raise ValueError("Incomplete COSINE9 readout")
    return files


def execute(proposal_file, private_file, approval_file):
    deadline = shared.Deadline(BUDGET["maximum_seconds"])
    p, v, _, bootstrap, length = shared.bootstrap(proposal_file, private_file, approval_file, validate=validate_grant)
    if Path(sys.executable).resolve() != Path(v["runtime_python"]).resolve():
        raise PermissionError("The native PyTorch runtime is required")
    shared.require_host()
    output = Path(v["output_root"])
    guard = shared.ReadGuard(
        v, task=TASK, metadata_cap=BUDGET["metadata_cap_bytes"], metadata_opens=BUDGET["metadata_open_cap"],
        check=deadline.remaining, output_roots=(output,), bootstrap=bootstrap, initial_bytes=length, initial_opens=3,
    )
    Path(v["output_root"]).mkdir(exist_ok=False)
    guard.install()
    try:
        shared.validate_bound_inputs(p, v, worker=True, tasks=(TASK,), limits=BUDGET)
        shared.resources(output, limits=BUDGET)
        guard.block_subprocess = True
        check = shared.OutputLimit(output, BUDGET["output_storage_cap_bytes"], deadline,
                                   extra_roots=(v["service_dir"],))
        from tools.research_readiness.paired_point_worker import run_task
        from tools.research_readiness.point_rank_readout import PairedPointRankReadout

        control_receipt = Path(v["control_completion"])
        files = control_shards(shared.read(control_receipt), p["control_reference"]["proposal_sha256"],
                               p["control_reference"]["checkpoint_sha256"])

        def readout(pack, ids, reference):
            for name in ("population_ids_sha256", "partition_sha256"):
                if reference[name] != baseline.READOUT_IDENTITY[name]:
                    raise ValueError(f"Frozen A20 Development report has a different {name}")
            return PairedPointRankReadout(output / "a20_scores", control_receipt.parent / "arrays",
                                          files, pack, ids, CONTRACT, check)

        run = run_task(ROOT, p, v, TASK, output, check, include_joint=False, readout_factory=readout)
        if run["forward_calls"] != BUDGET["forward_batches"] or run["optimizer_updates"] != 0:
            raise RuntimeError("Single A20 pass boundaries differ")
        accounting = guard.close()
        if (accounting["payload_archive_reserved_bytes"], accounting["payload_open_instances"]) != (
                BUDGET["payload_archive_reference_bytes"], BUDGET["payload_open_instances"]):
            raise RuntimeError("Actual read reservations differ from the approved A20 pack")
        check()
        shared.write(output / "completion.json", dict(
            status="COMPLETE_MATCHED_POINT_A_RANKING", proposal_sha256=p["proposal_sha256"],
            execution_code_commit=p["execution_code_commit"], checkpoint_sha256=A20_SHA,
            accounting={k: value for k, value in accounting.items() if k != "reservations"},
            result=run, optimizer_updates=0, automatic_retry=False, final_2025_access=False, finished=shared.now()))
    except BaseException as error:
        accounting = guard.close()
        shared.write(output / "failure.json", dict(
            status="STOP_NO_RETRY", error_type=type(error).__name__, details=str(error),
            accounting={k: value for k, value in accounting.items() if k != "reservations"}, finished=shared.now()))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["execute"])
    for flag in ("proposal", "private-preparation", "researcher-approval"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    execute(args.proposal, args.private_preparation, args.researcher_approval)
