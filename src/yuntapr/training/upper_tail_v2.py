"""Detached, exact per-forward diagnostics. Never a training decision input."""
import math
import csv
import os
from pathlib import Path
import numpy as np
import torch
from .phase_a_audit_v2 import append_event

THRESHOLDS = (10, 50, 100, 500, 1000)
BOUNDARY = math.log1p(np.finfo(np.float64).max)


def save_csv(path, reports):
    fields=['phase','region','max_qlog','q32_per_forward_max_p99','q32_per_forward_max_p99_9',
            'FP64_PHYSICAL_OVERFLOW_RISK','threshold_mm_h','scene_pixel_tau_exceedances',
            'scene_pixel_any_tau_exceedances','scene_pixel_tau_exposure','scene_pixel_any_tau_exposure']
    with Path(path).open('x',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for phase,report in reports.items():
            for label in ('YUNNAN_INSIDE','YUNNAN_OUTSIDE'):
                values=report[label]
                for threshold in THRESHOLDS:
                    counts=values['threshold_exceedances'][str(threshold)]
                    writer.writerow({'phase':phase,'region':label,'threshold_mm_h':threshold,
                        **{k:values[k] for k in fields[2:6]},
                        'scene_pixel_tau_exceedances':counts['scene_pixel_tau_exposure'],
                        'scene_pixel_any_tau_exceedances':counts['scene_pixel_any_tau_exposure'],
                        'scene_pixel_tau_exposure':values['scene_pixel_tau_exposure'],
                        'scene_pixel_any_tau_exposure':values['scene_pixel_any_tau_exposure']})
        stream.flush();os.fsync(stream.fileno())


class UpperTailDiagnostics:
    def __init__(self, mask, phase, log_path=None):
        self.mask = torch.as_tensor(mask, dtype=torch.bool).cpu()
        if self.mask.ndim != 2 or not self.mask.any() or self.mask.all():
            raise ValueError('Nonempty inside and outside mask required')
        if phase not in ('TRAIN', 'VALIDATION', 'TEST_FIXTURE_ONLY'):
            raise ValueError('Explicit phase required')
        self.phase, self.log_path = phase, log_path
        self.rows = []

    @torch.no_grad()
    def observe(self, qlog, sample_ids):
        if qlog.dtype != torch.float64 or qlog.shape[1:] != (32, *self.mask.shape) or len(sample_ids) != qlog.shape[0]:
            raise ValueError('Diagnostic tensor identity mismatch')
        # Caller enforces the numerical contract. Diagnostics do not repair it.
        q = qlog.detach().cpu()
        if not torch.isfinite(q).all():
            raise FloatingPointError('Nonfinite diagnostic input; numerical guard must reject it')
        item = {'phase': self.phase, 'forward_index': len(self.rows) + 1,
                'sample_ids': list(sample_ids), 'batch_size': q.shape[0]}
        for label, mask in (('YUNNAN_INSIDE', self.mask), ('YUNNAN_OUTSIDE', ~self.mask)):
            positions = mask.nonzero()
            values = q[:, :, mask]
            flat = int(values.argmax()); cells = values.shape[-1]
            scene, tau, cell = flat // (32 * cells), flat // cells % 32, flat % cells
            counts = {}
            for threshold in THRESHOLDS:
                exceeded = values > math.log1p(threshold)
                counts[str(threshold)] = {
                    'scene_pixel_tau_exposure': int(exceeded.sum(dtype=torch.int64)),
                    'scene_pixel_any_tau_exposure': int(exceeded.any(dim=1).sum(dtype=torch.int64)),
                }
            item[label] = {
                'max_qlog': float(values.max()), 'q32_max_qlog': float(values[:, 31].max()),
                'max_location': {'sample_id': sample_ids[scene], 'batch_index': scene,
                                 'tau_index': tau, 'tau': (tau + .5) / 32,
                                 'row': int(positions[cell, 0]), 'column': int(positions[cell, 1])},
                'FP64_PHYSICAL_OVERFLOW_RISK': bool((values > BOUNDARY).any()),
                'fp64_boundary_exceedance_count': int((values > BOUNDARY).sum(dtype=torch.int64)),
                'scene_pixel_tau_exposure': values.numel(),
                'scene_pixel_any_tau_exposure': values.shape[0] * cells,
                'threshold_exceedances': counts,
            }
        if self.log_path:
            append_event(self.log_path, 'UPPER_TAIL_FORWARD', **item)
        self.rows.append(item)
        return item

    def report(self):
        if not self.rows:
            raise ValueError('No diagnostic forwards')
        report = {'phase': self.phase, 'forwards': len(self.rows),
                  'scenes': sum(r['batch_size'] for r in self.rows),
                  'qlog_unit': 'log1p(mm/h)', 'FP64_physical_boundary': BOUNDARY,
                  'percentile_method': 'numpy.quantile float64 linear; each forward has equal weight',
                  'threshold_comparison': 'qlog > log1p(threshold_mm_h)',
                  'affects_loss_BEST_early_stop_LR_parameters_batch_or_termination': False}
        for label in ('YUNNAN_INSIDE', 'YUNNAN_OUTSIDE'):
            rows = [r[label] for r in self.rows]
            maxima = np.asarray([r['q32_max_qlog'] for r in rows], dtype=np.float64)
            p99, p999 = np.quantile(maxima, [.99, .999], method='linear')
            report[label] = {
                'max_qlog': max(r['max_qlog'] for r in rows),
                'q32_per_forward_max_p99': float(p99), 'q32_per_forward_max_p99_9': float(p999),
                'FP64_PHYSICAL_OVERFLOW_RISK': any(r['FP64_PHYSICAL_OVERFLOW_RISK'] for r in rows),
                'fp64_boundary_exceedance_count': sum(r['fp64_boundary_exceedance_count'] for r in rows),
                'scene_pixel_tau_exposure': sum(r['scene_pixel_tau_exposure'] for r in rows),
                'scene_pixel_any_tau_exposure': sum(r['scene_pixel_any_tau_exposure'] for r in rows),
                'threshold_exceedances': {str(t): {unit: sum(r['threshold_exceedances'][str(t)][unit] for r in rows)
                    for unit in ('scene_pixel_tau_exposure', 'scene_pixel_any_tau_exposure')} for t in THRESHOLDS},
            }
        return report
