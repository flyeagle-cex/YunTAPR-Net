from pathlib import Path
import ast,csv,json,hashlib
import numpy as np
import torch
import pytest
from torch.utils.data import DataLoader
from data.b0_smoke_dataset import smoke_collate,check_causality,sha256
from models.b0_smoke import B0SmokeUNet
from losses.b0_smoke_loss import masked_mse
RUN=Path(__file__).resolve().parents[1]
def j(p):return json.loads((RUN/p).read_text(encoding='utf-8'))
@pytest.fixture(scope='module')
def tensors():
 with np.load(RUN/'B0_SMOKE/real_smoke_tensors.npz',allow_pickle=False) as a:return {k:a[k].copy() for k in a.files}

def test_real_sources_and_sample_count():
 r=j('B0_SMOKE/execution_results.json')
 assert r['real_data_end_to_end'] and r['sample_count']==16
 assert r['unique_himawari_files']==16 and r['unique_imerg_files']==1
 meta=j('B0_SMOKE/smoke_sample_metadata.json')
 assert all(Path(x['himawari_path']).is_file() and Path(x['imerg_path']).is_file() for x in meta)

def test_actual_b13_mapping_metadata():
 reports=j('B0_SMOKE/reader_actual_metadata.json')
 assert len(reports)==16
 for x in reports.values():
  b=x['b13'];assert b['variable']=='tbb_13' and b['decoded_dtype']=='float32'
  assert b['original_shape']==[501,501] and b['attrs']['units']=='K'
  assert '_FillValue' in b['attrs'] or 'missing_value' in b['attrs']

def test_actual_imerg_precipitation_contract():
 for x in j('B0_SMOKE/reader_actual_metadata.json').values():
  b=x['imerg'];assert b['variable']=='precipitation' and b['attrs']['units']=='mm hr-1'
  assert b['original_shape']==[48,130,140] and b['native_window']=='NOT_INFERRED'

@pytest.mark.parametrize('field',['x','y'])
def test_real_tensor_dtype_shape(field,tensors):
 assert tensors[field].shape==(16,1,32,32) and tensors[field].dtype==np.float32

@pytest.mark.parametrize('field',['input_valid_mask','target_valid_mask'])
def test_valid_mask_shape_dtype(field,tensors):
 assert tensors[field].shape==(16,1,32,32) and tensors[field].dtype==bool

def test_real_missing_finite_contract(tensors):
 for name,mask in [('x','input_valid_mask'),('y','target_valid_mask')]:
  assert np.isfinite(tensors[name][tensors[mask]]).all()
  assert np.isnan(tensors[name][~tensors[mask]]).all()
 assert tensors['input_valid_mask'].all()

def test_real_zero_rain_valid(tensors):
 z=(tensors['y']==0)&tensors['target_valid_mask']
 assert z.sum()>0  # Actual selected subset contains real dry target pixels.
 assert j('B0_SMOKE/diagnostic_metrics.json')['zero_rain_included']>0

def test_real_time_mapping_and_causality():
 import pandas as pd
 for m in j('B0_SMOKE/smoke_sample_metadata.json'):
  assert check_causality(m) and m['causality_pass']
  assert m['mapping_status']=='ENGINEERING_SMOKE_TIME_MAPPING_ONLY'
  assert pd.Timestamp(m['candidate_analysis_time'])-pd.Timestamp(m['imerg_converted_time'])==pd.Timedelta(minutes=30)
  assert pd.Timestamp(m['candidate_analysis_time'])-pd.Timestamp(m['selected_himawari_nominal_time'])==pd.Timedelta(minutes=10)
  assert all(k in m for k in ['obs_start','obs_end','date_created'])

def test_real_dataloader_batch_contract():
 r=j('B0_SMOKE/dataloader_check.json')
 for bs in [1,4]:
  assert r[str(bs)]['shape']==[bs,1,32,32]
  assert r[str(bs)]['shuffle'] is False and r[str(bs)]['num_workers']==0

