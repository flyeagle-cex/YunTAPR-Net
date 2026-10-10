"""Closed run identities and immutable public-source provenance."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, get_config, proposed_runs, workload
from . import SCOPE

REPO = Path(__file__).resolve().parents[4]
DELIVERY = REPO / "docs/phase_b_v2_runner_engineering/v1"
SOURCE_SHA = "7f0ab0238e74559afa5e17411684fbb5c54d89aedbc081f6da05544cd5470c52"
PROTOCOL_SHA = "66cddf4483ecd18208b5913c7a231e92eecce7a05a320cf76d5ee04db6859c17"
BASELINE = "8958745558ee0a1a2928454ccf894287d8cbfbe9"
FLAGS = {"V2_PHASE_B_AUTHORIZED": False, "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED": False,
         "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED": True,
         "HISTORICAL_RECOVERY_RATIFICATION": "NOT_GRANTED", "2025_RAW_ACCESS": 0, "2025_PIXELS_READ": 0}


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sources() -> int:
    path = DELIVERY / "source_identity.json"
    if file_sha(path) != SOURCE_SHA:
        raise ValueError("Runner source inventory identity mismatch")
    inventory = json.loads(path.read_text(encoding="utf-8"))
    for entry in inventory["inherited_files"]:
        candidate = (REPO / entry["path"]).resolve()
        if not candidate.is_relative_to(REPO) or file_sha(candidate) != entry["sha256"]:
            raise ValueError("Protected source identity mismatch: " + entry["path"])
    protocol = REPO / "docs/phase_b_v2_ablation_preregistration/v1/protocol_proposed.json"
    if file_sha(protocol) != PROTOCOL_SHA:
        raise ValueError("Proposed protocol identity mismatch")
    return len(inventory["inherited_files"])


def identity(spec: RunSpec) -> dict:
    if type(spec) is not RunSpec:
        raise ValueError("Exact closed RunSpec required")
    RunSpec(spec.experiment_id, spec.model, spec.seed)
    code_sha = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        code_sha.update(path.name.encode("ascii"))
        code_sha.update(path.read_bytes())
    return {"scope": SCOPE, "synthetic_run_id": "SYNTHETIC__" + spec.run_id,
            "model": spec.model, "arm": spec.experiment_id, "seed": spec.seed,
            "parameters": asdict(get_config(spec.experiment_id)), "source_commit": BASELINE,
            "source_sha": SOURCE_SHA, "candidate_code_sha": code_sha.hexdigest(), "protocol_sha": PROTOCOL_SHA,
            "data_role": "ARTIFICIAL_ONLY_NO_OBSERVATIONAL_YEARS", "data_years": [],
            "proposed_epochs": 9, "proposed_endpoint": 9, "warm_start": False,
            "flags": dict(FLAGS)}


def candidate_plan() -> dict:
    return {"status": "PROPOSED_FOR_RESEARCHER_APPROVAL", "scope": SCOPE,
            "runs": [identity(s) for s in proposed_runs()], "formal_budget_not_executed": workload(),
            "synthetic_steps_per_model_arm_max": 2, "synthetic_steps_task_max": 12, **FLAGS}


def reject_formal_execution(*args, **kwargs) -> None:
    raise PermissionError("No formal runner or data connector exists; synthetic results cannot grant authorization")
