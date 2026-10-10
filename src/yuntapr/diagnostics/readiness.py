"""Fail-closed preparation checklist simulator. Never grants launch authority.

This isolated engineering reference is NOT wired into a formal Phase-B runner.
Boolean fields are evidence of intent only; human identity cannot be inferred
from a JSON field. The result always requires independent researcher review.
"""
from collections.abc import Mapping
import re


def assess_entry(metadata: Mapping[str, object], expected_sha256: Mapping[str, str],
                 *, resume: bool) -> dict[str, object]:
    if type(resume) is not bool:
        raise ValueError("Explicit bool resume required")
    gaps = []
    for field in ("researcher_phase_a_acceptance", "independent_phase_b_approval",
                  "preflight_passed", "dedicated_clean_checkout", "data_identity_verified"):
        if metadata.get(field) is not True:
            gaps.append(field)
    if metadata.get("scope") != "V2_PHASE_B" or metadata.get("allowed_years") != [2023, 2024]:
        gaps.append("scope_or_allowed_years")
    if metadata.get("allow_2025") is not False:
        gaps.append("sealed_2025")
    if not expected_sha256:
        gaps.append("empty_identity_binding")
    for name, sha in expected_sha256.items():
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha) or metadata.get(name) != sha:
            gaps.append("identity:" + name)
    if resume:
        for field in ("independent_LAST_bound_approval", "completed_epoch_marker", "restored_state_verified"):
            if metadata.get(field) is not True:
                gaps.append(field)
        if "LAST_sha256" not in expected_sha256 or "origin_authorization_sha256" not in expected_sha256:
            gaps.append("resume_ancestry_binding")
    return {"status": "CHECKLIST_GAPS" if gaps else "SYNTHETIC_CHECKLIST_CONSISTENT",
            "gaps": sorted(set(gaps)), "can_launch_formal_training": False,
            "scope": "PREPARATION_ONLY", "RESEARCHER_DECISION_REQUIRED": True}
