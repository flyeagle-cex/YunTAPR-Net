"""Audit/index existing aggregates. No raw data, model or checkpoint loading.

Publication uses a fixed allowlist; this tool neither stages Git nor signs any
scientific decision. Existing result files and historical ledgers are read only.
"""
from __future__ import annotations
import csv
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import subprocess

ROOT=Path(__file__).absolute().parents[1]
BASE=ROOT/'docs/phase_b_v2_formal_execution'
OUT=BASE/'seed2026_operator_v3'
RUNS=(('seed2026_v2','B0_MATCHED_V2__E0__s2026'),('seed2026_v2','B1_V2__E0__s2026'),
      ('seed2026_v2','B0_MATCHED_V2__E1__s2026'),('seed2026_operator_v3','B1_V2__E1__s2026'),
      ('seed2026_operator_v3','B0_MATCHED_V2__E2__s2026'),('seed2026_operator_v3','B1_V2__E2__s2026'))


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def read_json(path):
    raw=path.read_bytes()
    if re.search(rb'[A-Za-z]:[\\/]|/Users/|/home/|\\\\[^\\\s]+\\',raw):
        raise ValueError('PRIVATE_ABSOLUTE_PATH: '+path.name)
    def reject(value):raise ValueError('NONFINITE_JSON: '+value)
    return json.loads(raw,parse_constant=reject)


