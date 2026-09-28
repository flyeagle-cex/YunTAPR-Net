"""Immutable-by-hash scientific artifacts. Call verification before consuming them."""
import hashlib,json
from pathlib import Path
import numpy as np,netCDF4,shapely
from shapely.geometry import shape
IDENTITY={'NAME_1':'Yunnan','GID_1':'CHN.30_1','HASC_1':'CN.YN','ISO_1':'CN-YN','ENGTYPE_1':'Province'}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def coordinate_hash(a):
 a=np.asarray(a,dtype='<f8').copy();a[a==0]=0
 return hashlib.sha256(str(a.shape).encode('ascii')+a.tobytes(order='C')).hexdigest()
def geometry_hash(g):return hashlib.sha256(json.dumps(g,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf8')).hexdigest()
def check_identity(props):
 if any(props.get(k)!=v for k,v in IDENTITY.items()):raise ValueError('Frozen Yunnan identity requires ALL five approved attributes')
def verify_frozen(run):
 run=Path(run);r=json.loads((run/'freeze_registry.json').read_text(encoding='utf8'))
 for label,item in r['artifacts'].items():
  p=(run/item['relative_path']).resolve()
  if not p.is_relative_to(run.resolve()) or sha(p)!=item['sha256']:raise ValueError('Frozen artifact changed: '+label)
 b=json.loads((run/r['artifacts']['boundary']['relative_path']).read_text(encoding='utf8'));feat=b['features'][0];check_identity(feat['properties'])
 if geometry_hash(feat['geometry'])!=r['boundary']['geometry_sha256']:raise ValueError('Geometry hash mismatch')
 refs=np.load(run/r['artifacts']['coordinates']['relative_path'])
 with netCDF4.Dataset(str(run/r['artifacts']['primary_mask']['relative_path']),'r') as ds:
  lat=np.array(ds['lat'][:]);lon=np.array(ds['lon'][:]);mask=np.array(ds['yunnan_mask'][:]);dims=ds['yunnan_mask'].dimensions
 if dims!=('lat','lon') or mask.shape!=(130,140) or not np.array_equal(lat,refs['lat']) or not np.array_equal(lon,refs['lon']):raise ValueError('Frozen grid alignment changed')
 if not np.all(np.diff(lat)>0) or not np.all(np.diff(lon)>0) or int(mask.sum())!=3430 or not set(np.unique(mask))<={0,1}:raise ValueError('Frozen mask convention changed')
 if coordinate_hash(lat)!=r['mask']['lat_hash'] or coordinate_hash(lon)!=r['mask']['lon_hash']:raise ValueError('Coordinate hash mismatch')
 x,y=np.meshgrid(lon,lat,indexing='xy');expected=shapely.contains_xy(shape(feat['geometry']),x,y)
 if not np.array_equal(mask,expected):raise ValueError('Mask differs from approved center-in-polygon geometry')
 return {'status':'PASS','shape':list(mask.shape),'true_cells':int(mask.sum()),'boundary_all_identity_fields_match':True,'lat_exact_match':True,'lon_exact_match':True}
