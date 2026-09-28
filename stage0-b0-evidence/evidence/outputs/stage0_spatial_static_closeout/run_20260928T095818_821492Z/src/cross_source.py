import json,sys,zipfile
import numpy as np,pandas as pd,shapely,pyproj
from shapely.geometry import shape,box
from config import *
from common import *
sys.stdout.reconfigure(encoding='utf8')
sc=readj('logs/discovery_scope.json');dem=readj('DEM/dem_audit_summary.json');poly=shape(readj('MASK/engineering_polygon_candidate.geojson')['features'][0]['geometry']);pb=poly.bounds
# Distinguish entirely absent province support from partially covering support; no raster reread.
for root in dem:
 q=pd.read_csv(OUT/'DEM/dem_pixel_qc.csv');q=q[q.root==root]
 if q.yunnan_touched_cells.sum()==0:dem[root]['yunnan_coverage']='MISSING'
writej('DEM/dem_audit_summary.json',dem)
m=readj('MASK/mask_engineering_result.json');m['fixed_0p05_degree_offset_assumed']=m.pop('fixed_half_degree_step_assumed');writej('MASK/mask_engineering_result.json',m)
sidecars=[]
for r in sc['dem_files']:
 with zipfile.ZipFile(r['path']) as z:
  for n in z.namelist():
   if not n.lower().endswith('.hgt'):sidecars.append({'archive':r['path'],'member':n})
writej('DEM/sidecar_discovery.json',{'non_hgt_archive_members':sidecars,'loose_files_inventory_count':len(sc['dem_files']),'crs_basis':'SRTMHGT standard format/member naming interpreted by GDAL; no guessed EPSG if missing'})
rows=[]
for source,key in [('IMERG','imerg'),('GFS','gfs'),('Himawari','himawari')]:
 p=Path(sc['grid_evidence'][key]);protect(p,True);df=pd.read_csv(p);r=df.iloc[0]
 bounds=[float(r.lon_min),float(r.lat_min),float(r.lon_max),float(r.lat_max)]
 assert df[['lon_min','lat_min','lon_max','lat_max']].drop_duplicates().shape[0]==1
 res=f'{r.mean_dlon};{r.mean_dlat}' if source in ['IMERG','GFS'] else f'{r.median_dlon};{r.median_dlat}'
 rows.append(dict(source=source,lat_min=bounds[1],lat_max=bounds[3],lon_min=bounds[0],lon_max=bounds[2],resolution=res,orientation=f'lat {r.lat_direction}; lon {r.lon_direction}',coverage_status='YUNNAN_WITHIN_COORDINATE_ENVELOPE' if box(*bounds).covers(poly) else 'PARTIAL_COORDINATE_ENVELOPE',evidence_source=str(p),coverage_semantics='coordinate-center envelope only; not all-time per-variable valid-pixel proof',yunnan_polygon_inside=box(*bounds).covers(poly)))
for root,d in dem.items():
 b=d['center_footprint_bounds'];rows.append(dict(source='DEM_'+root,lat_min=b[1],lat_max=b[3],lon_min=b[0],lon_max=b[2],resolution=1/3600,orientation='lat descending; lon ascending',coverage_status=d['yunnan_coverage'],evidence_source=str(OUT/'DEM/dem_pixel_qc.csv'),coverage_semantics='per-root footprint plus exhaustive valid-pixel QC; envelope alone is not coverage',yunnan_polygon_inside=d['yunnan_footprint_covers']))
rows.append(dict(source='Yunnan_polygon_candidate',lat_min=pb[1],lat_max=pb[3],lon_min=pb[0],lon_max=pb[2],resolution='VECTOR',orientation='lon,lat; CRS84',coverage_status='SOURCE_GEOMETRY_VALID; CANDIDATE_ONLY',evidence_source=readj('MASK/polygon_selection_evidence.json')['selected_for_engineering_only'],coverage_semantics='raw GADM level-1 province feature',yunnan_polygon_inside=True))
csv('CROSS_SOURCE/spatial_coverage_closeout.csv',rows)
# Primary DEM root explicitly considered separately; AWS complement is never silently mosaicked.
primary=[r for r in rows if r['source'] in ['IMERG','GFS','Himawari','DEM_SRTM']]
b=(max(r['lon_min'] for r in primary),max(r['lat_min'] for r in primary),min(r['lon_max'] for r in primary),min(r['lat_max'] for r in primary))
common=box(*b);assert b==(97.,20.,107.,30.)
result={'status':'CANDIDATE_ONLY','bounds_order':'west,south,east,north','numerical_common_overlap':b,'sources':['IMERG','GFS','Himawari','DEM_SRTM'],'DEM_root_selection':'SRTM independently covers province; AWS_Skadi remains separate; not final DEM approval','yunnan_polygon_inside':common.covers(poly),'dem_valid_pixel_coverage':dem['SRTM']['common_candidate_coverage'],'all_time_all_variable_common_validity':'NOT_ESTABLISHED_NOT_TESTED_THIS_STATIC_AUDIT','model_input_bbox_frozen':False,'context_margin':'ENGINEERING_EVIDENCE_ONLY','no_context_width_selected':True}
writej('CROSS_SOURCE/common_overlap_candidate.json',result)
geo=pyproj.Geod(ellps='WGS84');margins=[]
for r in rows[:-1]+[{'source':'COMMON_CANDIDATE','lon_min':b[0],'lat_min':b[1],'lon_max':b[2],'lat_max':b[3]}]:
 west=pb[0]-r['lon_min'];east=r['lon_max']-pb[2];south=pb[1]-r['lat_min'];north=r['lat_max']-pb[3];mlat=(pb[1]+pb[3])/2;mlon=(pb[0]+pb[2])/2
 km=lambda x1,y1,x2,y2,sign:float(geo.inv(x1,y1,x2,y2)[2]/1000*np.sign(sign))
 margins.append(dict(source=r['source'],west_deg=west,east_deg=east,south_deg=south,north_deg=north,west_km_approx=km(r['lon_min'],mlat,pb[0],mlat,west),east_km_approx=km(pb[2],mlat,r['lon_max'],mlat,east),south_km_approx=km(mlon,r['lat_min'],mlon,pb[1],south),north_km_approx=km(mlon,pb[3],mlon,r['lat_max'],north),semantics='envelope upper-bound margins at polygon midlat/midlon; negative means shortfall; footprint gaps remain separate'))
csv('CROSS_SOURCE/context_margins.csv',margins)
# Only documentation, no scientific downloads.
writej('logs/official_documentation_sources.json',[{'url':'https://gdal.org/en/stable/drivers/raster/srtmhgt.html','finding':'HGT driver recognizes named HGT zip archives and supplies georeferencing','role':'format behavior; not authentication of local source'},{'url':'https://gdal.org/en/stable/tutorials/geotransforms_tut.html','finding':'Affine transform addresses pixel corner; center is offset half a pixel','role':'interpret raster support vs Point sample footprint'},{'url':'https://gadm.org/data.html','finding':'GADM documents version 4.1','role':'official version reference; current local artifact authentication unresolved'}])
print(json.dumps({'common':result,'common_margin':margins[-1],'source_rows':len(rows),'sidecars':sidecars}))
