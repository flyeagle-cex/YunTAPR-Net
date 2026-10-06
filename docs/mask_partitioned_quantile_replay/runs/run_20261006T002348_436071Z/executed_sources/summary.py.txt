"""Saved scalar/argmax journals only; never construct or run a model."""
import csv
import json
import math
from mask_partitioned_replay_v1 import common as c
from diagnose_saved_quantile_extremes_v1 import percentile


def distribution(values):
    return {"n_forwards": len(values), "median": percentile(values, .5), "p90": percentile(values, .9),
            "p99": percentile(values, .99), "p99_9": percentile(values, .999), "max": max(values)}


def cohort(rows):
    result = {"forwards": len(rows), "scene_exposures": sum(len(r["sample_ids"]) for r in rows), "regions": {}}
    for name in c.REGIONS:
        parts = [r["mask_partitioned"][name] for r in rows]
        maximum_row = max(rows, key=lambda r: r["mask_partitioned"][name]["global_qlog_max"])
        maximum_part = maximum_row["mask_partitioned"][name]
        spatial = sum(p["scene_pixel_exposures"] for p in parts)
        totals = []
        for i, rate in enumerate(c.RATES):
            value = sum(p["threshold_exceedance_counts"][i]["scene_pixel_tau_exposure"] for p in parts)
            any_tau = sum(p["threshold_exceedance_counts"][i]["scene_pixel_any_tau_exposure"] for p in parts)
            totals.append({"physical_threshold_mm_h": rate, "qlog_threshold": math.log1p(rate),
                "scene_pixel_tau_exposure": value, "scene_pixel_any_tau_exposure": any_tau,
                "per_tau_scene_pixel_exposure": [sum(p["threshold_exceedance_counts"][i]["per_tau_scene_pixel_exposure"][t] for p in parts) for t in range(32)],
                "fraction_of_scene_pixel_tau_exposures": value / (spatial * 32),
                "fraction_of_scene_pixel_any_tau_exposures": any_tau / spatial})
        result["regions"][name] = {"global_qlog_min": min(p["global_qlog_min"] for p in parts),
            "global_qlog_max": maximum_part["global_qlog_max"],
            "global_argmax": {"update": maximum_row["update"], **maximum_part["argmax"]},
            "per_forward_max_distribution": distribution([p["global_qlog_max"] for p in parts]),
            "per_tau_forward_max_distributions": [{"tau_ordinal": t + 1, "tau": (t + .5) / 32,
                **distribution([p["per_tau_qlog_max"][t] for p in parts])} for t in range(32)],
            "threshold_exceedance_totals": totals, "cells_per_scene": c.CELLS[name],
            "scene_pixel_exposures": spatial, "scene_pixel_tau_exposures": spatial * 32,
            "FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED": maximum_part["global_qlog_max"] > c.FP64_BOUNDARY,
            "fp64_boundary_scene_pixel_tau_exposure": sum(p["fp64_boundary_scene_pixel_tau_exposure"] for p in parts),
            "fp64_boundary_scene_pixel_any_tau_exposure": sum(p["fp64_boundary_scene_pixel_any_tau_exposure"] for p in parts)}
    return result


CSV_FIELDS = ["update", "epoch_batch", "status", "region", "global_qlog_min", "global_qlog_max",
              "argmax_sample_id", "argmax_batch_index", "argmax_tau_ordinal", "argmax_tau", "argmax_row", "argmax_column",
              "per_tau_qlog_max", "per_tau_qlog_median", "FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED",
              "fp64_boundary_scene_pixel_tau_exposure", "fp64_boundary_scene_pixel_any_tau_exposure"]
for rate in c.RATES:
    CSV_FIELDS += [f"above_{rate}_scene_pixel_tau", f"above_{rate}_scene_pixel_any_tau", f"above_{rate}_per_tau_scene_pixel"]


