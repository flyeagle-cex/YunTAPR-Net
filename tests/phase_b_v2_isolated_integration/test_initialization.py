import gc
import pytest
import torch
from yuntapr.training.phase_a_protocol import epoch_permutation, state_digest
from yuntapr.experimental.phase_b_v2_integration.initialization import fresh_paired_models
from yuntapr.experimental.phase_b_v2_integration.controls import synthetic_epoch_order
from yuntapr.experimental.phase_b_v2_integration.pins import verify_frozen_sources


@pytest.mark.parametrize("seed", [2026, 2027, 2028])
def test_actual_fresh_states_match_across_arms(seed, record):
    proofs = []
    for arm in ("E0", "E1", "E2"):
        models, proof = fresh_paired_models(seed)
        assert proof["same_shape_shared_bit_identical"] and proof["native_zero_skip_preserved"]
        assert all(p.grad is None for m in models.values() for p in m.parameters())
        assert proof["parameter_counts"]["B0_MATCHED_V2"]["total"] == 4329410
        assert proof["parameter_counts"]["B1_V2"]["total"] == 4331810
        proof["candidate_arm"] = arm
        proofs.append(proof)
        del models
        gc.collect()
    for key in ("state_sha256", "buffers_sha256", "post_pair_rng_sha256", "shared_tensor_sha256", "native_B1_input_sha256"):
        assert proofs[0][key] == proofs[1][key] == proofs[2][key]
    record(f"actual_initialization_seed_{seed}", {"scope": "SYNTHETIC_ENGINEERING_ONLY", "proofs": proofs,
           "three_independent_fresh_pairs_match": True, "formal_initialization_artifact_saved": False})


def test_seed2026_order_matches_frozen_rule():
    ids = tuple(f"SYNTHETIC_ENGINEERING_ONLY/order_{i:05d}" for i in range(29))
    for epoch in range(9):
        expected = tuple(ids[int(i)] for i in epoch_permutation(epoch, count=len(ids)))
        assert synthetic_epoch_order(ids, 2026, epoch) == expected


def test_source_identities_still_pinned():
    assert verify_frozen_sources() == 66

