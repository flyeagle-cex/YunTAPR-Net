"""Hand oracles, original-loss comparisons and explicit rejection boundaries."""
from types import SimpleNamespace
import math
import pytest
import torch
from conftest import synthetic_case
from yuntapr.experimental.phase_b_v2_ablations import candidate_loss, get_config, occurrence_numerator
from yuntapr.experimental.phase_b_v2_ablations.pinball import _pinball_from_errors, conditional_pinball_numerator, frozen_taus
from yuntapr.experimental.phase_b_v2_ablations.total import combine_numerators
from yuntapr.experimental.phase_b_v2_ablations.validation import ZeroValidPixelsError, graph_zero
from yuntapr.experimental.phase_b_v2_ablations.metrics import ReportingSums, common_validation_sums
from yuntapr.losses.focal import focal_bce_sum as original_focal
from yuntapr.losses.pinball import pinball_sum as original_pinball
from yuntapr.losses.total_loss import b0_core_loss as original_total


@pytest.mark.parametrize("rain,gamma,count,expected", [
    (True, 2., 1, math.log(2)/8), (True, 0., 1, math.log(2)/2),
    (False, 2., 1, math.log(2)/8), (True, 0., 2, math.log(2))])
def test_hand_F1_F4(rain, gamma, count, expected):
    l = torch.zeros(1, 1, 1, count, dtype=torch.float64)
    labels = torch.full_like(l, rain, dtype=torch.bool)
    result = occurrence_numerator(l, labels, torch.ones_like(labels), alpha=.5, gamma=gamma)
    assert float(result) == pytest.approx(expected, rel=1e-12, abs=1e-14)


@pytest.mark.parametrize("error,active,expected", [(1., True, .5), (-1., True, .5), (0., True, 0.), (1., False, 0.)])
def test_hand_P1_P4_signed_errors_only(error, active, expected):
    errors = torch.full((1, 32, 1, 1), error, dtype=torch.float64, requires_grad=True)
    mask = torch.full((1, 1, 1, 1), active, dtype=torch.bool)
    result = _pinball_from_errors(errors, mask)
    assert float(result.detach()) == expected
    result.backward()
    assert errors.grad is not None and torch.isfinite(errors.grad).all()


@pytest.mark.parametrize("weight,expected", [(1., .5), (2., .8)])
def test_hand_T1(weight, expected):
    result = combine_numerators(torch.tensor(2.), torch.tensor(3., dtype=torch.float64), 10, lambda_q=weight)
    assert float(result) == expected


def test_hand_T2_scientific_denominator():
    assert ReportingSums(2., 3., 10, 2).conditional_pinball == 1.5


def test_all_32_taus_exact():
    tau = frozen_taus()
    assert tau.dtype == torch.float64 and tau.shape == (32,)
    assert tau.tolist() == [(i - .5)/32 for i in range(1, 33)]
    assert float(tau[-1]) == .984375


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64, torch.bfloat16, torch.float16])
@pytest.mark.parametrize("gamma", [0., 2.])
def test_precision_path_and_E0_focal_oracle(dtype, gamma):
    l, _, y, valid, _ = synthetic_case(dtype=dtype)
    rainy = y > .1
    actual = occurrence_numerator(l, rainy, valid, alpha=.5, gamma=gamma)
    arithmetic_l = l.double() if dtype == torch.float64 else l.float()
    expected = original_focal(arithmetic_l, rainy, valid, .5, gamma)
    torch.testing.assert_close(actual, expected, rtol=8e-7 if dtype != torch.float64 else 1e-12, atol=1e-8 if dtype != torch.float64 else 1e-14)
    assert actual.dtype == (torch.float64 if dtype == torch.float64 else torch.float32)
    actual.backward()
    assert l.grad.dtype == dtype and torch.isfinite(l.grad).all()


