import json
from pathlib import Path
import numpy as np,pandas as pd,pytest,netCDF4,rasterio,shapely,pyproj
from shapely.geometry import box,Polygon,shape
from config import OUT,CACHE
from common import readj,coordhash,hashfile,writej
from spatial_rules import *

def test_actual_dem_crs_reading():
 r=readj('DEM/first_raster_probe.json');uri='/vsizip/'+Path(r['path']).as_posix()+'/'+r['member']
 with rasterio.Env(GDAL_PAM_ENABLED='NO'):
  with rasterio.open(uri,'r') as ds:assert ds.crs.to_epsg()==4326 and ds.mode=='r' and ds.tags()['AREA_OR_POINT']=='Point'

def test_nodata_negative_and_zero_preserved():
 a=np.array([-32768,-468,0,7439,np.nan,np.inf]);copy=a.copy();assert np.array_equal(valid_mask(a,-32768),[False,True,True,True,False,False]);np.testing.assert_equal(a,copy)

def test_gap_detection():
 x=footprint_topology([box(0,0,1,1),box(2,0,3,1)]);assert x['gap'].area==pytest.approx(1) and x['overlap_area']==0

def test_overlap_detection():
 x=footprint_topology([box(0,0,2,1),box(1,0,3,1)]);assert x['overlap_area']==pytest.approx(1) and x['gap'].area==0

def test_real_tile_gaps_and_shared_edges():
 s=readj('DEM/dem_audit_summary.json');assert s['SRTM']['nominal_gap_area_deg2']==pytest.approx(3)
 assert s['SRTM']['nominal_duplicate_footprints']==0 and s['SRTM']['support_overlap_area_deg2']>0
 edges=pd.read_csv(OUT/'DEM/dem_shared_edge_comparison.csv');assert len(edges)==440 and edges.unequal_count.sum()==0

def test_all_dem_resolutions_match_actual_inventory():
 d=pd.read_csv(OUT/'DEM/dem_inventory.csv',float_precision='round_trip');assert len(d)==240 and (d.width==3601).all() and (d.height==3601).all()
 assert set(d.crs)=={'EPSG:4326'};assert np.allclose(d.resolution_x,1/3600,rtol=0,atol=1e-17)

def test_polygon_source_validity():
 p=shape(readj('MASK/engineering_polygon_candidate.geojson')['features'][0]['geometry']);assert p.is_valid and not p.is_empty
 f=pd.read_csv(OUT/'MASK/yunnan_polygon_features.csv');assert len(f)==284 and set(f.source_geometry_status)=={'SOURCE_GEOMETRY_VALID'}

def test_invalid_geometry_only_repair_in_memory():
 p=Polygon([(0,0),(1,1),(0,1),(1,0),(0,0)]);before=p.wkb;assert not p.is_valid;assert shapely.make_valid(p).is_valid;assert p.wkb==before and not p.is_valid

@pytest.mark.parametrize('props,wanted',[({'NAME_1':'Yunnan'},True),({'ISO_1':'CN-YN'},True),({'HASC_1':'CN.YN'},True),({'filename':'Yunnan.geojson'},False),({'NAME_1':'Sichuan'},False),({},False)])
def test_identity_attribute_parsing(props,wanted):assert yunnan_identity(props)==wanted

def test_actual_identity_evidence_not_filename():
 f=pd.read_csv(OUT/'MASK/yunnan_polygon_features.csv');assert all(yunnan_identity(json.loads(s)) for s in f.properties)

def test_actual_imerg_coordinates_reused_by_hash():
 c=np.load(OUT/'MASK/imerg_actual_coordinates.npz');s=readj('MASK/imerg_coordinate_reuse.json')
 assert coordhash(c['lat'])==s['lat_hash'] and coordhash(c['lon'])==s['lon_hash']
 assert not s['coordinate_array_synthesized'] and s['attempts'][-1]['exact_hash_match_prior_formal_audit']
 assert not s['attempts'][0]['exact_hash_match_prior_formal_audit']

@pytest.mark.parametrize('kind',['center','intersection'])
def test_mask_shape_exact_coordinates_no_transposition(kind):
 c=np.load(OUT/'MASK/imerg_actual_coordinates.npz')
 with netCDF4.Dataset(str(OUT/f'MASK/yunnan_imerg_mask_{kind}_candidate.nc'),'r') as ds:
  assert ds['yunnan_mask'].shape==(130,140) and ds['yunnan_mask'].dimensions==('lat','lon')
  assert np.array_equal(ds['lat'][:],c['lat']) and np.array_equal(ds['lon'][:],c['lon'])
  assert np.all(np.diff(ds['lat'][:])>0) and np.all(np.diff(ds['lon'][:])>0)
  assert ds['lat'].dtype==c['lat'].dtype and ds['lon'].dtype==c['lon'].dtype

def test_actual_mask_recomputes_and_difference_retained():
 c=np.load(OUT/'MASK/imerg_actual_coordinates.npz');p=shape(readj('MASK/engineering_polygon_candidate.geojson')['features'][0]['geometry']);a,b,_,_=masks_from_actual_centers(c['lat'],c['lon'],p)
 for kind,value in [('center',a),('intersection',b)]:
  with netCDF4.Dataset(str(OUT/f'MASK/yunnan_imerg_mask_{kind}_candidate.nc')) as ds:assert np.array_equal(ds['yunnan_mask'][:],value)
 assert a.sum()==3430 and b.sum()==3752 and (b&~a).sum()==322 and np.all(b[a])
 d=pd.read_csv(OUT/'MASK/boundary_difference_cells.csv');assert len(d)==322

