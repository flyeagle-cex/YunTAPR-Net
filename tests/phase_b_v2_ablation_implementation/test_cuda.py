"""Optional, isolated and bounded CUDA synthetic loss tests; no model/optimizer."""
import os
import pytest
import torch
from conftest import synthetic_case
from yuntapr.experimental.phase_b_v2_ablations import candidate_loss, get_config

pytestmark = pytest.mark.skipif(os.environ.get("YUNTAPR_SYNTHETIC_CUDA") != "1",
                              reason="CUDA tests run only in the explicitly enabled bounded subprocess")


@pytest.mark.parametrize("arm", ["E0", "E1", "E2"])
def test_cuda_loss_and_gradients_match_CPU_synthetic(arm):
    if not torch.cuda.is_available(): pytest.skip("CUDA unavailable; no fake pass")
    cpu = synthetic_case(batch=1, height=1, width=3, dtype=torch.float64)
    gpu = tuple(x.detach().to("cuda").requires_grad_(x.requires_grad) for x in cpu)
    rc = candidate_loss(*cpu, config=get_config(arm)); rg = candidate_loss(*gpu, config=get_config(arm))
    rc.training_objective.backward(); rg.training_objective.backward(); torch.cuda.synchronize()
    torch.testing.assert_close(rg.training_objective.cpu(), rc.training_objective, rtol=1e-10, atol=1e-12)
    for c, g in zip(cpu[:2], gpu[:2]):
        torch.testing.assert_close(g.grad.cpu(), c.grad, rtol=1e-10, atol=1e-12)
