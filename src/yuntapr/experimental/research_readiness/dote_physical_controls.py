"""Label-free nonzero DOTE controls; never change GFS/static/supervision inputs.

The selected candidate rotates only the gradient used INSIDE PhysicalDote by
an exact +90 degrees in (east,north). It is a directional-projection probe,
not an alternate real DEM or a causal identification strategy.
"""
from dataclasses import replace
import numpy as np
from .dynamic_terrain import PhysicalDote

ROTATION=((0,-1),(1,0))


class PerpendicularGradientDote:
    def __init__(self,pack,definition):
        self.physical=PhysicalDote(pack,definition)
        t=self.physical.terrain
        # Exact integer rotation; no fitted angle, rescale, clipping or wrap.
        # The real pack and B6 static features remain untouched.
        self.physical.terrain=replace(t,east_gradient=-t.north_gradient.copy(),north_gradient=t.east_gradient.copy(),
                                      aspect_degrees=(t.aspect_degrees.copy()-90.)%360.)

    def __call__(self,frame):
        return self.physical(frame)


def joint_mask_permutation(values,valid,region,*,seed=20261030):
    """Alternative only: joint 8-vectors, exact validity-class bijection.

    Every non-singleton class is deranged by a fixed cyclic shift of a seeded
    ordering. Retains each class's exact multivariate distribution, but changes
    spatial autocorrelation and local elevation/climate/meteorology alignment.
    No label, date, model outcome or training seed is accepted.
    """
    x=np.asarray(values);m=np.asarray(valid);r=np.asarray(region)
    if x.shape!=(8,100,100) or m.shape!=x.shape or m.dtype!=bool or r.shape!=(100,100) or r.dtype!=bool:
        raise ValueError('Frozen 8-channel SP04 arrays and real masks required')
    if not np.isfinite(x[m]).all():raise ValueError('Nonfinite valid DOTE value')
    signature=(m.astype(np.uint16)*(1<<np.arange(8,dtype=np.uint16))[:,None,None]).sum(0)
    mapping=np.arange(10000);rng=np.random.Generator(np.random.PCG64(seed));flat=r.ravel();sig=signature.ravel()
    for key in np.unique(sig[flat]):
        ids=np.flatnonzero(flat&(sig==key))
        if len(ids)>1:
            order=rng.permutation(ids);mapping[order]=np.roll(order,1)
    result=x.reshape(8,-1)[:,mapping].reshape(x.shape).copy()
    if not np.array_equal(m,m.reshape(8,-1)[:,mapping].reshape(m.shape)):
        raise RuntimeError('Validity classes changed')
    return result,m.copy(),mapping.reshape(100,100)
