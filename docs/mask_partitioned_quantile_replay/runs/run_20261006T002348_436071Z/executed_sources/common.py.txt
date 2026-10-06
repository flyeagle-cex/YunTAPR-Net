"""New diagnostic authority; inherited immutable historical identities."""
from pathlib import Path
import math
import os
import sys
from quantile_autopsy_v1.common import (
    ROOT, FAILED, SUCCESS, FAIL_BATCH, BOUNDARY, FORMAL_STEPS, CHECKPOINT_SHA,
    MODEL_SHA, ERROR, now, digest, read, write, progress, pin, verify, csv_rows,
    historical_updates, exact_reconcile,
)
from quantile_autopsy_v1 import common as previous

BASELINE = "ea50934d6da89e774feb864e997ea132232534f3"
SCOPE = "ENGINEERING_DIAGNOSTIC_REPLAY_ONLY"
PRIOR = ROOT / "docs/quantile_overflow_autopsy/runs/run_20261005T145434_644569Z"
RUN_ROOT = ROOT / "docs/mask_partitioned_quantile_replay/runs"
RATES = (10, 50, 100, 500, 1000)
FP64_BOUNDARY = math.log1p(sys.float_info.max)
REGIONS = ("YUNNAN_INSIDE", "YUNNAN_OUTSIDE")
CELLS = {"YUNNAN_INSIDE": 3430, "YUNNAN_OUTSIDE": 6570}


def checkpoint_byte_read_policy(path, mutate, pinned_paths):
    if mutate or Path(path).resolve() not in {Path(p).resolve() for p in pinned_paths}:
        raise PermissionError("Only pinned checkpoint byte verification is allowed")


def checkpoint_deserialization_policy(path, last):
    if not isinstance(path, (str, os.PathLike)) or Path(path).resolve() != Path(last).resolve():
        raise PermissionError("Only verified epoch-4 LAST may be deserialized")


def snapshot(run):
    # Prior failure/checkpoint hashes, including all four completed checkpoints.
    refs = previous.snapshot(run)
    known = {r["path"] for r in refs}
    publications = [PRIOR / "publication_manifest.json",
        ROOT / "docs/saved_quantile_extremes/runs/run_20261005T235831_960691Z/publication_manifest.json"]
    for pub in publications:
        if str(pub.resolve()) not in known:
            refs.append(pin(pub)); known.add(str(pub.resolve()))
        for ref in read(pub)["files"]:
            path = (ROOT / ref["relative_path"]).resolve()
            if path.stat().st_size != ref["bytes"] or digest(path) != ref["sha256"]:
                raise ValueError("Published historical evidence changed: " + str(path))
            if str(path) not in known:
                refs.append(pin(path)); known.add(str(path))
    # previous.snapshot created a temporary initial inventory; this new run's
    # authoritative expanded inventory is separate and never alters old runs.
    write(run / "historical_immutability_before.json", {"utc": now(), "files": refs})
    return refs


def verify_snapshot(run):
    refs = read(run / "historical_immutability_before.json")["files"]
    for ref in refs:
        verify(ref)
    manifest = read(FAILED / "run_manifest.json")
    if read(FAILED / "execution_counters.json")["FORMAL_OPTIMIZER_STEPS"] != FORMAL_STEPS:
        raise ValueError("Formal update counter changed")
    return {"all_byte_identical": True, "file_count": len(refs),
            "protocol_sha256": manifest["protocol"]["sha256"],
            "normalization_sha256": manifest["normalization"]["sha256"],
            "formal_optimizer_steps": FORMAL_STEPS}


def check_partition_union(prior, actual):
    if prior["sample_ids"] != actual["sample_ids"] or prior["update"] != actual["update"]:
        raise ValueError("REPRODUCTION_FAILURE: prior autopsy identity")
    parts = actual["mask_partitioned"]
    maxima = [max(parts[r]["per_tau_qlog_max"][t] for r in REGIONS) for t in range(32)]
    if (maxima != prior["qlog_per_tau_max"]
            or min(parts[r]["global_qlog_min"] for r in REGIONS) != prior["qlog"]["min"]
            or max(parts[r]["global_qlog_max"] for r in REGIONS) != prior["qlog"]["max"]):
        raise ValueError("REPRODUCTION_FAILURE: partition union vs prior whole-grid qlog")


def preflight_matches_prior(gate):
    prior = read(PRIOR / "replay_identity_preflight.json")
    for key in ("checkpoint_identity", "state_hashes", "scheduler", "epoch_5_permutation_sha256",
                "environment", "source_preflight"):
        if gate[key] != prior[key]:
            raise ValueError("Preflight differs from completed autopsy: " + key)
    return {"all_exact": True, "prior_identity_preflight": pin(PRIOR / "replay_identity_preflight.json"),
            "fields": ["checkpoint_identity", "model", "optimizer", "RNG", "scheduler", "permutation", "environment", "sources"]}
