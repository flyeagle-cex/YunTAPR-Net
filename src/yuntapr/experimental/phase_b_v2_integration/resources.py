"""Resource admission before construction; thresholds are engineering limits."""
from __future__ import annotations
import ctypes
import os
import shutil
from pathlib import Path
import torch

GIB = 1024 ** 3


class ResourceLimit(RuntimeError):
    """Stop this test without changing batch, precision, seed or architecture."""


def host_available_bytes() -> int:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in
                ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual", "avail_virtual", "extended")]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise ResourceLimit("Cannot establish host memory availability")
        return int(status.avail_phys)
    # Linux /proc contains OS resource metadata, never scientific observations.
    with open("/proc/meminfo", encoding="ascii") as stream:
        entries = dict(line.split(":", 1) for line in stream)
    return int(entries["MemAvailable"].split()[0]) * 1024


def resource_snapshot(*, full_backward: bool) -> dict:
    if type(full_backward) is not bool:
        raise ValueError("Explicit resource scope required")
    result = {"scope": "SYNTHETIC_ENGINEERING_ONLY", "host_available_bytes": host_available_bytes(),
              "workspace_free_bytes": shutil.disk_usage(Path(__file__).resolve().parents[4]).free,
              "minimum_host_bytes": (8 if full_backward else 2) * GIB,
              "minimum_workspace_bytes": GIB, "full_backward": full_backward}
    if full_backward:
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise ResourceLimit("CUDA BF16 unavailable; no CPU/precision fallback")
        free, total = torch.cuda.mem_get_info(0)
        result.update(cuda_free_bytes=free, cuda_total_bytes=total, minimum_cuda_free_bytes=5 * GIB,
                      cuda_name=torch.cuda.get_device_name(0), torch_version=torch.__version__,
                      cuda_build=torch.version.cuda)
    return result


def require_resources(snapshot: dict) -> None:
    for actual, minimum in (("host_available_bytes", "minimum_host_bytes"),
                            ("workspace_free_bytes", "minimum_workspace_bytes")):
        if type(snapshot.get(actual)) is not int or snapshot[actual] < snapshot[minimum]:
            raise ResourceLimit("Insufficient resource: " + actual)
    if snapshot["full_backward"] and snapshot["cuda_free_bytes"] < snapshot["minimum_cuda_free_bytes"]:
        raise ResourceLimit("Insufficient CUDA memory; do not reduce batch or precision")

