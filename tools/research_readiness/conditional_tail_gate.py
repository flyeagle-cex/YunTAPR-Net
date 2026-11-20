"""Build the fixed 2024 Dev tail baseline and evaluate future aggregate receipts."""

import argparse
import hashlib
import json
import math
from pathlib import Path


PROTOCOL = "CONDITIONAL_TAIL_2024_DEV_V1"
POPULATION = dict(scenes=963, n_valid=3303090, n_rain=407820, n_strong=717, n_weak=246473)
GATES = {
    "strong_physical_pinball_over20": "lt",
    "q32_support_tp": "ge",
    "q32_support_fp": "le",
    "point_a_tp": "ge",
    "point_a_fp": "le",
    "weak_log_pinball": "le",
    "occurrence_brier": "le",
    "occurrence_ap": "ge",
    "occurrence_auroc": "ge",
}
COUNTS = {"q32_support_tp", "q32_support_fp", "point_a_tp", "point_a_fp"}
FILES = {
    "paired": "20261115_mountain_pair_results/PAIRED_METRICS.json",
    "b": "20261119_conditional_intensity_diagnostic/B_READOUT_RESULTS.json",
    "heads": "20261119_conditional_intensity_diagnostic/B_HEAD_DIAGNOSTIC.json",
    "proposal": "20261119_conditional_intensity_diagnostic/B_RECOVERY_PROPOSAL.json",
}


def build_baseline(root):
    records, source_hashes = {}, {}
    for label, filename in FILES.items():
        raw = (root / filename).read_bytes()
        records[label] = json.loads(raw)
        source_hashes[filename] = hashlib.sha256(raw).hexdigest()
    paired, b, heads, proposal = (records[name] for name in FILES)
    if not (b["proposal_sha256"] == heads["proposal_sha256"] == proposal["proposal_sha256"]
            and b["completion_receipt_sha256"] == heads["completion_receipt_sha256"]
            and b["checkpoint_sha256"] == heads["checkpoint_sha256"] == proposal["models"][0]["checkpoint_sha256"]
            and paired["proposal_sha256"] == proposal["prior_pair_proposal_sha256"]
            and b["frozen_metrics_gate"]["passed"] is True):
        raise ValueError("The baseline evidence does not identify the same fixed REAL model and population")

    full = paired["full_population"]["REAL_COSINE9"]
    for key in ("scenes", "n_valid", "n_rain"):
        if full[key] != b["population"][key] or full[key] != POPULATION[key]:
            raise ValueError("Invalid population receipt")
    strong = [row for cells in paired["cells"].values() for row in cells
              if row["lower_exclusive"] >= 20 and row["n_rain"]]
    weak = [row for row in b["conditional_bins"]
            if (row["lower_exclusive_mm_h"], row["upper_inclusive_mm_h"]) == (0.1, 1.0)]
    if (sum(row["n_rain"] for row in strong) != POPULATION["n_strong"]
            or b["n_observed_over20"] != POPULATION["n_strong"]
            or len(weak) != 1 or weak[0]["n_rain"] != POPULATION["n_weak"]):
        raise ValueError("Strong or weak truth cohort changed")

    by_group = heads["cohorts"]
    supports = {k: row["n"] - row["funnel"]["no_node_over_20"] for k, row in by_group.items()}
    point_a = next(row for row in paired["point_metrics"]["REAL_COSINE9"]["methods"]["A"]["thresholds"]
                   if row["threshold_mm_h"] == 20.0)
    if any(point_a[k] != v for k, v in heads["replicated_A_contingency"].items()):
        raise ValueError("Point A fixed detection receipt differs")
    metrics = dict(
        strong_physical_pinball_over20=math.fsum(row["real_physical_pinball_over20"] * row["n_rain"]
                                                 for row in strong) / POPULATION["n_strong"],
        q32_support_tp=supports["observed_over_20"],
        q32_support_fp=supports["dry"] + supports["wet_up_to_20"],
        point_a_tp=point_a["TP"], point_a_fp=point_a["FP"],
        weak_log_pinball=weak[0]["conditional_log_pinball"],
        occurrence_brier=full["brier"], occurrence_ap=full["average_precision"],
        occurrence_auroc=full["auroc"],
    )
    if (metrics["q32_support_tp"], metrics["q32_support_fp"], metrics["point_a_tp"], metrics["point_a_fp"]) != (160, 5769, 0, 0):
        raise ValueError("Frozen tail support and point detection counts differ")
    identity = {key: proposal["readout_identity"][key] for key in
                ("population_ids_sha256", "partition_sha256", "supervision_mask_sha256")}
    identity["paired_truth_mask_terrain_sha256"] = paired["paired_population_sha256"]
    return dict(
        status="FROZEN_BASELINE_NO_CANDIDATE", protocol=PROTOCOL, population=POPULATION,
        identity=identity, checkpoint_sha256=b["checkpoint_sha256"], metrics=metrics,
        comparison_directions=GATES, source_receipt_sha256=source_hashes,
        new_inference=0, prediction_shard_opens=0, optimizer_updates=0,
        final_2025_access=False, scientific_status="NOT_VERIFIED",
    )


def validate_metrics(metrics):
    if set(metrics) != set(GATES):
        raise ValueError("Missing or unexpected metric")
    for name, value in metrics.items():
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid metric: {name}")
        if name in COUNTS:
            limit = POPULATION["n_strong"] if name.endswith("_tp") else POPULATION["n_valid"] - POPULATION["n_strong"]
            if type(value) is not int or value > limit:
                raise ValueError(f"Invalid event count: {name}")
        if name.startswith("occurrence_") and value > 1:
            raise ValueError(f"Invalid probability score: {name}")


def evaluate(baseline, candidate):
    if any(candidate.get(key) != baseline[key] for key in ("protocol", "population", "identity")):
        raise ValueError("Candidate must bind the same Development truth, mask, order and node contract")
    if baseline["protocol"] != PROTOCOL or baseline["population"] != POPULATION:
        raise ValueError("Unexpected baseline contract")
    if candidate.get("final_2025_access") is not False:
        raise ValueError("A Development-only candidate receipt is required")
    validate_metrics(baseline["metrics"])
    validate_metrics(candidate["metrics"])
    checks = {}
    for name, direction in GATES.items():
        old, new = baseline["metrics"][name], candidate["metrics"][name]
        passed = new < old if direction == "lt" else new <= old if direction == "le" else new >= old
        checks[name] = dict(baseline=old, candidate=new, delta=new-old, pass_gate=passed)
    passed = all(entry["pass_gate"] for entry in checks.values())
    return dict(
        status="PASS_DEV_TAIL_GATE" if passed else "FAIL_DEV_TAIL_GATE",
        protocol=PROTOCOL, checks=checks,
        point_a_detection_restored=checks["point_a_tp"]["delta"] > 0 and checks["point_a_fp"]["pass_gate"],
        scientific_status="NOT_VERIFIED",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    baseline = sub.add_parser("baseline")
    baseline.add_argument("--receipts-root", type=Path, required=True)
    candidate = sub.add_parser("candidate")
    candidate.add_argument("--baseline", type=Path, required=True)
    candidate.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "baseline":
        result = build_baseline(args.receipts_root)
        validate_metrics(result["metrics"])
    else:
        result = evaluate(json.loads(args.baseline.read_bytes()), json.loads(args.candidate.read_bytes()))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
