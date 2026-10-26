"""Bounded candidate DEM production: native metric derivatives, then area means.

HGT posts are represented by nearest-post (Voronoi) cells. WGS84 ellipsoid
surface area is separable in latitude/longitude. This is an explicitly versioned
candidate quadrature, not an assertion about the frozen 25-centre SP04 pool.
"""
import io
import json
import math
import sqlite3
import time
import zipfile
from pathlib import Path
import numpy as np
from ..core_innovation.grid import GridSpec
from ..core_innovation.terrain import (TerrainFeatures, terrain_features,
    WGS84_A_M, WGS84_E2)
from ..core_innovation.stage3.planning import digest
from ..core_innovation.stage3.metered_io import SourceMeter, path_key
from .static_terrain import pack_terrain, fit_static_train_scalers

RULE='NATIVE_WGS84_CENTRAL_GRADIENT_THEN_ELLIPSOID_AREA_MEAN_COMPONENTS_V1'

def edges(centres):
    a=np.asarray(centres,dtype=float)
    if a.ndim!=1 or len(a)<2 or not np.all(np.diff(a)>0):
        raise ValueError('Ascending explicit centres required')
    return np.r_[a[0]-(a[1]-a[0])/2,(a[:-1]+a[1:])/2,a[-1]+(a[-1]-a[-2])/2].astype('float32').astype(float)

def dilate(mask, radius=2):
    r=np.asarray(mask);out=r.copy()
    if r.dtype!=bool or r.ndim!=2 or type(radius)!=int or radius<0:raise ValueError('Boolean mask and nonnegative radius required')
    pad=np.pad(r,radius)
    for i in range(2*radius+1):
        for j in range(2*radius+1):out |= pad[i:i+r.shape[0],j:j+r.shape[1]]
    return out

def latitude_area(edges_degrees):
    """Integral of M(phi) N(phi) cos(phi) from equator, apart from longitude."""
    phi=np.radians(edges_degrees);s=np.sin(phi);e=math.sqrt(WGS84_E2)
    return WGS84_A_M**2*(1-WGS84_E2)/2*(s/(1-WGS84_E2*s*s)+np.arctanh(e*s)/e)

def interval_integrals(values, source_edges, target_edges):
    """Integrate piecewise-constant rows over target intervals without dense maps."""
    v=np.asarray(values,dtype=float);s=np.asarray(source_edges,dtype=float);t=np.asarray(target_edges,dtype=float)
    if v.shape[-1]+1!=len(s) or np.any(np.diff(s)<=0) or np.any(np.diff(t)<=0) or t[0]<s[0] or t[-1]>s[-1]:
        raise ValueError('Complete ascending area support required; no extrapolation')
    c=np.concatenate((np.zeros(v.shape[:-1]+(1,)),np.cumsum(v*np.diff(s),axis=-1)),axis=-1)
    i=np.clip(np.searchsorted(s,t,side='right')-1,0,len(s)-2)
    f=c[...,i]+v[...,i]*(t-s[i])
    return np.diff(f,axis=-1)

def finish_features(grid,z,gx,gn,evalid,gvalid):
    mag=np.hypot(gx,gn);av=gvalid&(mag>0)
    aspect=np.where(av,np.degrees(np.arctan2(-gx,-gn))%360,np.nan)
    return TerrainFeatures(grid,np.where(evalid,z,np.nan),evalid,np.where(gvalid,gx,np.nan),np.where(gvalid,gn,np.nan),gvalid,np.where(gvalid,np.degrees(np.arctan(mag)),np.nan),aspect,av)

