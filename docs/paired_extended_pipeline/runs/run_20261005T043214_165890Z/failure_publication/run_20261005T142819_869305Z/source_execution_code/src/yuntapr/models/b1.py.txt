"""Six causal B13 channels; otherwise the frozen B0 architecture and heads."""
import torch
from torch import nn
from yuntapr.contracts.loader import REPO_ROOT, load_contract
from yuntapr.models.b0 import B0Model
from yuntapr.models.backbone_b0 import B0Backbone
from yuntapr.models.blocks import ResidualBlock
from yuntapr.models.probability_heads import ProbabilityHeads
from yuntapr.spatial.projection import SP04Projection
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.phase_a_protocol import seed_reproducibility, state_digest


class B1Backbone(B0Backbone):
    def __init__(self, cfg, channels):
        nn.Module.__init__(self)
        if tuple(channels) != (48,96,192,256):
            raise ValueError('Frozen backbone channels required')
        groups=cfg['groupnorm_groups']; kernel=cfg['downsample_kernel']; pad=cfg['downsample_padding']
        self.mode=cfg['decoder_interpolation_mode']; self.align_corners=cfg['align_corners']
        self.enc0=ResidualBlock(6,48,groups)
        if cfg['input_projection_skip_initialization']!='zeros':
            raise ValueError('Inherited native skip initialization must remain zeros')
        nn.init.zeros_(self.enc0.skip.weight); nn.init.zeros_(self.enc0.skip.bias)
        self.down1=nn.Conv2d(48,96,kernel,stride=2,padding=pad); self.enc1=ResidualBlock(96,96,groups)
        self.down2=nn.Conv2d(96,192,kernel,stride=2,padding=pad); self.enc2=ResidualBlock(192,192,groups)
        self.down3=nn.Conv2d(192,256,kernel,stride=2,padding=pad); self.enc3=ResidualBlock(256,256,groups)
        self.dec2=ResidualBlock(448,192,groups); self.dec1=ResidualBlock(288,96,groups); self.dec0=ResidualBlock(144,48,groups)

    def forward(self,x):
        if x.ndim!=4 or x.shape[1:]!=(6,501,501):
            raise ValueError('B1 input must be [B,6,501,501]')
        s0=self.enc0(x); s1=self.enc1(self.down1(s0)); s2=self.enc2(self.down2(s1)); s3=self.enc3(self.down3(s2))
        out=self.dec0(self._up(self.dec1(self._up(self.dec2(self._up(s3,s2)),s1)),s0))
        if out.shape[1:]!=(48,501,501): raise RuntimeError('Native feature shape mismatch')
        return out


class B1Model(B0Model):
    def __init__(self, root=REPO_ROOT):
        nn.Module.__init__(self)
        science,eng=load_contract(root)
        self.backbone=B1Backbone(eng['backbone'],tuple(science['backbone']['channels']))
        self.projection=SP04Projection(load_sp04(root),eng['projection']['feature_reduction_operator'])
        self.heads=ProbabilityHeads(48,.1,epsilon_mono=eng['quantile_numerics']['epsilon_mono'],
                                   accumulation_dtype=getattr(torch,eng['quantile_numerics']['accumulation_dtype']))

    def forward(self,x,b13_valid_mask):
        if x.ndim!=4 or x.shape[1:]!=(6,501,501) or b13_valid_mask.shape!=x.shape or b13_valid_mask.dtype!=torch.bool:
            raise ValueError('Six ordered full-valid channels required')
        if not bool(b13_valid_mask.all()) or not bool(torch.isfinite(x).all()):
            raise ValueError('M1 rejects the entire sample; placeholders are forbidden')
        mask=b13_valid_mask.all(dim=1,keepdim=True)
        out=self._evaluate(x,mask,mask.flatten(1).sum(-1))
        out.placeholder_policy='FULL_VALID_NORMALIZED_NO_PLACEHOLDER'
        return out


MISMATCHED={'backbone.enc0.conv1.weight','backbone.enc0.skip.weight'}


def paired_models(root=REPO_ROOT):
    """Independent fresh reseeds, then copy only equal-name/equal-shape tensors."""
    seed_reproducibility(); anchor=B0Model(root)
    seed_reproducibility(); temporal=B1Model(root)
    a,b=anchor.state_dict(),temporal.state_dict()
    if a.keys()!=b.keys(): raise ValueError('Unapproved tensor names')
    different={n for n in a if a[n].shape!=b[n].shape}
    if different!=MISMATCHED: raise ValueError('Unapproved shape differences')
    native={n:state_digest(b[n]) for n in different}
    with torch.no_grad():
        for n in a:
            if n not in different: b[n].copy_(a[n])
    proof={n:state_digest(a[n]) for n in a if n not in different}
    if not all(torch.equal(a[n],b[n]) for n in proof): raise AssertionError('Shared tensor identity failed')
    if native!={n:state_digest(b[n]) for n in different}: raise AssertionError('Native input kernels changed')
    manifest={'seed':2026,'independent_reseed_before_each_model':True,'same_shape_tensor_count':len(proof),
              'all_shared_tensors_bit_identical':True,'shared_tensor_sha256':proof,
              'different_tensors':sorted(different),'native_b1_input_kernel_sha256':native,
              'native_zero_skip_preserved':bool((b['backbone.enc0.skip.weight']==0).all()),
              'B0_MATCHED_INITIAL_MODEL_SHA256':state_digest(a),'B1_INITIAL_MODEL_SHA256':state_digest(b),
              'historical_checkpoint_loaded':False,'optimizer_state_transferred':False}
    return anchor,temporal,manifest
