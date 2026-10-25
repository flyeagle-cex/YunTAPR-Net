"""Explicit geographic axes and optional point interpolation, no grid inference."""
from dataclasses import dataclass
import hashlib
import numpy as np


@dataclass(frozen=True, eq=False)
class GridSpec:
    lat: np.ndarray
    lon: np.ndarray

    def __post_init__(self):
        for name, bound in (('lat',90),('lon',180)):
            value=np.array(getattr(self,name),dtype=np.float64,copy=True)
            if value.ndim!=1 or len(value)<2 or not np.isfinite(value).all() or np.any(np.abs(value)>bound):
                raise ValueError('Finite geographic 1D axes with at least two cells required')
            d=np.diff(value)
            if not (np.all(d>0) or np.all(d<0)):raise ValueError('Strictly monotonic geographic axes required')
            value.setflags(write=False)
            object.__setattr__(self,name,value)

    @property
    def shape(self): return (len(self.lat),len(self.lon))

    @property
    def identity(self):
        h=hashlib.sha256(b'WGS84_GEOGRAPHIC_CELL_CENTERS_EAST_NORTH')
        for a in (self.lat,self.lon):
            h.update(np.asarray([len(a)],dtype='<i8').tobytes());h.update(a.astype('<f8').tobytes())
        return h.hexdigest()

    def assert_same(self,other):
        if not isinstance(other,GridSpec) or self.identity!=other.identity:
            raise ValueError('Explicit grid identity mismatch; no hidden flip or resize')


def frozen_sp04_grid(root=None):
    """Reuse the existing hash/float32-bit-verified SP04 reader, not reconstructed axes."""
    from yuntapr.spatial.sp04_mapping import load_sp04
    mapping=load_sp04() if root is None else load_sp04(root)
    return GridSpec(mapping.axes['target_lat'],mapping.axes['target_lon'])


@dataclass(frozen=True)
class BilinearMap:
    source: GridSpec
    target: GridSpec
    indices: np.ndarray
    weights: np.ndarray
    inside: np.ndarray

    @classmethod
    def build(cls,source,target):
        """Candidate point interpolation; NOT SP04's native 25-cell area reduction.

        Source array directions are preserved in the flattened indices. Outside
        the source domain is invalid; neither extrapolation nor nearest fill.
        """
        if not isinstance(source,GridSpec) or not isinstance(target,GridSpec):raise TypeError('Explicit GridSpec objects required')
        def bracket(axis,points):
            ascending=axis[0]<axis[-1];ordered=axis if ascending else axis[::-1]
            left=np.clip(np.searchsorted(ordered,points,side='right')-1,0,len(axis)-2)
            right=left+1;fraction=(points-ordered[left])/(ordered[right]-ordered[left])
            inside=(points>=ordered[0])&(points<=ordered[-1])
            if not ascending:left,right=len(axis)-1-left,len(axis)-1-right
            return left,right,fraction,inside
        y,x=np.meshgrid(target.lat,target.lon,indexing='ij')
        r0,r1,fy,iy=bracket(source.lat,y.ravel());c0,c1,fx,ix=bracket(source.lon,x.ravel())
        indices=np.stack((r0*len(source.lon)+c0,r0*len(source.lon)+c1,r1*len(source.lon)+c0,r1*len(source.lon)+c1),-1)
        weights=np.stack(((1-fy)*(1-fx),(1-fy)*fx,fy*(1-fx),fy*fx),-1)
        inside=iy&ix
        # Outside weights are never used and are kept neutral for finite math.
        weights=np.where(inside[:,None],weights,0.)
        for a in (indices,weights,inside):a.setflags(write=False)
        return cls(source,target,indices,weights,inside)

    def apply(self,values,valid):
        x=np.asarray(values,dtype=np.float64);mask=np.asarray(valid)
        if x.shape[-2:]!=self.source.shape or mask.shape!=x.shape or mask.dtype!=bool:
            raise ValueError('Values and independent bool mask must share source [...,row,col] shape')
        selected=np.take(x.reshape(x.shape[:-2]+(-1,)),self.indices,axis=-1)
        good=np.take(mask.reshape(mask.shape[:-2]+(-1,)),self.indices,axis=-1)&np.isfinite(selected)
        required=self.weights>0
        complete=np.all(good|~required,axis=-1)&self.inside
        result=np.sum(np.where(good,selected,0.)*self.weights,axis=-1)
        shape=x.shape[:-2]+self.target.shape
        return np.where(complete,result,np.nan).reshape(shape),complete.reshape(shape)