def produce(plan, output, region, grid, population_sha, *, max_seconds=1800):
    """Only plan-listed DEM archives; one metered open/decompression each."""
    started=time.monotonic();output=Path(output)
    if output.exists():raise PermissionError('Fresh production directory only; no automatic replay')
    if max_seconds!=plan['max_seconds'] or grid.identity!=plan['grid_sha256'] or digest(region.tolist())!=plan['region_sha256']:
        raise ValueError('Plan/mask/grid/deadline changed')
    def deadline():
        if time.monotonic()-started>max_seconds:raise RuntimeError('DEM production time cap; stop without retry')
    output.mkdir()
    db=sqlite3.connect(output/'production.sqlite');db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)')
    files={str(Path(f['path']).resolve()):dict(bytes=f['bytes'],sha=None,job_id=f['name']) for f in plan['files']}
    meter=SourceMeter(db,files,max_files=plan['max_files'],max_bytes=plan['max_source_bytes'])
    south,north,west,east=plan['mosaic_integer_bounds'];n=3600
    height,width=(north-south)*n+1,(east-west)*n+1
    mosaic=np.memmap(output/'native_mosaic_int16.bin',mode='w+',dtype='int16',shape=(height,width));mosaic[:]=-32768
    done=set();sources=[];seams=0;decompressed=0
    try:
        for f in plan['files']:
            deadline();p=str(Path(f['path']).resolve());key=path_key(p)
            with db:db.execute('INSERT INTO jobs VALUES (?,?)',(f['name'],'PENDING'))
            meter.active={key}
            with meter.open(p,'rb') as handle:raw=handle.read()
            meter.active=set();rr=meter.receipt(p)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members=[q for q in archive.infolist() if q.filename.lower().endswith('.hgt')]
                if len(members)!=1 or members[0].file_size!=3601**2*2:raise ValueError('One native 3601-square HGT required')
                if Path(members[0].filename).name!=f['member']:raise ValueError('HGT member changed')
                decompressed+=members[0].file_size
                if decompressed>plan['max_decompressed_bytes']:raise PermissionError('Decompression cap')
                a=np.frombuffer(archive.read(members[0]),dtype='>i2').reshape(3601,3601)
                y,x=f['south'],f['west'];r=(north-y-1)*n;c=(x-west)*n
                if (y+1,x) in done:
                    if not np.array_equal(mosaic[r,c:c+3601],a[0]):raise ValueError('North seam mismatch; no averaging or repair')
                    seams+=1
                if (y,x-1) in done:
                    if not np.array_equal(mosaic[r:r+3601,c],a[:,0]):raise ValueError('West seam mismatch; no averaging or repair')
                    seams+=1
                mosaic[r:r+3601,c:c+3601]=a
                sources.append(dict(name=f['name'],bytes=f['bytes'],sha256=rr['sha256'],member=f['member'],hgt_crc32=f'{members[0].CRC:08x}',south=y,west=x))
                done.add((y,x))
                del a,raw
            with db:db.execute("UPDATE jobs SET state='COMPLETE' WHERE id=?",(f['name'],))
        mosaic.flush()
        context=dilate(region,2);tey=edges(grid.lat);tex=edges(grid.lon)
        # Only the static encoder's 2-cell target halo needs features. A native
        # one-post derivative halo remains in the mosaic outside this support.
        iy,ix=np.where(context);r0,r1=iy.min(),iy.max()+1;c0,c1=ix.min(),ix.max()+1
        target_x=tex[c0:c1+1];lo,hi=tey[r0],tey[r1]
        lon=west+np.arange(width)/n;lat=north-np.arange(height)/n
        se_x=np.r_[lon[0]-1/(2*n),(lon[:-1]+lon[1:])/2,lon[-1]+1/(2*n)]
        first=max(1,int(np.floor((north-hi)*n)) - 1);last=min(height-1,int(np.ceil((north-lo)*n))+2)
        sums=np.zeros((3,*grid.shape));valid_area=np.zeros((2,*grid.shape));full_area=np.diff(latitude_area(tey))[:,None]*np.radians(np.diff(tex))[None,:]
        for start in range(first,last,64):
            deadline();stop=min(last,start+64)
            z=np.asarray(mosaic[start-1:stop+1],dtype=float);mask=z!=-32768
            features=terrain_features(z,mask,GridSpec(lat[start-1:stop+1],lon),elevation_unit='m')
            values=(features.elevation_m[1:-1],features.east_gradient[1:-1],features.north_gradient[1:-1])
            masks=(features.elevation_valid[1:-1],features.gradient_valid[1:-1])
            horizontal=[interval_integrals(np.where(masks[0 if i==0 else 1],v,0),se_x,target_x)*np.pi/180 for i,v in enumerate(values)]
            horizontal_valid=[interval_integrals(m.astype(float),se_x,target_x)*np.pi/180 for m in masks]
            for j,r in enumerate(range(start,stop)):
                lower=lat[r]-1/(2*n);upper=lat[r]+1/(2*n)
                target_rows=np.flatnonzero((tey[:-1]<upper)&(tey[1:]>lower))
                for tr in target_rows:
                    if tr<r0 or tr>=r1:continue
                    w=float(latitude_area(min(upper,tey[tr+1]))-latitude_area(max(lower,tey[tr])))
                    for channel in range(3):sums[channel,tr,c0:c1]+=w*horizontal[channel][j]
                    for channel in range(2):valid_area[channel,tr,c0:c1]+=w*horizontal_valid[channel][j]
            del features,z,mask,values,masks,horizontal,horizontal_valid
        coverage=valid_area/full_area
        ev=context&(coverage[0]>=1-1e-9);gv=context&(coverage[1]>=1-1e-9)
        if not (ev[region].all() and gv[region].all()):raise RuntimeError('Missing DEM/gradient coverage in frozen3430 supervision pixels; no mask shrink')
        f=finish_features(grid,*(sums/full_area),ev,gv)
        source_id=digest(sources);packs={};scalers={}
        for kind in ('B5','B6'):
            pack=pack_terrain(f,kind=kind,region=region,expected_grid=grid,source_sha256=source_id,aggregation_rule=RULE)
            scalers[kind]=fit_static_train_scalers(pack,fit_role='Train',fit_years=[2023],train_region=region,population_sha256=population_sha)
            path=output/f'{kind}_static.npz'
            np.savez(path,values=pack.values,valid=pack.valid,region=region,lat=grid.lat,lon=grid.lon)
            packs[kind]=dict(file=path.name,channels=list(pack.channels),units=list(pack.units))
        result=dict(status='COMPLETE_CANDIDATE_DEM_PRODUCTION_NOT_A_TRAINING_GRANT',aggregation_rule=RULE,grid_sha256=grid.identity,region_sha256=plan['region_sha256'],source_sha256=source_id,supervision_pixels=int(region.sum()),elevation_valid_supervision=int(ev[region].sum()),gradient_valid_supervision=int(gv[region].sum()),flat_aspect_supervision=int((region&~f.aspect_valid).sum()),static_context_pixels=int(context.sum()),area_coverage_supervision_min=[float(a[region].min()) for a in coverage],seams_checked=seams,seam_mismatch=0,source_reads=meter.totals(),decompressed_bytes=decompressed,sources=sources,packs=packs,scalers=scalers,elapsed_seconds=time.monotonic()-started,scientific_status='CANDIDATE_FOR_CONSOLIDATED_DECISION',vertical_datum='EGM96_PER_SRTM_PRODUCT_SPEC_LOCAL_RELEASE_CHAIN_NOT_VERIFIED',release_version='LOCAL_CONTENT_SHA_PINNED_SRTMGL1_NAMED_ARCHIVES_VENDOR_RELEASE_NOT_VERIFIED',raw_2025_reads=0,normalization_fit_role='2023_TRAIN_SPATIAL_SUPPORT_UNIQUE_PIXELS',optimizer_updates=0)
        deadline()
        with (output/'production_receipt.json').open('x',encoding='utf-8') as h:json.dump(result,h,indent=2,allow_nan=False)
        return result
    except BaseException as exc:
        with (output/'failure.json').open('x',encoding='utf-8') as h:json.dump(dict(status='STOP_NO_AUTOMATIC_REPLAY',error=type(exc).__name__+': '+str(exc),reads=meter.totals()),h,indent=2)
        raise
    finally:db.close()
