import sys,json,zipfile,time,collections,xml.sax.saxutils
import numpy as np,pandas as pd,rasterio,pyproj,shapely
from rasterio.features import geometry_mask
from rasterio.windows import Window
from shapely.geometry import shape,box,mapping
from config import *
from common import *
from spatial_rules import *
sys.stdout.reconfigure(encoding='utf8')
poly=shape(readj('MASK/engineering_polygon_candidate.geojson')['features'][0]['geometry'])
common_candidate=box(97,20,107,30) # exactly the reused Himawari center envelope, not model-input bbox
scope=readj('logs/discovery_scope.json');inventory=[];geo=[];qc=[];edge_data={};sources={};footprints={};nominals={}
start=time.perf_counter()
with rasterio.Env(GDAL_PAM_ENABLED='NO',GDAL_CACHEMAX=128):
 for index,item in enumerate(scope['dem_files']):
  p=Path(item['path']);root=p.parent.name;t=time.perf_counter()
  with zipfile.ZipFile(p) as z:members=[n for n in z.namelist() if n.lower().endswith('.hgt')]
  assert len(members)==1;member=members[0];uri='/vsizip/'+p.as_posix()+'/'+member
  try:
   with rasterio.open(uri,'r') as ds:
    crs=pyproj.CRS(ds.crs);a=ds.read(1);v=valid_mask(a,ds.nodata,ds.read_masks(1));foot=box(*ds.bounds)
    x0,y0=ds.xy(0,0);x1,y1=ds.xy(ds.height-1,ds.width-1);nom=box(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1))
    assert crs.to_epsg()==4326 and ds.count==1 and ds.transform.b==ds.transform.d==0
    footprints.setdefault(root,[]).append(foot);nominals.setdefault(root,[]).append(nom)
    total=a.size;nodata=int(np.sum(a==ds.nodata));nf=int(np.sum(~np.isfinite(a)));valid=int(v.sum())
    py=geometry_mask([mapping(poly)],out_shape=a.shape,transform=ds.transform,invert=True,all_touched=True) if foot.intersects(poly) else None
    boundary=geometry_mask([mapping(poly.boundary)],out_shape=a.shape,transform=ds.transform,invert=True,all_touched=True) if foot.intersects(poly.boundary) else None
    pc=geometry_mask([mapping(common_candidate)],out_shape=a.shape,transform=ds.transform,invert=True,all_touched=True) if foot.intersects(common_candidate) else None
    row=dict(root=root,relative_path=str(p.relative_to(DATA)),filename=p.name,extension=''.join(p.suffixes),size_bytes=p.stat().st_size,archive_member=member,format=ds.driver,width=ds.width,height=ds.height,bands=ds.count,dtype=ds.dtypes[0],crs=str(ds.crs),nodata=ds.nodata,resolution_x=abs(ds.transform.a),resolution_y=abs(ds.transform.e),bounds=json.dumps(list(ds.bounds)),read_status='PASS',nominal_center_bounds=json.dumps(list(nom.bounds)))
    inventory.append(row);geo.append(dict(relative_path=row['relative_path'],crs=str(ds.crs),epsg=crs.to_epsg(),datum=crs.datum.name,coordinate_units=crs.axis_info[0].unit_name,affine_transform=json.dumps(list(ds.transform)),pixel_size_x=ds.transform.a,pixel_size_y=ds.transform.e,orientation='latitude descending; longitude ascending',pixel_semantics=ds.tags().get('AREA_OR_POINT','UNKNOWN'),bounds=row['bounds'],nominal_center_bounds=row['nominal_center_bounds'],elevation_units=str(ds.units[0]),crs_evidence='GDAL SRTMHGT driver georeferencing from HGT format and member name; no embedded CRS header',vertical_datum='NOT_ESTABLISHED_FROM_LOCAL_HEADER',sidecar_source='none located in archive'))
    qc.append(dict(root=root,relative_path=row['relative_path'],total_pixels=total,valid_pixels=valid,nodata_pixels=nodata,nonfinite_pixels=nf,invalid_pixels=total-valid,min_elevation=float(a[v].min()) if valid else None,max_elevation=float(a[v].max()) if valid else None,yunnan_touched_cells=int(py.sum()) if py is not None else 0,yunnan_invalid_touched_cells=int((~v & py).sum()) if py is not None else 0,yunnan_boundary_touched_cells=int(boundary.sum()) if boundary is not None else 0,yunnan_boundary_invalid_cells=int((~v & boundary).sum()) if boundary is not None else 0,common_candidate_touched_cells=int(pc.sum()) if pc is not None else 0,common_candidate_invalid_cells=int((~v & pc).sum()) if pc is not None else 0,statistic_role='QC_STAT_ONLY',read_qc_seconds=time.perf_counter()-t))
    key=(root,round(x0),round(y1));edge_data[key]=(a[0].copy(),a[-1].copy(),a[:,0].copy(),a[:,-1].copy());sources[key]=uri
    if p.name=='N25E102.SRTMGL1.hgt.zip':
     # 33x33 real native samples only, no resampling or formal terrain features.
     z=a[1784:1817,1784:1817].astype(float);vv=v[1784:1817,1784:1817];z[~vv]=np.nan
     xs=np.array([ds.xy(1784,j)[0] for j in range(1784,1817)]);ys=np.array([ds.xy(i,1784)[1] for i in range(1784,1817)])
     terrain=terrain_gradient(z,ys,xs);np.savez(OUT/'DEM/terrain_smoke_arrays.npz',elevation=z,lat=ys,lon=xs,**terrain)
     writej('DEM/terrain_smoke_result.json',{'status':'ENGINEERING_SMOKE_TEST_ONLY','source':str(p),'window':[1784,1784,33,33],'shape':list(z.shape),'elevation_unit':ds.units[0],'horizontal_unit':'meter, WGS84 ellipsoidal Geod.inv adjacent distances','gradient_units':'m/m','aspect_convention':'downslope azimuth clockwise from north; undefined flat cells NaN','latitude_orientation':'descending preserved','finite_elevation':int(np.isfinite(z).sum()),'finite_gradients':int(np.isfinite(terrain['dh_dx']).sum()),'slope_min':float(np.nanmin(terrain['slope_degrees'])),'slope_max':float(np.nanmax(terrain['slope_degrees'])),'formal_feature_algorithm_frozen':False,'no_formal_DOTE':True})
  except Exception as e:
   inventory.append(dict(root=root,relative_path=str(p.relative_to(DATA)),filename=p.name,read_status='FAIL',error=repr(e)));raise
  if (index+1)%20==0:print(json.dumps({'tiles_complete':index+1,'tiles_total':len(scope['dem_files']),'elapsed_seconds':round(time.perf_counter()-start,1)}),flush=True)
