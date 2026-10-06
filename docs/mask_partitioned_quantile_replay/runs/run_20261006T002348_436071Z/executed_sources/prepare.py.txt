"""Prepare a fresh authority and immutable history inventory, without raw reads."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from mask_partitioned_replay_v1 import common as c
from datetime import datetime, timezone
import json
import subprocess


def main():
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != c.BASELINE:
        raise ValueError("Current diagnostic baseline changed")
    if subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ROOT).returncode:
        raise ValueError("Tracked historical/code changes require investigation")
    run = c.RUN_ROOT / ("run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
    run.mkdir(parents=True, exist_ok=False)
    auth = run / "researcher_mask_partitioned_replay_authorization.txt"
    auth.write_bytes(Path(__file__).with_name("researcher_authorization.txt").read_bytes())
    identity = c.read(c.FAILED / "last_checkpoint_identity.json")
    prior = c.read(c.PRIOR / "replay_identity_preflight.json")
    if identity != prior["checkpoint_identity"] or identity["sha256"] != c.CHECKPOINT_SHA:
        raise ValueError("Epoch-4 checkpoint identity differs from completed autopsy")
    if identity["epoch"] != 4 or identity["global_update"] != c.BOUNDARY:
        raise ValueError("Checkpoint boundary changed")
    c.verify({"path": identity["absolute_local_path"], "bytes": identity["bytes"], "sha256": identity["sha256"]})
    c.write(run / "execution_scope.json", {"utc": c.now(), "operation": c.SCOPE, "model": "B0_MATCHED",
        "AUTHORIZED": True, "baseline": head, "researcher_authorization": c.pin(auth),
        "authorization_source": "Current researcher chat task, transcribed into immutable UTF-8 evidence",
        "2025_raw_access": False, "formal_resume_authorized": False, "B1_authorized": False,
        "production_changes_allowed": False, "checkpoint_writes_allowed": False,
        "exact_successful_updates": c.SUCCESS, "exact_failure_batch": c.FAIL_BATCH,
        "checkpoint_identity": identity, "formal_optimizer_steps_immutable": c.FORMAL_STEPS,
        "frozen_rates_are_descriptive_only": list(c.RATES), "FP64_PHYSICAL_BOUNDARY": c.FP64_BOUNDARY,
        "full_tensor_persistence_allowed": False, "automatic_retry_allowed": False,
        "stop_after_audit_and_GitHub_main_publication": True})
    refs = c.snapshot(run)
    c.progress(run, {"status": "PREPARED_AWAITING_FIXTURE_GATE", "run": str(run), "engineering_updates": 0,
        "expected_successful_updates": c.SUCCESS, "failure_batch": c.FAIL_BATCH,
        "formal_optimizer_steps": c.FORMAL_STEPS, "2025_raw_access": 0, "B1_phase_b_started": False})
    print(json.dumps({"run": str(run), "immutable_files": len(refs), "checkpoint_sha_verified": True}))


if __name__ == "__main__":
    main()
