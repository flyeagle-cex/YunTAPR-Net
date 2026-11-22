"""Bound fixed-endpoint reachability on the saved COSINE9 strong-rain subset."""

import argparse
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path

import numpy as np


ARCHIVE_BYTES = 199996
ARCHIVE_SHA256 = "6ec4deab0c82ca55ee64355c3c3da1b80239ed599d11717285df6b1ce195e690"
CHECKPOINT_SHA256 = "1c9b5f8c595935674f6952da6b239a50e26ca4eb4d90a217ab5593866d5b319e"
TAU = (np.arange(32, dtype=np.float64) + .5) / 32
WEAK_LIMIT = math.log1p(1.)
THRESHOLD = np.float32(20.)


def point(probability, nodes_log):
    return float(np.float32(probability * np.expm1(nodes_log).mean()))


def pinball(delta):
    return np.maximum(TAU * delta, (TAU - 1) * delta).mean()


def weak_preserving_vertex(nodes_log, upper_cut=None):
    """Maximize physical mean with fixed q32 and exact log Pinball for every weak truth."""
    adjustable = nodes_log > WEAK_LIMIT
    adjustable[-1] = False
    if upper_cut is not None:
        adjustable &= nodes_log <= upper_cut
    indices = np.flatnonzero(adjustable)
    if indices.size < 2:
        return nodes_log.copy()
    end = indices[-1] + 1
    upper = nodes_log[end] if upper_cut is None else min(nodes_log[end], upper_cut)
    width = upper - WEAK_LIMIT
    weights = 1 - TAU[indices]
    moment = float(weights @ (nodes_log[indices] - WEAK_LIMIT))
    suffix = np.r_[np.cumsum(weights[::-1])[::-1], 0.]
    left, right = np.triu_indices(len(suffix), k=1)
    first = (moment - suffix[right] * width) / (suffix[left] - suffix[right])
    feasible = (first >= -1e-12) & (first <= width + 1e-12)
    left, right, first = left[feasible], right[feasible], first[feasible].clip(0, width)
    if not len(first):
        raise ArithmeticError("No vertex found for a feasible weak-rain constraint")
    increments = np.zeros((len(first), len(suffix)), dtype=np.float64)
    increments[np.arange(len(first)), left] = first
    increments[np.arange(len(first)), right] = width - first
    vertices = WEAK_LIMIT + increments.cumsum(axis=1)[:, :-1]
    winner = int(np.expm1(vertices).sum(axis=1).argmax())
    result = nodes_log.copy()
    result[indices] = vertices[winner]
    if (np.any(np.diff(result) < -1e-12)
            or not math.isclose(float(weights @ (result[indices] - WEAK_LIMIT)), moment, rel_tol=0, abs_tol=1e-12)
            or np.expm1(result).sum() + 1e-12 < np.expm1(nodes_log).sum()):
        raise ArithmeticError("Invalid weak-preserving maximum")
    return result


def strict_hit(probability, original, vertex):
    if point(probability, vertex) <= THRESHOLD:
        return None
    low, high = 0., 1.
    for _ in range(44):
        center = (low + high) / 2
        if point(probability, original + center * (vertex - original)) > THRESHOLD:
            high = center
        else:
            low = center
    matched = original + ((high * .99 + .01) * (vertex - original))
    if (point(probability, matched) <= THRESHOLD or np.any(np.diff(matched) <= 0)
            or matched[-1] != original[-1]):
        raise ArithmeticError("Strict ordered crossing could not be reproduced")
    for y in (.11, .5, 1.):
        if abs(pinball(np.log1p(y) - matched) - pinball(np.log1p(y) - original)) > 1e-12:
            raise ArithmeticError("Weak rain loss changed in the crossing witness")
    return matched


def analyze(p, qlog, truth):
    physical = np.expm1(qlog)
    raw_a = (p * physical.mean(axis=1)).astype(np.float32)
    natural = (p * physical[:, -1]).astype(np.float32)
    q32_supported = qlog[:, -1] > math.log1p(20.)
    if np.any(raw_a > natural) or int(q32_supported.sum()) != 160 or np.any(raw_a > THRESHOLD):
        raise ValueError("Archived strong-rain fixed baseline differs")
    bounds = {}
    for name, upper_cut in (("all_high_interior_nodes", None),
                            ("changes_confined_at_or_below_20", math.log1p(20.))):
        ceilings, simultaneous = [], []
        for prob, nodes, observed in zip(p, qlog, truth):
            vertex = weak_preserving_vertex(nodes, upper_cut)
            ceiling = point(prob, vertex)
            ceilings.append(ceiling)
            witness = strict_hit(prob, nodes, vertex)
            if witness is not None:
                change = pinball((observed - np.expm1(witness)) / 20) - pinball(
                    (observed - np.expm1(nodes)) / 20)
                simultaneous.append(float(change))
        bounds[name] = dict(max_A=float(max(ceilings)), n_ceiling_over20=int(sum(value > THRESHOLD for value in ceilings)),
                            strict_crossing_witnesses=len(simultaneous),
                            strict_crossings_improving_own_physical_pinball=sum(delta < 0 for delta in simultaneous),
                            best_crossing_physical_pinball_delta=min(simultaneous, default=None))
    return dict(n=717, existing_a_hits=int((raw_a > THRESHOLD).sum()),
                p_times_q32_max=float(natural.max()), p_times_q32_n_over20=int((natural > THRESHOLD).sum()),
                weak_preserving_bounds=bounds)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists() or args.archive.name != "strong_joint_pixels.npz":
        raise ValueError("Fresh result path and pinned archive name required")
    if args.archive.stat().st_size != ARCHIVE_BYTES:
        raise ValueError("Saved strong-rain record length differs")
    with args.archive.open("rb") as stream:
        raw = stream.read(ARCHIVE_BYTES)
    if len(raw) != ARCHIVE_BYTES or hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Pinned COSINE9 archive identity differs")
    with np.load(BytesIO(raw), allow_pickle=False) as data:
        p, qlog, y = (data[k] for k in ("p_occ", "qlog", "truth_mm_h"))
        ids, times, pixels = (data[k] for k in ("scene_id", "analysis_time", "pixel_index"))
        if (p.shape != (717,) or y.shape != (717,) or qlog.shape != (717, 32)
                or p.dtype != np.float64 or qlog.dtype != np.float64 or y.dtype != np.float64
                or not all(np.isfinite(value).all() for value in (p, qlog, y))
                or np.any((p < 0) | (p > 1)) or np.any(np.diff(qlog, axis=1) <= 0)
                or not all(str(value).startswith("2024-") for value in times)
                or len(set(zip(ids, times, pixels))) != 717 or not np.all(y.astype(np.float32) > THRESHOLD)):
            raise ValueError("Saved strong-rain records differ from the 2024 Development contract")
        result = analyze(p, qlog, y)
    receipt = dict(status="COMPLETE_SAVED_STRONG_SUBSET_BOUND", checkpoint_sha256=CHECKPOINT_SHA256,
                   archive_sha256=ARCHIVE_SHA256, saved_record_bytes=ARCHIVE_BYTES, saved_record_opens=1,
                   observed_development_only=True, full_population_false_alarms_evaluated=False,
                   formal_updates=0, inference_passes=0, raw_source_opens=0, checkpoint_loads=0,
                   final_2025_access=False, **result)
    with args.receipt.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(receipt, allow_nan=False))


if __name__ == "__main__":
    main()
