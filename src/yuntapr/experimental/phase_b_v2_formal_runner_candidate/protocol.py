"""Fixed B9/S0/V0 contract, identities, metadata arithmetic and public pins."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, get_config, proposed_runs, workload
from yuntapr.experimental.phase_b_v2_integration.controls import candidate_plan, audit_plan, endpoint_boundary
from yuntapr.experimental.phase_b_v2_integration import initialization
from . import SCOPE

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs/phase_b_v2_formal_runner_candidate/v1"
SOURCE_SHA = "d3daf9803a766648afe1cbdfc7c4add72018afeb1e921967e4a77bdf9cad6927"
BASELINE = "435f303a1bdebb30a687f8e02dd8576d0d28cb55"
PROTOCOL_SHA = "66cddf4483ecd18208b5913c7a231e92eecce7a05a320cf76d5ee04db6859c17"
FLAGS = {"V2_PHASE_B_AUTHORIZED": False, "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED": False,
         "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED": True, "HISTORICAL_RECOVERY_RATIFICATION": "NOT_GRANTED",
         "2025_RAW_ACCESS": 0, "2025_PIXELS_READ": 0}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def public_inventory() -> dict:
    path = OUT / "source_identity.json"
    if sha(path) != SOURCE_SHA:
        raise ValueError("Source inventory altered")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_public_sources() -> int:
    items = public_inventory()["checked_public_files"]
    for item in items:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != item["sha256"]:
            raise ValueError("Public source SHA mismatch: " + item["path"])
    return len(items)


def code_sha() -> str:
    digest = hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(p.name.encode()); digest.update(p.read_bytes())
    return digest.hexdigest()


def run_identity(spec: RunSpec, registry_sha: str) -> dict:
    if type(spec) is not RunSpec or type(registry_sha) is not str or len(registry_sha) != 64:
        raise ValueError("Closed RunSpec and synthetic registry SHA required")
    spec.__post_init__()
    audit_plan(candidate_plan(spec))
    return {"scope": SCOPE, "run": asdict(spec), "arm_parameters": asdict(get_config(spec.experiment_id)),
            "namespace": "SYNTHETIC_EPOCH_ENGINE_v1__" + spec.run_id, "source_commit": BASELINE,
            "source_sha": SOURCE_SHA, "code_sha": code_sha(), "protocol_sha": PROTOCOL_SHA,
            "synthetic_registry_sha": registry_sha, "synthetic_data_years": [],
            "synthetic_terminal_epoch": 2, "formal_epochs": 9, "formal_endpoint": "V0_EPOCH9",
            "formal_train_year": 2023, "formal_report_role": "2024_DEVELOPMENT_NOT_INDEPENDENT_TEST",
            "train_batch": 2, "validation_batch": 8, "accumulation": 1, "drop_last": False,
            "warm_start": False, "flags": dict(FLAGS)}


def _initialization_public_pins() -> int:
    # Only replace the I/O verifier dependency, NEVER the fresh initialization
    # algorithm. The older verifier reads a real scaler; this turn forbids that.
    record = public_inventory()
    allowed = {e["path"]: e for e in record["checked_public_files"]}
    from yuntapr.experimental.phase_b_v2_integration import pins
    if sha(ROOT / pins.REFERENCE) != pins.REFERENCE_SHA:
        raise ValueError("Original fresh source reference identity mismatch")
    old = json.loads((ROOT / pins.REFERENCE).read_text(encoding="utf-8"))
    count = 0
    deferred = {e["path"] for e in record["deferred_observational_artifacts"]}
    for item in old["repository_files"]:
        if item["path"] in deferred:
            continue  # identity already carried by published inventory; no bytes
        if item["path"] not in allowed or sha(ROOT / item["path"]) != item["sha256"]:
            raise ValueError("Fresh initialization source identity mismatch")
        count += 1
    return count


def fresh_models_without_observational_artifacts(seed: int):
    """Serial scoped verifier injection; original fresh algorithm unchanged."""
    with patch.object(initialization, "verify_frozen_sources", _initialization_public_pins):
        models, proof = initialization.fresh_paired_models(seed)
    proof["real_scaler_and_mask_bytes_accessed"] = False
    proof["scaler_byte_verification_deferred_to_authorized_preflight"] = True
    return models, proof


def fixed_endpoint(completed_epoch: int, *, best_epoch: object = None) -> dict:
    result = endpoint_boundary(completed_epoch)
    result.update(selection="V0_FIXED_EPOCH9", selected_epoch=9 if completed_epoch == 9 else None,
                  best_epoch_ignored=True)
    return result


def plans() -> dict:
    return {"status": "PROPOSED_FOR_RESEARCHER_APPROVAL", "plans": [
        {k: asdict(v) if type(v) is RunSpec else v for k, v in candidate_plan(r).items()} for r in proposed_runs()],
        "budget_not_executed": workload(), "formal_runs_executed": 0, **FLAGS}
