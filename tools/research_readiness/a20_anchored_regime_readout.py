"""Prepare one bounded overlap readout of the already-saved COSINE9 Development arrays."""

import argparse
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
READINESS = ROOT / "docs/research_readiness"
LOCAL = READINESS / ".local"
SOURCE = LOCAL / "b_readout_prepare_20261120_v2/readout"
RUN = LOCAL / "a20_anchored_regime_readout_20261122_v1"
PROPOSAL = READINESS / "20261121_a20_negative_coverage/A20_ANCHORED_REGIME_READOUT_PROPOSAL.json"
COMPLETION_SHA = "1a3396a7fd0d9564590967881d576060ffd7801c7f24b37102c68b7911b76614"
CHECKPOINT_SHA = "1c9b5f8c595935674f6952da6b239a50e26ca4eb4d90a217ab5593866d5b319e"
MASK_SHA = "70368bec3149e998922d565dab83347ba33f465df481a03ac3f90b85f1286d4b"
CAP = dict(saved_array_bytes=881894762, saved_array_opens=121, max_seconds=300,
           raw_source_opens=0, checkpoint_loads=0, inference_passes=0, optimizer_updates=0,
           additional_retries=0)
COHORTS = ("dry", "weak", "other_wet", "strong")
ROUTES = ("inactive", "active_low_p", "active_high_p")


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    raw = (SOURCE / "completion.json").read_bytes()
    if digest(raw) != COMPLETION_SHA:
        raise ValueError("Saved COSINE9 completion receipt changed")
    saved = json.loads(raw)["result"]
    readout = saved["full_dev_readout"]
    if (saved["status"] != "COMPLETE" or saved["checkpoint_sha256"] != CHECKPOINT_SHA
            or readout["identity"]["supervision_mask_sha256"] != MASK_SHA):
        raise ValueError("Wrong saved Development population or endpoint")
    files = readout["storage"]["files"]
    if readout["storage"]["folder"] != "arrays" or len(files) != CAP["saved_array_opens"]:
        raise ValueError("Unexpected archived shard namespace")
    if sum(item["bytes"] for item in files) != CAP["saved_array_bytes"]:
        raise ValueError("Unexpected archived payload size")
    return files


def proposal(files):
    return dict(
        status="READY_WAITING_EXACT_READOUT_APPROVAL", authorization_scope="COSINE9_SAVED_DEV_ROUTE_OVERLAP",
        script_sha256=digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        input_completion_sha256=COMPLETION_SHA, input_checkpoint_identity=CHECKPOINT_SHA,
        supervision_mask_sha256=MASK_SHA, saved_shards=len(files), budget=CAP,
        definition=dict(weak_truth="0.1 < FP32 R <= 1", strong_truth="FP32 R > 20",
                        active="mean(expm1(qlog_16), expm1(qlog_17)) > 1",
                        low_p="p < 0.5", q32_risk="qlog_32 > log1p(20)",
                        aggregate_only=True, final_2025_access=False),
        purpose="Quantify overlap of the fixed synthetic routing rule with weak and strong real labels.",
    )


def tally(truth, p, qlog):
    n = len(truth)
    if (truth.shape != (n,) or p.shape != (n,) or qlog.shape != (n, 32)
            or truth.dtype != np.float32 or p.dtype != np.float32 or qlog.dtype != np.float64
            or not all(np.isfinite(array).all() for array in (truth, p, qlog))
            or (truth < 0).any() or ((p < 0) | (p > 1)).any()
            or (qlog[:, 1:] <= qlog[:, :-1]).any()):
        raise ValueError("Malformed saved array")
    with np.errstate(over="raise", invalid="raise"):
        median = np.expm1(qlog[:, 15:17]).mean(axis=1)
    cohort = (truth > np.float32(.1)).astype(np.int64)
    cohort += truth > np.float32(1.)
    cohort += truth > np.float32(20.)
    route = np.where(median > 1., np.where(p < np.float32(.5), 1, 2), 0)
    group = cohort * len(ROUTES) + route
    supported = qlog[:, -1] > math.log1p(20.)
    return np.bincount(group, minlength=12).reshape(4, 3), np.bincount(
        group[supported], minlength=12).reshape(4, 3)


