"""Build a common-scene manifest from in-memory, fictitious 2001 metadata."""

from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import re

from ..core_innovation.stage2 import OFFSETS
from .final_test_draft import validate_synthetic_alignment


IDENTITY_FIELDS = (
    "sp04_grid_sha256",
    "supervision_mask_sha256",
    "static_sha256",
    "train_scalers_sha256",
)


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("A lowercase SHA-256 identity is required")
    return value


def _utc(value):
    timestamp = datetime.fromisoformat(value)
    if timestamp.year != 2001:
        raise PermissionError("Every fixture timestamp must belong to synthetic 2001")
    if timestamp.utcoffset() != timedelta(0):
        raise ValueError("An explicit UTC timestamp is required")
    return timestamp


def _bind_scene(row, expected_identity):
    analysis = _utc(row["analysis_time"])
    target_start = _utc(row["target_start"])
    if analysis.microsecond or target_start != analysis - timedelta(minutes=30):
        raise ValueError("Expected a half-hour target ending at exact UTC analysis time")
    if row["identity"] != expected_identity:
        raise ValueError("SP04, supervision, static or Train scaler identity mismatch")
    sample_id = row["sample_id"]
    if not isinstance(sample_id, str) or not sample_id:
        raise ValueError("A nonempty synthetic sample ID is required")

    satellite = []
    previous_end = None
    for slot, offset in zip(row["satellite"], OFFSETS, strict=True):
        nominal = _utc(slot["nominal_time"])
        start = _utc(slot["obs_start"])
        end = _utc(slot["obs_end"])
        if nominal != analysis - timedelta(minutes=offset) or not (start <= end <= analysis):
            raise ValueError("Satellite nominal slot or CF observation interval mismatch")
        if previous_end is not None and end <= previous_end:
            raise ValueError("Satellite observation ends must increase")
        previous_end = end
        satellite.append(dict(nominal_time=nominal.isoformat(), obs_start=start.isoformat(),
                              obs_end=end.isoformat(), grid_sha256=_sha(slot["grid_sha256"]),
                              source_sha256=_sha(slot["source_sha256"])))
    if len({slot["source_sha256"] for slot in satellite}) != len(OFFSETS):
        raise ValueError("Expected six distinct satellite sources")
    if len({slot["grid_sha256"] for slot in satellite}) != 1:
        raise ValueError("Satellite native grid differs between slots")

    if set(row["gfs"]) != {"main", "thermo"}:
        raise ValueError("Expected both GFS main and thermo sources")
    gfs = {}
    for kind, source in row["gfs"].items():
        init = _utc(source["init_time"])
        valid = _utc(source["valid_time"])
        if init != analysis - timedelta(hours=6) or valid != analysis or source["lead_hours"] != 6:
            raise ValueError("Each GFS source must be f006 valid at analysis time")
        gfs[kind] = dict(init_time=init.isoformat(), valid_time=valid.isoformat(),
                         lead_hours=6, grid_sha256=_sha(source["grid_sha256"]),
                         source_sha256=_sha(source["source_sha256"]))
    if gfs["main"]["grid_sha256"] != gfs["thermo"]["grid_sha256"]:
        raise ValueError("GFS main and thermo native grid mismatch")
    if gfs["main"]["source_sha256"] == gfs["thermo"]["source_sha256"]:
        raise ValueError("Expected distinct GFS main and thermo sources")

    imerg = row["imerg"]
    window_start = _utc(imerg["window_start"])
    window_end = _utc(imerg["window_end"])
    source_date = date.fromisoformat(imerg["source_date"])
    if source_date.year != 2001:
        raise PermissionError("IMERG daily source date must belong to synthetic 2001")
    half_hour = target_start.hour * 2 + target_start.minute // 30
    if (window_start, window_end, source_date, imerg["half_hour_index"]) != (
        target_start, analysis, target_start.date(), half_hour
    ):
        raise ValueError("IMERG half-hour window, source date or index mismatch")
    if (imerg["product"], imerg["units"]) != ("IMERG_V07_Final", "mm/h"):
        raise ValueError("Expected IMERG V07 Final in mm/h")

    return dict(
        sample_id=sample_id, analysis_time=analysis.isoformat(), target_start=target_start.isoformat(),
        satellite=satellite, gfs=gfs,
        imerg=dict(product="IMERG_V07_Final", units="mm/h", window_start=window_start.isoformat(),
                   window_end=window_end.isoformat(), source_date=source_date.isoformat(),
                   half_hour_index=half_hour, source_sha256=_sha(imerg["source_sha256"])),
    )


