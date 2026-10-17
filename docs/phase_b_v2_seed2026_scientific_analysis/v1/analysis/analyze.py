"""Recompute manuscript tables, paired M-C intervals and measured resource needs.

No model imports or pixel reads. All statistical inference remains exploratory.
"""
import importlib.metadata,json,math,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from common import ROOT,OUT,FORMAL,RUNS,read,save,table,load,digest,close,sha
sys.path.insert(0,str(OUT/'.local/deps'))
import numpy as np

def bootstrap_metrics(report,weights):
    b=report['blocks'];nv=np.array([x['n_valid'] for x in b]);nr=np.array([x['n_rain'] for x in b])
    if weights.ndim!=2 or weights.shape[1]!=len(b) or not np.isfinite(weights).all() or (weights<0).any():
        raise ValueError('INVALID_BLOCK_MULTIPLICITIES')
    if (weights@nv<=0).any() or (weights@nr<=0).any():
        raise ValueError('UNESTIMABLE_BOOTSTRAP_DENOMINATOR')
    return {'brier':weights@np.array([x['brier_sum'] for x in b])/(weights@nv),
      'q32_absolute_error':np.abs(weights@np.array([x['covered'][31] for x in b])/(weights@nr)-.984375)}

def validation_folder(model,arm,epoch,default):
    if (model,arm)==('B1','E1'):
        return 'seed2026_v2' if epoch<=3 else ('seed2026_resume_v2' if epoch<=7 else 'seed2026_operator_v3')
    return default

