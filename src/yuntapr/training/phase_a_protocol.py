"""Researcher-approved protocol utilities; this module provides no fitting loop."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import random

import numpy as np
import torch
from torch import nn
import yaml

from yuntapr.contracts.loader import REPO_ROOT, sha256

PROTOCOL_PATH = Path("config/training/phase_a_training_protocol_v1.yaml")
EXPECTED_COUNTS = {"DECAY_GROUP": 4322832, "NO_DECAY_GROUP": 6529, "total": 4329361}


def load_protocol(root=REPO_ROOT, *, expected_sha256=None):
    path = Path(root) / PROTOCOL_PATH
    if expected_sha256 is not None and sha256(path) != expected_sha256:
        raise ValueError("protocol SHA256 mismatch")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config["status"] != "RESEARCHER_APPROVED" or config["version"] != "v1.0":
        raise ValueError("Unapproved protocol")
    if config["authorization"]["FORMAL_TRAINING_AUTHORIZED"] or config["authorization"]["B0_FORMAL_TRAINING_STARTED"]:
        raise ValueError("Formal training is outside this engineering protocol release")
    for name, reference in config["identity"].items():
        source = Path(reference["path"])
        source = source if source.is_absolute() else Path(root) / source
        if sha256(source) != reference["sha256"]:
            raise ValueError("Pinned identity mismatch: " + name)
    return config


def require_engineering_scope(scope):
    if scope != "ENGINEERING_ONLY":
        raise ValueError("Explicit ENGINEERING_ONLY scope required; formal training unauthorized")


def head_pin(model):
    heads = model.heads
    if set(dict(heads.named_children())) != {"occurrence", "quantile"}:
        raise ValueError("Unexpected head module")
    result = {}
    for name, channels in (("occurrence", 1), ("quantile", 32)):
        module = getattr(heads, name)
        if (type(module) is not nn.Conv2d or module.in_channels != 48 or module.out_channels != channels
                or module.kernel_size != (1, 1) or module.stride != (1, 1)
                or module.padding != (0, 0) or module.dilation != (1, 1)
                or module.groups != 1 or module.bias is None or list(module.children())):
            raise ValueError("Exact head implementation mismatch: " + name)
        result[name] = {"module": "Conv2d", "in_channels": 48, "out_channels": channels,
                        "kernel_size": 1, "bias": True, "hidden_layers": 0,
                        "parameters": sum(p.numel() for p in module.parameters())}
    return result


def parameter_groups(model, *, check_counts=True):
    """Classify by owning module, never by an ambiguous name substring."""
    all_parameters = {name: p for name, p in model.named_parameters() if p.requires_grad}
    classification = {}
    for module_name, module in model.named_modules():
        for local_name, p in module.named_parameters(recurse=False):
            if not p.requires_grad:
                continue
            name = module_name + "." + local_name if module_name else local_name
            if type(module) is nn.Conv2d and local_name == "weight":
                group = "DECAY_GROUP"
            elif ((type(module) is nn.Conv2d and local_name == "bias")
                  or (type(module) is nn.GroupNorm and local_name in ("weight", "bias"))):
                group = "NO_DECAY_GROUP"
            else:
                raise ValueError("Unknown trainable parameter classification: " + name)
            if name in classification or all_parameters.get(name) is not p:
                raise ValueError("Duplicate/shared parameter ownership: " + name)
            classification[name] = group
    if set(classification) != set(all_parameters):
        raise ValueError("Parameter group union mismatch")
    names = {g: sorted(n for n, value in classification.items() if value == g)
             for g in ("DECAY_GROUP", "NO_DECAY_GROUP")}
    if set(names["DECAY_GROUP"]) & set(names["NO_DECAY_GROUP"]):
        raise ValueError("Parameter group intersection")
    counts = {g: sum(all_parameters[n].numel() for n in ns) for g, ns in names.items()}
    counts["total"] = sum(counts.values())
    if check_counts and counts != EXPECTED_COUNTS:
        raise ValueError("Pinned parameter count mismatch: " + repr(counts))
    groups = [{"params": [all_parameters[n] for n in names[g]], "weight_decay": decay, "group_name": g}
              for g, decay in (("DECAY_GROUP", 1e-4), ("NO_DECAY_GROUP", 0.0))]
    evidence = {"names": names, "counts": counts, "disjoint": True, "complete_union": True,
                "classification": "Conv2d kernel only; Conv2d bias and GroupNorm affine have no decay"}
    return groups, evidence


def adamw(model):
    groups, evidence = parameter_groups(model)
    optimizer = torch.optim.AdamW(groups, lr=1e-4, betas=(.9, .999), eps=1e-8,
                                 amsgrad=False, maximize=False, capturable=False,
                                 differentiable=False, foreach=False, fused=False)
    return optimizer, evidence


def lr_for_update(u, *, steps_per_epoch=5860):
    """One-based update on the unchanged 50-epoch horizon, also for FinalFit replay."""
    if isinstance(u, bool) or not isinstance(u, int) or isinstance(steps_per_epoch, bool) or not isinstance(steps_per_epoch, int):
        raise ValueError("Integer update and steps_per_epoch required")
    W, U = steps_per_epoch, 50 * steps_per_epoch
    if W < 1 or not 1 <= u <= U:
        raise ValueError("Update outside the protocol horizon")
    if u <= W:
        return 1e-4 * u / W
    progress = (u - W) / (U - W)
    return 1e-6 + (1e-4 - 1e-6) * (1 + math.cos(math.pi * progress)) / 2


def phase_a_lr_for_update(u):
    return lr_for_update(u)


def epoch_permutation(epoch_index, *, count=11720):
    if isinstance(epoch_index, bool) or not isinstance(epoch_index, int) or epoch_index < 0:
        raise ValueError("Zero-based nonnegative epoch index required")
    generator = torch.Generator().manual_seed(2026 + epoch_index)
    return torch.randperm(count, generator=generator)


def seed_reproducibility():
    # Environment must be set by the launcher before Python/CUDA startup.
    if os.environ.get("PYTHONHASHSEED") != "2026" or os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
        raise RuntimeError("Required startup environment is missing")
    random.seed(2026)
    np.random.seed(2026)
    torch.manual_seed(2026)
    torch.cuda.manual_seed_all(2026)
    torch.use_deterministic_algorithms(True, warn_only=False)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision("highest")


def capture_rng():
    return {"python": random.getstate(), "numpy": np.random.get_state(),
            "torch_cpu": torch.get_rng_state(), "torch_cuda": torch.cuda.get_rng_state_all()}


def restore_rng(states):
    random.setstate(states["python"])
    np.random.set_state(states["numpy"])
    torch.set_rng_state(states["torch_cpu"].cpu())
    torch.cuda.set_rng_state_all([state.cpu() for state in states["torch_cuda"]])


def state_digest(value):
    """Stable logical SHA of a nested state, including buffers, shapes and dtypes."""
    digest = hashlib.sha256()
    def visit(item):
        if isinstance(item, torch.Tensor):
            item = item.detach().cpu().contiguous()
            digest.update(str((str(item.dtype), tuple(item.shape))).encode())
            digest.update(item.reshape(-1).view(torch.uint8).numpy().tobytes())
        elif isinstance(item, np.ndarray):
            digest.update(str((str(item.dtype), item.shape)).encode())
            digest.update(item.tobytes())
        elif isinstance(item, dict):
            digest.update(b"dict{")
            for key in sorted(item, key=lambda key: (type(key).__name__, str(key))):
                visit(key)
                visit(item[key])
            digest.update(b"}")
        elif isinstance(item, (tuple, list)):
            digest.update(type(item).__name__.encode() + b"[")
            for child in item:
                visit(child)
            digest.update(b"]")
        else:
            digest.update((type(item).__name__ + ":" + repr(item) + ";").encode())
    visit(value)
    return digest.hexdigest()


@dataclass
class ValidationSelection:
    best_checkpoint_value: float | None = None
    selected_checkpoint_epoch: int | None = None
    early_stop_best: float | None = None
    non_improvement_count: int = 0
    completed_epoch: int = 0

    def update(self, epoch, global_val_core_loss):
        if epoch != self.completed_epoch + 1 or not math.isfinite(global_val_core_loss):
            raise ValueError("Sequential completed epochs and finite global core loss required")
        self.completed_epoch = epoch
        selected = self.best_checkpoint_value is None or global_val_core_loss < self.best_checkpoint_value
        if selected:
            self.best_checkpoint_value = global_val_core_loss
            self.selected_checkpoint_epoch = epoch
        improved = self.early_stop_best is None or global_val_core_loss < self.early_stop_best - 1e-4
        if improved:
            self.early_stop_best = global_val_core_loss
            self.non_improvement_count = 0
        else:
            self.non_improvement_count += 1
        return {"checkpoint_selected": selected, "early_stop_improvement": improved,
                "stop": self.non_improvement_count >= 8}


def checkpoint_metadata(protocol, protocol_sha256, groups, environment, global_update):
    metadata = {"scope": "ENGINEERING_ONLY", "checkpoint_kind": "TEMPORARY_PARTIAL_UPDATE_SCHEMA_TEST",
            "completed_epoch": 0, "global_update": global_update, "protocol_version": protocol["version"],
            "protocol_sha256": protocol_sha256, "scientific_freeze_version": "v1.1",
            "identities": {name: ref["sha256"] for name, ref in protocol["identity"].items()},
            "focal_alpha": .5, "focal_gamma": 2., "optimizer_config": protocol["optimizer"],
            "weight_decay_groups": groups, "base_lr": 1e-4, "min_lr": 1e-6,
            "physical_batch": 2, "effective_batch": 2, "AMP_mode": "BF16", "seed": 2026,
            "epoch_seed_rule": "2026 + zero_based_epoch_index", "best_checkpoint_metric": "global_val_core_loss",
            "best_checkpoint_value": None, "early_stop_best": None, "non_improvement_count": 0,
            "EPOCH_BOUNDARY_RESUME_ONLY": True, "engineering_partial_update_exception": True,
            "environment": environment, "FORMAL_TRAINING_AUTHORIZED": False}
    aliases = {"scientific_contract_sha256": "scientific_contract_v1.1", "engineering_config_sha256": "engineering_v4",
               "normalization_artifact_sha256": "phase_a_normalization_artifact", "train_manifest_sha256": "eligible_train_manifest",
               "validation_manifest_sha256": "eligible_validation_manifest", "SP04_mapping_sha256": "SP04_mapping",
               "Yunnan_mask_sha256": "yunnan_mask"}
    metadata.update({key: protocol["identity"][name]["sha256"] for key, name in aliases.items()})
    return metadata


def validate_checkpoint_metadata(metadata, expected):
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError("Checkpoint provenance mismatch: " + key)
    require_engineering_scope(metadata["scope"])
    if metadata["FORMAL_TRAINING_AUTHORIZED"] or metadata["checkpoint_kind"] != "TEMPORARY_PARTIAL_UPDATE_SCHEMA_TEST":
        raise ValueError("Formal checkpoint is not accepted by this temporary loader")
    if metadata["completed_epoch"] != 0 or metadata["global_update"] != 2:
        raise ValueError("Only the explicitly authorized two-update engineering fixture can resume here")


def load_temporary_checkpoint(path, model, optimizer, expected_metadata):
    """Load only a trusted file created in this run; reject identity BEFORE applying states."""
    payload = torch.load(path, map_location="cpu", weights_only=False)
    validate_checkpoint_metadata(payload["metadata"], expected_metadata)
    model.load_state_dict(payload["model_state_dict"], strict=True)
    optimizer.load_state_dict(payload["optimizer_state_dict"])
    restore_rng(payload["rng_states"])
    return payload["metadata"]["global_update"]
