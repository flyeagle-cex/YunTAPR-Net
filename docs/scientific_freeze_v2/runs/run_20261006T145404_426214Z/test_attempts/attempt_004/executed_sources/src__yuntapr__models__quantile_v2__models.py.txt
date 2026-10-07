"""Fresh version-isolated models; no checkpoint loader, optimizer or training loop."""
import torch
from torch import nn
from yuntapr.contracts.loader import REPO_ROOT, load_contract
from yuntapr.models.backbone_b0 import B0Backbone
from yuntapr.models.b1 import B1Backbone
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.spatial.projection import SP04Projection
from .heads import ProbabilityHeadsV2
from .parameterization import CandidateNumerics


class _ModelV2(nn.Module):
    def __init__(self, frames, *, numerics: CandidateNumerics, root=REPO_ROOT):
        super().__init__()
        science, engineering = load_contract(root)
        self.frames = frames
        factory = B0Backbone if frames == 1 else B1Backbone
        self.backbone = factory(engineering['backbone'], tuple(science['backbone']['channels']))
        self.projection = SP04Projection(load_sp04(root), engineering['projection']['feature_reduction_operator'])
        self.heads = ProbabilityHeadsV2(numerics=numerics)

    def forward(self, x, valid_mask):
        if x.ndim != 4 or x.shape[1:] != (self.frames, 501, 501):
            raise ValueError("Frozen latest/six-slot input shape required")
        if valid_mask.shape != x.shape or valid_mask.dtype != torch.bool:
            raise ValueError("Independent bool native validity mask required")
        if not bool(valid_mask.all()) or not bool(torch.isfinite(x).all()):
            raise ValueError("Strict full-valid matched samples only; no placeholder or fallback")
        native = self.backbone(x)
        target = self.projection(native)
        output = self.heads(target)
        output.native_feature_shape = tuple(native.shape)
        output.target_feature_shape = tuple(target.shape)
        reduced_mask = valid_mask.all(dim=1, keepdim=True)
        output.target_support_fraction = self.projection.support_fraction(reduced_mask)
        output.b13_invalid_count = torch.zeros(x.shape[0], dtype=torch.int64, device=x.device)
        output.b13_valid_fraction = reduced_mask.flatten(1).sum(-1) / (501 * 501)
        return output


class B0MatchedV2(_ModelV2):
    def __init__(self, *, numerics: CandidateNumerics, root=REPO_ROOT):
        super().__init__(1, numerics=numerics, root=root)


class B1V2(_ModelV2):
    def __init__(self, *, numerics: CandidateNumerics, root=REPO_ROOT):
        super().__init__(6, numerics=numerics, root=root)
