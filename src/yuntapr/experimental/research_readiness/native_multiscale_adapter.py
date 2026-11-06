"""Isolated native-encoder taps, multi-scale fusion, and existing decoder seam.

The selected encoder tensors are fused *after* all four encoder levels have
been computed and *before* the original decoder consumes its skips/bottleneck.
This is not progressive conditioning of the encoder.  Tap selection, condition
width, physical grids and injection site must all be supplied explicitly.

Only the existing B0Backbone family and unchanged fusion primitives are used.
No SP04 conditions are resized here.  Callers must separately establish a real
condition-to-native-grid mapping; declared matching axes do not prove that
mapping was scientifically correct.  This module does not attach SP04 output
projection, MEE/static residuals, probability heads, losses, or an executor.
"""
import copy
from collections.abc import Sequence
from dataclasses import dataclass

import torch
from torch import Tensor, nn

from yuntapr.models.backbone_b0 import B0Backbone
from ..core_innovation.grid import GridSpec
from .multiscale_candidate import (
    ExplicitMultiscaleFusionCandidate,
    paired_multiscale_candidates,
)


TAP_NAMES = ('enc0', 'enc1', 'enc2', 'enc3')
INJECTION_SITE = 'ENCODER_PYRAMID_BEFORE_DECODER'


def _ordered_taps(tap_names):
    if (not isinstance(tap_names, Sequence)
            or isinstance(tap_names, (str, bytes, bytearray))):
        raise ValueError('Tap names require an explicit ordered Sequence')
    taps = tuple(tap_names)
    if (len(taps) < 2 or any(t not in TAP_NAMES for t in taps)
            or len(set(taps)) != len(taps)
            or taps != tuple(t for t in TAP_NAMES if t in taps)):
        raise ValueError('Select at least two distinct encoder taps in native encoder order')
    return taps


def encoder_tap_grids(backbone, native_grid):
    """Derive convolution-center axes only for the unchanged 3/1/2 geometry.

    For kernel3/padding1/stride2/dilation1, output center i is input center 2i.
    The physical axes are therefore selected from explicit native axes; this
    operation is neither interpolation nor a new geographic data product.
    """
    if not isinstance(backbone, B0Backbone) or not isinstance(native_grid, GridSpec):
        raise TypeError('An existing B0Backbone family instance and explicit native GridSpec are required')
    grids = [native_grid]
    for name in ('down1', 'down2', 'down3'):
        layer = getattr(backbone, name)
        if (not isinstance(layer, nn.Conv2d) or layer.kernel_size != (3, 3)
                or layer.padding != (1, 1) or layer.stride != (2, 2)
                or layer.dilation != (1, 1) or layer.padding_mode != 'zeros'):
            raise ValueError('Native tap coordinates require the unchanged kernel3/padding1/stride2 geometry')
        lat, lon = grids[-1].lat[::2], grids[-1].lon[::2]
        if min(len(lat), len(lon)) < 2:
            raise ValueError('Native grid must retain at least two centers at every encoder level')
        grids.append(GridSpec(lat, lon))
    return tuple(grids)


@dataclass(frozen=True)
class NativeAdapterOutput:
    decoded_native: Tensor
    native_grid: GridSpec
    encoder_feature_shapes: tuple
    fused_taps: tuple[str, ...]
    condition_used: tuple[Tensor, ...]