def test_real_step_losses_finite_and_minimal():
 with (RUN/'B0_SMOKE/step_log.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
 assert len(rows)==4 and all(np.isfinite(float(r['loss'])) for r in rows)
 assert {r['epoch'] for r in rows}=={'1'}

def test_real_backward_grad_and_update():
 r=j('B0_SMOKE/gradient_update_check.json');assert r['parameter_count']>0
 assert all(x['all_grad_non_none'] and x['all_grad_finite'] and x['changed_parameter_tensors']>0 for x in r['steps'])

def test_actual_checkpoint_complete_and_reload(tensors):
 p=RUN/'B0_SMOKE/checkpoints/b0_smoke_only.pt';saved=torch.load(p,map_location='cpu',weights_only=True)
 assert {'model_state_dict','optimizer_state_dict','step','config','sample_contract_version'}<=saved.keys()
 assert saved['step']==4 and 'NOT SCIENTIFIC CHECKPOINT' in saved['checkpoint_role']
 model=B0SmokeUNet(saved['config']['model_width']).eval();model.load_state_dict(saved['model_state_dict'])
 with torch.no_grad():pred=model(torch.from_numpy(tensors['x'][:4]))
 assert pred.shape==(4,1,32,32) and torch.isfinite(pred).all()
 assert j('B0_SMOKE/checkpoint_reload_check.json')['consistent']

def test_inference_outputs_finite():
 with np.load(RUN/'B0_SMOKE/inference_outputs.npz') as a:
  assert a['prediction'].shape==(4,1,32,32) and np.isfinite(a['prediction']).all()
 assert j('B0_SMOKE/inference_check.json')['raw_files_reread']

def test_metrics_are_diagnostic_only():
 r=j('B0_SMOKE/diagnostic_metrics.json');assert r['scope']=='ENGINEERING_DIAGNOSTIC_ONLY'
 assert np.isfinite(r['MAE_mm_hr']) and np.isfinite(r['RMSE_mm_hr'])
 assert 'IN_SAMPLE' in r['evaluation_scope']

def test_frozen_mask_and_stage0_decisions_unchanged():
 for p,b in j('logs/old_evidence_before.json').items():
  p=Path(p);s=p.stat();assert s.st_size==b['size_bytes'] and s.st_mtime_ns==b['mtime_ns'] and sha256(p)==b['sha256']

def test_raw_read_only_identity():
 for p,b in j('logs/raw_inputs_before.json').items():
  p=Path(p);s=p.stat();assert s.st_size==b['size_bytes'] and s.st_mtime_ns==b['mtime_ns'] and sha256(p)==b['sha256']
 assert j('logs/raw_integrity_after_execution.json')['all_unchanged']

def test_staging_bounded_clean_and_verified():
 r=j('logs/staging_summary.json')
 assert r['remaining_owned_copies']==0 and r['cleanup_failures']==0 and r['all_size_hash_verified']
 assert r['max_single_temporary_bytes']<=r['max_bytes']

@pytest.mark.parametrize('forbidden',['gfs','dem','era5','dote','dtfm','mee'])
def test_forbidden_sources_not_imported_or_model_inputs(forbidden):
 for folder in ['data','models','losses','scripts']:
  for p in (RUN/'src'/folder).glob('*.py'):
   tree=ast.parse(p.read_text(encoding='utf-8'))
   modules=[]
   for node in ast.walk(tree):
    if isinstance(node,ast.Import):modules.extend(a.name for a in node.names)
    elif isinstance(node,ast.ImportFrom) and node.module:modules.append(node.module)
   assert not any(forbidden in m.lower() for m in modules)
 cfg=j('smoke_config.json');assert cfg['input_channel']=='tbb_13' and cfg['input_times']==1

def test_no_formal_normalization_split_or_architecture_freeze():
 c=j('smoke_config.json')
 assert not c['formal_normalization'] and not c['train_val_test_split'] and not c['formal_experiment']
 assert not c['model_architecture_frozen'] and not c['model_input_bbox_frozen'] and not c['operational_replay']
 assert not list(RUN.rglob('*normalization_stats*')) and not list(RUN.rglob('*train_mean*'))

def test_reused_function_bodies_match_original_source():
 info=j('logs/reader_reuse.json')
 for original,snapshot,names in [(info['himawari_source'],RUN/'src/vendor/stage0_read_himawari.py',['decode_packed','_time']),(info['imerg_source'],RUN/'src/vendor/stage0_data_qc.py',['decode_values'])]:
  def bodies(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(Path(p).read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef) and n.name in names}
  assert bodies(original)==bodies(snapshot)
