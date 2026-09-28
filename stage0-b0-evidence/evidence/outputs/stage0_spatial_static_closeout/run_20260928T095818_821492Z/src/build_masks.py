import sys,json
import numpy as np,netCDF4,shapely
from shapely.geometry import shape,mapping
from config import *
from common import *
from spatial_rules import *
sys.stdout.reconfigure(encoding='utf8')
coords=np.load(OUT/'MASK/imerg_actual_coordinates.npz');lat=coords['lat'];lon=coords['lon'];poly=shape(readj('MASK/engineering_polygon_candidate.geojson')['features'][0]['geometry'])
a,b,le,oe=masks_from_actual_centers(lat,lon,poly);diff=b&~a
rows=[]
for name,mask in [('center',a),('intersection',b)]:
 p=OUT/f'MASK/yunnan_imerg_mask_{name}_candidate.nc'
 with netCDF4.Dataset(str(p),'w',format='NETCDF4') as ds:
  ds.createDimension('lat',len(lat));ds.createDimension('lon',len(lon));ds.createDimension('bounds',2)
  la=ds.createVariable('lat',lat.dtype,('lat',));lo=ds.createVariable('lon',lon.dtype,('lon',));la[:]=lat;lo[:]=lon;la.units='degrees_north';lo.units='degrees_east';la.standard_name='latitude';lo.standard_name='longitude'
  la.bounds='lat_bounds';lo.bounds='lon_bounds';ds.createVariable('lat_bounds','f8',('lat','bounds'))[:]=np.column_stack([le[:-1],le[1:]]);ds.createVariable('lon_bounds','f8',('lon','bounds'))[:]=np.column_stack([oe[:-1],oe[1:]])
  m=ds.createVariable('yunnan_mask','u1',('lat','lon'),fill_value=255,zlib=True,complevel=1);m[:]=mask.astype('u1');m.flag_values=np.array([0,1],dtype='u1');m.flag_meanings='outside inside_candidate';m.coordinates='lat lon'
  ds.candidate_only='true';ds.scientific_mask_convention_frozen='false';ds.frozen_scientific_principle='Final evaluation uses the whole Yunnan provincial administrative mask';ds.boundary_rule='strict cell-center interior; exact-boundary centers excluded' if name=='center' else 'closed midpoint-derived cell polygon intersects province, including boundary touching';ds.cell_edge_definition='midpoints of actual saved centers, end extrapolation from local neighbor spacing; engineering candidate only';ds.source_polygon=readj('MASK/polygon_selection_evidence.json')['selected_for_engineering_only'];ds.source_coordinates=readj('MASK/imerg_coordinate_reuse.json')['source'];ds.lat_hash=coordhash(lat);ds.lon_hash=coordhash(lon);ds.no_flip_or_transpose='true'
 with netCDF4.Dataset(str(p),'r') as ds:
  assert ds['yunnan_mask'].dimensions==('lat','lon') and np.array_equal(ds['yunnan_mask'][:],mask)
  assert np.array_equal(ds['lat'][:],lat) and np.array_equal(ds['lon'][:],lon)
 rr,cc=np.where(mask);rows.append(dict(candidate=name,mask_shape='130x140',true_cell_count=int(mask.sum()),false_cell_count=int(mask.size-mask.sum()),fraction=float(mask.mean()),row_min=int(rr.min()),row_max=int(rr.max()),col_min=int(cc.min()),col_max=int(cc.max()),lat_min=float(lat[rr.min()]),lat_max=float(lat[rr.max()]),lon_min=float(lon[cc.min()]),lon_max=float(lon[cc.max()]),boundary_difference_cell_count=int(diff.sum()),boundary_rule='strict_center_interior' if name=='center' else 'closed_cell_intersection',scientific_convention_frozen=False))
csv('MASK/yunnan_imerg_mask_comparison.csv',rows)
r,c=np.where(diff);csv('MASK/boundary_difference_cells.csv',[dict(row=int(i),col=int(j),lat=float(lat[i]),lon=float(lon[j]),center=False,intersection=True) for i,j in zip(r,c)])
xx,yy=np.meshgrid(lon,lat);on_boundary=shapely.intersects_xy(poly.boundary,xx,yy)
summary={'center_cells':int(a.sum()),'intersection_cells':int(b.sum()),'difference_cells':int(diff.sum()),'center_subset_intersection':bool(np.all(b[a])),'centers_exactly_on_polygon_boundary':int(on_boundary.sum()),'shape':[130,140],'lat_exact_match':True,'lon_exact_match':True,'lat_ascending_preserved':True,'dimensions':['lat','lon'],'transposed':False,'flipped':False,'index_offset':0,'fixed_half_degree_step_assumed':False,'edge_rule':'midpoint actual centers; edge extrapolation is provisional geometry convention','lat_edge_min':float(le[0]),'lat_edge_max':float(le[-1]),'lon_edge_min':float(oe[0]),'lon_edge_max':float(oe[-1]),'candidate_only':True,'final_evaluation_yunnan_administrative_mask_principle':'FROZEN_UNCHANGED','final_boundary_version_frozen':False,'mask_boundary_rule_frozen':False}
writej('MASK/mask_engineering_result.json',summary)
writej('logs/researcher_clarification.json',{'frozen_scientific_principle':'最终评价必须使用云南省全境行政区 mask','not_frozen':['具体边界文件','来源版本','边界像元判定规则'],'instruction':'继续自动发现并审计候选，不改变冻结原则'})
print(json.dumps(summary))
