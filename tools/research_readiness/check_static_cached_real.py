"""Actual B5/B6 static data plus inherited2023/2024 caches; zero optimizer use."""
from pathlib import Path
import argparse,gc,hashlib,io,json,os,sys,time,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
os.environ.update(CUBLAS_WORKSPACE_CONFIG=':4096:8',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--terrain',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists() or os.environ.get('PYTHONHASHSEED')!='2029':raise PermissionError('Fresh receipt/seed2029 required')
    import torch
    torch.set_num_threads(1)
    from yuntapr.experimental.core_innovation.stage4.data import Batch,read,sha
    from yuntapr.experimental.core_innovation.stage4.engine import forward,resources,state_digest
    from yuntapr.experimental.research_readiness.static_training import unpack,model_factory
    v=read(a.inputs);cache=Path(v['cache']);r=read(a.terrain/'production_receipt.json');cr=read(cache/'batch_receipt.json')
    allowed={str((cache/n).resolve()).lower() for n in ('train_batch.pt','dev_batch.pt')}
    def audit(event,args):
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            s=str(Path(os.fsdecode(args[0])).resolve()).lower()
            if s.endswith(('.nc','.h5','.hdf5','.hgt','.hgt.zip','.grib','.grb2')) or (s.endswith(('.pt','.pth','.ckpt')) and s not in allowed):raise PermissionError('Cached2023/2024/static only; raw/weights forbidden')
    sys.addaudithook(audit)
    def forbidden(*args,**kwargs):raise PermissionError('No optimizer construction/update in preparation')
    torch.optim.Optimizer.__init__=forbidden;torch.optim.AdamW.step=forbidden
    before_time=time.monotonic();admission=resources();static_raw={k:(a.terrain/f'{k}_static.npz').read_bytes() for k in ('B5','B6')};packs={k:unpack(raw,k,r) for k,raw in static_raw.items()}
    models=model_factory(packs,r['scalers'])(2029,ROOT)
    init={k:state_digest(m.state_dict()) for k,m in models.items()}
    wrapper=read(ROOT/v['inherited_preparation']);ref=read(Path(wrapper['historical_b3_run'])/'paired_initial_identity.json')
    for k in ('B3','B4'):
        if init[k]!=ref[k]['full_state_sha256']:raise ValueError('Historical seed2029 common initialization differs')
    report=dict(status='IN_PROGRESS',scope='ACTUAL_STATIC_PLUS_CACHED_TRAIN_DEV_ZERO_UPDATES',preparation_code_commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),code_sha256={n:sha(ROOT/n) for n in ('tools/research_readiness/check_static_cached_real.py','src/yuntapr/experimental/research_readiness/static_training.py','src/yuntapr/experimental/core_innovation/stage4/engine.py')},resource_admission=admission,optimizer_updates=0,optimizer_constructions=0,model_checkpoint_loads=0,raw_weather_reads=0,raw_2025_reads=0,static_sha256={k:hashlib.sha256(raw).hexdigest() for k,raw in static_raw.items()},cases=[],parameter_counts={k:sum(p.numel() for p in m.parameters()) for k,m in models.items()},source_data=wrapper['prepared']['data'],limits=dict(raw_weather_source_bytes=0,cached_payload_files=2,static_payload_files=2,max_seconds=600,cached_payload_bytes=sum((cache/f'{k}_batch.pt').stat().st_size for k in ('train','dev')),static_payload_bytes=sum(len(v) for v in static_raw.values())))
    try:
        torch.cuda.reset_peak_memory_stats()
        for role,key,n in (('Train','train',2),('Development','dev',1)):
            if time.monotonic()-before_time>600:raise RuntimeError('Real-cache precheck10min cap')
            path=cache/f'{key}_batch.pt'
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=cr['tensor_sha256'][key]:raise ValueError('Inherited real cache changed')
            b=torch.load(io.BytesIO(raw),map_location='cpu',weights_only=False);del raw
            if b.role!=role or any(not s.startswith('2023-' if role=='Train' else '2024-') for s in b.ids):raise PermissionError('Year/role mismatch')
            batch=Batch(*(getattr(b,k)[:n] for k in ('x','native_valid','environment','environment_valid','rate','valid','region')),b.ids[:n],b.analyses[:n],role,wrapper['prepared']['data']).to('cuda')
            reference=models['B4'].cuda().eval()
            with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):out,loss=forward(reference,batch)
            logits=out.rain_logit.detach().cpu();quantiles=out.conditional_quantiles_log.detach().cpu();del out,loss;reference.cpu()
            for kind in ('B5','B6'):
                model=models[kind].cuda();model.train(role=='Train')
                with torch.set_grad_enabled(role=='Train'),torch.autocast('cuda',dtype=torch.bfloat16):out,loss=forward(model,batch)
                identical=torch.equal(out.rain_logit.detach().cpu(),logits) and torch.equal(out.conditional_quantiles_log.detach().cpu(),quantiles)
                if not identical or not torch.isfinite(loss.training_objective):raise RuntimeError('Zero residual changed B4 predictions or loss not finite')
                if role=='Train':
                    loss.training_objective.backward()
                    if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):raise RuntimeError('Missing/nonfinite static gradients')
                    if not torch.count_nonzero(model.static.output.weight.grad):raise RuntimeError('Static branch disconnected')
                report['cases'].append(dict(model=kind,role=role,scenes=n,n_valid=loss.n_valid,loss=float(loss.training_objective.detach()),forward_identical_to_B4=True,backward=role=='Train',gradients_finite=True))
                model.zero_grad(set_to_none=True);model.cpu();del out,loss;gc.collect();torch.cuda.empty_cache()
            del batch,b;torch.cuda.empty_cache()
        if any(init[k]!=state_digest(m.state_dict()) for k,m in models.items()):raise RuntimeError('Precheck modified weights or buffers')
        report.update(status='PASS_ACTUAL_STATIC_CACHED_REAL_ZERO_UPDATES',weights_unchanged=True,peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),elapsed_seconds=time.monotonic()-before_time)
    except BaseException as exc:
        report.update(status='STOP_NO_AUTOMATIC_RETRY',error=type(exc).__name__+': '+str(exc));raise
    finally:
        with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({k:report[k] for k in ('status','parameter_counts','peak_cuda_allocated_bytes','elapsed_seconds','optimizer_updates')}))

if __name__=='__main__':main()
