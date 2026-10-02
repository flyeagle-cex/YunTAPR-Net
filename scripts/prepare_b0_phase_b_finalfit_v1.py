"""Researcher acceptance and bounded FinalFit preparation; no formal fitting loop."""
import argparse
import csv
from dataclasses import asdict, replace, fields
from datetime import datetime, timezone, timedelta
import gc
import importlib.metadata
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import traceback
from unittest.mock import patch
import weakref

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT)]
import netCDF4
import numpy as np
import torch
import yaml
from yuntapr.contracts.loader import sha256 as _sha256
from yuntapr.data.himawari_b13 import read_b13_local
from yuntapr.data.formal_policy import require_full_valid
from yuntapr.data.sample_schema import utc
from yuntapr.data.staging import BoundedEnglishStaging
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.phase_a_protocol import load_protocol, seed_reproducibility, state_digest
from yuntapr.training.phase_b_preparation import (SCENES,PIXELS,STEPS,EPOCHS,UPDATES,TAIL_POLICY,
    INITIALIZATION,validate_population,exact_histogram_summary,merge_moments,PhaseBNormalizer,batch_plan,finalfit_lr)

BASELINE = '5050b6cc77ab75eacb96e1494a165d61142227f4'
REVIEW_ID = 'run_20261002T005448_798068Z'
REVIEW = ROOT/'docs/scientific_review/b0_phase_a/runs'/REVIEW_ID
FORMAL = ROOT/'docs/formal_training/b0_phase_a/runs/run_20261001T035003_243409Z'
CLOSURE = ROOT/'docs/b0_pretraining_closure/runs/run_20260930T095416Z'
VALIDATION = ROOT/'docs/phase_a_protocol_prefreeze/runs/run_20261001T014523Z/eligible_validation_manifest.csv'
HROOT = Path(r'H:\葵花202303_202510')
IROOT = Path(r'F:\云南极端降水数据\raw\IMERG')
PRIVATE = Path(r'F:\pytorch\Research\outputs\phase_b_finalfit_preparation')
STAGING = Path(r'F:\pytorch\Research\stage0_himawari\cache\staging')
DECISION = ROOT/'config/decisions/b0_phase_a_acceptance_v1.yaml'
PROTOCOL = ROOT/'config/training/phase_b_finalfit_preparation_v1.yaml'
AUTH_ATTACHMENT = Path(r'C:\Users\chenerxiao\.codex\attachments\014d272d-bd83-4b92-b972-6e7ba9485182\已粘贴的文本.txt')


def sha256(path):
    return _sha256(Path(path))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path,value):
    path = Path(path)
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False,default=str)
        f.write('\n')


def rows(path):
    with Path(path).open(encoding='utf-8',newline='') as f:
        return list(csv.DictReader(f))


