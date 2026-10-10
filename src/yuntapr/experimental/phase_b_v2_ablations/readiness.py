"""Metadata-only identity checks and an unconditionally blocked runner stub.

No torch import, tensor state loading, dataset access or approval issuance.
Synthetically valid metadata never implies that real initial states exist.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import NoReturn, Sequence
from .config import RunSpec, proposed_runs, workload

INPUT_DIFFERENCES = {"backbone.enc0.conv1.weight", "backbone.enc0.skip.weight"}


def require_sha(value: object, name: str) -> None:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name}: lowercase SHA256 required, never a path or credential")


@dataclass(frozen=True)
class TensorIdentity:
    shape: tuple[int, ...]
    dtype: str
    sha256: str

    def __post_init__(self) -> None:
        if type(self.shape) is not tuple or not self.shape or not all(type(n) is int and n > 0 for n in self.shape):
            raise ValueError("Nonempty positive integer shape required")
        if self.dtype != "float32":
            raise ValueError("Frozen candidate parameter dtype is float32")
        require_sha(self.sha256, "tensor identity")


def state_metadata_digest(tensors: dict[str, TensorIdentity]) -> str:
    if type(tensors) is not dict or not tensors or not all(type(k) is str and k and
            type(v) is TensorIdentity for k, v in tensors.items()):
        raise ValueError("Named tensor identity metadata required")
    for value in tensors.values():
        value.__post_init__()
    body = json.dumps({k: asdict(v) for k, v in sorted(tensors.items())}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


@dataclass(frozen=True)
class FreshRecord:
    run: RunSpec
    tensors: dict[str, TensorIdentity]
    state_sha256: str
    post_pair_rng_sha256: str
    epoch_order_sha256: str
    initializer_code_sha256: str
    historical_checkpoint_loaded: bool = False

    def validate(self) -> None:
        if type(self.run) is not RunSpec:
            raise ValueError("Closed candidate RunSpec required")
        self.run.__post_init__()
        for name in ("state_sha256", "post_pair_rng_sha256", "epoch_order_sha256", "initializer_code_sha256"):
            require_sha(getattr(self, name), name)
        if self.historical_checkpoint_loaded is not False:
            raise ValueError("Historical model/optimizer/RNG state transfer forbidden")
        if state_metadata_digest(self.tensors) != self.state_sha256:
            raise ValueError("Declared state digest differs from supplied tensor metadata")


def audit_fresh_metadata(records: Sequence[FreshRecord]) -> dict:
    """Review declarations only; cannot prove origins or instantiate a model."""
    if len(records) != 18 or not all(type(r) is FreshRecord for r in records):
        raise ValueError("Exactly 18 fresh metadata records required")
    for r in records:
        r.validate()
    table = {r.run.run_id: r for r in records}
    if set(table) != {r.run_id for r in proposed_runs()}:
        raise ValueError("Missing, duplicate or unregistered run identity")
    if len({r.initializer_code_sha256 for r in records}) != 1:
        raise ValueError("Initializer code identity differs across arms")
    for seed in (2026, 2027, 2028):
        subset = [r for r in records if r.run.seed == seed]
        if len({r.post_pair_rng_sha256 for r in subset}) != 1 or len({r.epoch_order_sha256 for r in subset}) != 1:
            raise ValueError("Same-seed RNG/order metadata differs")
        for model in ("B0_MATCHED_V2", "B1_V2"):
            arms = [r for r in subset if r.run.model == model]
            if len({r.state_sha256 for r in arms}) != 1:
                raise ValueError("Same-model same-seed full fresh states differ across arms")
        a = table[RunSpec("E0", "B0_MATCHED_V2", seed).run_id].tensors
        b = table[RunSpec("E0", "B1_V2", seed).run_id].tensors
        if a.keys() != b.keys():
            raise ValueError("B0/B1 parameter names differ")
        different = {k for k in a if a[k].shape != b[k].shape}
        if different != INPUT_DIFFERENCES or any(a[k] != b[k] for k in a if k not in different):
            raise ValueError("Only two frozen input-shape differences permitted; shared tensors must match")
    return {"metadata_consistent": True, "actual_model_instantiated": False,
            "actual_initialization_proven": False, "scope": "DECLARED_OR_SYNTHETIC_METADATA_ONLY",
            "can_launch_formal_training": False}


def review_checkpoint_binding(metadata: dict, expected: dict, *, resume_approval_reference: str | None = None) -> dict:
    """No files are opened and no state can be applied by this review.

    A supplied reference is not authenticated here and cannot authorize resume.
    Future formal integration must bind a real independent event to LAST SHA.
    """
    fields = {"run_id", "last_sha256", "model_sha256", "optimizer_sha256", "rng_sha256",
              "scheduler_sha256", "code_sha256", "protocol_sha256", "data_sha256", "init_sha256",
              "completed_epoch", "retained_updates", "boundary", "original_execution_reference"}
    if type(metadata) is not dict or set(metadata) != fields or type(expected) is not dict:
        raise ValueError("Closed checkpoint metadata required")
    if metadata["run_id"] not in {r.run_id for r in proposed_runs()}:
        raise ValueError("Checkpoint run identity is not in candidate matrix")
    for key in fields:
        if key.endswith("sha256"):
            require_sha(metadata[key], key)
    epoch, updates = metadata["completed_epoch"], metadata["retained_updates"]
    if type(epoch) is not int or not 1 <= epoch <= 9 or type(updates) is not int or updates != epoch * 5228:
        raise ValueError("Complete-epoch retained budget mismatch")
    if metadata["boundary"] != "COMPLETED_TRAIN_AND_VALIDATION_EPOCH_ONLY":
        raise ValueError("Partial epoch is not a legal LAST")
    if type(metadata["original_execution_reference"]) is not str or not metadata["original_execution_reference"]:
        raise ValueError("Original execution provenance reference missing")
    binding = {"run_id", "last_sha256", "code_sha256", "protocol_sha256", "data_sha256", "init_sha256"}
    if set(expected) != binding or any(metadata[k] != expected[k] for k in binding):
        raise ValueError("Expected LAST/code/protocol/data/init/run binding differs")
    if resume_approval_reference is not None and (type(resume_approval_reference) is not str or not resume_approval_reference):
        raise ValueError("Nonempty independent-event reference or None required")
    return {"metadata_consistent": True, "remaining_retained_updates": 47052 - updates,
            "next_epoch": epoch + 1 if epoch < 9 else None, "approval_authenticity_verified": False,
            "resume_approval_reference_present": resume_approval_reference is not None,
            "can_apply_checkpoint_state": False, "can_launch_formal_training": False}


class FormalExecutionBlocked(RuntimeError):
    pass


class BlockedRunner:
    """Design skeleton with no execution implementation, even after flag edits."""

    def describe(self) -> dict:
        return {"runs": [r.run_id for r in proposed_runs()], "budget": workload(),
                "runner_implemented": False, "can_launch_formal_training": False,
                "required": ["Independent scientific approval", "Researcher code review",
                             "Explicit formal integration approval", "Data and compute permissions",
                             "Real fresh/data/code identities", "Separately bound stage execution authorization"]}

    def run(self, *args: object, **kwargs: object) -> NoReturn:
        raise FormalExecutionBlocked("Candidate skeleton has NO TRAINING CAPABILITY; new reviewed runner and independent approvals required")