def test_cell_edges_use_actual_nonuniform_centers_not_fixed_offset():
 assert np.array_equal(coordinate_edges([0,1,3]),[-.5,.5,2,4])
 with pytest.raises(ValueError):coordinate_edges([3,1,0])

def test_asymmetric_toy_no_lat_lon_swap_or_offset():
 a,b,_,_=masks_from_actual_centers(np.array([0.,1.]),np.array([10.,11.,12.]),box(11.8,-.2,12.2,.2));assert a.shape==(2,3)
 assert a[0,2] and a.sum()==1 and b[0,2]

@pytest.mark.parametrize('covers,invalid,checked,wanted',[(True,0,True,'FULL'),(True,1,True,'PARTIAL'),(True,0,False,'NOT_ESTABLISHED'),(False,0,True,'PARTIAL')])
def test_full_coverage_requires_actual_valid_pixels(covers,invalid,checked,wanted):assert coverage_class(covers,invalid,checked)==wanted

def test_real_yunnan_coverage_and_nodata():
 s=readj('DEM/dem_audit_summary.json');assert s['SRTM']['yunnan_coverage']=='FULL' and s['SRTM']['yunnan_invalid_touched_cells']==0 and s['SRTM']['yunnan_boundary_invalid_cells']==0
 assert s['AWS_Skadi']['yunnan_coverage']=='MISSING'
 q=pd.read_csv(OUT/'DEM/dem_pixel_qc.csv');assert (q.valid_pixels+q.invalid_pixels==q.total_pixels).all() and q.nonfinite_pixels.sum()==0 and q.nodata_pixels.sum()==0

def test_common_overlap_candidate_only():
 c=readj('CROSS_SOURCE/common_overlap_candidate.json');assert c['status']=='CANDIDATE_ONLY' and c['numerical_common_overlap']==[97.,20.,107.,30.]
 assert not c['model_input_bbox_frozen'] and c['no_context_width_selected'] and c['all_time_all_variable_common_validity'].startswith('NOT_ESTABLISHED')

def test_frozen_yunnan_principle_preserved_other_choices_not_frozen():
 m=readj('MASK/mask_engineering_result.json');assert m['final_evaluation_yunnan_administrative_mask_principle']=='FROZEN_UNCHANGED'
 assert not m['final_boundary_version_frozen'] and not m['mask_boundary_rule_frozen']

def test_raw_size_mtime_and_sampled_hash_protection():
 r=readj('logs/integrity_summary.json');assert r['size_mtime_all_unchanged'] and r['sha256_sampled_all_pass'] and r['raw_write_operations']==0
 assert r['input_files_checked']==253 and r['sha256_sampled']==17

def test_old_runs_unchanged_live_hash():
 n=0
 for p,r in readj('logs/input_protection_before.json').items():
  if '\\outputs\\' in p and r['sha256']:
   assert hashfile(p)==r['sha256'];n+=1
 assert n>=4

def test_output_guard_prevents_raw_write():
 with pytest.raises(AssertionError):writej(Path(r'F:\not_authorized_raw.json'),{})

def test_temporary_files_cleaned():
 assert not list(CACHE.iterdir());s=readj('logs/cache_summary.json');assert s['cleanup_failures']==s['remaining_staged_bytes']==0 and s['temporary_vrt_cleaned'] and s['copy_count']==2

def test_existing_dependencies_unchanged():assert readj('logs/dependency_change_record.json')['existing_changed']=={}

def test_physical_distance_gradient_east_and_north():
 lat=np.array([25.002,25.001,25.,24.999,24.998]);lon=np.array([102.,102.001,102.002,102.003,102.004]);g=pyproj.Geod(ellps='WGS84');z=np.empty((5,5))
 for i,la in enumerate(lat):
  _,_,dist=g.inv(np.full(4,lon[0]),np.full(4,la),lon[1:],np.full(4,la));z[i]=.03*np.r_[0,dist]
 t=terrain_gradient(z,lat,lon);np.testing.assert_allclose(t['dh_dx'],.03,rtol=1e-8,atol=1e-10);assert np.all(t['dy_m']<0)
 _,_,dist=g.inv(np.full(4,lon[0]),np.full(4,lat[0]),np.full(4,lon[0]),lat[1:]);y=-np.r_[0,dist];z=np.tile(.02*y[:,None],(1,5));t=terrain_gradient(z,lat,lon)
 np.testing.assert_allclose(t['dh_dy'],.02,rtol=1e-8,atol=1e-10)
 with pytest.raises(ValueError):terrain_gradient(np.zeros((4,5)),lat,lon)

def test_smoke_real_units_and_flat_aspect_nan():
 s=readj('DEM/terrain_smoke_result.json');assert s['status']=='ENGINEERING_SMOKE_TEST_ONLY' and s['elevation_unit']=='m' and s['finite_gradients']==1089
 t=terrain_gradient(np.zeros((3,3)),np.array([25.,24.999,24.998]),np.array([102.,102.001,102.002]));assert np.isnan(t['aspect_radians']).all() and np.all(t['slope_degrees']==0)

def test_longitude_latitude_order_safe():
 tr=pyproj.Transformer.from_crs('EPSG:4326','EPSG:3857',always_xy=True);x,y=tr.transform(102,25);assert np.isfinite(x) and np.isfinite(y) and x>1e7 and y>2e6
 inv=pyproj.Transformer.from_crs('EPSG:3857','OGC:CRS84',always_xy=True);np.testing.assert_allclose(inv.transform(x,y),(102,25),atol=1e-10)

def test_parquet_outputs_equal_csv():
 for r in pd.read_csv(OUT/'logs/parquet_validation.csv').itertuples():
  p=OUT/r.csv;pd.testing.assert_frame_equal(pd.read_csv(p,dtype=str,keep_default_na=False),pd.read_parquet(p.with_suffix('.parquet')))

