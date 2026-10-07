"""The frozen Conv-GN-GELU residual block."""
import torch
from torch import nn


class ResidualBlock(nn.Module):
    def __init__(self, input_channels: int, output_channels: int, groups: int):
        super().__init__()
        if output_channels % groups:
            raise ValueError("GroupNorm groups must divide channels")
        self.conv1 = nn.Conv2d(input_channels, output_channels, 3, padding=1)
        self.norm1 = nn.GroupNorm(groups, output_channels)
        self.act1 = nn.GELU()
        self.conv2 = nn.Conv2d(output_channels, output_channels, 3, padding=1)
        self.norm2 = nn.GroupNorm(groups, output_channels)
        self.act2 = nn.GELU()
        self.skip = nn.Identity() if input_channels == output_channels else nn.Conv2d(input_channels, output_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act2(self.norm2(self.conv2(self.act1(self.norm1(self.conv1(x))))) + self.skip(x))