csv('DEM/dem_inventory.csv',inventory);csv('DEM/dem_crs_georeferencing_audit.csv',geo);csv('DEM/dem_pixel_qc.csv',qc)
pairs=[]
for (root,x,y),edges in edge_data.items():
 for dx,dy,label in [(1,0,'east'),(0,1,'north')]:
  other=(root,x+dx,y+dy)
  if other in edge_data:
   a,b=(edges[3],edge_data[other][2]) if dx else (edges[0],edge_data[other][1]);valid=(a!=-32768)&(b!=-32768)
   pairs.append(dict(root=root,tile_x=x,tile_y=y,neighbor_direction=label,shared_sample_count=len(a),both_valid_count=int(valid.sum()),unequal_count=int(np.sum(a[valid]!=b[valid])),max_abs_difference=float(np.max(np.abs(a[valid].astype(float)-b[valid]))) if valid.any() else None,overlap_interpretation='HGT duplicated edge samples; not automatically duplicate tiles'))
csv('DEM/dem_shared_edge_comparison.csv',pairs)
top=[];summ={}
for root,fs in footprints.items():
 nom=nominals[root];t=footprint_topology(nom);support=shapely.union_all(fs);q=[r for r in qc if r['root']==root]
 missing=t['gap'];dupes=len(nom)-len(set(g.wkb for g in nom));invalid=sum(r['yunnan_invalid_touched_cells'] for r in q)
 summ[root]=dict(tile_count=len(fs),center_footprint_bounds=list(t['union'].bounds),raster_support_bounds=list(support.bounds),nominal_gap_area_deg2=missing.area,nominal_duplicate_footprints=dupes,nominal_overlap_area_deg2=t['overlap_area'],support_overlap_area_deg2=sum(g.area for g in fs)-support.area,crs_mismatch=False,resolution_mismatch=False,total_pixels=sum(r['total_pixels'] for r in q),valid_pixels=sum(r['valid_pixels'] for r in q),nodata_pixels=sum(r['nodata_pixels'] for r in q),nonfinite_pixels=sum(r['nonfinite_pixels'] for r in q),min_elevation=min(r['min_elevation'] for r in q if r['min_elevation'] is not None),max_elevation=max(r['max_elevation'] for r in q if r['max_elevation'] is not None),yunnan_footprint_covers=bool(support.covers(poly)),yunnan_invalid_touched_cells=invalid,yunnan_boundary_invalid_cells=sum(r['yunnan_boundary_invalid_cells'] for r in q),yunnan_coverage=coverage_class(support.covers(poly),invalid,True),common_candidate_footprint_covers=bool(support.covers(common_candidate)),common_candidate_invalid_cells=sum(r['common_candidate_invalid_cells'] for r in q),common_candidate_coverage=coverage_class(support.covers(common_candidate),sum(r['common_candidate_invalid_cells'] for r in q),True))
 writej('DEM/'+root+'_footprint_and_gaps.geojson',{'type':'FeatureCollection','candidate_only':True,'features':[{'type':'Feature','properties':{'kind':'nominal_tile_union'},'geometry':mapping(t['union'])},{'type':'Feature','properties':{'kind':'nominal_gap_within_root_envelope'},'geometry':mapping(missing)}]})
 for i,(n,f) in enumerate(zip(nom,fs)):top.append(dict(root=root,tile_index=i,nominal_bounds=json.dumps(n.bounds),support_bounds=json.dumps(f.bounds),intersects_yunnan=n.intersects(poly),contains_yunnan= n.covers(poly),nominal_gap_in_root_envelope_deg2=missing.area,duplicate_footprint_count=dupes,crs='EPSG:4326',resolution=1/3600,role='per-root topology; roots not merged'))
