"""Describe the fixed A point readout using saved B predictions only."""

import argparse
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path

import numpy as np


GROUPS = ("dry", "wet_up_to_20", "observed_over_20")
FUNNEL = ("no_node_over_20", "node_over_20_but_conditional_mean_at_most_20",
          "conditional_mean_over_20_but_A_at_most_20", "A_over_20")


def summary(values):
    quantiles = np.quantile(values, [0, .1, .5, .9, 1])
    return dict(zip(("min", "p10", "median", "p90", "max"), map(float, quantiles)))


def analyze(completion_file, reference, paired):
    raw = completion_file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference["completion_receipt_sha256"]:
        raise ValueError("Unexpected B completion receipt")
    finished = json.loads(raw)
    if finished["status"] != "COMPLETE_SINGLE_ARM_READOUT" or finished["proposal_sha256"] != reference["proposal_sha256"]:
        raise ValueError("The frozen B pass must be complete")
    b = finished["result"]["full_dev_readout"]
    shards = b["storage"]["files"]
    source_cap = reference["prediction_archive_bytes"]
    if len(shards) != reference["output_shards"] or sum(s["bytes"] for s in shards) != source_cap:
        raise ValueError("Saved readout manifest has a different size or file count")

    result = {name: dict(n=0, p=[], q32=[], conditional_mean=[], A=[],
                         funnel=np.zeros(4, dtype=np.int64)) for name in GROUPS}
    groups_by_scene = set()
    delivered = 0
    size_offset = 0
    for i, item in enumerate(shards):
        if (item["file"] != f"batch_{i:03d}.npz" or item["scene_start"] != size_offset
                or type(item["bytes"]) is not int or not 0 < item["bytes"] <= 16 * 1024**2
                or delivered + item["bytes"] > source_cap):
            raise ValueError("Unexpected or over-budget shard binding")
        path = completion_file.parent / "arrays" / item["file"]
        with path.open("rb") as stream:
            if os.fstat(stream.fileno()).st_size != item["bytes"]:
                raise ValueError("Readout shard changed size")
            data = stream.read(item["bytes"])
        delivered += len(data)
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Readout shard differs from its sealed hash")
        with np.load(BytesIO(data), allow_pickle=False) as batch:
            scene_ids, mask = batch["scene_ids"], batch["supervision_mask"]
            p, qlog, truth = batch["p"], batch["qlog"], batch["truth_mm_h"]
        n = item["n_valid"]
        if (scene_ids.shape != (item["scenes"],) or scene_ids.dtype.kind != "U"
                or mask.shape != (item["scenes"], 100, 100) or mask.dtype != np.bool_
                or int(mask.sum()) != n or p.shape != (n,) or truth.shape != (n,)
                or qlog.shape != (n, 32) or p.dtype != np.float32
                or truth.dtype != np.float32 or qlog.dtype != np.float64):
            raise ValueError("Unaligned saved fields")
        ids = set(scene_ids.tolist())
        if len(ids) != item["scenes"] or ids & groups_by_scene or not all(s.startswith("2024-") for s in ids):
            raise ValueError("Unexpected Development scene identity")
        groups_by_scene.update(ids)
        size_offset += len(scene_ids)
        with np.errstate(over="raise", invalid="raise"):
            conditional = np.expm1(qlog).mean(axis=1)
            q32 = np.expm1(qlog[:, -1])
            a = p.astype(np.float64) * conditional
            mean_pass = conditional.astype(np.float32) > np.float32(20)
            a_pass = a.astype(np.float32) > np.float32(20)
        q32_pass = qlog[:, -1] > math.log1p(20)
        if np.any(mean_pass & ~q32_pass) or np.any(a_pass & ~mean_pass):
            raise ValueError("The inherited A readout violated its threshold ordering")
        strong = truth > np.float32(20)
        wet = truth > np.float32(.1)
        for name, cohort in zip(GROUPS, (~wet, wet & ~strong, strong)):
            out = result[name]
            out["n"] += int(cohort.sum())
            for field, data_vector in zip(("p", "q32", "conditional_mean", "A"), (p, q32, conditional, a)):
                out[field].append(data_vector[cohort])
            out["funnel"] += [
                int((cohort & ~q32_pass).sum()),
                int((cohort & q32_pass & ~mean_pass).sum()),
                int((cohort & mean_pass & ~a_pass).sum()),
                int((cohort & a_pass).sum()),
            ]

    populations = reference["population"]
    n_strong = reference["n_observed_over20"]
    expected = (populations["n_valid"] - populations["n_rain"], populations["n_rain"] - n_strong, n_strong)
    if len(groups_by_scene) != populations["scenes"] or tuple(result[k]["n"] for k in GROUPS) != expected:
        raise ValueError("Saved population does not reproduce")
    if delivered != source_cap or sum(r["funnel"][0] for r in result.values()) != reference["quantile_nodes_above20_counts"][0]:
        raise ValueError("Saved archive or q32 totals do not reproduce")
    inherited = paired["point_metrics"]["REAL_COSINE9"]["methods"]["A"]["thresholds"]
    tp = int(result["observed_over_20"]["funnel"][-1])
    fp = sum(int(result[key]["funnel"][-1]) for key in GROUPS[:2])
    saved = next(row for row in inherited if row["threshold_mm_h"] == 20)
    if (tp, fp, n_strong - tp, sum(expected[:2]) - fp) != tuple(saved[k] for k in ("TP", "FP", "FN", "TN")):
        raise ValueError("Method A 20 mm/h table does not reproduce")
    groups = {}
    for name, row in result.items():
        groups[name] = dict(n=row["n"], funnel={k: int(v) for k, v in zip(FUNNEL, row["funnel"])})
        for field in ("p", "q32", "conditional_mean", "A"):
            groups[name][field] = summary(np.concatenate(row[field]))
    return dict(
        status="COMPLETE_SAVED_READOUT_DESCRIPTIVE",
        proposal_sha256=reference["proposal_sha256"],
        completion_receipt_sha256=reference["completion_receipt_sha256"],
        checkpoint_sha256=reference["checkpoint_sha256"],
        saved_prediction_bytes=delivered, saved_prediction_opens=len(shards),
        raw_source_opens=0, checkpoint_loads=0, new_inference=0, optimizer_updates=0,
        thresholds=dict(wet_truth_mm_h=.1, strong_truth_mm_h=20, truth_and_point_classification="strict FP32 >",
                        native_q32_comparison="FP64 qlog32 > log1p(20)"),
        readout="A = p × mean(expm1(qlog_1..32))",
        replicated_A_contingency=dict(TP=tp, FP=fp, FN=n_strong-tp, TN=sum(expected[:2])-fp),
        cohorts=groups,
        interpretation_scope="Single fixed E9 and 2024 Dev; descriptive decomposition of the finite-node A point readout",
        scientific_status="NOT_VERIFIED",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("completion", "reference", "paired", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a new aggregate receipt filename")
    result = analyze(args.completion, json.loads(args.reference.read_bytes()), json.loads(args.paired.read_bytes()))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(result["cohorts"]["observed_over_20"], ensure_ascii=False))


if __name__ == "__main__":
    main()
