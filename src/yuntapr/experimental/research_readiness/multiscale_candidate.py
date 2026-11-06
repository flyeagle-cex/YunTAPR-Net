"""Explicit multi-scale fusion interface, not a formal YunTAPR model.

The caller supplies features and physical conditions already aligned on every
declared grid.  This module never resizes data, derives coordinates, reads a
mapping, taps the native encoder, connects a decoder, or launches an experiment.
Two distinct tensor sizes are required; repeating SP04 does not create a scale
hierarchy.  Even valid caller metadata is not independent proof of real-data
alignment or of a native-encoder hierarchy.

The existing concat/DTFM primitives and their initialization are reused without
change.  Equal parameter counts do not establish equal effective capacity or
equal optimization dynamics.  In particular, zero residual outputs initially
block upstream gradients, and the DTFM affine layers also start at zero.
"""
from dataclasses import dataclass
from collections.abc import Sequence

from torch import Tensor, nn

from ..core_innovation.grid import GridSpec
from ..core_innovation.stage2.fusion import (
    FusionCandidate,
    paired_fusion_candidates,
)


@dataclass(frozen=True)
class ExplicitScaleSpec:
    """Caller-declared feature/condition layout with an explicit physical grid.

    ``feature_source`` is provenance text, not a verification certificate.  No
    native-encoder or external-map identity is inferred from a scale name.
    """

    name: str
    feature_channels: int
    gfs_channels: int
    terrain_channels: int
    grid: GridSpec
    feature_source: str

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError('An explicit nonempty scale name is required')
        if not isinstance(self.feature_source, str) or not self.feature_source.strip():
            raise ValueError('Explicit feature provenance is required')
        if not isinstance(self.grid, GridSpec):
            raise TypeError('An explicit physical GridSpec is required')
        if any(type(value) is not int or value <= 0 for value in (
            self.feature_channels, self.gfs_channels, self.terrain_channels
        )):
            raise ValueError('Explicit positive channel counts are required')


def _checked_scales(scales):
    if not isinstance(scales, Sequence) or isinstance(scales, (str, bytes, bytearray)):
        raise ValueError('Scale specifications require an ordered Sequence, not an arbitrary iterable')
    result = tuple(scales)
    if len(result) < 2 or any(not isinstance(s, ExplicitScaleSpec) for s in result):
        raise ValueError('At least two explicit scale specifications are required')
    if len({s.name for s in result}) != len(result):
        raise ValueError('Scale names must be unique and ordered explicitly')
    if len({s.grid.identity for s in result}) != len(result):
        raise ValueError('Repeated physical grids cannot stand in for multiple scales')
    if len({s.grid.shape for s in result}) < 2:
        raise ValueError('At least two distinct spatial tensor sizes are required')
    return result


class ExplicitMultiscaleFusionCandidate(nn.Module):
    """Checked wrapper around the existing per-scale fusion primitive.

    A differing feature/condition grid is rejected.  There is deliberately no
    interpolation fallback: its physical operator and validity propagation
    would require a separate, reviewed integration.
    """

    candidate_only = True
    formal_integration = False
    native_encoder_connected = False
    decoder_connected = False
    real_grid_mapping_verified = False
    scientific_effectiveness = 'NOT_VERIFIED'

    def __init__(self, scales: Sequence[ExplicitScaleSpec], fusion: FusionCandidate):
        super().__init__()
        self.scales = _checked_scales(scales)
        if not isinstance(fusion, FusionCandidate):
            raise TypeError('The existing FusionCandidate primitive is required')
        if (
            tuple(fusion.feature_channels) != tuple(s.feature_channels for s in self.scales)
            or tuple(p.in_channels for p in fusion.gfs) != tuple(s.gfs_channels for s in self.scales)
            or tuple(p.in_channels for p in fusion.terrain) != tuple(s.terrain_channels for s in self.scales)
        ):
            raise ValueError('Fusion channels must match all explicit scale specifications')
        self.fusion = fusion
        self.kind = fusion.kind

    @property
    def scale_names(self):
        return tuple(s.name for s in self.scales)

    def forward(self, features, gfs, terrain, feature_valid, gfs_valid, terrain_valid,
                *, scale_names, feature_grids, gfs_grids, terrain_grids):
        if tuple(scale_names) != self.scale_names:
            raise ValueError('Scale order must match the explicit specification')
        collections = (features, gfs, terrain, feature_valid, gfs_valid,
                       terrain_valid, feature_grids, gfs_grids, terrain_grids)
        if any(len(items) != len(self.scales) for items in collections):
            raise ValueError('One aligned entry is required for every explicit scale')
        batch_size = None
        for feature in features:
            if (not isinstance(feature, Tensor) or feature.ndim != 4
                    or feature.numel() == 0 or feature.shape[0] <= 0):
                raise ValueError('Every feature must be a nonempty 4D Tensor with a positive batch size')
            if batch_size is None:
                batch_size = feature.shape[0]
            elif feature.shape[0] != batch_size:
                raise ValueError('Feature batch size must agree across all explicit scales')
        for index, spec in enumerate(self.scales):
            for grid in (feature_grids[index], gfs_grids[index], terrain_grids[index]):
                spec.grid.assert_same(grid)
        # The reused primitive validates tensors, independent bool masks,
        # nonfinite marked-valid values, channel counts and device/dtype.
        return self.fusion(
            features, gfs, terrain, feature_valid, gfs_valid, terrain_valid,
            feature_grids=feature_grids, gfs_grids=gfs_grids,
            terrain_grids=terrain_grids,
        )


def paired_multiscale_candidates(scales: Sequence[ExplicitScaleSpec], *,
                                projection_width: int, modulation_limit: float):
    """Reuse the original paired factory; the caller controls experimental RNG.

    No layer initialization is changed.  Shared condition projections are copied
    by the existing factory, not aliased between arms.  Residual output layers
    retain their existing zero initialization.  This factory has no training,
    optimizer, checkpoint, data loading or execution authorization interface.
    """
    checked = _checked_scales(scales)
    concat, dtfm = paired_fusion_candidates(
        feature_channels=[s.feature_channels for s in checked],
        gfs_channels=[s.gfs_channels for s in checked],
        terrain_channels=[s.terrain_channels for s in checked],
        projection_width=projection_width,
        modulation_limit=modulation_limit,
    )
    return (
        ExplicitMultiscaleFusionCandidate(checked, concat),
        ExplicitMultiscaleFusionCandidate(checked, dtfm),
    )