csv('DEM/dem_tile_coverage.csv',top);writej('DEM/dem_audit_summary.json',summ)
# Temporary two-tile native VRT, one root only. No resampling. Read away from overlap and verify exact values.
CACHE.mkdir(parents=True,exist_ok=True);vrt=CACHE/'owned_two_tile_feasibility.vrt';k=('SRTM',102,25);k2=('SRTM',103,25)
assert k in sources and k2 in sources
esc=xml.sax.saxutils.escape
xmltext=f'<VRTDataset rasterXSize="7201" rasterYSize="3601"><SRS>EPSG:4326</SRS><GeoTransform>101.99986111111111,0.0002777777777777778,0,26.00013888888889,0,-0.0002777777777777778</GeoTransform><VRTRasterBand dataType="Int16" band="1"><NoDataValue>-32768</NoDataValue>'
for off,key in [(0,k),(3600,k2)]:xmltext+=f'<SimpleSource><SourceFilename relativeToVRT="0">{esc(sources[key])}</SourceFilename><SourceBand>1</SourceBand><SrcRect xOff="0" yOff="0" xSize="3601" ySize="3601"/><DstRect xOff="{off}" yOff="0" xSize="3601" ySize="3601"/></SimpleSource>'
xmltext+='</VRTRasterBand></VRTDataset>';vrt.write_text(xmltext,encoding='utf8')
try:
 with rasterio.Env(GDAL_PAM_ENABLED='NO'):
  with rasterio.open(vrt,'r') as ds,rasterio.open(sources[k],'r') as orig:
   v=ds.read(1,window=Window(100,100,4,4));ref=orig.read(1,window=Window(100,100,4,4));assert np.array_equal(v,ref)
   result={'status':'PASS','scope':'two adjacent SRTM tiles, native spacing; metadata-only VRT plus 4x4 exact-value check','formal_mosaic_generated':False,'roots_merged':False,'temporary_path':str(vrt),'overlap_order':'right source later only for temporary feasibility; no scientific seam rule selected'}
finally:
 assert vrt.resolve().parent==CACHE.resolve();vrt.unlink()
result['temporary_cleaned']=not vrt.exists();writej('DEM/mosaic_feasibility_result.json',result)
print(json.dumps({'dem_summary':summ,'mosaic':result,'elapsed_seconds':time.perf_counter()-start}),flush=True)
