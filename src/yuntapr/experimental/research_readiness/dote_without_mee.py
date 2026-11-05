"""B3 + physical DOTE only: no direct GFS/MEE or static-terrain input branch.

GFS wind/PWAT/pressure still drive the unchanged PhysicalDote transform. This
ablation must never be described as independent of all GFS information.
"""
import copy
import torch
from torch import nn
from ..core_innovation.stage2 import CHANNELS

KIND='B3_DOTE_ONLY'


class DoteResidual(nn.Module):
    """Eight physical channels + their masks, width16, zero-output residual."""
    def __init__(self,width=16):
        super().__init__()
        if width!=16:raise ValueError('The single prepared experiment uses width16')
        self.input=nn.Conv2d(16,width,3,padding=1)
        self.activation=nn.GELU()
        self.output=nn.Conv2d(width,48,1)
        nn.init.zeros_(self.output.weight);nn.init.zeros_(self.output.bias)

    def forward(self,values,valid,region,*,output_dtype):
        if values.ndim!=4 or values.shape[1:]!=(8,100,100) or valid.shape!=values.shape or valid.dtype!=torch.bool:
            raise ValueError('Eight aligned DOTE channels with per-channel bool masks required')
        if region.shape!=(1,1,100,100) or region.dtype!=torch.bool or region.device!=values.device:
            raise ValueError('Frozen independent supervision region required')
        if valid.device!=values.device or not bool(torch.isfinite(values[valid]).all()):raise ValueError('Finite valid DOTE values required')
        use=valid.any(1,keepdim=True)&region
        with torch.autocast(values.device.type,enabled=False):
            safe=torch.where(valid&region,values,0.).float()
            payload=torch.cat((safe,(valid&region).float()),1)
            features=self.activation(self.input(payload))
            addition=self.output(features)
            addition=torch.where(use,addition,0.)
        if not bool(torch.isfinite(addition).all()):raise FloatingPointError('Nonfinite DOTE residual')
        return addition.to(output_dtype),use


class DoteWithoutMee(nn.Module):
    def __init__(self,base_b3,region):
        super().__init__()
        if base_b3.kind!='B3' or base_b3.mee is not None:raise ValueError('Only the no-MEE B3 backbone is allowed')
        self.base=base_b3;self.dynamic_residual=DoteResidual();self.kind=KIND
        mask=torch.as_tensor(region,dtype=torch.bool).clone()
        if mask.shape!=(100,100) or int(mask.sum())!=3430:raise ValueError('The unchanged3430-point mask is required')
        self.register_buffer('region',mask[None,None],persistent=False)
    @property
    def backbone(self):return self.base.backbone
    @property
    def heads(self):return self.base.heads
    @property
    def grid(self):return self.base.grid

    def forward(self,x,valid,*,channel_order,dynamic,dynamic_valid,dynamic_grid):
        # There is intentionally no environment/environment_valid argument.
        self.grid.assert_same(dynamic_grid)
        if tuple(channel_order)!=CHANNELS or x.ndim!=4 or x.shape[1:]!=(42,501,501):raise ValueError('Frozen time-major 7x6 satellite input required')
        if valid.shape!=x.shape or valid.dtype!=torch.bool or not bool(valid.all()) or not bool(torch.isfinite(x).all()):raise ValueError('Strict original native-valid population')
        if len(dynamic)!=len(x):raise ValueError('DOTE and satellite batch identities must match')
        target=self.base.projection(self.backbone(x))
        addition,used=self.dynamic_residual(dynamic,dynamic_valid,self.region,output_dtype=target.dtype)
        out=self.heads(target+addition)
        out.target_feature_shape=tuple(target.shape)
        out.target_support_fraction=self.base.projection.support_fraction(valid.all(1,keepdim=True))
        out.dynamic_used=used
        return out


def create(seed,root,region):
    from ..core_innovation.stage4.engine import paired_models
    models=paired_models(seed,root)
    base=models['B3']
    # Preserve exactly the historical B3 initial state and post-construction RNG.
    # Only the auxiliary branch draws from a separate, predeclared RNG stream.
    with torch.random.fork_rng(devices=[]):
        torch.set_rng_state(torch.Generator(device='cpu').manual_seed(seed+40000).get_state())
        candidate=DoteWithoutMee(copy.deepcopy(base),region)
    return base,candidate
