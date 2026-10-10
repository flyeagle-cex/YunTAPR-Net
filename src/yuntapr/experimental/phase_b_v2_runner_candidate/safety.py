"""Task-wide durable step quota and scoped synthetic I/O/AdamW protections.

This is a process guard, not a security sandbox against hostile Python code.
There is deliberately no real-data loader or approval-switch execution branch.
"""
from __future__ import annotations
from contextlib import contextmanager
import contextvars
import json
import os
from pathlib import Path
import sys
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import MODELS
from .identity import DELIVERY, REPO, SOURCE_SHA

TEMP_ROOT = DELIVERY / ".local/synthetic_checkpoint_workspace"
_io = contextvars.ContextVar("candidate_checkpoint_io", default=None)
_step = contextvars.ContextVar("candidate_optimizer_step", default=None)
_installed = False
_allowed_csv: set[Path] = set()
_original_step = torch.optim.AdamW.step
_original_save, _original_load = torch.save, torch.load
_keys = {m + "__" + a for m in MODELS for a in ("E0", "E1", "E2")}


def _audit(event, args):
    if event != "open" or not args or not isinstance(args[0], (str, bytes, Path)):
        return
    path = Path(args[0]).resolve()
    name = path.name.lower()
    if "2025" in name or path.suffix.lower() in {".nc", ".h5", ".hdf5", ".tif", ".tiff", ".npy", ".npz"}:
        raise PermissionError("Observational/raw/test data I/O prohibited")
    if path.suffix.lower() == ".csv" and path not in _allowed_csv:
        raise PermissionError("Only SHA-bound published CSV metadata may be read")
    if path.suffix.lower() in {".pt", ".pth", ".ckpt", ".part"}:
        root = _io.get()
        if root is None or not path.is_relative_to(root):
            raise PermissionError("Checkpoint I/O outside current synthetic store prohibited")


def install_guard() -> None:
    global _installed
    if _installed:
        return
    inventory = json.loads((DELIVERY / "source_identity.json").read_text(encoding="utf-8"))
    _allowed_csv.update((REPO / e["path"]).resolve() for e in inventory["inherited_files"]
                        if e["path"].endswith(".csv"))
    sys.addaudithook(_audit)
    def guarded_step(optimizer, *args, **kwargs):
        if _step.get() is not optimizer or type(optimizer) is not torch.optim.AdamW:
            raise PermissionError("Unregistered optimizer step blocked")
        return _original_step(optimizer, *args, **kwargs)
    def guarded_save(*args, **kwargs):
        if _io.get() is None:
            raise PermissionError("Synthetic checkpoint store context required")
        return _original_save(*args, **kwargs)
    def guarded_load(*args, **kwargs):
        if _io.get() is None or kwargs.get("weights_only") is not True:
            raise PermissionError("Only weights_only synthetic checkpoint reads allowed")
        return _original_load(*args, **kwargs)
    # Protect other standard PyTorch optimizers as well; only the registered
    # AdamW transaction is permitted in this candidate process.
    for cls in list(vars(torch.optim).values()):
        if isinstance(cls, type) and issubclass(cls, torch.optim.Optimizer):
            cls.step = guarded_step
    torch.save, torch.load = guarded_save, guarded_load
    _installed = True


@contextmanager
def checkpoint_io(root: Path):
    root = root.resolve()
    if not root.is_relative_to(TEMP_ROOT.resolve()) or root == TEMP_ROOT.resolve():
        raise PermissionError("Dedicated per-session synthetic temporary store required")
    token = _io.set(root)
    try:
        yield
    finally:
        _io.reset(token)


class StepLedger:
    """Reservations are durable and never refunded, even after a failed step.

    Recreating a runner or restoring RNG/checkpoints cannot reset the task quota.
    This serial harness uses one ledger; concurrent writers are rejected by lock.
    """
    def __init__(self, path: Path):
        self.path = path.resolve()
        if not self.path.is_relative_to(TEMP_ROOT.resolve()):
            raise PermissionError("Ledger must stay in task synthetic workspace")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("x", encoding="utf-8") as stream:
                json.dump({"source_sha": SOURCE_SHA, "reserved": {}, "completed": {}, "failed": False,
                           "FORMAL_OPTIMIZER_STEPS": 0}, stream)
        self.read()

    def read(self) -> dict:
        state = json.loads(self.path.read_text(encoding="utf-8"))
        if (state.get("source_sha") != SOURCE_SHA or state.get("FORMAL_OPTIMIZER_STEPS") != 0
                or set(state["reserved"]) - _keys or set(state["completed"]) - set(state["reserved"])
                or type(state["failed"]) is not bool
                or any(type(v) is not int or v < 0 for v in state["completed"].values())
                or any(type(v) is not int or not 0 <= v <= 2 for v in state["reserved"].values())
                or sum(state["reserved"].values()) > 12
                or any(state["completed"].get(k, 0) > v for k, v in state["reserved"].items())):
            raise ValueError("Synthetic ledger invalid; fail closed")
        return state

    def _mutate(self, key: str, completed: bool = False, failed: bool = False):
        if type(key) is not str or key not in _keys:
            raise ValueError("Closed model/arm quota key required")
        lock = self.path.with_suffix(".lock")
        lock.open("x", encoding="ascii").close()  # close before Windows unlink
        try:
            state = self.read()
            if failed:
                state["failed"] = True
            elif completed:
                if state["completed"].get(key, 0) >= state["reserved"].get(key, 0):
                    raise ValueError("Completion without durable reservation")
                state["completed"][key] = state["completed"].get(key, 0) + 1
            else:
                if state["failed"] or state["reserved"].get(key, 0) >= 2 or sum(state["reserved"].values()) >= 12:
                    raise PermissionError("Synthetic task quota exhausted or failed; no automatic retry")
                state["reserved"][key] = state["reserved"].get(key, 0) + 1
            temporary = self.path.with_suffix(".json.tmp")
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(state, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
        finally:
            lock.unlink()

    def perform(self, optimizer: torch.optim.AdamW, key: str) -> None:
        self._mutate(key)
        token = _step.set(optimizer)
        try:
            optimizer.step()
            self._mutate(key, completed=True)
        except BaseException:
            self._mutate(key, failed=True)
            raise
        finally:
            _step.reset(token)

