"""Frozen FP64 global core-loss arithmetic without physical materialization."""
import math
import torch
import torch.nn.functional as F
from yuntapr.models.quantile_v2.outputs import validate_log_quantiles


class LogDomainValidation:
    def __init__(self):
        self.s_occ = self.s_qr = 0.0
        self.n_valid = self.n_rain = self.scenes = self.forwards = 0

    @torch.no_grad()
    def add(self, output, target, valid, mask):
        validate_log_quantiles(output.conditional_quantiles_log)
        selected = valid & mask
        if int(selected.sum()) != target.shape[0] * 3430:
            raise ValueError('Frozen validation denominator mismatch')
        with torch.autocast(target.device.type, enabled=False):
            rate = target[selected].double()
            logit = output.rain_logit[selected].double()
            prob = output.rain_prob[selected].double()
            q = output.conditional_quantiles_log.movedim(1, -1)[selected.squeeze(1)]
            if not all(bool(torch.isfinite(v).all()) for v in (rate, logit, prob)) or bool((rate < 0).any()) or bool(((prob < 0) | (prob > 1)).any()):
                raise FloatingPointError('Invalid validation values')
            rainy = target[selected] > .1  # preserve original float32 event boundary
            bce = F.binary_cross_entropy_with_logits(logit, rainy.double(), reduction='none')
            self.s_occ += float((.5 * (1 - torch.exp(-bce)).pow(2) * bce).sum(dtype=torch.float64))
            tau = (torch.arange(1, 33, device=q.device, dtype=torch.float64) - .5) / 32
            error = torch.log1p(rate[rainy])[:, None] - q[rainy]
            pinball = torch.maximum(tau * error, (tau - 1) * error)
            self.s_qr += float(pinball.mean(-1).sum(dtype=torch.float64))
        self.n_valid += len(rate); self.n_rain += int(rainy.sum())
        self.scenes += target.shape[0]; self.forwards += 1

    def report(self):
        if not self.n_valid or not math.isfinite(self.s_occ + self.s_qr):
            raise FloatingPointError('Invalid global validation accumulation')
        return {'S_occ': self.s_occ, 'S_qr': self.s_qr, 'N_valid': self.n_valid,
                'N_rain': self.n_rain, 'scenes': self.scenes, 'forwards': self.forwards,
                'global_val_core_loss': (self.s_occ + self.s_qr) / self.n_valid,
                'global_L_occ': self.s_occ / self.n_valid, 'global_core_L_qr': self.s_qr / self.n_valid,
                'numerator_dtype': 'float64', 'physical_materialization': False,
                'strict_crossing_count': 0, 'support_violation_count': 0, 'nonfinite_count': 0}
