"""Pure candidate arithmetic and synthetic role checks; no dataset/model I/O."""
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


def _positive_int(value: int, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer, not bool")
    return value


@dataclass(frozen=True)
class Budget:
    scenes: int
    physical_batch: int
    epochs: int
    steps_per_epoch: int
    total_updates: int
    scene_presentations: int
    tail_batch_scenes: int


def budget(scenes: int, physical_batch: int, epochs: int) -> Budget:
    """No drop/duplicate/accumulation; this is NOT a scheduler or launch plan."""
    for name, value in (("scenes", scenes), ("batch", physical_batch), ("epochs", epochs)):
        _positive_int(value, name)
    steps = (scenes + physical_batch - 1) // physical_batch
    return Budget(scenes, physical_batch, epochs, steps, steps * epochs,
                  scenes * epochs, scenes % physical_batch or physical_batch)


def update_budget_parts(scenes: int, physical_batch: int, updates: int) -> tuple[int, int]:
    """Expose partial-epoch implications without making it a valid checkpoint."""
    one_epoch = budget(scenes, physical_batch, 1)
    _positive_int(updates, "updates")
    return divmod(updates, one_epoch.steps_per_epoch)


@dataclass(frozen=True)
class RoleSupport:
    sample_id: str
    role: str
    input_start: datetime
    analysis_time: datetime
    label_start: datetime
    label_end: datetime

    def bounds(self) -> tuple[datetime, datetime]:
        return min(self.input_start, self.label_start), max(self.analysis_time, self.label_end)


def check_role_supports(records: Iterable[RoleSupport]) -> None:
    """Reject cross-role overlapping support on tiny synthetic fixtures only.

    Time support conservatively spans earliest input through analysis/label end.
    Real eligibility still requires frozen per-frame obs_end and complete M1 slots;
    this helper does not open manifests, certify weather independence, or approve.
    """
    rows = list(records)
    if not rows:
        raise ValueError("Empty candidate partition")
    seen: set[str] = set()
    for row in rows:
        if not row.sample_id or row.sample_id in seen:
            raise ValueError("Missing/duplicate sample identity")
        seen.add(row.sample_id)
        if row.role not in {"Train", "Selection", "Calibration", "Report"}:
            raise ValueError("Explicit candidate role required")
        times = (row.input_start, row.analysis_time, row.label_start, row.label_end)
        if any(t.tzinfo is None or t.utcoffset() is None for t in times):
            raise ValueError("Timezone-aware supports required")
        if any(t.year not in {2023, 2024} for t in times):
            raise ValueError("Sealed/out-of-scope year")
        if not row.input_start < row.analysis_time or not row.label_start < row.label_end:
            raise ValueError("Invalid interval")
        if row.label_end != row.analysis_time:
            raise ValueError("Frozen analysis at label window end required")
    for index, left in enumerate(rows):
        a, b = left.bounds()
        for right in rows[index + 1:]:
            c, d = right.bounds()
            if left.role != right.role and max(a, c) < min(b, d):
                raise ValueError("Shared temporal support across candidate roles")


def single_factor_changes(baseline: dict, candidate: dict) -> set[str]:
    """Reject omitted control fields rather than silently accepting defaults."""
    if baseline.keys() != candidate.keys():
        raise ValueError("Control fields differ")
    return {key for key in baseline if baseline[key] != candidate[key]}
