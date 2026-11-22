"""Check a conditional-head correction that preserves the E0 rain and weak-rain outputs."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F

from a20_q32_gradient_route_synthetic import load_reference
from a20_q32_guard_synthetic import REFERENCE, REFERENCE_SHA256, q32_guard
from a20_twcrps_synthetic import SEED, FixtureModel, compare, fixture, metrics, run_arm
from yuntapr.models.quantile_v2.outputs import LogDomainOutput
from yuntapr.models.quantile_v2.parameterization import normalized_monotonic_quantiles


PREVIOUS = REFERENCE.with_name("A20_Q32_GRADIENT_ROUTE_RESULTS.json")
PREVIOUS_SHA256 = "ad576545fad9e655c6630ce112d439f0dd53853693ec53dfc99bf1e481b9ce11"
SVD_REL_TOLERANCE = 1e-6
MATCH_TOLERANCE = 1e-12


def match_metrics(actual, expected):
    if actual.keys() != expected.keys() or any(
            not math.isclose(value, expected[name], rel_tol=0, abs_tol=MATCH_TOLERANCE)
            for name, value in actual.items()):
        raise RuntimeError("The anchored fixture differs from the archived reference")


@torch.no_grad()
def weak_projection(anchor, batches, device):
    rows = []
    with torch.autocast(device.type, dtype=torch.bfloat16):
        for x, truth, valid, region, _ in batches:
            weak = (valid & region & (truth > .1) & (truth <= 1))[:, 0]
            rows.append(anchor.features(x).movedim(1, -1)[weak].double())
    protected = torch.cat(rows, dim=0)
    _, values, vectors = torch.linalg.svd(protected, full_matrices=False)
    rank = int((values > SVD_REL_TOLERANCE * values[0]).sum())
    basis = vectors[:rank]
    projection = torch.eye(protected.shape[1], device=device, dtype=torch.float64) - basis.T @ basis
    if not 0 < rank < protected.shape[1]:
        raise ValueError("Fixture cannot identify a nonempty protected and free subspace")
    return projection, dict(training_weak_rows=protected.shape[0], protected_rank=rank,
                            residual_degrees_of_freedom=protected.shape[1] - rank,
                            max_training_projected_feature=float((protected @ projection).abs().max()))


class ProtectedCorrection(nn.Module):
    def __init__(self, anchor, projection):
        super().__init__()
        self.anchor = anchor.requires_grad_(False).eval()
        self.register_buffer("projection", projection.float()[..., None, None])
        self.residual = nn.Conv2d(48, 33, 1, bias=False, device=projection.device)
        with torch.no_grad():
            self.residual.weight.zero_()

    def forward(self, x):
        with torch.no_grad():
            features = self.anchor.features(x)
            logit = self.anchor.heads.occurrence(features)
            p = logit.sigmoid()
        with torch.autocast(features.device.type, enabled=False):
            features = features.float()
            free = F.conv2d(features, self.projection)
            raw = self.anchor.heads.quantile(features) + self.residual(free)
            qlog = normalized_monotonic_quantiles(raw[:, :32], raw[:, 32:],
                                                   numerics=self.anchor.heads.numerics)
        return LogDomainOutput(logit, p, qlog)


@torch.no_grad()
def protection_evidence(anchor, model, batch, device):
    x, truth, valid, region, _ = batch
    weak = (valid & region & (truth > .1) & (truth <= 1))[:, 0]
    with torch.autocast(device.type, dtype=torch.bfloat16):
        anchor_output = anchor(x)
        corrected_output = model(x)
    difference = (anchor_output.conditional_quantiles_log - corrected_output.conditional_quantiles_log)
    return dict(occurrence_prediction_bitwise_equal=bool(torch.equal(anchor_output.rain_prob, corrected_output.rain_prob)),
                weak_log_node_max_abs_delta=float(difference.movedim(1, -1)[weak].abs().max()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise FileExistsError("Use a new result path")
    reference = load_reference(REFERENCE, REFERENCE_SHA256)
    previous = load_reference(PREVIOUS, PREVIOUS_SHA256)
    torch.set_num_threads(1)
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    device = torch.device("cuda")
    if (not torch.cuda.is_available() or not torch.cuda.is_bf16_supported()
            or torch.cuda.get_device_name() != reference["gpu"]
            or torch.__version__ != reference["torch_version"] or SEED != reference["seed"]):
        raise RuntimeError("Matched synthetic CUDA BF16 runtime required")
    anchor = FixtureModel().to(device)
    train = [fixture(SEED + index, device) for index in range(reference["training_grids"])]
    evaluation = fixture(SEED + 1000, device)
    match_metrics(metrics(anchor, evaluation, device), reference["initial"])
    anchor_run = run_arm(anchor, train, device, candidate=False)
    control = metrics(anchor, evaluation, device)
    match_metrics(control, reference["control"])
    projection, evidence = weak_projection(anchor, train, device)
    candidate = ProtectedCorrection(anchor, projection)
    match_metrics(metrics(candidate, evaluation, device), control)
    candidate_run = run_arm(candidate, train, device, candidate=True, extra_loss=q32_guard)
    corrected = metrics(candidate, evaluation, device)
    protection = protection_evidence(anchor, candidate, evaluation, device)
    delta, gates = compare(control, corrected)
    relative, twcrps_gates = compare(reference["candidate"], corrected)
    gates["q32_drop_relative_to_twcrps"] = twcrps_gates["low_p_negative_q32_drop"]
    gates["fixed_a_hits_without_false_alarms"] = corrected["a_tp"] > 0 and corrected["a_fp"] == 0
    gates["q32_false_alarms_not_higher"] = corrected["q32_fp"] <= control["q32_fp"]
    result = dict(
        status="PASS_SYNTHETIC_DIRECTION_ONLY" if all(gates.values()) else "STOP_BEFORE_REAL_TRAINING",
        scientific_status="NOT_VERIFIED", seed=SEED,
        design="Fixed E0 anchor with a zero-initialized quantile correction projected off Train weak features",
        projection_relative_svd_tolerance=SVD_REL_TOLERANCE, projection=evidence,
        archived_control_reproduced=True, zero_initial_correction_matches_anchor=True,
        previous_settings=previous["settings"], anchor_run=anchor_run, correction_run=candidate_run,
        evaluation_protection=protection, e0=control, previous_gradient_route=previous["candidate"],
        candidate=corrected, candidate_minus_e0=delta, candidate_minus_twcrps=relative,
        synthetic_direction_gates=gates, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        reference_sha256=REFERENCE_SHA256, previous_sha256=PREVIOUS_SHA256,
        real_source_payload_reads=0, real_checkpoints_loaded=0, formal_updates=0, final_2025_access=False,
    )
    with args.receipt.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(dict(status=result["status"], protection=protection, projection=evidence,
                          candidate=corrected, gates=gates)))


if __name__ == "__main__":
    main()
