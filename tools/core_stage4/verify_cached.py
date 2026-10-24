"""Reconcile current metadata/guards with cached batches; no raw opens or GPU."""
from pathlib import Path
import argparse,ast,hashlib,json,os,sqlite3,sys
ROOT=Path(__file__).resolve().parents[2];sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'))
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import torch
from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan,sha
from yuntapr.experimental.core_innovation.stage4.engine import epoch_order
from yuntapr.experimental.core_innovation.stage4 import DRY_SEED,PAIR_CAP,STEPS
from yuntapr.experimental.core_innovation.stage3.planning import digest
torch.set_num_threads(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage3-run',type=Path,required=True);p.add_argument('--request',type=Path,required=True);p.add_argument('--dry-run',type=Path,required=True);a=p.parse_args()
    def audit(event,values):
        if event=='open' and isinstance(values[0],(str,bytes,os.PathLike)) and os.fsdecode(values[0]).lower().endswith(('.nc','.hgt','.hgt.zip','.h5','.hdf5')):raise PermissionError('CACHED_ONLY_NO_RAW_WEATHER_OR_DEM')
    sys.addaudithook(audit)
    plan=PopulationPlan(a.stage3_run,a.request,root=ROOT);run=a.dry_run;receipt=json.loads((run/'batch_receipt.json').read_text());completion=json.loads((run/'completion.json').read_text())
    ledger_before=sha(run/'reads/reads.sqlite');selected=plan.dry_ids()
    for role,key in (('Train','train'),('Development','dev')):
        path=run/(key+'_batch.pt')
        if sha(path)!=receipt['tensor_sha256'][key]:raise ValueError('Cached tensor identity changed')
        b=torch.load(path,map_location='cpu',weights_only=False)
        if b.ids!=selected[role] or any(plan.identity[k]!=v for k,v in b.identity.items()):raise ValueError('Cached population/scaler/label ancestry conflict')
        if b.x.shape!=(len(b.ids),42,501,501) or b.environment.shape!=(len(b.ids),13,100,100) or not b.native_valid.all() or not torch.isfinite(b.x).all() or int((b.valid&b.region).sum())!=len(b.ids)*3430:raise ValueError('Cached batch tensor contract')
        if (b.environment[~b.environment_valid]!=0).any():raise ValueError('Invalid GFS layer not neutral')
        del b
    for epoch in range(1,10):
        if digest(epoch_order(plan.ids('Train'),DRY_SEED,epoch))!=completion['order_sha256'][str(epoch)]:raise ValueError('Paired order changed')
    sources=list((ROOT/'src/yuntapr/experimental/core_innovation/stage4').glob('*.py'))+[ROOT/f'src/yuntapr/experimental/core_innovation/stage2/{x}.py' for x in ('__init__','models','environment')]
    for path in sources:ast.parse(path.read_text(encoding='utf-8'))
    if ledger_before!=sha(run/'reads/reads.sqlite'):raise ValueError('Original read ledger changed')
    r=dict(status='PASS_CACHED_ONLY_CURRENT_METADATA',new_weather_reads=0,optimizer_updates=0,prior_read_ledger_unchanged=True,
        final_data_identity=plan.identity,final_development_strong_scenes=len(plan.strong_scene_ids),steps_per_epoch=STEPS,paired_update_cap=PAIR_CAP,
        original_real_dry_receipt_sha256=sha(run/'completion.json'),current_source_sha256={x.relative_to(ROOT).as_posix():sha(x) for x in sources},
        post_probe_changes='Only provenance, startup/partition guards, target-buffer bound and inactive formal-run receipts changed; numerical GPU path was not rerun unchanged.')
    with (run/'cached_verification.json').open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
    print(json.dumps({k:v for k,v in r.items() if k not in ('current_source_sha256','final_data_identity')},indent=2))