@pytest.mark.parametrize("batch", [1, 2, 3, 5])
@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_E0_original_total_and_gradient_compatibility(batch, dtype):
    l, q, y, valid, mask = synthetic_case(batch=batch, dtype=dtype)
    valid.reshape(-1)[-1] = False
    mask.reshape(-1)[0] = False
    original = original_total(SimpleNamespace(rain_logit=l, conditional_quantiles_log=q), y, valid, mask,
                              focal_alpha=.5, focal_gamma=2., quantile_axis_reduction="mean")
    actual = candidate_loss(l, q, y, valid, mask, config=get_config("E0"))
    torch.testing.assert_close(actual.training_objective, original.total, rtol=8e-7, atol=1e-8)
    assert actual.n_valid == original.valid_supervised_count and actual.n_rain == original.rainy_valid_count
    old_grads = torch.autograd.grad(original.total, (l, q), retain_graph=True)
    new_grads = torch.autograd.grad(actual.training_objective, (l, q))
    for a, b in zip(new_grads, old_grads):
        torch.testing.assert_close(a, b, rtol=8e-7, atol=1e-8)
    selected = valid & mask
    old_q = original_pinball(q, torch.log1p(torch.where(selected, y, 0).double()), (y > .1) & selected, "mean")
    torch.testing.assert_close(actual.s_qr, old_q, rtol=1e-12, atol=1e-14)


def test_B1_float32_threshold_before_promotion():
    l, q, y, valid, mask = synthetic_case(batch=1, height=1, width=3)
    boundary = torch.tensor(.1, dtype=torch.float32)
    y.reshape(-1)[:] = torch.stack((torch.nextafter(boundary, torch.tensor(0.)), boundary,
                                   torch.nextafter(boundary, torch.tensor(float("inf")))))
    r = candidate_loss(l, q, y, valid, mask, config=get_config("E0"))
    assert r.n_rain == 1
    # FP64 comparison with decimal .1 would mislabel the middle float32 value.
    assert int((y.double() > .1).sum()) == 2


def test_Z1_no_rain_connected_zero_and_NA_metric():
    l, q, y, valid, mask = synthetic_case()
    y.zero_()
    result = candidate_loss(l, q, y, valid, mask, config=get_config("E2"))
    assert result.n_valid == 12 and result.n_rain == 0 and result.conditional_skipped
    assert result.s_qr.dtype == torch.float64 and result.s_qr.requires_grad
    assert result.scientific_conditional_pinball is None
    result.training_objective.backward()
    assert torch.equal(q.grad, torch.zeros_like(q)) and l.grad is not None


def test_Z2_zero_valid_is_explicit_error_not_skip():
    args = synthetic_case()
    args[3].zero_()
    with pytest.raises(ZeroValidPixelsError, match="ZERO_VALID"):
        candidate_loss(*args, config=get_config("E0"))


def test_invalid_reference_NaN_is_temporarily_cleaned_without_mutation():
    l, q, y, valid, mask = synthetic_case()
    valid.reshape(-1)[0] = False
    y.reshape(-1)[0] = float("nan")
    before = y.clone()
    result = candidate_loss(l, q, y, valid, mask, config=get_config("E0"))
    assert torch.isfinite(result.training_objective)
    torch.testing.assert_close(y, before, equal_nan=True)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.])
def test_valid_bad_reference_rejected(bad):
    args = synthetic_case()
    args[2].reshape(-1)[0] = bad
    with pytest.raises(ValueError, match="finite nonnegative"):
        candidate_loss(*args, config=get_config("E0"))


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_outputs_even_at_invalid_pixels_rejected(index, bad):
    args = list(synthetic_case())
    args[3].reshape(-1)[0] = False
    args[index] = args[index].detach().clone()
    args[index].reshape(-1)[0] = bad
    with pytest.raises(FloatingPointError):
        candidate_loss(*args, config=get_config("E0"))


@pytest.mark.parametrize("bad_kind", ["constant", "crossing", "support_equal", "support_below", "FP32", "31taus"])
def test_quantile_order_support_precision_reject(bad_kind):
    l, q, y, valid, mask = synthetic_case()
    q = q.detach().clone()
    if bad_kind == "constant": q.fill_(1.)
    elif bad_kind == "crossing": q[:, 5] = q[:, 4] - .01
    elif bad_kind == "support_equal": q[:, 0] = math.log1p(.1)
    elif bad_kind == "support_below": q[:, 0] = 0.
    elif bad_kind == "FP32": q = q.float()
    else: q = q[:, :31]
    with pytest.raises((ValueError, FloatingPointError)):
        candidate_loss(l, q, y, valid, mask, config=get_config("E0"))


