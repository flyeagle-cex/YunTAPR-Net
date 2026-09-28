"""Create a new run; prepare -> scoped tests -> real-data smoke -> final tests/report."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,io,json,os,platform,random,shutil,subprocess,sys,time,traceback
import importlib.metadata as md
import xml.etree.ElementTree as ET
SRC=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SRC))
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from data.b0_smoke_dataset import (AuditedReaders,BoundedStaging,B0SmokeDataset,smoke_collate,sha256,jsonable,utc_timestamp,check_causality,CONTRACT_VERSION)
from models.b0_smoke import B0SmokeUNet
from losses.b0_smoke_loss import masked_mse,diagnostic_metrics

PYTHON=Path(r'F:\pytorch\Research\.venv\Scripts\python.exe')
OUTPUT_ROOT=Path(r'F:\pytorch\Research\outputs\stage1_b0_engineering_smoke')
P0=Path(r'F:\pytorch\Research\outputs\stage0_p0_audit\run_20260927T161311_417313Z')
FREEZE=Path(r'F:\pytorch\Research\outputs\stage0_spatial_decision_update\run_20260928T102636_513428Z')
GATE=Path(r'F:\pytorch\Research\outputs\stage0_final_gate_package\run_20260928T113745_449683Z')
HIM_SOURCE=Path(r'F:\pytorch\Research\stage0_himawari\src\read_himawari.py')
REQUEST=Path(r'C:\Users\chenerxiao\.codex\attachments\d97497c5-4596-4c9b-9759-febdd38628ee\已粘贴的文本.txt')
ENDING='B0 engineering smoke run complete.\nReal-data Dataset-to-inference pipeline was tested.\nNo formal B0 scientific experiment was started.\nNo formal Train/Validation/Test split was executed.\nNo scientific result is claimed from this smoke run.\nAll Stage-0 frozen conventions remain unchanged.'
TIME_LIMIT='The cross-source IMERG-Himawari time binding used in this\nB0 smoke run is provisional and was used only to test the\nengineering pipeline. It is not a frozen scientific sample\ntiming convention.'

def utc():return datetime.now(timezone.utc).isoformat()
def write(run,rel,text):
 p=(run/rel).resolve()
 if not p.is_relative_to(run.resolve()):raise ValueError('Output path escape')
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
def wjson(run,rel,value):write(run,rel,json.dumps(jsonable(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def load(run,rel):return json.loads((run/rel).read_text(encoding='utf-8-sig'))
def csvrows(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def table(run,rel,rows):
 fields=list(rows[0]) if rows else ['sample_id','reason']
 b=io.StringIO(newline='');w=csv.DictWriter(b,fieldnames=fields);w.writeheader();w.writerows([{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in x.items()} for x in rows]);write(run,rel,b.getvalue())
def snapshot(paths):
 return {str(p):dict(size_bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,sha256=sha256(p)) for p in paths}
def check_snapshot(old):
 rows=[]
 for name,s in old.items():
  p=Path(name);st=p.stat();rows.append(dict(path=name,size_unchanged=st.st_size==s['size_bytes'],mtime_unchanged=st.st_mtime_ns==s['mtime_ns'],sha256_unchanged=sha256(p)==s['sha256']))
 return rows
def ok_integrity(rows):return all(r['size_unchanged'] and r['mtime_unchanged'] and r['sha256_unchanged'] for r in rows)
def packages():return {d.metadata['Name']:d.version for d in md.distributions() if d.metadata['Name']}
def seed_settings():
 random.seed(42);np.random.seed(42);torch.manual_seed(42)
 if torch.cuda.is_available():torch.cuda.manual_seed_all(42)
 torch.set_num_threads(2);torch.use_deterministic_algorithms(True,warn_only=True)
 torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True

def copy_python_sources(root,run):
 """Snapshot runnable modules; audited vendor files are refreshed separately.

 Excluding vendor also permits prepare to be invoked from an archived run.
 """
 for folder in ['src','tests']:
  paths=(root/folder).rglob('*.py') if folder=='src' else (root/folder).glob('*.py')
  for p in paths:
   if folder=='src' and 'vendor' in p.relative_to(root/folder).parts:continue
   write(run,str(p.relative_to(root)),p.read_text(encoding='utf-8-sig'))

def prepare():
 if Path(sys.executable).resolve()!=PYTHON.resolve():raise RuntimeError('Wrong Python')
 root=SRC.parent
 run=OUTPUT_ROOT/('run_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
 run.mkdir(parents=True,exist_ok=False)
 copy_python_sources(root,run)
 old=[P0/'audit_final_status.json',P0/'config.json',P0/'src/data_qc.py',P0/'src/time_rules.py',HIM_SOURCE,
      P0/'IMERG/imerg_time_audit.csv',P0/'IMERG/imerg_inventory.csv',P0/'HIMAWARI_202407/himawari_202407_latency.csv',
      FREEZE/'freeze_registry.json',FREEZE/'audit_final_status.json',FREEZE/'docs/RESEARCHER_APPROVAL_RECORD.md',
      GATE/'stage0_final_gate_status.json',GATE/'FINAL_STAGE0_GATE_REPORT.md',GATE/'FROZEN_CONVENTIONS.md',GATE/'DECISIONS/gate_assessment.json',GATE/'output_manifest.csv',
      Path(r'F:\pytorch\Research\outputs\stage0_continuous_engineering\run_20260928T041855_828904Z\schemas\sample_index_schema.md')]
 reg=load(FREEZE,'freeze_registry.json')
 for a in reg['artifacts'].values():
  p=FREEZE/a['relative_path'];assert sha256(p)==a['sha256'];old.append(p)
 assert sha256(FREEZE/'freeze_registry.json')=='04077f6d33f7535bcff28d426de4c1970da6c86255c32f16ec043fe2c12779df'
 gate=load(GATE,'stage0_final_gate_status.json');assert gate['b0_engineering_smoke_ready'] and not gate['b0_formal_experiment_ready']
 wjson(run,'logs/old_evidence_before.json',snapshot(old));wjson(run,'logs/packages_before.json',packages())
 write(run,'src/vendor/stage0_read_himawari.py',HIM_SOURCE.read_text(encoding='utf-8-sig'))
 write(run,'src/vendor/stage0_data_qc.py',(P0/'src/data_qc.py').read_text(encoding='utf-8-sig'))
 # Byte copies preserve exact source SHA; text write above may normalize newlines, so record both.
 wjson(run,'logs/reader_reuse.json',{'himawari_source':str(HIM_SOURCE),'himawari_original_sha256':sha256(HIM_SOURCE),'himawari_snapshot_sha256':sha256(run/'src/vendor/stage0_read_himawari.py'),'functions_reused':['decode_packed','_time'],'imerg_source':str(P0/'src/data_qc.py'),'imerg_original_sha256':sha256(P0/'src/data_qc.py'),'imerg_snapshot_sha256':sha256(run/'src/vendor/stage0_data_qc.py'),'imerg_functions_reused':['decode_values'],'reuse_method':'unchanged AST function bodies; no Stage-0 runner/config import; B13 variable-only adapter; snapshots may normalize source newlines','existing_model_assessment':'Data/lesson_3/lesson03_mini_unet.py expects 42 channels and executes at import; lesson03_mini_b0_train.py includes quantile teaching/training. Not imported; dedicated one-head small U-Net used.'})
 write(run,'PROVENANCE/task_request.txt',REQUEST.read_text(encoding='utf-8-sig'))
 write(run,'PROVENANCE/researcher_time_mapping_approval.md','# Explicit researcher approval for this smoke only\n\n研究者本轮明确确认：T 为 IMERG converted CF coordinate；candidate analysis_time=T+30min；selected nominal=analysis_time−10min。实际保存 nominal/obs_start/obs_end/date_created，强制 obs_end<=analysis_time；失败拒绝，不修改时间或选择未来帧。每条记录保留 imerg_converted_time、candidate_analysis_time、selected_himawari_nominal_time、obs_start、obs_end、date_created、causality_pass、mapping_status。mapping_status=ENGINEERING_SMOKE_TIME_MAPPING_ONLY。date_created 仅记录，不是 availability。本轮为 offline smoke，未证明 native window start 或 [T,T+30min) 科学语义，未冻结正式单帧绑定。正式 B0 仍需后续明确科学批准。\n\n'+TIME_LIMIT+'\n')
 config=dict(purpose='OFFLINE_ENGINEERING_SMOKE_ONLY',sample_count=16,seed=42,epochs=1,batch_size=4,num_workers=0,shuffle=False,model_width=8,optimizer='Adam',learning_rate=0.001,input_channel='tbb_13',input_times=1,target_variable='precipitation',crop_indices=[44,76,54,86],crop_scope='ENGINEERING_SMOKE_CROP_ONLY',alignment_status='PROVISIONAL_SMOKE_ALIGNMENT',mapping_status='ENGINEERING_SMOKE_TIME_MAPPING_ONLY',analysis_offset_minutes=30,nominal_offset_minutes=-10,sample_contract_version=CONTRACT_VERSION,model_architecture_frozen=False,model_input_bbox_frozen=False,formal_experiment=False,formal_normalization=False,train_val_test_split=False,operational_replay=False,source_imerg_grid_anchor=str(FREEZE/reg['artifacts']['coordinates']['relative_path']))
 wjson(run,'smoke_config.json',config)
 seed_settings();device='cuda' if torch.cuda.is_available() else 'cpu'
 wjson(run,'logs/environment.json',dict(utc=utc(),python=sys.executable,torch_version=str(torch.__version__),numpy_version=np.__version__,netCDF4_version=md.version('netCDF4'),pyarrow_version=md.version('pyarrow'),CUDA_available=torch.cuda.is_available(),GPU_name=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,CPU=platform.processor(),platform=platform.platform(),device_used=device,dtype='float32',seed=42,python_random_seed=42,numpy_seed=42,pytorch_seed=42,deterministic_algorithms_enabled=True,deterministic_warn_only=True,cudnn_benchmark=False,cudnn_deterministic=True,cpu_threads=2,bitwise_cuda_determinism_claimed=False))
 # Select only existing audit records, no raw inventory scan. Read actual fields later.
 p0cfg=load(P0,'config.json')
 times=next(r for r in csvrows(P0/'IMERG/imerg_time_audit.csv') if r['filename']=='imerg_20240701.nc')
 hrows=csvrows(P0/'HIMAWARI_202407/himawari_202407_latency.csv')
 bytime={utc_timestamp(r['nominal_time']):r for r in hrows if r['parse_status']=='OK'}
 samples=[];rejections=[]
 for index,t in enumerate(json.loads(times['decoded_values'])):
  analysis=utc_timestamp(t)+pd.Timedelta(minutes=30);nominal=analysis-pd.Timedelta(minutes=10)
  r=bytime.get(nominal)
  if r is None:rejections.append(dict(sample_id=t,reason='EXACT_NOMINAL_NOT_IN_AUDITED_MONTH_INDEX'));continue
  s=dict(sample_id='b0_smoke_'+utc_timestamp(t).strftime('%Y%m%dT%H%M%SZ'),himawari_path=str(Path(p0cfg['himawari_root'])/r['relative_path']),imerg_path=str(Path(p0cfg['imerg_root'])/times['relative_path']),imerg_index=index,imerg_target_time=t,analysis_time=analysis.isoformat(),nominal_time=nominal.isoformat(),obs_start=r['obs_start'],obs_end=r['obs_end'],date_created=r['date_created'],latency_tail_review=r['latency_tail_review'],mapping_status=config['mapping_status'])
  try:check_causality(s)
  except ValueError as e:rejections.append(dict(sample_id=s['sample_id'],reason=str(e)));continue
  samples.append(s)
  if len(samples)==config['sample_count']:break
 if len(samples)!=config['sample_count']:raise RuntimeError('Insufficient audited candidates in one day; no broader scan')
 wjson(run,'B0_SMOKE/selected_samples.json',samples);table(run,'B0_SMOKE/candidate_selection_rejections.csv',rejections)
 wjson(run,'logs/preflight_check.json',{'status':'PASS','fixed_python':True,'old_gate_pass':True,'frozen_hashes_pass':True,'single_channel':True,'single_time':True,'selected_candidate_count':len(samples),'raw_libraries_scanned':False,'science_rules_changed':False})
 print(json.dumps({'run':str(run),'device':device,'samples':len(samples),'preflight':'PASS'},ensure_ascii=False))

def make_dataset(run,cache=True):
 cfg=load(run,'smoke_config.json');samples=load(run,'B0_SMOKE/selected_samples.json')
 readers=AuditedReaders(run/'src/vendor')
 staging=BoundedStaging(run,{s[k] for s in samples for k in ['himawari_path','imerg_path']})
 with np.load(cfg['source_imerg_grid_anchor'],allow_pickle=False) as a:lat=a['lat'].copy();lon=a['lon'].copy()
 ds=B0SmokeDataset(samples,readers,staging,lat,lon,tuple(cfg['crop_indices']),cache=cache)
 return ds,staging

def sync(device):
 if device.type=='cuda':torch.cuda.synchronize()

def execute(run):
 seed_settings();cfg=load(run,'smoke_config.json');device=torch.device(load(run,'logs/environment.json')['device_used'])
 if (run/'B0_SMOKE/execution_results.json').exists():raise FileExistsError('Smoke already executed; no silent rerun')
 ds,staging=make_dataset(run)
 wjson(run,'logs/raw_inputs_before.json',staging.before)
 batches=[];loaders={}
 # Real Dataset -> DataLoader loads, including batch 1 and >1, with deterministic ordering.
 for bs in [1,cfg['batch_size']]:
  loader=DataLoader(ds,batch_size=bs,shuffle=False,num_workers=0,collate_fn=smoke_collate)
  t=time.perf_counter();b=next(iter(loader));elapsed=time.perf_counter()-t
  assert b['x'].shape==(bs,1,32,32) and b['y'].shape==b['x'].shape
  assert b['x'].dtype==b['y'].dtype==torch.float32
  assert b['input_valid_mask'].all() and b['target_valid_mask'].any()
  loaders[str(bs)]={'status':'PASS','load_seconds':elapsed,'shape':list(b['x'].shape),'num_workers':0,'shuffle':False,'sample_ids':[m['sample_id'] for m in b['metadata']]}
 # Validate all selected raw-backed items once before optimizer work; cache only small aligned tensors.
 items=[]
 for i in range(len(ds)):
  try:
   item=ds[i]
   if not item['input_valid_mask'].all():raise ValueError('SMOKE_ONLY fully-valid-input requirement; no fill')
   if not item['target_valid_mask'].any():raise ValueError('No valid target pixels')
   if not torch.isfinite(item['x']).all():raise ValueError('Nonfinite input')
   items.append(item)
  except Exception as e:
   wjson(run,'B0_SMOKE/rejected_sample_'+str(i)+'.json',dict(sample=ds.samples[i],reason=repr(e),timestamps_modified=False));raise
 real=smoke_collate(items)
 metadata=[x['metadata'] for x in items]
 table(run,'B0_SMOKE/smoke_sample_manifest.csv',metadata)
 wjson(run,'B0_SMOKE/smoke_sample_metadata.json',metadata)
 wjson(run,'B0_SMOKE/reader_actual_metadata.json',ds.read_reports)
 wjson(run,'B0_SMOKE/dataloader_check.json',loaders)
 np.savez_compressed(run/'B0_SMOKE/real_smoke_tensors.npz',x=real['x'].numpy(),y=real['y'].numpy(),input_valid_mask=real['input_valid_mask'].numpy(),target_valid_mask=real['target_valid_mask'].numpy(),lat=ds.lat[cfg['crop_indices'][0]:cfg['crop_indices'][1]],lon=ds.lon[cfg['crop_indices'][2]:cfg['crop_indices'][3]])
 assert all(m['causality_pass'] for m in metadata)
 model=B0SmokeUNet(cfg['model_width']).to(device)
 optimizer=torch.optim.Adam(model.parameters(),lr=cfg['learning_rate'])
 count=sum(p.numel() for p in model.parameters() if p.requires_grad)
 assert count>0
 if device.type=='cuda':torch.cuda.reset_peak_memory_stats()
 steps=[];gradient=[]
 loader=DataLoader(ds,batch_size=cfg['batch_size'],shuffle=False,num_workers=0,collate_fn=smoke_collate)
 for step,b in enumerate(loader,1):
  x=b['x'].to(device);y=b['y'].to(device);valid=b['target_valid_mask'].to(device)
  optimizer.zero_grad(set_to_none=True)
  sync(device);tick=time.perf_counter();pred=model(x);sync(device);fsec=time.perf_counter()-tick
  assert pred.shape==y.shape and torch.isfinite(pred).all()
  loss=masked_mse(pred,y,valid);assert torch.isfinite(loss)
  sync(device);tick=time.perf_counter();loss.backward();sync(device);bsec=time.perf_counter()-tick
  params=[p for p in model.parameters() if p.requires_grad]
  assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in params)
  gradnonzero=sum(bool(torch.count_nonzero(p.grad)) for p in params)
  assert gradnonzero>0
  before=[p.detach().clone() for p in params]
  tick=time.perf_counter();optimizer.step();sync(device);osec=time.perf_counter()-tick
  changed=sum(not torch.equal(a,p.detach()) for a,p in zip(before,params));assert changed>0
  gradient.append(dict(step=step,trainable_parameter_tensors=len(params),all_grad_non_none=True,all_grad_finite=True,nonzero_gradient_tensors=gradnonzero,changed_parameter_tensors=changed))
  steps.append(dict(step=step,epoch=1,batch_size=x.shape[0],loss=float(loss.detach()),loss_finite=True,forward_seconds=fsec,backward_seconds=bsec,optimizer_seconds=osec,scope='ENGINEERING_SMOKE_ONLY'))
 table(run,'B0_SMOKE/step_log.csv',steps);wjson(run,'B0_SMOKE/gradient_update_check.json',{'status':'PASS','parameter_count':count,'steps':gradient})
 # Real checkpoint, new model object, safe weights-only load, same input comparison.
 checkpoint=run/'B0_SMOKE/checkpoints/b0_smoke_only.pt';checkpoint.parent.mkdir(parents=True,exist_ok=True)
 model.eval();same=real['x'][:4].to(device)
 with torch.no_grad():before=model(same).detach().cpu()
 payload=dict(model_state_dict=model.state_dict(),optimizer_state_dict=optimizer.state_dict(),step=len(steps),config=cfg,sample_contract_version=CONTRACT_VERSION,checkpoint_role='SMOKE CHECKPOINT / NOT SCIENTIFIC CHECKPOINT')
 with checkpoint.open('xb') as f:torch.save(payload,f)
 loaded=torch.load(checkpoint,map_location=device,weights_only=True)
 reloaded=B0SmokeUNet(cfg['model_width']).to(device);reloaded.load_state_dict(loaded['model_state_dict']);reloaded.eval()
 with torch.no_grad():after=reloaded(same).cpu()
 maxdiff=float((before-after).abs().max());consistent=torch.allclose(before,after,rtol=1e-5,atol=1e-6)
 assert consistent
 reopt=torch.optim.Adam(reloaded.parameters(),lr=cfg['learning_rate']);reopt.load_state_dict(loaded['optimizer_state_dict'])
 wjson(run,'B0_SMOKE/checkpoint_reload_check.json',dict(status='PASS',path=str(checkpoint),sha256=sha256(checkpoint),new_model_instance=True,optimizer_state_restored=True,step=loaded['step'],same_input_max_abs_diff=maxdiff,rtol=1e-5,atol=1e-6,consistent=consistent,role=payload['checkpoint_role']))
 # Force actual rereads for inference, using the SAME protected staging tracker.
 fresh=B0SmokeDataset(ds.samples[:4],ds.readers,staging,ds.lat,ds.lon,ds.crop,cache=False)
 t=time.perf_counter();b=next(iter(DataLoader(fresh,batch_size=4,shuffle=False,num_workers=0,collate_fn=smoke_collate)));inferload=time.perf_counter()-t
 with torch.no_grad():
  sync(device);t=time.perf_counter();pred=reloaded(b['x'].to(device));sync(device);infersec=time.perf_counter()-t
 assert pred.shape==(4,1,32,32) and torch.isfinite(pred).all()
 metrics=diagnostic_metrics(pred.cpu(),b['y'],b['target_valid_mask'])
 metrics.update(sample_ids=[m['sample_id'] for m in b['metadata']],evaluation_scope='IN_SAMPLE_ENGINEERING_DIAGNOSTIC_ONLY; same smoke samples, no held-out claim; all target-valid crop pixels, not full Yunnan evaluation')
 wjson(run,'B0_SMOKE/diagnostic_metrics.json',metrics)
 np.savez_compressed(run/'B0_SMOKE/inference_outputs.npz',prediction=pred.cpu().numpy(),target=b['y'].numpy(),target_valid_mask=b['target_valid_mask'].numpy())
 wjson(run,'B0_SMOKE/inference_check.json',dict(status='PASS',shape=list(pred.shape),finite=True,raw_files_reread=True,load_seconds=inferload,inference_seconds=infersec))
 integrity=staging.integrity();assert ok_integrity(integrity)
 wjson(run,'logs/raw_integrity_after_execution.json',{'checked_files':len(integrity),'all_unchanged':True,'checks':integrity})
 wjson(run,'logs/staging_summary.json',staging.summary())
 assert not staging.created
 results=dict(real_data_end_to_end=True,dataset_pass=True,dataloader_pass=True,forward_pass=True,backward_pass=True,optimizer_pass=True,checkpoint_reload_pass=True,inference_pass=True,sample_count=len(ds),sample_date_range=[metadata[0]['imerg_converted_time'],metadata[-1]['imerg_converted_time']],unique_himawari_files=len({s['himawari_path'] for s in metadata}),unique_imerg_files=len({s['imerg_path'] for s in metadata}),input_channels=1,input_times=1,parameter_count=count,optimizer_steps=len(steps),epochs=1,all_losses_finite=all(x['loss_finite'] for x in steps),device_used=str(device),peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated() if device.type=='cuda' else None,peak_gpu_memory_status='MEASURED' if device.type=='cuda' else 'NOT_APPLICABLE_CPU',sample_contract_version=CONTRACT_VERSION,formal_experiment_started=False,scientific_result_claimed=False,raw_data_modified=False,finished_utc=utc())
 wjson(run,'B0_SMOKE/execution_results.json',results)
 print(json.dumps(results,ensure_ascii=False))

def run_tests(run,phase):
 selection=['tests/test_b0_unit.py'] if phase=='unit' else ['tests/test_b0_unit.py','tests/test_b0_real_pipeline.py']
 cmd=[sys.executable,'-B','-m','pytest',*selection,'--rootdir=.','--confcutdir=tests','--import-mode=importlib','-p','no:cacheprovider','--basetemp='+str(run/'tests'/('tmp_'+phase)),f'--junitxml=tests/pytest_{phase}.xml','-q']
 if (run/f'tests/pytest_{phase}.xml').exists():raise FileExistsError('Keep prior test results; select new attempt name')
 proc=subprocess.run(cmd,cwd=run,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
 write(run,f'tests/pytest_{phase}_output.txt',proc.stdout);wjson(run,f'logs/pytest_{phase}_execution.json',dict(command=cmd,exit_code=proc.returncode,utc=utc()))
 print(proc.stdout)
 if proc.returncode:raise RuntimeError('Tests failed; isolate error before continuing')

def finalize(run):
 from smoke_reports import finalize_report
 finalize_report(sys.modules[__name__],run)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','unit','execute','final_tests','finalize']);parser.add_argument('--run',type=Path)
 a=parser.parse_args()
 if a.phase=='prepare':prepare()
 else:
  run=a.run.resolve()
  if not run.is_relative_to(OUTPUT_ROOT.resolve()):raise ValueError('Wrong run root')
  try:
   if a.phase in ['unit','final_tests']:run_tests(run,'unit' if a.phase=='unit' else 'final')
   elif a.phase=='execute':execute(run)
   else:finalize(run)
  except Exception as e:
   write(run,'logs/error_'+datetime.now(timezone.utc).strftime('%H%M%S_%f')+'.txt',traceback.format_exc())
   raise
