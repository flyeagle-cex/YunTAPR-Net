"""New epoch/loader/authorization and transaction boundary tests; no steps."""
from dataclasses import replace
import copy
import json
from pathlib import Path
import pytest
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, learning_rate_prefix
from yuntapr.experimental.phase_b_v2_integration.controls import synthetic_epoch_order
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.protocol import (
    plans, verify_public_sources, fixed_endpoint, run_identity, ROOT, public_inventory)
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.data import (
    artificial_registry, Registry, Scene, Loader, Coverage, ROLES, Batch)
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.authorization import start_formal, open_real_data
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.safety import install_guard, Ledger, TEMP_ROOT
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.checkpoint import EpochStore
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.metrics import StreamingValidation
from yuntapr.models.quantile_v2.outputs import LogDomainOutput

install_guard()


@pytest.fixture(scope="module")
def registry():
    return artificial_registry()


def test_source_identity_no_real_scaler_access():
    assert verify_public_sources() == 402
    deferred = public_inventory()["deferred_observational_artifacts"]
    assert len(deferred) == 1
    with pytest.raises(PermissionError):
        (ROOT / deferred[0]["path"]).open("rb")


def test_18_formal_plans_only():
    p = plans()
    assert len(p["plans"]) == 18 and p["formal_runs_executed"] == 0
    assert p["budget_not_executed"]["updates_total"] == 846936
    assert p["budget_not_executed"]["stage1_updates"] == 282312


@pytest.mark.parametrize("best", [None, 1, 2, 8, 9, "APPROVED", {"best": 1}])
def test_fixed_endpoint_never_uses_best(best):
    assert fixed_endpoint(8, best_epoch=best)["selected_epoch"] is None
    assert fixed_endpoint(9, best_epoch=best)["selected_epoch"] == 9
    assert fixed_endpoint(9)["remaining_budget"] == 0


@pytest.mark.parametrize("model", ["B0_MATCHED_V2", "B1_V2"])
@pytest.mark.parametrize("seed", [2026, 2027, 2028])
def test_small_epoch_exactly_once_and_tail(registry, model, seed):
    loader = Loader(registry, model, ROLES[0], seed, 0)
    again = Loader(registry, model, ROLES[0], seed, 0)
    assert loader.order == again.order
    coverage = Coverage(registry.ids(ROLES[0]))
    sizes = []
    for batch in loader:
        coverage.add(batch.ids); sizes.append(len(batch.ids))
        assert batch.x.shape[1] == (1 if model == "B0_MATCHED_V2" else 6)
        assert batch.rate.dtype == torch.float32
        assert int((batch.reference_valid & batch.region_mask).sum()) == len(batch.ids)*3430
    assert sizes == [2, 2, 1] and coverage.finish()["exactly_once"]
    validation = list(Loader(registry, model, ROLES[1], seed, 0))
    assert [len(b.ids) for b in validation] == [5]
    assert not set(registry.ids(ROLES[0])) & set(registry.ids(ROLES[1]))


@pytest.mark.parametrize("seed", [2026, 2027, 2028])
def test_full_integer_coverage_no_observations(seed):
    # IDs explicitly artificial, not copies of real scene catalogues.
    ids = tuple(f"SYNTHETIC_ENGINEERING_ONLY/order_{i:05d}" for i in range(10455))
    for e in range(9):
        order = synthetic_epoch_order(ids, seed, e)
        assert len(order) == len(set(order)) == 10455 and set(order) == set(ids)
        assert sum(1 for _ in range(0, len(order), 2)) == 5228
        assert len(order[-1:]) == 1
    assert 9 * 5228 == 47052
    assert 10501 // 8 == 1312 and 10501 % 8 == 5


@pytest.mark.parametrize("fault", ["duplicate", "missing", "unknown"])
def test_coverage_rejects_incomplete(fault):
    c = Coverage(("a", "b", "c"))
    with pytest.raises(ValueError):
        if fault == "duplicate": c.add(("a", "a"))
        elif fault == "unknown": c.add(("bad",))
        else: c.add(("a", "b")); c.finish()


