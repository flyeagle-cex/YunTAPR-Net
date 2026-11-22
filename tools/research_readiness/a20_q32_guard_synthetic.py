"""Run one synthetic arm adding a direct non-strong q32 penalty to E0 + twCRPS."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import torch

from a20_twcrps_synthetic import ROOT, SEED, FixtureModel, fixture, metrics, run_arm, compare
from yuntapr.models.quantile_v2.outputs import LogDomainOutput


REFERENCE = (ROOT / "docs/research_readiness/20261121_a20_negative_coverage/"
             "A20_TWCRPS_SYNTHETIC_RESULTS.json")
REFERENCE_SHA256 = "635fa0da94d17d46a201282ce5059f9ef1403024d62953ca4443b690ba825fa1"
GUARD_WEIGHT = .1
THRESHOLD = 20.
LOG_THRESHOLD = math.log1p(THRESHOLD)


def q32_guard(output, rate, valid, region, n_valid):
    """Penalize the physical excess of q32 over 20 on valid non-strong truth."""
    nonstrong = (valid & region & (rate <= THRESHOLD))[:, 0]
    with torch.autocast(rate.device.type, enabled=False):
        q32 = output.conditional_quantiles_log[:, -1][nonstrong]
        # expm1(q32) - threshold, with exact zero at the frozen log threshold.
        excess = (1 + THRESHOLD) * torch.expm1((q32 - LOG_THRESHOLD).clamp_min(0.))
        penalty = GUARD_WEIGHT * (excess / THRESHOLD).square().sum() / n_valid
    if not bool(torch.isfinite(penalty)):
        raise FloatingPointError("Nonfinite non-strong q32 penalty")
    return penalty


def mechanism_check(device):
    # Eligible dry, below threshold, at threshold, strong, invalid, outside region.
    q32 = torch.tensor([math.log1p(40), math.log1p(19), LOG_THRESHOLD, math.log1p(45),
                        math.log1p(50), math.log1p(55)],
                       dtype=torch.float64, device=device, requires_grad=True)
    lower = torch.linspace(.2, 1., 31, dtype=torch.float64, device=device).log1p()
    qlog = torch.cat((lower.view(1, 31, 1, 1).expand(-1, -1, -1, 6), q32.view(1, 1, 1, 6)), dim=1)
    p = torch.tensor([.01, .9, .8, .8, .1, .1], dtype=torch.float64,
                     device=device, requires_grad=True).view(1, 1, 1, 6)
    rate = torch.tensor([0., 2., 20., 30., float("nan"), 0.],
                        dtype=torch.float32, device=device).view_as(p)
    valid = torch.tensor([1, 1, 1, 1, 0, 1], dtype=torch.bool, device=device).view_as(p)
    region = torch.tensor([1, 1, 1, 1, 1, 0], dtype=torch.bool, device=device).view_as(p)
    penalty = q32_guard(LogDomainOutput(p, p, qlog), rate, valid, region, 4)
    grad_q32, grad_p = torch.autograd.grad(penalty, (q32, p), allow_unused=True)
    torch.testing.assert_close(penalty, q32.new_tensor(.025), rtol=0, atol=1e-14)
    torch.testing.assert_close(grad_q32[0], q32.new_tensor(.1025), rtol=0, atol=1e-14)
    assert grad_p is None and not bool(grad_q32[1:].any())
    return dict(dry_q32_at_40_gradient=float(grad_q32[0]), direct_occurrence_gradient=False,
                noneligible_gradients_zero=True, physical_threshold_boundary_exact=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise FileExistsError("Use a new result path")
    reference_bytes = REFERENCE.read_bytes()
    reference_sha = hashlib.sha256(reference_bytes.replace(b"\r\n", b"\n")).hexdigest()
    if reference_sha != REFERENCE_SHA256:
        raise ValueError("The archived synthetic reference differs")
    reference = json.loads(reference_bytes)
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
    checks = mechanism_check(device)
    model = FixtureModel().to(device)
    train = [fixture(SEED + index, device) for index in range(reference["training_grids"])]
    evaluation = fixture(SEED + 1000, device)
    initial = metrics(model, evaluation, device)
    if initial.keys() != reference["initial"].keys() or any(
            not math.isclose(value, reference["initial"][name], rel_tol=0, abs_tol=1e-12)
            for name, value in initial.items()):
        raise RuntimeError("Synthetic fixture or initial model differs from the two archived controls")
    run = run_arm(model, train, device, candidate=True, extra_loss=q32_guard)
    candidate = metrics(model, evaluation, device)
    delta_e0, gates = compare(reference["control"], candidate)
    delta_twcrps, added_term_deltas = compare(reference["candidate"], candidate)
    gates["q32_drop_relative_to_twcrps"] = added_term_deltas["low_p_negative_q32_drop"]
    gates["fixed_a_hits_without_false_alarms"] = candidate["a_tp"] > 0 and candidate["a_fp"] == 0
    gates["q32_false_alarms_not_higher"] = candidate["q32_fp"] <= reference["control"]["q32_fp"]
    result = dict(
        status="PASS_SYNTHETIC_DIRECTION_ONLY" if all(gates.values()) else "STOP_BEFORE_REAL_TRAINING",
        scientific_status="NOT_VERIFIED", seed=SEED, settings=dict(
            intervention="Add non-strong q32 physical squared hinge to E0 + fixed twCRPS",
            threshold_mm_h=THRESHOLD, weight=GUARD_WEIGHT, denominator="ALL_VALID_PIXELS",
            synthetic_admission_thresholds=reference["admission_thresholds"],
        ),
        synthetic_checks=checks, initial=initial, archived_e0=reference["control"],
        archived_twcrps=reference["candidate"], candidate=candidate, run=run,
        candidate_minus_e0=delta_e0, candidate_minus_twcrps=delta_twcrps, synthetic_direction_gates=gates,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        harness_sha256=hashlib.sha256(Path(__file__).with_name("a20_twcrps_synthetic.py").read_bytes()).hexdigest(),
        reference_sha256=reference_sha,
        real_source_payload_reads=0, real_checkpoints_loaded=0, formal_updates=0, final_2025_access=False,
    )
    with args.receipt.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(dict(status=result["status"], candidate=candidate, gates=gates)))


if __name__ == "__main__":
    main()
