"""Derive fixed-cutoff occurrence scores from two SHA-bound saved reports.

The ten saved reliability bins use searchsorted([.1, ..., .9], p,
side='right'). Bins 5 through 9 therefore retain exact contingency counts
for the declared p_occ >= .5 rule. No individual predictions are needed.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_REPORT_SHA256 = {
    "CONTROL_E0": "ff46da36310725f185c270061731e0afd31c513c797223f387890ff93a5dc060",
    "CANDIDATE_COSINE9": "e4c030b305904a7a5e0b009460d75ab13f69d31b2f7bd6aa1d824eea660acee1",
}
EXPECTED_RESULTS_SHA256 = "b4420b1388d31f6bc86eeaa088d04ef4ccea2c5ebde18ef2cf7dd271f63eb3ae"
EXPECTED_N_VALID = 3303090
EXPECTED_N_RAIN = 407820
EXPECTED_N_SCENES = 963
METRIC_FIELDS = {
    "brier": "brier",
    "occurrence_ap": "average_precision",
    "occurrence_auroc": "auroc",
}


def read_bound_json(path, expected_sha256):
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"Saved input SHA256 mismatch for {path.name}")
    return json.loads(raw), {"bytes": len(raw), "sha256": actual}


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Counts must be nonnegative integers")
    return value


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Finite numeric statistic required")
    return value


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def contingency_from_summary(summary):
    bins = summary["reliability"]
    if not isinstance(bins, list) or len(bins) != 10:
        raise ValueError("Exactly ten saved reliability bins required")
    n_valid = count(summary["n_valid"])
    n_rain = count(summary["n_rain"])
    total = positive = predicted_total = true_positive = 0
    for index, row in enumerate(bins):
        n = count(row["n"])
        rain = count(row["rain"])
        probability_sum = number(row["probability_sum"])
        if rain > n:
            raise ValueError("Rain count exceeds bin count")
        if not index * n / 10 <= probability_sum <= (index + 1) * n / 10:
            raise ValueError("Probability sum lies outside its saved bin")
        if n:
            if not math.isclose(number(row["mean_probability"]), probability_sum / n,
                                rel_tol=1e-12, abs_tol=1e-15):
                raise ValueError("Saved bin mean probability differs")
            if not math.isclose(number(row["frequency"]), rain / n,
                                rel_tol=1e-12, abs_tol=1e-15):
                raise ValueError("Saved bin frequency differs")
        elif row["mean_probability"] is not None or row["frequency"] is not None:
            raise ValueError("Empty-bin statistics must be null")
        total += n
        positive += rain
        if index >= 5:
            predicted_total += n
            true_positive += rain
    if (total, positive) != (n_valid, n_rain):
        raise ValueError("Saved bins and population totals disagree")
    return {
        "TP": true_positive,
        "FP": predicted_total - true_positive,
        "FN": n_rain - true_positive,
        "TN": n_valid - n_rain - predicted_total + true_positive,
    }


def classification_metrics(table):
    tp, fp, fn, tn = (count(table[key]) for key in ("TP", "FP", "FN", "TN"))
    population = tp + fp + fn + tn
    random_hits_numerator = (tp + fp) * (tp + fn)
    return {
        "POD": ratio(tp, tp + fn),
        "FAR": ratio(fp, tp + fp),
        "CSI": ratio(tp, tp + fp + fn),
        "Precision": ratio(tp, tp + fp),
        "F1": ratio(2 * tp, 2 * tp + fp + fn),
        "ETS": ratio(tp * population - random_hits_numerator,
                     (tp + fp + fn) * population - random_hits_numerator),
        "HSS": ratio(2 * (tp * tn - fp * fn),
                     (tp + fn) * (fn + tn) + (tp + fp) * (fp + tn)),
        "frequency_bias": ratio(tp + fp, tp + fn),
    }


def build_result(control_path, candidate_path, results_path):
    saved_results, results_identity = read_bound_json(results_path, EXPECTED_RESULTS_SHA256)
    references = {row["metric"]: row for row in saved_results["metrics"]}
    arms = {}
    reports = {}
    for name, path, comparison_field in (
        ("CONTROL_E0", control_path, "control"),
        ("CANDIDATE_COSINE9", candidate_path, "candidate"),
    ):
        report, identity = read_bound_json(path, EXPECTED_REPORT_SHA256[name])
        group = report["groups"]["all"]
        summary = group["summary"]
        if not group["complete"] or report["scope"] != "2024_DEVELOPMENT_FIXED_F006_RETROSPECTIVE":
            raise ValueError("Complete frozen 2024 Development report required")
        if (summary["scenes"], summary["n_valid"], summary["n_rain"]) != (
                EXPECTED_N_SCENES, EXPECTED_N_VALID, EXPECTED_N_RAIN):
            raise ValueError("Unexpected evaluation population")
        for metric, field in METRIC_FIELDS.items():
            if summary[field] != references[metric][comparison_field]:
                raise ValueError(f"Saved result metric identity differs: {metric}")
        table = contingency_from_summary(summary)
        arms[name] = {"input_identity": identity, "contingency": table,
                      "metrics": classification_metrics(table)}
        reports[name] = report
    control = reports["CONTROL_E0"]
    candidate = reports["CANDIDATE_COSINE9"]
    for field in ("source_identity", "population_ids_sha256", "partition_sha256"):
        if control[field] != candidate[field]:
            raise ValueError(f"Paired report identity differs: {field}")
    if control["groups"]["all"]["ids_sha"] != candidate["groups"]["all"]["ids_sha"]:
        raise ValueError("Paired all-group scene identity differs")
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "SAVED_2024_DEVELOPMENT_E9_OCCURRENCE_FIXED_CUTOFF_ARITHMETIC",
        "truth_event": "float32(rate_mm_h) > float32(0.1)",
        "prediction_event": "native saved occurrence probability >= 0.5",
        "cutoff_selection": "FIXED_0_5_NO_DEVELOPMENT_OPTIMIZATION",
        "population": {"scenes": EXPECTED_N_SCENES, "n_valid": EXPECTED_N_VALID,
                       "n_rain": EXPECTED_N_RAIN, "unit": "PIXEL_TIMES"},
        "source_results_identity": results_identity,
        "arms": arms,
        "candidate_minus_control": {
            metric: (arms["CANDIDATE_COSINE9"]["metrics"][metric]
                     - arms["CONTROL_E0"]["metrics"][metric])
            if (arms["CANDIDATE_COSINE9"]["metrics"][metric] is not None
                and arms["CONTROL_E0"]["metrics"][metric] is not None) else None
            for metric in arms["CONTROL_E0"]["metrics"]
        },
        "implementation": {"script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                           "bin_semantics_source": "src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py:75"},
        "engineering_status": "PASS",
        "scientific_status": "NOT_VERIFIED",
        "researcher_knowledge": "NOT_ASSESSED",
        "evidence_grade": "DIRECT_VERIFIED",
        "evidence_scope": "SAVED_SUMMARY_ARITHMETIC_AND_INPUT_FILE_IDENTITIES",
        "limitations": ["ONE_SEED2029_REUSED_2024_DEVELOPMENT",
                        "FIXED_PROBABILITY_CUTOFF_DECLARED_AFTER_ORIGINAL_TRAINING",
                        "R_GT20_CONTINGENCY_AND_PHYSICAL_POINT_ERRORS_UNAVAILABLE_FROM_THESE_SUMMARIES"],
    }


def self_test():
    rows = []
    for index in range(10):
        rows.append({"n": 4, "rain": index % 3, "probability_sum": 4 * (index + .5) / 10,
                     "mean_probability": (index + .5) / 10, "frequency": (index % 3) / 4})
    summary = {"n_valid": 40, "n_rain": 9, "reliability": rows}
    table = contingency_from_summary(summary)
    assert table == {"TP": 5, "FP": 15, "FN": 4, "TN": 16}
    values = classification_metrics({"TP": 3, "FP": 1, "FN": 2, "TN": 4})
    expected = {"POD": 3 / 5, "FAR": 1 / 4, "CSI": 1 / 2, "Precision": 3 / 4,
                "F1": 2 / 3, "ETS": 1 / 4, "HSS": 2 / 5, "frequency_bias": 4 / 5}
    assert values == expected
    zero = classification_metrics({"TP": 0, "FP": 0, "FN": 2, "TN": 8})
    assert zero["FAR"] is None and zero["Precision"] is None and zero["POD"] == 0
    for invalid in (-1, True, 1.0):
        try:
            count(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid count accepted")
    print(json.dumps({"self_test": "PASS", "scientific_inputs_read": 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    paths = (args.control, args.candidate, args.results, args.output)
    if args.self_test:
        if any(path is not None for path in paths):
            parser.error("Self-test cannot receive scientific input or output paths")
        self_test()
        return
    if any(path is None for path in paths):
        parser.error("Explicit --control, --candidate, --results and --output are required")
    if args.output.exists():
        raise FileExistsError("Output already exists")
    result = build_result(args.control, args.candidate, args.results)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": result["engineering_status"], "arms": result["arms"]},
                     ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
