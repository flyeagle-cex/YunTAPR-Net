"""Supplemental read-only Phase-A metrics; no physical quantile materialization.

Uses the pinned v2 core accumulator unchanged, and the existing exact equal-score
ranking conventions. Conditional pinball is the existing log1p-mm/h conditional
mean: S_qr / N_rain. These values cannot select checkpoints or alter training.
"""
from contextlib import contextmanager
from pathlib import Path
import sys
from unittest.mock import patch
import numpy as np
import torch

EXECUTION = Path(__file__).resolve().parents[3] / 'YunTAPR-Net-v2-phase-a-execution'
sys.path[:0] = [str(EXECUTION / 'src'), str(EXECUTION / 'scripts')]
from yuntapr.training.phase_a_validation_v2 import LogDomainValidation
from yuntapr.training.phase_a_validation import grouped_occurrence_metrics


class ReadOnlyMetrics(LogDomainValidation):
    def __init__(self):
        super().__init__()
        self.brier_sum = 0.0
        self.tau_pinball_sum = np.zeros(32, dtype=np.float64)
        self.scores, self.labels = [], []

    @torch.no_grad()
    def add(self, output, target, valid, mask):
        super().add(output, target, valid, mask)
        selected = valid & mask
        with torch.autocast(target.device.type, enabled=False):
            # Label before promotion, preserving the frozen float32 0.1 boundary.
            rainy = target[selected] > .1
            probability = output.rain_prob[selected].double()
            rate = target[selected].double()
            quantiles = output.conditional_quantiles_log.movedim(1, -1)[selected.squeeze(1)]
            tau = (torch.arange(1, 33, device=quantiles.device, dtype=torch.float64) - .5) / 32
            error = torch.log1p(rate[rainy])[:, None] - quantiles[rainy]
            pinball = torch.maximum(tau * error, (tau - 1) * error)
            self.tau_pinball_sum += pinball.sum(0, dtype=torch.float64).cpu().numpy()
            self.brier_sum += float((probability - rainy.double()).square().sum(dtype=torch.float64))
            self.scores.append(probability.cpu().numpy())
            self.labels.append(rainy.cpu().numpy())

    def report(self):
        core = super().report()
        return {**core, 'Brier_Score': self.brier_sum / self.n_valid,
                **grouped_occurrence_metrics(np.concatenate(self.scores), np.concatenate(self.labels)),
                'conditional_mean_pinball': self.s_qr / self.n_rain if self.n_rain else None,
                'conditional_pinball_units': 'log1p(mm/h)',
                'conditional_pinball_denominator': 'N_rain; tau mean over 32 frozen conditional quantiles',
                'per_tau_pinball': (self.tau_pinball_sum / self.n_rain).tolist() if self.n_rain else [None] * 32,
                'POD': 'THRESHOLD_NOT_FROZEN', 'FAR': 'THRESHOLD_NOT_FROZEN', 'CSI': 'THRESHOLD_NOT_FROZEN',
                'physical_materialization': False, 'checkpoint_selection_performed': False}


@contextmanager
def inference_only():
    def forbidden(*args, **kwargs):
        raise PermissionError('READ_ONLY_PHASE_A_REVIEW_FORBIDS_OPTIMIZER_AND_BACKWARD')
    with patch.object(torch.optim.Optimizer, '__init__', forbidden), \
         patch.object(torch.Tensor, 'backward', forbidden), \
         patch.object(torch.autograd, 'backward', forbidden):
        with torch.inference_mode():
            yield


def require_completed_pair(public):
    """Reject partial runs before loading torch models, sources or checkpoints."""
    import json
    public = Path(public)
    for kind in ('B0_MATCHED_V2', 'B1_V2'):
        path = public / kind / 'final_report.json'
        if not path.is_file():
            raise PermissionError('Both frozen Phase-A runs must complete before BEST review')
        value = json.loads(path.read_text(encoding='utf-8'))
        if value['status'] != 'COMPLETE' or value['model'] != kind:
            raise PermissionError('Phase-A terminal identity not complete')
        epoch, counter = value['completed_epoch'], value['final_early_stop_counter']
        if not (1 <= epoch <= 50) or value['patience'] != 8 or value['min_delta'] != 1e-4:
            raise ValueError('Frozen terminal policy differs')
        reason = 'EARLY_STOP_PATIENCE_8' if counter >= 8 else 'MAX_EPOCH_50'
        if value['termination_reason'] != reason or (counter < 8 and epoch != 50):
            raise ValueError('Premature Phase-A completion')
    if not (public / 'pair_training_completed.json').is_file():
        raise PermissionError('Pair completion marker required')
