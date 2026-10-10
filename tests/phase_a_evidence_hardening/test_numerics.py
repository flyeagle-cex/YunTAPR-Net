"""Actual frozen v2 numerical APIs on tiny CPU fixtures; no backward/optimizer."""
import math
import numpy as np
import pytest
import torch
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics, normalized_monotonic_quantiles
from yuntapr.models.quantile_v2.outputs import LogDomainOutput, materialize_physical, physical_risk
from yuntapr.diagnostics.candidates import require_same_grid


def fixture(q):
    return LogDomainOutput(torch.zeros((1,1,1,1)), torch.ones((1,1,1,1))*.5, q)


def test_actual_normalized_head_32_outputs_33_raw_channels():
    with torch.no_grad():
        q = normalized_monotonic_quantiles(torch.zeros((1,32,1,1)), torch.zeros((1,1,1,1)),
                                          numerics=CandidateNumerics(1e-6, 1e-6))
    assert q.shape == (1,32,1,1) and q.dtype == torch.float64 and not q.requires_grad
    assert bool((q[:,1:] > q[:,:-1]).all())
    assert q[0,-1,0,0].item() == pytest.approx(math.log1p(.1)+math.log(2)+1e-6)
    assert not physical_risk(q)["FP64_PHYSICAL_OVERFLOW_RISK"]
    assert torch.isfinite(materialize_physical(fixture(q)).conditional_quantiles_physical).all()


def test_actual_head_rejects_nonfinite_raw():
    a = torch.zeros((1,32,1,1)); a[0,1] = float("nan")
    with torch.no_grad(), pytest.raises(FloatingPointError, match="RAW_NONFINITE"):
        normalized_monotonic_quantiles(a, torch.zeros((1,1,1,1)), numerics=CandidateNumerics(1e-6,1e-6))


def test_actual_head_rejects_lost_support_without_clipping():
    with torch.no_grad(), pytest.raises(FloatingPointError, match="SUPPORT_LOST"):
        normalized_monotonic_quantiles(torch.zeros((1,32,1,1)), torch.full((1,1,1,1), -1000.),
                                      numerics=CandidateNumerics(1e-300,1e-300))


def test_actual_physical_conversion_above_fp64_boundary_stops():
    q = torch.linspace(1.,1000.,32,dtype=torch.float64).reshape(1,32,1,1)
    assert physical_risk(q)["FP64_PHYSICAL_OVERFLOW_RISK"]
    with pytest.raises(FloatingPointError, match="PHYSICAL_OVERFLOW"):
        materialize_physical(fixture(q))


def test_actual_physical_fp32_risk_not_fp64():
    q = torch.linspace(1.,100.,32,dtype=torch.float64).reshape(1,32,1,1)
    r = physical_risk(q)
    assert r["FP32_PHYSICAL_OVERFLOW_RISK"] and not r["FP64_PHYSICAL_OVERFLOW_RISK"]


def test_aligned_grid_accepted():
    require_same_grid(np.arange(3), np.arange(3)[::-1], np.arange(3), np.arange(3)[::-1], absolute_tolerance=0)


@pytest.mark.parametrize("bad", [np.arange(3)+.5, np.arange(3)[::-1], np.arange(2), np.array([0,0,1])])
def test_half_cell_shift_flip_shape_or_duplicate_grid_rejected(bad):
    with pytest.raises(ValueError): require_same_grid(bad, np.arange(3), np.arange(3), np.arange(3), absolute_tolerance=1e-9)
