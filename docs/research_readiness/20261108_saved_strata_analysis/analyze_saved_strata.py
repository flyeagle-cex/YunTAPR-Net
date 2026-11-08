"""Decompose four saved 2024 Dev summaries, without loading a model or array."""

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SOURCES = {
    "E0_B7": (
        "docs/research_readiness/20261025/evidence/b7_b8_terminal_20261028.json",
        399020,
        "196b5efb6008cb0590ed73acf91e3daa1037851e49d1d433bc1e576f6f3d2729",
    ),
    "E0_B8": (
        "docs/research_readiness/20261025/evidence/b8_recovery_completion_20261028.json",
        302359,
        "3fb57ebd6301d57598bca0f1bdf903160bb0f54acb3b82225616dd8a47fe0ab3",
    ),
    "E2": (
        "docs/research_readiness/20261108_lambda2_recovery/RESULTS.json",
        9527,
        "1d351fe3f8fc5c5dd6fc7f8d223dd52a4d79c2ffe629d3fe644bb76b5b64bdaf",
    ),
}
BOUNDS = [(0.1, 1.0), (1.0, 5.0), (5.0, 10.0), (10.0, 20.0),
          (20.0, 30.0), (30.0, 50.0), (50.0, None)]
COUNTS = [246473, 135686, 20145, 4799, 564, 147, 6]
N_RAIN = 407820


def require(condition, message):
    if not condition:
        raise ValueError(message)


def aggregate(rows):
    count = sum(row["n_rain"] for row in rows)
    covered = sum(row["q32_covered"] for row in rows)
    return {
        "n_rain": count,
        "conditional_pinball": math.fsum(row["n_rain"] * row["conditional_pinball"] for row in rows) / count,
        "q32_covered": covered,
        "q32_coverage": covered / count,
    }