def csv_records(rows):
    for row in rows:
        for name in c.REGIONS:
            p = row["mask_partitioned"][name]; loc = p["argmax"]
            record = {"update": row["update"], "epoch_batch": row["update"] - c.BOUNDARY,
                      "status": row["status"], "region": name,
                      "global_qlog_min": p["global_qlog_min"], "global_qlog_max": p["global_qlog_max"],
                      **{"argmax_" + k: loc[k] for k in ("sample_id", "batch_index", "tau_ordinal", "tau", "row", "column")},
                      "per_tau_qlog_max": json.dumps(p["per_tau_qlog_max"], separators=(",", ":")),
                      "per_tau_qlog_median": json.dumps(p["per_tau_qlog_median"], separators=(",", ":")),
                      **{k: p[k] for k in ("FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED", "fp64_boundary_scene_pixel_tau_exposure", "fp64_boundary_scene_pixel_any_tau_exposure")}}
            for counts in p["threshold_exceedance_counts"]:
                rate = counts["physical_threshold_mm_h"]
                record.update({f"above_{rate}_scene_pixel_tau": counts["scene_pixel_tau_exposure"],
                               f"above_{rate}_scene_pixel_any_tau": counts["scene_pixel_any_tau_exposure"],
                               f"above_{rate}_per_tau_scene_pixel": json.dumps(counts["per_tau_scene_pixel_exposure"], separators=(",", ":"))})
            yield record


def validate_row(row):
    parts = row["mask_partitioned"]
    if set(parts) != set(c.REGIONS) or row["scope"] != c.SCOPE or not row["captured_before_expm1"]:
        raise ValueError("Incomplete or wrong-scope regional observation")
    for name in c.REGIONS:
        p = parts[name]; loc = p["argmax"]; b = len(row["sample_ids"])
        if (p["cells_per_scene"] != c.CELLS[name] or p["scene_exposures"] != b
                or p["scene_pixel_exposures"] != b * c.CELLS[name]
                or p["scene_pixel_tau_exposures"] != b * c.CELLS[name] * 32):
            raise ValueError("Partition exposure denominator mismatch")
        if (len(p["per_tau_qlog_max"]) != 32 or len(p["per_tau_qlog_median"]) != 32
                or max(p["per_tau_qlog_max"]) != p["global_qlog_max"]
                or loc["qlog_value"] != p["global_qlog_max"]
                or row["sample_ids"][loc["batch_index"]] != loc["sample_id"]
                or not (0 <= loc["row"] < 100 and 0 <= loc["column"] < 100)
                or loc["tau"] != (loc["tau_ordinal"] - .5) / 32):
            raise ValueError("Argmax/per-tau summary identity mismatch")
        if not all(math.isfinite(v) for v in p["per_tau_qlog_max"] + p["per_tau_qlog_median"]):
            raise ValueError("Nonfinite saved qlog summary")
        if p["FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED"] != (p["global_qlog_max"] > c.FP64_BOUNDARY):
            raise ValueError("FP64 boundary flag mismatch")
        for rate, counts in zip(c.RATES, p["threshold_exceedance_counts"]):
            if (counts["physical_threshold_mm_h"] != rate or counts["qlog_threshold"] != math.log1p(rate)
                    or len(counts["per_tau_scene_pixel_exposure"]) != 32
                    or sum(counts["per_tau_scene_pixel_exposure"]) != counts["scene_pixel_tau_exposure"]
                    or not 0 <= counts["scene_pixel_any_tau_exposure"] <= p["scene_pixel_exposures"]
                    or not counts["scene_pixel_any_tau_exposure"] <= counts["scene_pixel_tau_exposure"] <= counts["scene_pixel_any_tau_exposure"] * 32):
                raise ValueError("Threshold exposure unit/count mismatch")


