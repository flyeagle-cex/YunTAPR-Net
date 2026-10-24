"""Mask-safe, identity-initialized DTFM interface candidate; no backbone changes.

This latent affine prototype is not a frozen DTFM scientific definition. Every
scale and conditioning channel count and the modulation limit are explicit.
Inputs must already share physical grid coordinates; no resizing is performed.
"""
from dataclasses import dataclass
from collections.abc import Sequence
import math

import torch
from torch import nn

from .grid import GridSpec


@dataclass(frozen=True)
class ModulatedFeatures:
    values: tuple[torch.Tensor, ...]
    valid: tuple[torch.Tensor, ...]
    condition_used: tuple[torch.Tensor, ...]


def _positive_channels(name, channels):
    result = tuple(channels)
    if not result or any(type(c) is not int or c <= 0 for c in result):
        raise ValueError(f'{name}: explicit positive integer channels required')
    return result


class MaskedTerrainModulation(nn.Module):
    """Per-scale candidate: f * (1 + limit*tanh(gamma)) + limit*tanh(beta).

    A 1x1 projection predicts gamma and beta from caller-selected aligned
    terrain/dynamic features. Zero initialization makes the initial action an
    identity. Invalid conditioning leaves valid backbone features unchanged;
    invalid backbone features produce a masked neutral zero. The returned mask
    is always required to interpret those zeros. This does not define a new
    precipitation distribution, output head, scale hierarchy, or training arm.
    """

    def __init__(self, *, feature_channels: Sequence[int],
                 condition_channels: Sequence[int], modulation_limit: float):
        super().__init__()
        self.feature_channels = _positive_channels('feature_channels', feature_channels)
        self.condition_channels = _positive_channels('condition_channels', condition_channels)
        if len(self.feature_channels) != len(self.condition_channels):
            raise ValueError('One explicit conditioning count required for every scale')
        if isinstance(modulation_limit, bool) or not math.isfinite(modulation_limit) or not 0 < modulation_limit <= 1:
            raise ValueError('Explicit finite modulation_limit in (0,1] required')
        self.modulation_limit = float(modulation_limit)
        self.projections = nn.ModuleList([
            nn.Conv2d(condition, feature * 2, 1)
            for feature, condition in zip(self.feature_channels, self.condition_channels)
        ])
        for layer in self.projections:
            nn.init.zeros_(layer.weight)
            nn.init.zeros_(layer.bias)

    def forward(self, features: Sequence[torch.Tensor], conditions: Sequence[torch.Tensor],
                feature_valid: Sequence[torch.Tensor], condition_valid: Sequence[torch.Tensor], *,
                feature_grids: Sequence[GridSpec], condition_grids: Sequence[GridSpec]) -> ModulatedFeatures:
        all_inputs = (features, conditions, feature_valid, condition_valid, feature_grids, condition_grids)
        if any(len(items) != len(self.projections) for items in all_inputs):
            raise ValueError('Explicit aligned entries required for every configured scale')
        outputs, masks, used_masks = [], [], []
        for index, layer in enumerate(self.projections):
            feature, condition = features[index], conditions[index]
            fmask, cmask = feature_valid[index], condition_valid[index]
            fg, cg = feature_grids[index], condition_grids[index]
            if not isinstance(fg, GridSpec) or not isinstance(cg, GridSpec):
                raise TypeError('Both feature and conditioning physical grids required')
            fg.assert_same(cg)
            for name, value, channels in (('feature', feature, self.feature_channels[index]),
                                          ('condition', condition, self.condition_channels[index])):
                if not isinstance(value, torch.Tensor) or value.ndim != 4 or not value.is_floating_point():
                    raise ValueError(f'{name}: floating [B,C,H,W] tensor required')
                if value.shape[0] <= 0 or value.shape[1] != channels or tuple(value.shape[-2:]) != fg.shape:
                    raise ValueError(f'{name}: configured channels/spatial grid mismatch')
                if value.device != layer.weight.device or value.dtype != layer.weight.dtype:
                    raise ValueError(f'{name}: module, input device and dtype must agree explicitly')
            if feature.shape[0] != condition.shape[0]:
                raise ValueError('Feature and conditioning batch sizes must agree')
            expected = (feature.shape[0], 1, *fg.shape)
            for name, value, mask in (('feature', feature, fmask), ('condition', condition, cmask)):
                if not isinstance(mask, torch.Tensor) or mask.dtype != torch.bool or tuple(mask.shape) != expected:
                    raise ValueError(f'{name}: independent bool [B,1,H,W] validity mask required')
                if mask.device != value.device:
                    raise ValueError(f'{name}: validity mask device mismatch')
                if not bool(torch.isfinite(value).logical_or(~mask).all()):
                    raise ValueError(f'{name}: nonfinite value marked valid')
            safe_feature = torch.where(fmask, feature, 0.)
            safe_condition = torch.where(cmask, condition, 0.)
            gamma, beta = layer(safe_condition).chunk(2, dim=1)
            used = fmask & cmask
            gamma = torch.where(used, torch.tanh(gamma) * self.modulation_limit, 0.)
            beta = torch.where(used, torch.tanh(beta) * self.modulation_limit, 0.)
            output = safe_feature * (1 + gamma) + beta
            output = torch.where(fmask, output, 0.)
            if not bool(torch.isfinite(output).all()):
                raise FloatingPointError('DTFM candidate produced nonfinite features')
            outputs.append(output)
            masks.append(fmask.clone())
            used_masks.append(used)
        return ModulatedFeatures(tuple(outputs), tuple(masks), tuple(used_masks))
