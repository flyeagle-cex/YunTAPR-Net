"""Artificial CPU fixtures for the isolated physical Pinball loss candidate."""

import argparse
from contextlib import ExitStack
import io
import json
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import torch

from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.physical_pinball import physical_pinball_loss
from yuntapr.experimental.phase_b_v2_ablations.total import candidate_loss
from yuntapr.experimental.phase_b_v2_ablations.validation import ZeroValidPixelsError


def fixture(rates):
    width = len(rates)
    logit = torch.zeros((1, 1, 1, width), dtype=torch.float64, requires_grad=True)
    nodes = torch.arange(1, 33, dtype=torch.float64).reshape(1, 32, 1, 1)
    qlog = torch.log1p(nodes).expand(1, 32, 1, width).clone().requires_grad_()
    rate = torch.tensor(rates, dtype=torch.float32).reshape(1, 1, 1, width)
    mask = torch.ones_like(rate, dtype=torch.bool)
    return logit, qlog, rate, mask, mask.clone()


def run_checks():
    checks = {}
    for label, truth in (("all_under", 40.0), ("all_over", .5)):
        args = fixture([truth])
        result = physical_pinball_loss(*args, config=get_config("E0"))
        expected = sum(
            max(((k - .5) / 32) * (truth - k) / 20,
                (((k - .5) / 32) - 1) * (truth - k) / 20)
            for k in range(1, 33)
        ) / 32
        assert math.isclose(result.weighted_quantile_per_valid.item(), expected, abs_tol=1e-13)
        result.training_objective.backward()
        expected_gradient = torch.tensor([
            (-(k - .5) / 32 if truth > k else 1 - (k - .5) / 32)
            * (k + 1) / (20 * 32)
            for k in range(1, 33)
        ], dtype=torch.float64).reshape(1, 32, 1, 1)
        torch.testing.assert_close(args[1].grad, expected_gradient, rtol=1e-12, atol=1e-13)
        base = candidate_loss(*args, config=get_config("E0"))
        torch.testing.assert_close(result.s_qr, base.s_qr, rtol=0, atol=0)
        torch.testing.assert_close(result.s_occ, base.s_occ, rtol=0, atol=0)
        torch.testing.assert_close(result.training_objective, result.s_occ + expected, rtol=1e-12, atol=1e-13)
        assert result.experiment_id == "PHYSICAL_PINBALL20_V1"
        checks[label + "_hand_value_gradient_and_inherited_diagnostics"] = True

    logit, qlog, rate, valid, region = fixture([40, .1, float("nan"), 40])
    valid[..., 2] = False
    region[..., 3] = False
    args = (logit, qlog, rate, valid, region)
    result = physical_pinball_loss(*args, config=get_config("E0"))
    base = candidate_loss(*args, config=get_config("E0"))
    expected_occ_grad = torch.autograd.grad(base.s_occ / base.n_valid, logit)[0]
    result.training_objective.backward()
    assert result.n_valid == 2 and result.n_rain == 1
    torch.testing.assert_close(logit.grad, expected_occ_grad, rtol=0, atol=0)
    assert torch.count_nonzero(qlog.grad[..., 1:]).item() == 0
    checks["threshold_equal_dry_invalid_labels_region_and_occurrence_gradient"] = True

    args = fixture([0, .1])
    result = physical_pinball_loss(*args, config=get_config("E0"))
    result.training_objective.backward()
    assert result.conditional_skipped and result.n_rain == 0
    assert result.weighted_quantile_per_valid.item() == 0
    assert torch.count_nonzero(args[1].grad).item() == 0
    checks["dry_batch_connected_zero"] = True

    for label, rates in (("wet_overflow", [40.0]), ("dry_overflow", [0.0])):
        logit, qlog, rate, valid, region = fixture(rates)
        qlog = (torch.arange(32, dtype=torch.float64) + 1000).reshape(1, 32, 1, 1).requires_grad_()
        try:
            physical_pinball_loss(logit, qlog, rate, valid, region, config=get_config("E0"))
        except FloatingPointError:
            checks[label + "_rejected"] = True
        else:
            raise AssertionError(label + " accepted")

    for label, config, zero_mask, exception in (
        ("e2_config", get_config("E2"), False, PermissionError),
        ("zero_valid", get_config("E0"), True, ZeroValidPixelsError),
    ):
        args = list(fixture([40]))
        if zero_mask:
            args[3].zero_()
        try:
            physical_pinball_loss(*args, config=config)
        except exception:
            checks[label + "_rejected"] = True
        else:
            raise AssertionError(label + " accepted")
    return checks