def finalize(run):
    rows = []
    with (run / "mask_partitioned_forward_observations.jsonl").open(encoding="utf8") as handle:
        for ordinal, line in enumerate(handle):
            row = json.loads(line); validate_row(row)
            expected = "SUCCESS_EXACT_MATCH" if ordinal < c.SUCCESS else "EXPECTED_FORWARD_OVERFLOW"
            if row["update"] != c.BOUNDARY + ordinal + 1 or row["status"] != expected:
                raise ValueError("Incomplete or reordered replay journal")
            rows.append(row)
    if len(rows) != c.FAIL_BATCH:
        raise ValueError("Only complete frozen replay can yield a complete summary")
    cohorts = {"SUCCESSFUL_UPDATES_ONLY": cohort(rows[:-1]),
               "SUCCESSFUL_UPDATES_PLUS_FAILING_FORWARD": cohort(rows)}
    all_parts = cohorts["SUCCESSFUL_UPDATES_PLUS_FAILING_FORWARD"]["regions"]
    inside, outside = all_parts[c.REGIONS[0]], all_parts[c.REGIONS[1]]
    key_results = {"INSIDE_MAX_QLOG": inside["global_qlog_max"], "OUTSIDE_MAX_QLOG": outside["global_qlog_max"],
        "INSIDE_PER_FORWARD_MAX_P99": inside["per_forward_max_distribution"]["p99"],
        "INSIDE_PER_FORWARD_MAX_P99_9": inside["per_forward_max_distribution"]["p99_9"],
        "OUTSIDE_PER_FORWARD_MAX_P99": outside["per_forward_max_distribution"]["p99"],
        "OUTSIDE_PER_FORWARD_MAX_P99_9": outside["per_forward_max_distribution"]["p99_9"],
        "INSIDE_THRESHOLD_COUNTS": inside["threshold_exceedance_totals"],
        "OUTSIDE_THRESHOLD_COUNTS": outside["threshold_exceedance_totals"],
        "INSIDE_PHYSICAL_OVERFLOW_RISK_OBSERVED": inside["FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED"],
        "OUTSIDE_PHYSICAL_OVERFLOW_RISK_OBSERVED": outside["FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED"]}
    result = {"utc": c.now(), "scope": c.SCOPE, "baseline_commit": c.BASELINE,
        "status": "COMPLETE_MASK_PARTITIONED_REPLAY", "cohorts": cohorts, **key_results,
        "FP64_PHYSICAL_BOUNDARY": c.FP64_BOUNDARY, "failure_forward": c.read(run / "mask_partitioned_failure_forward.json"),
        "definitions": {"qlog": "log1p(mm/h)", "count_operator": "strict > log1p(rate)",
            "threshold_purpose": "Descriptive only; not training rules, exclusions, QC or scientific thresholds.",
            "scene_pixel_tau_exposure": "One scene, native pixel and tau in one forward; sum per-tau counts.",
            "scene_pixel_any_tau_exposure": "One scene/pixel in one forward, counted once if any tau exceeds; not 32 pixels.",
            "per_tau_qlog_median": "Lower median across all batch elements and regional pixels, inherited torch.median convention.",
            "per_forward_max_distribution": "One regional maximum over batch/pixels/taus per forward; empirical quantiles linear h=(n-1)*p.",
            "per_tau_max_distribution": "One regional spatial/batch maximum at each tau per forward; same linear empirical quantiles.",
            "coordinate_convention": "Zero-based native target row/column; frozen mask; no transpose or flip.",
            "outside": "Complement of frozen Yunnan evaluation mask within native 100x100 target grid; no IMERG-validity filter.",
            "interpretation": "Risk booleans describe only this frozen replay trajectory; not a future guarantee. Major tail concentration is described by extrema, counts and exposure fractions; no new mainly threshold is selected.",
            "pixel_percentiles": "Pooled pixel-level p99/p99.9 are not measured; only the requested per-forward maxima distributions."},
        "FORMAL_OPTIMIZER_STEPS": c.FORMAL_STEPS, "FORMAL_OPTIMIZER_STEPS_ADDED": 0,
        "B1_PHASE_B_STARTED": False, "2025_RAW_ACCESS": 0, "FORMAL_RESUME_AUTHORIZED": False,
        "RESEARCHER_DECISION_REQUIRED": True, "full_tensors_saved": False,
        "journal_identity": c.pin(run / "mask_partitioned_forward_observations.jsonl")}
    c.write(run / "mask_partitioned_quantile_extremes.json", result)
    records = list(csv_records(rows))
    with (run / "mask_partitioned_quantile_extremes.csv").open("x", encoding="utf8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(records)
    with (run / "mask_partitioned_quantile_extremes.csv").open(encoding="utf8", newline="") as handle:
        actual = list(csv.DictReader(handle))
    expected = [{k: str(row[k]) for k in CSV_FIELDS} for row in records]
    if actual != expected:
        raise ValueError("Regional CSV/JSON journal mismatch")
    lines = ["# 云南内外 quantile extrema：冻结轨迹工程诊断", "",
             "本次仅重放 B0-Matched Phase-B epoch 5 的 8625 次成功更新及第 8626 次失败 forward；正式训练没有恢复。", "",
             f"FP64 physical boundary = `{c.FP64_BOUNDARY!r}`。所有风险结论只针对此次冻结轨迹，不是未来保证。", "",
             "|统计（成功更新 + 失败 forward）|云南内|云南外|", "|---|---:|---:|"]
    for stat in ("median", "p90", "p99", "p99_9", "max"):
        lines.append(f"|per-forward max {stat}|{inside['per_forward_max_distribution'][stat]:.17g}|{outside['per_forward_max_distribution'][stat]:.17g}|")
    lines += ["", f"INSIDE_PHYSICAL_OVERFLOW_RISK_OBSERVED = {key_results['INSIDE_PHYSICAL_OVERFLOW_RISK_OBSERVED']}",
              f"OUTSIDE_PHYSICAL_OVERFLOW_RISK_OBSERVED = {key_results['OUTSIDE_PHYSICAL_OVERFLOW_RISK_OBSERVED']}", "",
              "这些结果不能把‘溢出仅在省外’扩大为‘所有高 upper-tail 值仅在省外’。完整两区 extrema、计数及按暴露量归一化的比例见 JSON。", "",
              "|描述性阈值 mm/h|云南内 pixel-tau|云南外 pixel-tau|云南内 any-tau pixel|云南外 any-tau pixel|", "|---:|---:|---:|---:|---:|"]
    for a, b in zip(inside["threshold_exceedance_totals"], outside["threshold_exceedance_totals"]):
        lines.append(f"|{a['physical_threshold_mm_h']}|{a['scene_pixel_tau_exposure']}|{b['scene_pixel_tau_exposure']}|{a['scene_pixel_any_tau_exposure']}|{b['scene_pixel_any_tau_exposure']}|")
    lines += ["", "阈值仅作 descriptive diagnostics；不改变训练、loss、QC、expm1 或模型。any-tau 每个 scene-pixel 只计一次；pixel-tau 对 tau 分别计数。", "",
              "两个 cohort、32 个 tau 分布、全部 forward 的两区 argmax 身份分别保存在 JSON、CSV 和 aggregate journal；不保存完整 tensor。", "",
              "正式 optimizer steps=50537，新增正式 steps=0；B1 Phase-B 未启动；2025 raw access=0；正式恢复未授权，等待研究者决定。"]
    with (run / "inside_vs_outside_extreme_summary.md").open("x", encoding="utf8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return {"status": result["status"], "key_results": key_results,
            "csv_rows": len(records), "json_csv_reconciliation_pass": True,
            "output_identities": {name: c.pin(run / name) for name in (
                "mask_partitioned_quantile_extremes.json", "mask_partitioned_quantile_extremes.csv", "inside_vs_outside_extreme_summary.md")}}
