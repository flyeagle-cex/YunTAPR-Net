"""ENGINEERING_SMOKE_MODEL: one B13 frame, one precipitation field."""
import torch
from torch import nn

def block(nin,nout):
 return nn.Sequential(nn.Conv2d(nin,nout,3,padding=1),nn.ReLU(),nn.Conv2d(nout,nout,3,padding=1),nn.ReLU())

class B0SmokeUNet(nn.Module):
 def __init__(self,width=8):
  super().__init__();self.width=width
  self.enc1=block(1,width);self.pool=nn.MaxPool2d(2)
  self.enc2=block(width,width*2);self.bridge=block(width*2,width*4)
  self.up2=nn.ConvTranspose2d(width*4,width*2,2,stride=2);self.dec2=block(width*4,width*2)
  self.up1=nn.ConvTranspose2d(width*2,width,2,stride=2);self.dec1=block(width*2,width)
  self.head=nn.Sequential(nn.Conv2d(width,1,1),nn.Softplus())
 def forward(self,x):
  if x.ndim!=4 or x.shape[1]!=1 or x.shape[-1]%4 or x.shape[-2]%4:raise ValueError('Expected [B,1,H,W], H/W divisible by 4')
  if x.dtype!=torch.float32 or not torch.isfinite(x).all():raise ValueError('Finite float32 B13 required; no silent missing fill')
  # Fixed dimensionless conditioning constant, SMOKE_ONLY; no data-fitted statistics.
  a=self.enc1(x/300.0);b=self.enc2(self.pool(a));c=self.bridge(self.pool(b))
  z=self.dec2(torch.cat([self.up2(c),b],dim=1))
  return self.head(self.dec1(torch.cat([self.up1(z),a],dim=1)))
