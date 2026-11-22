"""Bind a single saved-array pass testing a common, weak-loss-preserving redistribution."""

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import time

import numpy as np

from a20_anchored_regime_readout import (
    CAP, CHECKPOINT_SHA, COMPLETION_SHA, LOCAL, MASK_SHA, PROPOSAL as ROUTE_PROPOSAL, SOURCE,
    digest, manifest, tally, write,
)
from a20_fixed_endpoint_bounds import point, weak_preserving_vertex


PROPOSAL = ROUTE_PROPOSAL.with_name("A20_FIXED_ENDPOINT_SCALAR_PROPOSAL.json")
RUN = LOCAL / "a20_fixed_endpoint_scalar_20261122_v1"
COPIED_SOURCES = (Path(__file__), Path(__file__).with_name("a20_fixed_endpoint_bounds.py"),
                  Path(__file__).with_name("a20_anchored_regime_readout.py"))


def canonical(plan):
    return json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def proposal():
    return dict(
        status="READY_WAITING_EXACT_READOUT_APPROVAL", scope="SAVED_COSINE9_COMMON_REDISTRIBUTION_SCREEN",
        code_sha256={path.name: digest(path.read_bytes().replace(b"\r\n", b"\n")) for path in COPIED_SOURCES},
        input_checkpoint_sha256=CHECKPOINT_SHA, input_completion_sha256=COMPLETION_SHA,
        input_mask_sha256=MASK_SHA, budget=CAP,
        definition=dict(alpha="Common input-independent interpolation from saved nodes to their weak-preserving maximum",
                        ordering="The interior is strictly ordered for alpha < 1",
                        strong="strict FP32 truth > 20", point_threshold="strict FP32 A > 20",
                        decision="Existence of a shared alpha with TP > 0 and FP = 0; descriptive feasibility only",
                        no_parameter_selection=True, final_2025_access=False),
    )


def first_crossing(p, nodes):
    vertex = weak_preserving_vertex(nodes)
    if point(p, vertex) <= np.float32(20.):
        return None
    if point(p, nodes) > np.float32(20.):
        raise ValueError("Saved COSINE9 must have no fixed-A exceedances")
    low, high = 0., 1.
    for _ in range(40):
        center = (low + high) / 2
        if point(p, nodes + center * (vertex - nodes)) > np.float32(20.):
            high = center
        else:
            low = center
    return low, high


def conclusion(positive, negative):
    if positive is None:
        return "NO_REACHABLE_STRONG_RAIN_IN_THIS_FAMILY"
    if negative is None or positive[1] < negative[0]:
        return "SAVED_DEV_NONEMPTY_SCALAR_INTERVAL"
    if negative[1] <= positive[0]:
        return "NEGATIVE_CROSSES_FIRST_CLOSE_SHARED_SCALAR_FAMILY"
    return "CROSSING_ORDER_UNRESOLVED_AT_NUMERICAL_RESOLUTION"


def execute(files, plan):
    if plan != json.loads(PROPOSAL.read_text(encoding="utf-8")):
        raise ValueError("The saved-array or code identity changed")
    identity = digest(canonical(plan))
    grant = json.loads((RUN / "RESEARCHER_APPROVAL.json").read_text(encoding="utf-8"))
    if (grant.get("approved_by_researcher") is not True or not grant.get("decision_id")
            or grant.get("proposal_sha256") != identity or grant.get("budget") != CAP):
        raise PermissionError("Exact full-population saved-array analysis grant required")
    write(RUN / "attempt.json", dict(proposal_sha256=identity, automatic_retry=False))
    started = time.monotonic()
    earliest = {"strong": None, "nonstrong": None}
    counts = dict(strong=0, nonstrong=0)
    totals = np.zeros((4, 3), dtype=np.int64)
    q32_totals = np.zeros_like(totals)
    mask_hash = hashlib.sha256()
    size_total = scenes = 0
    for index, item in enumerate(files):
        name = f"batch_{index:03}.npz"
        path = SOURCE / "arrays" / name
        size = item["bytes"]
        if (item["file"] != name or item["scene_start"] != scenes or path.stat().st_size != size
                or path.resolve().parent != SOURCE.resolve() / "arrays"
                or size_total + size > CAP["saved_array_bytes"]
                or time.monotonic() - started > CAP["max_seconds"]):
            raise ValueError("Saved shard identity or budget differs before read")
        with path.open("rb") as stream:
            blob = stream.read(size)
        if len(blob) != size or digest(blob) != item["sha256"]:
            raise ValueError("Saved shard digest changed")
        size_total += size
        with np.load(BytesIO(blob), allow_pickle=False) as arrays:
            ids, mask = arrays["scene_ids"], arrays["supervision_mask"]
            if (len(ids) != item["scenes"] or mask.shape != (len(ids), 100, 100)
                    or mask.dtype != np.bool_ or not np.all(mask.sum(axis=(1, 2)) == 3430)):
                raise ValueError("Saved supervision mask differs")
            for scene, valid in zip(ids, mask):
                key = str(scene).encode()
                mask_hash.update(len(key).to_bytes(4, "big"))
                mask_hash.update(key)
                mask_hash.update(np.asarray(valid.shape, dtype="<i8").tobytes())
                mask_hash.update(valid.tobytes(order="C"))
            obs, p, qlog = arrays["truth_mm_h"], arrays["p"], arrays["qlog"]
            t, q = tally(obs, p, qlog)
            if int(t.sum()) != item["n_valid"] or int(t.sum()) != int(mask.sum()):
                raise ValueError("Saved prediction and label populations differ")
            totals += t
            q32_totals += q
            scenes += len(ids)
            ceiling = (p.astype(np.float64) * np.expm1(qlog[:, -1])).astype(np.float32)
            for i in np.flatnonzero(ceiling > np.float32(20.)):
                root = first_crossing(float(p[i]), qlog[i])
                if root is not None:
                    row = "strong" if obs[i] > np.float32(20.) else "nonstrong"
                    counts[row] += 1
                    current = earliest[row]
                    earliest[row] = root if current is None else tuple(map(min, zip(current, root)))
    elapsed = time.monotonic() - started
    if (scenes != 963 or tuple(totals.sum(axis=1)) != (2895270, 246473, 160630, 717)
            or (int(q32_totals[:3].sum()), int(q32_totals[3].sum())) != (5769, 160)
            or mask_hash.hexdigest() != MASK_SHA or size_total != CAP["saved_array_bytes"]
            or elapsed > CAP["max_seconds"] or counts["strong"] != 5):
        raise ValueError("The archived population, strong overlap or execution budget differs")
    write(RUN / "result.json", dict(
        status=conclusion(earliest["strong"], earliest["nonstrong"]), proposal_sha256=identity,
        crossing_brackets=earliest, reachable_counts=counts, scenes=scenes, elapsed_seconds=elapsed,
        saved_array_bytes=size_total, saved_array_opens=len(files), trained_model=False, final_2025_access=False,
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "execute"))
    args = parser.parse_args()
    files = manifest()
    plan = proposal()
    if args.mode == "prepare":
        if PROPOSAL.exists() or RUN.exists():
            raise FileExistsError("Use a fresh saved-array analysis")
        for i, item in enumerate(files):
            name = f"batch_{i:03}.npz"
            if item["file"] != name or (SOURCE / "arrays" / name).stat().st_size != item["bytes"]:
                raise ValueError("Saved shard metadata differs")
        RUN.mkdir()
        write(PROPOSAL, plan)
        print(digest(canonical(plan)))
    else:
        execute(files, plan)


if __name__ == "__main__":
    main()
