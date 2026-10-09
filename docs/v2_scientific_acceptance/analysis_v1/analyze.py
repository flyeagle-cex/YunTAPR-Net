"""Paired week-block exploratory analysis from registered sufficient statistics."""
from pathlib import Path
import argparse, json, csv, hashlib
import numpy as np
from sufficient_stats import GROUPS, TAU, metrics
NAMES=['Core_loss','Brier','AUROC','AP','conditional_pinball']
def clean(x):
    if isinstance(x,np.ndarray): return clean(x.tolist())
    if isinstance(x,(np.floating,float)): return float(x) if np.isfinite(x) else None
    if isinstance(x,dict): return {k:clean(v) for k,v in x.items()}
    if isinstance(x,list): return [clean(v) for v in x]
    if isinstance(x,np.integer): return int(x)
    return x
def save(path,value):
    with path.open('x',encoding='utf-8') as f: json.dump(clean(value),f,indent=2,ensure_ascii=False,allow_nan=False); f.write('\n')
def table(path,rows):
    with path.open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(clean(rows))
def block_weights():
    rng=np.random.default_rng(2026)
    return np.array([np.bincount(rng.integers(0,35,35),minlength=35) for _ in range(2000)],dtype=np.int64)
def rank_many(counts):
    c=counts[:,::-1]; neg,pos=c[:,:,0],c[:,:,1]
    P,N=pos.sum(1),neg.sum(1); tp=np.cumsum(pos,axis=1); fp=np.cumsum(neg,axis=1)
    precision=np.divide(tp,tp+fp,out=np.zeros_like(tp),where=(tp+fp)>0)
    ap=np.divide((pos*precision).sum(1),P,out=np.full(len(c),np.nan),where=P>0)
    auc=np.divide((neg*(2*tp-pos)).sum(1),2*P*N,out=np.full(len(c),np.nan),where=(P*N)>0)
    return np.c_[auc,ap]
def ci(values):
    finite=np.asarray(values)[np.isfinite(values)]
    return {'lower':float(np.quantile(finite,.025)) if len(finite) else None,
            'upper':float(np.quantile(finite,.975)) if len(finite) else None,'valid_replicates':len(finite),'requested_replicates':2000}
def bootstrap_metrics(blocks,scores,weights):
    weighted=weights @ blocks
    result=np.full((2000,5),np.nan); n,rain=weighted[:,:2].T
    result[:,0]=np.divide(weighted[:,2]+weighted[:,3],n,out=np.full(2000,np.nan),where=n>0)
    result[:,1]=np.divide(weighted[:,4],n,out=np.full(2000,np.nan),where=n>0)
    result[:,4]=np.divide(weighted[:,3],rain,out=np.full(2000,np.nan),where=rain>0)
    # Globally pool exact scores at each paired replicate; never average daily AUROC/AP.
    active = np.flatnonzero(scores.sum((0,2)) > 0)
    positive, negative = scores[:,:,1].sum(), scores[:,:,0].sum()
    if positive and negative:
        exact_counts = scores[:,active].reshape(35,-1).astype(np.float64)
        for start in range(0,2000,100):
            counts=(weights[start:start+100].astype(float) @ exact_counts).reshape(-1,len(active),2)
            assert np.all(counts == np.floor(counts))  # integer counts remain exactly representable
            result[start:start+100,2:4]=rank_many(counts)
    elif positive:
        result[n>0,3]=1.0  # all-positive AP, explicitly flagged as trivial

    return result,weighted
