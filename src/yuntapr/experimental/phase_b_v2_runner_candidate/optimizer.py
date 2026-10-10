"""Frozen AdamW/grouping/clipping and S0 pre-step learning-rate transaction."""
from __future__ import annotations
import math
import torch
from yuntapr.training.phase_a_protocol import parameter_groups
from yuntapr.experimental.phase_b_v2_ablations.config import learning_rate_prefix


def new_adamw(model: torch.nn.Module) -> tuple[torch.optim.AdamW, dict]:
    groups, evidence = parameter_groups(model, check_counts=False)
    optimizer = torch.optim.AdamW(groups, lr=1e-4, betas=(.9, .999), eps=1e-8,
                                 amsgrad=False, maximize=False, capturable=False,
                                 differentiable=False, foreach=False, fused=False)
    return optimizer, evidence


def clip_and_check(model: torch.nn.Module) -> dict:
    parameters = tuple(model.parameters())
    missing = [name for name, p in model.named_parameters() if p.grad is None]
    if missing or any(not bool(torch.isfinite(p.grad).all()) for p in parameters):
        raise FloatingPointError("Missing/nonfinite gradients: " + repr(missing))
    before = float(torch.nn.utils.clip_grad_norm_(parameters, 5., error_if_nonfinite=True))
    after = float(torch.sqrt(sum(p.grad.double().square().sum() for p in parameters)))
    if not math.isfinite(before) or not math.isfinite(after) or after > 5.00001:
        raise FloatingPointError("Frozen gradient clipping contract failed")
    return {"pre_clip_norm": before, "post_clip_norm": after, "limit": 5., "missing_gradients": missing}


def check_finite(value) -> None:
    if isinstance(value, torch.Tensor):
        if not bool(torch.isfinite(value).all()):
            raise FloatingPointError("Nonfinite state tensor")
    elif isinstance(value, dict):
        for child in value.values():
            check_finite(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            check_finite(child)
    elif type(value) is float and not math.isfinite(value):
        raise FloatingPointError("Nonfinite state scalar")


class PrefixSchedule:
    """Set LR before step; commit update count afterwards; never shrink horizon."""
    def __init__(self):
        self.completed = 0

    def prepare(self, optimizer: torch.optim.AdamW) -> float:
        lr = learning_rate_prefix(self.completed + 1)
        for group in optimizer.param_groups:
            group["lr"] = lr
        return lr

    def commit(self) -> None:
        self.completed += 1

    def state_dict(self) -> dict:
        return {"trajectory": "S0_ORIGINAL_50_EPOCH_PREFIX", "steps_per_epoch": 5228,
                "original_horizon": 261400, "proposed_stop": 47052, "completed": self.completed}

    def load_state_dict(self, state: dict) -> None:
        expected = self.state_dict()
        expected["completed"] = state.get("completed")
        if state != expected or type(state["completed"]) is not int or not 0 <= state["completed"] <= 2:
            raise ValueError("Synthetic schedule identity/progress mismatch")
        self.completed = state["completed"]

