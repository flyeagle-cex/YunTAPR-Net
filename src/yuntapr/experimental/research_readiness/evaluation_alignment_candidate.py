"""Metadata-only alignment candidate; no loader, payload checks or event detection.

Inputs are caller-supplied identity claims. Equal fingerprints do not prove that
the caller read or understood their payloads. This module neither authorizes
data access nor turns calendar groups into independent weather events.
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import re


METHOD_STATUS = "PROPOSED_METADATA_ONLY_NOT_SCIENTIFIC_ACCEPTANCE"
EVENT_ID_STATUS = "NOT_IDENTIFIED"
_UTC_FORMAT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_DATE_FORMAT = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = frozenset({
    "scene_id", "scene_time_utc", "window_start_utc", "window_end_utc",
    "window_convention", "grid_sha256", "mask_sha256",
    "pixel_order_sha256", "pixel_count", "rate_unit",
})


@dataclass(frozen=True)
class SceneIdentity:
    scene_id: str
    scene_time_utc: str
    window_start_utc: str
    window_end_utc: str
    window_convention: str
    grid_sha256: str
    mask_sha256: str
    pixel_order_sha256: str
    pixel_count: int
    rate_unit: str


@dataclass(frozen=True)
class CalendarDay:
    date_utc: str
    scene_indices: tuple[int, ...]


@dataclass(frozen=True)
class AlignmentResult:
    scenes: tuple[SceneIdentity, ...]
    calendar_days: tuple[CalendarDay, ...]
    adjacent_scene_gaps_seconds: tuple[int, ...]
    contiguous_half_hour_windows: bool
    event_id_status: str = EVENT_ID_STATUS
    evidence_scope: str = "CALLER_METADATA_ONLY_NOT_PAYLOAD_VERIFIED"
    method_status: str = METHOD_STATUS
    calendar_group_basis: str = "SCENE_TIMESTAMP_UTC"
    scene_timestamp_role: str = "CALLER_MATCHING_KEY_NOT_BOUND_TO_REFERENCE_ENDPOINT"
    reference_window_extent_verified: bool = False
    reference_window_timestamp_relation_verified: bool = False


def _utc(value, field):
    if not isinstance(value, str) or not _UTC_FORMAT.fullmatch(value):
        raise ValueError(f"{field}: canonical YYYY-MM-DDTHH:MM:SSZ required")
    try:
        stamp = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError(f"{field}: invalid UTC timestamp") from error
    if stamp.year != 2024:
        raise ValueError(f"{field}: only 2024 metadata admitted")
    return stamp


def _day(value, field):
    if not isinstance(value, str) or not _DATE_FORMAT.fullmatch(value):
        raise ValueError(f"{field}: explicit YYYY-MM-DD required")
    try:
        result = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field}: invalid date") from error
    if result.year != 2024:
        raise ValueError(f"{field}: only 2024 calendar admitted")
    return result


def _identity(row, side, index):
    name = f"{side}[{index}]"
    if not isinstance(row, Mapping) or set(row) != _FIELDS:
        raise ValueError(f"{name}: exact declared metadata fields required")
    scene_id = row["scene_id"]
    if not isinstance(scene_id, str) or not scene_id or scene_id != scene_id.strip():
        raise ValueError(f"{name}: explicit nonempty scene_id required")
    for field in ("grid_sha256", "mask_sha256", "pixel_order_sha256"):
        value = row[field]
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise ValueError(f"{name}.{field}: canonical lowercase SHA256 required")
    if type(row["pixel_count"]) is not int or row["pixel_count"] <= 0:
        raise ValueError(f"{name}: positive integer pixel_count required")
    if row["rate_unit"] != "mm/h":
        raise ValueError(f"{name}: explicit mm/h required; no unit conversion")
    if row["window_convention"] != "START_INCLUSIVE_END_EXCLUSIVE":
        raise ValueError(f"{name}: explicit half-open window convention required")
    stamp = _utc(row["scene_time_utc"], name + ".scene_time_utc")
    start = _utc(row["window_start_utc"], name + ".window_start_utc")
    end = _utc(row["window_end_utc"], name + ".window_end_utc")
    if end - start != timedelta(minutes=30):
        raise ValueError(f"{name}: exact 30-minute reference window required")
    return SceneIdentity(**dict(row)), stamp, start, end


def validate_alignment(predictions, labels, *, expected_scene_ids,
                       first_day_utc, last_day_utc):
    """Require exact paired identities without sorting, joining or dropping rows.

    ``scene_time_utc`` is an explicitly supplied matching timestamp, not an
    inferred GFS release time or reference-window endpoint. Both sides must
    declare identical actual reference windows. Nonoverlap is checked, but no
    relation between that timestamp and either window endpoint is invented.

    The caller supplies a separately frozen ordered scene-ID manifest and the
    calendar extent; empty days remain empty groups. The manifest itself is a
    caller claim, not independently verified here. Omitting the same scene on
    both sides fails against that declared manifest.
    A half-hour continuity flag describes sampled windows only, never storm
    independence. No missing observation outside the declared manifest can be
    inferred from a sparse calendar.

    Calendar groups use scene timestamps. This candidate does not establish
    whether those timestamps are window starts, ends or another matching key,
    or whether reference windows lie inside the declared calendar extent.
    Returned flags make those unresolved semantics explicit. A real-data
    integration must first freeze the timestamp role and cross-day rules.
    """
    first = _day(first_day_utc, "first_day_utc")
    last = _day(last_day_utc, "last_day_utc")
    if last < first:
        raise ValueError("Calendar end precedes start")
    for rows in (predictions, labels):
        if (not isinstance(rows, Sequence) or isinstance(rows, (str, bytes))
                or not len(rows)):
            raise ValueError("Nonempty explicit metadata sequences required")
    if len(predictions) != len(labels):
        raise ValueError("Missing paired scenes: sequence lengths differ")
    if (not isinstance(expected_scene_ids, Sequence)
            or isinstance(expected_scene_ids, (str, bytes))
            or not len(expected_scene_ids)
            or any(not isinstance(item, str) or not item or item != item.strip()
                   for item in expected_scene_ids)):
        raise ValueError("Explicit frozen ordered scene-ID manifest required")
    expected = tuple(expected_scene_ids)
    if len(set(expected)) != len(expected):
        raise ValueError("Duplicate scene in declared manifest")
    if len(predictions) != len(expected):
        raise ValueError("Missing or extra scenes relative to declared manifest")
    scenes, stamps, windows = [], [], []
    seen_ids = set()
    for index, (prediction, label) in enumerate(zip(predictions, labels)):
        p, stamp, start, end = _identity(prediction, "predictions", index)
        truth, _, _, _ = _identity(label, "labels", index)
        if p != truth:
            raise ValueError(f"Scene {index}: prediction/label identity mismatch")
        if p.scene_id != expected[index]:
            raise ValueError(f"Scene {index}: declared manifest order or membership mismatch")
        if p.scene_id in seen_ids:
            raise ValueError("Duplicate scene_id; no deduplication")
        if not first <= stamp.date() <= last:
            raise ValueError("Scene outside declared calendar")
        if stamps and stamp <= stamps[-1]:
            raise ValueError("Scene timestamps must be strictly increasing; no sorting")
        if windows and start < windows[-1][1]:
            raise ValueError("Reference windows overlap or are out of order")
        seen_ids.add(p.scene_id)
        scenes.append(p)
        stamps.append(stamp)
        windows.append((start, end))
    gaps = tuple(int((b - a).total_seconds()) for a, b in zip(stamps, stamps[1:]))
    contiguous = bool(gaps) and all(gap == 1800 for gap in gaps) and all(
        right[0] == left[1] for left, right in zip(windows, windows[1:]))
    by_day = {}
    for index, stamp in enumerate(stamps):
        by_day.setdefault(stamp.date(), []).append(index)
    days = tuple(CalendarDay((first + timedelta(days=i)).isoformat(),
                             tuple(by_day.get(first + timedelta(days=i), ())))
                 for i in range((last - first).days + 1))
    return AlignmentResult(tuple(scenes), days, gaps, contiguous)
