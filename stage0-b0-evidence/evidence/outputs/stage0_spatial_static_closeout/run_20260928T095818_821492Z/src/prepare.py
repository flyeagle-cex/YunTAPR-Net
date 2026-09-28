import sys,json,zipfile,subprocess,importlib.metadata as m
import numpy as np,pandas as pd,netCDF4,rasterio,shapely,pyproj
from shapely.geometry import shape,mapping
from shapely.ops import transform,unary_union
from config import *
from common import *
sys.stdout.reconfigure(encoding='utf8')
before=readj('logs/environment_before.json');after={x.metadata['Name']:x.version for x in m.distributions()}
changed={k:[v,after.get(k)] for k,v in before['packages'].items() if after.get(k)!=v};added={k:v for k,v in after.items() if k not in before['packages']};assert not changed
writej('logs/dependency_change_record.json',{'python':sys.executable,'added':added,'existing_changed':changed,'existing_removed':[],'rasterio':rasterio.__version__,'gdal':rasterio.__gdal_version__,'shapely':shapely.__version__,'pyproj':pyproj.__version__,'minimal_install':True,'geopandas_not_required':'GeoJSON loaded with stdlib json; geometry via shapely','protected_original_packages':before['packages']})
roots=[DATA/'raw/SRTM',DATA/'raw/AWS_Skadi'];dem=[]
for root in roots:
 for i,p in enumerate(sorted(root.rglob('*'))):
  if p.is_file():protect(p,hash_sample=i in [0,100,200]);dem.append({'path':str(p),'root':str(root),'extension':''.join(p.suffixes),'size_bytes':p.stat().st_size})
# Additional bounded file-name discovery in relevant static roots and project text/spatial files, not other raw datasets.
args=['rg','--files',str(PROJECT),'-g','*.geojson','-g','*.shp','-g','*.gpkg','-g','*boundary*.json','-g','*yunnan*.json','-g','!**/.venv/**','-g','!**/cache/**','-g','!**/outputs/**']
r=subprocess.run(args,capture_output=True,text=True,encoding='utf8');assert r.returncode in [0,1]
bounds=sorted(list((DATA/'raw/BOUNDARY').rglob('*.zip'))+list((DATA/'processed/boundary').rglob('*.geojson'))+[Path(x) for x in r.stdout.splitlines() if x])
old=PROJECT/'outputs/stage0_p0_audit/run_20260927T161311_417313Z'
gfs=PROJECT/'outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/GFS/gfs_grid_audit.csv'
him=PROJECT/'stage0_himawari/outputs/202407/resume_20260927T104625_772423Z/qc/grid_consistency_report_202407.csv'
for p in [old/'IMERG/imerg_grid_audit.csv',gfs,him,PROJECT/'outputs/stage0_gfs_provenance_vintage_resolution/run_20260928T092552_449937Z/audit_final_status.json',DATA/'manifests/srtm_manifest.jsonl']:
 protect(p,True)
writej('logs/discovery_scope.json',{'dem_roots':roots,'multiple_dem_roots_status':'MULTIPLE_DEM_ROOTS_RESEARCHER_REVIEW','dem_files':dem,'boundary_candidates':bounds,'project_boundary_search':args,'search_return_code':r.returncode,'excluded':'Other raw datasets, all-disk search, old output recursion','legacy_static_products':[str(p) for p in (DATA/'processed').glob('*topograph*.nc')],'grid_evidence':{'imerg':str(old/'IMERG/imerg_grid_audit.csv'),'gfs':str(gfs),'himawari':str(him)}})
features=[];summaries=[];geoms={}
for p in bounds:
 protect(p,True)
 if p.suffix=='.zip':
  with zipfile.ZipFile(p) as z:
   names=[n for n in z.namelist() if n.endswith(('.json','.geojson'))];assert len(names)==1;doc=json.loads(z.read(names[0]));member=names[0]
 else:doc=json.loads(p.read_text(encoding='utf8'));member=''
 crs_name=doc.get('crs',{}).get('properties',{}).get('name');crs=pyproj.CRS.from_user_input(crs_name) if crs_name else None
 ys=[];seen=set()
 for idx,feat in enumerate(doc['features']):
  props=feat.get('properties',{});identity=props.get('NAME_1')=='Yunnan' or props.get('ISO_1')=='CN-YN' or props.get('HASC_1')=='CN.YN'
  if not identity:continue
  geom=shape(feat['geometry']);valid=geom.is_valid;fix=shapely.make_valid(geom) if not valid else geom
  if crs is not None and not crs.equals(pyproj.CRS.from_user_input('OGC:CRS84')):
   tr=pyproj.Transformer.from_crs(crs,'OGC:CRS84',always_xy=True);mapped=transform(tr.transform,fix)
  else:mapped=fix
  polys=list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom];holes=sum(len(g.interiors) for g in polys if g.geom_type=='Polygon');key=geom.wkb_hex
  features.append(dict(path=str(p),archive_member=member,feature_index=idx,geometry_type=geom.geom_type,source_geometry_status='SOURCE_GEOMETRY_VALID' if valid else 'SOURCE_GEOMETRY_INVALID_BUT_REPAIRABLE_IN_MEMORY' if fix.is_valid else 'SOURCE_GEOMETRY_INVALID_UNRESOLVED',validity_reason=shapely.is_valid_reason(geom),empty=geom.is_empty,duplicate_geometry=key in seen,multipart=len(polys)>1,parts=len(polys),holes=holes,bounds=json.dumps(geom.bounds),native_area=geom.area,native_area_units='degree_squared_NOT_km2' if crs and crs.is_geographic else 'native_crs_squared',crs=crs_name or 'CRS_NOT_ESTABLISHED',identity='ATTRIBUTE_SUPPORTED_YUNNAN',properties=json.dumps(props,ensure_ascii=False),source_version_evidence='GADM41 path/member name and GADM field schema; upstream checksum receipt not located'))
  seen.add(key);ys.append(mapped)
 if ys:
  union=unary_union(ys);geoms[str(p)]=union
  summaries.append({'path':str(p),'member':member,'all_features':len(doc['features']),'yunnan_features':len(ys),'crs':crs_name,'union_valid':union.is_valid,'bounds':union.bounds,'identity':'ATTRIBUTE_SUPPORTED_YUNNAN','source_version':'GADM 4.1 declared by archive/member naming; not independently authenticated'})
 csv('MASK/yunnan_polygon_features.csv',features)