@pytest.mark.parametrize("index", [0, 1, 2, 3, 4])
def test_shape_mismatch_no_broadcast(index):
    args = list(synthetic_case())
    args[index] = args[index][..., :1]
    with pytest.raises(ValueError): candidate_loss(*args, config=get_config("E0"))


@pytest.mark.parametrize("index", [3, 4])
def test_masks_require_bool(index):
    args = list(synthetic_case())
    args[index] = args[index].float()
    with pytest.raises(ValueError, match="bool"): candidate_loss(*args, config=get_config("E0"))


@pytest.mark.parametrize("dtype", [torch.float64, torch.float16, torch.int64])
def test_reference_requires_original_FP32(dtype):
    args = list(synthetic_case())
    args[2] = args[2].to(dtype)
    with pytest.raises(ValueError, match="float32"): candidate_loss(*args, config=get_config("E0"))


@pytest.mark.parametrize("index", [1, 2, 3, 4])
def test_device_mismatch_before_tensor_arithmetic(index):
    args = list(synthetic_case())
    args[index] = torch.empty_like(args[index], device="meta")
    with pytest.raises(ValueError, match="device"): candidate_loss(*args, config=get_config("E0"))


@pytest.mark.parametrize("name,bad", [("alpha", True), ("gamma", True), ("alpha", None), ("gamma", None),
    ("alpha", float("nan")), ("gamma", float("nan")), ("gamma", float("inf")),
    ("alpha", -.1), ("alpha", 1.1), ("gamma", -1.), ("alpha", "0.5")])
def test_focal_bad_parameters_reject(name, bad):
    l, _, y, valid, _ = synthetic_case()
    params = {"alpha": .5, "gamma": 2.}; params[name] = bad
    with pytest.raises(ValueError): occurrence_numerator(l, y > .1, valid, **params)


@pytest.mark.parametrize("weight", [0, -1, True, float("nan"), float("inf"), None])
def test_bad_weight_rejected(weight):
    with pytest.raises(ValueError): combine_numerators(torch.tensor(1.), torch.tensor(1., dtype=torch.float64), 2, lambda_q=weight)


@pytest.mark.parametrize("count", [0, -1, True, 1.5])
def test_bad_denominator_rejected(count):
    with pytest.raises(ValueError): combine_numerators(torch.tensor(1.), torch.tensor(1., dtype=torch.float64), count, lambda_q=1)


def test_class_imbalance_sum_not_mean():
    l = torch.zeros(1, 1, 1, 101, dtype=torch.float64)
    labels = torch.zeros_like(l, dtype=torch.bool); labels[..., -1] = True
    result = occurrence_numerator(l, labels, torch.ones_like(labels), alpha=.5, gamma=0)
    assert float(result) == pytest.approx(101 * math.log(2)/2)


@pytest.mark.parametrize("gamma", [0., 2.])
def test_extreme_finite_logits(gamma):
    l = torch.tensor([-1000., 1000., -1e30, 1e30], dtype=torch.float32).reshape(1, 1, 1, 4).requires_grad_()
    labels = torch.tensor([True, False, True, False]).reshape_as(l)
    result = occurrence_numerator(l, labels, torch.ones_like(labels), alpha=.5, gamma=gamma)
    assert torch.isfinite(result)
    result.backward(); assert torch.isfinite(l.grad).all()


def test_empty_view_graph_zero_avoids_sum_overflow():
    l = torch.full((1, 1, 1, 32), 1e38, requires_grad=True)
    result = occurrence_numerator(l, torch.zeros_like(l, dtype=torch.bool), torch.zeros_like(l, dtype=torch.bool), alpha=.5, gamma=0)
    assert float(result.detach()) == 0
    result.backward(); assert torch.equal(l.grad, torch.zeros_like(l))


def test_no_expm1_even_beyond_physical_float64_boundary():
    args = list(synthetic_case())
    args[1] = (710. + torch.arange(32, dtype=torch.float64)/10).reshape(1, 32, 1, 1).expand_as(args[1]).clone().requires_grad_()
    result = candidate_loss(*args, config=get_config("E0"))
    assert torch.isfinite(result.training_objective)
    result.training_objective.backward(); assert torch.isfinite(args[1].grad).all()


