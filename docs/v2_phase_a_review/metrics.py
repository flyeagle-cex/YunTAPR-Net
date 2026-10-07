"""Read-only v2 review metrics; same occurrence definitions as historical review.

Caller must separately gate finished Phase-A runs and frozen 2024 BEST identities.
This component performs no model execution, checkpoint selection or physical transform.
"""
import numpy as np
import torch
from yuntapr.training.phase_a_validation import grouped_occurrence_metrics
from yuntapr.training.phase_a_validation_v2 import LogDomainValidation


class ReviewMetrics:
    def __init__(self):
        self.core = LogDomainValidation()
        self.brier_sum = 0.
        self.scores, self.labels = [], []

    @torch.no_grad()
    def add(self, output, target, valid, mask):
        self.core.add(output, target, valid, mask)
        selected = valid & mask
        probability = output.rain_prob[selected].double()
        rainy = target[selected] > .1
        self.brier_sum += float((probability - rainy.double()).square().sum(dtype=torch.float64))
        self.scores.append(probability.cpu().numpy().copy())
        self.labels.append(rainy.cpu().numpy().copy())

    def report(self):
        core = self.core.report()
        return {**core, 'Brier_Score': self.brier_sum / core['N_valid'],
                **grouped_occurrence_metrics(np.concatenate(self.scores), np.concatenate(self.labels)),
                'conditional_mean_pinball': core['S_qr'] / core['N_rain'] if core['N_rain'] else None,
                'conditional_pinball_denominator': 'rainy valid Yunnan scene-pixel exposures; mean across 32 tau',
                'Brier_denominator': 'all valid Yunnan scene-pixel exposures',
                'rain_label': 'float32 target > 0.1 mm/h before float64 promotion',
                'ranking_scope': 'all validation scene-pixel exposures jointly; exact score ties grouped',
                'physical_materialization': False, 'selection_effect': 'NONE_READ_ONLY_REVIEW',
                'BACKWARD_CALLS': 0, 'OPTIMIZER_STEPS': 0}