def main():
    p=argparse.ArgumentParser(); p.add_argument('--run',type=Path,required=True); args=p.parse_args(); run=args.run
    result=json.loads((run/'paired_best_metrics.json').read_text())
    assert result['status']=='PAIRED_SCIENTIFIC_ACCEPTANCE_READ_ONLY_2024_PASS'
    weights=block_weights(); np.save(run/'paired_bootstrap_block_multiplicities.npy',weights)
    data={k:np.load(run/k/'sufficient_statistics.npz') for k in ('B0_MATCHED_V2','B1_V2')}
    for k,d in data.items():
        assert d['daily'][:,0,0].sum()==36018430 and d['daily'][:,0,1].sum()==4496600
        assert d['scores'][:,0,:,1].sum()==4496600 and d['scores'][:,0].sum()==36018430
        assert np.array_equal(d['daily'][:,0,0],data['B0_MATCHED_V2']['daily'][:,0,0])
    rows=[]; comparisons={}; reliability=[]; coverage=[]; assumptions=[]; reconciliation=[]
    for group,name in enumerate(GROUPS):
        point={}; boots={}; weighted={}
        for k,d in data.items():
            blocks=d['daily'][:,group].reshape(35,7,-1).sum(1)
            point[k]=metrics(blocks.sum(0),d['scores'][:,group].sum(0))
            boots[k],weighted[k]=bootstrap_metrics(blocks,d['scores'][:,group],weights)
            sums=blocks.sum(0)
            if group==0:
                old=result['models'][k]['metrics']
                expected=np.array([old['global_val_core_loss'],old['Brier_Score'],old['AUROC'],old['Average_Precision'],old['conditional_mean_pinball']])
                np.testing.assert_allclose(point[k],expected,rtol=1e-12,atol=1e-12)
                reconciliation.append({'model':k,'point_metric_absolute_differences':np.abs(point[k]-expected).tolist(),'supplemental_tolerance':{'absolute':1e-12,'relative':1e-12},'reported_global_points':'REUSED_PUBLISHED_EXACT_FULL_2024_METRICS'})
                point[k]=expected
                for j in range(10):
                    counts=weighted[k][:,73+j]; observed=np.divide(weighted[k][:,93+j],counts,out=np.full(2000,np.nan),where=counts>0)
                    predicted=np.divide(weighted[k][:,83+j],counts,out=np.full(2000,np.nan),where=counts>0)
                    reliability.append({'model':k,'bin_index':j,'lower':j/10,'upper':(j+1)/10,'count':int(sums[73+j]),
                        'mean_probability':sums[83+j]/sums[73+j] if sums[73+j] else None,
                        'observed_frequency':sums[93+j]/sums[73+j] if sums[73+j] else None,
                        'observed_ci_lower':ci(observed)['lower'],'observed_ci_upper':ci(observed)['upper'],
                        'predicted_ci_lower':ci(predicted)['lower'],'predicted_ci_upper':ci(predicted)['upper'],
                        'bootstrap_valid_replicates':ci(observed)['valid_replicates']})
                for j,tau in enumerate(TAU):
                    empirical=sums[9+j]/sums[1]; rain=weighted[k][:,1]
                    samples=np.divide(weighted[k][:,9+j],rain,out=np.full(2000,np.nan),where=rain>0)
                    coverage.append({'model':k,'tau':tau,'N_rain':int(sums[1]),'coverage':empirical,'coverage_error':empirical-tau,
                        'coverage_ci_lower':ci(samples)['lower'],'coverage_ci_upper':ci(samples)['upper'],
                        'conditional_pinball':sums[41+j]/sums[1]})
            proxy={'DIAGNOSTIC_PROXY_Bias_mm_h':sums[6]/sums[0] if sums[0] else None,
                'DIAGNOSTIC_PROXY_MAE_mm_h':sums[7]/sums[0] if sums[0] else None,
                'DIAGNOSTIC_PROXY_RMSE_mm_h':np.sqrt(sums[8]/sums[0]) if sums[0] else None}
            rows.append({'group':name,'model':k,'N_valid':int(sums[0]),'N_rain':int(sums[1]),
                **dict(zip(NAMES,point[k])),**proxy,'POD_FAR_CSI':'THRESHOLD_NOT_FROZEN',
                'scope':'EXPLORATORY_2024_DEVELOPMENT_TRUTH_CONDITIONED' if group>=14 else 'EXPLORATORY_2024_DEVELOPMENT',
                **{n+'_ci_lower':ci(boots[k][:,j])['lower'] for j,n in enumerate(NAMES)},
                **{n+'_ci_upper':ci(boots[k][:,j])['upper'] for j,n in enumerate(NAMES)}})
        a,b=point.values(); ba,bb=boots.values()
        diff=b-a; relative=100*diff/np.abs(a)
        comparisons[name]={}
        for j,n in enumerate(NAMES):
            delta=bb[:,j]-ba[:,j]
            rel=np.divide(100*delta,np.abs(ba[:,j]),out=np.full(2000,np.nan),where=np.abs(ba[:,j])>0)
            comparisons[name][n]={'B0':a[j],'B1':b[j],'B1_minus_B0':diff[j],'relative_percent_of_B0':relative[j],
                'paired_difference_95_percentile_interval':ci(delta),'paired_relative_difference_95_percentile_interval':ci(rel),
                'interpretation':'ALL_RAIN_AP_TRIVIAL_NOT_DETECTION_EVIDENCE' if group>=15 and n=='AP' else 'SINGLE_CLASS_NOT_ESTIMABLE' if group>=14 and n=='AUROC' else 'EXPLORATORY_DEVELOPMENT_ONLY'}
        if group==0:
            # Check correlation descriptively; never tune block length from this result.
            a_day=data['B0_MATCHED_V2']['daily'][:,0]; b_day=data['B1_V2']['daily'][:,0]
            series=(b_day[:,2:4].sum(1)-a_day[:,2:4].sum(1))/a_day[:,0]
            for lag in (1,2,7,14): assumptions.append({'lag_days':lag,'daily_paired_core_delta_correlation':float(np.corrcoef(series[:-lag],series[lag:])[0,1])})
        print(json.dumps({'analysis_group_complete':name}),flush=True)
    table(run/'PAIRED_STRATIFIED_ANALYSIS.csv',rows); table(run/'reliability_fixed_bins.csv',reliability); table(run/'conditional_quantile_calibration.csv',coverage)
    save(run/'paired_uncertainty.json',{'status':'EXPLORATORY_DEVELOPMENT_ANALYSIS_COMPLETE','comparisons':comparisons,
        'replicates':2000,'seed':2026,'week_blocks':35,'CI':'pointwise paired percentile; not multiplicity-adjusted; no confirmatory p-values',
        'daily_core_delta_lag_correlations':assumptions,'published_global_point_reconciliation':reconciliation,
        'observed_calendar_dates':int((data['B0_MATCHED_V2']['daily'][:,0,0]>0).sum()),'block_length_changed_from_results':False,
        'BEST_selection_optimism_not_corrected':True,'independent_seed_uncertainty_not_estimated':True,
        '2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,'MODEL_PARAMETERS_UPDATED':False,'OPTIMIZER_STEPS':0})
    save(run/'analysis_input_binding.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('sufficient_stats.py'),*(run/k/'sufficient_statistics.npz' for k in data)]})
if __name__=='__main__': main()
