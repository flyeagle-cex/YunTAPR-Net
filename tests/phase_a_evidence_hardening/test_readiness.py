import pytest
from yuntapr.diagnostics.readiness import assess_entry


def metadata():
    return {"researcher_phase_a_acceptance": True, "independent_phase_b_approval": True,
            "preflight_passed": True, "dedicated_clean_checkout": True, "data_identity_verified": True,
            "scope": "V2_PHASE_B", "allowed_years": [2023, 2024], "allow_2025": False,
            "protocol_sha256": "a"*64}


def test_current_no_authorization_fail_closed():
    r = assess_entry({}, {"protocol_sha256": "a"*64}, resume=False)
    assert r["status"] == "CHECKLIST_GAPS" and not r["can_launch_formal_training"]


def test_even_consistent_synthetic_metadata_cannot_grant_authority():
    r = assess_entry(metadata(), {"protocol_sha256": "a"*64}, resume=False)
    assert not r["gaps"] and not r["can_launch_formal_training"] and r["RESEARCHER_DECISION_REQUIRED"]


@pytest.mark.parametrize("bad", [1, "true", False, None])
def test_truthy_nonbool_is_not_human_approval(bad):
    m = metadata(); m["independent_phase_b_approval"] = bad
    assert "independent_phase_b_approval" in assess_entry(m, {"protocol_sha256": "a"*64}, resume=False)["gaps"]


def test_sealed_year_cannot_be_included():
    m = metadata(); m["allowed_years"] = [2023, 2024, 2025]; m["allow_2025"] = True
    r = assess_entry(m, {"protocol_sha256": "a"*64}, resume=False)
    assert "scope_or_allowed_years" in r["gaps"] and "sealed_2025" in r["gaps"]


def test_sha_mismatch_and_empty_bindings():
    assert "identity:protocol_sha256" in assess_entry(metadata(), {"protocol_sha256": "b"*64}, resume=False)["gaps"]
    assert "empty_identity_binding" in assess_entry(metadata(), {}, resume=False)["gaps"]


def test_resume_requires_independent_last_and_completed_marker():
    r = assess_entry(metadata(), {"protocol_sha256": "a"*64}, resume=True)
    assert "independent_LAST_bound_approval" in r["gaps"] and "completed_epoch_marker" in r["gaps"]
    assert "resume_ancestry_binding" in r["gaps"]


def test_resume_still_does_not_launch():
    m = metadata() | {"independent_LAST_bound_approval": True, "completed_epoch_marker": True,
                      "restored_state_verified": True, "LAST_sha256": "b"*64,
                      "origin_authorization_sha256": "c"*64}
    r = assess_entry(m, {"protocol_sha256": "a"*64, "LAST_sha256": "b"*64, "origin_authorization_sha256": "c"*64}, resume=True)
    assert not r["gaps"] and not r["can_launch_formal_training"]


def test_resume_requires_explicit_bool():
    with pytest.raises(ValueError): assess_entry(metadata(), {}, resume="true")
