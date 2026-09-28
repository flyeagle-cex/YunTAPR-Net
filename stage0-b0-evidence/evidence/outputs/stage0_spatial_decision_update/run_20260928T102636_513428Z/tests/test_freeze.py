import json,shutil
from pathlib import Path
import pytest,numpy as np,netCDF4,shapely
from shapely.geometry import shape
from config import OUT,BASE,CACHE
from frozen_contract import *
def registry():return json.loads((OUT/'freeze_registry.json').read_text(encoding='utf8'))
def artifact(key):return OUT/registry()['artifacts'][key]['relative_path']
def test_complete_frozen_contract():assert verify_frozen(OUT)['status']=='PASS'
@pytest.mark.parametrize('key',list(IDENTITY))
def test_all_five_identity_fields_required(key):
 p=IDENTITY.copy();p[key]='not-approved'
 with pytest.raises(ValueError):check_identity(p)

def test_boundary_original_structure_and_geometry_hash():
 r=registry();raw=json.loads(artifact('original_geojson_member').read_text(encoding='utf8'));f=raw['features'][r['boundary']['feature_index_zero_based']];formal=json.loads(artifact('boundary').read_text(encoding='utf8'))['features'][0]
 assert formal==f and formal['geometry']['type']=='MultiPolygon';assert geometry_hash(formal['geometry'])==r['boundary']['geometry_sha256'];check_identity(formal['properties'])

def test_representation_difference_has_zero_spatial_difference():
 raw=shape(json.loads(artifact('boundary').read_text(encoding='utf8'))['features'][0]['geometry']);old=shape(json.loads((BASE/'MASK/engineering_polygon_candidate.geojson').read_text(encoding='utf8'))['features'][0]['geometry'])
 assert raw.geom_type=='MultiPolygon' and old.geom_type=='Polygon' and raw.equals(old) and raw.symmetric_difference(old).area==0

def test_formal_mask_shape_and_true_count():
 with netCDF4.Dataset(str(artifact('primary_mask')),'r') as ds:assert ds['yunnan_mask'].shape==(130,140) and int(ds['yunnan_mask'][:].sum())==3430

def test_exact_real_imerg_coordinates_and_dtype():
 ref=np.load(artifact('coordinates'));r=registry()
 with netCDF4.Dataset(str(artifact('primary_mask')),'r') as ds:
  for name in ['lat','lon']:
   assert np.array_equal(ds[name][:],ref[name]);assert ds[name].dtype==ref[name].dtype;assert coordinate_hash(ds[name][:])==r['mask'][name+'_hash']
 assert r['mask']['actual_raw_coordinates_reread_equal'] and not r['mask']['generated_coordinates']

def test_lat_ascending_no_transpose_or_silent_flip():
 with netCDF4.Dataset(str(artifact('primary_mask')),'r') as ds:
  assert ds['yunnan_mask'].dimensions==('lat','lon');assert np.all(np.diff(ds['lat'][:])>0) and np.all(np.diff(ds['lon'][:])>0)
 with netCDF4.Dataset(str(artifact('adopted_candidate')),'r') as old,netCDF4.Dataset(str(artifact('primary_mask')),'r') as new:
  for key in old.variables:assert np.array_equal(old[key][:],new[key][:]) and old[key].dimensions==new[key].dimensions

def test_primary_metadata_formalized():
 with netCDF4.Dataset(str(artifact('primary_mask')),'r') as ds:
  assert ds.candidate_only=='false' and ds.scientific_mask_convention_frozen=='true' and ds.evaluation_role=='PRIMARY_YUNNAN_EVALUATION_MASK'

def test_center_predicate_matches_approved_original_geometry():
 p=shape(json.loads(artifact('boundary').read_text(encoding='utf8'))['features'][0]['geometry'])
 with netCDF4.Dataset(str(artifact('primary_mask')),'r') as ds:
  x,y=np.meshgrid(ds['lon'][:],ds['lat'][:],indexing='xy');assert np.array_equal(ds['yunnan_mask'][:],shapely.contains_xy(p,x,y));assert shapely.intersects_xy(p.boundary,x,y).sum()==0

def test_intersection_retained_nonprimary_byte_identical():
 r=registry();assert not r['intersection']['is_primary_evaluation_mask'];assert sha(artifact('intersection_comparison'))==sha(BASE/'MASK/yunnan_imerg_mask_intersection_candidate.nc')
 with netCDF4.Dataset(str(artifact('intersection_comparison')),'r') as b,netCDF4.Dataset(str(artifact('primary_mask')),'r') as a:assert int(b['yunnan_mask'][:].sum())==3752 and int((b['yunnan_mask'][:]-a['yunnan_mask'][:]).sum())==322

def test_source_generator_hashes_unchanged():
 for s in json.loads((OUT/'PROVENANCE/generator_script_hashes.json').read_text(encoding='utf8')):
  assert sha(OUT/s['snapshot_relative_path'] if 'snapshot_relative_path' in s else s['path'])==s['sha256']

def test_srtm_source_only_frozen_not_production():
 d=registry()['dem'];assert d['primary_source_status']=='FROZEN' and d['registered_files']==237 and not d['production_processing_frozen'];assert d['auxiliary_status']=='SEPARATE_NOT_MERGED_NOT_DELETED'

def test_bbox_context_terrain_still_not_frozen():
 r=registry();assert set(r['not_yet_frozen'])=={'model_input_bbox','weather_system_context_margin','DEM_aggregation_method','slope_aspect_relief_curvature_parameters','dh_dx_dh_dy_formal_production_pipeline'}
 assert not r['common_numerical_overlap']['is_model_input_bbox'];assert r['common_numerical_overlap']['designation']=='CANDIDATE COMMON NUMERICAL OVERLAP'
 assert all(v is False for v in r['execution_limits'].values())

def test_scientific_physical_distance_principle_frozen():assert any('real physical distances' in s for s in registry()['frozen_principles'])

def test_old_sources_still_match_before_hashes():
 for p,r in json.loads((OUT/'logs/input_protection_before.json').read_text(encoding='utf8')).items():
  s=Path(p).stat();assert s.st_size==r['size'] and s.st_mtime_ns==r['mtime_ns']
  if r['sha256'] is not None:assert sha(p)==r['sha256']

def test_integrity_and_cache():
 i=json.loads((OUT/'logs/integrity_summary.json').read_text(encoding='utf8'));assert i['all_size_mtime_unchanged'] and i['sha256_all_checked_unchanged'] and i['dependencies_unchanged'];assert not list(CACHE.iterdir())

def test_silent_artifact_replacement_is_rejected(tmp_path):
 # Only process-owned copies in the explicit new-run pytest temp directory are mutated.
 assert tmp_path.resolve().is_relative_to((OUT/'tests/tmp').resolve())
 r=registry();(tmp_path/'freeze_registry.json').write_text(json.dumps(r),encoding='utf8')
 try:
  for a in r['artifacts'].values():
   dest=tmp_path/a['relative_path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OUT/a['relative_path'],dest)
  target=tmp_path/r['artifacts']['primary_mask']['relative_path']
  with target.open('ab') as f:f.write(b'changed')
  with pytest.raises(ValueError,match='Frozen artifact changed'):verify_frozen(tmp_path)
 finally:
  for p in tmp_path.rglob('*'):
   assert p.resolve().is_relative_to(tmp_path.resolve())
   if p.is_file():p.unlink()
