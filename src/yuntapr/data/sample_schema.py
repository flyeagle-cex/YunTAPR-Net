"""B0 sample metadata and UTC causal frame selection."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np


def utc(value: datetime | str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Explicit UTC timestamp required")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class HimawariFrame:
    path: Path
    nominal_time: datetime
    obs_start: datetime
    obs_end: datetime
    date_created: datetime | None


def select_latest_causal_frame(frames: list[HimawariFrame], analysis_time: datetime) -> HimawariFrame:
    """Select latest completed observation; no implicit fallback or future frame."""
    a = utc(analysis_time)
    causal = []
    for frame in frames:
        start, end, nominal = utc(frame.obs_start), utc(frame.obs_end), utc(frame.nominal_time)
        if start > end:
            raise ValueError("Himawari observation interval inverted")
        if end <= a and nominal <= a:
            causal.append(frame)
    if not causal:
        raise ValueError("NO_COMPLETED_CAUSAL_HIMAWARI_FRAME")
    latest = max(utc(frame.obs_end) for frame in causal)
    tied = [frame for frame in causal if utc(frame.obs_end) == latest]
    return min(tied, key=lambda frame: str(frame.path))  # logged engineering tie breaker


@dataclass
class B0Sample:
    sample_id: str
    analysis_time: datetime
    imerg_window_start: datetime
    imerg_window_end: datetime
    himawari_path: Path
    himawari_nominal_time: datetime
    himawari_obs_start: datetime
    himawari_obs_end: datetime
    himawari_date_created: datetime | None
    x_b13: np.ndarray
    b13_valid_mask: np.ndarray
    y_imerg: np.ndarray | None
    imerg_valid_mask: np.ndarray | None
    yunnan_eval_mask: np.ndarray | None
    target_support_fraction: np.ndarray
    observation_eligible: bool
    supervised_eligible: bool
    inference_eligible: bool
    internal_test_eligible: bool
    external_validation_eligible: bool
    imerg_product: str | None
    imerg_version: str | None
    imerg_run_type: str | None
    imerg_provenance_verified: bool
    qc_status: str
    reject_reason: str | None
    b13_invalid_count: int
    b13_valid_fraction: float
    execution_scope: str = "ENGINEERING_ONLY"
    expected_latest_slot: datetime | None = None
    expected_latest_available: bool = False
    older_causal_available: bool = False
    used_older_causal_frame: bool = False
    b13_full_valid: bool = False
    formal_supervised_qc_pass: bool = False
    normalization_version: str | None = None
    normalization_mu: float | None = None
    normalization_sigma: float | None = None
    normalization_artifact_sha256: str | None = None
    x_b13_normalized: np.ndarray | None = None
    eligibility_scope: str = "ENGINEERING_ONLY"
