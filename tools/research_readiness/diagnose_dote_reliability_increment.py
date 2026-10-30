"""Only three new ZERO_DOTE score tables; inherit all completed B7/B8 results."""
import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import struct
import sys
from datetime import datetime,timedelta,timezone

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
E=ROOT/'docs/research_readiness/20261025/evidence'


def exact_counts(rows):
    n=sum(p+q for _,p,q in rows);nr=sum(p for _,p,q in rows)
    if n<=0 or not 0<nr<n:raise ValueError('Nonempty two-class population required')
    climatology=nr/n;rel=res=bs=p2=py=0.;bins=[[0,0,0.] for _ in range(10)]
    for probability,p,q in rows:
        count=p+q
        if not 0<=probability<=1 or min(p,q)<0 or count<=0:raise ValueError('Invalid native score count')
        w=count/n;frequency=p/count
        rel+=w*(probability-frequency)**2;res+=w*(frequency-climatology)**2
        bs+=(q*probability**2+p*(1-probability)**2)/n;p2+=count*probability**2/n;py+=p*probability/n
        b=bins[bisect.bisect_right([i/10 for i in range(1,10)],probability)]
        for k,v in enumerate((count,p,count*probability)):b[k]+=v
    uncertainty=climatology*(1-climatology)
    if not math.isclose(bs,rel-res+uncertainty,abs_tol=1e-12):raise ValueError('Exact empirical identity failed')
    return dict(n_valid=n,n_rain=nr,unique_native_scores=len(rows),brier=bs,empirical_score_reliability=rel,
                empirical_score_resolution=res,uncertainty=uncertainty,identity_residual=bs-(rel-res+uncertainty),
                within_bin_probability_variance=p2-sum(b[2]**2/b[0]/n for b in bins if b[0]),
                within_bin_probability_outcome_covariance=py-sum(b[2]*b[1]/b[0]/n for b in bins if b[0]),
                min_score_group_count=min(p+q for _,p,q in rows),score_groups_n_lt20=sum(p+q<20 for _,p,q in rows),
                reliability_bins=[dict(n=b[0],rain=b[1],probability_sum=b[2]) for b in bins])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    assert not a.output.exists(),'Never overwrite an analysis receipt'
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    from yuntapr.experimental.research_readiness.scientific_diagnostics import binned_brier
    real_file=E/'brier_exact_score_decomposition_20261029.json';real=read(real_file)
    control_file=E/'dote_control_three_seed_completion_20261029.json';complete=read(control_file)
    zero2029=read(ROOT/'docs/research_readiness/.local/dote_control_preparation_20261029.json')
    zero_new=read(ROOT/'docs/research_readiness/.local/dote_control_multiseed_preparation_20261029.json')
    models={};sources={}
    for seed in ('2029','2030','2031'):
        folder=Path(zero2029['output_root'] if seed=='2029' else zero_new['output_root'])/f'B7_s{seed}'
        db=folder/'B7_evaluation_09/all.sqlite';con=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)
        try:records=con.execute('SELECT block,score,pos,neg FROM scores ORDER BY block,score').fetchall()
        finally:con.close()
        h=hashlib.sha256()
        for block,score,p,q in records:h.update(struct.pack('>i',block)+score+struct.pack('>QQ',p,q))
        group=complete['endpoint_groups'][seed]['B7_ZERO_DOTE']['all'];assert h.hexdigest()==group['exact_score_table_sha256']
        rows=[(struct.unpack('>d',score)[0],p,q) for block,score,p,q in records if block==-1]
        exact=exact_counts(rows);summary=group['summary']
        assert (exact['n_valid'],exact['n_rain'])==(3303090,407820)
        assert math.isclose(exact['brier'],summary['brier'],abs_tol=1e-12)
        bins=binned_brier(exact['n_valid'],exact['n_rain'],summary['brier'],exact['reliability_bins'])
        assert math.isclose(bins['binning_residual'],exact['within_bin_probability_variance']-2*exact['within_bin_probability_outcome_covariance'],abs_tol=1e-12)
        inherited=real['models'][seed]['B7'];assert math.isclose(inherited['brier'],complete['summary']['group_endpoints'][seed]['all']['B7']['brier'],abs_tol=1e-12)
        models[seed]=dict(B7=inherited,B7_ZERO_DOTE=dict(exact,coarse_bin_diagnostic=bins))
        sources[f'ZERO_DOTE_s{seed}']=dict(exact_score_table_sha256=h.hexdigest(),score_sqlite_bytes=db.stat().st_size,
            score_sqlite_sha256=hashlib.sha256(db.read_bytes()).hexdigest(),scope='LOCAL_ONLY_SAVED_2024_COUNTS_NOT_PREDICTION_PAYLOAD')
    keys=('brier','empirical_score_reliability','empirical_score_resolution','uncertainty')
    deltas={s:{k:a['B7'][k]-a['B7_ZERO_DOTE'][k] for k in keys} for s,a in models.items()}
    for s,d in deltas.items():assert math.isclose(d['brier'],d['empirical_score_reliability']-d['empirical_score_resolution']+d['uncertainty'],abs_tol=1e-12)
    result=dict(status='PASS_INCREMENTAL_ZERO_DOTE_THREE_SEED_EXACT_BRIER',created_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        inherited_B7_B8_exact_decomposition_sha256=hashlib.sha256(real_file.read_bytes()).hexdigest(),dote_three_seed_completion_sha256=hashlib.sha256(control_file.read_bytes()).hexdigest(),
        coverage_before='RealB7/B8 all3 seeds complete;ZERO_DOTE all3 missing from previous exact decomposition',models=models,real_B7_minus_ZERO_DOTE=deltas,
        sufficient_statistics='Native exact probability score and positive/negative counts; logical table digest checked; empirical REL-RES+UNC exact',
        limitations=['Finite-sample empirical calibration, sparse score groups; not population reliability or causal evidence',
                    'Exact-score group resolution is not AUROC/AP or a clean causal mechanism',
                    'No independent storm IDs; inherited35-week B7/B8 intervals are not ZERO_DOTE intervals or independent-event tests'],
        sources=sources,activity=dict(new_saved_score_tables=3,inherited_B7_tables_recomputed=0,new_inference=0,checkpoint_reads=0,raw_weather_reads=0,new_training=0,final_2025='FROZEN_NO_ACCESS'),
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    a.output.write_text(text,encoding='utf-8')
    print(json.dumps(dict(status=result['status'],differences=deltas,score_sqlite_bytes=sum(x['score_sqlite_bytes'] for x in sources.values())),ensure_ascii=False))


if __name__=='__main__':main()