def write_json(path,value):
    if path.exists():raise FileExistsError('AUDIT_ALREADY_EXISTS: '+path.name)
    path.write_bytes((json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())


def require(ok,code):
    if not ok:raise ValueError(code)


def main():
    status=read_json(OUT/'execution_status.json');release=read_json(OUT/'release.json');quota=status['quota']
    require(status['status']=='SIX_RUNS_COMPLETE','SIX_RUNS_NOT_COMPLETE')
    require(quota['reserved']==quota['returned_verified']==quota['limit']==298474,'ATTEMPTS_INCOMPLETE')
    require(quota['abandoned_old_updates']==16162 and 6*47052+16162==298474,'REPLAY_ACCOUNTING')
    for relative,expected in release['source_pins'].items():
        require(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected,'TRAINING_SOURCE_CHANGED')
    db=ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v3.sqlite'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as con:
        con.execute('PRAGMA query_only=ON');con.execute('BEGIN')
        require(con.execute('SELECT status FROM campaign').fetchone()==('COMPLETE',),'CAMPAIGN_NOT_COMPLETE')
        session=con.execute('SELECT n,status FROM sessions ORDER BY n DESC LIMIT 1').fetchone()
        require(dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status'))=={'RETURNED_VERIFIED':104560},'NEW_QUOTA_UNCERTAINTY')
    term=read_json(OUT/'.local/sessions'/f'session_{session[0]:04d}'/'termination.json')
    require(term['status']=='COMPLETE' and term['job_empty_and_handles_signaled'] and term['failure'] is None,'JOB_COMPLETION_NOT_VERIFIED')
    publish=[];table=[];checkpoints=[];metrics={};train_ids={};dev_ids=set();validated=0
    root_keys={'run_id','status','epochs','updates','initial_sha256','final_sha256','elapsed_seconds','cuda_peak_allocated_bytes','cuda_peak_reserved_bytes'}
    for folder,ident in RUNS:
        path=BASE/folder/(ident+'.json');row=read_json(path)
        require(set(row)==root_keys and row['run_id']==ident and row['status']=='COMPLETE' and row['updates']==47052 and len(row['epochs'])==9,'FINAL_RUN_CONTRACT')
        for epoch,entry in enumerate(row['epochs'],1):
            report=dict(entry['development']);receipt=report.pop('receipt_sha');s=report['summary'];train=entry['train']
            require(entry['epoch']==epoch and report['complete'] and digest(report)==receipt,'DEVELOPMENT_RECEIPT_SHA')
            require(s['scenes']==10501 and s['n_valid']==36018430 and s['n_rain']==4496600,'DEVELOPMENT_DENOMINATORS')
            require(train['scenes']==10455 and train['batches']==5228 and train['n_valid']==10455*3430,'TRAIN_COVERAGE')
            require(len(s['tau'])==len(s['covered'])==len(s['coverage'])==32 and s['tau']==[(i+.5)/32 for i in range(32)],'FROZEN_TAU')
            require(len(s['reliability'])==10 and len(s['rain_strata'])==7 and len(s['tail'])==5 and len(report['blocks'])==35,'REPORT_STRUCTURE')
            require(len(report['scene_blocks'])==10501 and all(isinstance(v,list) and len(v)==2 and isinstance(v[0],str) and type(v[1]) is int for v in report['scene_blocks']),'PUBLIC_SCENE_BLOCK_IDENTITY_ONLY')
            require(abs(s['conditional_pinball']-s['s_qr']/s['n_rain'])<1e-14,'UNWEIGHTED_PINBALL')
            require(abs(s['core_fp64']-(s['s_occ']+s['s_qr'])/s['n_valid'])<1e-14,'COMMON_FP64_CORE')
            require(all(abs(c-k/s['n_rain'])<1e-14 for c,k in zip(s['coverage'],s['covered'])),'COVERAGE_DENOMINATOR')
            train_ids.setdefault(epoch,set()).add(train['ids_sha']);dev_ids.add(report['ids_sha']);validated+=1
        cp=row['epochs'][-1]['checkpoint'];location=BASE/folder/'.local'/ident/'checkpoints'
        raw=(location/cp['reference_name']).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==cp['receipt_sha256'],'LAST_RECEIPT_CURRENT_SHA')
        require(json.loads(raw)['sha256']==cp['payload_sha256'] and (location/'LAST_epoch_09.registration.json').exists(),'LAST_REGISTERED_IDENTITY')
        require(cp['same_bytes_deserialized'] and cp['weights_only'] and cp['validated_before_last'],'LAST_TRANSACTION_RECEIPT')
        checkpoints.append(dict(run_id=ident,epoch=9,update=47052,**cp,payload_bytes_rehashed_for_publication=False))
        s=row['epochs'][-1]['development']['summary'];metrics[ident]=s
        tail=next(t for t in s['tail'] if t['threshold_mm_h']==100.)
        table.append(dict(run_id=ident,seed=2026,endpoint_epoch=9,updates=47052,development_scenes=s['scenes'],n_valid=s['n_valid'],n_rain=s['n_rain'],
            core_fp64=s['core_fp64'],brier=s['brier'],auroc=s['auroc'],average_precision=s['average_precision'],conditional_pinball=s['conditional_pinball'],
            q32_target=.984375,q32_coverage=s['coverage'][31],q32_signed_bias=s['q32_signed_bias'],q32_over_100_exposures=tail['exposures'],
            runner_reported_elapsed_seconds=row['elapsed_seconds'],elapsed_field_scope='CURRENT_INVOCATION_FOR_RESUMED_RUNS_NOT_FULL_RUN_TOTAL'))
        curve=BASE/folder/(ident+'_curve_data.json');c=read_json(curve)
        require(c['epoch']==list(range(1,10)) and c['development_brier']==[e['development']['summary']['brier'] for e in row['epochs']],'CURVE_REPORT_IDENTITY')
        publish.extend((path,curve))
    require(len(dev_ids)==1 and all(len(v)==1 for v in train_ids.values()),'MATCHED_DATA_AND_EPOCH_ORDER')
    compare=read_json(OUT/'primary_comparisons.json')
    require(len(compare['contrasts'])==4 and compare['scope']=='2024_DEVELOPMENT_SEED2026_ONLY' and compare['confirmatory_significance'] is False,'EXPLORATORY_SCOPE')
    for c in compare['contrasts']:
        a=metrics[c['model']+'__'+c['contrast'][:2]+'__s2026'];b=metrics[c['model']+'__E0__s2026'];key=c['primary_metric']
        require(abs(c['difference']-(a[key]-b[key]))<1e-14,'CONTRAST_ARITHMETIC')
    weights=read_json(OUT/'paired_bootstrap_multiplicities.json')
    require(weights['replicates']==2000 and weights['blocks']==35 and digest(weights['values'])==weights['sha256'],'BOOTSTRAP_IDENTITY')
    publish.extend(OUT/name for name in ('primary_comparisons.json','paired_bootstrap_multiplicities.json','execution_status.json'))
    csv_path=OUT/'FINAL_METRICS.csv'
    if csv_path.exists():raise FileExistsError('FINAL_METRICS_ALREADY_EXISTS')
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    csv_path.write_bytes(stream.getvalue().replace('\r\n','\n').encode())
    write_json(OUT/'FINAL_CHECKPOINT_RECEIPTS.json',dict(scope='RECEIPT_IDENTITY_ONLY_NO_WEIGHT_UPLOAD',receipts=checkpoints))
    write_json(OUT/'COMPLETION_PUBLICATION_AUDIT.json',dict(status='PASS',audit_utc=datetime.now(timezone.utc).isoformat(),training_finished_utc=status['finished_utc'],
        parent_git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),training_source_commit=release['source_commit'],training_source_sha256=release['source_sha256'],
        completed_runs=6,endpoint_epoch=9,planned_endpoint_updates=282312,replay_attempts=16162,actual_attempts=298474,returned_verified=298474,
        validation_receipts_verified=validated,final_last_receipts_verified=6,primary_contrasts_verified=4,source_pins_verified=len(release['source_pins']),
        matched_epoch_train_order=True,matched_development_ids=True,job_empty=True,session_row_status=session[1],
        session_row_note='STALE_ACTIVE_LABEL_DOES_NOT_OVERRIDE_COMPLETE_CAMPAIGN_AND_EMPTY_JOB',
        raw_data_reads_for_publication=0,checkpoint_payload_reads_for_publication=0,model_forwards=0,optimizer_steps=0,
        scope='2024_DEVELOPMENT_SEED2026_ONLY',confirmatory_significance=False,other_seeds_authorized=False,test_2025_authorized=False,
        HISTORICAL_RECOVERY_RATIFICATION='NOT_GRANTED',HISTORICAL_2025_PATH_ATTRIBUTE_ACCESS='NOT_INSTRUMENTED'))
    publish.extend(OUT/name for name in ('FINAL_METRICS.csv','FINAL_CHECKPOINT_RECEIPTS.json','COMPLETION_PUBLICATION_AUDIT.json','RESULTS.md'))
    for path in publish:
        require('.local' not in path.parts and path.suffix in ('.json','.csv','.md'),'PUBLIC_ALLOWLIST_ONLY')
        if path.suffix=='.json':read_json(path)
    write_json(OUT/'PUBLICATION_MANIFEST.json',dict(training_source_commit=release['source_commit'],
        files={p.relative_to(ROOT).as_posix():dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in publish},
        excluded=['checkpoint weights','raw observations and reference pixels','private runtime logs','exact-score SQLite databases','unrelated historical status changes']))
    print(json.dumps(dict(status='PUBLICATION_AUDIT_PASS',validation_receipts=validated,checkpoint_receipts=6,public_files=len(publish)+1,total_bytes=sum(p.stat().st_size for p in publish))))


if __name__=='__main__':main()