def build_synthetic_common_manifest(rows_by_arm, *, expected_identity, range_anchor, end_month):
    """Intersect eligible fixture IDs after validating chronology and matching source identity."""
    if range_anchor not in ("target_start", "analysis_time") or end_month not in (9, 10):
        raise ValueError("An explicit synthetic range anchor and September/October end are required")
    if set(expected_identity) != set(IDENTITY_FIELDS):
        raise ValueError("Incomplete frozen geometry and preprocessing identity")
    identity = {field: _sha(expected_identity[field]) for field in IDENTITY_FIELDS}
    if len(rows_by_arm) < 2 or any(not isinstance(arm, str) or not arm for arm in rows_by_arm):
        raise ValueError("At least two distinctly named fixture arms are required")

    range_start = "2001-03-01T00:00:00+00:00"
    range_end = f"2001-{end_month + 1:02d}-01T00:00:00+00:00"
    all_rows = {}
    sample_by_target = {}
    eligible_by_arm = {}
    outside_range_by_arm = {}
    for arm, input_rows in sorted(rows_by_arm.items()):
        rows = list(input_rows)
        validate_synthetic_alignment(rows)
        eligible = set()
        outside = []
        for row in rows:
            scene = _bind_scene(row, identity)
            sample_id = scene["sample_id"]
            target = scene["target_start"]
            if sample_by_target.setdefault(target, sample_id) != sample_id:
                raise ValueError("One target window has multiple scene IDs")
            if all_rows.setdefault(sample_id, scene) != scene:
                raise ValueError("The same scene ID binds different sources across arms")
            if range_start <= scene[range_anchor] < range_end:
                eligible.add(sample_id)
            else:
                outside.append(sample_id)
        eligible_by_arm[arm] = eligible
        outside_range_by_arm[arm] = sorted(outside)

    intersection = set.intersection(*eligible_by_arm.values())
    union = set.union(*eligible_by_arm.values())
    scenes = sorted((all_rows[sample_id] for sample_id in intersection),
                    key=lambda scene: scene["target_start"])
    sources = {
        "satellite": {slot["source_sha256"] for scene in scenes for slot in scene["satellite"]},
        "gfs_main": {scene["gfs"]["main"]["source_sha256"] for scene in scenes},
        "gfs_thermo": {scene["gfs"]["thermo"]["source_sha256"] for scene in scenes},
        "imerg": {scene["imerg"]["source_sha256"] for scene in scenes},
    }
    manifest = dict(
        status="SYNTHETIC_METADATA_ONLY", fixture_year=2001, identity=identity,
        scope=dict(anchor=range_anchor, start_inclusive=range_start, end_exclusive=range_end),
        scenes=scenes, supervised_points_per_scene=3430,
        missing_in_arm={arm: sorted(union - eligible) for arm, eligible in eligible_by_arm.items()},
        outside_range_by_arm=outside_range_by_arm,
        common_source_counts={kind: len(hashes) for kind, hashes in sources.items()},
        real_population="NOT_VERIFIED", actual_inference_adapter="NOT_IMPLEMENTED",
        payload_access_authorized=False,
    )
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return dict(manifest, manifest_sha256=sha256(encoded).hexdigest())
