"""Test the fixed occurrence and upper-quantile endpoints on the synthetic fixture."""

import argparse
import hashlib
import json
from pathlib import Path

import torch

from a20_anchored_rain_regime_synthetic import RainRegimeCorrection, overlap_fixture
from a20_protected_correction_synthetic import match_metrics
from a20_q32_gradient_route_synthetic import load_reference
from a20_q32_guard_synthetic import REFERENCE, REFERENCE_SHA256, q32_guard
from a20_twcrps_synthetic import SEED, FixtureModel, fixture, metrics, run_arm


PREVIOUS = REFERENCE.with_name("A20_ANCHORED_RAIN_REGIME_RESULTS.json")
PREVIOUS_SHA256 = "370f13d200eed15cb0391835e88b585a04346ed0f95b7eea75b4122b3fcfb7c7"


def frozen_directions(baseline, candidate):
    return dict(
        strong_physical_pinball=candidate["strong_physical_pinball_over20"] < baseline["strong_physical_pinball_over20"],
        q32_hits=candidate["q32_tp"] >= baseline["q32_tp"],
        q32_false_alarms=candidate["q32_fp"] <= baseline["q32_fp"],
        point_a_hits=candidate["a_tp"] > 0,
        point_a_false_alarms=candidate["a_fp"] == 0,
        weak_log_pinball=candidate["weak_log_pinball"] <= baseline["weak_log_pinball"],
        occurrence_brier=candidate["occurrence_brier"] <= baseline["occurrence_brier"],
        occurrence_ap=candidate["occurrence_ap"] >= baseline["occurrence_ap"],
        occurrence_auroc=candidate["occurrence_auroc"] >= baseline["occurrence_auroc"],
    )


@torch.no_grad()
def endpoint_checks(anchor, candidate, batch, device):
    x, truth, valid, region, _ = batch
    with torch.autocast(device.type, dtype=torch.bfloat16):
        original, corrected = anchor(x), candidate(x)
    qlog = corrected.conditional_quantiles_log
    if (not torch.equal(original.rain_prob, corrected.rain_prob)
            or not torch.equal(original.conditional_quantiles_log[:, -1], qlog[:, -1])):
        raise RuntimeError("Frozen occurrence or q32 changed")
    if not bool((qlog[:, 1:] > qlog[:, :-1]).all()):
        raise RuntimeError("Conditional node ordering changed")
    selection = (valid & region)[:, 0]
    truth = truth[:, 0][selection]
    strong = truth > 20
    weak = (truth > .1) & (truth <= 1)
    probability = corrected.rain_prob[:, 0][selection].double()
    nodes = qlog.movedim(1, -1)[selection].expm1()
    a_ceiling = (probability * nodes[:, -1]).float()
    actual_a = (probability * nodes.mean(dim=1)).float()
    if not bool((actual_a <= a_ceiling).all()):
        raise ValueError("The fixed-endpoint bound must hold")
    diff = (qlog - original.conditional_quantiles_log).movedim(1, -1)[selection]
    return dict(
        occurrence_bitwise_equal=True, q32_bitwise_equal=True, strict_node_order=True,
        strong_with_ceiling_over20=int(((a_ceiling > 20) & strong).sum()),
        nonstrong_with_ceiling_over20=int(((a_ceiling > 20) & ~strong).sum()),
        strong_ceiling_max=float(a_ceiling[strong].max()),
        weak_log_node_max_abs_delta=float(diff[weak].abs().max()),
        interior_log_node_max_abs_delta=float(diff[:, :-1].abs().max()),
    )


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
    correction = RainRegimeCorrection(anchor, device, preserve_span=True)
    match_metrics(metrics(correction, evaluation, device), control)
    correction_run = run_arm(correction, train, device, candidate=True, extra_loss=q32_guard)
    candidate = metrics(correction, evaluation, device)
    endpoints = endpoint_checks(anchor, correction, evaluation, device)
    normal = frozen_directions(control, candidate)
    overlap = overlap_fixture(evaluation)
    overlap_baseline = metrics(anchor, overlap, device)
    overlap_candidate = metrics(correction, overlap, device)
    stress = frozen_directions(overlap_baseline, overlap_candidate)
    result = dict(
        status="PASS_SYNTHETIC_DIRECTIONS" if all(normal.values()) else "STOP_BEFORE_REAL_TRAINING",
        scientific_status="NOT_VERIFIED", seed=SEED, reference_sha256=REFERENCE_SHA256,
        previous_sha256=PREVIOUS_SHA256,
        intervention="Allow changes to conditional node allocations only; freeze occurrence and q32",
        prior_synthetic_candidate=previous["candidate"], e0=control, candidate=candidate,
        verified_endpoints=endpoints, checks_with_original_directions_on_fixture=normal,
        feature_overlap_stress=dict(labels_changed=4, e0=overlap_baseline, candidate=overlap_candidate, checks=stress),
        anchor_run=anchor_run, correction_run=correction_run,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        conditional_correction_sha256=hashlib.sha256(Path(__file__).with_name(
            "a20_anchored_rain_regime_synthetic.py").read_bytes()).hexdigest(),
        real_source_payload_reads=0, real_checkpoints_loaded=0, formal_updates=0, final_2025_access=False,
    )
    with args.receipt.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(dict(status=result["status"], endpoints=endpoints, metrics=candidate, gates=normal,
                          stress_a_tp=overlap_candidate["a_tp"], stress_a_fp=overlap_candidate["a_fp"])))


if __name__ == "__main__":
    main()
