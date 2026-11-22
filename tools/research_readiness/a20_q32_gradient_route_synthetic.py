"""Compare one q32 guard gradient route on the existing synthetic fixture."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import torch

from a20_twcrps_synthetic import ROOT, SEED, FixtureModel, fixture, metrics, run_arm, compare
from a20_q32_guard_synthetic import REFERENCE, REFERENCE_SHA256, q32_guard


PREVIOUS = REFERENCE.with_name("A20_Q32_GUARD_SYNTHETIC_RESULTS.json")
PREVIOUS_SHA256 = "d1840ad72139f9ec7d7ae9f0ca61779fe1decef247cb58586cb402f101db9577"


def detached_features(model, x):
    with torch.no_grad():
        features = model.features(x)
    return model.heads(features)


def load_reference(path, expected_sha):
    raw = path.read_bytes()
    if hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() != expected_sha:
        raise ValueError("Archived comparison identity changed")
    return json.loads(raw)


def dot(left, right):
    return math.fsum(float((x.double() * y.double()).sum()) for x, y in zip(left, right)
                     if x is not None and y is not None)


def trace_gate(model, batch, device):
    """Trace the guard contribution at initialization in each parameter group."""
    x, rate, valid, region, category = batch
    selected = (valid & region)[:, 0]
    count = int(selected.sum())
    params = tuple(model.named_parameters())
    values = tuple(p for _, p in params)
    with torch.autocast(device.type, dtype=torch.bfloat16):
        ordinary = model(x)
        routed = detached_features(model, x)
        guard = q32_guard(ordinary, rate, valid, region, count)
        routed_guard = q32_guard(routed, rate, valid, region, count)
    torch.testing.assert_close(ordinary.conditional_quantiles_log, routed.conditional_quantiles_log,
                               rtol=0, atol=0)
    torch.testing.assert_close(guard, routed_guard, rtol=0, atol=0)
    grad_full = torch.autograd.grad(guard, values, allow_unused=True, retain_graph=True)
    grad_routed = torch.autograd.grad(routed_guard, values, allow_unused=True)
    shared = [name.startswith("shared.") for name, _ in params]
    for is_shared, full, detached in zip(shared, grad_full, grad_routed):
        if is_shared:
            if detached is not None or full is None:
                raise AssertionError("q32 guard must stop before the shared layer")
        elif full is None or detached is None:
            assert full is None and detached is None
        else:
            torch.testing.assert_close(full, detached, rtol=0, atol=0)
    physical = ordinary.conditional_quantiles_log.movedim(1, -1)[selected].expm1()
    p = ordinary.rain_prob[:, 0][selected].double()
    strong_a = (p * physical.mean(dim=-1))[category == 4].mean()
    q32_on_dry = physical[category == 1, -1].mean()
    result = {}
    for name, metric in (("strong_low_mean_a", strong_a), ("low_p_negative_mean_q32", q32_on_dry)):
        gradient = torch.autograd.grad(metric, values, allow_unused=True, retain_graph=True)
        result[name] = dict(
            shared_feature_direction=-dot([g for g, part in zip(grad_full, shared) if part],
                                          [g for g, part in zip(gradient, shared) if part]),
            head_direction=-dot([g for g, part in zip(grad_full, shared) if not part],
                                [g for g, part in zip(gradient, shared) if not part]),
        )
    return dict(loss_and_forward_values_equal=True, head_gradients_equal=True,
                guard_does_not_reach_shared_layer=True, unit_gradient_step_directions=result,
                interpretation="One local derivative of the guard alone; not an AdamW update")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise FileExistsError("Use a new result path")
    reference = load_reference(REFERENCE, REFERENCE_SHA256)
    previous = load_reference(PREVIOUS, PREVIOUS_SHA256)
    if previous["reference_sha256"] != REFERENCE_SHA256 or previous["seed"] != SEED:
        raise ValueError("The two archived comparison receipts do not share a fixture")
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
    model = FixtureModel().to(device)
    train = [fixture(SEED + index, device) for index in range(reference["training_grids"])]
    evaluation = fixture(SEED + 1000, device)
    initial = metrics(model, evaluation, device)
    if initial.keys() != reference["initial"].keys() or any(
            not math.isclose(value, reference["initial"][name], rel_tol=0, abs_tol=1e-12)
            for name, value in initial.items()):
        raise RuntimeError("Synthetic fixture or initial model differs from archived runs")
    trace = trace_gate(model, train[0], device)
    run = run_arm(model, train, device, candidate=True, extra_loss=q32_guard, extra_forward=detached_features)
    candidate = metrics(model, evaluation, device)
    delta_e0, gates = compare(reference["control"], candidate)
    delta_twcrps, twcrps_gates = compare(reference["candidate"], candidate)
    delta_full, _ = compare(previous["candidate"], candidate)
    gates["q32_drop_relative_to_twcrps"] = twcrps_gates["low_p_negative_q32_drop"]
    gates["fixed_a_hits_without_false_alarms"] = candidate["a_tp"] > 0 and candidate["a_fp"] == 0
    gates["q32_false_alarms_not_higher"] = candidate["q32_fp"] <= reference["control"]["q32_fp"]
    result = dict(
        status="PASS_SYNTHETIC_DIRECTION_ONLY" if all(gates.values()) else "STOP_BEFORE_REAL_TRAINING",
        scientific_status="NOT_VERIFIED", seed=SEED, settings=previous["settings"],
        only_change="Stop the q32 guard gradient before the shared feature layer",
        trace=trace, run=run, initial=initial, archived_e0=reference["control"],
        archived_twcrps=reference["candidate"], archived_full_gradient=previous["candidate"], candidate=candidate,
        candidate_minus_e0=delta_e0, candidate_minus_twcrps=delta_twcrps,
        candidate_minus_full_gradient=delta_full, synthetic_direction_gates=gates,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        harness_sha256=hashlib.sha256(Path(__file__).with_name("a20_twcrps_synthetic.py").read_bytes()).hexdigest(),
        reference_sha256=REFERENCE_SHA256, previous_sha256=PREVIOUS_SHA256,
        real_source_payload_reads=0, real_checkpoints_loaded=0, formal_updates=0, final_2025_access=False,
    )
    with args.receipt.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(dict(status=result["status"], trace=trace, candidate=candidate, gates=gates)))


if __name__ == "__main__":
    main()
