import sys,json,zipfile,shutil,hashlib,time,importlib.metadata as metadata
from pathlib import Path
from datetime import datetime,timezone
import numpy as np,pandas as pd,netCDF4,shapely,pyproj
from shapely.geometry import shape
from config import *
from frozen_contract import *
sys.stdout.reconfigure(encoding='utf8')
def write(rel,v):
 p=OUT/rel;assert p.resolve().is_relative_to(OUT.resolve())
 with p.open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False)
def txt(rel,v):
 with (OUT/rel).open('x',encoding='utf8') as f:f.write(v)
inputs={}
def protect(p,hashit=True):
 p=Path(p);s=p.stat()
 if str(p) not in inputs:inputs[str(p)]={'size':s.st_size,'mtime_ns':s.st_mtime_ns,'sha256':sha(p) if hashit else None}
 return p
oldmanifest={r['relative_path'].replace('\\','/'):r for r in pd.read_csv(BASE/'output_manifest.csv',keep_default_na=False).to_dict('records')};protect(BASE/'output_manifest.csv')
def previous(rel):
 p=protect(BASE/rel)
 assert sha(p)==oldmanifest[rel]['sha256'],f'Prior output changed: {rel}'
 return p
old_protection=json.loads(previous('logs/input_protection_before.json').read_text(encoding='utf8'))
def copy(src,rel):
 src=protect(src);dst=OUT/rel;assert dst.resolve().is_relative_to(OUT.resolve())
 if dst.exists():
  assert sha(src)==sha(dst),'Existing new-run copy differs; do not overwrite';return dst
 with src.open('rb') as a,dst.open('xb') as b:shutil.copyfileobj(a,b)
 assert sha(src)==sha(dst);return dst
# Verify every adopted old artifact against that run's completed output manifest.
for rel in ['audit_final_status.json','DEM/dem_audit_summary.json','DEM/dem_inventory.csv','MASK/polygon_selection_evidence.json','MASK/imerg_coordinate_reuse.json','MASK/imerg_actual_coordinates.npz','MASK/mask_engineering_result.json','MASK/engineering_polygon_candidate.geojson','MASK/yunnan_imerg_mask_center_candidate.nc','MASK/yunnan_imerg_mask_intersection_candidate.nc','MASK/yunnan_imerg_mask_comparison.csv','src/build_masks.py','src/spatial_rules.py','src/config.py','src/common.py']:
 previous(rel)
archive=protect(DATA/'raw/BOUNDARY/GADM41/gadm41_CHN_1.json.zip')
assert sha(archive)==old_protection[str(archive)]['sha256']
archive_copy=copy(archive,'FROZEN/BOUNDARY/gadm41_CHN_1.source.json.zip')
with zipfile.ZipFile(archive) as z:
 member='gadm41_CHN_1.json';member_bytes=z.read(member);doc=json.loads(member_bytes)
