"""Reaggregate saved Development endpoints. No model, training or raw-data imports."""
import argparse
import hashlib
import io
import json
import math
import statistics
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT.parent
OLD = HOME / 'YunTAPR-B2-readiness-20261025'
LOCAL = OLD / 'docs/research_readiness/.local'
JOINT = LOCAL / 'extreme_diagnostic_execution_20261031_v3'
THRESHOLDS = (.1, 1., 5., 10., 20.)
COLORS = ['EAF2F8', 'FCEFE8', 'EAF4E8', 'F4ECF7', 'FFF4D6',
          'E2F0ED', 'F7E6EC', 'E8EDF8', 'EDE8F5', 'F1F1F1']
NAMES = ['单通道单时次反演', '单通道六时次反演', '七通道单时次反演',
         '七通道六时次反演', '七通道六时次融合 GFS 环境场', 'GFS 环境场融合 DEM 高程',
         'GFS 环境场融合完整静态地形特征', '完整静态地形融合 DOTE 动态地形特征（简单拼接）',
         'DOTE 动态地形融合 DTFM 多尺度条件调制', '策略九融合 ERA5 教师—学生知识蒸馏（可选，暂缓）']
LABELS = ['策略一','策略二','策略三','策略四','策略五','策略六','策略七','策略八','策略九','策略十']


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8', newline='\n')


def rates(c):
    a,b,c,d = (int(c[k]) for k in ('TP','FP','FN','TN'))
    div = lambda x,y: x/y if y else None
    return dict(POD=div(a,a+c), FAR=div(b,a+b), CSI=div(a,a+b+c),
                HSS=div(2*(a*d-b*c),(a+b)*(b+d)+(a+c)*(c+d)))


def stats(values):
    valid = [x for x in values if x is not None]
    # Never report a mean over only the defined seeds as if all seeds were defined.
    if len(valid) != len(values) or not valid:
        return dict(mean=None, sd=None, defined=len(valid), total=len(values))
    return dict(mean=statistics.mean(valid),
                sd=statistics.stdev(valid) if len(valid)>1 else None,
                defined=len(valid), total=len(values))


def self_test():
    c = dict(TP=3, FP=2, FN=1, TN=4)
    r = rates(c)
    assert r['POD']==.75 and r['FAR']==.4 and r['CSI']==.5
    assert math.isclose(r['HSS'], 2*(12-2)/(5*6+4*5))
    assert rates(dict(TP=0,FP=0,FN=0,TN=10))['HSS'] is None
    assert rates(dict(TP=0,FP=0,FN=1,TN=10))['FAR'] is None
    assert stats([1])['sd'] is None
    assert stats([0,None])['mean'] is None
    assert stats([1,3])['sd']==math.sqrt(2)
    assert [h<1000 for h in (999,1000,2000,2001)]==[True,False,False,False]
    assert [1000<=h<=2000 for h in (999,1000,2000,2001)]==[False,True,True,False]
    print('PASS: formulas, undefined denominators, sample SD, missing seeds, elevation boundaries')


