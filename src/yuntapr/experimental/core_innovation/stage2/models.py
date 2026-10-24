"""B3/B4 construction candidates; inherited backbone widths, SP04 and V2 heads.

Only input stem and explicit target-grid MEE residual adapter are added. No
optimizer, checkpoint loading, new probability definition or training defaults.
"""
import torch
from torch import nn
from yuntapr.contracts.loader import REPO_ROOT, load_contract
from yuntapr.models.backbone_b0 import B0Backbone
from yuntapr.models.blocks import ResidualBlock
from yuntapr.models.quantile_v2.heads import ProbabilityHeadsV2
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.spatial.projection import SP04Projection
from ..grid import frozen_sp04_grid
from . import CHANNELS, MEE_KEYS


class NativeBackboneCandidate(B0Backbone):
    def __init__(self, cfg, channels, *, input_channels):
        super().__init__(cfg, channels)
        self.input_channels = input_channels
        self.enc0 = ResidualBlock(input_channels, 48, cfg['groupnorm_groups'])
        nn.init.zeros_(self.enc0.skip.weight); nn.init.zeros_(self.enc0.skip.bias)

    def forward(self, x):
        if x.shape[1:] != (self.input_channels, 501, 501):
            raise ValueError('Native candidate input shape differs')
        s0 = self.enc0(x); s1 = self.enc1(self.down1(s0))
        s2 = self.enc2(self.down2(s1)); s3 = self.enc3(self.down3(s2))
        return self.dec0(self._up(self.dec1(self._up(self.dec2(self._up(s3, s2)), s1)), s0))


class MEECandidate(nn.Module):
    """11 specified normalized variables + 11 separate validity channels.

    T/RH 850/700 hPa and width are explicit candidates, not scientific freeze.
    Raw physical values require separate 2023 Train scalers before formal use.
    Missing pressure layers are neutral with masks, never replaced by other levels.
    """
    def __init__(self, *, width):
        super().__init__()
        if type(width) is not int or width <= 0:
            raise ValueError('Explicit positive MEE candidate width required')
        self.encoder = nn.Sequential(nn.Conv2d(22, width, 3, padding=1), nn.GELU(),
                                     nn.Conv2d(width, width, 3, padding=1), nn.GELU())
        self.output = nn.Conv2d(width, 48, 1)
        nn.init.zeros_(self.output.weight); nn.init.zeros_(self.output.bias)

    def forward(self, values, valid, *, keys):
        if tuple(keys) != MEE_KEYS or values.ndim != 4 or values.shape[1] != 11 or valid.shape != values.shape or valid.dtype != torch.bool:
            raise ValueError('Exact MEE order and independent per-channel masks required')
        if values.device != valid.device or not bool((torch.isfinite(values) | ~valid).all()):
            raise ValueError('MEE nonfinite valid value or device mismatch')
        if values.dtype != self.output.weight.dtype or values.device != self.output.weight.device:
            raise ValueError('MEE dtype/device mismatch')
        safe = torch.where(valid, values, 0.)
        # Column/surface fields and one complete above-ground thermodynamic/wind
        # level required. The missing second level remains explicitly masked.
        low = valid[:, [2, 4, 6, 7]].all(1, keepdim=True)
        high = valid[:, [3, 5, 8, 9]].all(1, keepdim=True)
        usable = valid[:, [0, 1, 10]].all(1, keepdim=True) & (low | high)
        features = self.output(self.encoder(torch.cat((safe, valid.to(values.dtype)), 1)))
        return torch.where(usable, features, 0.), usable


class SpectralCandidate(nn.Module):
    """B2=7x1, B3=7x6, B4=B3+MEE; pilot=B1+MEE (not B4)."""
    def __init__(self, kind, *, numerics, mee_width=None, root=REPO_ROOT):
        super().__init__()
        sizes = {'B2': 7, 'B3': 42, 'B4': 42, 'B1_GFS_PILOT': 6}
        if kind not in sizes or (kind in ('B4', 'B1_GFS_PILOT')) != (mee_width is not None):
            raise ValueError('Explicit supported candidate and MEE width required')
        science, cfg = load_contract(root)
        self.kind = kind; self.input_channels = sizes[kind]
        self.backbone = NativeBackboneCandidate(cfg['backbone'], tuple(science['backbone']['channels']), input_channels=sizes[kind])
        self.projection = SP04Projection(load_sp04(root), cfg['projection']['feature_reduction_operator'])
        self.grid = frozen_sp04_grid(root)
        self.mee = MEECandidate(width=mee_width) if mee_width is not None else None
        self.heads = ProbabilityHeadsV2(numerics=numerics)

    def forward(self, x, valid, *, channel_order, environment=None, environment_valid=None,
                environment_grid=None, environment_keys=None):
        expected = ('B13',) if self.kind == 'B1_GFS_PILOT' else CHANNELS
        if tuple(channel_order) != expected or x.ndim != 4 or x.shape[1:] != (self.input_channels, 501, 501):
            raise ValueError('Exact time-major spectral input required')
        if valid.shape != x.shape or valid.dtype != torch.bool or valid.device != x.device or not bool(valid.all()) or not bool(torch.isfinite(x).all()):
            raise ValueError('Strict joint full-valid population required')
        target = self.projection(self.backbone(x))
        used = None
        if self.mee is not None:
            self.grid.assert_same(environment_grid)
            if environment is None or environment.shape[0] != x.shape[0] or environment.shape[-2:] != (100, 100):
                raise ValueError('MEE must already be mapped to frozen target grid')
            addition, used = self.mee(environment, environment_valid, keys=environment_keys)
            target = target + addition
        elif any(a is not None for a in (environment, environment_valid, environment_grid, environment_keys)):
            raise ValueError('B3/B2 cannot silently consume GFS')
        out = self.heads(target)
        out.target_feature_shape = tuple(target.shape)
        out.target_support_fraction = self.projection.support_fraction(valid.all(1, keepdim=True))
        out.environment_used = used
        return out


def paired_spectral_candidates(*, numerics, mee_width, root=REPO_ROOT):
    """Fresh B3/B4 common weights bit-identical; no historical checkpoint reuse.

    Caller controls the candidate RNG. MEE's zero output makes initial B4 target
    features equal B3; no claim about effectiveness follows from that identity.
    """
    b3 = SpectralCandidate('B3', numerics=numerics, root=root)
    b4 = SpectralCandidate('B4', numerics=numerics, mee_width=mee_width, root=root)
    b4.backbone.load_state_dict(b3.backbone.state_dict()); b4.heads.load_state_dict(b3.heads.state_dict())
    for part in ('backbone', 'heads'):
        a = getattr(b3, part).state_dict(); b = getattr(b4, part).state_dict()
        if not all(torch.equal(a[k], b[k]) for k in a): raise AssertionError('Paired common initialization differs')
    return b3, b4
