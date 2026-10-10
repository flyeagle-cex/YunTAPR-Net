"""Actual fresh paired initialization; hashes only, no state serialization."""
from __future__ import annotations
from contextlib import contextmanager
import os
import random
import numpy as np
import torch
from yuntapr.models.quantile_v2.models import B0MatchedV2, B1V2
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics
from yuntapr.training.phase_a_protocol import capture_rng, state_digest, parameter_groups
from yuntapr.experimental.phase_b_v2_ablations.config import SEEDS
from yuntapr.experimental.phase_b_v2_ablations.readiness import INPUT_DIFFERENCES
from .resources import resource_snapshot, require_resources
from .pins import verify_frozen_sources, REPO
from . import SCOPE


@contextmanager
def seeded_environment(seed: int):
    """Fixed process hash seed; per-run Python/NumPy/Torch seeds vary as proposed."""
    if type(seed) is not int or seed not in SEEDS:
        raise ValueError("Only three preregistered candidate seeds")
    if os.environ.get("PYTHONHASHSEED") != "2026" or os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
        raise RuntimeError("Set fixed hash and cuBLAS environment before process startup")
    py_state, np_state = random.getstate(), np.random.get_state()
    old = (torch.are_deterministic_algorithms_enabled(), torch.is_deterministic_algorithms_warn_only_enabled(),
           torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark,
           torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32,
           torch.get_float32_matmul_precision())
    with torch.random.fork_rng(devices=list(range(torch.cuda.device_count()))):
        try:
            random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
            torch.use_deterministic_algorithms(True, warn_only=False)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            torch.set_float32_matmul_precision("highest")
            yield
        finally:
            random.setstate(py_state); np.random.set_state(np_state)
            torch.use_deterministic_algorithms(old[0], warn_only=old[1])
            torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark = old[2:4]
            torch.set_float32_matmul_precision(old[6])
            torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = old[4:6]


def fresh_paired_models(seed: int) -> tuple[dict[str, torch.nn.Module], dict]:
    admission = resource_snapshot(full_backward=False)
    require_resources(admission)  # before either full model constructor
    pins = verify_frozen_sources()
    numerics = CandidateNumerics(epsilon_w=1e-4, epsilon_span=1e-4)
    with seeded_environment(seed):
        anchor = B0MatchedV2(numerics=numerics, root=REPO)
        # Reset every proposed RNG source independently before B1 construction.
        random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
        temporal = B1V2(numerics=numerics, root=REPO)
        a, b = anchor.state_dict(), temporal.state_dict()
        if a.keys() != b.keys():
            raise ValueError("Frozen paired tensor names differ")
        different = {name for name in a if a[name].shape != b[name].shape}
        if different != INPUT_DIFFERENCES:
            raise ValueError("Unexpected model input shape differences")
        native = {name: state_digest(b[name]) for name in sorted(different)}
        with torch.no_grad():
            for name in a:
                if name not in different:
                    if a[name].dtype != b[name].dtype:
                        raise ValueError("Paired state dtype differs")
                    b[name].copy_(a[name])
        if native != {name: state_digest(b[name]) for name in sorted(different)}:
            raise ValueError("Native B1 input initialization changed")
        if not all(torch.equal(a[name], b[name]) for name in a if name not in different):
            raise ValueError("Shared initialization not identical")
        models = {"B0_MATCHED_V2": anchor, "B1_V2": temporal}
        counts = {kind: parameter_groups(model, check_counts=False)[1]["counts"] for kind, model in models.items()}
        expected_totals = {"B0_MATCHED_V2": 4329410, "B1_V2": 4331810}
        if any(counts[k]["total"] != expected_totals[k] for k in models):
            raise ValueError("Frozen parameter count changed")
        proof = {"scope": SCOPE, "seed": seed, "actual_fresh_models_constructed": True,
                 "historical_checkpoint_loaded": False, "optimizer_created": False,
                 "state_sha256": {k: state_digest(m.state_dict()) for k, m in models.items()},
                 "buffers_sha256": {k: state_digest(dict(m.named_buffers())) for k, m in models.items()},
                 "shared_tensor_sha256": {n: state_digest(a[n]) for n in a if n not in different},
                 "native_B1_input_sha256": native, "same_shape_shared_bit_identical": True,
                 "native_zero_skip_preserved": bool((b["backbone.enc0.skip.weight"] == 0).all()),
                 "post_pair_rng_sha256": state_digest(capture_rng()), "parameter_counts": counts,
                 "source_pins_verified": pins, "resource_admission": admission,
                 "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED": False}
    return models, proof

