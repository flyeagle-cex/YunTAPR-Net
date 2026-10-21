"""Predeclared M-C primary contrasts, paired UTC-week exploratory intervals.

Executed only after all six fixed epoch9 endpoints. No model/data re-evaluation,
threshold selection, p-values, seed pooling or confirmatory success decision.
"""
from __future__ import annotations
import numpy as np
from .protocol import OUT,run_id,atomic_json,digest,SEED

def compare(completed):
    reports={r['run_id']:r['epochs'][-1]['development'] for r in completed}
    generator=np.random.default_rng(2026)
    draw=generator.integers(0,35,size=(2000,35))
    weights=np.stack([np.bincount(row,minlength=35) for row in draw])
    assert bool((weights.sum(1)==35).all())
    atomic_json(OUT/'paired_bootstrap_multiplicities.json',dict(seed=2026,replicates=2000,blocks=35,
        values=weights.tolist(),sha256=digest(weights.tolist())))
    def metrics(report):
        blocks=report['blocks'];nv=np.array([b['n_valid'] for b in blocks]);nr=np.array([b['n_rain'] for b in blocks])
        brier=weights @ np.array([b['brier_sum'] for b in blocks]);cover=weights @ np.array([b['covered'][31] for b in blocks])
        with np.errstate(divide='ignore',invalid='ignore'):
            return dict(brier=brier/(weights@nv),q32_absolute_error=np.abs(cover/(weights@nr)-.984375))
    sampled={k:metrics(v) for k,v in reports.items()};rows=[]
    for model in ('B0_MATCHED_V2','B1_V2'):
        base=reports[run_id(model,'E0')]
        for arm,key in (('E1','brier'),('E2','q32_absolute_error')):
            alternative=reports[run_id(model,arm)]
            delta=sampled[run_id(model,arm)][key]-sampled[run_id(model,'E0')][key]
            delta=delta[np.isfinite(delta)]
            point=None if base['summary'][key] is None or alternative['summary'][key] is None else alternative['summary'][key]-base['summary'][key]
            rows.append(dict(model=model,seed=SEED,contrast=f'{arm}-E0',primary_metric=key,units='dimensionless',difference=point,
                exploratory_95_percentile_interval=np.quantile(delta,[.025,.975]).tolist() if len(delta) else [None,None],
                valid_replicates=len(delta),side_effect_differences={m:None if base['summary'][m] is None or alternative['summary'][m] is None
                    else alternative['summary'][m]-base['summary'][m] for m in ('core_fp64','conditional_pinball','auroc','average_precision')}))
    atomic_json(OUT/'primary_comparisons.json',dict(contrasts=rows,scope=f'2024_DEVELOPMENT_SEED{SEED}_ONLY',
        paired_same_week_weights=True,block_method='35 nonoverlapping UTC seven-day blocks, label window_start',
        intervals_cover_primary_contrasts_only=True,multiplicity_correction=False,confirmatory_significance=False,
        limitations=['2024 already used for BEST and diagnostics','cross-week dependence','seasonal nonstationarity',
                    'single seed does not estimate training-seed variability','scene-pixel exposures are not independent events'],
        minimum_meaningful_effect='NOT_YET_ESTABLISHED',scientific_success='NOT_ESTABLISHED'))
