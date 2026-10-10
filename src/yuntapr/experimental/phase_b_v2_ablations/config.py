"""Three closed, unapproved loss conditions and 18 candidate run identities."""
from __future__ import annotations
from dataclasses import dataclass
import math

_PARAMETERS = {"E0": (.5, 2., 1.), "E1": (.5, 0., 1.), "E2": (.5, 2., 2.)}
MODELS = ("B0_MATCHED_V2", "B1_V2")
SEEDS = (2026, 2027, 2028)
PROTOCOL_STATUS = "PROPOSED_FOR_RESEARCHER_APPROVAL"


def finite_number(name: str, value: object) -> float:
    """Reject booleans, strings, NaN and infinity rather than silently coerce."""
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name}: finite Python int/float required, excluding bool")
    return float(value)


@dataclass(frozen=True)
class AblationConfig:
    experiment_id: str
    alpha: float
    gamma: float
    lambda_q: float

    def __post_init__(self) -> None:
        if type(self.experiment_id) is not str or self.experiment_id not in _PARAMETERS:
            raise ValueError("Unknown experiment ID; only E0/E1/E2 are candidates")
        values = tuple(finite_number(k, getattr(self, k)) for k in ("alpha", "gamma", "lambda_q"))
        if values != _PARAMETERS[self.experiment_id]:
            raise ValueError("Experiment parameters do not match the closed candidate condition")


def get_config(experiment_id: str) -> AblationConfig:
    if type(experiment_id) is not str or experiment_id not in _PARAMETERS:
        raise ValueError("Unknown experiment ID; no parameter search or automatic selection")
    return AblationConfig(experiment_id, *_PARAMETERS[experiment_id])


@dataclass(frozen=True)
class RunSpec:
    experiment_id: str
    model: str
    seed: int

    def __post_init__(self) -> None:
        get_config(self.experiment_id)
        if type(self.model) is not str or self.model not in MODELS:
            raise ValueError("Unknown candidate model identity")
        if type(self.seed) is not int or self.seed not in SEEDS:
            raise ValueError("Candidate seeds are exactly 2026/2027/2028")

    @property
    def run_id(self) -> str:
        return f"{self.experiment_id}__{self.model}__s{self.seed}"

    @property
    def stage(self) -> int:
        return 1 if self.seed == 2026 else 2


def proposed_runs() -> tuple[RunSpec, ...]:
    return tuple(RunSpec(arm, model, seed) for seed in SEEDS for arm in _PARAMETERS for model in MODELS)


def workload() -> dict[str, int]:
    """Pure arithmetic; these counts do not mean that any updates took place."""
    train_batches, val_batches = (10455 + 1) // 2, (10501 + 7) // 8
    return {"runs": 18, "epochs": 9, "updates_per_epoch": train_batches,
            "updates_per_run": 9 * train_batches, "updates_total": 18 * 9 * train_batches,
            "validation_batches_per_epoch": val_batches, "validation_batches_total": 18 * 9 * val_batches,
            "stage1_updates": 6 * 9 * train_batches, "stage2_updates": 12 * 9 * train_batches}


def learning_rate_prefix(update: int) -> float:
    """First nine epochs of the original 50-epoch trajectory, no optimizer."""
    if type(update) is not int or not 1 <= update <= 47052:
        raise ValueError("Candidate one-based update must be in [1,47052]")
    if update <= 5228:
        return 1e-4 * (update / 5228)  # warmup is not clamped to the cosine floor
    progress = (update - 5228) / (261400 - 5228)
    return 1e-6 + (1e-4 - 1e-6) * (1 + math.cos(math.pi * progress)) / 2
