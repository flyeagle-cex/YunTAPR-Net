"""Masked physical-unit MSE; no rain threshold or target normalization."""
import torch

def masked_mse(prediction,target,target_valid_mask):
 if prediction.shape!=target.shape or target.shape!=target_valid_mask.shape:raise ValueError('Loss shape mismatch')
 if target_valid_mask.dtype!=torch.bool:raise TypeError('Mask must be bool')
 if not target_valid_mask.any():raise ValueError('No valid target pixels')
 p=prediction[target_valid_mask];t=target[target_valid_mask]
 if not torch.isfinite(p).all() or not torch.isfinite(t).all():raise ValueError('Valid pixels must be finite')
 return ((p-t)**2).mean()

def diagnostic_metrics(prediction,target,mask):
 if not mask.any():raise ValueError('No valid diagnostic pixels')
 d=prediction[mask]-target[mask]
 if not torch.isfinite(d).all():raise ValueError('Nonfinite metric inputs')
 return {'scope':'ENGINEERING_DIAGNOSTIC_ONLY','MAE_mm_hr':float(d.abs().mean()),'RMSE_mm_hr':float(d.square().mean().sqrt()),'valid_pixels':int(mask.sum()),'zero_rain_included':int(((target==0)&mask).sum())}
