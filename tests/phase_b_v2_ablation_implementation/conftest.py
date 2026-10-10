"""Synthetic-only fixtures; all optimizer/state-file operations are forbidden."""
from pathlib import Path
import sys
import pytest
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))


@pytest.fixture(autouse=True)
def forbid_updates_and_state_files(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Optimizer step or model-state file access is outside this synthetic scope")
    monkeypatch.setattr(torch, "load", forbidden)
    monkeypatch.setattr(torch, "save", forbidden)
    monkeypatch.setattr(torch, "expm1", forbidden)
    monkeypatch.setattr(torch.Tensor, "expm1", forbidden)
    for value in vars(torch.optim).values():
        if isinstance(value, type) and issubclass(value, torch.optim.Optimizer):
            monkeypatch.setattr(value, "step", forbidden)
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous_threads)


def synthetic_case(batch=2, height=2, width=3, dtype=torch.float32, device="cpu"):
    size = batch * height * width
    logit = torch.linspace(-2, 2, size, dtype=dtype, device=device).reshape(batch, 1, height, width).requires_grad_()
    q = (.2 + .04 * torch.arange(1, 33, dtype=torch.float64, device=device)).reshape(1, 32, 1, 1)
    q = q.expand(batch, 32, height, width).clone().requires_grad_()
    values = torch.tensor([0., .1, .2, 1., 5., 20.], dtype=torch.float32, device=device)
    rate = values[torch.arange(size, device=device) % 6].reshape(batch, 1, height, width)
    valid = torch.ones_like(rate, dtype=torch.bool)
    yunnan = valid.clone()
    return logit, q, rate, valid, yunnan