def main():
    rows=load();sources={};summaries=[];curves=[];reliability=[];quantiles=[];strata=[];tails=[];timing=[];final={};audited=0
    expected_weights=read(FORMAL/'seed2026_operator_v3/paired_bootstrap_multiplicities.json')
    draw=np.random.default_rng(2026).integers(0,35,size=(2000,35))
    weights=np.stack([np.bincount(v,minlength=35) for v in draw])
    if not np.array_equal(weights,expected_weights['values']) or digest(weights.tolist())!=expected_weights['sha256']:raise ValueError('BOOTSTRAP_WEIGHTS_IDENTITY')
    validation_ids=set();orders={};scene_pairs=None
    for model,arm,folder,run in RUNS:
        row=rows[(model,arm)];path=FORMAL/folder/(run+'.json');sources[path.relative_to(ROOT).as_posix()]=sha(path.read_bytes())
        if row['updates']!=47052 or len(row['epochs'])!=9:raise ValueError('NINTH_ENDPOINT')
        for epoch,entry in enumerate(row['epochs'],1):
            r=dict(entry['development']);receipt=r.pop('receipt_sha');s=r['summary'];train=entry['train']
            if digest(r)!=receipt or not r['complete'] or entry['epoch']!=epoch:raise ValueError('RECEIPT_SHA')
            if train['scenes']!=10455 or train['batches']!=5228:raise ValueError('TRAIN_COVERAGE_BUDGET')
            close(train['weighted_training_mean'],(train['s_occ_unweighted']+(2 if arm=='E2' else 1)*train['s_qr_unweighted'])/train['n_valid'])
            validation_ids.add(r['ids_sha']);orders.setdefault(epoch,set()).add(train['ids_sha'])
            if scene_pairs is None:scene_pairs=r['scene_blocks']
            elif r['scene_blocks']!=scene_pairs:raise ValueError('PAIRED_SCENE_WEEK_IDENTITIES')
            for key,count in [('n_valid',36018430),('n_rain',4496600),('scenes',10501)]:
                if s[key]!=count or sum(b[key] for b in r['blocks'])!=count:raise ValueError('BLOCK_DENOMINATOR')
            for key in ('s_occ','s_qr','brier_sum'):close(sum(b[key] for b in r['blocks']),s[key])
            close(s['core_fp64'],(s['s_occ']+s['s_qr'])/s['n_valid']);close(s['conditional_pinball'],s['s_qr']/s['n_rain'])
            if s['tau']!=[(i+.5)/32 for i in range(32)]:raise ValueError('TAU')
            for i in range(32):close(sum(b['covered'][i] for b in r['blocks']),s['covered'][i]);close(s['coverage'][i],s['covered'][i]/s['n_rain'])
            if sum(b['n'] for b in s['reliability'])!=s['n_valid'] or sum(b['rain'] for b in s['reliability'])!=s['n_rain']:raise ValueError('RELIABILITY_COUNTS')
            if sum(x['n'] for x in s['rain_strata'])!=s['n_rain']:raise ValueError('STRATA_COUNTS')
            audited+=1
            curves.append(dict(model=model,arm=arm,epoch=epoch,weighted_train_loss=train['weighted_training_mean'],
              **{k:s[k] for k in ('core_fp64','brier','auroc','average_precision','conditional_pinball')},q32_coverage=s['coverage'][31]))
            vf=validation_folder(model,arm,epoch,folder)
            resource=FORMAL/vf/'.local'/run/f'development_epoch_{epoch:02d}/resources.json';vr=read(resource)
            sources[resource.relative_to(ROOT).as_posix()]=sha(resource.read_bytes())
            timing.append(dict(model=model,arm=arm,epoch=epoch,train_seconds=train['elapsed_seconds'],validation_seconds=vr['elapsed_seconds'],
              total_seconds=train['elapsed_seconds']+vr['elapsed_seconds']))
        s=row['epochs'][-1]['development']['summary'];final[(model,arm)]=s
        ece=sum(b['n']*abs(b['mean_probability']-b['frequency']) for b in s['reliability'] if b['n'])/s['n_valid']
        meanp=sum(b['probability_sum'] for b in s['reliability'])/s['n_valid'];prev=s['n_rain']/s['n_valid']
        summaries.append(dict(model=model,arm=arm,**{k:s[k] for k in ('core_fp64','brier','auroc','average_precision','conditional_pinball')},
          q32_coverage=s['coverage'][31],q32_signed_bias=s['q32_signed_bias'],q32_absolute_error=s['q32_absolute_error'],
          ece10_descriptive=ece,mean_predicted_probability=meanp,rain_prevalence=prev,mean_probability_bias=meanp-prev,
          q32_max_mm_h=math.expm1(s['q32_log_max']),max_span_log=s['span_log_max']))
        for i,b in enumerate(s['reliability']):reliability.append(dict(model=model,arm=arm,bin=i,lower=i/10,upper=(i+1)/10,**b,
            gap=None if not b['n'] else b['mean_probability']-b['frequency']))
        for i,(tau,cov,n) in enumerate(zip(s['tau'],s['coverage'],s['covered'])):quantiles.append(dict(model=model,arm=arm,index=i+1,tau=tau,coverage=cov,covered=n,n_rain=s['n_rain'],signed_bias=cov-tau))
        for i,v in enumerate(s['rain_strata']):strata.append(dict(model=model,arm=arm,stratum=i+1,lower=[.1,1,5,10,20,30,50][i],upper=v['upper'],n=v['n'],conditional_pinball=v['conditional_pinball']))
        for v in s['tail']:tails.append(dict(model=model,arm=arm,**v))
    if len(validation_ids)!=1 or any(len(v)!=1 for v in orders.values()):raise ValueError('PAIRED_DATA')
    published=read(FORMAL/'seed2026_operator_v3/primary_comparisons.json');contrasts=[]
    reports={k:rows[k]['epochs'][-1]['development'] for k in rows}
    sampled={k:bootstrap_metrics(r,weights) for k,r in reports.items()}
    for c in published['contrasts']:
        m='B0' if c['model']=='B0_MATCHED_V2' else 'B1';arm=c['contrast'][:2];key=c['primary_metric']
        diff=sampled[(m,arm)][key]-sampled[(m,'E0')][key]
        interval=np.quantile(diff,[.025,.975],method='linear');point=final[(m,arm)][key]-final[(m,'E0')][key]
        close(point,c['difference']);close(interval[0],c['exploratory_95_percentile_interval'][0]);close(interval[1],c['exploratory_95_percentile_interval'][1])
        # Independent direct draw pooling checks weighting (not averaging blocks).
        direct=[]
        for selected in draw:
            vals=[]
            for a in (arm,'E0'):
                blocks=reports[(m,a)]['blocks'];selected_blocks=[blocks[int(j)] for j in selected]
                if key=='brier':vals.append(sum(b['brier_sum'] for b in selected_blocks)/sum(b['n_valid'] for b in selected_blocks))
                else:vals.append(abs(sum(b['covered'][31] for b in selected_blocks)/sum(b['n_rain'] for b in selected_blocks)-.984375))
            direct.append(vals[0]-vals[1])
        if not np.allclose(direct,diff,rtol=0,atol=2e-14):raise ValueError('DIRECT_DRAW_POOLING_MISMATCH')
        contrasts.append(dict(model=m,contrast=c['contrast'],metric=key,difference=point,lower=float(interval[0]),upper=float(interval[1]),replicates=2000,registered_primary=True,confirmatory=False))
    temporal=[];sideeffects=[]
    for arm in ('E0','E1','E2'):
        b0,b1=final[('B0',arm)],final[('B1',arm)]
        temporal.append(dict(arm=arm,**{k:b1[k]-b0[k] for k in ('core_fp64','brier','auroc','average_precision','conditional_pinball','q32_absolute_error')}))
    for model in ('B0','B1'):
        for arm in ('E1','E2'):
            b,a=final[(model,'E0')],final[(model,arm)]
            sideeffects.append(dict(model=model,contrast=arm+'-E0',**{k:a[k]-b[k] for k in ('core_fp64','brier','auroc','average_precision','conditional_pinball','q32_absolute_error')}))
    for name,values in [('final_metrics.csv',summaries),('curves.csv',curves),('reliability.csv',reliability),('coverage32.csv',quantiles),('rain_strata.csv',strata),('tail_exposures.csv',tails),('registered_contrasts.csv',contrasts),('temporal_differences.csv',temporal),('side_effects.csv',sideeffects),('epoch_timings.csv',timing)]:table(name,values)
    models={};future_total=0.;total_measured=sum(x['total_seconds'] for x in timing)
    for model in ('B0','B1'):
        subset=[r for r in timing if r['model']==model];train=np.array([r['train_seconds'] for r in subset]);val=np.array([r['validation_seconds'] for r in subset]);total=train+val
        models[model]=dict(observed_epochs=len(subset),train_median_seconds=float(np.median(train)),validation_median_seconds=float(np.median(val)),
          mean_train_seconds=float(train.mean()),mean_validation_seconds=float(val.mean()),epoch_p10_seconds=float(np.quantile(total,.1)),epoch_p90_seconds=float(np.quantile(total,.9)),
          future_runs=6,future_epochs=54,future_central_hours=float(54*total.mean()/3600),future_p10_scenario_hours=float(54*np.quantile(total,.1)/3600),future_p90_scenario_hours=float(54*np.quantile(total,.9)/3600))
        future_total+=54*total.mean()/3600
    finished=read(FORMAL/'seed2026_operator_v3/execution_status.json');terms=[];logbytes=0;missing=[]
    # Exact declared audit namespaces only; never traverse raw data roots.
    session_paths=[('seed2026_v2','.local'),('seed2026_resume_v1','.local'),('seed2026_resume_v2','.local'),('seed2026_operator_v1','.local/sessions/session_0001'),('seed2026_operator_v2','.local/sessions/session_0001'),('seed2026_operator_v3','.local/sessions/session_0001'),('seed2026_operator_v3','.local/sessions/session_0002')]
    for ns,session in session_paths:
        directory=FORMAL/ns/session
        for name in ('heartbeat.json','termination.json','preflight.json'):
            p=directory/name
            if p.exists():
                r=read(p);terms.append(dict(namespace=ns,session=session,kind=name,data=r));sources[p.relative_to(ROOT).as_posix()]=sha(p.read_bytes())
        p=directory/'access_and_events.jsonl'
        if p.exists():logbytes+=p.stat().st_size
    payload_bytes=sum(rows[k]['epochs'][-1]['checkpoint']['bytes'] for k in rows)
    # All 54 committed score DB files are existing aggregate workspaces; size only.
    scorebytes=0
    for model,arm,folder,run in RUNS:
        for epoch in range(1,10):
            f=validation_folder(model,arm,epoch,folder);p=FORMAL/f/'.local'/run/f'development_epoch_{epoch:02d}/exact_scores.sqlite'
            if p.exists():scorebytes+=p.stat().st_size
            else:missing.append(dict(run=run,epoch=epoch))
    peaks=dict(cuda_allocated=max(r['cuda_peak_allocated_bytes'] for r in rows.values()),cuda_reserved=max(r['cuda_peak_reserved_bytes'] for r in rows.values()),
       working_set=max((t['data'].get('peak_process_working_set_bytes',t['data'].get('cpu',{}).get('peak_working_set_bytes',0)) for t in terms),default=0),
       sampled_private_commit=max((t['data'].get('peak_process_private_commit_bytes',0) for t in terms),default=0),
       peak_pagefile_proxy=max((t['data'].get('cpu',{}).get('peak_pagefile_bytes',0) for t in terms),default=0))
    resource=dict(models=models,remaining_planned_updates=12*47052,remaining_epochs=108,remaining_validation_scenes=108*10501,
      committed_six_train_validation_hours=total_measured/3600,remaining_core_hours=future_total,
      remaining_p10_scenario_hours=sum(v['future_p10_scenario_hours'] for v in models.values()),remaining_p90_scenario_hours=sum(v['future_p90_scenario_hours'] for v in models.values()),
      observed_all_campaign_active_hours=finished['elapsed_seconds']/3600,
      remaining_historical_elapsed_ratio_hours=2*finished['elapsed_seconds']/3600,
      planning_25_percent_margin_hours=1.25*max(future_total,2*finished['elapsed_seconds']/3600),
      observed_raw_content_bytes=finished['actual_content_bytes'],remaining_content_bytes_linear_scenario=2*finished['actual_content_bytes'],
      six_final_payload_bytes=payload_bytes,remaining_108_checkpoint_payload_bytes=18*payload_bytes,three_copy_checkpoint_bytes=54*payload_bytes,
      observed_audit_log_bytes=logbytes,remaining_log_bytes_linear_scenario=2*logbytes,observed_committed_score_db_bytes=scorebytes,
      remaining_score_db_bytes_linear_scenario=2*scorebytes,remaining_score_db_hard_bound_bytes=108*256*1024**2,
      missing_score_db_metadata=missing,peaks_bytes=peaks,
      crash=dict(record='ancestor latest_crash_ancestor; source scripts/prepare_seed2026_operator_v3.py',driver='nvlddmkm event153 / LiveKernelEvent',utc='2026-10-14T00:26:59Z',lost_verified_updates=1795,root_cause='NOT_ESTABLISHED'),
      forecast_scope='OCCUPIED_SINGLE_GPU_WALL_HOURS_NOT_GPU_UTILIZATION_INTEGRAL',forecast_is_confidence_interval=False,
      margin_is_assumption_not_execution_grant=True,training_new_seeds_authorized=False)
    save('RESOURCE_ESTIMATE.json',resource);save('ANALYSIS_DATA.json',dict(final=summaries,curves=curves,reliability=reliability,quantiles=quantiles,strata=strata,tails=tails,
      contrasts=contrasts,temporal=temporal,sideeffects=sideeffects,timing=timing,resource=resource))
    save('RECOMPUTATION_AUDIT.json',dict(status='PASS',validated_epoch_receipts=audited,paired_scene_block_sets=6,primary_contrasts=4,replicates=2000,
      seed=2026,block_count=35,draw_weights_exact_match=True,direct_draw_pooling_verified=True,statistics='M-C_EXPLORATORY',new_optimizer_steps=0,
      raw_data_reads=0,model_inferences=0,scientific_success='NOT_FORMALLY_ESTABLISHED',sources=sources))
    packages=['numpy','matplotlib','pillow','contourpy','cycler','fonttools','kiwisolver','packaging','pyparsing','python-dateutil','six']
    versions={p:importlib.metadata.version(p) for p in packages};save('environment.json',dict(python=sys.version.split()[0],packages=versions))
    (OUT/'requirements-analysis.txt').write_text('\n'.join(p+'=='+v for p,v in versions.items())+'\n',encoding='utf-8')
    print(json.dumps(dict(status='ANALYSIS_PASS',registered_contrasts=contrasts,resource=resource),ensure_ascii=False))
if __name__=='__main__':main()
