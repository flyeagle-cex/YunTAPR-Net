"""Plan/produce bounded candidate terrain from the inherited2023 cached mask."""
import argparse,csv,json,os,sys,math,hashlib,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUTF8='1')

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('plan','produce'));p.add_argument('--inputs',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--public-receipt',type=Path)
    a=p.parse_args();import torch,numpy as np
    from yuntapr.experimental.core_innovation.grid import frozen_sp04_grid
    from yuntapr.experimental.core_innovation.stage3.planning import digest
    from yuntapr.experimental.research_readiness.terrain_production import edges,dilate,produce
    def read(x):return json.loads(Path(x).read_text(encoding='utf-8'))
    def sha(x):return hashlib.sha256(Path(x).read_bytes()).hexdigest()
    v=read(a.inputs);cache=Path(v['cache']);receipt=read(cache/'batch_receipt.json')
    if sha(cache/'train_batch.pt')!=receipt['tensor_sha256']['train']:raise ValueError('Inherited cached2023 tensor changed')
    b=torch.load(cache/'train_batch.pt',map_location='cpu',weights_only=False)
    if b.role!='Train' or any(not s.startswith('2023-') for s in b.ids):raise PermissionError('2023 Train cache only')
    region=b.region[0,0].numpy().astype(bool)
    if region.sum()!=3430 or not np.all(b.valid[:,0].numpy()[:,region]) or not torch.equal(b.region,b.region[:1].expand_as(b.region)):raise ValueError('Frozen3430 spatial support differs')
    grid=frozen_sp04_grid(ROOT);context=dilate(region,2);iy,ix=np.where(context);ey,ex=edges(grid.lat),edges(grid.lon)
    bounds=[math.floor(ey[iy.min()]-1/3600),math.ceil(ey[iy.max()+1]+1/3600),math.floor(ex[ix.min()]-1/3600),math.ceil(ex[ix.max()+1]+1/3600)]
    if a.mode=='plan':
        if a.plan.exists() or a.output.exists():raise PermissionError('New plan and output only')
        files=[];south,north,west,east=bounds
        inventory=ROOT/'stage0-b0-evidence/evidence/outputs/stage0_spatial_static_closeout/run_20260928T095818_821492Z/DEM/dem_inventory.csv'
        rows={r['filename']:r for r in csv.DictReader(inventory.open(encoding='utf-8-sig')) if r['root']=='SRTM'}
        for y in range(north-1,south-1,-1):
            for x in range(west,east):
                name=f'N{y:02d}E{x:03d}.SRTMGL1.hgt.zip';r=rows[name];path=Path(v['dem_root'])/name
                if not path.is_file() or path.stat().st_size!=int(r['size_bytes']) or r['read_status']!='PASS':raise ValueError('Required native tile absent or changed size')
                files.append(dict(path=str(path.resolve()),name=name,bytes=int(r['size_bytes']),member=r['archive_member'],south=y,west=x))
        mosaic_bytes=((north-south)*3600+1)*((east-west)*3600+1)*2
        if shutil.disk_usage(a.output.parent).free<8*1024**3:raise RuntimeError('Reserve8GiB for candidate terrain production')
        plan=dict(status='BOUNDED_PREPARATION_AUTHORIZED_BY_USER_TASK_NOT_FORMAL_TRAINING',files=files,mosaic_integer_bounds=bounds,mosaic_bytes=mosaic_bytes,max_files=len(files),max_source_bytes=sum(f['bytes'] for f in files),max_decompressed_bytes=len(files)*3601**2*2,max_seconds=1800,minimum_free_bytes=8*1024**3,grid_sha256=grid.identity,region_sha256=digest(region.tolist()),train_cache_sha256=receipt['tensor_sha256']['train'],population_sha256=b.identity['population_sha256'],source_inventory_sha256=sha(inventory),user_task_sha256=sha(v['user_task']),formal_training_authorized=False)
        a.plan.write_text(json.dumps(plan,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in plan.items() if k!='files'}));return
    plan=read(a.plan)
    result=produce(plan,a.output,region,grid,b.identity['population_sha256'])
    result['artifacts_sha256']={n:sha(a.output/n) for n in ('B5_static.npz','B6_static.npz','production_receipt.json')}
    result['plan_source_byte_cap']=plan['max_source_bytes'];result['plan_file_cap']=plan['max_files'];result['preparation_code_commit']=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    result['production_code_sha256']={n:sha(ROOT/n) for n in ('src/yuntapr/experimental/research_readiness/terrain_production.py','tools/research_readiness/prepare_static_terrain.py')}
    result['raw_source_archives_not_published']=True
    with a.public_receipt.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({k:result[k] for k in ('status','supervision_pixels','elevation_valid_supervision','gradient_valid_supervision','source_reads','elapsed_seconds')}))

if __name__=='__main__':main()