def execute(plan, files):
    published = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    if plan != published:
        raise ValueError("Prepared proposal or script changed")
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    approval = json.loads((RUN / "RESEARCHER_APPROVAL.json").read_text(encoding="utf-8"))
    if (approval.get("approved_by_researcher") is not True
            or not approval.get("decision_id") or approval.get("proposal_sha256") != digest(canonical)
            or approval.get("budget") != CAP):
        raise PermissionError("Exact new archived-array scope approval required")
    write(RUN / "attempt.json", dict(proposal_sha256=digest(canonical), automatic_retry=False))
    started = time.monotonic()
    totals, q32s = (np.zeros((4, 3), dtype=np.int64) for _ in range(2))
    bytes_read = scenes = 0
    mask_hasher = hashlib.sha256()
    for i, item in enumerate(files):
        name = f"batch_{i:03}.npz"
        path = SOURCE / "arrays" / name
        size = item["bytes"]
        if (time.monotonic() - started > CAP["max_seconds"] or item["file"] != name
                or item["scene_start"] != scenes or bytes_read + size > CAP["saved_array_bytes"]
                or path.resolve().parent != SOURCE.resolve() / "arrays" or path.stat().st_size != size):
            raise RuntimeError("Saved shard identity or readout budget changed")
        with path.open("rb") as stream:
            blob = stream.read(size)
        if len(blob) != size or digest(blob) != item["sha256"]:
            raise ValueError("Saved shard digest differs")
        bytes_read += size
        with np.load(BytesIO(blob), allow_pickle=False) as arrays:
            ids, mask = arrays["scene_ids"], arrays["supervision_mask"]
            if (len(ids) != item["scenes"] or mask.shape != (len(ids), 100, 100)
                    or mask.dtype != np.bool_ or not np.all(mask.sum(axis=(1, 2)) == 3430)):
                raise ValueError("Saved supervision mask differs")
            for scene_id, valid in zip(ids, mask):
                value = str(scene_id).encode()
                mask_hasher.update(len(value).to_bytes(4, "big"))
                mask_hasher.update(value)
                mask_hasher.update(np.asarray(valid.shape, dtype="<i8").tobytes())
                mask_hasher.update(valid.tobytes(order="C"))
            counts, q32_counts = tally(arrays["truth_mm_h"], arrays["p"], arrays["qlog"])
            if int(counts.sum()) != item["n_valid"] or int(counts.sum()) != int(mask.sum()):
                raise ValueError("Prediction and label populations differ")
            totals += counts
            q32s += q32_counts
            scenes += len(ids)
    if (scenes != 963 or tuple(totals.sum(axis=1)) != (2895270, 246473, 160630, 717)
            or int(q32s[:3].sum()) != 5769 or int(q32s[3].sum()) != 160
            or mask_hasher.hexdigest() != MASK_SHA or bytes_read != CAP["saved_array_bytes"]
            or time.monotonic() - started > CAP["max_seconds"]):
        raise ValueError("Archived population or end-to-end cap differs")
    write(RUN / "result.json", dict(
        status="COMPLETE_DESCRIPTIVE_ROUTE_OVERLAP", projection="FROZEN_E0_RULE", scenes=scenes,
        proposal_sha256=digest(canonical), bytes_read=bytes_read, elapsed_seconds=time.monotonic() - started,
        rows={group: {route: {"n": int(totals[i, j]), "q32_over20": int(q32s[i, j])}
                      for j, route in enumerate(ROUTES)} for i, group in enumerate(COHORTS)},
        final_2025_access=False, scientific_status="NOT_VERIFIED",
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "execute"))
    args = parser.parse_args()
    files = manifest()
    plan = proposal(files)
    if args.mode == "prepare":
        if PROPOSAL.exists() or RUN.exists():
            raise FileExistsError("Use the fresh readout namespace")
        for i, item in enumerate(files):
            name = f"batch_{i:03}.npz"
            if item["file"] != name or (SOURCE / "arrays" / name).stat().st_size != item["bytes"]:
                raise ValueError("Saved shard name or length differs")
        RUN.mkdir()
        write(PROPOSAL, plan)
        print(digest(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()))
    else:
        execute(plan, files)


if __name__ == "__main__":
    main()
