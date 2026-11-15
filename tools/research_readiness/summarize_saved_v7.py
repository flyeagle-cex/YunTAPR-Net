"""Summarize two saved V7 strong-pixel records without model or source access."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path

import numpy as np


PROPOSAL = "00c5174611d23195bc212f7642a4964ee40b753a2c2b4cd104df857d5f623d5c"
ARMS = ("CONTROL_E0", "CANDIDATE_COSINE9")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def summarize(folder, proposal_path):
    metadata = {}
    metadata_bytes = 0
    for name in ("completion.json", "paired_metrics.json", "paired_joint_evidence.json"):
        raw = (folder / name).read_bytes()
        metadata_bytes += len(raw)
        metadata[name] = (json.loads(raw), digest(raw))
    raw = proposal_path.read_bytes()
    metadata_bytes += len(raw)
    proposal = json.loads(raw)
    canonical = json.dumps({k: v for k, v in proposal.items() if k != "proposal_sha256"},
                           sort_keys=True, separators=(",", ":")).encode()
    if digest(canonical) != PROPOSAL:
        raise ValueError("Canonical proposal digest differs")
    complete = metadata["completion.json"][0]
    paired = metadata["paired_metrics.json"][0]
    joint = metadata["paired_joint_evidence.json"][0]
    if any(d.get("proposal_sha256") != PROPOSAL for d in (complete, paired, joint)):
        raise ValueError("Receipt proposal binding differs")
    if (complete["paired_metrics_sha256"] != metadata["paired_metrics.json"][1]
            or paired["paired_joint_evidence_sha256"] != metadata["paired_joint_evidence.json"][1]):
        raise ValueError("Receipt digest chain differs")
    if complete["status"] != "COMPLETE_PAIRED_POINT_EVALUATION":
        raise ValueError("Completed V7 receipt required")
    if (folder / "failure.json").exists():
        raise ValueError("Failure receipt present")

    arms = {}
    keys = None
    truth = None
    record_bytes = 0
    for arm in ARMS:
        result = complete["results"][arm]
        summary = result["joint_summary"]
        path = folder / arm / "strong_joint_pixels.npz"
        size = path.stat().st_size
        if record_bytes + size > 1024 ** 2:
            raise ValueError("Two saved record files exceed 1 MiB admission cap")
        raw = path.read_bytes()
        record_bytes += len(raw)
        if len(raw) != summary["record_bytes"] or digest(raw) != summary["record_sha256"]:
            raise ValueError("Saved record identity differs")
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            a = {name: archive[name] for name in archive.files}
        current_keys = list(zip(a["scene_id"].tolist(), a["analysis_time"].tolist(),
                                a["pixel_index"].tolist()))
        if len(current_keys) != 717 or len(set(current_keys)) != 717:
            raise ValueError("Exact 717 unique strong-pixel keys required")
        if keys is not None and (current_keys != keys or not np.array_equal(a["truth_mm_h"], truth)):
            raise ValueError("Paired keys or truth differ")
        keys, truth = current_keys, a["truth_mm_h"]
        if not all(str(stamp).startswith("2024-") for stamp in a["analysis_time"]):
            raise ValueError("2024 Development records required")
        if not np.all(truth.astype(np.float32) > np.float32(20)):
            raise ValueError("Record contains observations outside strong subset")
        p = a["p_occ"].astype(np.float64)
        q = np.expm1(a["qlog"].astype(np.float64))
        if (q.shape != (717, 32) or not np.isfinite(q).all()
                or not np.isfinite(p).all() or np.any((p < 0) | (p > 1))):
            raise ValueError("Invalid saved prediction fields")
        conditional_mean = q.mean(axis=1)
        q32_gt20 = q[:, -1].astype(np.float32) > np.float32(20)
        point_counts = {m: int(np.sum(a[f"point_{m}_mm_h"].astype(np.float32) > np.float32(20)))
                        for m in ("A", "B", "C")}
        counts = {"q32_ge_truth": int(np.sum(q[:, -1] >= truth)),
                  "q32_gt20": int(q32_gt20.sum()),
                  **{f"{m}_gt20": n for m, n in point_counts.items()}}
        if any(counts[k] != summary["strong_joint_counts"][k] for k in counts):
            raise ValueError("Saved records and completion summary disagree")
        expected_A = p * conditional_mean
        if not np.allclose(expected_A, a["point_A_mm_h"], atol=1e-12, rtol=1e-12):
            raise ValueError("Saved A formula disagrees with quantiles and probability")
        for method, count in point_counts.items():
            row = next(r for r in paired["arms"][arm]["methods"][method]["thresholds"]
                       if r["threshold_mm_h"] == 20)
            if row["TP"] != count or row["TP"] + row["FN"] != 717:
                raise ValueError("Point summary and strong records disagree")
        dates, date_counts = np.unique([str(x)[:10] for x in a["analysis_time"]], return_counts=True)
        node_counts = np.sum(q.astype(np.float32) > np.float32(20), axis=1)
        shape_groups = {}
        for label, selected in (("all_strong", np.ones(717, dtype=bool)),
                                ("q32_gt20_strong", q32_gt20)):
            group = q[selected]
            group_counts = node_counts[selected]
            shape_groups[label] = dict(
                n=int(selected.sum()),
                node_count_gt20_histogram=np.bincount(group_counts, minlength=33).tolist(),
                median_node_count_gt20=float(np.median(group_counts)) if group_counts.size else None,
                nodes={f"q{index + 1}": dict(
                    tau=(index + 0.5) / 32,
                    median_mm_h=float(np.median(group[:, index])) if group.size else None,
                    mean_mm_h=float(np.mean(group[:, index])) if group.size else None,
                    gt20_count=int(np.sum(group[:, index].astype(np.float32) > np.float32(20))),
                ) for index in (15, 23, 27, 31)},
            )
        arms[arm] = dict(
            n=717, counts=counts,
            quantile_node_shape=shape_groups,
            p_occ_ge_half=int(np.sum(p >= 0.5)),
            conditional_node_mean_gt20=int(np.sum(conditional_mean.astype(np.float32) > np.float32(20))),
            conditional_mean_gt20_but_A_le20=int(np.sum((conditional_mean.astype(np.float32) > np.float32(20)) & (a["point_A_mm_h"].astype(np.float32) <= np.float32(20)))),
            q32_gt20_and_p_occ_ge_half=int(np.sum(q32_gt20 & (p >= 0.5))),
            p_occ_percentiles=dict(zip(("min", "p25", "median", "p75", "max"), np.percentile(p, [0, 25, 50, 75, 100]).tolist())),
            conditional_node_mean_percentiles_mm_h=dict(zip(("min", "p25", "median", "p75", "max"), np.percentile(conditional_mean, [0, 25, 50, 75, 100]).tolist())),
            strong_record_dates=int(len(dates)),
            largest_calendar_day_share=float(date_counts.max() / 717),
            calendar_dates_are_independent_events=False,
        )
    budget = proposal["budget"]
    accounting = complete["accounting"]
    if (accounting["cumulative_source_reserved_bytes"] > budget["cumulative_source_cap_bytes"]
            or accounting["cumulative_total_open_instances"] > budget["cumulative_total_opens"]):
        raise ValueError("Completion exceeds cumulative execution budget")
    return dict(
        status="COMPLETE_SAVED_RECORD_DESCRIPTIVE_DIAGNOSTIC", proposal_sha256=PROPOSAL,
        execution_code_commit=proposal["execution_code_commit"],
        observed_at=datetime.now(timezone.utc).isoformat(),
        source_receipt_sha256={name: value[1] for name, value in metadata.items()},
        original_execution_accounting=accounting,
        original_execution_finished=complete["finished"],
        original_elapsed_seconds=complete["elapsed_since_first_preflight_seconds"],
        postprocessing_reads=dict(metadata_files=4, metadata_bytes=metadata_bytes,
                                 saved_record_files=2, saved_record_bytes=record_bytes,
                                 original_weather_or_weight_files=0),
        checks=dict(canonical_proposal=True, receipt_chain=True, paired_record_identity=True,
                    counts_match_saved_receipts=True, point_A_formula=True, execution_budget=True),
        arms=arms, scientific_status="NOT_VERIFIED", interpretation="STRONG_SUBSET_DESCRIPTIVE_ONLY",
        full_population_event_bootstrap_feasible_from_saved_point_summaries=False,
        missing_for_full_population_event_comparison=["per_scene_error_sums", "per_scene_contingency_tables", "frozen_event_membership"],
        no_inference_or_training_performed=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--proposal", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    if args.receipt.exists():
        raise FileExistsError("Use a fresh receipt destination")
    receipt = summarize(args.output_root, args.proposal)
    with args.receipt.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "arms": receipt["arms"],
                      "postprocessing_reads": receipt["postprocessing_reads"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