def run_integration_checks():
    from yuntapr.experimental.core_innovation.stage4 import engine
    from yuntapr.experimental.phase_b_v2_ablations.physical_pinball import PHYSICAL_PROFILE, profile_identity
    from yuntapr.experimental.phase_b_v2_ablations.schedule import COSINE9, ORIGINAL_50
    from yuntapr.experimental.phase_b_v2_ablations.upper_quantile import MILD_PROFILE, UNIFORM
    from yuntapr.experimental.research_readiness import dynamic_training

    checks = {}
    args = fixture([40.] * 3430)
    logit, qlog, rate, valid, region = args
    output = SimpleNamespace(rain_logit=logit, conditional_quantiles_log=qlog)
    model = MagicMock(return_value=output)
    model.kind, model.grid = "B7", object()
    batch = SimpleNamespace(
        identity={"population_sha256": engine.POPULATION_SHA}, ids=("ARTIFICIAL",),
        x=None, native_valid=None, environment=None, environment_valid=None,
        dynamic=object(), dynamic_valid=object(), rate=rate, valid=valid, region=region,
    )
    for profile, function, expected_id in (
        (UNIFORM, "candidate_loss", "E0"),
        (MILD_PROFILE, "upper_quantile_loss", MILD_PROFILE),
        (PHYSICAL_PROFILE, "physical_pinball_loss", PHYSICAL_PROFILE),
    ):
        with patch.object(engine, function, wraps=getattr(engine, function)) as selected:
            _, result = engine.forward(model, batch, quantile_profile=profile)
            assert selected.call_count == 1 and result.experiment_id == expected_id
        checks["forward_" + profile] = True

    decision = SimpleNamespace(seed=2029)
    origin = {"original_model_state_sha256": "a" * 64, "epoch_order_sha256": ["b" * 64] * 9}
    valid_options = dict(decision=decision, kinds=("B7",), lambda_q=1.0,
                         quantile_profile=PHYSICAL_PROFILE, schedule_profile=COSINE9,
                         origin_reference=origin)
    executor = engine.PairedExecutor(None, "ARTIFICIAL_NO_OUTPUT", **valid_options)
    assert executor.loss_identity == profile_identity()
    assert executor.modified_loss and executor.modified_schedule
    checks["executor_physical_profile_identity"] = True
    for label, changes in (
        ("wrong_model", dict(kinds=("B8",))),
        ("wrong_seed", dict(decision=SimpleNamespace(seed=2030))),
        ("wrong_lambda", dict(lambda_q=2.0)),
        ("wrong_schedule", dict(schedule_profile=ORIGINAL_50)),
        ("recovery", dict(recovery=object())),
        ("missing_origin", dict(origin_reference=None)),
    ):
        options = dict(valid_options, **changes)
        try:
            engine.PairedExecutor(None, "ARTIFICIAL_NO_OUTPUT", **options)
        except PermissionError:
            checks["executor_rejects_" + label] = True
        else:
            raise AssertionError("executor accepted " + label)
    for profile, schedule in ((UNIFORM, ORIGINAL_50), (MILD_PROFILE, ORIGINAL_50), (UNIFORM, COSINE9)):
        engine.PairedExecutor(None, "ARTIFICIAL_NO_OUTPUT", **dict(
            valid_options, quantile_profile=profile, schedule_profile=schedule))
    checks["existing_profiles_constructor_preserved"] = True

    proposal = dict(
        protocol=dict(loss="E0", lambda_q=1.0, quantile_profile=PHYSICAL_PROFILE, schedule_profile=COSINE9),
        budget=dict(minimum_task_free_bytes=0, max_model_seconds=60),
        static_source_sha256={"B7": "c" * 64}, data={"population_sha256": engine.POPULATION_SHA},
        scientific_choices=dict(origin_reference={"B7": origin}, DOTE={}, modulation_limit=.1),
    )
    private = dict(output_root="ARTIFICIAL_NO_OUTPUT", terrain="ARTIFICIAL_NO_SOURCE")
    prepared = dict(private_inputs=dict(stage3_run="ARTIFICIAL", request="ARTIFICIAL"))
    fake_meter = MagicMock()
    fake_meter.open.side_effect = lambda *a, **k: io.BytesIO(b"ARTIFICIAL")
    fake_meter.totals.return_value = dict(bytes=312828, files=1)
    fake_executor = MagicMock()
    fake_plan = SimpleNamespace(identity=proposal["data"])
    with ExitStack() as stack:
        stack.enter_context(patch.dict(dynamic_training.os.environ, {"PYTHONHASHSEED": "2029"}))
        replacements = {
            "SourceMeter": MagicMock(return_value=fake_meter),
            "unpack": MagicMock(return_value=object()),
            "read": MagicMock(return_value=dict(scalers={})),
            "PopulationPlan": MagicMock(return_value=fake_plan),
            "DoteDefinition": MagicMock(return_value=object()),
            "model_factory": MagicMock(return_value=object()),
            "PairedExecutor": fake_executor,
            "ReaderFactory": MagicMock(return_value=object()),
            "endpoint": MagicMock(return_value=dict(logical_source_bytes=0, logical_source_files=0)),
            "write": MagicMock(),
        }
        for name, replacement in replacements.items():
            stack.enter_context(patch.object(dynamic_training, name, replacement))
        connect = stack.enter_context(patch.object(dynamic_training.sqlite3, "connect", return_value=MagicMock()))
        stack.enter_context(patch.object(dynamic_training.shutil, "disk_usage", return_value=SimpleNamespace(free=100)))
        result = dynamic_training.run_task(
            Path("."), proposal, private, dict(decision_id="ARTIFICIAL"), prepared, "d" * 40,
            "B7", 2029, started=time.monotonic(), pair_reference=None, static_name="ARTIFICIAL.sqlite",
            dynamic_transform_factory=MagicMock(return_value=object()),
            quantile_profile=PHYSICAL_PROFILE, schedule_profile=COSINE9,
        )
        kwargs = fake_executor.call_args.kwargs
        assert kwargs["quantile_profile"] == PHYSICAL_PROFILE and kwargs["schedule_profile"] == COSINE9
        assert kwargs["origin_reference"] == origin and kwargs["lambda_q"] == 1.0
        assert fake_executor.return_value.run.call_count == 1
        assert result["loss_arm"] == PHYSICAL_PROFILE
        checks["dynamic_task_forwards_bound_profile_to_executor_without_io"] = True
        count = connect.call_count
        for label, changes in (
            ("wrong_schedule", dict(schedule_profile=ORIGINAL_50)),
            ("profile_mismatch", dict(quantile_profile=UNIFORM)),
            ("wrong_seed", dict(seed=2030)),
            ("wrong_model", dict(kind="B8")),
        ):
            options = dict(kind="B7", seed=2029, quantile_profile=PHYSICAL_PROFILE, schedule_profile=COSINE9)
            options.update(changes)
            try:
                dynamic_training.run_task(
                    Path("."), proposal, private, dict(decision_id="ARTIFICIAL"), prepared, "d" * 40,
                    started=time.monotonic(), pair_reference=None, static_name="ARTIFICIAL.sqlite", **options)
            except PermissionError:
                checks["dynamic_rejects_" + label + "_before_io"] = True
            else:
                raise AssertionError("dynamic accepted " + label)
        assert connect.call_count == count
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--integration", action="store_true")
    args = parser.parse_args()
    checks = run_checks()
    if args.integration:
        checks.update(run_integration_checks())
    receipt = {
        "status": "PASS_ARTIFICIAL_CPU_ONLY",
        "profile": "PHYSICAL_PINBALL20_V1",
        "torch_version": torch.__version__,
        "checks": checks,
        "checks_passed": len(checks),
        "internal_profile_channel_connected": args.integration,
        "formal_dispatcher_prepared": False,
        "raw_data_reads": 0,
        "checkpoint_reads": 0,
        "model_forwards": 0,
        "optimizer_updates": 0,
        "scientific_acceptance": "NOT_VERIFIED",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "checks_passed": len(checks)}))


if __name__ == "__main__":
    main()
