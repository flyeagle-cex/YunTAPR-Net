from pathlib import Path
import json
import os
import sys
import pytest
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from yuntapr.experimental.phase_b_v2_integration.safety import synthetic_operation_guards
from yuntapr.experimental.phase_b_v2_integration.synthetic import make_synthetic_pair


@pytest.fixture(autouse=True)
def isolated_operations():
    previous = torch.get_num_threads()
    torch.set_num_threads(2)
    with synthetic_operation_guards():
        yield
    torch.set_num_threads(previous)


@pytest.fixture
def pair():
    return make_synthetic_pair()


@pytest.fixture
def record():
    def write(name, data):
        output = Path(os.environ["YUNTAPR_SYNTHETIC_EVIDENCE"])
        output.mkdir(parents=True, exist_ok=True)
        with (output / (name + ".json")).open("x", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
    return write

