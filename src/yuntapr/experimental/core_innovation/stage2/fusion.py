"""B7 concat / B8 DTFM candidates with exactly equal active parameter counts."""
import torch
from torch import nn
from ..dtfm import MaskedTerrainModulation, ModulatedFeatures


class FusionCandidate(nn.Module):
    """Identical per-scale GFS/terrain inputs and projections for both controls.

    B7: residual + Conv3x3(Conv1x1(concat(f,g,t))).
    B8: residual + Conv3x3(Linear1x1(DTFM(f,concat(g,t)))).
    With latent width 2C, B7 concat has 2C*(C+2r+1) parameters;
    B8 affine has 2C*(2r+1), feature linear has 2C*C (no bias).
    All parameters have active forward paths; no dummy parameter padding.
    Fusion output starts at zero, preserving the inherited identity behaviour.
    """
    def __init__(self, *, kind, feature_channels, gfs_channels, terrain_channels,
                 projection_width, modulation_limit):
        super().__init__()
        if kind not in ('B7', 'B8') or len(set(map(len, (feature_channels, gfs_channels, terrain_channels)))) != 1:
            raise ValueError('Explicit B7/B8 and aligned scale counts required')
        if type(projection_width) is not int or projection_width <= 0:
            raise ValueError('Positive candidate condition projection width required')
        if not feature_channels or any(type(c) is not int or c <= 0 for seq in (feature_channels, gfs_channels, terrain_channels) for c in seq):
            raise ValueError('Positive channel counts required')
        self.kind = kind; self.feature_channels = tuple(feature_channels)
        self.gfs = nn.ModuleList(nn.Conv2d(c, projection_width, 1) for c in gfs_channels)
        self.terrain = nn.ModuleList(nn.Conv2d(c, projection_width, 1) for c in terrain_channels)
        self.modulation = MaskedTerrainModulation(feature_channels=feature_channels,
            condition_channels=[2*projection_width]*len(feature_channels), modulation_limit=modulation_limit) if kind == 'B8' else None
        self.mix = nn.ModuleList(nn.Conv2d(c if kind == 'B8' else c+2*projection_width, 2*c, 1,
                                         bias=kind == 'B7') for c in feature_channels)
        self.fuse = nn.ModuleList(nn.Conv2d(2*c, c, 3, padding=1) for c in feature_channels)
        for layer in self.fuse:
            nn.init.zeros_(layer.weight); nn.init.zeros_(layer.bias)

    def forward(self, features, gfs, terrain, feature_valid, gfs_valid, terrain_valid, *,
                feature_grids, gfs_grids, terrain_grids):
        if not features or len(features) != len(self.mix):
            raise ValueError('Explicit feature scale count required')
        # A BF16 backbone and FP32 physical conditions are the ordinary AMP
        # boundary. Keep affine/fusion arithmetic in parameter precision and
        # return each feature's original dtype. The inherited strict DTFM API
        # itself is unchanged. FP64 is never silently downcast.
        device_type = features[0].device.type
        amp = torch.is_autocast_enabled(device_type)
        dtype = self.gfs[0].weight.dtype
        for seq in (features, gfs, terrain):
            for value in seq:
                if value.dtype != dtype and not (amp and dtype == torch.float32 and value.dtype in (torch.bfloat16, torch.float16)):
                    raise ValueError('Explicit matching dtype or active AMP boundary required')
        with torch.autocast(device_type, enabled=False):
            out = self._forward([x.to(dtype=dtype) for x in features], [x.to(dtype=dtype) for x in gfs],
                [x.to(dtype=dtype) for x in terrain], feature_valid, gfs_valid, terrain_valid,
                feature_grids=feature_grids, gfs_grids=gfs_grids, terrain_grids=terrain_grids)
        return ModulatedFeatures(tuple(x.to(dtype=f.dtype) for x, f in zip(out.values, features)), out.valid, out.condition_used)

    def _forward(self, features, gfs, terrain, feature_valid, gfs_valid, terrain_valid, *,
                 feature_grids, gfs_grids, terrain_grids):
        collections = (features, gfs, terrain, feature_valid, gfs_valid, terrain_valid, feature_grids, gfs_grids, terrain_grids)
        if any(len(seq) != len(self.mix) for seq in collections):
            raise ValueError('One entry per explicit scale required')
        conditions, cmasks, safe_features = [], [], []
        for i, (gp, tp) in enumerate(zip(self.gfs, self.terrain)):
            grid = feature_grids[i]; grid.assert_same(gfs_grids[i]); grid.assert_same(terrain_grids[i])
            f = features[i]
            for x, mask, channels in ((f, feature_valid[i], self.feature_channels[i]),
                                     (gfs[i], gfs_valid[i], gp.in_channels),
                                     (terrain[i], terrain_valid[i], tp.in_channels)):
                if (x.ndim != 4 or x.shape != (f.shape[0], channels, *grid.shape)
                    or x.device != gp.weight.device or x.dtype != gp.weight.dtype
                    or mask.dtype != torch.bool or mask.shape != (f.shape[0], 1, *grid.shape) or mask.device != x.device
                    or not bool((torch.isfinite(x) | ~mask).all())):
                    raise ValueError('Aligned finite masked conditioning required')
            gm, tm = gfs_valid[i], terrain_valid[i]
            conditions.append(torch.cat((torch.where(gm, gp(torch.where(gm, gfs[i], 0.)), 0.),
                                         torch.where(tm, tp(torch.where(tm, terrain[i], 0.)), 0.)), 1))
            cmasks.append(gm & tm); safe_features.append(torch.where(feature_valid[i], f, 0.))
        mod = self.modulation(safe_features, conditions, feature_valid, cmasks,
            feature_grids=feature_grids, condition_grids=feature_grids).values if self.modulation else safe_features
        outputs, used = [], []
        for i, (mix, fuse) in enumerate(zip(self.mix, self.fuse)):
            payload = mod[i] if self.modulation else torch.cat((safe_features[i], conditions[i]), 1)
            latent = mix(payload)
            # Invalid support cannot enter the neighbourhood convolution.
            use = feature_valid[i] & cmasks[i]
            residual = fuse(torch.where(use, latent, 0.))
            output = safe_features[i] + torch.where(use, residual, 0.)
            output = torch.where(feature_valid[i], output, 0.)
            if not bool(torch.isfinite(output).all()):
                raise FloatingPointError('Nonfinite fusion candidate')
            outputs.append(output); used.append(use)
        return ModulatedFeatures(tuple(outputs), tuple(feature_valid), tuple(used))


def paired_fusion_candidates(**kwargs):
    """Share initial GFS/terrain projections; all distinct functional layers native.

    Caller controls the experimental RNG. Both arms must consume the same
    DynamicTerrainCandidate.stack() payload and the same grid/mask hierarchy.
    """
    b7 = FusionCandidate(kind='B7', **kwargs); b8 = FusionCandidate(kind='B8', **kwargs)
    b8.gfs.load_state_dict(b7.gfs.state_dict()); b8.terrain.load_state_dict(b7.terrain.state_dict())
    if sum(p.numel() for p in b7.parameters()) != sum(p.numel() for p in b8.parameters()):
        raise AssertionError('B7/B8 active parameter mismatch')
    return b7, b8
