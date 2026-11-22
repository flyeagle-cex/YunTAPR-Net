"""Prepare or run one approved local-gradient diagnostic on a pinned saved archive."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
import time

import numpy as np

from tools.research_readiness.a20_fixed_endpoint_bounds import ARCHIVE_BYTES, ARCHIVE_SHA256, CHECKPOINT_SHA256, TAU


SCOPE = "COSINE9_E9_DEV_SAVED_STRONG_TAIL_GRADIENT"
PROPOSAL_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/research_readiness/20261121_stage45_observation_feasibility/COSINE9_SAVED_TAIL_GRADIENT_PROPOSAL.json"
)
BUDGET = dict(saved_record_bytes=ARCHIVE_BYTES, saved_record_opens=1, seconds=60,
              scientific_source_reads=0, checkpoint_loads=0, forwards=0,
              optimizer_updates=0, retries=0, final_2025_access=False)
SUPPORT = math.log1p(.1)
EPS = np.finfo(np.float64).eps


def summarize(probability, nodes, truth):
    """Classify infinitesimal directions before FP32 point-value rounding."""
    n = truth.size
    if (truth.shape != (n,) or probability.shape != (n,) or nodes.shape != (n, 32)
            or not all(x.dtype == np.float64 and np.isfinite(x).all() for x in (probability, nodes, truth))
            or np.any((probability < 0) | (probability > 1)) or np.any(truth.astype(np.float32) <= 20)
            or np.any(nodes[:, 0] <= SUPPORT) or np.any(np.diff(nodes, axis=1) <= 0)):
        raise ValueError("Expected finite FP64 strong-rain arrays and strictly ordered supported nodes")

    target = np.log1p(truth)[:, None]
    delta = nodes - target
    tie = np.any(np.abs(delta) <= 8 * EPS * np.maximum(np.abs(nodes), np.abs(target)), axis=1)
    grad = (np.asarray(delta > 0, dtype=np.float64) - TAU) / 32
    with np.errstate(over="raise", invalid="raise"):
        point_grad = probability[:, None] * np.exp(nodes) / 32
    span_fraction = (nodes - SUPPORT) / (nodes[:, -1:] - SUPPORT)

    def directions(terms):
        # Each product sum has 32 terms. Only classify signs separated from FP64 roundoff.
        dot = np.sum(terms, axis=1)
        tolerance = 64 * EPS * np.sum(np.abs(terms), axis=1)
        reliable = ~tie & (probability > 0)
        conflict = reliable & (dot > tolerance)
        aligned = reliable & (dot < -tolerance)
        return dict(conflict=conflict, aligned=aligned, indeterminate=~(conflict | aligned))

    results = {
        "independent_nodes": directions(grad * point_grad),
        # dA/dS > 0 for p>0. The raw span logit contributes only a positive factor.
        "fixed_allocation_span": directions(grad * span_fraction),
    }

    def counts(mask):
        count = int(mask.sum())
        return dict(
            n=count, near_truth_knot=int((mask & tie).sum()),
            zero_probability=int((mask & (probability == 0)).sum()),
            all_nodes_below_truth=int((mask & (delta[:, -1] < 0)).sum()),
            strictly_mixed=int((mask & (delta[:, 0] < 0) & (delta[:, -1] > 0)).sum()),
            **{method: dict(**{key: int((mask & selected).sum()) for key, selected in group.items()},
                            conflict_fraction=int((mask & group["conflict"]).sum()) / count if count else None)
               for method, group in results.items()},
        )

    return dict(all_strong=counts(np.ones(n, dtype=bool)),
                by_truth_mm_h={
                    "(20,30]": counts(truth <= 30),
                    "(30,50]": counts((truth > 30) & (truth <= 50)),
                    "(50,inf)": counts(truth > 50),
                })


def build_proposal():
    plan = dict(
        authorization_scope=SCOPE, budget=BUDGET,
        code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        constants_module_sha256=sha256(Path(__file__).with_name("a20_fixed_endpoint_bounds.py").read_bytes()).hexdigest(),
        archive_sha256=ARCHIVE_SHA256, checkpoint_sha256=CHECKPOINT_SHA256,
        population=dict(year=2024, split="Dev", arm="B7_REAL_COSINE9", seed=2029,
                        endpoint="E9_LAST", strong_pixel_times=717),
        methods=["independent_nodes", "fixed_allocation_span"],
        status="PROPOSAL_ONLY_REQUIRES_SEPARATE_APPROVAL",
    )
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    return dict(plan, proposal_sha256=sha256(encoded).hexdigest())


def _verified_result(raw):
    if len(raw) != ARCHIVE_BYTES or sha256(raw).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Saved COSINE9 archive length or digest differs")
    with np.load(BytesIO(raw), allow_pickle=False) as data:
        p, nodes, truth = (data[key] for key in ("p_occ", "qlog", "truth_mm_h"))
        scene, time_utc, pixel = (data[key] for key in ("scene_id", "analysis_time", "pixel_index"))
        if (truth.shape != (717,) or not all(x.shape == truth.shape for x in (scene, time_utc, pixel))
                or len(set(zip(scene, time_utc, pixel))) != 717
                or not all(t.startswith("2024-") for t in time_utc)):
            raise ValueError("Frozen 2024 Dev scene and pixel-time identities differ")
        result = summarize(p, nodes, truth)
        with np.errstate(over="raise", invalid="raise"):
            physical = np.expm1(nodes)
            point = (p * physical.mean(axis=1)).astype(np.float32)
        q32 = physical[:, -1]
        saved_a = data["point_A_mm_h"]
        if (saved_a.shape != truth.shape or not np.array_equal(point, saved_a.astype(np.float32))
                or np.any(point > 20) or int((q32.astype(np.float32) > 20).sum()) != 160
                or int((q32 >= truth).sum()) != 100):
            raise ValueError("Predictive counts or frozen FP32 point A differ")
    return result


def execute_once(archive, run_folder):
    start = time.monotonic()
    proposal = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    if proposal != build_proposal():
        raise PermissionError("Frozen proposal and current code differ")
    grant = json.loads((run_folder / "RESEARCHER_APPROVAL.json").read_text(encoding="utf-8"))
    if (grant.get("approved_by_researcher") is not True or not grant.get("decision_id")
            or any(grant.get(k) != proposal[k] for k in ("authorization_scope", "budget", "proposal_sha256"))):
        raise PermissionError("Separate approval of this exact saved-record scope is required")
    if archive.name != "strong_joint_pixels.npz" or archive.stat().st_size != ARCHIVE_BYTES:
        raise ValueError("Saved strong-rain archive name or size differs")
    output = run_folder / "output"
    output.mkdir(exist_ok=False)
    with archive.open("rb") as stream:
        raw = stream.read(ARCHIVE_BYTES)
    result = _verified_result(raw)
    elapsed = time.monotonic() - start
    if elapsed > BUDGET["seconds"]:
        raise TimeoutError("Saved-record analysis deadline exceeded")
    result.update(
        status="COMPLETE_SAVED_STRONG_LOCAL_GRADIENT", scientific_status="NOT_VERIFIED",
        proposal_sha256=proposal["proposal_sha256"], elapsed_seconds=elapsed,
        archive_sha256=ARCHIVE_SHA256, checkpoint_sha256=CHECKPOINT_SHA256,
        actual_usage=BUDGET | {"seconds": elapsed},
    )
    with (output / "completion.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    commands.add_parser("proposal")
    execute = commands.add_parser("execute")
    execute.add_argument("--archive", type=Path, required=True)
    execute.add_argument("--run-folder", type=Path, required=True)
    args = parser.parse_args()
    result = build_proposal() if args.mode == "proposal" else execute_once(args.archive, args.run_folder)
    print(json.dumps(result, indent=2, allow_nan=False))
