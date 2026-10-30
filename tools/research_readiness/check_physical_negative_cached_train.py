"""One cached2023 Train batch forward/backward, zero optimizer operations."""
import argparse
import copy
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime,timedelta,timezone

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pair-cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists()
    import numpy as np
    import torch
    from yuntapr.experimental.core_innovation.stage4.data import Batch
    from yuntapr.experimental.core_innovation.stage4.engine import resources,forward,state_digest
    from yuntapr.experimental.research_readiness.static_training import unpack
    from yuntapr.experimental.research_readiness.dynamic_terrain import model_factory
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    cache=ROOT/'docs/research_readiness/.local/b7_b8_real_cache_20261027_v2';inputs=read(cache/'inputs.json')
    oldmeta=read(ROOT/'docs/research_readiness/.local/b5_b6_local_inputs.json');oldcache=Path(oldmeta['cache']);oldreceipt=read(oldcache/'batch_receipt.json')
    allowed=(oldcache/'train_batch.pt').resolve()
    def guard(event,items):
        if event=='open' and isinstance(items[0],(str,bytes,os.PathLike)):
            path=Path(os.fsdecode(items[0])).resolve();s=str(path).lower()
            if '2025' in path.parts or s.endswith(('.nc','.h5','.hdf5','.hgt','.grib','.grb2','.zip')) or (s.endswith(('.pt','.pth','.ckpt')) and path!=allowed):
                raise PermissionError('Only frozen Train tensor cache; no source,Dev,2025 or weights')
    sys.addaudithook(guard)
    def forbidden(*args,**kwargs):raise PermissionError('No optimizer may be constructed or updated')
    torch.optim.Optimizer.__init__=forbidden;torch.optim.AdamW.step=forbidden
    started=time.monotonic();torch.set_num_threads(1);admission=resources()
    raw=(cache/'B6_static.npz').read_bytes();pack=unpack(raw,'B6',inputs['static_receipt'])
    models=model_factory(pack,inputs['scalers'])(2029,ROOT);model=models['B7'];initial=state_digest(model.state_dict());del models
    reference=read(ROOT/'docs/research_readiness/20261025/evidence/dote_control_completion_20261029.json')
    assert initial==reference['initialization']['B7']['full_state_sha256']
    tensor_raw=allowed.read_bytes();assert hashlib.sha256(tensor_raw).hexdigest()==oldreceipt['tensor_sha256']['train']
    old=torch.load(io.BytesIO(tensor_raw),map_location='cpu',weights_only=False);del tensor_raw
    assert old.role=='Train' and len(old.ids)==2 and all(s.startswith('2023-') for s in old.ids)
    with np.load(a.pair_cache,allow_pickle=False) as f:real=f['real'];perp=f['perpendicular'];valid=f['valid']
    with np.load(cache/'Train_dynamic.npz',allow_pickle=False) as f:
        assert np.array_equal(real,f['values']) and np.array_equal(valid,f['valid'])
    inherited_before=state_digest({k:getattr(old,k) for k in ('x','native_valid','environment','environment_valid','rate','valid','region')})
    batch=Batch(*(getattr(old,k) for k in ('x','native_valid','environment','environment_valid','rate','valid','region')),old.ids,old.analyses,'Train',inputs['data'],torch.from_numpy(perp),torch.from_numpy(valid)).to('cuda')
    captured={}
    def hook(module,args,kwargs):
        captured['args']=[[x.detach().float().cpu() for x in items] for items in args]
        # Masks must remain boolean in the projection probe.
        for i in (3,4,5):captured['args'][i]=[x.bool() for x in captured['args'][i]]
        captured['kwargs']=kwargs
    handle=model.fusion.register_forward_pre_hook(hook,with_kwargs=True)
    model.cuda().train();torch.cuda.reset_peak_memory_stats()
    with torch.autocast('cuda',dtype=torch.bfloat16):out,loss=forward(model,batch)
    assert loss.n_valid==6860 and bool(torch.isfinite(loss.training_objective))
    assert bool((torch.diff(out.conditional_quantiles_log,dim=1)>0).all())
    loss.training_objective.backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    assert torch.count_nonzero(model.fusion.fuse[0].weight.grad)>0
    peak=torch.cuda.max_memory_allocated();diagnostic_loss=float(loss.training_objective.detach())
    handle.remove();del out,loss,batch;model.zero_grad(set_to_none=True);model.cpu();gc.collect();torch.cuda.empty_cache()
    assert initial==state_digest(model.state_dict())
    assert inherited_before==state_digest({k:getattr(old,k) for k in ('x','native_valid','environment','environment_valid','rate','valid','region')})
    probe=copy.deepcopy(model.fusion)
    with torch.no_grad():probe.fuse[0].weight.fill_(.001)
    response=probe(*captured['args'],**captured['kwargs']).values[0]
    response.square().mean().backward();grad=probe.terrain[0].weight.grad[:,12:20]
    assert torch.isfinite(grad).all();nonzero=int(torch.count_nonzero(grad))
    report=dict(status='PASS_CACHED_2023_TRAIN_NONZERO_CONTROL_ZERO_OPTIMIZER',created_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        seed=2029,scenes=2,n_valid=6860,initial_B7_full_sha256=initial,initial_matches_completed_B7=True,weights_and_buffers_unchanged=True,
        GFS_DEM_labels_supervision_unchanged=True,real_dynamic_reproduces_frozen_Train_cache=True,real_masks_unchanged=True,
        nominal_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),finite_forward_loss_backward=True,strict_32_quantile_order=True,
        initial_zero_residual='Condition-projection loss gradients initially zero for both real/control; not evidence of permanent dead inputs',
        real_input_nonzero_output_probe=dict(zero_numeric_columns=0,nonzero_loss_gradients_of_128=nonzero,finite=True,only_probe_copy_modified=True),
        training_objective_engineering_only=diagnostic_loss,resource_admission=admission,peak_cuda_allocated_bytes=peak,elapsed_seconds=time.monotonic()-started,
        cache_payload_reads=dict(Train_tensor_bytes=allowed.stat().st_size,static_bytes=312828,derived_pair_bytes=a.pair_cache.stat().st_size,old_Train_dynamic_bytes=(cache/'Train_dynamic.npz').stat().st_size),
        activity=dict(optimizer_constructions=0,optimizer_updates=0,checkpoint_loads=0,raw_weather_reads=0,Dev_inference=0,final_2025_access=0,formal_performance_evaluation=0),
        interpretation='One untrained cached Train batch,not a scientific model-performance result',code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    text=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n';a.output.write_text(text,encoding='utf-8')
    print(json.dumps(dict(status=report['status'],n_valid=6860,probe_nonzero_gradients=nonzero,peak_cuda=peak,elapsed=report['elapsed_seconds']),ensure_ascii=False))


if __name__=='__main__':main()
