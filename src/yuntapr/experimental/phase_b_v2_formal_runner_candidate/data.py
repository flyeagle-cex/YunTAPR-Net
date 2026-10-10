"""Pathless artificial scenes, deterministic loader, and exhaustive ID receipts."""
from __future__ import annotations
from dataclasses import dataclass
import re
import torch
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.experimental.phase_b_v2_integration.synthetic import make_synthetic_pair
from yuntapr.experimental.phase_b_v2_integration.controls import synthetic_epoch_order
from . import SCOPE

ROLES = ("SYNTHETIC_TRAIN", "SYNTHETIC_DEVELOPMENT")


@dataclass(frozen=True)
class Scene:
    scene_id: str
    role: str
    x6: torch.Tensor
    rate: torch.Tensor
    native_valid: torch.Tensor
    reference_valid: torch.Tensor
    region_mask: torch.Tensor
    scope: str = SCOPE
    years: tuple = ()

    def validate(self) -> None:
        if (type(self.scene_id) is not str or re.fullmatch(SCOPE + r"/order_[0-9]{5}", self.scene_id) is None
                or self.role not in ROLES or self.scope != SCOPE or self.years != ()):
            raise ValueError("Artificial ID/role only; real identity claims forbidden")
        for name, shape, dtype in (("x6", (6, 501, 501), torch.float32), ("rate", (1, 100, 100), torch.float32),
                ("native_valid", (6, 501, 501), torch.bool), ("reference_valid", (1, 100, 100), torch.bool),
                ("region_mask", (1, 100, 100), torch.bool)):
            value = getattr(self, name)
            if (not isinstance(value, torch.Tensor) or value.shape != shape or value.dtype != dtype
                    or value.device.type != "cpu" or value.layout != torch.strided or value.requires_grad):
                raise ValueError("Scene tensor signature: " + name)
        if not bool(torch.isfinite(self.x6).all()) or not bool(torch.isfinite(self.rate).all()) or bool((self.rate < 0).any()):
            raise FloatingPointError("Nonfinite/negative scene")
        if not bool(self.native_valid.all()) or int((self.reference_valid & self.region_mask).sum()) != 3430:
            raise ValueError("M1/Q1 complete artificial support required; no scene skip")
        if int(self.region_mask.sum()) != 3430:
            raise ValueError("Artificial 3430-cell mask only")


class Registry:
    def __init__(self, scenes: tuple[Scene, ...]):
        if type(scenes) is not tuple or not scenes or any(type(s) is not Scene for s in scenes):
            raise ValueError("Exact artificial Scene tuple required; no external dataset/reader")
        for scene in scenes:
            scene.validate()
        if len({s.scene_id for s in scenes}) != len(scenes):
            raise ValueError("Duplicate IDs, including train/development overlap")
        self._scenes = {s.scene_id: s for s in scenes}
        if any(len(self.ids(role)) != 5 for role in ROLES):
            raise ValueError("Engineering profile: exactly five artificial scenes per role")
        self.identity_sha = self.digest()

    def ids(self, role: str) -> tuple[str, ...]:
        if role not in ROLES:
            raise ValueError("Unknown role")
        return tuple(sorted(s.scene_id for s in self._scenes.values() if s.role == role))

    def digest(self) -> str:
        return state_digest({k: vars(v) for k, v in sorted(self._scenes.items())})

    def check(self):
        if self.digest() != self.identity_sha:
            raise ValueError("Artificial registry mutated after identity freeze")

    def get(self, scene_id: str, role: str) -> Scene:
        scene = self._scenes[scene_id]
        if scene.role != role:
            raise ValueError("Train/development role mismatch")
        scene.validate()
        return scene


def artificial_registry() -> Registry:
    base = make_synthetic_pair()["B1_V2"]
    scenes = []
    for role in ROLES:
        for i in range(5):
            number = i if role == ROLES[0] else 10000 + i
            # Four dry train scenes guarantee an empty-rain batch regardless of
            # shuffle. This is a declared engineering fixture, no threshold fit.
            rate = base.rate[0].clone() if i == 2 or role == ROLES[1] else torch.zeros_like(base.rate[0])
            scenes.append(Scene(f"{SCOPE}/order_{number:05d}", role, base.x[0].clone() + .11 * i,
                rate, base.native_valid[0].clone(), base.reference_valid[0].clone(), base.region_mask[0].clone()))
    return Registry(tuple(scenes))


@dataclass(frozen=True)
class Batch:
    ids: tuple[str, ...]
    role: str
    x: torch.Tensor
    rate: torch.Tensor
    native_valid: torch.Tensor
    reference_valid: torch.Tensor
    region_mask: torch.Tensor


class Loader:
    """Deterministic, serial in-memory loader; no workers or observational I/O."""
    def __init__(self, registry: Registry, model: str, role: str, seed: int, epoch_index: int):
        if type(registry) is not Registry or model not in ("B0_MATCHED_V2", "B1_V2"):
            raise ValueError("Exact artificial registry/model required")
        registry.check()
        self.registry, self.model, self.role = registry, model, role
        ids = registry.ids(role)
        self.order = synthetic_epoch_order(ids, seed, epoch_index) if role == ROLES[0] else ids
        self.batch_size = 2 if role == ROLES[0] else 8

    def __iter__(self):
        for offset in range(0, len(self.order), self.batch_size):
            ids = self.order[offset:offset + self.batch_size]
            scenes = [self.registry.get(i, self.role) for i in ids]
            def stack(name):
                return torch.stack([getattr(s, name) for s in scenes])
            x, native = stack("x6"), stack("native_valid")
            if self.model == "B0_MATCHED_V2":
                x, native = x[:, -1:].clone(), native[:, -1:].clone()
            yield Batch(ids, self.role, x, stack("rate"), native, stack("reference_valid"), stack("region_mask"))


def to_cuda(batch: Batch) -> Batch:
    return Batch(batch.ids, batch.role, **{n: getattr(batch, n).to("cuda:0") for n in
                 ("x", "rate", "native_valid", "reference_valid", "region_mask")})


class Coverage:
    def __init__(self, expected: tuple[str, ...]):
        if type(expected) is not tuple or not expected or len(set(expected)) != len(expected):
            raise ValueError("Unique nonempty expected IDs required")
        self.expected, self.seen = expected, []

    def add(self, ids: tuple[str, ...]):
        if type(ids) is not tuple or not ids or any(i not in self.expected or i in self.seen for i in ids) or len(set(ids)) != len(ids):
            raise ValueError("Duplicate/unknown scene; cannot commit epoch")
        self.seen.extend(ids)

    def finish(self) -> dict:
        if len(self.seen) != len(self.expected) or set(self.seen) != set(self.expected):
            raise ValueError("Incomplete scene coverage")
        return {"expected_ids": list(self.expected), "visited_ids": list(self.seen), "exactly_once": True}

