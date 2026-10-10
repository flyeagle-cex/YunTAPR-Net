"""Synthetic checkpoint transaction: exclusive lock, SHA, commit receipt.

Only returned committed references are recoverable. Partial/orphan files are
preserved for diagnosis. Windows rename/fsync tests do not prove power-loss
durability of the filesystem directory. No formal LAST authorization is made.
"""
from __future__ import annotations
from contextlib import contextmanager
import json
import os
from collections import OrderedDict
from pathlib import Path
import re
import tempfile
import uuid
import torch
from .identity import file_sha
from .safety import TEMP_ROOT, checkpoint_io
from .optimizer import check_finite
from . import rng

SCHEMA = "SYNTHETIC_B9_V0_CANDIDATE_v1"


class SyntheticStore:
    def __init__(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="session_", dir=TEMP_ROOT)).resolve()

    def _path(self, name: str) -> Path:
        if type(name) is not str or re.fullmatch(r"[A-Za-z0-9_-]+", name) is None:
            raise ValueError("Simple synthetic checkpoint name required")
        return self.root / (name + ".pt")

    @contextmanager
    def io(self):
        with checkpoint_io(self.root):
            yield

    def save(self, name: str, payload: dict, *, fault: str | None = None) -> Path:
        if fault not in (None, "after_serialization", "after_blob", "rename_locked"):
            raise ValueError("Unknown synthetic fault")
        destination = self._path(name)
        reference = destination.with_suffix(".ref.json")
        lock = destination.with_suffix(".lock")
        # O_EXCL ensures we never own or clean a pre-existing lock.
        lock.open("x", encoding="ascii").close()  # close before Windows unlink
        try:
            if destination.exists() or reference.exists():
                raise FileExistsError("No checkpoint overwrite")
            part = self.root / (name + "_" + uuid.uuid4().hex + ".part")
            with self.io(), part.open("xb") as stream:
                torch.save(payload, stream)
                stream.flush()
                os.fsync(stream.fileno())
            if fault == "after_serialization":
                raise OSError("INJECTED_SAVE_INTERRUPTION_AFTER_SERIALIZATION")
            with self.io():
                sha, size = file_sha(part), part.stat().st_size
            if fault == "rename_locked":
                raise PermissionError("INJECTED_FILE_LOCK_RENAME_FAILURE")
            part.replace(destination)
            if fault == "after_blob":
                raise OSError("INJECTED_INTERRUPTION_BEFORE_COMMIT_RECEIPT")
            record = {"schema": SCHEMA, "filename": destination.name, "bytes": size, "sha256": sha}
            ref_part = reference.with_suffix(".json.tmp")
            with ref_part.open("x", encoding="utf-8") as stream:
                json.dump(record, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            ref_part.replace(reference)
            return reference
        finally:
            lock.unlink()

    def read(self, reference: Path) -> dict:
        reference = reference.resolve()
        if reference.parent != self.root or not reference.name.endswith(".ref.json"):
            raise PermissionError("Only current synthetic store references accepted")
        record = json.loads(reference.read_text(encoding="utf-8"))
        if set(record) != {"schema", "filename", "bytes", "sha256"} or record["schema"] != SCHEMA:
            raise ValueError("Invalid checkpoint commit receipt")
        blob = (self.root / record["filename"]).resolve()
        if blob.parent != self.root or blob.suffix != ".pt":
            raise PermissionError("Checkpoint receipt path escapes synthetic store")
        with self.io():
            if blob.stat().st_size != record["bytes"] or file_sha(blob) != record["sha256"]:
                raise ValueError("Checkpoint byte identity mismatch; no deserialization")
            result = torch.load(blob, map_location="cpu", weights_only=True)
        if type(result) is not dict:
            raise ValueError("Checkpoint payload must be a mapping")
        return result


def validate_payload(payload: dict, expected_identity: dict, model_template: dict, optimizer_template: dict) -> None:
    """Complete validation before any mutation of live model/optimizer/RNG."""
    fields = {"schema", "identity", "model", "optimizer", "scheduler", "rng", "progress", "initial_sha"}
    if type(payload) is not dict or set(payload) != fields or payload["schema"] != SCHEMA:
        raise ValueError("Checkpoint required fields missing/unknown")
    if payload["identity"] != expected_identity:
        raise ValueError("Checkpoint source/protocol/model/seed/arm/data-role identity mismatch")
    progress = payload["progress"]
    if type(progress) is not dict or set(progress) != {
            "formal_epoch", "FORMAL_OPTIMIZER_STEPS", "synthetic_updates", "train_complete", "validation_complete"}:
        raise ValueError("Checkpoint progress fields mismatch")
    u = progress["synthetic_updates"]
    if (type(u) is not int or not 0 <= u <= 2 or type(progress["formal_epoch"]) is not int
            or progress["formal_epoch"] != 0 or type(progress["FORMAL_OPTIMIZER_STEPS"]) is not int
            or progress["FORMAL_OPTIMIZER_STEPS"] != 0
            or type(progress["train_complete"]) is not bool or type(progress["validation_complete"]) is not bool
            or progress["train_complete"] is not (u > 0) or progress["validation_complete"] is not (u > 0)):
        raise ValueError("Incomplete synthetic boundary or forbidden formal progress")
    expected_schedule = {"trajectory": "S0_ORIGINAL_50_EPOCH_PREFIX", "steps_per_epoch": 5228,
                         "original_horizon": 261400, "proposed_stop": 47052, "completed": u}
    if payload["scheduler"] != expected_schedule:
        raise ValueError("Checkpoint LR trajectory/update mismatch")
    if type(payload["initial_sha"]) is not str or re.fullmatch(r"[0-9a-f]{64}", payload["initial_sha"]) is None:
        raise ValueError("Initial state identity missing")
    model = payload["model"]
    if type(model) not in (dict, OrderedDict) or model.keys() != model_template.keys():
        raise ValueError("Checkpoint model state keys missing/unknown")
    for name, value in model.items():
        target = model_template[name]
        if not isinstance(value, torch.Tensor) or value.shape != target.shape or value.dtype != target.dtype:
            raise ValueError("Checkpoint model tensor signature mismatch: " + name)
    opt = payload["optimizer"]
    if type(opt) is not dict or set(opt) != {"state", "param_groups"}:
        raise ValueError("Checkpoint optimizer state missing/unknown")
    if len(opt["param_groups"]) != len(optimizer_template["param_groups"]):
        raise ValueError("Optimizer grouping mismatch")
    for group, template in zip(opt["param_groups"], optimizer_template["param_groups"], strict=True):
        if set(group) != set(template) or any(group[k] != template[k] for k in template if k != "lr"):
            raise ValueError("Optimizer hyperparameter/group membership mismatch")
        from yuntapr.experimental.phase_b_v2_ablations.config import learning_rate_prefix
        expected_lr = 1e-4 if u == 0 else learning_rate_prefix(u)
        if group["lr"] != expected_lr:
            raise ValueError("Optimizer LR does not match checkpoint update")
    ids = [i for g in opt["param_groups"] for i in g["params"]]
    if len(set(ids)) != len(ids) or (u == 0 and opt["state"]) or (u > 0 and set(opt["state"]) != set(ids)):
        raise ValueError("AdamW state coverage/update mismatch")
    # Group order follows the frozen name-sorted grouping. Template includes
    # parameter shape metadata supplied separately by the live runner.
    shapes = optimizer_template.get("_shapes", {})
    for index, state in opt["state"].items():
        if set(state) != {"step", "exp_avg", "exp_avg_sq"}:
            raise ValueError("AdamW moments missing/unknown")
        step = state["step"]
        if not isinstance(step, torch.Tensor) or step.dtype != torch.float32 or step.shape != () or float(step) != u:
            raise ValueError("AdamW step counter mismatch")
        for key in ("exp_avg", "exp_avg_sq"):
            moment = state[key]
            if not isinstance(moment, torch.Tensor) or moment.dtype != torch.float32 or tuple(moment.shape) != shapes[index]:
                raise ValueError("AdamW moment signature mismatch")
        if bool((state["exp_avg_sq"] < 0).any()):
            raise ValueError("Negative second moment")
    check_finite(model)
    check_finite(opt)
    rng.validate(payload["rng"])

