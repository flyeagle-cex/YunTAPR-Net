"""Development-only B13/QC audit rules; no threshold or training decisions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import calendar
import re
import numpy as np

from yuntapr.data.sample_schema import utc


H09_NAME = re.compile(r"^NC_H09_(\d{8})_(\d{4})_R21_FLDK\.06001_06001\.nc$")
TEN_MINUTES = timedelta(minutes=10)


def nominal_from_name(path: Path) -> datetime:
    match = H09_NAME.fullmatch(path.name)
    if match is None:
        raise ValueError(f"Unexpected H09 file name: {path.name}")
    nominal = datetime.strptime("_".join(match.groups()), "%Y%m%d_%H%M").replace(tzinfo=timezone.utc)
    if nominal.minute % 10:
        raise ValueError("Nominal time violates verified ten-minute cadence")
    return nominal


def expected_month_slots(year: int, month: int) -> list[datetime]:
    """Ten-minute H09 slots supported by Stage-0 index and verified names."""
    days = calendar.monthrange(year, month)[1]
    first = datetime(year, month, 1, tzinfo=timezone.utc)
    return [first + TEN_MINUTES * i for i in range(days * 144)]


def expected_latest_slot(analysis_time: datetime) -> datetime:
    analysis = utc(analysis_time)
    if analysis.minute not in (0, 30) or analysis.second or analysis.microsecond:
        raise ValueError("Analysis time must be an exact half-hour boundary")
    return analysis - TEN_MINUTES


def classify_pair(expected: dict | None, older: dict | None, analysis_time: datetime) -> str:
    """Expose missing latest slot rather than silently applying older fallback."""
    analysis = utc(analysis_time)
    if expected is not None:
        if expected.get("status") in ("METADATA_INVALID", "CORRUPT"):
            return "TIME_METADATA_ERROR" if expected["status"] == "METADATA_INVALID" else (
                "EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS" if older else "NO_CAUSAL_FRAME")
        if expected.get("status") == "READABLE" and expected.get("valid_count", 0) > 0:
            try:
                if utc(expected["obs_start"]) <= utc(expected["obs_end"]) <= analysis:
                    return "EXPECTED_LATEST_SLOT_AVAILABLE"
            except (KeyError, ValueError, TypeError):
                pass
            return "TIME_METADATA_ERROR"
    return "EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS" if older else "NO_CAUSAL_FRAME"


def support_counts(valid: np.ndarray, indices: np.ndarray) -> np.ndarray:
    if valid.shape != (501, 501) or indices.shape != (10000, 25):
        raise ValueError("Frozen SP04 support input dimensions mismatch")
    return valid.ravel()[indices].sum(axis=1, dtype=np.uint8)


def zone_masks(shape=(501, 501), edge_width=25) -> dict[str, np.ndarray]:
    """Disjoint audit zones; 25 native pixels is a descriptive band only."""
    if shape != (501, 501) or edge_width < 1 or edge_width * 2 >= min(shape):
        raise ValueError("Invalid native audit zone")
    zone = np.full(shape, "interior", dtype="<U8")
    zone[:edge_width, :] = "north"
    zone[-edge_width:, :] = "south"
    zone[edge_width:-edge_width, :edge_width] = "west"
    zone[edge_width:-edge_width, -edge_width:] = "east"
    return {name: zone == name for name in ("north", "south", "west", "east", "interior")}


def centikelvin_bins(values: np.ndarray) -> np.ndarray:
    """Packed H09 B13 is 0.01 K; rounded centikelvin retains exact bins."""
    packed = np.rint(np.asarray(values, dtype=np.float64) * 100).astype(np.int32)
    if packed.size and (packed.min() < 0 or packed.max() > 65535):
        raise ValueError("B13 physical range exceeds centikelvin audit histogram")
    return packed
