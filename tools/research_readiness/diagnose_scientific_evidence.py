"""Derive diagnostics from frozen public statistics and six saved Dev metadata sets."""
import argparse,csv,hashlib,io,json,math,re,sqlite3,struct,subprocess,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.research_readiness.scientific_diagnostics import binned_brier,paired_week_bootstrap

BASE='a2ffa75c5ed82d53b47e2dbe271b0eec4f697c22'
PUBLIC=ROOT/'docs/research_readiness/20261025/evidence'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists():raise PermissionError('Immutable diagnostic receipt; never overwrite')
    inputs={};tables={}
    for name in ('METRICS.csv','EXPERIMENT_MATRIX.csv'):
        raw=subprocess.check_output(['git','-C',str(ROOT),'show',BASE+':'+name])
        inputs[name]=dict(commit=BASE,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        tables[name]=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    flat={};pointers={}
    for r in tables['METRICS.csv']:
        if r['record_type']=='RAW_ENDPOINT' and r['group']=='all' and r['status']=='RECORDED':
            flat.setdefault(r['experiment_id'],{})[r['metric']]=float(r['value'])
            pointers.setdefault(r['experiment_id'],{})[r['metric']]=dict(source_file=r['source_file'],source_pointer=r['source_pointer'])
    models={}
    for exp in tables['EXPERIMENT_MATRIX.csv']:
        eid=exp['experiment_id'];a=flat.get(eid,{})
        if exp['epochs']!='9' or 'BEST' in exp['checkpoint_selection'] or 'brier' not in a:continue
        bins=[{k:a.get(f'reliability/{i}/{k}',0) for k in ('n','rain','probability_sum')} for i in range(10)]
        diag=binned_brier(a['n_valid'],a['n_rain'],a['brier'],bins)
        curve=[dict(tau=a[f'tau/{i}'],coverage=a[f'coverage/{i}'],covered=int(a[f'covered/{i}']),
                    signed_bias=a[f'coverage/{i}']-a[f'tau/{i}']) for i in range(32)]
        strata=[]
        for i,lo in enumerate((.1,1,5,10,20,30,50)):
            k=f'rain_strata/{i}'
            strata.append(dict(lower=lo,upper=(1,5,10,20,30,50,None)[i],n_rain=int(a[k+'/n']),
                               conditional_pinball=a[k+'/conditional_pinball'],q32_covered='NOT_AVAILABLE_IN_THIS_AGGREGATE'))
        models[eid]=dict(model=exp['model_id'],seed=int(exp['seed']),loss=exp['loss_arm'],population=exp['comparison_population'],
            training_commit=exp['executed_commit'],checkpoint_sha256=exp['checkpoint_reference'],brier=diag,quantiles=curve,
            q32=dict(coverage=curve[-1]['coverage'],signed_bias=curve[-1]['signed_bias'],absolute_error=abs(curve[-1]['signed_bias']),
            covered=curve[-1]['covered'],n_rain=int(a['n_rain'])),mean_absolute_32_coverage_error=float(np.mean([abs(v['signed_bias']) for v in curve])),
            strata=strata,source_example=pointers[eid]['brier'])
    # Supplement only the q32 rain-stratum sufficient statistics already published.
    tail_sources=[(PUBLIC/'b2_completion_and_paired_evidence.json','B2'),(PUBLIC/'b3_b4_three_seed_completion.json','B34'),
                  (PUBLIC/'b5_b6_completion_and_paired_evidence.json','STATIC'),(PUBLIC/'b8_recovery_completion_20261028.json','2029'),
                  (PUBLIC/'b7_b8_three_seed_completion_20261029.json','NEW')]
    for path,kind in tail_sources:
        x=read(path);inputs[path.name]=dict(sha256=sha(path),bytes=path.stat().st_size)
        if kind=='B2':items=[('B2','2029',x['B2_tail_strata'])]
        elif kind=='B34':items=[(m,s,t) for s,ms in x['tail_diagnostics'].items() for m,t in ms.items()]
        elif kind=='STATIC':items=[(m,'2029',t) for m,t in x['tail_diagnostics'].items()]
        elif kind=='2029':items=[('B8','2029',x['tail_diagnostics']['B8'])]
        else:items=[(m,s,t) for s,ms in x['tail_diagnostics'].items() for m,t in ms.items()]
        for m,seed,t in items:
            eid=f'{m}__E0__s{seed}__f006'+('__static' if m in ('B5','B6') else '__dynamic' if m in ('B7','B8') else '')
            if eid not in models:continue
            strata=t.get('strata',[]) if isinstance(t,dict) else t
            for row in strata:
                if 'q32_covered' not in row:continue
                j=next((z for z in models[eid]['strata'] if z['lower']==row['lower']),None)
                if j is not None:
                    assert j['n_rain']==row['n_rain']
                    j.update(q32_covered=row['q32_covered'],q32_coverage=row['q32_coverage'])
    b7_old=read(PUBLIC/'b7_b8_terminal_20261028.json')
    for j,row in zip(models['B7__E0__s2029__f006__dynamic']['strata'],b7_old['tail_diagnostics']['B7']['strata']):
        j.update(q32_covered=row['q32_covered'],q32_coverage=row['q32_coverage'])
    # Six local E9 metadata sets expose saved week blocks and exact score counts.
    private=read(ROOT/'docs/research_readiness/.local/b7_b8_multiseed_preparation_20261028.json')
    recovery=read(ROOT/'docs/research_readiness/.local/b7_b8_multiseed_recovery_preparation_20261028.json')
    completed=read(PUBLIC/'b7_b8_three_seed_completion_20261029.json');old=read(PUBLIC/'b8_recovery_completion_20261028.json')
    arms={};local_sources={};scene_ids=None;strong_ids=None;week_ids=None
    for seed in ('2029','2030','2031'):
        arms[seed]={}
        for model in ('B7','B8'):
            folder=Path(private['historical_'+model]) if seed=='2029' else Path(recovery['output_root'])/f'{model}_s{seed}'
            f=folder/f'{model}_development_09.json';report=read(f);g=report['groups']['all']
            expected=(b7_old['sources']['B7/development_09.json'] if model=='B7' else old['sources']['RECOVERY_B8/development_09.json']) if seed=='2029' else completed['sources'][f'{model}_s{seed}/development_09.json']
            assert sha(f)==expected['sha256'] and g['summary']['n_valid']==3303090
            ids=[s for s,b in g['scene_blocks']];blocks=[b for s,b in g['scene_blocks']]
            strong=[s for s,b in report['groups']['scene_max_ge20']['scene_blocks']]
            if scene_ids is None:scene_ids,strong_ids,week_ids=ids,strong,blocks
            assert (ids,strong,blocks)==(scene_ids,strong_ids,week_ids) and len(ids)==963
            for hour in (0,6,12,18):
                for sid,block in report['groups'][f'analysis_UTC_{hour:02d}']['scene_blocks']:
                    t=datetime.fromisoformat(sid)+timedelta(minutes=30)
                    assert t.year==2024 and t.hour==hour and t.minute==0
            db=folder/f'{model}_evaluation_09/all.sqlite'
            con=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)
            try:rows=con.execute('SELECT block,score,pos,neg FROM scores ORDER BY block,score').fetchall()
            finally:con.close()
            h=hashlib.sha256()
            for block,score,pos,neg in rows:h.update(struct.pack('>i',block)+score+struct.pack('>QQ',pos,neg))
            assert h.hexdigest()==g['exact_score_table_sha256']
            scores=sorted({score for block,score,pos,neg in rows if block>=0},reverse=True);index={s:i for i,s in enumerate(scores)}
            pos=np.zeros((35,len(scores)));neg=np.zeros_like(pos)
            for block,score,pn,nn in rows:
                if block>=0:pos[block,index[score]]=pn;neg[block,index[score]]=nn
            arms[seed][model]=dict(blocks=g['blocks'],pos=pos,neg=neg)
            local_sources[f'{model}_s{seed}']=dict(dev_json_sha256=sha(f),dev_json_bytes=f.stat().st_size,
                exact_score_table_sha256=g['exact_score_table_sha256'],score_sqlite_sha256=sha(db),score_sqlite_bytes=db.stat().st_size,
                scene_ids_sha256=canonical(ids),grid='INHERITED_SP04_100x100_SAME_SUPERVISION_3430',visibility='LOCAL_ONLY')
    bootstrap=paired_week_bootstrap(arms)
    for key,v in bootstrap['metrics'].items():assert math.isclose(v['point_estimate'],completed['summary']['metrics'][key]['mean'],abs_tol=1e-12)
    times=[datetime.fromisoformat(s)+timedelta(minutes=30) for s in scene_ids]
    gaps={str(h):sum((b-a).total_seconds()==h*3600 for a,b in zip(times,times[1:])) for h in (6,12,18,24)}
    result=dict(status='COMPLETE_EXISTING_EVIDENCE_DIAGNOSTICS_WITH_LIMITATIONS',created_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        source_commit=BASE,inputs=inputs,models=models,temporal_block_bootstrap=bootstrap,local_metadata_sources=local_sources,
        event_evidence=dict(scenes=963,strong_scene_count=len(strong_ids),scene_ids_sha256=canonical(scene_ids),
          UTC_analysis_hours=[0,6,12,18],time_rule='scene_id is IMERG window start T; analysis=T+30min',
          sampling_gaps_hours=gaps,week_blocks=35,nonempty_week_blocks=len(set(week_ids)),
          week_rule='Inherited 7-day blocks since2024-03-01UTC; no model-dependent threshold',
          event_ids='NOT_AVAILABLE',spatial_storm_components='NOT_AVAILABLE',storm_independence='NOT_VERIFIED',
          per_scene_pinball_q32='AVAILABLE_IN_SAVED_TAIL_METADATA',per_scene_Brier='NOT_IN_TAIL; AVAILABLE_ONLY_WEEKLY_SUMS_HERE',
          additional_raw_or_inference_required_for_week_analysis=False,
          new_strata_joint_errors='NOT_AVAILABLE_FOR_SLOPE_WINDWARD_PRESSURE_PWAT; joint pixel predictions/masks needed'),
        activity=dict(new_optimizer_updates=0,model_inference=0,checkpoint_payload_reads=0,raw_weather_reads=0,normalization_refits=0,
                      saved_Dev_json_files=6,saved_score_sqlite_files=6,final_2025='FROZEN_NO_ACCESS'),
        diagnostic_code_sha256={str(Path(__file__).relative_to(ROOT)).replace('\\','/'):sha(Path(__file__)),
            'src/yuntapr/experimental/research_readiness/scientific_diagnostics.py':sha(ROOT/'src/yuntapr/experimental/research_readiness/scientific_diagnostics.py')})
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    assert not re.search(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/Users/|/home/',text)
    with args.output.open('x',encoding='utf-8') as f:f.write(text)
    print(json.dumps(dict(status=result['status'],fixed_E9_experiments=len(models),temporal_bootstrap=bootstrap,event_evidence=result['event_evidence']),ensure_ascii=False))


if __name__=='__main__':main()
