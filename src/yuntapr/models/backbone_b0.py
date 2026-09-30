"""Four-level single-frame residual U-Net without temporal or auxiliary inputs."""
import torch
from torch import nn
from torch.nn import functional as F
from yuntapr.models.blocks import ResidualBlock


class B0Backbone(nn.Module):
    def __init__(self, cfg: dict, channels: tuple[int, ...]):
        super().__init__()
        if tuple(channels) != (48, 96, 192, 256):
            raise ValueError("B0 channels differ from frozen scientific contract")
        groups = cfg["groupnorm_groups"]
        kernel = cfg["downsample_kernel"]
        padding = cfg["downsample_padding"]
        self.mode = cfg["decoder_interpolation_mode"]
        self.align_corners = cfg["align_corners"]
        self.enc0 = ResidualBlock(1, 48, groups)
        if cfg["input_projection_skip_initialization"] != "zeros" or not isinstance(self.enc0.skip, nn.Conv2d):
            raise ValueError("B0 input projection skip requires explicit zero initialization")
        nn.init.zeros_(self.enc0.skip.weight)
        nn.init.zeros_(self.enc0.skip.bias)
        self.down1 = nn.Conv2d(48, 96, kernel, stride=2, padding=padding)
        self.enc1 = ResidualBlock(96, 96, groups)
        self.down2 = nn.Conv2d(96, 192, kernel, stride=2, padding=padding)
        self.enc2 = ResidualBlock(192, 192, groups)
        self.down3 = nn.Conv2d(192, 256, kernel, stride=2, padding=padding)
        self.enc3 = ResidualBlock(256, 256, groups)
        self.dec2 = ResidualBlock(256 + 192, 192, groups)
        self.dec1 = ResidualBlock(192 + 96, 96, groups)
        self.dec0 = ResidualBlock(96 + 48, 48, groups)

    def _up(self, source: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        if self.mode == "nearest":
            up = F.interpolate(source, size=skip.shape[-2:], mode=self.mode)
        else:
            up = F.interpolate(source, size=skip.shape[-2:], mode=self.mode, align_corners=self.align_corners)
        return torch.cat((up, skip), dim=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 4 or x.shape[1:] != (1, 501, 501):
            raise ValueError("B0 input must be [B,1,501,501]")
        s0 = self.enc0(x)
        s1 = self.enc1(self.down1(s0))
        s2 = self.enc2(self.down2(s1))
        s3 = self.enc3(self.down3(s2))
        out = self.dec0(self._up(self.dec1(self._up(self.dec2(self._up(s3, s2)), s1)), s0))
        if out.shape[1:] != (48, 501, 501):
            raise RuntimeError("Decoder failed native shape contract")
        return out
