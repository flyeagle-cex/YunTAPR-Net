"""Bounded shared-edge DEM join; no source I/O, resampling or seam averaging."""
import numpy as np
from ..grid import GridSpec
from ..terrain import DemWindow


def join_east_west(west,east,*,max_cells=65536):
    if type(max_cells)!=int or not 0<max_cells<=65536:raise ValueError('Bounded DEM halo join required')
    a,b=west.grid,east.grid
    if (not np.array_equal(a.lat,b.lat) or a.lon[0]>=a.lon[-1] or b.lon[0]>=b.lon[-1]
        or a.lon[-1]!=b.lon[0] or a.shape[0]*(a.shape[1]+b.shape[1]-1)>max_cells):
        raise ValueError('Aligned eastward grids with one identical shared edge required')
    am,bm=west.valid[:,-1],east.valid[:,0]
    if not np.array_equal(am,bm) or np.any(west.elevation_m[am,-1]!=east.elevation_m[bm,0]):
        raise ValueError('Shared-edge validity/elevation mismatch; no inferred seam repair')
    return DemWindow(GridSpec(a.lat,np.concatenate((a.lon,b.lon[1:]))),
        np.concatenate((west.elevation_m,east.elevation_m[:,1:]),axis=1),
        np.concatenate((west.valid,east.valid[:,1:]),axis=1))
