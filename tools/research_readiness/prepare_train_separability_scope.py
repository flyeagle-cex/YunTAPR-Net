"""Prepare metadata for a same-scene Train diagnostic. Never open scientific payloads."""

import argparse
from collections import Counter
import csv
import json
from pathlib import Path


def prepare(private_output):
    from tools.research_readiness import start_train_endpoint_screen as endpoint
    from tools.research_readiness.start_train_crossing_amplitude import QC, block_id, choose_batches, restrict_scope
    from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan

    root = endpoint.ROOT
    prior = endpoint.read(root / endpoint.REFERENCE)
    local = endpoint.read(root / endpoint.LOCAL / "cosine9_prepare_20261110_v1/PRIVATE_PREPARATION.json")
    inherited = Path(local["inherited"])
    if endpoint.sha(inherited) != local["inherited_file_sha256"]:
        raise ValueError("Inherited Train plan differs")
    _, prepared = endpoint.load_inherited(inherited)
    original = prepared["roles"]["Train"]
    if (endpoint.digest(endpoint.unsigned(prior)) != prior["proposal_sha256"]
            or prior["data"] != prepared["data"]
            or original["source_manifest_sha256"] != endpoint.TRAIN_MANIFEST):
        raise ValueError("Frozen COSINE9 and Train evidence differ")
    inputs = prepared["private_inputs"]
    plan = PopulationPlan(inputs["stage3_run"], inputs["request"], root=root)
    ids = tuple(original["ids"])
    qc = root / QC
    if (ids != tuple(plan.ids("Train")) or len(ids) != endpoint.CAP["train_scenes"]
            or any(not sid.startswith("2023-") for sid in ids)
            or plan.identity != prior["data"] or endpoint.sha(qc) != plan.identity["target_QC_sha256"]):
        raise ValueError("Frozen original Train order, population or QC identity differs")

    population = set(ids)
    with qc.open(encoding="utf-8-sig", newline="") as stream:
        eligible = [row for row in csv.DictReader(stream) if row["window_start"] in population]
    if len(eligible) != len(ids) or {row["window_start"] for row in eligible} != population:
        raise ValueError("QC must join exactly once to every Train scene")
    strong = {row["window_start"] for row in eligible if float(row["imerg_max_yunnan_mmhr"]) > 20}
    if len(strong) != endpoint.CAP["strong_scenes"]:
        raise ValueError("Train positive-scene counts differ")
    batches = choose_batches(ids, strong)
    subset = tuple(sid for batch in batches for sid in batch)
    if not strong <= set(subset) or len(set(subset)) != len(subset):
        raise ValueError("Missing or duplicate scenes in the selected intact batches")
    scope = restrict_scope(plan, original["files"], subset)
    if any(spec["year"] != 2023 for spec in scope["files"].values()):
        raise PermissionError("Train-only science scope required")
    fixed = {key: endpoint.CAP[key] for key in ("static_bytes", "checkpoint_bytes", "static_opens",
                                                  "checkpoint_source_opens", "checkpoint_loads")}
    waves = Counter(block_id(sid) for sid in strong)
    budget = dict(
        **fixed, weather_and_supervision_bytes=scope["bytes_per_pass"],
        weather_and_supervision_opens=scope["file_count"],
        total_scientific_source_bytes=scope["bytes_per_pass"] + fixed["static_bytes"] + fixed["checkpoint_bytes"],
        total_scientific_source_opens=scope["file_count"] + fixed["static_opens"] + fixed["checkpoint_source_opens"],
        forward_batches=len(batches), optimizer_updates=0, threshold_fits=0, retries=0,
        development_access=False, final_2025_access=False,
    )
    private = dict(batches=batches, positive_scene_ids=sorted(strong), source_scope=scope)
    result = dict(
        status="METADATA_SCOPE_ONLY_NOT_AN_EXECUTION_PROPOSAL",
        train_scenes=len(ids), selected_positive_scenes=len(strong), forward_scenes=len(subset),
        companion_scenes=len(subset) - len(strong), positive_scene_counts_by_14day_block=dict(sorted(waves.items())),
        original_train_manifest_sha256=original["source_manifest_sha256"],
        proposed_subset_source_sha256=scope["source_manifest_sha256"],
        fixed_batch_order_sha256=endpoint.digest(batches), private_scope_sha256=endpoint.digest(private),
        checkpoint_sha256=endpoint.CHECKPOINT_SHA256,
        static_pack_sha256=prior["static_source_sha256"]["B7"],
        target_qc_sha256=plan.identity["target_QC_sha256"],
        budget=budget, source_breakdown=scope["by_kind"], opened_scientific_payloads=0,
    )
    with private_output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(private | {"public_receipt": result}, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.private_output), indent=2))
