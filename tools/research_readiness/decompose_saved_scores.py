"""Exact empirical Brier decomposition from already saved native-score counts."""
import argparse,bisect,hashlib,json,math,sqlite3,struct
from pathlib import Path
from datetime import datetime,timedelta,timezone

ROOT=Path(__file__).resolve().parents[2];E=ROOT/'docs/research_readiness/20261025/evidence'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise PermissionError('Do not overwrite a receipt')
    d=read(E/'scientific_attribution_diagnostics_20261029.json')
    old=read(ROOT/'docs/research_readiness/.local/b7_b8_multiseed_preparation_20261028.json')
    new=read(ROOT/'docs/research_readiness/.local/b7_b8_multiseed_recovery_preparation_20261028.json')
    results={}
    for seed in ('2029','2030','2031'):
        results[seed]={}
        for m in ('B7','B8'):
            folder=Path(old['historical_'+m]) if seed=='2029' else Path(new['output_root'])/f'{m}_s{seed}'
            db=folder/f'{m}_evaluation_09/all.sqlite';con=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)
            try:rows=con.execute('SELECT score,pos,neg FROM scores WHERE block=-1 ORDER BY score').fetchall()
            finally:con.close()
            total=sum(p+n for s,p,n in rows);rain=sum(p for s,p,n in rows);clim=rain/total
            rel=res=bs=p2=py=0.;bins=[[0,0,0.,0.,0.] for _ in range(10)]
            for raw,pn,nn in rows:
                score=struct.unpack('>d',raw)[0];n=pn+nn;freq=pn/n;w=n/total
                rel+=w*(score-freq)**2;res+=w*(freq-clim)**2
                bs+=(nn*score**2+pn*(1-score)**2)/total;p2+=n*score**2/total;py+=pn*score/total
                b=bins[bisect.bisect_right([i/10 for i in range(1,10)],score)]
                for i,v in enumerate((n,pn,n*score,n*score**2,pn*score)):b[i]+=v
            unc=clim*(1-clim);within_var=p2-sum(b[2]**2/b[0]/total for b in bins if b[0])
            within_cov=py-sum(b[2]*b[1]/b[0]/total for b in bins if b[0])
            original=d['models'][f'{m}__E0__s{seed}__f006__dynamic']['brier']
            assert total==3303090 and rain==407820
            assert math.isclose(bs,original['original_brier'],abs_tol=1e-12) and math.isclose(bs,rel-res+unc,abs_tol=1e-12)
            assert math.isclose(within_var-2*within_cov,original['binning_residual'],abs_tol=1e-12)
            results[seed][m]=dict(n_valid=total,n_rain=rain,unique_native_scores=len(rows),brier=bs,empirical_score_reliability=rel,
                empirical_score_resolution=res,uncertainty=unc,identity_residual=bs-(rel-res+unc),
                within_bin_probability_variance=within_var,within_bin_probability_outcome_covariance=within_cov,
                binned_residual_reconstructed=within_var-2*within_cov,min_score_group_count=min(p+n for s,p,n in rows),
                score_groups_n_lt20=sum(p+n<20 for s,p,n in rows),
                inherited_exact_score_table_sha256=d['local_metadata_sources'][f'{m}_s{seed}']['exact_score_table_sha256'])
    deltas={s:{k:models['B8'][k]-models['B7'][k] for k in ('brier','empirical_score_reliability','empirical_score_resolution','uncertainty')} for s,models in results.items()}
    result=dict(status='PASS_EXACT_EMPIRICAL_NATIVE_SCORE_BRIER_DECOMPOSITION',created_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        source_diagnostic_sha256=hashlib.sha256((E/'scientific_attribution_diagnostics_20261029.json').read_bytes()).hexdigest(),models=results,B8_minus_B7=deltas,
        identity='Original BS = empirical score REL - empirical score RES + UNC; native exact sigmoid score groups, no coarse bin approximation',
        limitations='Empirical finite-sample groups, many sparse scores; not population conditional calibration, causal mechanism or independent-event inference',
        activity=dict(saved_score_sqlite_reads=6,query='block=-1 score counts only',raw_weather_reads=0,checkpoint_reads=0,new_inference=0,new_training=0,final_2025='FROZEN_NO_ACCESS'),
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(dict(status=result['status'],differences=deltas),ensure_ascii=False))


if __name__=='__main__':main()
