"""Bounded preparation only: three pinned GFS reads, then cached zero-step GPU check."""
import argparse,hashlib,io,json,os,sqlite3,sys,time,gc
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False)

def produce(args):
    import numpy as np
    from yuntapr.experimental.core_innovation.stage3.metered_io import SourceMeter,path_key
    from yuntapr.experimental.core_innovation.stage4.data import variable_requests
    from yuntapr.experimental.core_innovation.gfs import ForecastIdentity,EnvironmentFrame,read_gfs_file,_above_ground
    from yuntapr.experimental.research_readiness.static_training import unpack
    from yuntapr.experimental.research_readiness.dynamic_terrain import PhysicalDote,DoteDefinition
    if args.cache.exists():raise PermissionError('No overwrite/replay of source preparation')
    scope=read(args.scope);private=read(args.private);wrapper=read(private['inherited']);data=wrapper['prepared']['data']
    stats=read(Path(wrapper['prepared']['private_inputs']['stage3_run'])/'train_statistics.json')
    if stats['fit_years']!=[2023] or stats['fit_role']!='Train' or stats['population_sha256']!=data['population_sha256']:raise ValueError('Train-only source reference')
    entries=scope['entries']
    if len(entries)!=3 or scope['max_files']!=3 or sum(r['bytes'] for r in entries)!=scope['max_source_bytes'] or scope['max_source_bytes']!=901220:raise PermissionError('Exact minimal read scope required')
    if [r['role'] for r in entries]!=['Train','Train','Development'] or any(r['year']!=(2023 if r['role']=='Train' else 2024) for r in entries):raise PermissionError('Frozen three-scene scope only')
    args.cache.mkdir();started=time.monotonic();receipt=read(Path(private['terrain'])/'production_receipt.json')
    raw=(Path(private['terrain'])/'B6_static.npz').read_bytes()
    expected=read(ROOT/'docs/research_readiness/20261025/evidence/b5_b6_corrected_start_proposal.json')['static_source_sha256']['B6']
    if len(raw)!=312828 or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Frozen static source changed')
    (args.cache/'B6_static.npz').write_bytes(raw);pack=unpack(raw,'B6',receipt)
    definition=DoteDefinition(stats['positive_PWAT_reference_kg_m2'],'FROZEN_2023_TRAIN_POSITIVE_PWAT_MEAN_statistics_sha256='+data['statistics_sha256'])
    transform=PhysicalDote(pack,definition);db=sqlite3.connect(args.cache/'source_reads.sqlite')
    db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)')
    db.executemany('INSERT INTO jobs VALUES (?,?)',[(str(i),'PENDING') for i in range(3)]);db.commit()
    meter=SourceMeter(db,{r['source_path']:dict(bytes=r['bytes'],sha=r['sha'],job_id=str(i)) for i,r in enumerate(entries)},max_files=3,max_bytes=901220)
    meter.install();cases=[];buffers={'Train':[],'Development':[]};masks={'Train':[],'Development':[]};physical={}
    try:
        for i,r in enumerate(entries):
            if time.monotonic()-started>600:raise RuntimeError('Preparation10min cap')
            analysis=datetime.fromisoformat(r['sid'])+timedelta(minutes=30)
            ident=ForecastIdentity(analysis-timedelta(hours=6),timedelta(hours=6),analysis)
            meter.active={path_key(r['source_path'])}
            f=read_gfs_file(r['source_path'],ident,variable_requests()['main']);meter.active=set()
            with db:db.execute("UPDATE jobs SET state='COMPLETE' WHERE id=?",(str(i),))
            frame=EnvironmentFrame(f.identity,f.grid,_above_ground(f.fields),'retrospective',(f.provenance,))
            x,m=transform(frame);diagnostic=transform.physical(frame);mapped=frame.on_grid(pack.grid,operator='bilinear_point_candidate')
            buffers[r['role']].append(x);masks[r['role']].append(m)
            # Small physical fields are cached to verify source -> old MEE
            # correspondence without rereading any original source.
            physical[str(i)]={k:(v.values,v.valid) for k,v in mapped.fields.items() if k in ('u850','v850','u700','v700','ps','pwat')}
            cases.append(dict(role=r['role'],sample_id=r['sid'],source_alias=r['source_alias'],source_bytes=r['bytes'],source_sha256=r['sha'],
                              above_ground_valid_region=[int(z[pack.region].sum()) for z in diagnostic.valid],
                              moisture_valid_region=[int(z[pack.region].sum()) for z in diagnostic.moisture_valid],
                              physical_O_range_m_s=[float(np.nanmin(diagnostic.O)),float(np.nanmax(diagnostic.O))]))
        totals=meter.totals()
        if totals!=dict(opened_files=3,delivered_bytes=901220,reserved_bytes=901220,states={'READ_COMPLETE':3}):raise RuntimeError('Minimal source ledger mismatch')
    finally:meter.uninstall();db.close()
    for role in buffers:
        np.savez(args.cache/f'{role}_dynamic.npz',values=np.stack(buffers[role]),valid=np.stack(masks[role]))
    np.savez(args.cache/'physical_fields.npz',**{f'{i}_{k}_{label}':a for i,fields in physical.items() for k,pair in fields.items() for label,a in zip(('value','valid'),pair)})
    save(args.cache/'inputs.json',dict(data=data,definition=asdict(definition),cases=cases,scalers=receipt['scalers'],
                                     static_receipt=receipt,environment_scalers=stats['environment_scalers']))
    artifacts={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in args.cache.iterdir() if p.suffix in ('.npz','.json','.sqlite')}
    report=dict(status='PASS_THREE_FROZEN_SCENES_PHYSICAL_DOTE_CACHE',scope='USER_REQUESTED_B7_B8_PREPARATION_NOT_FORMAL_TRAINING',
                data_version=data,definition=asdict(definition),source_reads=totals,static_source_reads=dict(files=1,bytes=312828,sha256=expected),
                total_new_source_bytes=1214048,total_new_source_files=4,cases=cases,artifacts=artifacts,
                elapsed_seconds=time.monotonic()-started,optimizer_updates=0,raw_satellite_reads=0,raw_imerg_reads=0,raw_dem_tile_reads=0,final_2025='FROZEN_NO_ACCESS',
                preprocessing_cache_for_formal_training=False)
    save(args.receipt,report);print(json.dumps({k:report[k] for k in ('status','source_reads','total_new_source_bytes','elapsed_seconds')}))

