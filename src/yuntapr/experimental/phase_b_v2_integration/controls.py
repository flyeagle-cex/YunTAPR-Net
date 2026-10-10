"""Pure candidate-plan and synthetic-order checks, never an execution authority."""
from __future__ import annotations
import re
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, get_config, SEEDS, workload, learning_rate_prefix
from yuntapr.experimental.phase_b_v2_ablations.readiness import BlockedRunner, FormalExecutionBlocked, review_checkpoint_binding
from . import SCOPE


def isolated_run_id(run: RunSpec) -> str:
    if type(run) is not RunSpec:
        raise ValueError("Closed RunSpec required")
    run.__post_init__()
    return f"{SCOPE}__phase_b_v2_integration_v1__{run.run_id}"


def candidate_plan(run: RunSpec) -> dict:
    isolated_run_id(run)
    config = get_config(run.experiment_id)
    return {"run": run, "alpha": config.alpha, "gamma": config.gamma, "lambda_q": config.lambda_q,
            "data_years": (2023, 2024), "train_scenes": 10455, "validation_scenes": 10501,
            "qualification": "Q1_M1_PAIRED_FROZEN", "normalization": "N0_FROZEN_2023_SHARED",
            "epochs": 9, "physical_batch": 2, "accumulation": 1, "drop_last": False,
            "endpoint": "EPOCH_9_NO_BEST_SELECTION", "scheduler_horizon": 50}


def audit_plan(plan: dict) -> dict:
    if type(plan) is not dict or type(plan.get("run")) is not RunSpec:
        raise ValueError("Closed candidate metadata required")
    expected = candidate_plan(plan["run"])
    if set(plan) != set(expected):
        raise ValueError("Unknown/missing fields, including self-declared approval")
    if any(type(plan[k]) is not type(expected[k]) or plan[k] != expected[k] for k in expected):
        raise ValueError("Candidate parameters/year/qualification/seed/budget differ")
    return {"scope": SCOPE, "candidate_metadata_consistent": True, "run_id": isolated_run_id(plan["run"]),
            "budget": workload(), "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED": False,
            "can_launch_formal_training": False, "reason": "Independent approval and formal runner absent"}


def synthetic_epoch_order(sample_ids: tuple[str, ...], seed: int, epoch_index: int) -> tuple[str, ...]:
    if type(seed) is not int or seed not in SEEDS or type(epoch_index) is not int or not 0 <= epoch_index < 9:
        raise ValueError("Preregistered seed and zero-based epochs 0..8 required")
    if type(sample_ids) is not tuple or not 1 <= len(sample_ids) <= 10455 or len(set(sample_ids)) != len(sample_ids):
        raise ValueError("Nonempty unique synthetic identity tuple, at most 10455")
    if any(type(x) is not str or re.fullmatch(r"SYNTHETIC_ENGINEERING_ONLY/order_[0-9]{5}", x) is None for x in sample_ids):
        raise ValueError("No real or year-based sample IDs in synthetic order fixture")
    order = torch.randperm(len(sample_ids), generator=torch.Generator().manual_seed(seed + epoch_index))
    return tuple(sample_ids[int(i)] for i in order)


def endpoint_boundary(hypothetical_completed_epoch: int) -> dict:
    epoch = hypothetical_completed_epoch
    if type(epoch) is not int or not 0 <= epoch <= 9:
        raise ValueError("Candidate complete epochs 0..9 only")
    return {"scope": SCOPE, "hypothetical_completed_epoch": epoch,
            "hypothetical_retained_updates": epoch * 5228, "remaining_budget": (9 - epoch) * 5228,
            "next_epoch": epoch + 1 if epoch < 9 else None,
            "next_lr": learning_rate_prefix(epoch * 5228 + 1) if epoch < 9 else None,
            "formal_updates_executed": 0, "can_launch_formal_training": False}


def reject_resume(metadata: dict, expected: dict, *, checkpoint_kind: str,
                  resume_approval_reference: str | None = None) -> None:
    if checkpoint_kind != "LAST":
        raise ValueError("Only complete LAST can be proposed for independent review")
    # Existing candidate checker binds run/LAST/code/protocol/data/init and epoch.
    review_checkpoint_binding(metadata, expected, resume_approval_reference=resume_approval_reference)
    if resume_approval_reference is None:
        raise FormalExecutionBlocked("Independent LAST-bound resume approval is absent")
    raise FormalExecutionBlocked("A reference string is not authenticated human approval; no state loader exists")


def reject_formal_start(*args: object, **kwargs: object) -> None:
    BlockedRunner().run(*args, **kwargs)  # frozen candidate always raises, regardless of flags

