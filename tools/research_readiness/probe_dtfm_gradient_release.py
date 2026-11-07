"""Bounded CPU graph-reachability check of the unchanged B7/B8 fusion.

All tensors and parameters are synthetic and remain in memory. The optimizer
is an explicitly artificial SGD probe, not the scientific AdamW trajectory.
There is no data reader, checkpoint loader, model selection, or file output.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.stage2.fusion import paired_fusion_candidates


SEED = 20261107
UPDATES_PER_ARM = 5
LEARNING_RATE = 0.01
BLOCKS = ("fuse", "mix", "modulation", "gfs", "terrain")


def tensor_statistics(value: torch.Tensor) -> dict:
    value = value.detach()
    if value.device.type != "cpu" or not bool(torch.isfinite(value).all()):
        raise FloatingPointError("Finite CPU probe tensor required")
    return {
        "finite": True,
        "l2": float(value.double().square().sum().sqrt()),
        "max_abs": float(value.abs().max()),
        "nonzero": int(torch.count_nonzero(value)),
        "elements": value.numel(),
    }


def state_digest(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in model.state_dict().items():
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(str(tuple(value.shape)).encode("ascii") + b"\0")
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def block_statistics(model, before) -> dict:
    result = {}
    for block in BLOCKS:
        parameters = [(name, value) for name, value in model.named_parameters()
                      if name.startswith(block + ".")]
        if not parameters:
            continue
        if any(value.grad is None for _, value in parameters):
            raise RuntimeError("Missing probe gradient in " + block)
        result[block] = {
            "gradient_is_none": False,
            "gradient": tensor_statistics(torch.cat([
                value.grad.detach().flatten() for _, value in parameters])),
            "parameter": tensor_statistics(torch.cat([
                value.detach().flatten() for _, value in parameters])),
            "update_delta": tensor_statistics(torch.cat([
                (value.detach() - before[name]).flatten()
                for name, value in parameters])),
        }
    return result


def run_arm(model, feature, environment, terrain, target, grid, mask) -> dict:
    initial_state = state_digest(model)
    optimizer = torch.optim.SGD(model.parameters(), lr=LEARNING_RATE,
                                momentum=0.0, weight_decay=0.0)
    captured = {}

    def capture_affine(_module, _inputs, output):
        captured["affine"] = output.detach()

    handle = None
    if model.modulation is not None:
        handle = model.modulation.projections[0].register_forward_hook(capture_affine)
    records = []
    try:
        for update in range(1, UPDATES_PER_ARM + 1):
            before = {name: value.detach().clone()
                      for name, value in model.named_parameters()}
            optimizer.zero_grad(set_to_none=True)
            output = model(
                [feature], [environment], [terrain], [mask], [mask], [mask],
                feature_grids=[grid], gfs_grids=[grid], terrain_grids=[grid],
            ).values[0]
            loss = (output - target).square().mean()
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("Nonfinite synthetic objective")
            loss.backward()
            residual = tensor_statistics(output - feature)
            modulation = None
            if "affine" in captured:
                gamma, beta = captured["affine"].chunk(2, dim=1)
                limit = model.modulation.modulation_limit
                modulation = {
                    "gamma": tensor_statistics(limit * torch.tanh(gamma)),
                    "beta": tensor_statistics(limit * torch.tanh(beta)),
                    "tanh_saturation_fraction": float(
                        (torch.tanh(captured["affine"]).abs() >= 0.99).double().mean()),
                }
            # Gradients are recorded before any clipping or optimizer change.
            gradients = block_statistics(model, before)
            optimizer.step()
            after = block_statistics(model, before)
            records.append({
                "backward_update": update,
                "synthetic_mse": float(loss.detach()),
                "residual_before_update": residual,
                "modulation_before_update": modulation,
                "blocks": {
                    block: {
                        "gradient_is_none": gradients[block]["gradient_is_none"],
                        "gradient": gradients[block]["gradient"],
                        "parameter_before": gradients[block]["parameter"],
                        "update_delta": after[block]["update_delta"],
                    } for block in gradients
                },
            })
    finally:
        if handle is not None:
            handle.remove()
    first_nonzero = {
        block: next((row["backward_update"] for row in records
                     if row["blocks"][block]["gradient"]["nonzero"] > 0), None)
        for block in records[0]["blocks"]
    }
    released = all(value is not None for value in first_nonzero.values())
    return {
        "initial_state_sha256": initial_state,
        "final_state_sha256": state_digest(model),
        "fusion_parameters": sum(value.numel() for value in model.parameters()),
        "first_nonzero_gradient_backward": first_nonzero,
        "verdict": "RELEASE_OBSERVED" if released else "NOT_OBSERVED_WITHIN_BOUND",
        "steps": records,
    }


def run_probe() -> dict:
    previous_threads = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        with torch.random.fork_rng(devices=[]):
            generator = torch.Generator(device="cpu").manual_seed(SEED)
            torch.set_rng_state(generator.get_state())
            b7, b8 = paired_fusion_candidates(
                feature_channels=[48], gfs_channels=[26], terrain_channels=[28],
                projection_width=16, modulation_limit=0.1,
            )
            for block in ("gfs", "terrain", "fuse"):
                left = getattr(b7, block).state_dict()
                right = getattr(b8, block).state_dict()
                if any(not torch.equal(value, right[name]) for name, value in left.items()):
                    raise RuntimeError("Shared initialization mismatch in " + block)
            generator.manual_seed(SEED + 1)
            feature = torch.randn(2, 48, 9, 9, generator=generator)
            environment = torch.cat((torch.randn(2, 13, 9, 9, generator=generator),
                                     torch.ones(2, 13, 9, 9)), dim=1)
            terrain = torch.cat((torch.randn(2, 6, 9, 9, generator=generator),
                                 torch.ones(2, 6, 9, 9),
                                 torch.randn(2, 8, 9, 9, generator=generator),
                                 torch.ones(2, 8, 9, 9)), dim=1)
            target = feature + 0.2 * torch.randn(feature.shape, generator=generator)
            mask = torch.ones(2, 1, 9, 9, dtype=torch.bool)
            grid = GridSpec(np.linspace(24.0, 24.08, 9), np.linspace(101.0, 101.08, 9))
            results = {
                kind: run_arm(model, feature, environment, terrain, target, grid, mask)
                for kind, model in (("B7", b7), ("B8", b8))
            }
    finally:
        torch.set_num_threads(previous_threads)
    return {
        "SYNTHETIC_GRADIENT_PATH_CHECK": (
            "PASS" if all(row["verdict"] == "RELEASE_OBSERVED"
                          for row in results.values()) else "INCONCLUSIVE"),
        "scope": "CPU_SYNTHETIC_FUSION_GRAPH_ONLY",
        "torch_version": torch.__version__,
        "seed": SEED,
        "input_shape": [2, 48, 9, 9],
        "device": "cpu",
        "dtype": str(feature.dtype),
        "threads_during_probe": 1,
        "condition_channels": [26, 28],
        "condition_value_masks": "synthetic value channels and explicit all-one indicator channels",
        "initialization": "unchanged paired_fusion_candidates, no manual parameter assignment",
        "optimizer": {"kind": "SGD", "lr": LEARNING_RATE, "momentum": 0.0,
                      "weight_decay": 0.0, "scientific_AdamW_trajectory": False},
        "updates_per_arm": UPDATES_PER_ARM,
        "synthetic_optimizer_step_calls": 2 * UPDATES_PER_ARM,
        "scientific_optimizer_updates": 0,
        "scientific_payload_reads": 0,
        "real_training_cause": "NOT_VERIFIED",
        "performance_improvement": "NOT_VERIFIED",
        "models": results,
    }


if __name__ == "__main__":
    json.dump(run_probe(), sys.stdout, ensure_ascii=False, indent=2, allow_nan=False)
    sys.stdout.write("\n")
