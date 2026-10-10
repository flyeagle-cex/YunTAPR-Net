from pathlib import Path
import json
import os
import pytest
import torch
from yuntapr.experimental.phase_b_v2_integration.safety import synthetic_operation_guards


@pytest.fixture(autouse=True)
def isolated():
    before = torch.get_num_threads()
    torch.set_num_threads(2)
    with synthetic_operation_guards():
        yield
    torch.set_num_threads(before)


@pytest.fixture
def record():
    def write(name, data):
        target = Path(os.environ["YUNTAPR_SYNTHETIC_EVIDENCE"])/(name+".json")
        with target.open("x",encoding="utf-8",newline="\n") as stream:
            json.dump(data,stream,indent=2)
            stream.write("\n")
    return write
