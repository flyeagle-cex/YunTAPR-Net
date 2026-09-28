"""B13-only real-data smoke adapter. No formal sample or scientific alignment rule."""
from pathlib import Path
from contextlib import contextmanager
import ast, hashlib, json, shutil, time, uuid
import numpy as np
import pandas as pd
import netCDF4
import torch
from torch.utils.data import Dataset

CONTRACT_VERSION='b0-offline-engineering-smoke-v1'
def jsonable(x):
 if isinstance(x,dict):return {str(k):jsonable(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [jsonable(v) for v in x]
 if isinstance(x,np.ndarray):return jsonable(x.tolist())
 if isinstance(x,np.generic):return jsonable(x.item())
 if isinstance(x,float) and not np.isfinite(x):return str(x)
 if isinstance(x,Path):return str(x)
 return x
def sha256(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def utc_timestamp(value):
 t=pd.Timestamp(value)
 if t.tzinfo is None:raise ValueError('Explicit UTC timezone required')
 return t.tz_convert('UTC')

def reuse_functions(path,names):
 """Compile the unchanged pure functions from a hashed Stage-0 source snapshot.

 This avoids executing its task runner or importing its global config/common modules.
 """
 tree=ast.parse(Path(path).read_text(encoding='utf-8-sig'))
 nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 if {n.name for n in nodes}!=set(names):raise ValueError('Missing audited functions')
 env={'np':np,'netCDF4':netCDF4,'jsonable':jsonable,'MetadataError':ValueError}
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)
 return {n:env[n] for n in names}

class BoundedStaging:
 """Exact allowlist, one owned copy at a time, size and SHA256 check every copy."""
 def __init__(self,run,allowed_paths,max_bytes=16*1024*1024):
  self.run=Path(run).resolve();self.folder=self.run/'cache/staging'
  self.folder.mkdir(parents=True,exist_ok=True)
  self.allowed={Path(p).resolve() for p in allowed_paths};self.created=set()
  self.max_bytes=max_bytes;self.records=[];self.before={}
  for p in sorted(self.allowed):
   s=p.stat();self.before[str(p)]={'size_bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'sha256':sha256(p)}
 @contextmanager
 def local(self,source):
  source=Path(source).resolve()
  if source not in self.allowed:raise ValueError('Raw path not in this run sample allowlist')
  size=source.stat().st_size
  if self.created or size>self.max_bytes:raise RuntimeError('Bounded staging cap')
  dest=(self.folder/(uuid.uuid4().hex+'.nc')).resolve()
  if not dest.is_relative_to(self.folder.resolve()):raise RuntimeError('Staging path escape')
  r=dict(source_path=str(source),staging_path=str(dest),temporary_bytes=size,copy_seconds=None,read_seconds=None,size_match=False,sha256_verified=False,cleanup_success=False,error='')
  succeeded=False
  try:
   t=time.perf_counter()
   with source.open('rb') as src,dest.open('xb') as dst:
    self.created.add(dest);shutil.copyfileobj(src,dst,1024*1024)
   r['copy_seconds']=time.perf_counter()-t;r['size_match']=dest.stat().st_size==size
   if not r['size_match']:raise IOError('Copy size mismatch')
   r['sha256_verified']=sha256(dest)==self.before[str(source)]['sha256']
   if not r['sha256_verified']:raise IOError('Source identity changed or copy hash mismatch')
   t=time.perf_counter()
   try:yield dest;succeeded=True
   finally:r['read_seconds']=time.perf_counter()-t
  except Exception as e:r['error']=repr(e);raise
  finally:
   if succeeded and dest in self.created:
    if dest.resolve().parent!=self.folder.resolve() or not dest.resolve().is_relative_to(self.run):raise RuntimeError('Unsafe cleanup')
    try:dest.unlink();self.created.remove(dest);r['cleanup_success']=True
    except OSError as e:r['cleanup_error']=repr(e)
   self.records.append(r)
   with (self.run/'logs/staging_io.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 def integrity(self):
  rows=[]
  for name,b in self.before.items():
   p=Path(name);s=p.stat()
   rows.append(dict(path=name,size_unchanged=s.st_size==b['size_bytes'],mtime_unchanged=s.st_mtime_ns==b['mtime_ns'],sha256_unchanged=sha256(p)==b['sha256']))
  return rows
 def summary(self):
  return dict(copy_count=len(self.records),total_copied_bytes=sum(r['temporary_bytes'] for r in self.records),max_single_temporary_bytes=max((r['temporary_bytes'] for r in self.records),default=0),copy_seconds=sum(r['copy_seconds'] or 0 for r in self.records),read_seconds=sum(r['read_seconds'] or 0 for r in self.records),cleanup_failures=sum(not r['cleanup_success'] for r in self.records),remaining_owned_copies=len(self.created),max_bytes=self.max_bytes,all_size_hash_verified=all(r['size_match'] and r['sha256_verified'] for r in self.records))

class AuditedReaders:
 def __init__(self,vendor_dir):
  vendor=Path(vendor_dir)
  h=reuse_functions(vendor/'stage0_read_himawari.py',['decode_packed','_time'])
  self.decode_b13=h['decode_packed'];self.read_time=h['_time']
  self.decode_imerg=reuse_functions(vendor/'stage0_data_qc.py',['decode_values'])['decode_values']
 def b13(self,path,staging):
  with staging.local(path) as local,netCDF4.Dataset(str(local),'r') as ds:
   ds.set_auto_maskandscale(False)
   v=ds['tbb_13'];lat=np.asarray(ds['latitude'][:]).copy();lon=np.asarray(ds['longitude'][:]).copy()
   if v.dimensions!=('latitude','longitude') or v.shape!=(len(lat),len(lon)):raise ValueError('B13 coordinate/shape mismatch')
   attrs={k:v.getncattr(k) for k in v.ncattrs()}
   if attrs.get('units')!='K':raise ValueError('Unexpected B13 units')
   raw=v[:];x,valid=self.decode_b13(raw,attrs)
   meta=dict(variable='tbb_13',packed_dtype=str(raw.dtype),decoded_dtype=str(x.dtype),original_shape=list(x.shape),attrs=jsonable(attrs),obs_start=self.read_time(ds,'start_time')['iso'],obs_end=self.read_time(ds,'end_time')['iso'],date_created=str(getattr(ds,'date_created')),dimensions=list(v.dimensions))
   return x,valid,lat,lon,meta
 def imerg(self,path,index,staging):
  with staging.local(path) as local,netCDF4.Dataset(str(local),'r') as ds:
   ds.set_auto_maskandscale(False)
   v=ds['precipitation'];attrs={k:v.getncattr(k) for k in v.ncattrs()}
   if v.dimensions!=('time','lat','lon') or attrs.get('units')!='mm hr-1':raise ValueError('IMERG contract mismatch')
   y,valid,_,_=self.decode_imerg(v[index],attrs)
   if np.any(y[valid]<0):raise ValueError('Unexpected negative valid precipitation')
   tv=ds['time'];dt=netCDF4.num2date(tv[index],tv.units,calendar=getattr(tv,'calendar','standard'),only_use_cftime_datetimes=False)
   meta=dict(variable='precipitation',dtype=str(v.dtype),decoded_dtype='float32',original_shape=list(v.shape),dimensions=list(v.dimensions),attrs=jsonable(attrs),converted_time=dt.isoformat()+'Z',converted_time_raw=jsonable(tv[index]),time_units=tv.units,calendar=getattr(tv,'calendar','standard'),native_window='NOT_INFERRED')
   return y.astype(np.float32),valid.astype(bool),np.asarray(ds['lat'][:]).copy(),np.asarray(ds['lon'][:]).copy(),meta

def check_causality(meta):
 a=utc_timestamp(meta['analysis_time']);nom=utc_timestamp(meta['nominal_time'])
 if nom>a or utc_timestamp(meta['obs_end'])>a:raise ValueError('Future Himawari observation rejected')
 if utc_timestamp(meta['obs_start'])>utc_timestamp(meta['obs_end']):raise ValueError('Observation interval inverted')
 return True

def nearest_alignment(x,valid,source_lat,source_lon,target_lat,target_lon):
 """Coordinate-indexed nearest point, no interpolation or invalid-value filling.

 Explicitly gathers descending source rows into ascending target coordinate order.
 """
 for coords in (source_lat,source_lon,target_lat,target_lon):
  delta=np.diff(coords)
  if coords.ndim!=1 or not np.all(np.isfinite(coords)) or not (np.all(delta>0) or np.all(delta<0)):raise ValueError('Nonmonotonic/nonfinite coordinates')
 if target_lat.min()<source_lat.min() or target_lat.max()>source_lat.max() or target_lon.min()<source_lon.min() or target_lon.max()>source_lon.max():raise ValueError('No out-of-domain extrapolation')
 rows=np.abs(source_lat[:,None].astype(np.float64)-target_lat[None,:]).argmin(axis=0)
 cols=np.abs(source_lon[:,None].astype(np.float64)-target_lon[None,:]).argmin(axis=0)
 out=x[np.ix_(rows,cols)].copy();mask=valid[np.ix_(rows,cols)].copy()
 if not np.all(np.isnan(out[~mask])):raise ValueError('Invalid observations must remain NaN')
 info=dict(method='PROVISIONAL_SMOKE_ALIGNMENT: coordinate nearest-neighbor gather',source_row_indices=rows.tolist(),source_col_indices=cols.tolist(),max_abs_lat_offset_degrees=float(np.max(np.abs(source_lat[rows]-target_lat))),max_abs_lon_offset_degrees=float(np.max(np.abs(source_lon[cols]-target_lon))),source_lat_direction='ascending' if source_lat[-1]>source_lat[0] else 'descending',output_lat_direction='ascending' if target_lat[-1]>target_lat[0] else 'descending',source_lon_direction='ascending' if source_lon[-1]>source_lon[0] else 'descending',original_shape=list(x.shape),smoke_shape=list(out.shape),original_lat_range=[float(source_lat.min()),float(source_lat.max())],original_lon_range=[float(source_lon.min()),float(source_lon.max())],output_lat_range=[float(target_lat.min()),float(target_lat.max())],output_lon_range=[float(target_lon.min()),float(target_lon.max())],missing_handling='Preserve NaN and bool mask; never interpolate/fill; no source array flip; explicit index gather only')
 return out,mask,info

class B0SmokeDataset(Dataset):
 def __init__(self,samples,readers,staging,anchor_lat,anchor_lon,crop=(44,76,54,86),cache=True):
  self.samples=samples;self.readers=readers;self.staging=staging
  self.lat=anchor_lat;self.lon=anchor_lon;self.crop=crop;self.cache=cache;self._items={};self.read_reports={}
 def __len__(self):return len(self.samples)
 def __getitem__(self,index):
  if index in self._items:return self._items[index]
  s=self.samples[index]
  x,iv,slat,slon,hm=self.readers.b13(s['himawari_path'],self.staging)
  y,tv,tlat,tlon,im=self.readers.imerg(s['imerg_path'],s['imerg_index'],self.staging)
  if not np.array_equal(tlat,self.lat) or not np.array_equal(tlon,self.lon):raise ValueError('IMERG differs from frozen real coordinates')
  if utc_timestamp(im['converted_time'])!=utc_timestamp(s['imerg_target_time']):raise ValueError('IMERG time index mismatch')
  meta=dict(s,obs_start=hm['obs_start'],obs_end=hm['obs_end'],date_created=hm['date_created'],sample_contract_version=CONTRACT_VERSION)
  check_causality(meta)
  meta.update(imerg_converted_time=im['converted_time'],candidate_analysis_time=s['analysis_time'],selected_himawari_nominal_time=s['nominal_time'],causality_pass=True,mapping_status='ENGINEERING_SMOKE_TIME_MAPPING_ONLY')
  # Recheck the selected observation against P0 metadata. No inferred timestamp repair.
  for field in ['obs_start','obs_end','date_created']:
   if utc_timestamp(meta[field])!=utc_timestamp(s[field]):raise ValueError('Selected source metadata changed: '+field)
  r0,r1,c0,c1=self.crop
  tl=tlat[r0:r1];to=tlon[c0:c1]
  x,iv,align=nearest_alignment(x,iv,slat,slon,tl,to)
  y=y[r0:r1,c0:c1].copy();tv=tv[r0:r1,c0:c1].copy()
  meta.update(time_mapping_scope='ENGINEERING_SMOKE_TIME_MAPPING_ONLY',spatial_scope='ENGINEERING_SMOKE_CROP_ONLY / PROVISIONAL_SMOKE_ALIGNMENT')
  item=dict(x=torch.from_numpy(x[None].copy()),y=torch.from_numpy(y[None].copy()),input_valid_mask=torch.from_numpy(iv[None].copy()),target_valid_mask=torch.from_numpy(tv[None].copy()),metadata=meta)
  self.read_reports[index]=dict(b13=hm,imerg=im,alignment=align,valid_input_cells=int(iv.sum()),valid_target_cells=int(tv.sum()),zero_rain_valid_cells=int(((y==0)&tv).sum()),source_input_invalid_cells=int((~iv).sum()),target_invalid_cells=int((~tv).sum()))
  if self.cache:self._items[index]=item
  return item

def smoke_collate(items):
 return {**{k:torch.stack([x[k] for x in items]) for k in ['x','y','input_valid_mask','target_valid_mask']},'metadata':[x['metadata'] for x in items]}