@pytest.mark.parametrize("fault", ["real_id", "year", "role", "nan", "shape", "fp64_rate", "native_missing", "reference_missing"])
def test_scene_firewall_and_shapes(registry, fault):
    scene = registry.get(registry.ids(ROLES[0])[0], ROLES[0])
    if fault == "real_id": scene = replace(scene, scene_id="2023_real_scene")
    elif fault == "year": scene = replace(scene, years=(2023,))
    elif fault == "role": scene = replace(scene, role="2024_TEST")
    elif fault == "nan": scene = replace(scene, rate=torch.full_like(scene.rate, float("nan")))
    elif fault == "shape": scene = replace(scene, x6=scene.x6[:1])
    elif fault == "fp64_rate": scene = replace(scene, rate=scene.rate.double())
    elif fault == "native_missing": scene = replace(scene, native_valid=torch.zeros_like(scene.native_valid))
    elif fault == "reference_missing": scene = replace(scene, reference_valid=torch.zeros_like(scene.reference_valid))
    with pytest.raises((ValueError, FloatingPointError)):
        scene.validate()


def test_registry_duplicate_and_role_overlap(registry):
    scene = registry.get(registry.ids(ROLES[0])[0], ROLES[0])
    with pytest.raises(ValueError): Registry((scene, scene))


@pytest.mark.parametrize("claim", [True, "APPROVED", {"approved": True}, {"commit": "435f303"}, {"tests_passed": True}])
def test_self_claims_never_authorize(claim):
    with pytest.raises(PermissionError): start_formal(approval=claim)
    with pytest.raises(PermissionError): open_real_data(approval=claim)


@pytest.mark.parametrize("path", ["raw.nc", "best.pt", "private.ckpt", "sealed_2025.json", "unknown.csv"])
def test_raw_path_firewall(path):
    with pytest.raises(PermissionError): Path(path).open("rb")


@pytest.mark.parametrize("fault", ["after_serialization", "after_blob", "rename_locked"])
def test_reused_atomic_store_faults_isolated(fault):
    store = EpochStore()
    with pytest.raises(OSError): store.save("fault", {"synthetic": torch.ones(2)}, fault=fault)
    assert not (store.root / "fault.ref.json").exists()
    with pytest.raises(FileNotFoundError): store.read(store.root / "fault.ref.json")


def test_byte_sha_and_store_escape():
    store = EpochStore()
    ref = store.save("tiny_artificial", {"x": torch.ones(2)})
    assert torch.equal(store.read(ref)["x"], torch.ones(2))
    record = json.loads(ref.read_text()); record["sha256"] = "0"*64
    ref.write_text(json.dumps(record))
    with pytest.raises(ValueError): store.read(ref)
    with pytest.raises(PermissionError): store.read(Path("private.ref.json"))


def test_versioned_quota_reservation_only():
    store = EpochStore()
    ledger = Ledger(metadata_fixture_path=store.root / "metadata_only_quota.json")
    for i in range(3): ledger.mutate("B0_MATCHED_V2__E1", event={"mock_reservation_only": i})
    with pytest.raises(PermissionError): ledger.mutate("B0_MATCHED_V2__E1", event={})
    assert not ledger.read()["completed"]  # NEVER called optimizer step
    assert Ledger(metadata_fixture_path=ledger.path).read()["reserved"]["B0_MATCHED_V2__E1"] == 3


def output_and_batch(ids, rate):
    n = len(ids)
    shape = (n, 1, 100, 100)
    logit = torch.zeros(shape, dtype=torch.bfloat16)
    q = torch.linspace(.2, 3.2, 32, dtype=torch.float64).reshape(1,32,1,1).expand(n,32,100,100).clone()
    output = LogDomainOutput(logit, logit.sigmoid(), q)
    mask = (torch.arange(10000).reshape(1,1,100,100) < 3430).expand(shape).clone()
    batch = Batch(ids, ROLES[1], torch.empty(0), torch.full(shape, rate, dtype=torch.float32), torch.empty(0),
                  torch.ones(shape, dtype=torch.bool), mask)
    return output, batch


def test_streaming_global_denominator_not_batch_mean():
    ids = ("a", "b", "c", "d", "e")
    accumulator = StreamingValidation(ids)
    for group, rate in ((ids[:2], 0.), (ids[2:], 2.)):
        out, batch = output_and_batch(group, rate); accumulator.add(out, batch)
    report = accumulator.finish()
    assert report["N_valid"] == 17150 and report["N_rain"] == 10290
    assert report["global_val_core_loss"] == (report["S_occ"]+report["S_qr"])/17150
    assert report["conditional_pinball_synthetic"] == report["S_qr"]/10290
    assert not report["lambda_in_common_metric"] and report["numerator_dtype"] == "float64"


def test_streaming_empty_rain_none():
    out, batch = output_and_batch(("a",), 0.)
    v = StreamingValidation(("a",)); v.add(out, batch)
    assert v.finish()["conditional_pinball_synthetic"] is None