def audit(out):
    snapshot_path = LOCAL / 'complete_metrics_final_20261031.json'
    snapshot = read(snapshot_path)
    assert snapshot['metric_runs_complete']==snapshot['required_metric_runs']==19
    private = read(LOCAL / 'metric_b01_correction_preparation_20261030_v1/private.json')
    registry_path = Path(private['registry'])
    registry = read(registry_path)
    assert sha(registry_path)==private['registry_sha256']
    known = {r['run_id']:r for r in snapshot['records']}
    runs=[]; sources=[]; core_read_bytes=0; core_read_instances=0
    for reg in registry['runs']:
        rid=reg['run_id']; model=reg['model']; index=int(model[1:])
        rec=known[rid]
        if rid in private['inherited']:
            p=Path(private['inherited'][rid]['result'])
            assert sha(p)==private['inherited'][rid]['sha256']
        else:
            p=Path(private['new_output_root'])/'runs'/rid/'result.json'
        d=read(p)
        assert d['run_id']==rid and d['status']=='COMPLETE' and d['gate']['passed'] is True
        assert d['checkpoint_identity']['expected_sha256']==reg['checkpoint_sha256']==rec['checkpoint']
        n=d['new_metrics']['N_valid']
        assert n==rec['n_valid'] and d['new_metrics']['N_rain']==rec['n_rain']
        brier=d['recomputed_frozen_metrics']['summary']['brier']
        assert abs(brier-rec['brier'])<1e-12
        point=next(x for x in d['new_metrics']['point_estimates'] if x['candidate']=='A')
        if index>=2:
            meter=d['read_scope_actual']['meter_totals']
            core_read_bytes+=meter['delivered_bytes'];core_read_instances+=meter['opened_files']
        classification=d['new_metrics']['contingency']['A']['rows']
        cs={}
        for threshold in THRESHOLDS:
            c=classification[str(threshold)]
            assert sum(c[k] for k in ('TP','FP','FN','TN'))==n
            calc=rates(c)
            for k,v in calc.items():
                assert (c[k] is None and v is None) or math.isclose(c[k],v,rel_tol=1e-12,abs_tol=1e-12)
            cs[str(threshold)]={k:int(c[k]) for k in ('TP','FP','FN','TN')}
        cp=Path(reg['checkpoint_path'])
        runs.append(dict(run_id=rid,strategy=index,strategy_name=LABELS[index],seed=reg['seed'],
                         n_valid=n,n_rain=rec['n_rain'],train=reg['population_detail']['train'],
                         dev=reg['population_detail']['dev'],protocol='历史单通道开发集' if index<2 else '四起报时次开发集',
                         brier=brier,rmse=point['RMSE_mm_h'],counts=cs,
                         checkpoint_sha256=reg['checkpoint_sha256'],checkpoint_file=cp.name,
                         checkpoint_present=cp.is_file(),checkpoint_bytes=cp.stat().st_size if cp.is_file() else None,
                         checkpoint_expected_bytes=reg['checkpoint_bytes'],training_commit=rec['training_commit'],
                         result_sha256=sha(p),result_source='SAVED_METRIC_'+rid,
                         evaluation_code_sha256=registry['scope']['b01_evaluator' if index<2 else 'evaluation_script']['sha256'],
                         population_detail=reg['population_detail'],elapsed_seconds=d['elapsed_seconds']))
        sources.append(dict(id='SAVED_METRIC_'+rid,path=str(p),sha256=sha(p),bytes=p.stat().st_size))
    pop_path=Path(read(LOCAL/'b2_preparation_20261025_v4.json')['prepared']['private_inputs']['stage3_run'])/'populations.json'
    pop=read(pop_path); ids=pop['populations']['Development']['accepted_ids']
    assert len(ids)==len(set(ids))==963 and all(x.startswith('2024-') for x in ids)
    assert sha(pop_path)==registry['runs'][4]['population_detail']['populations_sha256']
    # IDs are half-hour window starts; both pre- and post-shift UTC dates are audited.
    by_date=Counter(datetime.fromisoformat(x).date().isoformat() for x in ids)
    full=[day for day,n in by_date.items() if n==48]
    assert max(by_date.values())<=4 and not full
    missing=[]
    start=datetime(2024,3,1,tzinfo=timezone.utc)
    stop=datetime(2024,11,1,tzinfo=timezone.utc)
    have=set(datetime.fromisoformat(x) for x in ids)
    while start<stop:
        windows=[start+timedelta(minutes=30*k) for k in range(48)]
        for w in windows:
            if w not in have: missing.append(w.isoformat())
        start+=timedelta(days=1)
    assert 245*48-963==len(missing)
    save(out/'missing_daily_windows_internal.json',dict(scope='2024 Development calendar; eligibility not approved',
         unit='half-hour window start UTC',missing_windows=missing))
    joint=[]
    for p in sorted(JOINT.glob('*/joint/joint_summary.json')):
        d=read(p); rid=p.parent.parent.name
        assert d['status'].startswith('COMPLETE') and d['scenes']==963 and d['n_valid']==3303090
        for chunk in d['chunks']:
            f=p.parent/chunk['filename']; assert f.stat().st_size==chunk['bytes']
        joint.append(dict(run_id=rid,source=str(p),sha256=sha(p),chunks=len(d['chunks']),
                          bytes=sum(c['bytes'] for c in d['chunks'])))
    assert len(joint)==9
    grouped=[]
    for i in range(9):
        rr=sorted([r for r in runs if r['strategy']==i],key=lambda r:r['seed'])
        assert rr
        grouped.append(dict(strategy=i,name=LABELS[i],full_name=NAMES[i],color=COLORS[i],seeds=[r['seed'] for r in rr],
                            protocol=rr[0]['protocol'],train=rr[0]['train'],dev=rr[0]['dev'],n_valid=rr[0]['n_valid'],
                            rmse=stats([r['rmse'] for r in rr]),brier=stats([r['brier'] for r in rr]),
                            metrics={str(t):{k:stats([rates(r['counts'][str(t)])[k] for r in rr])
                                            for k in ('POD','FAR','CSI','HSS')} for t in THRESHOLDS}))
    result=dict(status='AUDITED_SAVED_ENDPOINTS_NO_NEW_INFERENCE',as_of='2026-11-05 Asia/Shanghai',
        point_rule='RESEARCHER_CONFIRMED_20261105_A_PHYSICAL_QUANTILE_MEAN_APPROXIMATION',
        day_boundary='北京时间08:00—次日08:00（对应UTC 00:00—24:00）',
        original_snapshot_sha256=sha(snapshot_path),registry_sha256=sha(registry_path),runs=runs,groups=grouped,
        daily=dict(calendar_dates=245,present_dates=len(by_date),present_windows=len(ids),full_dates=full,
                   max_windows_per_date=max(by_date.values()),missing_windows=len(missing),
                   hours_utc=dict(Counter(x[11:16] for x in ids)),
                   no_zero_fill=True,new_protocol_needed='Non-analysis-hour GFS alignment and common eligible complete days',
                   provisional_core_estimate=dict(new_scene_forwards=len(missing)*15,
                     linear_wall_hours=sum(r['elapsed_seconds'] for r in runs if r['strategy']>=2)*len(missing)/963/3600,
                     linear_source_bytes=core_read_bytes*len(missing)/963,
                     linear_source_instances=core_read_instances*len(missing)/963,
                     basis='Linear scaling of 15 saved passes; excludes B0/B1, labels, new eligibility checks; NOT_AN_EXECUTABLE_BUDGET')),
        terrain_saved=joint,terrain_budget=dict(saved_prediction_bytes=sum(x['bytes'] for x in joint),
        files=sum(x['chunks'] for x in joint),max_seconds=600,max_additional_ram_bytes=536870912,
        gpu_inference=0,checkpoint_loads=0,raw_observation_reads=0,retries=0),
        new_training=0,new_inference=0,final_2025='FROZEN_NO_ACCESS',
        source_gaps=['科研原则.txt：已查本轮附件、Downloads、Desktop、OneDrive及科研工作区，未找到原件',
        '指定20261029导师汇报文件未找到；采用可用20261029 Tier0工作簿作格式参考、20261031核验收据作数值来源',
        '策略一、二旧检查点及原评价报告位于当前不可用H盘；只继承已保存且通过一致性门槛的结果',
        '策略一、二与策略三至九样本人口不同，禁止直接作严格配对归因',
        '现有W/L/M未找到训练集冻结分位数阈值，不用开发集拟合阈值',
        '当前策略九是单SP04条件调制实现，策略名中的多尺度不代表已有多尺度证据'],
        internal_sources=sources)
    save(out/'evaluation_data_internal.json',result)
    public={k:v for k,v in result.items() if k not in ('internal_sources','terrain_saved')}
    save(out/'evaluation_receipt_public.json',public)
    print(json.dumps(dict(status=result['status'],runs=len(runs),strategies=len(grouped),
        full_daily_dates=0,missing_daily_windows=len(missing),terrain_budget=result['terrain_budget']),ensure_ascii=False))