class NativeMultiscaleAdapter(nn.Module):
    """Existing encoder -> explicit selected fusion -> existing decoder.

    Arbitrary small native grids are accepted for synthetic engineering checks.
    The historical production 501x501 input/default is not changed, and a small
    synthetic forward is not a real-grid or formal-model integration receipt.
    """

    candidate_only = True
    native_encoder_connected = True
    decoder_connected = True
    formal_integration = False
    real_grid_mapping_verified = False
    probability_heads_connected = False
    scientific_effectiveness = 'NOT_VERIFIED'

    def __init__(self, backbone, fusion, *, native_grid, tap_names, injection_site):
        super().__init__()
        if injection_site != INJECTION_SITE:
            raise ValueError('The injection site must explicitly select ENCODER_PYRAMID_BEFORE_DECODER')
        if not isinstance(fusion, ExplicitMultiscaleFusionCandidate):
            raise TypeError('The existing explicit multi-scale fusion wrapper is required')
        self.tap_names = _ordered_taps(tap_names)
        self.tap_grids = encoder_tap_grids(backbone, native_grid)
        if fusion.scale_names != self.tap_names:
            raise ValueError('Fusion scale names must explicitly match selected encoder taps')
        for name, spec in zip(self.tap_names, fusion.scales):
            index = TAP_NAMES.index(name)
            self.tap_grids[index].assert_same(spec.grid)
            if spec.feature_channels != getattr(backbone, name).conv2.out_channels:
                raise ValueError('Fusion feature channels must match the actual encoder module')
        self.backbone = backbone
        self.fusion = fusion
        self.native_grid = native_grid
        self.injection_site = injection_site
        self.kind = fusion.kind

    def forward(self, x, native_valid, *, gfs, terrain, gfs_valid, terrain_valid,
                gfs_grids, terrain_grids):
        weight = self.backbone.enc0.conv1.weight
        if (not isinstance(x, Tensor) or x.ndim != 4 or x.numel() == 0
                or x.shape[1] != self.backbone.enc0.conv1.in_channels
                or tuple(x.shape[-2:]) != self.native_grid.shape
                or not x.is_floating_point() or x.dtype != weight.dtype
                or x.device != weight.device or not bool(torch.isfinite(x).all())):
            raise ValueError('Finite nonempty native features must match the actual input stem and explicit grid')
        if (not isinstance(native_valid, Tensor) or native_valid.dtype != torch.bool
                or native_valid.shape != (x.shape[0], 1, *self.native_grid.shape)
                or native_valid.device != x.device or not bool(native_valid.all())):
            raise ValueError('The inherited fully-valid native context requires a separate all-valid bool mask')

        # Invoke the actual existing encoder modules, not resized copies of
        # the final SP04 feature. No custom encoder or decoder layers are added.
        b = self.backbone
        features = [b.enc0(x)]
        for down, encoder in ((b.down1, b.enc1), (b.down2, b.enc2), (b.down3, b.enc3)):
            features.append(encoder(down(features[-1])))
        for feature, grid in zip(features, self.tap_grids):
            if tuple(feature.shape[-2:]) != grid.shape:
                raise RuntimeError('Actual encoder geometry differs from the explicit tap grid')

        selected = [features[TAP_NAMES.index(name)] for name in self.tap_names]
        grids = [self.tap_grids[TAP_NAMES.index(name)] for name in self.tap_names]
        masks = [torch.ones((x.shape[0], 1, *grid.shape), dtype=torch.bool,
                            device=x.device) for grid in grids]
        fused = self.fusion(
            selected, gfs, terrain, masks, gfs_valid, terrain_valid,
            scale_names=self.tap_names, feature_grids=grids,
            gfs_grids=gfs_grids, terrain_grids=terrain_grids,
        )
        decoder_inputs = list(features)
        for name, value in zip(self.tap_names, fused.values):
            decoder_inputs[TAP_NAMES.index(name)] = value
        s0, s1, s2, s3 = decoder_inputs
        decoded = b.dec0(b._up(b.dec1(b._up(b.dec2(b._up(s3, s2)), s1)), s0))
        if decoded.shape != (x.shape[0], b.enc0.conv2.out_channels, *self.native_grid.shape):
            raise RuntimeError('Existing decoder did not return the native feature shape')
        return NativeAdapterOutput(
            decoded, self.native_grid, tuple(tuple(f.shape) for f in features),
            self.tap_names, fused.condition_used,
        )


def paired_native_multiscale_adapters(backbone, *, native_grid, scales, tap_names,
                                      injection_site, projection_width, modulation_limit):
    """Copy common existing weights; preserve original paired fusion initialization.

    No seed, checkpoint, scientific scale choice or execution budget is selected
    here. The caller owns the fresh backbone and controls its construction RNG.
    Equal parameter numbers are not an equal-effective-capacity guarantee.
    """
    concat, dtfm = paired_multiscale_candidates(
        scales, projection_width=projection_width, modulation_limit=modulation_limit,
    )
    return tuple(
        NativeMultiscaleAdapter(
            copy.deepcopy(backbone), fusion, native_grid=native_grid,
            tap_names=tap_names, injection_site=injection_site,
        )
        for fusion in (concat, dtfm)
    )
