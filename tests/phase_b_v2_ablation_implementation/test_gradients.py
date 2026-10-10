"""Independent analytic oracles and double-precision finite differences."""
import pytest
import torch
from conftest import synthetic_case
from yuntapr.experimental.phase_b_v2_ablations import candidate_loss, get_config, occurrence_numerator
from yuntapr.experimental.phase_b_v2_ablations.pinball import _pinball_from_errors, frozen_taus


@pytest.mark.parametrize("gamma", [0., 2.])
def test_focal_analytic_gradient(gamma):
    l = torch.tensor([-2., -.3, .7, 2.], dtype=torch.float64).reshape(1, 1, 1, 4).requires_grad_()
    labels = torch.tensor([True, False, True, False]).reshape_as(l)
    occurrence_numerator(l, labels, torch.ones_like(labels), alpha=.5, gamma=gamma).backward()
    p, z = torch.sigmoid(l.detach()), labels.double()
    b = torch.nn.functional.binary_cross_entropy_with_logits(l.detach(), z, reduction="none")
    pt = torch.exp(-b); mod = 1 - pt
    expected = .5 * (p - z) if gamma == 0 else .5 * (p - z) * (mod.pow(gamma) + gamma * b * pt * mod.pow(gamma-1))
    torch.testing.assert_close(l.grad, expected, rtol=1e-12, atol=1e-14)


@pytest.mark.parametrize("gamma", [0., 2.])
def test_focal_gradcheck_and_second_derivative(gamma):
    l = torch.tensor([-.7, .3], dtype=torch.float64).reshape(1, 1, 1, 2).requires_grad_()
    labels = torch.tensor([True, False]).reshape_as(l); valid = torch.ones_like(labels)
    fn = lambda x: occurrence_numerator(x, labels, valid, alpha=.5, gamma=gamma)
    assert torch.autograd.gradcheck(fn, (l,), eps=1e-6, atol=1e-6, rtol=1e-5)
    assert torch.autograd.gradgradcheck(fn, (l,), eps=1e-6, atol=1e-6, rtol=1e-5)


@pytest.mark.parametrize("sign", [1., -1.])
def test_all_tau_pinball_analytic_gradient(sign):
    error = torch.full((1, 32, 1, 1), sign, dtype=torch.float64, requires_grad=True)
    _pinball_from_errors(error, torch.ones(1, 1, 1, 1, dtype=torch.bool)).backward()
    expected = (frozen_taus() if sign > 0 else frozen_taus()-1)/32
    torch.testing.assert_close(error.grad.reshape(32), expected, rtol=0, atol=0)


@pytest.mark.parametrize("arm", ["E0", "E1", "E2"])
def test_total_gradcheck_both_heads_away_from_kinks(arm):
    l, q, y, valid, mask = synthetic_case(batch=1, height=1, width=2, dtype=torch.float64)
    y.fill_(20.)
    fn = lambda x, v: candidate_loss(x, v, y, valid, mask, config=get_config(arm)).training_objective
    assert torch.autograd.gradcheck(fn, (l, q), eps=1e-6, atol=1e-6, rtol=1e-5)


@pytest.mark.parametrize("arm", ["E0", "E1", "E2"])
def test_total_q_gradient_weight_and_single_coordinate_difference(arm):
    l, q, y, valid, mask = synthetic_case(batch=1, height=1, width=2, dtype=torch.float64)
    y.fill_(20.)
    result = candidate_loss(l, q, y, valid, mask, config=get_config(arm))
    result.training_objective.backward()
    expected = (-get_config(arm).lambda_q * frozen_taus()/32/2).reshape(1, 32, 1, 1).expand_as(q)
    torch.testing.assert_close(q.grad, expected, rtol=1e-12, atol=1e-14)
    eps = 1e-6
    plus, minus = q.detach().clone(), q.detach().clone()
    plus[0, 31, 0, 1] += eps; minus[0, 31, 0, 1] -= eps
    vp = candidate_loss(l.detach(), plus, y, valid, mask, config=get_config(arm)).training_objective
    vm = candidate_loss(l.detach(), minus, y, valid, mask, config=get_config(arm)).training_objective
    difference = float((vp-vm)/(2*eps))
    assert difference == pytest.approx(float(q.grad[0, 31, 0, 1]), rel=2e-8, abs=1e-9)


def test_invalid_pixels_have_zero_gradients():
    args = synthetic_case()
    args[3].reshape(-1)[0] = False
    result = candidate_loss(*args, config=get_config("E2")); result.training_objective.backward()
    assert float(args[0].grad.reshape(-1)[0]) == 0
    assert torch.equal(args[1].grad[0, :, 0, 0], torch.zeros(32, dtype=torch.float64))
