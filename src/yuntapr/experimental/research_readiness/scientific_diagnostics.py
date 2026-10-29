"""Offline statistics only; no model, source observations, or selection rules."""
import math
import numpy as np


def binned_brier(n_valid, n_rain, brier, bins):
    """Exact Murphy identity for the BIN-MEAN forecast, plus original-score residual.

    Original scores vary inside each fixed 0.1-wide bin. The residual is NOT
    calibration error: Var(p|bin) - 2 Cov(p,y|bin), weighted by bin population.
    Saved counts/sums cannot identify those two terms separately.
    """
    if sum(x['n'] for x in bins)!=n_valid or sum(x['rain'] for x in bins)!=n_rain:
        raise ValueError('Reliability population mismatch')
    climatology=n_rain/n_valid;rel=res=ece=bs_bin=0.;records=[]
    for i,b in enumerate(bins):
        n,r=b['n'],b['rain']
        if not n:
            records.append(dict(index=i,n=0,mean_probability=None,observed_frequency=None,bias=None))
            continue
        p=b['probability_sum']/n;f=r/n;w=n/n_valid
        rel+=w*(p-f)**2;res+=w*(f-climatology)**2;ece+=w*abs(p-f)
        bs_bin+=w*(f*(p-1)**2+(1-f)*p**2)
        records.append(dict(index=i,n=n,rain=r,mean_probability=p,observed_frequency=f,bias=p-f,weight=w))
    unc=climatology*(1-climatology)
    if not math.isclose(bs_bin,rel-res+unc,abs_tol=1e-12):raise ValueError('Binned decomposition identity failed')
    return dict(original_brier=brier,binned_mean_forecast_brier=bs_bin,binned_reliability=rel,binned_resolution=res,
                uncertainty=unc,binning_residual=brier-bs_bin,binned_ECE=ece,climatology=climatology,
                bins=records,exact_original_score_reliability='NOT_AVAILABLE_WITHIN_BIN_P2_AND_PY_NOT_SAVED',
                high_probability_ge_0_8_count=sum(b['n'] for b in bins[8:]),
                high_probability_ge_0_9_count=bins[9]['n'],
                interpretation='BIN_MEAN_DIAGNOSTIC_NOT_EXACT_ORIGINAL_SCORE_CALIBRATION_DECOMPOSITION')


def paired_week_bootstrap(arms, *, repetitions=2000, seed=20261029):
    """Resample the same fixed weeks across every seed and model, not pixels/seeds.

    arms[seed][model] holds 35 saved block summaries and score-count arrays
    [week,descending score]. AUROC/AP are recomputed from pooled weighted
    score counts, never averaged from weekly AUROCs/APs.
    """
    if set(arms)!={'2029','2030','2031'}:raise ValueError('Three paired training seeds required')
    rng=np.random.default_rng(seed)
    multiplicity=rng.multinomial(35,np.full(35,1/35),size=repetitions)
    weights=np.vstack((np.ones((1,35)),multiplicity))
    deltas={k:[] for k in ('brier','auroc','average_precision','conditional_pinball','q32_coverage','q32_absolute_error')}
    for models in arms.values():
        forecasts={}
        for kind in ('B7','B8'):
            a=models[kind];blocks=a['blocks']
            if len(blocks)!=35:raise ValueError('Inherit all 35 pre-existing weekly blocks')
            total=lambda key:weights@np.array([x[key] for x in blocks],dtype=float)
            nv,nr=total('n_valid'),total('n_rain')
            if (nv<=0).any() or (nr<=0).any():raise ValueError('Empty bootstrap denominator; record unestimable draws explicitly')
            pos=weights@a['pos'];neg=weights@a['neg'];tp=pos.cumsum(axis=1);fp=neg.cumsum(axis=1)
            np_,nn_=pos.sum(axis=1),neg.sum(axis=1)
            if not np.allclose(np_,nr):raise ValueError('Scores and block rainy counts differ')
            cov=(weights@np.array([x['covered'][-1] for x in blocks]))/nr
            forecasts[kind]=dict(brier=total('brier_sum')/nv,conditional_pinball=total('s_qr')/nr,q32_coverage=cov,
                q32_absolute_error=np.abs(cov-.984375),auroc=(pos*(nn_[:,None]-fp+.5*neg)).sum(axis=1)/(np_*nn_),
                average_precision=(pos/np_[:,None]*np.divide(tp,tp+fp,out=np.zeros_like(tp),where=(tp+fp)>0)).sum(axis=1))
        for key in deltas:deltas[key].append(forecasts['B8'][key]-forecasts['B7'][key])
    result={}
    for key,ds in deltas.items():
        mean=np.mean(ds,axis=0)
        result[key]=dict(point_estimate=float(mean[0]),percentile_interval_95=np.quantile(mean[1:],[.025,.975]).tolist())
    return dict(status='EXPLORATORY_TEMPORAL_WEEK_BOOTSTRAP_NOT_INDEPENDENT_STORM_CI',blocks=35,repetitions=repetitions,
                seed=seed,interval='PERCENTILE_2_5_97_5',metrics=result,
                seed_handling='SAME_RESAMPLED_WEEKS_FOR_ALL_ARMS_AND_SEEDS_THEN_MEAN_PAIRED_DELTA',
                independence='NOT_VERIFIED; weather may cross weeks; no storm ids/spatial components',significance='NOT_CLAIMED')