def check(args):
    import numpy as np
    import torch
    from yuntapr.experimental.core_innovation.stage4.data import Batch
    from yuntapr.experimental.core_innovation.stage4.engine import forward,resources,state_digest
    from yuntapr.experimental.core_innovation.stage2 import MEE_V13_KEYS
    from yuntapr.experimental.research_readiness.static_training import unpack
    from yuntapr.experimental.research_readiness.dynamic_terrain import model_factory
    if args.receipt.exists():raise PermissionError('Fresh GPU receipt required')
    started=time.monotonic();torch.set_num_threads(1);inputs=read(args.cache/'inputs.json');private=read(args.private)
    old_inputs=read(ROOT/'docs/research_readiness/.local/b5_b6_local_inputs.json');old_cache=Path(old_inputs['cache']);old_receipt=read(old_cache/'batch_receipt.json')
    allowed={(old_cache/n).resolve() for n in ('train_batch.pt','dev_batch.pt')}
    def audit(event,items):
        if event=='open' and isinstance(items[0],(str,bytes,os.PathLike)):
            path=Path(os.fsdecode(items[0])).resolve();s=str(path).lower()
            if s.endswith(('.nc','.h5','.hdf5','.hgt','.zip','.grib','.grb2')) or (s.endswith(('.pt','.pth','.ckpt')) and path not in allowed):raise PermissionError('Cached preparation only; original sources/checkpoints forbidden')
    sys.addaudithook(audit)
    def forbidden(*a,**k):raise PermissionError('No optimizer construction or update')
    torch.optim.Optimizer.__init__=forbidden;torch.optim.AdamW.step=forbidden
    admission=resources();pack=unpack((args.cache/'B6_static.npz').read_bytes(),'B6',inputs['static_receipt'])
    models=model_factory(pack,inputs['scalers'])(2029,ROOT);initial={k:state_digest(m.state_dict()) for k,m in models.items()}
    old_initial=read(Path(private['output_root'])/'B6_s2029/paired_initial_identity.json')
    if initial['B6']!=old_initial['B6']['full_state_sha256']:raise ValueError('Full B6 common initialization differs')
    torch.cuda.reset_peak_memory_stats();cases=[];physical=np.load(args.cache/'physical_fields.npz',allow_pickle=False)
    for role,key,n,offset in [('Train','train',2,0),('Development','dev',1,2)]:
        if time.monotonic()-started>600:raise RuntimeError('GPU precheck10min cap')
        raw=(old_cache/f'{key}_batch.pt').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=old_receipt['tensor_sha256'][key]:raise ValueError('Old real cache identity changed')
        old=torch.load(io.BytesIO(raw),map_location='cpu',weights_only=False);del raw
        if old.role!=role:raise ValueError('Role mismatch')
        for i in range(n):
            if old.ids[i]!=inputs['cases'][i+offset]['sample_id']:raise ValueError('Frozen sample selection differs')
            for k in ('u850','v850','u700','v700','ps','pwat'):
                value=physical[f'{i+offset}_{k}_value'];valid=physical[f'{i+offset}_{k}_valid'];s=inputs['environment_scalers'][k]
                normalized=((np.where(valid,value,s['mean'])-s['mean'])/s['std']).astype(np.float32)
                index=MEE_V13_KEYS.index(k)
                if not np.array_equal(normalized,old.environment[i,index].numpy()) or not np.array_equal(valid,old.environment_valid[i,index].numpy()):raise ValueError('Raw physical GFS does not reproduce the cached MEE binding')
        with np.load(args.cache/f'{role}_dynamic.npz',allow_pickle=False) as d:
            batch=Batch(*(getattr(old,k)[:n] for k in ('x','native_valid','environment','environment_valid','rate','valid','region')),old.ids[:n],old.analyses[:n],role,inputs['data'],torch.from_numpy(d['values']),torch.from_numpy(d['valid'])).to('cuda')
        ref=models['B6'].cuda().eval()
        with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):out,loss=forward(ref,batch)
        logits=out.rain_logit.detach().cpu();q=out.conditional_quantiles_log.detach().cpu();ref.cpu();del out,loss
        for kind in ('B7','B8'):
            model=models[kind].cuda();model.train(role=='Train')
            with torch.set_grad_enabled(role=='Train'),torch.autocast('cuda',dtype=torch.bfloat16):out,loss=forward(model,batch)
            if not torch.equal(out.rain_logit.detach().cpu(),logits) or not torch.equal(out.conditional_quantiles_log.detach().cpu(),q):raise ValueError('Identity fusion changed the inherited B6 prediction')
            if not torch.isfinite(loss.training_objective) or not bool((torch.diff(out.conditional_quantiles_log,dim=1)>0).all()):raise RuntimeError('Nonfinite loss or unordered quantiles')
            if role=='Train':
                loss.training_objective.backward()
                if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):raise RuntimeError('Disconnected/nonfinite new full-model gradients')
                if not torch.count_nonzero(model.fusion.fuse[0].weight.grad):raise RuntimeError('New residual branch has no initial gradient response')
            cases.append(dict(model=kind,role=role,scenes=n,n_valid=loss.n_valid,loss=float(loss.training_objective.detach()),
                              initial_prediction_identical_to_B6=True,finite_backward=role=='Train',q32_strict_order=True,
                              dynamic_used_pixels=int(out.dynamic_used.sum())))
            model.zero_grad(set_to_none=True);model.cpu();del out,loss;gc.collect();torch.cuda.empty_cache()
        del batch,old;torch.cuda.empty_cache()
    if any(initial[k]!=state_digest(m.state_dict()) for k,m in models.items()):raise RuntimeError('Preparation changed weights or buffers')
    report=dict(status='PASS_B7_B8_ACTUAL_CACHED_TRAIN_DEV_ZERO_UPDATES',data_version=inputs['data'],definition=inputs['definition'],
                cases=cases,initial_state_sha256=initial,parameter_counts={k:sum(p.numel() for p in m.parameters()) for k,m in models.items()},
                peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),resource_admission=admission,elapsed_seconds=time.monotonic()-started,
                optimizer_updates=0,optimizer_constructions=0,model_checkpoint_loads=0,weights_unchanged=True,raw_weather_reads=0,
                physical_fields_reproduce_cached_MEE=True,final_2025='FROZEN_NO_ACCESS',
                cache_read_bytes=sum((old_cache/f'{k}_batch.pt').stat().st_size for k in ('train','dev')),
                code_sha256={n:sha(ROOT/n) for n in ('tools/research_readiness/check_dynamic_cached_real.py','src/yuntapr/experimental/research_readiness/dynamic_terrain.py','src/yuntapr/experimental/core_innovation/stage2/fusion.py','src/yuntapr/experimental/core_innovation/dtfm.py','src/yuntapr/experimental/core_innovation/stage4/engine.py','src/yuntapr/experimental/core_innovation/stage4/data.py')})
    save(args.receipt,report);print(json.dumps({k:report[k] for k in ('status','parameter_counts','peak_cuda_allocated_bytes','elapsed_seconds')}))

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('produce','check'));p.add_argument('--scope',type=Path);p.add_argument('--private',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
    if a.mode=='produce':produce(a)
    else:check(a)
if __name__=='__main__':main()
