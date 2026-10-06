"""Describe saved replay summaries only. No torch, forward, raw data or checkpoints.

Regional pixel percentiles/counts were not saved. Unknown values stay null;
only witnessed maxima and provable count bounds are reported. Rates below
are descriptive queries, never model/QC rules.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "3aca3b73466035f0ae80151aaf256c6223c1eba9"
SOURCE = "docs/quantile_overflow_autopsy/runs/run_20261005T145434_644569Z"
MASK_SOURCE = (
    "docs/paired_extended_pipeline/runs/run_20261005T043214_165890Z/"
    "failure_publication/run_20261005T142819_869305Z/"
    "source_execution_code/src/yuntapr/data/masks.py.txt"
)
INPUT_SHAS = {
    SOURCE + "/replay_observations.jsonl":
        "4f50ba13c2d9554d8292556ffc69e6647fe1328f7d27bd11898799c25ad74f86",
    SOURCE + "/failing_tensor_diagnostics.json":
        "fed2c542705741179f08911a6bfd9b488df5120d1f244855a25a3caa797ee8e1",
    SOURCE + "/readonly_closeout/executed_sources/observer.py.txt":
        "f4a837970de1402ec85ad4cf9231ae8078a624bfbe70acff71f556f5f23e6081",
    SOURCE + "/replay_identity_preflight.json":
        "5f46a79620819dcc9413aadda2bac71f9b047ab2feb7ecc33aa48f51c686ad6d",
    MASK_SOURCE: "c397a5866af834098fd5f36e4acd23a26dfa607058ad298f8781a9766d5a8542",
}
RATES = (10, 50, 100, 500, 1000)
TAUS = tuple((i + 0.5) / 32 for i in range(32))
REGION_CELLS = {"YUNNAN_INSIDE": 3430, "YUNNAN_OUTSIDE": 6570}
EXACT = "EXACT_FROM_SAVED_OBSERVATIONS"
UNKNOWN = "NOT_RECOVERABLE_FROM_SAVED_OBSERVATIONS"
OUTPUT_NAMES = (
    "yunnan_vs_outside_quantile_extremes.json",
    "yunnan_vs_outside_quantile_extremes.csv",
    "saved_observation_execution_manifest.json",
)


def percentile(values, p):
    """Linear empirical quantile: h=(n-1)*p, interpolate adjacent order stats."""
    if not values or not 0 <= p <= 1:
        raise ValueError("Nonempty values and 0<=p<=1 required")
    ordered = sorted(values)
    if not all(math.isfinite(v) for v in ordered):
        raise ValueError("Nonfinite saved qlog statistic")
    h = (len(ordered) - 1) * p
    lo, hi = math.floor(h), math.ceil(h)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (h - lo)


def metric(value=None, *, lower=None, upper=None, reason=""):
    return {"value": value, "status": EXACT if value is not None else UNKNOWN,
            "lower_bound": lower, "upper_bound": upper, "reason": reason}


def maximum_from_witness(whole_max, witness_value=None):
    """A value at a known regional pixel proves equality only if it attains M."""
    if witness_value is not None and witness_value > whole_max:
        raise ValueError("Witness exceeds saved whole-grid maximum")
    if witness_value == whole_max:
        return metric(whole_max, lower=whole_max, upper=whole_max,
                      reason="Known regional pixel attains the cohort whole-grid maximum.")
    return metric(lower=witness_value, upper=whole_max,
                  reason="No saved location/value proves this region's maximum.")


def validate_row(row, ordinal):
    expected_status = "SUCCESS_EXACT_MATCH" if ordinal < 8625 else "EXPECTED_FORWARD_OVERFLOW"
    if ordinal > 8625 or row.get("status") != expected_status or row.get("update") != 41913 + ordinal:
        raise ValueError("Saved observation order/count/status mismatch")
    if row.get("scope") != "ENGINEERING_OVERFLOW_REPLAY_ONLY":
        raise ValueError("Observation scope mismatch")
    ids = row.get("sample_ids", [])
    if len(ids) != 2 or any(s[:4] not in ("2023", "2024") for s in ids):
        raise ValueError("Only the saved 2023/2024 batch2 identities are permitted")
    vals = row.get("qlog_per_tau_max", [])
    if len(vals) != 32 or not all(math.isfinite(v) for v in vals):
        raise ValueError("Invalid saved per-tau maxima")
    q = row["qlog"]
    if q["all_finite"] is not True or q["dtype"] != "torch.float64":
        raise ValueError("Saved qlog must be finite FP64")
    if not math.isfinite(q["min"]) or q["min"] < 0 or q["max"] != max(vals):
        raise ValueError("Saved qlog scalar/max mismatch")
    if any(a > b for a, b in zip(vals, vals[1:])) or q["min"] > min(vals):
        raise ValueError("Inconsistent positive monotone quantile summaries")
    if ordinal < 8625 and row.get("actual_denominator") != 6860:
        raise ValueError("Saved batch2 Yunnan denominator mismatch")


def load_rows(path):
    # Keep only small scalar summaries, never instantiate model/input tensors.
    rows = []
    with path.open(encoding="utf-8") as handle:
        for ordinal, line in enumerate(handle):
            row = json.loads(line)
            validate_row(row, ordinal)
            rows.append({k: row[k] for k in
                         ("update", "status", "sample_ids", "qlog", "qlog_per_tau_max")})
    if len(rows) != 8626:
        raise ValueError("Expected 8625 saved successful updates and one failing forward")
    return rows


def validate_witness(failure, rows):
    row = rows[-1]
    loc = failure["location"]
    values = failure["qlog_32_at_pixel"]
    if (failure["update"] != row["update"] or failure["Yunnan_mask"] is not False
            or failure["qlog_all_finite"] is not True or len(values) != 32
            or failure["observation"]["qlog_per_tau_max"] != row["qlog_per_tau_max"]
            or [r["sample_id"] for r in failure["sample_identities"]] != row["sample_ids"]
            or failure["actual_denominator"] != 6860):
        raise ValueError("Failing outside-pixel witness does not bind to the saved observation")
    if not (0 <= loc["batch_index"] < 2 and 0 <= loc["row"] < 100 and 0 <= loc["column"] < 100):
        raise ValueError("Witness position outside tensor shape")
    if not all(math.isfinite(v) and 0 <= v <= m for v, m in zip(values, row["qlog_per_tau_max"])):
        raise ValueError("Invalid witness quantiles")
    if values[loc["tau_index_zero_based"]] != failure["qlog_max"] or failure["qlog_max"] != row["qlog"]["max"]:
        raise ValueError("Witness global maximum inconsistent")
    return {"update": row["update"], "region": "YUNNAN_OUTSIDE",
            "sample_id": row["sample_ids"][loc["batch_index"]],
            "location": loc, "qlog_values": values, "mask_membership": False,
            "membership_source": "Saved Observer.capture Yunnan_mask; mask was not reopened."}


def distribution(values):
    return {"n_forward_observations": len(values), "p99": percentile(values, .99),
            "p99_9": percentile(values, .999), "max": max(values)}


def count_metric(lower, upper):
    return metric(lower if lower == upper else None, lower=lower, upper=upper,
                  reason=("Count fully determined by saved summaries." if lower == upper else
                          "Exact pixel counts were not saved; these are conservative bounds."))


def exceedance_bounds(rows, region, rate, witness=None):
    """Count scene-pixel exposures, never mistake maximum groups for pixel counts.

    Whole-grid min above threshold proves every regional pixel exceeds it.
    Whole-grid per-tau max <= threshold proves zero exceedances at that tau.
    Otherwise the unknown regional count is bounded by 0 and B*region_cells.
    A single observed outside pixel tightens lower bounds without double counting.
    """
    threshold = math.log1p(rate)
    lower, upper = [0] * 32, [0] * 32
    any_lower = any_upper = 0
    for row in rows:
        all_above = row["qlog"]["min"] > threshold
        size = len(row["sample_ids"]) * REGION_CELLS[region]
        known = (witness is not None and witness["update"] == row["update"]
                 and witness["region"] == region)
        known_vals = witness["qlog_values"] if known else []
        for tau, whole_max in enumerate(row["qlog_per_tau_max"]):
            upper[tau] += size if whole_max > threshold else 0
            if all_above:
                lower[tau] += size
            elif known and known_vals[tau] > threshold:
                lower[tau] += 1
        any_upper += size if row["qlog"]["max"] > threshold else 0
        if all_above:
            any_lower += size
        elif known and any(v > threshold for v in known_vals):
            any_lower += 1
    return {"physical_threshold_mm_h": rate, "log1p_threshold": threshold,
            "comparison": "qlog > log1p(physical_threshold_mm_h)",
            "per_tau_pixel_exposure_counts": [
                {"tau_ordinal": t + 1, "tau": TAUS[t], **count_metric(lower[t], upper[t])}
                for t in range(32)],
            "pixel_tau_exposure_count": count_metric(sum(lower), sum(upper)),
            "spatial_pixel_exposure_count_any_tau": count_metric(any_lower, any_upper)}


def describe_cohort(rows, witness=None):
    whole = {"per_forward_global_max_distribution": distribution([r["qlog"]["max"] for r in rows]),
             "per_tau_forward_max_distributions": [
                 {"tau_ordinal": t + 1, "tau": TAUS[t],
                  **distribution([r["qlog_per_tau_max"][t] for r in rows])}
                 for t in range(32)]}
    active = witness if witness and any(r["update"] == witness["update"] for r in rows) else None
    regions = {}
    for region in REGION_CELLS:
        values = active["qlog_values"] if active and active["region"] == region else None
        per_tau = [
            {"tau_ordinal": t + 1, "tau": TAUS[t],
             **maximum_from_witness(whole["per_tau_forward_max_distributions"][t]["max"],
                                    values[t] if values else None)} for t in range(32)]
        maximum = maximum_from_witness(whole["per_forward_global_max_distribution"]["max"],
                                       max(values) if values else None)
        pixel_stats = {
            "p99": metric(upper=maximum["upper_bound"], reason="Regional full pixel qlog arrays/histograms were not saved."),
            "p99_9": metric(upper=maximum["upper_bound"], reason="Regional full pixel qlog arrays/histograms were not saved."),
            "max": maximum,
        }
        update_stats = {"n_forward_observations": len(rows)}
        for name in ("p99", "p99_9", "max"):
            if name == "max":
                update_stats[name] = maximum
            elif len(rows) == 1 and maximum["value"] is not None:
                update_stats[name] = metric(maximum["value"], lower=maximum["value"], upper=maximum["value"],
                                            reason="Singleton distribution of one regional forward maximum; not a pixel percentile.")
            else:
                update_stats[name] = metric(upper=whole["per_forward_global_max_distribution"][name],
                    reason="Regional forward maxima were not saved; corresponding whole-grid percentile is an upper bound.")
        regions[region] = {"cells_per_scene": REGION_CELLS[region],
            "spatial_pixel_exposures": sum(len(r["sample_ids"]) for r in rows) * REGION_CELLS[region],
            "per_tau_qlog_max": per_tau, "pooled_pixel_quantile_distribution": pixel_stats,
            "per_forward_region_max_distribution": update_stats,
            "exceedance_counts": [exceedance_bounds(rows, region, rate, active) for rate in RATES]}
    return {"n_forward_observations": len(rows), "n_scene_exposures": sum(len(r["sample_ids"]) for r in rows),
            "first_update": rows[0]["update"], "last_update": rows[-1]["update"],
            "regions": regions, "whole_grid_maxima_supplement": whole}


def csv_rows(report):
    for cohort_name, cohort in report["cohorts"].items():
        base = {"cohort": cohort_name, "n_forward_observations": cohort["n_forward_observations"]}
        for region, data in cohort["regions"].items():
            regional = {**base, "region": region, "unit": "log1p(mm/h)"}
            for name in ("pooled_pixel_quantile_distribution", "per_forward_region_max_distribution"):
                for stat in ("p99", "p99_9", "max"):
                    yield {**regional, "aggregation": name, "statistic": stat, **data[name][stat]}
            for tau in data["per_tau_qlog_max"]:
                yield {**regional, "aggregation": "pooled_pixels_per_tau", "statistic": "max", **tau}
            for threshold in data["exceedance_counts"]:
                counts = {**base, "region": region, "physical_threshold_mm_h": threshold["physical_threshold_mm_h"],
                          "log1p_threshold": threshold["log1p_threshold"], "statistic": "count_strictly_above"}
                for tau in threshold["per_tau_pixel_exposure_counts"]:
                    yield {**counts, "aggregation": "per_tau_pixel_exposures", "unit": "scene-pixel exposure", **tau}
                for name, unit in (("pixel_tau_exposure_count", "scene-pixel-tau exposure"),
                                   ("spatial_pixel_exposure_count_any_tau", "scene-pixel exposure (any tau)")):
                    yield {**counts, "aggregation": name, "unit": unit, **threshold[name]}
        # These recovered percentile distributions are NOT regional pixel distributions.
        whole = cohort["whole_grid_maxima_supplement"]
        for stat in ("p99", "p99_9", "max"):
            yield {**base, "region": "WHOLE_GRID_UNPARTITIONED", "aggregation": "per_forward_global_max_distribution",
                   "statistic": stat, "unit": "log1p(mm/h)", **metric(whole["per_forward_global_max_distribution"][stat])}
        for tau in whole["per_tau_forward_max_distributions"]:
            for stat in ("p99", "p99_9", "max"):
                yield {**base, "region": "WHOLE_GRID_UNPARTITIONED", "aggregation": "per_tau_forward_max_distribution",
                       "statistic": stat, "tau_ordinal": tau["tau_ordinal"], "tau": tau["tau"],
                       "unit": "log1p(mm/h)", **metric(tau[stat])}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def pin_inputs():
    refs = []
    for relative, expected in INPUT_SHAS.items():
        path = ROOT / relative
        actual = digest(path)
        if actual != expected:
            raise ValueError("Saved source SHA changed: " + relative)
        refs.append({"relative_path": relative, "bytes": path.stat().st_size, "sha256": actual})
    return refs


class SavedOnlyGuard:
    """After imports, restrict file opens to pinned local evidence/new outputs."""
    def __init__(self, inputs, outputs):
        self.inputs = {str(p.resolve()).casefold() for p in inputs}
        self.outputs = {str(p.resolve()).casefold() for p in outputs}
        self.events = []

    def __call__(self, event, args):
        if event == "open":
            path, mode, flags = args
            if isinstance(path, int):
                raise PermissionError("File-descriptor opens not permitted")
            key = str(Path(os.fsdecode(path)).resolve()).casefold()
            writing = bool((flags or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if key not in (self.outputs if writing else self.inputs | self.outputs):
                raise PermissionError("Only saved evidence and new diagnostic outputs may be opened: " + str(path))
            self.events.append({"path": str(Path(os.fsdecode(path)).resolve()), "access": "write" if writing else "read"})
        elif event.startswith(("subprocess.", "socket.")) or event in ("os.system", "os.remove", "os.rename", "os.rmdir"):
            raise PermissionError("No subprocess/network/deletion in saved-only diagnostics")


def write_json(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"),
                        help="Fresh run identifier (default: actual UTC); existing outputs cannot be overwritten")
    args = parser.parse_args()
    if not args.run_id.startswith("run_") or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in args.run_id):
        raise ValueError("Invalid new run identifier")
    output = ROOT / "docs/saved_quantile_extremes/runs" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    own_source = Path(__file__).resolve()
    guard = SavedOnlyGuard([ROOT / p for p in INPUT_SHAS] + [own_source], [output / n for n in OUTPUT_NAMES])
    sys.addaudithook(guard)
    before = pin_inputs()
    script_sha = digest(own_source)
    observer_text = (ROOT / (SOURCE + "/readonly_closeout/executed_sources/observer.py.txt")).read_text(encoding="utf-8")
    mask_text = (ROOT / MASK_SOURCE).read_text(encoding="utf-8")
    if ("qlog.amax(dim=(0,2,3))" not in observer_text or "(32,100,100)" not in observer_text
            or "target = full[10:110, 20:120]" not in mask_text or "int(target.sum()) != 3430" not in mask_text):
        raise ValueError("Saved observation/grid/mask execution semantics mismatch")
    rows = load_rows(ROOT / (SOURCE + "/replay_observations.jsonl"))
    failure = json.loads((ROOT / (SOURCE + "/failing_tensor_diagnostics.json")).read_text(encoding="utf-8"))
    witness = validate_witness(failure, rows)
    identity = json.loads((ROOT / (SOURCE + "/replay_identity_preflight.json")).read_text(encoding="utf-8"))
    cohorts = {"SUCCESSFUL_UPDATES_ONLY": describe_cohort(rows[:-1]),
               "FAILING_FORWARD_ONLY": describe_cohort(rows[-1:], witness),
               "SUCCESSFUL_UPDATES_PLUS_FAILING_FORWARD": describe_cohort(rows, witness)}
    source_unchanged = pin_inputs() == before
    if not source_unchanged:
        raise ValueError("Saved source changed during diagnostics")
    report = {
        "schema_version": "1.0", "utc": datetime.now(timezone.utc).isoformat(), "baseline_commit": BASELINE,
        "scope": "DESCRIPTIVE_SAVED_OBSERVATIONS_ONLY_NO_NEW_FORWARD",
        "status": "PARTIAL_RECOVERY_SAVED_OBSERVATIONS_ONLY", "all_requested_regional_statistics_recoverable": False,
        "summary_zh": "合并 8625 次成功 update 与 1 次失败 forward 后，云南外 32 个 tau 最大值可精确恢复；云南内最大值、区域像元 p99/p99.9 和精确超阈值计数不可恢复。",
        "limitations": [
            "Saved records contain whole-grid extrema/means/std/medians and one outside pixel; no full spatial qlog arrays or regional histograms.",
            "The 8625 successful observations cover updates 41913..50537, not every successful update of the original training run.",
            "Null is unavailable, never zero. Bounds are not measured counts or regional percentile estimates.",
            "Per-forward maximum percentiles describe maxima across forwards, not percentiles across pixels/taus.",
            "Known outside extreme does not establish absence of extreme values inside Yunnan.",
        ],
        "definitions": {
            "requested_percentile_views": "Both pooled pixel-quantile values and per-forward regional maxima; recoverable parts only.",
            "percentile_method": "Linear empirical quantile, h=(n-1)*p; p99=p=.99, p99.9=p=.999.",
            "qlog_unit": "log1p(mm/h)", "tau_order": "(ordinal-0.5)/32, ordinal 1..32",
            "grid_shape": [100, 100], "batch_size": 2, "grid_source": "Saved executed observer.py.txt and masks.py.txt; no mask/raw reopen.",
            "pooled_pixel_quantile_distribution": "All scene-pixel-tau exposures in the region over the selected forwards.",
            "per_forward_region_max_distribution": "One maximum over all regional pixels/taus/batch elements per saved forward.",
            "outside": "Complement of frozen Yunnan evaluation mask within the 100x100 target grid.",
            "count_units": "Per-tau scene-pixel exposures; their sum is scene-pixel-tau exposures. Any-tau counts a spatial pixel once per scene/forward. Repeated scenes are not deduplicated across forwards.",
            "count_bounds_method": "Global min > log1p(rate) proves all regional pixels exceed; per-tau whole max <= log1p(rate) proves zero; otherwise count upper bound is batch*regional_cells. The saved outside witness supplies a lower bound without double counting.",
            "threshold_purpose": "Descriptive diagnostics only; not exclusion criteria, training rules, QC or scientific thresholds.",
            "threshold_operator": "strictly greater than", "thresholds_mm_h": list(RATES),
            "whole_grid_supplement": "Unpartitioned distributions of saved per-forward maxima. No regional pixel percentile is inferred from them.",
        },
        "provenance": {"inputs": before, "generator_relative_path": own_source.relative_to(ROOT).as_posix(),
                       "generator_sha256": script_sha,
                       "frozen_protocol_sha256_record_only": identity["checkpoint_identity"]["protocol_sha256"],
                       "frozen_normalization_sha256_record_only": identity["checkpoint_identity"]["normalization_sha256"]},
        "witness": witness,
        "outside_per_tau_max_proof": [
            {"tau_ordinal": t + 1, "tau": TAUS[t], "outside_witness_value": witness["qlog_values"][t],
             "whole_grid_cohort_max": cohorts["SUCCESSFUL_UPDATES_PLUS_FAILING_FORWARD"]["whole_grid_maxima_supplement"]["per_tau_forward_max_distributions"][t]["max"],
             "exact_equality": witness["qlog_values"][t] == cohorts["SUCCESSFUL_UPDATES_PLUS_FAILING_FORWARD"]["whole_grid_maxima_supplement"]["per_tau_forward_max_distributions"][t]["max"]}
            for t in range(32)],
        "cohorts": cohorts,
        "execution": {"FORWARD_CALLS": 0, "BACKWARD_CALLS": 0, "OPTIMIZER_STEPS": 0,
                      "MODEL_PARAMETERS_UPDATED": False, "RAW_SOURCE_OPENS": 0, "2025_RAW_ACCESS": 0,
                      "CHECKPOINT_OPENS": 0, "TORCH_IMPORTED": "torch" in sys.modules,
                      "saved_inputs_byte_identical": source_unchanged,
                      "historical_artifacts_modified": False, "numerical_or_training_rules_changed": False,
                      "read_guard": "Pinned saved local inputs and new outputs only; no raw/checkpoint/network/subprocess opens."},
    }
    if report["execution"]["TORCH_IMPORTED"]:
        raise RuntimeError("Saved-only process must not import torch")
    write_json(output / OUTPUT_NAMES[0], report)
    columns = ("cohort", "region", "aggregation", "statistic", "tau_ordinal", "tau",
               "physical_threshold_mm_h", "log1p_threshold", "value", "status", "lower_bound", "upper_bound",
               "unit", "n_forward_observations", "reason")
    records = list(csv_rows(report))
    with (output / OUTPUT_NAMES[1]).open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)
    # Read back both new artifacts and reconcile CSV exactly with JSON-derived rows.
    loaded = json.loads((output / OUTPUT_NAMES[0]).read_text(encoding="utf-8"))
    with (output / OUTPUT_NAMES[1]).open(encoding="utf-8", newline="") as handle:
        actual_csv = list(csv.DictReader(handle))
    expected_csv = [{c: "" if r.get(c) is None else str(r.get(c)) for c in columns} for r in records]
    if loaded != report or actual_csv != expected_csv:
        raise ValueError("JSON/CSV round-trip reconciliation failed")
    after = pin_inputs()
    if after != before:
        raise ValueError("Saved source changed during output verification")
    artifacts = [{"relative_path": (output / n).relative_to(ROOT).as_posix(),
                  "bytes": (output / n).stat().st_size, "sha256": digest(output / n)} for n in OUTPUT_NAMES[:2]]
    write_json(output / OUTPUT_NAMES[2], {"utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": BASELINE, "status": report["status"], "generator_sha256": script_sha,
        "inputs_before": before, "inputs_after": after, "all_inputs_unchanged": True,
        "artifacts": artifacts, "csv_data_rows": len(records), "json_csv_reconciliation_pass": True,
        "read_write_events_before_manifest_write": guard.events.copy(), "execution": report["execution"]})
    print(json.dumps({"run": str(output), "status": report["status"], "csv_rows": len(records),
                      "outside_global_qlog_max": cohorts["SUCCESSFUL_UPDATES_PLUS_FAILING_FORWARD"]["regions"]["YUNNAN_OUTSIDE"]["pooled_pixel_quantile_distribution"]["max"]["value"]}))


if __name__ == "__main__":
    main()
