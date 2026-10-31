"""Prepare an evidence-bound diagnostic proposal from public saved records only.

Reads an explicit list of Git blobs, never model files, meteorological data,
private locators, or a filesystem path taken from a source record. Output must
be new. This program cannot start inference, training, or evaluation.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
BASE = "7c19b9d36bc73b998fcf72b9cc630989f7e3b324"
PREFIX = "docs/research_readiness/20261025/evidence/"
AUDIT = "docs/research_readiness/20261031_extreme_precipitation_audit/"
JSON_NAMES = (
    "b2_completion_and_paired_evidence.json",
    "b3_b4_full_endpoint_metrics_20261027.json",
    "b3_b4_three_seed_completion.json",
    "b5_b6_completion_and_paired_evidence.json",
    "b7_b8_terminal_20261028.json",
    "b7_b8_three_seed_completion_20261029.json",
    "b8_recovery_completion_20261028.json",
    "dote_control_completion_20261029.json",
    "dote_control_three_seed_completion_20261029.json",
    "dote_physical_control_completion_20261030.json",
    "metric_completion_candidate_started_20261030.json",
    "compact_stage_comparison_delivery_20261031.json",
    "b7_b8_training_proposal.json",
)
ALLOWED = {
    "EXPERIMENT_MATRIX.csv", "METRICS.csv", "EVIDENCE_INDEX.md",
    "docs/research_progress/evidence/experiments.json",
    AUDIT + "EXTREME_PRECIPITATION_AUDIT.csv",
    AUDIT + "EXTREME_PRECIPITATION_AUDIT.md",
    "config/science_v2/quantile_head_v2_frozen_v1.json",
    *(PREFIX + n for n in JSON_NAMES),
}
CORE_METRICS = ("brier", "auroc", "average_precision", "conditional_pinball", "q32_coverage")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


class SavedSources:
    def __init__(self):
        self.payloads = {}
        self.parsed = {}

    def read(self, path):
        if path not in ALLOWED:
            raise PermissionError("Source outside the explicit public-statistics whitelist")
        if path not in self.payloads:
            self.payloads[path] = git("show", f"{BASE}:{path}")
        return self.payloads[path]

    def json(self, path):
        if path not in self.parsed:
            self.parsed[path] = json.loads(self.read(path).decode("utf-8-sig"))
        return self.parsed[path]

    def csv(self, path):
        return list(csv.DictReader(io.StringIO(self.read(path).decode("utf-8-sig"))))


def pointer(value, path):
    for token in path.lstrip("/").split("/"):
        key = token.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def close(a, b):
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=1e-14)


def prepare():
    source = SavedSources()
    matrix = source.csv("EXPERIMENT_MATRIX.csv")
    metrics = source.csv("METRICS.csv")
    extreme = source.csv(AUDIT + "EXTREME_PRECIPITATION_AUDIT.csv")
    lookup = {(r["experiment_id"], r["group"], r["metric"]): float(r["value"])
              for r in metrics if r["record_type"] in ("RAW_ENDPOINT", "OFFLINE_DERIVED")
              and r["value"] != ""}
    pointer_checks = 0
    for row in metrics:
        if (row["record_type"] == "RAW_ENDPOINT" and row["group"] == "all"
                and row["metric"] in CORE_METRICS):
            actual = pointer(source.json(row["source_file"]), row["source_pointer"])
            if not close(actual, row["value"]):
                raise ValueError("Saved core value disagrees with its source pointer")
            pointer_checks += 1

    normal_pairs, special_pairs, indexed_references = 0, 0, 0
    collision_rows = []
    perp_path = PREFIX + "dote_physical_control_completion_20261030.json"
    perp = source.json(perp_path)
    for row in metrics:
        if row["record_type"] != "PAIRED_DELTA":
            continue
        key = (row["experiment_id"], row["group"], row["metric"])
        if row["reference_value"]:
            expected = lookup[key] - float(row["reference_value"])
            refkey = (row["reference_experiment_id"], row["group"], row["metric"])
            if refkey in lookup:
                if not close(lookup[refkey], row["reference_value"]):
                    raise ValueError("Saved reference disagrees with the endpoint index")
                indexed_references += 1
            normal_pairs += 1
        else:
            if row["comparison"] != "B7_REAL_MINUS_B7_PERP_GRADIENT":
                raise ValueError("Unexplained empty reference in a saved comparison")
            if row["source_pointer"].startswith("/summary/group_deltas/"):
                left = ("B7__E0__s2029__f006__dynamic", row["group"], row["metric"])
                expected = lookup[left] - lookup[key]
            else:
                pair = pointer(perp, "/".join(row["source_pointer"].split("/")[:-2]))
                expected = pair["B7"][row["metric"]] - pair["B7_PERP_GRADIENT"][row["metric"]]
            special_pairs += 1
            if row["experiment_id"] == row["reference_experiment_id"]:
                collision_rows.append(dict(group=row["group"], metric=row["metric"],
                                           source_pointer=row["source_pointer"]))
        if not close(expected, row["value"]):
            raise ValueError("Saved paired delta fails independent subtraction")
    if (pointer_checks, normal_pairs, special_pairs, len(collision_rows)) != (178, 5737, 65, 65):
        raise ValueError("Unexpected baseline coverage; revise the proposal rather than silently continuing")

    abc = [r for r in extreme if r["record_type"] == "CLASSIFICATION"
           and r["method"] in ("A", "B", "C") and r["threshold_mm_h"] == "20.0"]
    if len(abc) != 27 or len({(r["model"], r["seed"], r["method"]) for r in abc}) != 27:
        raise ValueError("Nine-model / three-method saved classification coverage changed")
    for row in abc:
        if (row["TP"], row["FP"], row["FN"], row["TN"]) != ("0", "0", "717", "3302373"):
            raise ValueError("Saved >20 contingency counts changed")
        if float(row["CSI"]) or float(row["POD"]) or row["FAR"]:
            raise ValueError("Zero-denominator or detection semantics changed")

    checkpoint_rows = [r for r in extreme if r["record_type"] == "CHECKPOINT_CONFIG"]
    model_manifest = []
    for row in sorted(checkpoint_rows, key=lambda r: (r["model"], int(r["seed"]))):
        matches = [r for r in matrix if r["model_id"] == row["model"]
                   and r["seed"] == row["seed"] and r["loss_arm"] == "E0"
                   and r["status"] == "COMPLETE_TRAIN_AND_DEV_EVALUATION"]
        if len(matches) != 1 or matches[0]["checkpoint_reference"] != row["checkpoint_sha256"]:
            raise ValueError("Checkpoint identity is not uniquely bound to the completed matrix row")
        entry = matches[0]
        if (entry["train_scenes"], entry["dev_scenes"], entry["epochs"]) != ("959", "963", "9"):
            raise ValueError("Common population or fixed endpoint changed")
        size = [r for r in extreme if r["record_type"] == "FILE"
                and r["metric"] == "FIXED_E9_CHECKPOINT_BYTES_ONLY"
                and r["file_sha256"] == row["checkpoint_sha256"]]
        if len(size) != 1:
            raise ValueError("No unique inherited checkpoint-size receipt")
        model_manifest.append(dict(model=row["model"], seed=int(row["seed"]),
                                   experiment_id=entry["experiment_id"],
                                   checkpoint_sha256=row["checkpoint_sha256"],
                                   inherited_checkpoint_bytes=int(size[0]["value"]),
                                   training_execution_commit=entry["executed_commit"],
                                   effective_updates=4320))
    if len(model_manifest) != 9:
        raise ValueError("Only the existing nine-model core may enter this proposal")

    backfill = source.json(PREFIX + "metric_completion_candidate_started_20261030.json")["metrics"]
    if len(backfill["results"]) != 19 or not all(
            r["status"] == "COMPLETE" and r["gate"]["passed"] for r in backfill["results"]):
        raise ValueError("Inherited 19-result backfill gate is incomplete")

    evidence_text = source.read("EVIDENCE_INDEX.md").decode("utf-8-sig")
    obsolete_probe_row = "|B7_PERP_GRADIENT|2029|`NOT_AVAILABLE_NO_TRAINING`|`NOT_EXECUTED`|" in evidence_text
    scientific = source.json(PREFIX + "b7_b8_training_proposal.json")
    train_label = scientific["source_scope_summary"]["Train"]["by_kind"]["IMERG"]
    development = scientific["source_scope_summary"]["Development"]
    weather = 9 * development["bytes_per_pass"]
    instances = 9 * development["file_count"]
    static = 6 * 312828
    label_and_mask = train_label["bytes"] + 20916
    checkpoints = sum(m["inherited_checkpoint_bytes"] for m in model_manifest)
    if (weather, instances) != (239753278008, 71550):
        raise ValueError("Historical one-pass source reference changed")

    config = dict(
        protocol_id="YUNTAPR_EXTREME_DIAGNOSTIC_V1_20261031",
        status="PREPARED_METHOD_DRAFT_NO_NEW_COMPUTE_AUTHORIZATION",
        preparation_authorized=True,
        scientific_method_frozen=False,
        inference_authorized=False,
        training_authorized=False,
        budget_approved=False,
        final_2025_access=False,
        baseline_commit=BASE,
        purpose="Distinguish point conversion, conditional-tail, and observation/event evidence gaps without training",
        models=model_manifest,
        population=dict(train_year=2023, dev_year=2024, train_scenes=959, dev_scenes=963,
                        dev_pixel_times=3303090, dev_rain_pixel_times=407820,
                        source_identity_sha256="2f2cc75cfb6c209fd8195d3419207216c5c3f2a4fc8315b40a1d77cc537dedb8",
                        mask_sha256="9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef",
                        label_window="[T,T+30min)", analysis="T+30min", utc_hours=[0, 6, 12, 18],
                        mode="f006_retrospective_not_operational_availability_proof"),
        proposed_methods=dict(
            main_threshold_mm_h=20, truth_comparison="float32_truth_strictly_greater",
            secondary_thresholds_mm_h=[5, 10, 50], equal_boundary_counts_required=[20, 50],
            comparison_primary="B8_MINUS_B7", secondary=["B7_MINUS_B4", "B8_MINUS_B4"],
            comparison_policy="each seed first; descriptive three-seed mean and sample SD; no pooled pixels-as-seeds",
            point_methods="retain all A/B/C; none selected by development skill",
            mixture_probability="occurrence_probability*(1-conditional_CDF(log1p(r)))",
            tail_policy="monotone quantile-compatible probability intervals; no zero-tail filling or fitted extrapolation",
            main_probability_outputs=["full-population Brier bounds", "tie-aware AUROC bounds", "identification width and support fractions"],
            AP="NOT_POINT_IDENTIFIED unless separately preregistered full-distribution completion exists",
            exact_risk_skill="NOT_VERIFIED when interval comparisons cannot determine direction",
            probability_decision="0.5 historical diagnostic only; no development-optimized cutoff",
            conditional_outputs="all 32 coverages, existing log Pinball, q32 shortfall, physical point error by fixed truth stratum",
            positive_train_reference="proposed R>0 primary P95/P99; R>.1 sensitivity; per-pixel linear quantile; no Dev fitting",
            climatology="constant 2023 Train exceedance frequency on the exact shared supervision mask",
            event_policy="sample windows stay sample windows; independent-event rules and external observations need a separate researcher decision",
            inference_gate_tolerance=dict(abs=1e-12, rel=1e-12, integer_counts="EXACT")),
        future_resource_reference=dict(
            authorization="NOT_APPROVED_NOT_AN_EXECUTABLE_LAUNCH_PACKAGE",
            models=9, forward_passes_per_model=1, optimizer_updates=0,
            weather_and_mask_logical_bytes=weather, weather_and_mask_content_instances=instances,
            static_bytes=static, static_instances=6,
            train_label_and_mask_bytes=label_and_mask,
            train_label_and_mask_instances=train_label["files"] + 1,
            total_weather_static_label_logical_bytes=weather + static + label_and_mask,
            total_weather_static_label_content_instances=instances + 6 + train_label["files"] + 1,
            inherited_checkpoint_archive_bytes=checkpoints,
            proposed_checkpoint_hash_and_deserialization_each_once_logical_bytes=2 * checkpoints,
            checkpoint_accounting="archive-length reference, not a claim about torch/zip physical internal reads",
            historical_nine_pass_elapsed_seconds=11690.4,
            hard_time_cap_seconds=None, output_storage_cap_bytes=None, minimum_free_bytes=None,
            executable_adapter_commit=None, retry_allowance=0, replay_allowance=0,
            unresolved="Exact adapter, output layout/resource admission, time/storage ceilings and researcher grant must be bound before real reads"),
        stages=[
            dict(id="G0", status="COMPLETE_PREPARATION_ONLY", scope="saved public evidence, candidate methods and synthetic checks"),
            dict(id="G1", status="WAITING_RESEARCHER_METHOD_AND_EXACT_RESOURCE_APPROVAL", scope="freeze method and executable package without weather access"),
            dict(id="G2", status="NOT_STARTED", scope="one shared 2023 label reference pass and finite authorized nine-model extraction"),
            dict(id="G3", status="NOT_STARTED", scope="report all prespecified diagnostics, failures, identification limits and negative results"),
            dict(id="G4", status="NOT_AUTHORIZED", scope="independent observations/events or further training decided separately")],
    )
    raw_core = [r for r in metrics if r["record_type"] == "RAW_ENDPOINT"
                and r["group"] == "all" and r["model_id"] in ("B4", "B7", "B8")
                and r["metric"] == "q32_log_max"]
    audit = dict(
        status="PASS_SAVED_EVIDENCE_AND_PREPARATION_ONLY",
        created_at=datetime.now(timezone.utc).isoformat(), baseline_commit=BASE,
        checks=dict(core_values_verified_against_source_JSON_pointers=pointer_checks,
                    numeric_saved_pairs_independently_subtracted=normal_pairs,
                    indexed_reference_values_checked=indexed_references,
                    PERP_pairs_independently_reconstructed=special_pairs,
                    ABC_strict_gt20_contingencies=27,
                    nine_checkpoint_identities_bound_to_matrix=len(model_manifest),
                    inherited_backfill_results_gate_passed=19),
        saved_extreme_result=dict(TP=0, FP=0, FN=717, TN=3302373, CSI=0, POD=0,
                                  FAR=None, independent_events="NOT_IDENTIFIED"),
        saved_q32_physical_maxima=[dict(model=r["model_id"], seed=int(r["seed"]),
                                       maximum_mm_h=math.expm1(float(r["value"]))) for r in raw_core],
        provenance_findings=[
            dict(id="P1_PERP_PAIR_JOIN", affected_rows=len(collision_rows),
                 issue="target and reference experiment_id both identify PERP; numerical subtraction is valid",
                 safe_handling="use explicit B7 and PERP endpoints plus their source pointers; do not trust the ambiguous join",
                 historical_files_changed=False, affected=collision_rows),
            dict(id="P1_STALE_PROBE_TABLE", found=obsolete_probe_row,
                 issue="older current-core table says NOT_AVAILABLE_NO_TRAINING despite the completed receipt",
                 historical_files_changed=False)],
        activity=dict(new_model_inference=0, model_deserialization=0, weight_payload_reads=0,
                      optimizer_updates=0, raw_meteorological_reads=0, final_2025_reads=0,
                      original_result_files_modified=0, new_research_conclusions_approved=0),
    )
    # Record committed blob bytes rather than platform-dependent CRLF copies.
    for path in sorted(ALLOWED):
        source.read(path)
    manifest = dict(baseline_commit=BASE, hash_scope="COMMITTED_GIT_BLOB_BYTES_NOT_WORKTREE_LINE_ENDINGS",
                    files=[dict(path=p, bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
                           for p, b in sorted(source.payloads.items())])
    return config, audit, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed_parent = (ROOT / "docs/research_readiness").resolve()
    if not output.is_relative_to(allowed_parent) or output == allowed_parent or output.exists():
        raise PermissionError("Use a new output directory inside docs/research_readiness")
    config, audit, manifest = prepare()
    output.mkdir(parents=True, exist_ok=False)
    for name, data in [("proposal.json", config), ("saved_evidence_audit.json", audit),
                       ("source_manifest.json", manifest)]:
        with (output / name).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    print(json.dumps(dict(status=audit["status"], checks=audit["checks"],
                          raw_data_reads=0, inference=0, training=0,
                          proposal_authorized_for_execution=False), ensure_ascii=False))


if __name__ == "__main__":
    main()
