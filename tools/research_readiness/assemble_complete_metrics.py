"""Saved-statistics-only input for the final single-table workbook.

No torch/checkpoints/raw observations. Candidate point estimates remain unfrozen.
Partial mode is for builder development, never called a complete delivery.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'docs/research_readiness/20261025/evidence'
NOMINAL=.984375


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def csvrows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def num(x):return None if x in ('',None,'None','null') else float(x)
def rid(model,seed,arm):return f'{model}_s{int(seed)}'+('_'+arm if model in ('B0','B1') else '')
RATE_FIELDS=('POD_r01_Pge05','FAR_r01_Pge05','CSI_r01_Pge05','HSS_r01_Pge05')


def archived_group(x,known):
    key=rid(x['model'],x['seed'],x['arm'])
    if key not in known:raise ValueError('Archived group has no matching final-E9 record')
    c={k:int(x[k]) for k in ('TP','FP','FN','TN')};c['N']=int(x['N_valid'])
    if sum(c[k] for k in ('TP','FP','FN','TN'))!=c['N']:raise ValueError('Archived group denominator changed')
    if x['group']=='all' and c['N']!=known[key]['n_valid']:raise ValueError('Archived all population changed')
    return dict(run_id=key,group=x['group'],n_valid=c['N'],n_rain=int(x['N_rain']),
        values={k:num(x[k]) for k in ('Brier','AUROC','AP','conditional_pinball','q32_coverage')},
        counts=c,rates=[num(x[k]) for k in RATE_FIELDS],source_id='TIER0_ARCHIVED_GROUPS')


def historical_proxy(x):
    # These are old BEST weights, not the current campaign's fixed E9 LAST.
    return dict(model=x['model'],seed=int(x['seed']),generation=x['artifact_generation'],population=x['population'],
        mae=num(x['MAE_mm_h']),rmse=num(x['RMSE_mm_h']),bias=num(x['Bias_mm_h']),
        cc=None if x['Pearson_CC']=='NOT_AVAILABLE' else num(x['Pearson_CC']),
        status='HISTORICAL_DIFFERENT_WEIGHT_NOT_MAIN_E9',source_id='TIER0_HISTORICAL_PROXY',eligible_for_main_comparison=False)
def counts(summary):
    bins=summary.get('reliability') or summary.get('reliability_bins') or summary.get('sufficient_statistics',{}).get('reliability_bins')
    if bins is None:return None
    tp=sum(b['rain'] for b in bins[5:]);fp=sum(b['n']-b['rain'] for b in bins[5:]);nr=summary['n_rain'];n=summary['n_valid']
    return dict(TP=tp,FP=fp,FN=nr-tp,TN=n-nr-fp,N=n)


def ratios(x):
    a,b,c,d=(x[k] for k in ('TP','FP','FN','TN'));n=a+b+c+d
    if n!=x['N']:raise ValueError('Contingency denominator changed')
    divide=lambda u,v:u/v if v else None
    return dict(POD=divide(a,a+c),FAR=divide(b,a+b),CSI=divide(a,a+b+c),HSS=divide(2*(a*d-b*c),(a+c)*(c+d)+(a+b)*(b+d)))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--private',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--allow-in-progress',action='store_true');a=p.parse_args()
    v=read(a.private);backfill=Path(v['backfill_directory']);resume=read(v['metric_private']);registry=read(resume['registry']);runmap={x['run_id']:x for x in registry['runs']}
    rows=csvrows(backfill/'outputs/tier0_runs_all.csv');provenance={(x['model'],int(x['seed']),x['arm']):x for x in csvrows(backfill/'outputs/tier0_provenance.csv')};sources=[];classify=[];continuous=[];known={};infer_count=0
    def addsource(sid,path,checkpoint='',commit='',note=''):
        sources.append([sid,sha(path),Path(path).stat().st_size,checkpoint,commit,note])
    def normalize(x):
        model=x['model'];seed=int(x['seed']);arm=x['arm'];key=rid(model,seed,arm)
        return dict(run_id=key,model=model,seed=seed,arm=arm,population=x['population'],scenes=int(float(x['scenes'])),n_valid=int(float(x['N_valid'])),n_rain=int(float(x['N_rain'])),
            brier=num(x['Brier']),auroc=num(x['AUROC']),ap=num(x['AP']),pinball=num(x['conditional_pinball']),coverage=num(x['q32_coverage']),q32_bias=num(x['q32_coverage'])-NOMINAL,q32_error=abs(num(x['q32_coverage'])-NOMINAL),
            checkpoint=x['checkpoint_sha256'],training_commit=('NOT_VERIFIED_HISTORICAL_EXECUTION_BINDING' if model in ('B0','B1') else x['executed_commit']),status='COMPLETE_FIXED_E9_PROBABILITY',source_id='TIER0_'+key)
    for x in rows:
        d=normalize(x);known[d['run_id']]=d
        prov=provenance[(d['model'],d['seed'],d['arm'])]
        sources.append([d['source_id'],prov['artifact_sha256'],int(prov['artifact_bytes']),d['checkpoint'],d['training_commit'],'Inherited Tier0 provenance,not rehashed old observations/weights'])
        classify.append([d['run_id'],d['model'],d['seed'],d['arm'],d['population'],'OCC_P',.1,d['n_valid'],*[int(float(x[k])) for k in ('TP','FP','FN','TN')],d['n_valid'],0,'FULL_POPULATION_EXPLORATORY',d['source_id'],*[num(x[k]) for k in RATE_FIELDS]])
    addsource('TIER0_ARCHIVED_ROWS',backfill/'outputs/tier0_runs_all.csv',note='Original28 rows retained; paths not exported')
    archive_groups=[archived_group(x,known) for x in csvrows(backfill/'outputs/tier0_groups.csv')]
    archive_pairs=csvrows(backfill/'outputs/tier0_pairwise_deltas.csv')
    if any(x['direction']!='new-minus-old' for x in archive_pairs):raise ValueError('Archived pair direction changed')
    archive_proxies=[historical_proxy(x) for x in csvrows(backfill/'outputs/tier0_proxy_continuous.csv')]
    validation=read(backfill/'outputs/tier0_validation.json')
    if validation.get('all_checks_pass') is not True:raise ValueError('Prior Tier0 validation not passed')
    for sid,filename in [('TIER0_ARCHIVED_GROUPS','tier0_groups.csv'),('TIER0_ARCHIVED_PAIRS','tier0_pairwise_deltas.csv'),('TIER0_HISTORICAL_PROXY','tier0_proxy_continuous.csv'),('TIER0_ARCHIVED_VALIDATION','tier0_validation.json'),('TIER0_ARCHIVED_PROVENANCE','tier0_provenance.csv')]:
        addsource(sid,backfill/'outputs'/filename,note='Reuse saved statistics/identity only; no new inference or weight access')
    addsource('UNIFIED_METRICS_SAVED',ROOT/'METRICS.csv',note='Existing full endpoints and diagnostics; no model/raw-source reads')
    control=read(E/'dote_control_three_seed_completion_20261029.json')
    for seed in ('2030','2031'):
        group=control['endpoint_groups'][seed]['B7_ZERO_DOTE']['all'];s=group['summary'];t=next(x for x in control['tasks'] if x['seed']==int(seed));key=rid('B7_ZERO_DOTE',int(seed),'E0')
        h=control['summary']['group_endpoints'][seed]['all']['B7_ZERO_DOTE']
        d=dict(run_id=key,model='B7_ZERO_DOTE',seed=int(seed),arm='E0',population='959/963',scenes=963,n_valid=s['n_valid'],n_rain=s['n_rain'],brier=h['brier'],auroc=h['auroc'],ap=h['average_precision'],pinball=h['conditional_pinball'],coverage=h['q32_coverage'],q32_bias=h['q32_signed_bias'],q32_error=h['q32_absolute_error'],checkpoint=t['fixed_E9_sha256'],training_commit=control['training_commit'],status='COMPLETE_FIXED_E9_PROBABILITY',source_id='ZERO_THREE_SEED_PUBLIC')
        known[key]=d;c=counts(s)
        if c:classify.append([key,d['model'],d['seed'],'E0','959/963','OCC_P',.1,c['N'],*[c[k] for k in ('TP','FP','FN','TN')],c['N'],0,'FULL_POPULATION_EXPLORATORY',d['source_id']])
    addsource('ZERO_THREE_SEED_PUBLIC',E/'dote_control_three_seed_completion_20261029.json')
    perp=Path(v['candidate_closeout'])
    if perp.exists():
        close=read(perp)
        if close['status']!='VERIFIED_COMPLETE_PHYSICAL_CONTROL_TRAIN_AND_DEV':raise ValueError('Candidate not scientifically sealed')
        s=close['endpoint_groups']['B7_PERP_GRADIENT']['all']['summary'];key=rid('B7_PERP_GRADIENT',2029,'E0')
        d=dict(run_id=key,model='B7_PERP_GRADIENT',seed=2029,arm='E0',population='959/963',scenes=963,n_valid=s['n_valid'],n_rain=s['n_rain'],brier=s['brier'],auroc=s['auroc'],ap=s['average_precision'],pinball=s['conditional_pinball'],coverage=s['coverage'][-1],q32_bias=s['coverage'][-1]-NOMINAL,q32_error=abs(s['coverage'][-1]-NOMINAL),checkpoint=close['endpoint_sha256'],training_commit=close['training_commit'],status='COMPLETE_FIXED_E9_EXPLORATORY_DIRECTIONAL_PROBE',source_id='PHYSICAL_CONTROL_PUBLIC')
        known[key]=d;c=counts(s)
        if c:classify.append([key,d['model'],2029,'E0','959/963','OCC_P',.1,c['N'],*[c[k] for k in ('TP','FP','FN','TN')],c['N'],0,'FULL_POPULATION_EXPLORATORY',d['source_id']])
        addsource('PHYSICAL_CONTROL_PUBLIC',perp,d['checkpoint'],d['training_commit'])
    elif not a.allow_in_progress:raise RuntimeError('Candidate closeout missing; do not export a final workbook yet')
    for key,run in runmap.items():
        path=Path(resume['inherited'][key]['result']) if key in resume['inherited'] else Path(resume['new_output_root'])/'runs'/key/'result.json'
        if not path.exists():continue
        x=read(path)
        if x.get('status')!='COMPLETE' or x.get('gate',{}).get('passed') is not True:raise ValueError('No valid frozen-metric gate: '+key)
        d=known[key]
        if x['checkpoint_identity']['sha256_actual']!=d['checkpoint']:raise ValueError('Checkpoint mismatched to table')
        for metric,field in [('brier','brier'),('auroc','auroc'),('average_precision','ap'),('conditional_pinball','pinball'),('q32_coverage','coverage')]:
            if not math.isclose(x['gate']['metrics'][metric]['recomputed'],d[field],abs_tol=1e-12,rel_tol=1e-12):raise ValueError('Frozen value drift: '+key)
        sid='TIER1_'+key;addsource(sid,path,d['checkpoint'],run['executed_commit'],'Forward-only2024; A/B/C NOT_FROZEN; original training binding kept separately')
        n=x['new_metrics'];assert n['N_valid']==d['n_valid'];infer_count+=1
        for item in n['point_estimates']:
            continuous.append([key+'|'+item['candidate'],key,d['model'],d['seed'],d['arm'],d['population'],item['candidate'],item['MAE_mm_h'],item['RMSE_mm_h'],item['MeanBias_mm_h'],item['Pearson_CC'],d['n_valid'],'NOT_FROZEN_EXPLORATORY',sid])
        # OCC_P was retained from Tier0; enforce agreement rather than duplicate.
        for method,block in n['contingency'].items():
            for threshold,c in block['rows'].items():
                if c['N']!=d['n_valid']:raise ValueError('Full-population method shrank supervision')
                for name,value in ratios(c).items():
                    if value is not None and not math.isclose(value,c[name],abs_tol=1e-12):raise ValueError('Formula mismatch')
                if method=='OCC_P':
                    old=next(z for z in classify if z[0]==key and z[5]=='OCC_P');assert [c[k] for k in ('TP','FP','FN','TN')]==old[8:12];continue
                classify.append([key,d['model'],d['seed'],d['arm'],d['population'],method,float(threshold),c['N'],*[c[k] for k in ('TP','FP','FN','TN')],d['n_valid'],0,'FULL_POPULATION_NOT_FROZEN',sid,*[c[k] for k in ('POD','FAR','CSI','HSS')]])
        for threshold,block in n['candidate_D'].items():
            c=block['supported_contingency'];support=block['support'];assert c['N']==support['N_supported'];ratios(c)
            classify.append([key,d['model'],d['seed'],d['arm'],d['population'],'D_PROB_SUPPORTED_ONLY',float(threshold),c['N'],*[c[k] for k in ('TP','FP','FN','TN')],d['n_valid'],support['N_not_established'],'MODEL_SPECIFIC_SUPPORT_NOT_FAIR_PAIRED_COMPARISON' if support['N_not_established'] else 'FULL_POPULATION_NOT_FROZEN',sid,*[c[k] for k in ('POD','FAR','CSI','HSS')]])
    if infer_count!=19 and not a.allow_in_progress:raise RuntimeError('All19 metric runs must finish before final export')
    records=sorted(known.values(),key=lambda d:((0 if d['model'] in ('B0','B1') else 1),d['model'],d['seed'],d['arm']))
    completekeys={r[0] for r in continuous}
    for d in records:
        for method in ('A','B','C'):
            key=d['run_id']+'|'+method
            if key not in completekeys:continuous.append([key,d['run_id'],d['model'],d['seed'],d['arm'],d['population'],method,None,None,None,None,d['n_valid'],'NOT_COMPUTED_IN_CURRENT_19_RUN_SCOPE',d['source_id']])
    # Complete existing raw endpoint/group/quantile diagnostics stay inspectable.
    details=[]
    for row in csvrows(ROOT/'METRICS.csv'):
        if row['record_type'] in ('RAW_ENDPOINT','OFFLINE_DERIVED'):
            details.append([row['experiment_id'],row['model_id'],row['seed'],row['loss_arm'],row['group'],row['metric'],num(row['value']),row['unit'],row['status'],row['source_file'],row['source_pointer']])
    for d in records:
        if d['coverage'] is None or not 0<=d['coverage']<=1:raise ValueError('Invalid q32')
    data=dict(status='COMPLETE_WITH_EXPLICIT_UNCOMPUTED_SUPPLEMENTAL_METHODS' if infer_count==19 and perp.exists() else 'IN_PROGRESS_NOT_FINAL',metric_runs_complete=infer_count,required_metric_runs=19,candidate_closed=perp.exists(),records=records,continuous=continuous,classifications=classify,details=details,sources=sources,
        archive_groups=archive_groups,archive_pairs=archive_pairs,historical_proxies=archive_proxies,
        invariants=dict(old_Tier0_records=28,archived_groups=len(archive_groups),archived_pairs=len(archive_pairs),historical_not_main_proxies=len(archive_proxies),prior_Tier0_validation='INHERITED_PASS_NOT_RERUN',new_ZERO_records=2,candidate_records=int(perp.exists()),optimizer_updates_by_assembler=0,new_inference_by_assembler=0,raw_reads_by_assembler=0,final_2025='FROZEN_NO_ACCESS'),
        notes=['A/B/C are displayed separately, none scientifically frozen; no default selection.',
               'OCC_P columns are probability classification P>=0.5, not point Pred>r; D has model-specific partial support and must not enter fair paired ranking.',
               'ZERO controls and new physical probe lack A/B/C point backfill in the authorized19-run matrix; unavailable fields remain explicit, not zero.',
               'B8 is single-SP04 matched DTFM fusion replacement, not multi-scale proof. B0/B1 population differs from core.',
               'Legacy phase-A proxy metrics are not substituted for final campaign E9. No independent storm or final-year claims.'])
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status=data['status'],metric_runs_complete=infer_count,records=len(records),continuous_rows=len(continuous),classification_rows=len(classify),full_endpoint_detail_rows=len(details),sources=len(sources)),ensure_ascii=False))


if __name__=='__main__':main()