def analyze(repo):
    data = {}
    identities = {}
    for role, (relative, expected_bytes, expected_sha) in SOURCES.items():
        payload = (repo / relative).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        require(len(payload) == expected_bytes and digest == expected_sha, f"Source identity changed: {role}")
        data[role] = json.loads(payload.decode("utf-8", errors="strict"))
        identities[role] = {"path": relative, "bytes": len(payload), "sha256": digest}

    current = data["E2"]
    require(current["seed"] == 2029 and current["endpoint"] == "FIXED_EPOCH_9_LAST", "E2 identity changed")
    require(data["E0_B7"]["data_version"] == data["E0_B8"]["data_version"], "Historical data identities differ")
    cells = {}
    reconciliation = {}
    for model in ["B7", "B8"]:
        old = data["E0_" + model]
        require(old["endpoint"] == "FIXED_EPOCH_9_LAST", "Historical endpoint changed")
        old_summary = old["endpoint_groups"][model]["all"]["summary"]
        require((old_summary["scenes"], old_summary["n_valid"], old_summary["n_rain"]) == (963, 3303090, N_RAIN), "Historical population differs")
        require(old["tail_diagnostics"][model]["nominal_q32"] == 0.984375, "Quantile level changed")
        cells[model] = {
            "E0": old["tail_diagnostics"][model]["strata"],
            "E2": current["E2_tail_diagnostics"][model]["strata"],
        }
        reconciliation[model] = {}
        for loss, rows in cells[model].items():
            require([(row["lower"], row["upper"]) for row in rows] == BOUNDS, "Rain boundaries differ")
            require([row["n_rain"] for row in rows] == COUNTS, "Rain population differs")
            for row in rows:
                require(isinstance(row["q32_covered"], int) and 0 <= row["q32_covered"] <= row["n_rain"], "Invalid coverage count")
                require(math.isfinite(row["conditional_pinball"]) and row["conditional_pinball"] >= 0, "Invalid saved loss")
                require(abs(row["q32_coverage"] - row["q32_covered"] / row["n_rain"]) < 1e-12, "Saved coverage disagrees with count")
            total = aggregate(rows)
            saved = current["values"][model][loss]
            pin_residual = total["conditional_pinball"] - saved["conditional_pinball"]
            coverage_residual = total["q32_coverage"] - saved["q32_coverage"]
            require(abs(pin_residual) < 1e-10 and abs(coverage_residual) < 1e-12, "Saved strata do not recover overall metrics")
            if loss == "E0":
                require(saved["conditional_pinball"] == old_summary["conditional_pinball"], "E0 metric version differs")
            reconciliation[model][loss] = {"reconstructed": total, "pinball_residual": pin_residual, "coverage_residual": coverage_residual}

    table = []
    for index, (lower, upper) in enumerate(BOUNDS):
        row = {"lower_exclusive": lower, "upper_inclusive": upper, "n_rain": COUNTS[index], "wet_population_percent": COUNTS[index] / N_RAIN * 100, "cells": {}, "E2_minus_E0": {}}
        for model in ["B7", "B8"]:
            old = cells[model]["E0"][index]
            new = cells[model]["E2"][index]
            for loss, item in [("E0", old), ("E2", new)]:
                row["cells"][model + "_" + loss] = {key: item[key] for key in ["conditional_pinball", "q32_covered", "q32_coverage"]}
            delta = new["conditional_pinball"] - old["conditional_pinball"]
            row["E2_minus_E0"][model] = {
                "conditional_pinball": delta,
                "conditional_pinball_relative_percent": delta / old["conditional_pinball"] * 100,
                "overall_pinball_contribution": COUNTS[index] / N_RAIN * delta,
                "q32_covered_change": new["q32_covered"] - old["q32_covered"],
                "overall_q32_coverage_change_contribution": (new["q32_covered"] - old["q32_covered"]) / N_RAIN,
            }
        table.append(row)

    decomposition = {}
    for model in ["B7", "B8"]:
        contributions = [row["E2_minus_E0"][model]["overall_pinball_contribution"] for row in table]
        summed = math.fsum(contributions)
        saved_delta = current["lambda2_minus_lambda1"][model]["conditional_pinball"]
        require(abs(summed - saved_delta) < 1e-10, "Changes do not reconcile")
        groups = {}
        for name, indices in [("0.1_lt_R_le_5", range(2)), ("5_lt_R_le_20", range(2, 4)), ("R_gt_20", range(4, 7))]:
            old = aggregate([cells[model]["E0"][i] for i in indices])
            new = aggregate([cells[model]["E2"][i] for i in indices])
            delta = new["conditional_pinball"] - old["conditional_pinball"]
            groups[name] = {
                "E0": old, "E2": new,
                "pinball_change": delta,
                "pinball_relative_change_percent": delta / old["conditional_pinball"] * 100,
                "overall_pinball_contribution": math.fsum(contributions[i] for i in indices),
            }
        decomposition[model] = {
            "seven_bin_contribution_sum": summed,
            "saved_overall_change": saved_delta,
            "residual": summed - saved_delta,
            "groups": groups,
            "strong_bin_pinball_all_worsen": all(row["E2_minus_E0"][model]["conditional_pinball"] > 0 for row in table[4:]),
            "q32_covered_change_total": sum(row["E2_minus_E0"][model]["q32_covered_change"] for row in table),
            "q32_covered_change_1_to_5": table[1]["E2_minus_E0"][model]["q32_covered_change"],
        }

    return {
        "task": "SAVED_FOUR_CELL_SEVEN_BIN_DECOMPOSITION_20261108",
        "authorization": "Researcher message 开始吧 following LIVE.23 bounded three-JSON proposal",
        "scope": "2024 Development, Seed2029, fixed E9; statistics of existing summaries only",
        "input_identities": identities,
        "semantics": {
            "rate_unit": "mm/h",
            "rain_bin_rule": "lower < R <= upper; final upper unbounded",
            "conditional_pinball": "mean over 32 fixed tau log1p(R) Pinball losses, then mean over rainy valid pixel-times in the stratum",
            "q32_coverage": "count(log1p(R) <= qlog32) / stratum n_rain, conditional on observed rainfall bin; not POD or probability calibration",
            "tau32": 0.984375,
            "aggregation": "n-weighted rainy pixel-time means; not a scene mean or independent event mean",
            "evidence_code": ["src/yuntapr/experimental/research_readiness/tail_diagnostics.py", "src/yuntapr/experimental/phase_b_v2_ablations/pinball.py"],
        },
        "population": {
            "scenes": 963, "n_valid": 3303090, "n_rain": N_RAIN,
            "R_gt20": 717, "R_gt50": 6,
            "R_gt20_wet_population_percent": 717 / N_RAIN * 100,
            "historical_population_sha256": data["E0_B7"]["data_version"]["population_sha256"],
            "current_evidence": "Direct bin boundary/count equality and old data_version equality. E2 whole-scene/mask/partition identity inherited from prior terminal cross-review; equal counts alone do not prove alignment.",
            "independent_event_count": "NOT_IDENTIFIED",
            "four_cell_scene_sensitivity": "NOT_VERIFIED_E0_ACCESSIBLE_LOCATION_NOT_CONFIRMED",
        },
        "four_cell_rain_table": table,
        "overall_reconciliation": reconciliation,
        "loss_change_decomposition": decomposition,
        "existing_overall_guardrails": current["values"],
        "interpretation": {
            "verified": ["Both architectures have higher mean log-space 32-node Pinball in all three R>20 bins with E2.", "B7 overall improvement coexists with strong-bin degradation.", "B8 strong-bin q32 coverage increases while strong-bin mean Pinball worsens.", "Overall q32 coverage gains concentrate in the 1<R<=5 bin."],
            "not_identified": ["Training cause or gradient conflict", "Terrain mechanism or DTFM functional failure", "Cross-seed stability or independent-event generalization", "Per-tau loss changes or optimal tau weights", "A/B/C, P20, strong-rain AUROC/AP, MAE/RMSE/Bias from these three inputs"],
            "candidate_hypothesis_PROPOSED": "A separately defined upper-quantile-node loss emphasis may improve conditional strong-rain amplitude more directly than raising the whole conditional task weight. Fixed positive tau-only weights preserve the ideal per-node quantile target; finite shared-network tradeoffs and wet-population dominance still require validation. No weights, architecture, new training or success tolerance selected here.",
        },
        "execution": {"optimizer_updates": 0, "new_inference": 0, "new_model_evaluation": 0, "npz_reads": 0, "checkpoint_reads": 0, "raw_source_reads": 0, "final_test_2025_access": 0, "scientific_input_json_count": 3},
        "states": {"engineering": "PASS_FOR_BOUNDED_STATISTICS", "science": "NOT_VERIFIED", "researcher_knowledge": "NOT_ASSESSED"},
    }


if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[3]
    destination = Path(__file__).with_name("RESULTS.json")
    require(not destination.exists(), "Preserve previous output; use a reviewed new task path for another run")
    result = analyze(repo)
    result["completed_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"result": result["states"], "population": result["population"], "decomposition": result["loss_change_decomposition"]}, ensure_ascii=False, indent=2))
