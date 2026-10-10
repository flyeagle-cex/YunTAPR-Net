"""Only proposed JSON, synthetic metadata and integer workload are exercised."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from scripts.phase_b_v2_preregistration.review import (
    load_json, review_protocol, schema_errors, safe_reference_path, unique_object, reject_nonfinite)
from scripts.phase_b_v2_preregistration.budgets import run_rows, summary

OUT = REPO / "docs/phase_b_v2_ablation_preregistration/v1"


@pytest.fixture
def metadata():
    proposal = load_json(OUT / "protocol_proposed.json")
    schema = load_json(OUT / "protocol_schema.json")
    refs = [{"path":"config/synthetic_metadata.json","sha256":"a"*64}]
    observed = {refs[0]["path"]:refs[0]["sha256"]}
    return proposal,schema,refs,observed


def assess(metadata):
    proposal,schema,refs,observed = metadata
    return review_protocol(proposal,schema,identity_sha=proposal["source_identity_sha256"],
                           expected_refs=refs,observed_hashes=observed)


def test_valid_proposal_remains_blocked(metadata):
    result=assess(metadata)
    assert result.candidate_valid
    assert not result.can_launch_formal_training
    assert not result.runner_implemented
    assert len(result.blockers)==6


@pytest.mark.parametrize("path,value", [
    (("status",),"CANDIDATE"), (("status",),"APPROVED"), (("status",),"AUTHORIZED_TO_EXECUTE"),
    (("governance","V2_PHASE_B_AUTHORIZED"),True), (("governance","2025_RAW_ACCESS"),1),
    (("governance","2025_PIXELS_READ"),True), (("governance","HISTORICAL_RECOVERY_RATIFICATION"),"GRANTED"),
    (("controls","training","epochs"),10), (("controls","training","physical_batch"),True),
    (("controls","training","accumulation"),2), (("controls","training","drop_last"),True),
    (("controls","training","performance_early_stop"),True), (("controls","sealed_years"),[]),
    (("controls","train","year"),2025), (("controls","validation","year"),2025),
    (("controls","target","rain_label"),"float64_y>0.1"),
    (("controls","head","epsilon_w"),1e-6), (("controls","head","tau32"),.99),
    (("controls","normalizer","refit"),True), (("controls","seeds"),[2026]),
    (("controls","scheduler","U"),47052), (("controls","epoch_order_rule"),"2026_always"),
    (("controls","fresh","historical_state_transfer"),True),
    (("controls","validation_cadence"),"ENDPOINT_ONLY"), (("controls","auto_resume"),True),
    (("approvals","scientific_approval"),{"self_claimed":True}),
    (("approvals","integration_permission"),True), (("runner_implemented",),True),
])
def test_mutated_controls_cannot_be_promoted(metadata,path,value):
    cursor=metadata[0]
    for key in path[:-1]: cursor=cursor[key]
    cursor[path[-1]]=value
    result=assess(metadata)
    assert not result.candidate_valid
    assert not result.can_launch_formal_training


@pytest.mark.parametrize("operation",["missing_seed","duplicate_run","changed_gamma","changed_weight","extra_arm","removed_field","extra_field"])
def test_matrix_and_closed_fields(metadata,operation):
    proposal=metadata[0]
    if operation=="missing_seed": proposal["runs"]=proposal["runs"][:6]
    elif operation=="duplicate_run": proposal["runs"][-1]=deepcopy(proposal["runs"][0])
    elif operation=="changed_gamma": proposal["arms"][1]["gamma"]=1
    elif operation=="changed_weight": proposal["arms"][2]["lambda_q"]=3
    elif operation=="extra_arm": proposal["arms"].append({"id":"E3","alpha":.5,"gamma":2,"lambda_q":1})
    elif operation=="removed_field": del proposal["approvals"]
    else: proposal["approved"]=True
    assert not assess(metadata).candidate_valid


@pytest.mark.parametrize("observed",[None,{}, {"config/synthetic_metadata.json":"b"*64}])
def test_source_missing_or_mismatch(metadata,observed):
    proposal,schema,refs,_=metadata
    result=review_protocol(proposal,schema,identity_sha=proposal["source_identity_sha256"],expected_refs=refs,observed_hashes=observed)
    assert not result.candidate_valid and not result.can_launch_formal_training


def test_wrong_identity_manifest(metadata):
    proposal,schema,refs,observed=metadata
    result=review_protocol(proposal,schema,identity_sha="f"*64,expected_refs=refs,observed_hashes=observed)
    assert not result.candidate_valid and not result.can_launch_formal_training


def test_duplicate_refs_rejected(metadata):
    metadata[2].append(deepcopy(metadata[2][0]))
    assert not assess(metadata).candidate_valid


@pytest.mark.parametrize("path",["C:/raw/2025/data.nc","/tmp/source.py","config/../raw/source.csv",
    "docs/raw/source.csv","docs/2025/source.json","docs/weights/state.json","config/state.pt","config\\schema.json", "config//schema.json"])
def test_unsafe_source_path(path):
    assert not safe_reference_path(path)


@pytest.mark.parametrize("path",["config/example.json","src/yuntapr/losses/focal.py","docs/example/manifest.csv",
    "scripts/phase_b_v2_candidates/planning.py","scripts/phase_b_v2_candidates/build_delivery.py"])
def test_safe_static_source_path(path):
    assert safe_reference_path(path)


def test_unknown_schema_keyword_fails_closed(metadata):
    metadata[1]["$ref"]="#/some_unhandled_schema"
    assert not assess(metadata).candidate_valid


def test_duplicate_json_keys_rejected():
    with pytest.raises(ValueError,match="Duplicate"):
        unique_object([("status","PROPOSED_FOR_RESEARCHER_APPROVAL"),("status","APPROVED")])


@pytest.mark.parametrize("token",["NaN","Infinity","-Infinity"])
def test_non_json_numeric_constant(token):
    with pytest.raises(ValueError): json.loads(token,parse_constant=reject_nonfinite)


def test_malformed_proposal_rejected(metadata):
    result=review_protocol([],metadata[1])
    assert not result.candidate_valid and not result.can_launch_formal_training


def test_bool_not_equal_to_numeric_constant():
    assert schema_errors({"n":True},{"type":"object","const":{"n":1}})


def test_budget_matrix_and_stages():
    rows=run_rows(); totals=summary()
    assert len(rows)==18 and len({r["run_id"] for r in rows})==18
    assert totals["total_train_updates"]==846936
    assert totals["stage1_updates"]==282312 and totals["stage2_updates"]==564624
    assert totals["total_validation_batches"]==212706
    assert totals["endpoint_only_validation_batches_lower_bound"]==23634
    assert all(r["train_tail_batch"]==1 and r["validation_tail_batch"]==5 for r in rows)
    assert totals["checkpoint_count"]==162 and totals["six_fresh_anchors_parameter_bytes"]==103934640
    assert totals["dense_full_grid_qlog_endpoint_bytes_per_run"]==26882560000


def test_input_and_checkpoint_payload_are_not_measured():
    totals=summary()
    assert totals["gpu_hours"]=="NOT_YET_ESTABLISHED"
    assert totals["actual_checkpoint_bytes"]=="NOT_YET_MEASURED"
    assert totals["one_yunnan_diagnostic_variable_bytes"]==288147440
    assert totals["train_input_float32_presented_bytes"]==9*94095*7*501*501*4
    assert not totals["resources_approved"]
