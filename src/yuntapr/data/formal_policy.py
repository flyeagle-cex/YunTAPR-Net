"""Researcher-approved v1.1 eligibility, independent of normalization fitting."""
from datetime import timedelta
from yuntapr.data.sample_schema import utc, select_latest_causal_frame

MISSING_LATEST = "EXPECTED_LATEST_B13_MISSING_NO_FORMAL_FALLBACK"


def require_phase_a_fit_time(window_start):
    t = utc(window_start)
    if t.year != 2023 or t.month not in range(3, 11):
        raise ValueError("PHASE_A_NORMALIZATION_FIT_REQUIRES_2023_MARCH_OCTOBER")


def select_formal_frame(frames, analysis_time):
    a = utc(analysis_time)
    expected = a - timedelta(minutes=10)
    present = [f for f in frames if utc(f.nominal_time) == expected and f.path.is_file()]
    if not present:
        raise ValueError(MISSING_LATEST)
    selected = select_latest_causal_frame(frames, a)
    if utc(selected.nominal_time) != expected:
        raise ValueError("EXPECTED_LATEST_NOT_LATEST_COMPLETED_CAUSAL")
    return selected


def require_full_valid(x, valid):
    import numpy as np
    if x.shape != (501, 501) or valid.shape != x.shape or valid.dtype != bool:
        raise ValueError("B13_NATIVE_SHAPE_OR_MASK_ERROR")
    if not valid.any():
        raise ValueError("B13_ALL_FILL_REJECT_SAMPLE")
    if not valid.all():
        raise ValueError("B13_PARTIAL_FORMAL_SUPERVISION_REJECTED")
    if not np.isfinite(x).all():
        raise ValueError("B13_NONFINITE_FORMAL_SUPERVISION_REJECTED")


def indexed_reject_reason(pair, frame, imerg):
    """Evaluate the hash-verified audit snapshot; raw fit reads recheck all B13 QC."""
    if pair["expected_status"] == "MISSING":
        return MISSING_LATEST
    if pair["pair_status"] == "TIME_METADATA_ERROR":
        return "TIME_METADATA_ERROR"
    if pair["pair_status"] == "NO_CAUSAL_FRAME":
        return "NO_CAUSAL_FRAME"
    if not frame or frame["status"] == "CORRUPT_OR_UNREADABLE":
        return "B13_UNREADABLE"
    if frame["status"] == "ALL_FILL":
        return "B13_ALL_FILL_REJECT_SAMPLE"
    if frame["status"] == "PARTIAL":
        return "B13_PARTIAL_FORMAL_SUPERVISION_REJECTED"
    try:
        start, end = utc(frame["obs_start"]), utc(frame["obs_end"])
        if start > end or end > utc(pair["analysis_time"]):
            return "TIME_METADATA_ERROR"
        if utc(pair["expected_nominal"]) != utc(pair["analysis_time"]) - timedelta(minutes=10):
            return "TIME_METADATA_ERROR"
    except (ValueError, TypeError):
        return "TIME_METADATA_ERROR"
    if pair["pair_status"] != "EXPECTED_LATEST_SLOT_AVAILABLE" or pair["selected_nominal"] != pair["expected_nominal"]:
        return MISSING_LATEST
    if frame["status"] != "FULL_VALID" or int(frame["valid_count"]) != 501 * 501:
        return "B13_QC_ERROR"
    if imerg["status"] != "VALID_TARGET_SLOT" or int(imerg["valid_yunnan_count"] or 0) <= 0:
        return "IMERG_INVALID_OR_NO_VALID_YUNNAN"
    return ""
