"""One bounded2023 Train-only GFS pass for new negative-control confounds.

No satellite, precipitation label, Dev, final-year, checkpoint or optimizer.
Writes derived statistics and two frozen-calendar Train examples only.
"""
import argparse
from collections import defaultdict
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
import ctypes
from ctypes import wintypes

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True


def rss_bytes():
    class Memory(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in (
            'peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=wintypes.HANDLE
    ps=ctypes.WinDLL('psapi',use_last_error=True);ps.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Memory),wintypes.DWORD]
    m=Memory();m.cb=ctypes.sizeof(m)
    if not ps.GetProcessMemoryInfo(k.GetCurrentProcess(),ctypes.byref(m),m.cb):raise ctypes.WinError(ctypes.get_last_error())
    return m.working


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private',type=Path,required=True);parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prior-zero-source-setup',type=Path)
    a=parser.parse_args();assert not a.work.exists() and not a.output.exists()
    import numpy as np
    from yuntapr.experimental.core_innovation.stage3.metered_io import SourceMeter,path_key
    from yuntapr.experimental.core_innovation.stage4.data import variable_requests
    from yuntapr.experimental.core_innovation.gfs import ForecastIdentity,EnvironmentFrame,read_gfs_file,_above_ground
    from yuntapr.experimental.core_innovation.terrain import physical_spacing
    from yuntapr.experimental.research_readiness.static_training import unpack
    from yuntapr.experimental.research_readiness.dynamic_terrain import PhysicalDote,DoteDefinition
    from yuntapr.experimental.research_readiness.dote_physical_controls import PerpendicularGradientDote,joint_mask_permutation
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    private=read(a.private);prepared=read(private['inherited'])['prepared'];role=prepared['roles']['Train']
    entries={p:f for p,f in role['files'].items() if f['kind']=='GFS_main'}
    assert len(entries)==959 and sum(x['bytes'] for x in entries.values())==272589016
    assert all(x['year']==2023 for x in entries.values())
    locked=read(ROOT/'docs/research_readiness/.local/physical_negative_design_lock_20261030.json')
    assert locked['rotation_matrix_east_north']==[[0,-1],[1,0]]
    cache=ROOT/'docs/research_readiness/.local/b7_b8_real_cache_20261027_v2';inputs=read(cache/'inputs.json')
    raw=(cache/'B6_static.npz').read_bytes();pack=unpack(raw,'B6',inputs['static_receipt'])
    assert len(raw)==312828
    definition=DoteDefinition(**inputs['definition']);real=PhysicalDote(pack,definition);rot=PerpendicularGradientDote(pack,definition)
    region=pack.region;z=pack.values[0];lat=np.broadcast_to(np.asarray(pack.grid.lat)[:,None],region.shape);lon=np.broadcast_to(np.asarray(pack.grid.lon)[None,:],region.shape)
    # Frozen geometry/old altitude edges, no weather label or performance fit.
    latitude_cut=(lat.min()+lat.max())/2;longitude_cut=(lon.min()+lon.max())/2
    strata={'elevation_lt_1000m':region&(z<1000),'elevation_1000_to_2000m':region&(z>=1000)&(z<2000),'elevation_ge_2000m':region&(z>=2000)}
    for ns in (0,1):
        for ew in (0,1):strata[f'grid_quadrant_{ns}_{ew}']=region&((lat>=latitude_cut)==bool(ns))&((lon>=longitude_cut)==bool(ew))
    a.work.mkdir();db=sqlite3.connect(a.work/'source_reads.sqlite');db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)')
    ordered=sorted(entries);db.executemany('INSERT INTO jobs VALUES (?,?)',[(str(i),'PENDING') for i in range(959)]);db.commit()
    meter=SourceMeter(db,{p:dict(bytes=f['bytes'],sha=f['sha'],job_id=str(i)) for i,(p,f) in enumerate((p,entries[p]) for p in ordered)},max_files=959,max_bytes=272589016)
    buffers={name:[[] for _ in range(8)] for name in ('real','perpendicular')};pooled=defaultdict(lambda:np.zeros(6,np.float64));grouped=defaultdict(lambda:np.zeros(4,np.float64));valid_counts=np.zeros(8,np.int64)
    diagnostics=[];selected={};moved=eligible=0;started=time.monotonic();peak_rss=0
    prior=None
    if a.prior_zero_source_setup:
        con=sqlite3.connect((a.prior_zero_source_setup/'source_reads.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
        try:assert con.execute('SELECT COUNT(*) FROM file_io').fetchone()[0]==0
        finally:con.close()
        prior=dict(reason='Missing optional psutil before source I/O; replaced by native Windows RSS',raw_GFS_bytes=0,raw_GFS_files=0,static_cache_bytes=312828,static_cache_instances=1,optimizer_updates=0,old_namespace_preserved=True)
    def sums(x,y):
        return np.array([len(x),x.sum(dtype=np.float64),y.sum(dtype=np.float64),np.square(x,dtype=np.float64).sum(),np.square(y,dtype=np.float64).sum(),np.multiply(x,y,dtype=np.float64).sum()])
    def correlation(v):
        n,sx,sy,xx,yy,xy=v
        denominator=(xx-sx*sx/n)*(yy-sy*sy/n) if n else 0
        return float((xy-sx*sy/n)/np.sqrt(denominator)) if denominator>0 else None
    try:
        meter.install()
        for i,path in enumerate(ordered):
            if time.monotonic()-started>600:raise TimeoutError('CPU diagnostic ten-minute cap, no retry')
            rss=rss_bytes();peak_rss=max(peak_rss,rss)
            if rss>2*1024**3:raise MemoryError('Diagnostic RSS2GiB cap')
            match=re.fullmatch(r'gfs_0p25_(\d{10})_f006\.nc',Path(path).name)
            assert match
            init=datetime.strptime(match[1],'%Y%m%d%H').replace(tzinfo=timezone.utc);valid=init+timedelta(hours=6)
            sid=(valid-timedelta(minutes=30)).isoformat();assert sid in role['ids'] and valid.year==2023 and valid.hour in (0,6,12,18)
            identity=ForecastIdentity(init,timedelta(hours=6),valid);meter.active={path_key(path)}
            rawframe=read_gfs_file(path,identity,variable_requests()['main']);meter.active=set()
            frame=EnvironmentFrame(rawframe.identity,rawframe.grid,_above_ground(rawframe.fields),'retrospective',(rawframe.provenance,))
            x,m=real(frame);y,ym=rot(frame);assert np.array_equal(m,ym)
            perm,pm,mapping=joint_mask_permutation(x,m,region);assert np.array_equal(pm,m)
            valid_counts+=(m&region).sum(axis=(1,2));moved+=int((mapping[region]!=np.arange(10000).reshape(100,100)[region]).sum());eligible+=int(region.sum())
            for name,tensor in (('real',x),('perpendicular',y),('permuted',perm)):
                for c in range(8):
                    mask=m[c]&region;v=tensor[c][mask].astype(np.float64)
                    assert np.isfinite(v).all()
                    if name!='permuted':buffers[name][c].append(v.astype(np.float32))
                    else:assert np.array_equal(np.sort(v),np.sort(x[c][mask].astype(np.float64)))
                    for key,field in (('elevation',z),('latitude',lat),('longitude',lon)):
                        pooled[(name,c,'association_'+key)]+=sums(v,field[mask].astype(np.float64))
                    for lag in (1,3):
                        for axis in (0,1):
                            a1=(slice(None,-lag),slice(None)) if axis==0 else (slice(None),slice(None,-lag))
                            b1=(slice(lag,None),slice(None)) if axis==0 else (slice(None),slice(lag,None))
                            pair=mask[a1]&mask[b1];pooled[(name,c,f'lag{lag}_axis{axis}')]+=sums(tensor[c][a1][pair].astype(np.float64),tensor[c][b1][pair].astype(np.float64))
                    for key,spatial in {**strata,f'month_{valid.month:02d}':region,f'UTC_{valid.hour:02d}':region}.items():
                        vs=tensor[c][m[c]&spatial].astype(np.float64)
                        grouped[(name,c,key)]+=np.array([len(vs),vs.sum(),np.square(vs).sum(),np.count_nonzero(vs)])
            if sid in [c['sample_id'] for c in inputs['cases'] if c['role']=='Train']:
                selected[sid]=(x.copy(),y.copy(),m.copy())
            with db:db.execute("UPDATE jobs SET state='COMPLETE' WHERE id=?",(str(i),))
        totals=meter.totals();assert totals==dict(opened_files=959,delivered_bytes=272589016,reserved_bytes=272589016,states={'READ_COMPLETE':959})
    except BaseException as exc:
        failure=dict(status='STOP_DIAGNOSTIC_NO_RETRY',error_type=type(exc).__name__,totals=meter.totals(),elapsed_seconds=time.monotonic()-started)
        with (a.work/'failure.json').open('x',encoding='utf-8') as f:json.dump(failure,f,indent=2)
        raise
    finally:meter.uninstall();db.close()
    stats={}
    for name,channels in buffers.items():
        stats[name]={}
        for c,parts in enumerate(channels):
            v=np.concatenate(parts);stats[name][str(c)]=dict(n=len(v),mean=float(v.mean(dtype=np.float64)),std=float(v.std(dtype=np.float64)),
                minimum=float(v.min()),p05=float(np.quantile(v,.05)),median=float(np.quantile(v,.5)),p95=float(np.quantile(v,.95)),maximum=float(v.max()),nonzero_fraction=float(np.count_nonzero(v)/len(v)))
    # Joint permutation has exactly the same within-class marginals by proof and
    # every frame check; copying these statistics is not an estimated match.
    stats['permuted']=json.loads(json.dumps(stats['real']))
    group_records=[]
    for (name,c,key),v in sorted(grouped.items()):
        n,s,q,nz=v;group_records.append(dict(method=name,channel=c,group=key,n=int(n),mean=float(s/n) if n else None,std=float(np.sqrt(max(0,q/n-(s/n)**2))) if n else None,nonzero_fraction=float(nz/n) if n else None))
    cases=[x['sample_id'] for x in inputs['cases'] if x['role']=='Train'];assert len(selected)==len(cases)==2
    np.savez(a.work/'train_dynamic_pair.npz',real=np.stack([selected[k][0] for k in cases]),perpendicular=np.stack([selected[k][1] for k in cases]),valid=np.stack([selected[k][2] for k in cases]))
    east,north=physical_spacing(pack.grid)
    result=dict(status='PASS_FULL_2023_TRAIN_NEGATIVE_CONTROL_FEATURE_DIAGNOSTICS_NOT_A_TRAINING_GRANT',created_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        design_lock=locked,scenes=959,supervision_points_per_scene=int(region.sum()),channel_order=['O850','O700','W850','W700','L850','L700','M850','M700'],
        data_version=prepared['data'],definition=inputs['definition'],mask_valid_counts=valid_counts.tolist(),mask_valid_fraction=(valid_counts/(959*int(region.sum()))).tolist(),
        all_real_masks_preserved=True,real_static_pack_unchanged=True,global_distribution=stats,
        spatial_and_geographic_associations=[dict(method=k[0],channel=k[1],kind=k[2],n=int(v[0]),pearson=correlation(v)) for k,v in sorted(pooled.items())],
        group_statistics=group_records,joint_permutation_moved_fraction=moved/eligible,
        grid=dict(sha256=pack.grid.identity,latitude_step_degrees=float(np.median(np.diff(pack.grid.lat))),longitude_step_degrees=float(np.median(np.diff(pack.grid.lon))),median_east_spacing_m=float(np.median(np.abs(east))),median_north_spacing_m=float(np.median(np.abs(north)))),
        source_reads=totals,static_cache_read=dict(bytes=312828,instances=1,sha256=hashlib.sha256(raw).hexdigest()),
        source_manifest_sha256=hashlib.sha256(json.dumps(entries,sort_keys=True,separators=(',',':')).encode()).hexdigest(),source_ledger_sha256=hashlib.sha256((a.work/'source_reads.sqlite').read_bytes()).hexdigest(),
        derived_train_pair_sha256=hashlib.sha256((a.work/'train_dynamic_pair.npz').read_bytes()).hexdigest(),elapsed_seconds=time.monotonic()-started,observed_peak_RSS_bytes=peak_rss,
        activity=dict(raw_GFS_main_files=959,raw_GFS_main_bytes=272589016,raw_satellite_reads=0,raw_precipitation_label_reads=0,Dev_payload_reads=0,final_2025_payload_reads=0,checkpoint_reads=0,model_inference=0,optimizer_updates=0),
        prior_zero_source_setup=prior,cumulative_static_cache_bytes=312828+(prior['static_cache_bytes'] if prior else 0),
        limitations=['One Train year and frozen population only; regional/monthly/UTC associations are not independent climate validation',
                    'Gradient rotation preserves point geography/elevation/magnitude but changes scalar DOTE distribution and can be nonintegrable',
                    'Joint mask-class permutation preserves marginal/joint vectors but changes spatial/autocorrelation and local covariate relations',
                    'Neither control identifies physical causality while all original GFS/DEM information is retained'],
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n';assert not re.search(r'[A-Za-z]:[\\/]|/Users/|/home/',text)
    a.output.write_text(text,encoding='utf-8')
    print(json.dumps(dict(status=result['status'],source_reads=totals,elapsed_seconds=result['elapsed_seconds'],peak_RSS=peak_rss,selected_Train_cases=2),ensure_ascii=False))


if __name__=='__main__':main()
