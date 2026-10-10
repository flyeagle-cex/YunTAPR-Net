"""Process-local guards for synthetic tests; not a security sandbox."""
from __future__ import annotations
from contextlib import contextmanager, ExitStack
from pathlib import Path
import hashlib
import json
import os
import re
import sys
from unittest.mock import patch
import torch
from .pins import REPO, REFERENCE, REFERENCE_SHA

RAW_SUFFIXES = {".nc", ".nc4", ".h5", ".hdf", ".hdf5", ".grib", ".grb", ".tif", ".tiff",
                ".pt", ".pth", ".ckpt", ".npy", ".npz"}
ALLOWED_CSV_PATHS = {(REPO / "config/spatial" / name).resolve() for name in
                     ("sp04_coordinate_axes_v1.csv", "sp04_target_cell_membership_v1.csv")}


def reject_restricted_path(value: object) -> None:
    if not isinstance(value, (str, bytes, Path)):
        return  # integer file descriptor, not a new named scientific file
    decoded = os.fsdecode(value) if isinstance(value, bytes) else str(value)
    name = decoded.replace("\\", "/").lower()
    suffix = Path(name).suffix
    if suffix in RAW_SUFFIXES or re.search(r"(^|[/_.-])2025([/_.-]|$)", name):
        raise PermissionError("Synthetic guard forbids raw, checkpoint or sealed-year file access")
    if suffix == ".csv" and Path(decoded).resolve() not in ALLOWED_CSV_PATHS:
        raise PermissionError("Only exact pinned public metadata CSV paths are allowed")


def install_process_file_guard() -> None:
    """Irreversible in this disposable process; install before model construction."""
    reference = REPO / REFERENCE
    raw = reference.read_bytes()
    if hashlib.sha256(raw).hexdigest() != REFERENCE_SHA:
        raise ValueError("Source identity changed before constructing the file allowlist")
    for item in json.loads(raw)["repository_files"]:
        path = (REPO / item["path"]).resolve()
        if not path.is_relative_to(REPO.resolve()):
            raise PermissionError("External source reference is not a public metadata file")
        if path.suffix.lower() == ".csv":
            ALLOWED_CSV_PATHS.add(path)
    def audit(event: str, args: tuple) -> None:
        if event == "open" and args:
            reject_restricted_path(args[0])
    sys.addaudithook(audit)


def denied_operation(*args: object, **kwargs: object) -> None:
    raise PermissionError("Synthetic scope forbids optimizer update, state load/save and physical materialization")


@contextmanager
def synthetic_operation_guards():
    """No optimizer instance is needed; prohibit every available step method."""
    with ExitStack() as stack:
        for cls in vars(torch.optim).values():
            if isinstance(cls, type) and issubclass(cls, torch.optim.Optimizer) and hasattr(cls, "step"):
                stack.enter_context(patch.object(cls, "step", denied_operation))
        for owner, name in ((torch, "load"), (torch, "save"), (torch, "expm1"), (torch.Tensor, "expm1"),
                            (torch.nn.Module, "load_state_dict")):
            stack.enter_context(patch.object(owner, name, denied_operation))
        yield
