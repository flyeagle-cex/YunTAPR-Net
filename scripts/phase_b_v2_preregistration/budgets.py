"""Integer workload and tensor-payload lower bounds, with no execution code."""
from __future__ import annotations
from typing import Any
from scripts.phase_b_v2_candidates.planning import budget

MODELS = {"B0_MATCHED_V2": (1,4329410), "B1_V2": (6,4331810)}
SEEDS = (2026,2027,2028)
ARMS = ("E0","E1","E2")


def run_rows() -> list[dict[str, Any]]:
    training, validation = budget(10455,2,9), budget(10501,8,9)
    rows = []
    for seed in SEEDS:
        for arm in ARMS:
            for model,(frames,parameters) in MODELS.items():
                rows.append({"run_id":f"{arm}__{model}__s{seed}", "arm":arm,"model":model,"seed":seed,
                    "stage":1 if seed==2026 else 2,"epochs":9,"train_updates":training.total_updates,
                    "train_scene_presentations":training.scene_presentations,"train_tail_batch":training.tail_batch_scenes,
                    "validation_batches_per_epoch":validation.steps_per_epoch,"validation_batches_all_epochs":validation.total_updates,
                    "validation_endpoint_only_lower_bound":validation.steps_per_epoch,"validation_tail_batch":validation.tail_batch_scenes,
                    "train_input_float32_presented_bytes":training.scene_presentations*frames*501*501*4,
                    "validation_input_float32_presented_bytes":validation.scene_presentations*frames*501*501*4,
                    "checkpoint_tensor_payload_lower_bound_bytes":parameters*12,
                    "nine_checkpoints_tensor_lower_bound_bytes":parameters*12*9})
    return rows


def summary() -> dict:
    rows = run_rows()
    return {"runs":len(rows),"total_train_updates":sum(r["train_updates"] for r in rows),
        "total_train_scene_presentations":sum(r["train_scene_presentations"] for r in rows),
        "total_validation_batches":sum(r["validation_batches_all_epochs"] for r in rows),
        "endpoint_only_validation_batches_lower_bound":sum(r["validation_endpoint_only_lower_bound"] for r in rows),
        "stage1_updates":sum(r["train_updates"] for r in rows if r["stage"]==1),
        "stage2_updates":sum(r["train_updates"] for r in rows if r["stage"]==2),
        "train_input_float32_presented_bytes":sum(r["train_input_float32_presented_bytes"] for r in rows),
        "validation_input_float32_presented_bytes":sum(r["validation_input_float32_presented_bytes"] for r in rows),
        "checkpoint_count":9*len(rows),
        "checkpoint_tensor_payload_lower_bound_bytes":sum(r["nine_checkpoints_tensor_lower_bound_bytes"] for r in rows),
        "six_fresh_anchors_parameter_bytes":3*sum(parameters*4 for _,parameters in MODELS.values()),
        "dense_full_grid_qlog_endpoint_bytes_per_run":10501*32*100*100*8,
        "dense_qlog_endpoints_bytes_all_runs":18*10501*32*100*100*8,
        "one_yunnan_diagnostic_variable_bytes":36018430*8,
        "gpu_hours":"NOT_YET_ESTABLISHED","actual_checkpoint_bytes":"NOT_YET_MEASURED",
        "raw_unique_file_bytes":"NOT_MEASURED_RAW_NOT_OPENED","resources_approved":False,
        "execution":"NOT_EXECUTED","budget_kind":"ARITHMETIC_AND_PAYLOAD_LOWER_BOUNDS_ONLY"}