def table(path,values):
    with Path(path).open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(values[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(values)


def preserve(out=None):
    if out is None:
        entries = subprocess.check_output(['git','ls-tree','-r','-z',BASELINE],cwd=ROOT).decode().rstrip('\0').split('\0')
        pins={}
        import hashlib
        for entry in entries:
            meta,name=entry.split('\t',1)
            data=(ROOT/name).read_bytes()
            blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if blob != meta.split()[2]: raise ValueError('Baseline artifact changed: '+name)
            pins[name]=hashlib.sha256(data).hexdigest()
        return pins
    pins=read(out/'historical_preservation.json')['baseline_files_sha256']
    for name,expected in pins.items():
        if sha256(ROOT/name)!=expected: raise ValueError('Historical artifact changed: '+name)
    best=read(REVIEW/'review_manifest.json')['formal_best']
    if sha256(best['absolute_local_path'])!=best['sha256']: raise ValueError('BEST changed')
    return {'all_baseline_files_unchanged':True,'files_checked':len(pins),'BEST_sha256':best['sha256']}


def source_paths(row):
    t=utc(row['window_start'])
    if t.year not in (2023,2024) or t.month not in range(3,11): raise ValueError('Unauthorized source time')
    h=(HROOT/row['b13_relative_path']).resolve()
    i=Path(row['imerg_day_path']).resolve()
    if (not h.is_relative_to(HROOT.resolve()) or h.relative_to(HROOT.resolve()).parts[0]!=t.strftime('%Y%m')
        or not i.is_relative_to((IROOT/str(t.year)).resolve())): raise ValueError('Frozen source root changed')
    if utc(row['expected_nominal'])!=t+timedelta(minutes=20): raise ValueError('Expected latest slot changed')
    return h,i


def initialize():
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=BASELINE: raise ValueError('Wrong baseline')
    if not HROOT.is_dir(): raise FileNotFoundError('Original H root unavailable; no fallback')
    pins=preserve()
    protocol=load_protocol()
    review_manifest=read(REVIEW/'review_manifest.json')
    status=read(REVIEW/'final_status.json')
    if not status['B0_PHASE_A_SCIENTIFIC_REVIEW_COMPLETED'] or status['TOTAL_TESTS_EXECUTED']!=190: raise ValueError('Review incomplete')
    for name,identity in read(REVIEW/'artifact_sha256.json').items():
        if sha256(REVIEW/name)!=identity['sha256']: raise ValueError('Review artifact hash changed')
    best=review_manifest['formal_best']
    if (sha256(best['absolute_local_path'])!=best['sha256'] or Path(best['absolute_local_path']).stat().st_size!=best['bytes']
        or best['epoch']!=11 or best['global_val_core_loss']!=0.04730775889882134): raise ValueError('BEST identity mismatch')
    ledger=rows(FORMAL/'source_identity_preflight.csv')
    train=rows(CLOSURE/'normalization_phaseA_sample_manifest.csv')
    validation=rows(VALIDATION)
    pairs={r['window_start']:r for r in rows(CLOSURE/'formal_sample_eligibility_2023_2024.csv')}
    if len(ledger)!=SCENES or len(train)!=11720 or len(validation)!=11727: raise ValueError('Population count mismatch')
    originals={'Train':{r['sample_id']:r for r in train},'Validation':{r['window_start']:r for r in validation}}
    final=[]
    for identity in ledger:
        role=identity['role'];original=originals[role][identity['sample_id']];pair=pairs[identity['window_start']]
        if pair['formal_supervised_eligible']!='True' or pair['b13_full_valid']!='True' or pair['formal_reject_reason']:
            raise ValueError('Rejected or partial sample included')
        if pair['selected_b13_relative_path']!=identity['b13_relative_path'] or pair['imerg_day_path']!=identity['imerg_day_path'] or pair['imerg_index']!=identity['imerg_index']:
            raise ValueError('Pairing differs from frozen source ledger')
        if role=='Train':
            if (original['source_sha256']!=identity['b13_sha256'] or original['source_bytes']!=identity['b13_bytes']
                or original['b13_relative_path']!=identity['b13_relative_path'] or original['formal_supervised_qc_pass']!='True'
                or original['used_older_causal_frame']!='False'): raise ValueError('Train manifest identity differs')
        elif original['selected_b13_relative_path']!=identity['b13_relative_path'] or original['expected_nominal']!=pair['expected_nominal']:
            raise ValueError('Validation manifest identity differs')
        value={'finalfit_index':0,'role':'FinalFit','source_role':role,'original_role_index':identity['index'],
            **{k:v for k,v in identity.items() if k not in ('role','index')},
            'analysis_time':pair['analysis_time'],'expected_nominal':pair['expected_nominal'],
            'selected_obs_end':pair['selected_obs_end'],'full_valid_native_pixels':251001,
            'formal_supervised_qc_pass':True,'used_older_causal_frame':False,'imerg_product':'IMERG','imerg_version':'V07','imerg_run_type':'Final'}
        source_paths(value)
        final.append(value)
    final.sort(key=lambda r:(utc(r['window_start']),r['sample_id'],r['source_role']))
    for index,row in enumerate(final): row['finalfit_index']=index
    counts=validate_population(final)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    out=ROOT/'docs/phase_b_finalfit_preparation/runs'/('run_'+stamp)
    out.mkdir(parents=True,exist_ok=False)
    private=PRIVATE/out.name;private.mkdir(parents=True,exist_ok=False)
    table(out/'phase_b_finalfit_manifest.csv',final)
    save(out/'historical_preservation.json',{'baseline_commit':BASELINE,'baseline_files_sha256':pins})
    identity={**protocol['identity'],'phase_a_protocol':{'path':'config/training/phase_a_training_protocol_v1.yaml','sha256':sha256(ROOT/'config/training/phase_a_training_protocol_v1.yaml')},
        'scientific_review_manifest':{'path':(REVIEW/'review_manifest.json').relative_to(ROOT).as_posix(),'sha256':sha256(REVIEW/'review_manifest.json')},
        'scientific_review_report':{'path':(REVIEW/'B0_PHASE_A_SCIENTIFIC_REVIEW.md').relative_to(ROOT).as_posix(),'sha256':sha256(REVIEW/'B0_PHASE_A_SCIENTIFIC_REVIEW.md')}}
    decision={'version':'v1','status':'RESEARCHER_APPROVED','authority':'Researcher attachment and engineering dry-run confirmation in this chat',
        'authority_attachment_sha256':sha256(AUTH_ATTACHMENT),'scientific_review_run':REVIEW_ID,'scientific_review_commit':BASELINE,
        'ACCEPT_B0_PHASE_A':True,'B0_PHASE_A_ACCEPTED':True,'B0_role':'CONTROL / BASELINE; not the final YunTAPR-Net',
        'SELECTED_CHECKPOINT_EPOCH':11,'SELECTED_CHECKPOINT_VAL_CORE_LOSS':0.04730775889882134,
        'selected_checkpoint':best,'identity':identity,'TRANSFER_EPOCH_BUDGET_TO_PHASE_B':11,
        'PHASE_B_AUTHORIZED':False,'PHASE_B_FORMAL_TRAINING_STARTED':False,'known_limitations_retained':True,
        'limitation_inventory':{'path':(REVIEW/'B0_LIMITATION_INVENTORY.md').relative_to(ROOT).as_posix(),'sha256':sha256(REVIEW/'B0_LIMITATION_INVENTORY.md')},
        'PHASE_B_MODEL_INITIALIZATION':INITIALIZATION,'FINALFIT_EPOCHS':11,'FINALFIT_TAIL_BATCH_POLICY':TAIL_POLICY,
        'ENGINEERING_ONLY_TWO_BATCH_DRYRUN_AUTHORIZED':True,'created_utc':datetime.now(timezone.utc).isoformat()}
    DECISION.parent.mkdir(parents=True,exist_ok=True)
    with DECISION.open('x',encoding='utf-8',newline='\n') as f: yaml.safe_dump(decision,f,allow_unicode=True,sort_keys=False)
    doc=ROOT/'docs/researcher_decisions/B0_PHASE_A_ACCEPTANCE_v1.md';doc.parent.mkdir(parents=True,exist_ok=True)
    with doc.open('x',encoding='utf-8',newline='\n') as f:
        f.write('# B0 Phase-A researcher acceptance v1\n\n研究者正式接受 B0 Phase-A 作为 CONTROL / BASELINE；不声称完整 YunTAPR-Net 已被证明。\n\n')
        f.write(f'Scientific Review run: `{REVIEW_ID}`；commit: `{BASELINE}`。历史 review 保持 immutable；它当时的 UNDECIDED 状态由本独立决策继承并更新，不回写历史。\n\n')
        f.write(f'`ACCEPT_B0_PHASE_A=true`；`B0_PHASE_A_ACCEPTED=true`；BEST epoch=11，Val core=0.04730775889882134，checkpoint SHA256=`{best["sha256"]}`。完整 identity/hash 见 config/decisions/b0_phase_a_acceptance_v1.yaml。\n\n')
        f.write('`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=11`；FinalFit 11 epochs，fresh model seed=2026。BEST 仅为科学身份和预算选择证据，不载入 FinalFit model/optimizer/scheduler。\n\n')
        f.write('FinalFit population=23,447 eligible March–October scenes：2023 Train 11,720 + 2024 Validation 11,727。仅对其 full-valid native B13 重算 ddof=0 normalization。2025 禁止读取。\n\n')
        f.write('physical batch=2、drop_last=false；尾部 singleton 不丢弃、不复制、不替换。每 epoch 所有身份恰好一次，11,724 updates/epoch；计划总更新128,964。保持1 epoch warmup及50 epoch cosine horizon，W=11,724，U=586,200；不能压缩为11 epoch。\n\n')
        f.write('保留所有已知限制：epoch11后 Validation degradation、低tau calibration deviation、月份与空间差异、稀疏强雨样本、single-band/single-time设计信息限制。物理原因未证实，不据此修改冻结规则或参数。\n\n')
        f.write('本轮仅 acceptance + preparation + 两个独立 ENGINEERING_ONLY batch；`PHASE_B_AUTHORIZED=false`，`PHASE_B_FORMAL_TRAINING_STARTED=false`。不启动正式FinalFit或B1–B8。\n')
    save(out/'preparation_manifest.json',{'run_id':out.name,'baseline_commit':BASELINE,'private_directory':str(private),
        'scope':'ACCEPTANCE_AND_FINALFIT_PREPARATION_ONLY','population':counts,'total_scenes':SCENES,
        'sort_rule':'ascending UTC window_start, sample_id, source_role; FinalFit index zero-based',
        'source_ledger_sha256':sha256(FORMAL/'source_identity_preflight.csv'),'finalfit_manifest_sha256':sha256(out/'phase_b_finalfit_manifest.csv'),
        'acceptance_sha256':sha256(DECISION),'identity':identity,'formal_best':best,'2025_PIXELS_READ':0,
        'PHASE_B_AUTHORIZED':False,'PHASE_B_FORMAL_TRAINING_STARTED':False,'created_utc':datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'IDENTITY_AND_POPULATION_GATE':'PASS','run_id':out.name,'run_dir':str(out),'counts':counts,'expected_pixels':PIXELS},ensure_ascii=False),flush=True)


def fit(out):
    started=time.perf_counter()
    manifest=read(out/'preparation_manifest.json')
    identities=rows(out/'phase_b_finalfit_manifest.csv');validate_population(identities)
    if sha256(out/'phase_b_finalfit_manifest.csv')!=manifest['finalfit_manifest_sha256']: raise ValueError('Manifest changed')
    target=out/'normalization_phaseB_finalfit_2023_2024.json'
    if target.exists(): raise FileExistsError('Completed normalization cannot be overwritten')
    preserve(out)
    stage=BoundedEnglishStaging(STAGING/('phase_b_prepare_'+out.name)/'normalization',734003200,True,True)
    mapping=load_sp04();hist=np.zeros(65536,dtype=np.int64);moments=(0,0.,0.)
    audit=[];imerg_days={}
    for number,identity in enumerate(identities,1):
        h,i=source_paths(identity)
        expected=imerg_days.get(str(i))
        if expected is not None and expected!=identity['imerg_sha256']: raise ValueError('Conflicting IMERG identity')
        if expected is None:
            size=i.stat().st_size
            if size<=0 or sha256(i)!=identity['imerg_sha256'] or i.stat().st_size!=size: raise ValueError('IMERG identity changed')
            imerg_days[str(i)]=identity['imerg_sha256']
        if h.stat().st_size!=int(identity['b13_bytes']): raise ValueError('B13 source bytes changed')
        with stage.local(h) as local:
            if stage._owned!={local.resolve()}: raise ValueError('Unbounded owned cache')
            x,valid,meta=read_b13_local(local,mapping,identity['expected_nominal'])
            require_full_valid(x,valid)
            if (meta.nominal_time!=utc(identity['expected_nominal']) or meta.obs_end!=utc(identity['selected_obs_end'])
                or meta.obs_start>meta.obs_end or meta.obs_end>utc(identity['analysis_time']) or meta.date_created is None): raise ValueError('Causal time metadata differs')
            with netCDF4.Dataset(str(local)) as ds:
                ds.set_auto_maskandscale(False);var=ds['tbb_13'];raw=np.asarray(var[:])
                if raw.dtype!=np.int16 or np.float32(var.scale_factor)!=np.float32(.01) or np.float32(var.add_offset)!=np.float32(273.15): raise ValueError('Packed encoding changed')
                hist+=np.bincount(raw.astype(np.int32).ravel()+32768,minlength=65536)
            moments=merge_moments(moments,x)
        rec=stage.records[-1]
        if rec.source_sha256!=identity['b13_sha256'] or not rec.size_match or not rec.sha256_match or not rec.cleanup_success or stage._owned: raise ValueError('Source identity or cache cleanup failed')
        audit.append({'finalfit_index':number-1,'sample_id':identity['sample_id'],'year':identity['year'],
            'valid_pixel_count':x.size,'nominal_time':str(meta.nominal_time),'obs_start':str(meta.obs_start),
            'obs_end':str(meta.obs_end),'date_created':str(meta.date_created),**asdict(rec)})
        if number%500==0 or number==len(identities):
            from yuntapr.training.formal_phase_a import atomic_json
            progress={'normalization_scenes_read':number,'total_scenes':SCENES,'pixels_read':moments[0],
                'elapsed_seconds':time.perf_counter()-started,'2025_PIXELS_READ':0,'PHASE_B_AUTHORIZED':False}
            atomic_json(out/'normalization_progress.json',progress)
            print(json.dumps(progress),flush=True)
    stats=exact_histogram_summary(hist)
    streaming_std=math.sqrt(moments[2]/moments[0])
    if stats['valid_pixel_count']!=PIXELS or moments[0]!=PIXELS or SCENES*501*501!=PIXELS: raise ValueError('Normalization population mismatch')
    if abs(stats['mean_K']-moments[1])>1e-9 or abs(stats['std_K']-streaming_std)>1e-9: raise ValueError('Independent moment methods disagree')
    private=Path(manifest['private_directory'])
    np.save(private/'normalization_phaseB_exact_packed_code_histogram.npy',hist)
    table(private/'normalization_read_ledger.csv',audit)
    ledger_path=private/'normalization_read_ledger.csv';histpath=private/'normalization_phaseB_exact_packed_code_histogram.npy'
    result={'normalization_version':'PHASE_B_FINALFIT_2023_2024_ELIGIBLE_v1','status':'FINALFIT_DERIVED_PARAMETER','ready':True,
        'fit_years':[2023,2024],'fit_months':list(range(3,11)),'eligible_scene_count':SCENES,**stats,
        'scene_native_shape':[501,501],'full_valid_pixels_per_scene':251001,'sample_manifest_sha256':sha256(out/'phase_b_finalfit_manifest.csv'),
        'source_ledger_sha256':manifest['source_ledger_sha256'],'scientific_contract_sha256':sha256(ROOT/'config/science_contract_v1.1.yaml'),
        'statistics_method':'Full raw reread of every eligible scene; frozen float32 decoder promoted to float64; exact int16 code histogram, no rebinning; independently merged per-frame float64 central moments; type-7/linear percentiles',
        'streaming_mean_K':moments[1],'streaming_std_K':streaming_std,'independent_moments_agree_atol_K':1e-9,
        'phase_a_constants_reused':False,'partial_rejected_scenes_included':False,'older_fallback_included':False,
        '2025_PIXELS_READ':0,'source_years_read':[2023,2024],'source_root':str(HROOT),'baseline_commit':BASELINE,
        'code_sha256':{p.relative_to(ROOT).as_posix():sha256(p) for p in [Path(__file__),ROOT/'src/yuntapr/training/phase_b_preparation.py',ROOT/'src/yuntapr/data/himawari_b13.py',ROOT/'src/yuntapr/data/staging.py']},
        'PHASE_B_FORMAL_TRAINING_STARTED':False,'PHASE_B_AUTHORIZED':False,'completed_utc':datetime.now(timezone.utc).isoformat()}
    save(target,result)
    save(out/'normalization_execution.json',{'status':'PASS','wall_seconds':time.perf_counter()-started,'actual_scenes_read':len(audit),
        'actual_pixels_read':moments[0],'imerg_days_identity_verified':len(imerg_days),'copy_seconds_sum':sum(r['copy_seconds'] for r in audit),
        'read_seconds_sum':sum(r['read_seconds'] for r in audit),'peak_temporary_bytes':max(r['temporary_bytes'] for r in audit),
        'cleanup_success':all(r['cleanup_success'] for r in audit),'owned_staging_files_remaining':len(stage._owned),
        'local_artifacts':{p.name:{'absolute_local_path':str(p),'bytes':p.stat().st_size,'sha256':sha256(p)} for p in [ledger_path,histpath]},
        'preservation':preserve(out),'2025_PIXELS_READ':0})
    print(json.dumps({'NORMALIZATION_GATE':'PASS','scenes':SCENES,'pixels':PIXELS,'mean_K':stats['mean_K'],'std_K':stats['std_K']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['init','fit']);parser.add_argument('--run-dir',type=Path)
    args=parser.parse_args()
    try:
        if args.action=='init': initialize()
        else:
            if args.run_dir is None: parser.error('--run-dir required')
            fit(args.run_dir.resolve())
    except Exception as error:
        traceback.print_exc()
        if args.run_dir and args.run_dir.is_dir():
            save(args.run_dir/('failure_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'.json'),{'action':args.action,'error':repr(error),'traceback':traceback.format_exc(),'PHASE_B_AUTHORIZED':False,'PHASE_B_FORMAL_TRAINING_STARTED':False})
        raise SystemExit(1)
