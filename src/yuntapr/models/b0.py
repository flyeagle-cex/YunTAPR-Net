"""B0 single-B13 forward only; no optimizer or formal training loop."""
import torch
from torch import nn
from yuntapr.contracts.loader import REPO_ROOT, load_contract
from yuntapr.models.backbone_b0 import B0Backbone
from yuntapr.models.probability_heads import B0Output, ProbabilityHeads
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.spatial.projection import SP04Projection


class B0Model(nn.Module):
    def __init__(self, root=REPO_ROOT):
        super().__init__()
        science, engineering = load_contract(root)
        self.placeholder = float(engineering["missing"]["tensor_placeholder"])
        self.backbone = B0Backbone(engineering["backbone"], tuple(science["backbone"]["channels"]))
        self.projection = SP04Projection(load_sp04(root), engineering["projection"]["feature_reduction_operator"])
        self.heads = ProbabilityHeads(48, float(science["probability"]["occurrence"]["threshold"]))

    def forward(self, x_b13: torch.Tensor, b13_valid_mask: torch.Tensor) -> B0Output:
        if x_b13.ndim != 4 or x_b13.shape[1:] != (1, 501, 501):
            raise ValueError("B0 input must be [B,1,501,501]")
        if b13_valid_mask.shape != x_b13.shape or b13_valid_mask.dtype != torch.bool:
            raise ValueError("B13 requires independent bool validity mask")
        if not torch.isfinite(x_b13[b13_valid_mask]).all():
            raise ValueError("Valid B13 input contains nonfinite value")
        valid_counts = b13_valid_mask.flatten(1).sum(-1)
        if (valid_counts == 0).any():
            raise ValueError("B13 all-fill sample rejected")
        x = torch.where(b13_valid_mask, x_b13, torch.as_tensor(self.placeholder, dtype=x_b13.dtype, device=x_b13.device))
        native = self.backbone(x)
        target = self.projection(native)
        logit, prob, qlog, qphysical = self.heads(target)
        return B0Output(logit, prob, qlog, qphysical, prob * qphysical.mean(dim=1, keepdim=True), tuple(native.shape), tuple(target.shape), self.projection.support_fraction(b13_valid_mask), (501 * 501 - valid_counts), valid_counts / (501 * 501))
