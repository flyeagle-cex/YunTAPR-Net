"""Versioned bounded epoch campaign; durable quota is never checkpointed."""
from __future__ import annotations
from contextlib import contextmanager
import contextvars
import json
import os
from pathlib import Path
import sys
import torch
from .protocol import OUT, ROOT, SOURCE_SHA, code_sha, public_inventory

TEMP_ROOT = OUT / ".local/synthetic_checkpoint_workspace"
LIMITS = {m + "__" + a: (9 if a == "E0" else 3) for m in ("B0_MATCHED_V2", "B1_V2") for a in ("E0", "E1", "E2")}
_io = contextvars.ContextVar("epoch_candidate_io", default=None)
_active_step = contextvars.ContextVar("epoch_candidate_step", default=None)
_installed = False
_step_original = torch.optim.AdamW.step
_save_original, _load_original = torch.save, torch.load
_csv: set[Path] = set()
_deferred: set[Path] = set()


def _audit(event, args):
    if event != "open" or not args or not isinstance(args[0], (str, bytes, Path)):
        return
    path = Path(args[0]).resolve()
    if ("2025" in str(path) or path in _deferred
            or path.suffix.lower() in {".nc", ".h5", ".hdf5", ".npy", ".npz", ".tif", ".tiff"}):
        raise PermissionError("Observations, real scaler/mask, sealed-year I/O forbidden")
    if path.suffix.lower() == ".csv" and path not in _csv:
        raise PermissionError("Only SHA-bound published metadata CSV allowed")
    if path.suffix.lower() in {".pt", ".pth", ".ckpt", ".part"}:
        allowed = _io.get()
        if allowed is None or not path.is_relative_to(allowed):
            raise PermissionError("Only current dedicated synthetic store I/O allowed")


def install_guard() -> None:
    global _installed
    if _installed:
        return
    inventory = public_inventory()
    _csv.update((ROOT / e["path"]).resolve() for e in inventory["checked_public_files"] if e["path"].endswith(".csv"))
    _deferred.update((ROOT / e["path"]).resolve() for e in inventory["deferred_observational_artifacts"])
    sys.addaudithook(_audit)
    def step(optimizer, *args, **kwargs):
        if _active_step.get() is not optimizer or type(optimizer) is not torch.optim.AdamW:
            raise PermissionError("Optimizer update outside bounded synthetic epoch transaction")
        return _step_original(optimizer, *args, **kwargs)
    for cls in list(vars(torch.optim).values()):
        if isinstance(cls, type) and issubclass(cls, torch.optim.Optimizer):
            cls.step = step
    def save(*args, **kwargs):
        if _io.get() is None:
            raise PermissionError("No synthetic store I/O scope")
        return _save_original(*args, **kwargs)
    def load(*args, **kwargs):
        if _io.get() is None or kwargs.get("weights_only") is not True:
            raise PermissionError("Synthetic weights_only read required")
        return _load_original(*args, **kwargs)
    torch.save, torch.load = save, load
    _installed = True


@contextmanager
def checkpoint_io(root: Path):
    root = root.resolve()
    if not root.is_relative_to(TEMP_ROOT.resolve()) or root == TEMP_ROOT.resolve():
        raise PermissionError("Dedicated temporary session only")
    token = _io.set(root)
    try:
        yield
    finally:
        _io.reset(token)


class Ledger:
    def __init__(self, *, metadata_fixture_path: Path | None = None):
        install_guard()
        self.path = TEMP_ROOT / "task_epoch_ledger.json" if metadata_fixture_path is None else metadata_fixture_path.resolve()
        if not self.path.is_relative_to(TEMP_ROOT.resolve()):
            raise PermissionError("Versioned synthetic ledger only")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("x", encoding="utf-8") as stream:
                json.dump({"campaign": "EPOCH_ENGINEERING_v1_MAX30", "source_sha": SOURCE_SHA, "code_sha": code_sha(),
                           "limits": LIMITS, "reserved": {}, "completed": {}, "failed": False,
                           "FORMAL_OPTIMIZER_STEPS": 0, "events": []}, stream)
        self.read()

    def read(self) -> dict:
        state = json.loads(self.path.read_text(encoding="utf-8"))
        if (state.get("campaign") != "EPOCH_ENGINEERING_v1_MAX30" or state.get("source_sha") != SOURCE_SHA
                or state.get("code_sha") != code_sha() or state.get("limits") != LIMITS
                or type(state.get("FORMAL_OPTIMIZER_STEPS")) is not int or state["FORMAL_OPTIMIZER_STEPS"] != 0
                or type(state.get("failed")) is not bool or set(state["reserved"]) - set(LIMITS)
                or set(state["completed"]) - set(state["reserved"])
                or any(type(v) is not int or not 0 <= v <= LIMITS[k] for k, v in state["reserved"].items())
                or any(type(v) is not int or not 0 <= v <= state["reserved"][k] for k, v in state["completed"].items())
                or sum(state["reserved"].values()) > 30):
            raise ValueError("Ledger identity/quota invalid; no reset or recovery")
        return state

    def mutate(self, key: str, *, event: dict, completion: bool = False, failed: bool = False):
        if key not in LIMITS:
            raise ValueError("Unknown campaign model/arm")
        lock = self.path.with_suffix(".lock")
        lock.open("x").close()
        try:
            state = self.read()
            if failed:
                state["failed"] = True
            elif completion:
                if state["completed"].get(key, 0) >= state["reserved"].get(key, 0):
                    raise ValueError("No pending update reservation")
                state["completed"][key] = state["completed"].get(key, 0) + 1
            else:
                if state["failed"] or state["reserved"].get(key, 0) >= LIMITS[key] or sum(state["reserved"].values()) >= 30:
                    raise PermissionError("Synthetic budget exhausted/failed; no retry or expansion")
                state["reserved"][key] = state["reserved"].get(key, 0) + 1
            state["events"].append({"key": key, "completion": completion, "failed": failed, **event})
            temporary = self.path.with_suffix(".json.tmp")
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(state, stream, indent=2); stream.flush(); os.fsync(stream.fileno())
            temporary.replace(self.path)
        finally:
            lock.unlink()

    def perform(self, optimizer: torch.optim.AdamW, key: str, event: dict):
        self.mutate(key, event=event)
        token = _active_step.set(optimizer)
        try:
            optimizer.step()
            self.mutate(key, event=event, completion=True)
        except BaseException:
            self.mutate(key, event=event, failed=True)
            raise
        finally:
            _active_step.reset(token)