selected=[(n,f) for n,f in enumerate(doc['features']) if all(f.get('properties',{}).get(k)==v for k,v in IDENTITY.items())];assert len(selected)==1
idx,feature=selected[0];check_identity(feature['properties']);poly=shape(feature['geometry']);assert poly.is_valid and not poly.is_empty
candidate=shape(json.loads((BASE/'MASK/engineering_polygon_candidate.geojson').read_text(encoding='utf8'))['features'][0]['geometry']);assert poly.equals(candidate) and shapely.normalize(shapely.union_all([poly])).equals_exact(shapely.normalize(candidate),0)
write('PROVENANCE/geometry_representation_comparison.json',{'raw_type':poly.geom_type,'candidate_type':candidate.geom_type,'topological_equal':True,'normalized_union_exact':True,'symmetric_difference_area':poly.symmetric_difference(candidate).area,'raw_coordinate_points':int(shapely.get_num_coordinates(poly)),'candidate_coordinate_points':int(shapely.get_num_coordinates(candidate)),'formal_boundary_preserves_raw_geometry':True,'old_candidate_unchanged':True})
crs=doc['crs'];assert pyproj.CRS.from_user_input(crs['properties']['name']).equals(pyproj.CRS.from_user_input('OGC:CRS84'))
member_path=OUT/'PROVENANCE/gadm41_CHN_1.original_member.json'
with member_path.open('xb') as f:f.write(member_bytes)
write('FROZEN/BOUNDARY/yunnan_gadm41_level1_boundary.geojson',{'type':'FeatureCollection','name':'YunTAPR_Yunnan_GADM41_Level1_FROZEN_v1','crs':crs,'features':[feature]})
coords=copy(BASE/'MASK/imerg_actual_coordinates.npz','FROZEN/MASK/imerg_actual_coordinates.npz');ref=np.load(coords);lat=ref['lat'];lon=ref['lon'];reference=json.loads((BASE/'MASK/imerg_coordinate_reuse.json').read_text(encoding='utf8'))
assert coordinate_hash(lat)==reference['lat_hash'] and coordinate_hash(lon)==reference['lon_hash']
# One bounded English staging copy of the previously audited raw IMERG file, coordinate-only reread.
raw_ref=protect(Path(reference['source']));assert sha(raw_ref)==old_protection[str(raw_ref)]['sha256'];CACHE.mkdir(parents=True);temp=CACHE/'owned_imerg_coordinate_reference.nc';t=time.perf_counter()
with raw_ref.open('rb') as a,temp.open('xb') as b:shutil.copyfileobj(a,b)
copy_seconds=time.perf_counter()-t;assert temp.stat().st_size==raw_ref.stat().st_size and sha(temp)==sha(raw_ref)
try:
 with netCDF4.Dataset(str(temp),'r') as ds:
  rlat=np.array(ds['lat'][:]);rlon=np.array(ds['lon'][:])
 assert np.array_equal(lat,rlat) and np.array_equal(lon,rlon)
finally:
 assert temp.resolve().parent==CACHE.resolve() and temp.resolve().is_relative_to((PROJECT/'cache').resolve());temp.unlink()
write('logs/staging_summary.json',{'copy_count':1,'cumulative_bytes':raw_ref.stat().st_size,'max_single_copy':raw_ref.stat().st_size,'copy_seconds':copy_seconds,'sha256_verified':True,'cleanup_failures':0,'remaining_staged_bytes':0,'remaining_files':[p.name for p in CACHE.iterdir()]})
# Preserve byte-identical scientific arrays and original candidate; only official-copy global metadata is updated.
source_center=copy(BASE/'MASK/yunnan_imerg_mask_center_candidate.nc','PROVENANCE/adopted_center_candidate.nc')
primary=copy(BASE/'MASK/yunnan_imerg_mask_center_candidate.nc','FROZEN/MASK/yunnan_evaluation_mask_center_gadm41_imerg_v1.nc')
intersection=copy(BASE/'MASK/yunnan_imerg_mask_intersection_candidate.nc','COMPARISON/yunnan_imerg_mask_intersection_candidate.nc')
copy(BASE/'MASK/yunnan_imerg_mask_comparison.csv','COMPARISON/previous_mask_comparison.csv')
with netCDF4.Dataset(str(primary),'r+') as ds:
 ds.candidate_only='false';ds.scientific_mask_convention_frozen='true';ds.artifact_status='FROZEN';ds.evaluation_role='PRIMARY_YUNNAN_EVALUATION_MASK';ds.researcher_approval='Explicit user Stage-0 spatial decision';ds.frozen_version_id='YunTAPR_STAGE0_SPATIAL_v1_'+OUT.name
 ds.boundary_rule='center-in-polygon: strict interior (contains), inherited from researcher-approved 3430-cell candidate; exact-boundary center count=0'
 ds.source_polygon=str(OUT/'FROZEN/BOUNDARY/yunnan_gadm41_level1_boundary.geojson');ds.source_boundary_archive=str(archive);ds.source_candidate=str(BASE/'MASK/yunnan_imerg_mask_center_candidate.nc');ds.cell_edge_definition='Retained candidate midpoint-derived cell bounds for provenance; bounds are not used by frozen center rule and do not freeze model-input or DEM aggregation conventions'
with netCDF4.Dataset(str(source_center),'r') as old,netCDF4.Dataset(str(primary),'r') as new:
 assert list(old.variables)==list(new.variables)
 for name in old.variables:
  assert old[name].dtype==new[name].dtype and old[name].dimensions==new[name].dimensions and np.array_equal(old[name][:],new[name][:]),name
 mask=np.array(new['yunnan_mask'][:]);assert mask.shape==(130,140) and mask.sum()==3430
 x,y=np.meshgrid(lon,lat,indexing='xy');assert np.array_equal(mask,shapely.contains_xy(poly,x,y))
 assert shapely.intersects_xy(poly.boundary,x,y).sum()==0