def test_combine_overflow_explicitly_rejected():
    with pytest.raises(FloatingPointError):
        combine_numerators(torch.tensor(1e308, dtype=torch.float64), torch.tensor(1e308, dtype=torch.float64), 1, lambda_q=2)


def test_E1_E2_single_factor_and_unweighted_metric_separation():
    args = synthetic_case()
    outputs = {arm: candidate_loss(*args, config=get_config(arm)) for arm in ("E0", "E1", "E2")}
    assert torch.equal(outputs["E0"].s_occ, outputs["E2"].s_occ)
    for arm in ("E1", "E2"):
        assert torch.equal(outputs["E0"].s_qr, outputs[arm].s_qr)
        assert torch.equal(outputs["E0"].scientific_conditional_pinball, outputs[arm].scientific_conditional_pinball)
    expected = outputs["E0"].training_objective + outputs["E0"].s_qr / outputs["E0"].n_valid
    torch.testing.assert_close(outputs["E2"].training_objective, expected, rtol=1e-12, atol=1e-14)
    assert not outputs["E0"].execution_authorization


def test_common_validation_FP64_E0_independent_of_training_arm():
    args = synthetic_case()
    reported = common_validation_sums(*args)
    original = original_total(SimpleNamespace(rain_logit=args[0].double(), conditional_quantiles_log=args[1]), *args[2:],
                              focal_alpha=.5, focal_gamma=2., quantile_axis_reduction="mean")
    assert (reported.s_occ + reported.s_qr)/reported.n_valid == pytest.approx(float(original.total.detach()), rel=1e-12)
    assert reported.pooled(reported).conditional_pinball == reported.conditional_pinball


@pytest.mark.parametrize("bad", ["dtype", "shape", "negative", "nan", "mask_float", "mask_broadcast", "dry_selected"])
def test_public_pinball_rejects_ambiguous_target_and_masks(bad):
    _, q, y, valid, _ = synthetic_case()
    log_target = torch.log1p(torch.ones_like(y).double())
    if bad == "dtype": log_target = log_target.float()
    elif bad == "shape": log_target = log_target[..., :1]
    elif bad == "negative": log_target.fill_(-1)
    elif bad == "nan": log_target.fill_(float("nan"))
    elif bad == "mask_float": valid = valid.float()
    elif bad == "mask_broadcast": valid = valid[:1]
    else: log_target.zero_()
    with pytest.raises((ValueError, FloatingPointError)):
        conditional_pinball_numerator(q, log_target, valid)


@pytest.mark.parametrize("bad", ["integer_logit", "float_labels", "label_shape", "float_mask", "empty_batch"])
def test_bare_focal_rejects_dtype_and_shape(bad):
    l, _, y, valid, _ = synthetic_case()
    labels = y > .1
    if bad == "integer_logit": l = l.detach().long()
    elif bad == "float_labels": labels = labels.float()
    elif bad == "label_shape": labels = labels[:1]
    elif bad == "float_mask": valid = valid.float()
    else: l, labels, valid = l[:0], labels[:0], valid[:0]
    with pytest.raises(ValueError): occurrence_numerator(l, labels, valid, alpha=.5, gamma=2)


@pytest.mark.parametrize("gamma", [0., 2.])
def test_BF16_input_matches_frozen_autocast_BCE_path(gamma):
    l, q, y, valid, mask = synthetic_case(dtype=torch.bfloat16)
    with torch.autocast("cpu", dtype=torch.bfloat16):
        actual = occurrence_numerator(l, y > .1, valid, alpha=.5, gamma=gamma)
        original = original_focal(l, y > .1, valid, .5, gamma)
    assert actual.dtype == original.dtype == torch.float32
    torch.testing.assert_close(actual, original, rtol=8e-7, atol=1e-8)


def test_combine_device_mismatch_rejected_before_finite_operations():
    with pytest.raises(ValueError, match="device"):
        combine_numerators(torch.tensor(1.), torch.empty((), dtype=torch.float64, device="meta"), 1, lambda_q=1.)