def terrain(out, approval):
    if not approval:
        raise PermissionError('Saved-array bulk reaggregation requires this task researcher approval')
    if (out/'terrain_reaggregation_internal.json').exists():
        raise PermissionError('This once-only reaggregation is already complete; never replay')
    with (out/'terrain_once_claim_internal.json').open('x',encoding='utf-8') as claim:
        json.dump(dict(approval=approval,retries=0),claim)
    import numpy as np
    data=read(out/'evaluation_data_internal.json'); clock=time.monotonic(); used=0; rows=[]
    # One archive read per chunk, with hash verification from the same in-memory bytes.
    # No meteorological sources, checkpoint files or GPU runtime are touched.
    for source in data['terrain_saved']:
        rid=source['run_id']; summary_path=Path(source['source']); summary=read(summary_path)
        rr=next(r for r in data['runs'] if r['run_id']==rid)
        accum={g:dict(n=0,squared_sum=0.,counts={str(t):dict(TP=0,FP=0,FN=0,TN=0) for t in THRESHOLDS})
               for g in ('all','low','middle','high')}
        seen=set(); boundary=Counter()
        for c in summary['chunks']:
            assert time.monotonic()-clock < 600, 'CPU time cap reached; stop without replay'
            p=summary_path.parent/c['filename']; b=p.read_bytes(); used+=len(b)
            assert used<=data['terrain_budget']['saved_prediction_bytes']
            assert hashlib.sha256(b).hexdigest()==c['sha256'], 'Saved chunk changed'
            with np.load(io.BytesIO(b),allow_pickle=False) as z:
                y=z['rate'].astype(np.float64).reshape(-1)
                prob=z['occurrence_probability'].astype(np.float64).reshape(-1)
                q=z['conditional_quantiles_log'].astype(np.float64).reshape(-1,32)
                elevation=z['elevation_m'].reshape(-1)
                scene_ids=z['scene_id'].astype(str).tolist()
                assert all(x.startswith('2024-') for x in scene_ids)
                assert not seen.intersection(scene_ids); seen.update(scene_ids)
                assert np.isfinite(q).all() and np.isfinite(y).all() and np.isfinite(elevation).all()
                point=prob*np.expm1(q).mean(axis=1)
                boundary['H=1000']+=int((elevation==1000).sum())
                boundary['H=2000']+=int((elevation==2000).sum())
                masks=dict(all=np.ones(y.shape,dtype=bool),low=elevation<1000,
                           middle=(elevation>=1000)&(elevation<=2000),high=elevation>2000)
                assert sum(int(m.sum()) for g,m in masks.items() if g!='all')==len(y)
                for group,m in masks.items():
                    a=accum[group]; a['n']+=int(m.sum()); err=point[m]-y[m]
                    a['squared_sum']+=float(np.dot(err,err))
                    for t in THRESHOLDS:
                        truth=y[m].astype(np.float32)>np.float32(t); pred=point[m]>t
                        ct=a['counts'][str(t)]
                        for k,v in dict(TP=np.count_nonzero(pred&truth),FP=np.count_nonzero(pred&~truth),
                                        FN=np.count_nonzero(~pred&truth),TN=np.count_nonzero(~pred&~truth)).items():ct[k]+=int(v)
        assert len(seen)==963
        assert accum['all']['n']==rr['n_valid']
        assert math.isclose(math.sqrt(accum['all']['squared_sum']/rr['n_valid']),rr['rmse'],abs_tol=1e-12,rel_tol=1e-12)
        for t in THRESHOLDS: assert accum['all']['counts'][str(t)]==rr['counts'][str(t)]
        for group in ('low','middle','high'):
            a=accum[group]; rmse=math.sqrt(a['squared_sum']/a['n'])
            for t in THRESHOLDS:
                ct=a['counts'][str(t)]; assert sum(ct.values())==a['n']
                rows.append(dict(run_id=rid,strategy=rr['strategy'],seed=rr['seed'],group=group,n=a['n'],
                                 threshold=t,rmse=rmse,counts=ct,metrics=rates(ct)))
        print(json.dumps(dict(complete=rid,n=rr['n_valid'],boundaries=dict(boundary)),ensure_ascii=False),flush=True)
    assert used==data['terrain_budget']['saved_prediction_bytes']
    save(out/'terrain_reaggregation_internal.json',dict(status='PASS',rows=rows,actual_bytes=used,
         actual_seconds=time.monotonic()-clock,models=9,scenes_per_model=963,
         no_new_inference=True,no_raw_data=True,approval=approval))


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('self-test','audit','terrain'))
    p.add_argument('--output',type=Path);p.add_argument('--approval')
    a=p.parse_args()
    if a.mode=='self-test': self_test()
    elif a.mode=='audit':audit(a.output)
    else:terrain(a.output,a.approval)


if __name__=='__main__':main()