writej('MASK/boundary_candidate_summary.json',summaries)
# Most obvious candidate: raw level-1 province feature; no final scientific selection.
selected=next(str(p) for p in bounds if p.name=='gadm41_CHN_1.json.zip');poly=geoms[selected]
assert poly.is_valid and not poly.is_empty
writej('MASK/engineering_polygon_candidate.geojson',{'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'urn:ogc:def:crs:OGC:1.3:CRS84'}},'candidate_only':True,'source':selected,'features':[{'type':'Feature','properties':{'NAME_1':'Yunnan','scientific_approval':False},'geometry':mapping(poly)}]})
writej('MASK/polygon_selection_evidence.json',{'selected_for_engineering_only':selected,'multiple_candidate_status':'MULTIPLE_BOUNDARY_CANDIDATES_RESEARCHER_REVIEW','raw_vs_processed_level1_exact_geometry':poly.equals_exact(geoms[str(DATA/'processed/boundary/Yunnan_GADM41_level1.geojson')],0),'bounds':poly.bounds,'final_scientific_boundary_frozen':False,'crs_transform_always_xy':True,'geometries':summaries})
# Recover actual saved coordinates, first from legacy mask, then only one baseline-referenced IMERG file if needed.
reference=pd.read_csv(old/'IMERG/imerg_grid_audit.csv').iloc[0]
coord_attempts=[];chosen=None
for p in [DATA/'processed/yunnan_evaluation_mask_0p1deg.nc',DATA/'raw/IMERG'/reference.relative_path]:
 protect(p,True)
 # netCDF4 English staging is the already verified Windows workaround; one very small file.
 with staging(p) as local:
  with netCDF4.Dataset(str(local),'r') as ds:
   latkey=next(k for k in ['lat','latitude'] if k in ds.variables);lonkey=next(k for k in ['lon','longitude'] if k in ds.variables)
   lat=np.array(ds[latkey][:]);lon=np.array(ds[lonkey][:]);la=coordhash(lat);lo=coordhash(lon)
  ok=la==reference.lat_hash and lo==reference.lon_hash
  coord_attempts.append({'source':str(p),'lat_hash':la,'lon_hash':lo,'exact_hash_match_prior_formal_audit':ok})
  if ok:chosen=p;break
assert chosen is not None and lat.shape==(130,) and lon.shape==(140,) and np.all(np.diff(lat)>0) and np.all(np.diff(lon)>0)
np.savez(OUT/'MASK/imerg_actual_coordinates.npz',lat=lat,lon=lon)
writej('MASK/imerg_coordinate_reuse.json',{'source':str(chosen),'prior_formal_grid_audit':str(old/'IMERG/imerg_grid_audit.csv'),'reference_source_filename':reference.relative_path,'lat_hash':coordhash(lat),'lon_hash':coordhash(lon),'shape':[130,140],'lat_dtype':str(lat.dtype),'lon_dtype':str(lon.dtype),'attempts':coord_attempts,'coordinate_array_synthesized':False,'ascending_preserved':True})
# Probe exact zip member/georeferencing without reading all raster pixels yet.
p=Path(dem[0]['path'])
with rasterio.Env(GDAL_PAM_ENABLED='NO'):
 with zipfile.ZipFile(p) as z: member=next(n for n in z.namelist() if n.lower().endswith('.hgt'))
 with rasterio.open('/vsizip/'+p.as_posix()+'/'+member,'r') as ds:
  info={'path':str(p),'member':member,'driver':ds.driver,'crs':str(ds.crs),'shape':ds.shape,'bounds':list(ds.bounds),'transform':list(ds.transform),'nodata':ds.nodata,'units':ds.units,'tags':ds.tags(),'probe':ds.read(1,window=((0,2),(0,2))).tolist()}
writej('DEM/first_raster_probe.json',info)
print(json.dumps({'dem_files':len(dem),'roots':len(roots),'boundary_candidates':summaries,'coordinate_reuse':str(chosen),'raster_probe':info,'dependency_added':added},ensure_ascii=False))
