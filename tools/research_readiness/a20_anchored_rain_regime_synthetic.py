"""Test an anchored quantile correction routed by predicted rain intensity and probability."""

import argparse
import hashlib
import json
from pathlib import Path

import torch
from torch import nn

from a20_protected_correction_synthetic import match_metrics, protection_evidence
from a20_q32_gradient_route_synthetic import load_reference
from a20_q32_guard_synthetic import REFERENCE, REFERENCE_SHA256, q32_guard
from a20_twcrps_synthetic import SEED, FixtureModel, compare, fixture, metrics, run_arm
from yuntapr.models.quantile_v2.outputs import LogDomainOutput
from yuntapr.models.quantile_v2.parameterization import normalized_monotonic_quantiles


WEAK_LIMIT = 1.
RAIN_DECISION = .5


class RainRegimeCorrection(nn.Module):
    def __init__(self, anchor, device):
        super().__init__()
        self.anchor = anchor.requires_grad_(False).eval()
        self.low_probability = nn.Conv2d(48, 33, 1, bias=False, device=device)
        self.high_probability = nn.Conv2d(48, 33, 1, bias=False, device=device)
        with torch.no_grad():
            self.low_probability.weight.zero_()
            self.high_probability.weight.zero_()

    def forward(self, x):
        with torch.no_grad():
            features = self.anchor.features(x)
            logit = self.anchor.heads.occurrence(features)
            p = logit.sigmoid()
        with torch.autocast(features.device.type, enabled=False):
            features = features.float()
            raw = self.anchor.heads.quantile(features)
            numerics = self.anchor.heads.numerics
            baseline_nodes = normalized_monotonic_quantiles(raw[:, :32], raw[:, 32:], numerics=numerics)
            median = baseline_nodes[:, 15:17].expm1().mean(dim=1, keepdim=True)
            active = median > WEAK_LIMIT
            low = active & (p < RAIN_DECISION)
            high = active & (p >= RAIN_DECISION)
            correction = self.low_probability(features) * low + self.high_probability(features) * high
            adjusted = raw + correction
            qlog = normalized_monotonic_quantiles(adjusted[:, :32], adjusted[:, 32:], numerics=numerics)
        return LogDomainOutput(logit, p, qlog)


def overlap_fixture(batch):
    """Change four strong-near labels to weak rain while keeping their inputs."""
    x, rate, valid, region, category = batch
    selected = (valid & region).flatten()
    altered = rate.clone()
    positions = selected.nonzero().flatten()[(category == 5).nonzero().flatten()[:4]]
    altered.flatten()[positions] = .55
    return x, altered, valid, region, category


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise FileExistsError("Use a new result path")
    reference = load_reference(REFERENCE, REFERENCE_SHA256)
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
    correction = RainRegimeCorrection(anchor, device)
    match_metrics(metrics(correction, evaluation, device), control)
    correction_run = run_arm(correction, train, device, candidate=True, extra_loss=q32_guard)
    candidate = metrics(correction, evaluation, device)
    delta, gates = compare(control, candidate)
    relative, twcrps_gates = compare(reference["candidate"], candidate)
    gates["q32_drop_relative_to_twcrps"] = twcrps_gates["low_p_negative_q32_drop"]
    gates["fixed_a_hits_without_false_alarms"] = candidate["a_tp"] > 0 and candidate["a_fp"] == 0
    gates["q32_false_alarms_not_higher"] = candidate["q32_fp"] <= control["q32_fp"]
    stress = overlap_fixture(evaluation)
    stress_control = metrics(anchor, stress, device)
    stress_candidate = metrics(correction, stress, device)
    result = dict(
        status="PASS_SYNTHETIC_DIRECTION_ONLY" if all(gates.values()) else "STOP_BEFORE_REAL_TRAINING",
        scientific_status="NOT_VERIFIED", seed=SEED, reference_sha256=REFERENCE_SHA256,
        intervention=dict(frozen_e0_anchor=True, threshold_conditional_median_mm_h=WEAK_LIMIT,
                          probability_boundary=RAIN_DECISION, separate_conditional_corrections=True,
                          training_objective="E0 + unchanged twCRPS + unchanged q32 penalty"),
        anchor_run=anchor_run, correction_run=correction_run,
        protection=protection_evidence(anchor, correction, evaluation, device),
        e0=control, candidate=candidate, candidate_minus_e0=delta, candidate_minus_twcrps=relative,
        synthetic_direction_gates=gates,
        feature_overlap_stress=dict(labels_changed=4, optimization_updates=0, e0=stress_control,
                                    candidate=stress_candidate),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        real_source_payload_reads=0, real_checkpoints_loaded=0, formal_updates=0, final_2025_access=False,
    )
    with args.receipt.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(dict(status=result["status"], protection=result["protection"],
                          candidate=candidate, gates=gates, stress_a_fp=stress_candidate["a_fp"])))


if __name__ == "__main__":
    main()
