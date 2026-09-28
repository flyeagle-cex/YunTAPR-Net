import numpy as np
import shapely
from shapely.geometry import box
from pyproj import Geod

def coordinate_edges(centers):
 a=np.asarray(centers,dtype=float)
 if a.ndim!=1 or len(a)<2 or not np.all(np.diff(a)>0):raise ValueError('Strict ascending actual centers required')
 mid=(a[1:]+a[:-1])/2
 return np.r_[a[0]-(a[1]-a[0])/2,mid,a[-1]+(a[-1]-a[-2])/2]
def masks_from_actual_centers(lat,lon,poly):
 le=coordinate_edges(lat);oe=coordinate_edges(lon)
 x,y=np.meshgrid(lon,lat,indexing='xy')
 center=shapely.contains_xy(poly,x,y) # strict interior; exact boundary excluded explicitly
 cells=shapely.box(oe[:-1][None,:],le[:-1][:,None],oe[1:][None,:],le[1:][:,None])
 intersects=shapely.intersects(poly,cells)
 assert center.shape==(len(lat),len(lon)) and np.all(intersects[center])
 return center,intersects,le,oe

def valid_mask(a,nodata,mask=None):
 a=np.asarray(a);v=np.isfinite(a)
 if nodata is not None:v &= (a!=nodata)
 if mask is not None:v &= np.asarray(mask)>0
 return v

def coverage_class(footprint_covers,invalid_cells,valid_evidence):
 if not valid_evidence:return 'NOT_ESTABLISHED'
 return 'FULL' if footprint_covers and invalid_cells==0 else 'PARTIAL'
def footprint_topology(geoms):
 union=shapely.union_all(geoms);hull=box(*union.bounds)
 return {'union':union,'gap':hull.difference(union),'overlap_area':sum(x.area for x in geoms)-union.area}
def yunnan_identity(props):return props.get('NAME_1')=='Yunnan' or props.get('ISO_1')=='CN-YN' or props.get('HASC_1')=='CN.YN'
def terrain_gradient(z,lat,lon):
 z=np.asarray(z,dtype=float);lat=np.asarray(lat);lon=np.asarray(lon)
 if z.shape!=(len(lat),len(lon)):raise ValueError('lat/lon order mismatch')
 geod=Geod(ellps='WGS84');dx=[];dy=[]
 for la in lat:
  _,_,d=geod.inv(lon[:-1],np.full(len(lon)-1,la),lon[1:],np.full(len(lon)-1,la));dx.append(np.asarray(d)*np.sign(np.diff(lon)))
 for lo in lon:
  _,_,d=geod.inv(np.full(len(lat)-1,lo),lat[:-1],np.full(len(lat)-1,lo),lat[1:]);dy.append(np.asarray(d)*np.sign(np.diff(lat)))
 gx=np.full_like(z,np.nan);gy=np.full_like(z,np.nan)
 for i in range(len(lat)):gx[i]=np.gradient(z[i],np.r_[0,np.cumsum(dx[i])],edge_order=2)
 for j in range(len(lon)):gy[:,j]=np.gradient(z[:,j],np.r_[0,np.cumsum(dy[j])],edge_order=2)
 slope=np.degrees(np.arctan(np.hypot(gx,gy)))
 aspect=np.mod(np.arctan2(-gx,-gy),2*np.pi);aspect[np.hypot(gx,gy)<1e-12]=np.nan
 return dict(dh_dx=gx,dh_dy=gy,slope_degrees=slope,aspect_radians=aspect,sin_aspect=np.sin(aspect),cos_aspect=np.cos(aspect),dx_m=np.array(dx),dy_m=np.array(dy).T)
