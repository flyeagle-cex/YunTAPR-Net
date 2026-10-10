"""Epoch receipts above the already-tested atomic store; no historical reader."""
from __future__ import annotations
from collections import OrderedDict
import tempfile
from pathlib import Path
import torch
from yuntapr.experimental.phase_b_v2_runner_candidate.checkpoint import SyntheticStore
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import check_finite
from yuntapr.experimental.phase_b_v2_runner_candidate import rng
from yuntapr.experimental.phase_b_v2_ablations.config import learning_rate_prefix
from yuntapr.training.phase_a_protocol import state_digest
from .safety import TEMP_ROOT, checkpoint_io
from .data import ROLES, Coverage
from yuntapr.experimental.phase_b_v2_integration.controls import synthetic_epoch_order

SCHEMA = "SYNTHETIC_COMPLETED_EPOCH_LAST_v1"


class EpochStore(SyntheticStore):
    """Reuse exact atomic save/read/locks/SHA receipt; isolate storage/context."""
    def __init__(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="epoch_session_", dir=TEMP_ROOT)).resolve()

    def io(self):
        return checkpoint_io(self.root)


def validate_last(p: dict, expected_identity: dict, model_template: dict, optimizer_template: dict,
                  train_ids: tuple[str, ...], val_ids: tuple[str, ...], initial_sha: str):
    fields = {"schema", "identity", "initial_sha", "model", "optimizer", "scheduler", "rng", "epoch_receipt", "ancestor"}
    if type(p) is not dict or set(p) != fields or p["schema"] != SCHEMA or p["identity"] != expected_identity or p["initial_sha"] != initial_sha:
        raise ValueError("LAST source/protocol/code/data/seed/arm/fresh identity mismatch")
    receipt = p["epoch_receipt"]
    if type(receipt) is not dict or set(receipt) != {"epoch", "update", "train", "validation", "formal_epoch", "FORMAL_OPTIMIZER_STEPS"}:
        raise ValueError("Complete epoch receipt required")
    epoch, update = receipt["epoch"], receipt["update"]
    if (type(epoch) is not int or not 1 <= epoch <= 2 or type(update) is not int or update != epoch * 3
            or type(receipt["formal_epoch"]) is not int or receipt["formal_epoch"] != 0
            or type(receipt["FORMAL_OPTIMIZER_STEPS"]) is not int or receipt["FORMAL_OPTIMIZER_STEPS"] != 0):
        raise ValueError("Synthetic epoch/update or forbidden formal progress")
    for role, ids in (("train", train_ids), ("validation", val_ids)):
        report = receipt[role]
        coverage = report["coverage"]
        if coverage["expected_ids"] != list(ids) or coverage["exactly_once"] is not True:
            raise ValueError("LAST dataset coverage identity mismatch")
        c = Coverage(ids); c.add(tuple(coverage["visited_ids"])); c.finish()
        if type(report["N_valid"]) is not int or report["N_valid"] != 3430 * len(ids) or type(report["N_rain"]) is not int or not 0 <= report["N_rain"] <= report["N_valid"]:
            raise ValueError("LAST denominator mismatch")
        check_finite(report)
    if (receipt["train"]["batches"] != 3 or receipt["validation"]["forwards"] != 1
            or receipt["validation"]["numerator_dtype"] != "float64" or receipt["validation"]["lambda_in_common_metric"] is not False):
        raise ValueError("LAST train/validation completion or metric contract")
    expected_order = synthetic_epoch_order(train_ids, expected_identity["run"]["seed"], epoch - 1)
    if receipt["train"]["coverage"]["visited_ids"] != list(expected_order) or receipt["validation"]["coverage"]["visited_ids"] != list(val_ids):
        raise ValueError("LAST sample order identity mismatch")
    batches = receipt["train"]["batch_records"]
    if len(batches) != 3:
        raise ValueError("Missing train step receipts")
    for i, b in enumerate(batches):
        u = (epoch - 1) * 3 + i + 1
        if (b["synthetic_update"] != u or b["synthetic_epoch"] != epoch
                or b["scene_ids"] != list(expected_order[2*i:2*i+2]) or b["lr"] != learning_rate_prefix(u)
                or b["batch"] != len(b["scene_ids"]) or b["N_valid"] != 3430 * b["batch"]
                or b["limit"] != 5. or b["post_clip_norm"] > 5.00001):
            raise ValueError("LAST step/update/LR/clipping/coverage receipt mismatch")
    expected_schedule = {"trajectory": "S0_ORIGINAL_50_EPOCH_PREFIX", "steps_per_epoch": 5228,
                         "original_horizon": 261400, "proposed_stop": 47052, "completed": update}
    if p["scheduler"] != expected_schedule:
        raise ValueError("LAST scheduler trajectory/progress mismatch")
    if type(p["model"]) not in (dict, OrderedDict) or p["model"].keys() != model_template.keys():
        raise ValueError("Model state keys missing")
    for n, t in p["model"].items():
        if not isinstance(t, torch.Tensor) or t.shape != model_template[n].shape or t.dtype != model_template[n].dtype:
            raise ValueError("Model state tensor signature mismatch")
    opt = p["optimizer"]
    if type(opt) is not dict or set(opt) != {"state", "param_groups"} or len(opt["param_groups"]) != len(optimizer_template["param_groups"]):
        raise ValueError("AdamW state missing")
    for g, template in zip(opt["param_groups"], optimizer_template["param_groups"], strict=True):
        if set(g) != set(template) or any(g[k] != template[k] for k in template if k != "lr") or g["lr"] != learning_rate_prefix(update):
            raise ValueError("AdamW group/LR mismatch")
    if set(opt["state"]) != set(optimizer_template["_shapes"]):
        raise ValueError("Missing AdamW state")
    for n, value in opt["state"].items():
        if set(value) != {"step", "exp_avg", "exp_avg_sq"} or not isinstance(value["step"], torch.Tensor) or value["step"].shape != () or value["step"].dtype != torch.float32 or float(value["step"]) != update:
            raise ValueError("AdamW step mismatch")
        for key in ("exp_avg", "exp_avg_sq"):
            t = value[key]
            if not isinstance(t, torch.Tensor) or t.dtype != torch.float32 or tuple(t.shape) != optimizer_template["_shapes"][n]:
                raise ValueError("AdamW moment signature mismatch")
        if bool((value["exp_avg_sq"] < 0).any()):
            raise ValueError("Negative second moment")
    if type(p["ancestor"]) is not dict or set(p["ancestor"]) != {"campaign", "parent_last_sha"} or p["ancestor"]["campaign"] != "SYNTHETIC_EPOCH_ENGINE_v1":
        raise ValueError("Synthetic ancestry missing")
    parent = p["ancestor"]["parent_last_sha"]
    if (epoch == 1 and parent is not None) or (epoch > 1 and (type(parent) is not str or len(parent) != 64)):
        raise ValueError("Completed LAST ancestry mismatch")
    check_finite(p["model"]); check_finite(opt); rng.validate(p["rng"])


def optimizer_template(optimizer):
    state = optimizer.state_dict()
    state["_shapes"] = {i: tuple(p.shape) for group, metadata in zip(optimizer.param_groups, state["param_groups"], strict=True)
                        for i, p in zip(metadata["params"], group["params"], strict=True)}
    return state