# Root registration preserves per-file inventory; no DEM payload processing/resampling.
demroot=DATA/'raw/SRTM';oldinventory=pd.read_csv(BASE/'DEM/dem_inventory.csv',keep_default_na=False);registered=[]
for r in oldinventory[oldinventory.root=='SRTM'].to_dict('records'):
 p=DATA/r['relative_path'];prior=old_protection[str(p)];protect(p,prior['sha256'] is not None);s=p.stat()
 assert s.st_size==prior['size']==r['size_bytes'] and s.st_mtime_ns==prior['mtime_ns']
 if prior['sha256'] is not None:assert sha(p)==prior['sha256']
 registered.append({'path':str(p),'size_bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'sha256_sampled':prior['sha256'] or 'NOT_SAMPLED','source_role':'FORMAL_PRIMARY_DEM_ROOT','coverage_evidence':str(BASE/'DEM/dem_audit_summary.json')})
assert len(registered)==237 and {p.name for p in demroot.iterdir() if p.is_file()}=={Path(r['path']).name for r in registered}
pd.DataFrame(registered).to_csv(OUT/'DEM/frozen_primary_root_inventory.csv',index=False,encoding='utf-8-sig')
demsummary=json.loads((BASE/'DEM/dem_audit_summary.json').read_text(encoding='utf8'));assert demsummary['SRTM']['yunnan_coverage']=='FULL' and demsummary['SRTM']['yunnan_invalid_touched_cells']==0
copy(BASE/'DEM/dem_audit_summary.json','DEM/prior_coverage_evidence.json')
# Preserve the exact source code that produced the adopted candidate and the current formalization code hash.
generators=[]
for name in ['build_masks.py','spatial_rules.py','config.py','common.py']:
 dst=copy(BASE/'src'/name,'PROVENANCE/source_generator_'+name);generators.append({'original_path':str(BASE/'src'/name),'snapshot_relative_path':str(dst.relative_to(OUT)),'sha256':sha(dst),'role':'previous_candidate_generation_source'})
for name in ['freeze.py','frozen_contract.py','config.py']:generators.append({'path':str(OUT/'src'/name),'sha256':sha(OUT/'src'/name),'role':'current_formalization_or_validation_source'})
write('PROVENANCE/generator_script_hashes.json',generators)
artifacts={}
for label,p in [('archive',archive_copy),('original_geojson_member',member_path),('boundary',OUT/'FROZEN/BOUNDARY/yunnan_gadm41_level1_boundary.geojson'),('coordinates',coords),('primary_mask',primary),('adopted_candidate',source_center),('intersection_comparison',intersection)]:artifacts[label]={'relative_path':str(p.relative_to(OUT)),'sha256':sha(p),'size_bytes':p.stat().st_size,'role':'NON_PRIMARY_BOUNDARY_SENSITIVITY_COMPARISON' if label=='intersection_comparison' else 'FROZEN_PRIMARY_EVALUATION_MASK' if label=='primary_mask' else 'FROZEN_BOUNDARY' if label=='boundary' else 'PROVENANCE_OR_COORDINATE_ANCHOR'}
geometry_sha=geometry_hash(feature['geometry']);normalized_wkb=shapely.to_wkb(shapely.normalize(poly),byte_order=1,output_dimension=2,include_srid=False)
registry={'freeze_id':'YunTAPR_STAGE0_SPATIAL_v1_'+OUT.name,'decision_authority':'RESEARCHER_EXPLICIT_APPROVAL_THIS_USER_MESSAGE','approved_scope':'Current formal spatial execution convention only; no next Stage','created_utc':datetime.now(timezone.utc).isoformat(),'immutable_policy':'Never replace files or registry silently. Verify SHA256 before use via src/frozen_contract.py. Any scientific version change requires an explicit researcher decision and a new run; preserve this run. No OS-level immutability claim.','artifacts':artifacts,'boundary':{'status':'FROZEN','version':'GADM 4.1','administrative_level':1,'original_archive_path':str(archive),'original_archive_sha256':sha(archive),'archive_member':member,'member_sha256':hashlib.sha256(member_bytes).hexdigest(),'feature_index_zero_based':idx,'feature_identifier':'CHN.30_1','required_identity_fields':IDENTITY,'crs':crs,'axis_order':'longitude,latitude','geometry_type':poly.geom_type,'geometry_sha256':geometry_sha,'geometry_hash_definition':'SHA256 UTF-8 JSON original geometry; sorted keys; compact separators; ensure_ascii=False; no rounding/reordering of coordinate arrays','normalized_wkb_sha256':hashlib.sha256(normalized_wkb).hexdigest(),'normalized_wkb_definition':'shapely.normalize; 2D little-endian WKB, no SRID; supplementary geometric fingerprint','shapely_version':shapely.__version__,'bounds':list(poly.bounds),'provenance':'Selected the sole raw GADM41 CHN level-1 feature matching ALL five approved identity attributes; raw geometry unchanged; topologically equals audited candidate, normalized single-union representation exactly matches; raw MultiPolygon and old Polygon differ in representation only; archive/hash linked to prior audit. Local artifact adoption is researcher-approved. No new official download receipt/authentication claimed.'},'mask':{'status':'FROZEN','role':'PRIMARY_EVALUATION','rule':'CENTER_IN_POLYGON','predicate':'strict interior contains, inherited from approved candidate','exact_boundary_center_count':0,'shape':[130,140],'true_cells':3430,'false_cells':14770,'dimensions':['lat','lon'],'lat_direction':'ascending','lon_direction':'ascending','lat_dtype':str(lat.dtype),'lon_dtype':str(lon.dtype),'lat_hash':coordinate_hash(lat),'lon_hash':coordinate_hash(lon),'coordinate_hash_definition':'SHA256 ASCII shape + canonical little-endian float64 numeric values C-order; signed zero normalized','raw_imerg_coordinate_source':str(raw_ref),'raw_imerg_source_sha256':sha(raw_ref),'prior_formal_grid_audit':reference['prior_formal_grid_audit'],'actual_raw_coordinates_reread_equal':True,'generated_coordinates':False,'candidate_source':str(BASE/'MASK/yunnan_imerg_mask_center_candidate.nc'),'candidate_source_sha256':sha(source_center),'all_variable_arrays_unchanged_from_candidate':True,'only_global_metadata_updated_on_new_copy':True},'dem':{'primary_source_status':'FROZEN','primary_root':str(demroot),'registered_files':237,'coverage':'FULL_FOR_FROZEN_YUNNAN_POLYGON','coverage_evidence':str(BASE/'DEM/dem_audit_summary.json'),'inventory':'DEM/frozen_primary_root_inventory.csv','inventory_sha256':sha(OUT/'DEM/frozen_primary_root_inventory.csv'),'auxiliary_root':str(DATA/'raw/AWS_Skadi'),'auxiliary_status':'SEPARATE_NOT_MERGED_NOT_DELETED','production_processing_frozen':False},'frozen_principles':['Final main evaluation uses whole Yunnan provincial administrative mask','DOTE terrain gradients must use real physical distances, never longitude/latitude index gradients'],'not_yet_frozen':['model_input_bbox','weather_system_context_margin','DEM_aggregation_method','slope_aspect_relief_curvature_parameters','dh_dx_dh_dy_formal_production_pipeline'],'common_numerical_overlap':{'designation':'CANDIDATE COMMON NUMERICAL OVERLAP','lon_min':97.0,'lon_max':107.0,'lat_min':20.0,'lat_max':30.0,'is_model_input_bbox':False},'intersection':{'role':'BOUNDARY_SENSITIVITY_ENGINEERING_COMPARISON','is_primary_evaluation_mask':False,'preserved_byte_identical':True,'true_cells':3752,'difference_cells':322},'execution_limits':{'start_B0':False,'DEM_resampling':False,'formal_DOTE_features':False,'next_stage_automatically':False},'generator_script_hashes':'PROVENANCE/generator_script_hashes.json'}
write('freeze_registry.json',registry)
write('logs/input_protection_before.json',inputs)
write('logs/formalization_checks.json',verify_frozen(OUT))
print(json.dumps({'run':str(OUT),'identity':IDENTITY,'geometry_sha256':geometry_sha,'archive_sha256':sha(archive),'formal_mask_sha256':sha(primary),'formalization_checks':verify_frozen(OUT),'protected_inputs':len(inputs)}))

