"""Weights-only-compatible RNG snapshots and validated deterministic restore."""
from __future__ import annotations
import random
import numpy as np
import torch


def capture() -> dict:
    name, keys, pos, gauss, cache = np.random.get_state()
    return {"python": random.getstate(), "numpy": {"name": name, "keys": torch.tensor(keys.astype(np.int64)),
            "pos": pos, "gauss": gauss, "cache": cache}, "cpu": torch.get_rng_state(),
            "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}


def validate(state: dict) -> None:
    if type(state) is not dict or set(state) != {"python", "numpy", "cpu", "cuda"}:
        raise ValueError("RNG fields missing/unknown")
    probe = random.Random()
    probe.setstate(state["python"])  # local probe; does not change live RNG
    n = state["numpy"]
    if (set(n) != {"name", "keys", "pos", "gauss", "cache"} or n["name"] != "MT19937"
            or type(n["pos"]) is not int or not 0 <= n["pos"] <= 624 or n["gauss"] not in (0, 1)
            or type(n["cache"]) is not float or not np.isfinite(n["cache"])):
        raise ValueError("Invalid NumPy RNG metadata")
    if not isinstance(n["keys"], torch.Tensor) or n["keys"].dtype != torch.int64 or n["keys"].shape != (624,):
        raise ValueError("Invalid NumPy RNG keys")
    if bool(((n["keys"] < 0) | (n["keys"] > 2**32 - 1)).any()):
        raise ValueError("NumPy RNG key range")
    cpu = state["cpu"]
    if not isinstance(cpu, torch.Tensor) or cpu.dtype != torch.uint8 or cpu.device.type != "cpu":
        raise ValueError("Invalid CPU RNG bytes")
    torch.Generator().set_state(cpu)
    if type(state["cuda"]) is not list or len(state["cuda"]) != torch.cuda.device_count():
        raise ValueError("CUDA RNG device topology mismatch")
    for index, value in enumerate(state["cuda"]):
        if not isinstance(value, torch.Tensor) or value.dtype != torch.uint8 or value.device.type != "cpu":
            raise ValueError("Invalid CUDA RNG bytes")
        torch.Generator(device=f"cuda:{index}").set_state(value)


def restore(state: dict) -> None:
    validate(state)
    random.setstate(state["python"])
    n = state["numpy"]
    np.random.set_state((n["name"], n["keys"].cpu().numpy().astype(np.uint32), n["pos"], n["gauss"], n["cache"]))
    torch.set_rng_state(state["cpu"])
    if state["cuda"]:
        torch.cuda.set_rng_state_all(state["cuda"])

