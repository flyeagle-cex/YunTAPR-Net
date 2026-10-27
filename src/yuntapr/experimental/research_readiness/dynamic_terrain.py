"""B7/B8 shared physical DOTE input and a single SP04 fusion control.

Candidate scientific choices remain subject to explicit researcher approval.
No physical wind is reconstructed from normalized MEE tensors.
"""
import copy
from dataclasses import dataclass
import numpy as np
import torch
from torch import nn
from ..core_innovation.dote import dote_proxy
from ..core_innovation.gfs import EnvironmentFrame,_above_ground
from ..core_innovation.terrain import TerrainFeatures
from ..core_innovation.stage2 import CHANNELS, MEE_V13_KEYS
from ..core_innovation.stage2.dote_v13 import complete_dote
from ..core_innovation.stage2.fusion import paired_fusion_candidates
from .static_training import model_factory as static_factory

ORDER = ('O850','O700','W850','W700','L850','L700','M850','M700')


@dataclass(frozen=True)
class DoteDefinition:
    pwat_reference_kg_m2: float
    reference_provenance: str
    moisture_basis: str = 'windward_W'
    velocity_reference_m_s: float = 1.0
    def __post_init__(self):
        if (not np.isfinite(self.pwat_reference_kg_m2) or self.pwat_reference_kg_m2 <= 0
            or not self.reference_provenance or self.moisture_basis not in ('windward_W','signed_O')
            or self.velocity_reference_m_s != 1.0):
            raise ValueError('Explicit positive frozen PWAT reference and 1 m/s dimensional scale required')


class PhysicalDote:
    def __init__(self, pack, definition):
        if len(pack.channels)!=6 or pack.values.shape!=(6,100,100):raise ValueError('Use the unchanged production B6 pack')
        self.pack=pack;self.definition=definition
        v,m=pack.values,pack.valid
        self.terrain=TerrainFeatures(pack.grid,v[0],m[0],v[1],v[2],m[1]&m[2],v[3],
                                    np.degrees(np.arctan2(v[4],v[5]))%360,m[4]&m[5])
    def physical(self,frame):
        if frame.mode!='retrospective' or frame.identity.lead.total_seconds()!=21600:raise ValueError('Inherited f006 retrospective time required')
        # Exactly the inherited reader's native-pressure masking, followed by
        # its conservative bilinear support and target-pressure masking. A
        # pre-aligned physical cache must not be interpolated a second time.
        native=EnvironmentFrame(frame.identity,frame.grid,_above_ground(frame.fields),frame.mode,frame.provenance)
        mapped=native if frame.grid.identity==self.pack.grid.identity else native.on_grid(self.pack.grid,operator='bilinear_point_candidate')
        fields=mapped.fields
        for p in (850,700):
            for axis in ('u','v'):
                f=fields[f'{axis}{p}']
                if f.quantity!=axis or f.unit!='m/s' or f.level_pa!=p*100.:raise ValueError('Physical vector wind binding differs')
        ps,pw=fields['ps'],fields['pwat']
        if ps.quantity!='surface_pressure' or ps.unit!='Pa' or pw.quantity!='precipitable_water' or pw.unit!='kg m-2':raise ValueError('Explicit canonical surface pressure and column PWAT units required')
        u=np.stack([fields[f'u{p}'].values for p in (850,700)])
        v=np.stack([fields[f'v{p}'].values for p in (850,700)])
        mask=np.stack([fields[f'u{p}'].valid&fields[f'v{p}'].valid for p in (850,700)])
        proxy=dote_proxy(self.terrain,u,v,mask,np.array([850.,700.]),ps.values,ps.valid,
                         wind_grid=mapped.grid,wind_unit='m/s',pressure_unit='hPa',surface_pressure_unit='Pa')
        d=self.definition
        return complete_dote(proxy,pw.values,pw.valid,pwat_grid=mapped.grid,pwat_unit='kg m-2',
                             pwat_reference_kg_m2=d.pwat_reference_kg_m2,
                             reference_provenance=d.reference_provenance,moisture_basis=d.moisture_basis)
    def __call__(self,frame):
        result=self.physical(frame);values,valid,keys=result.stack()
        if keys!=ORDER:raise ValueError('Dynamic channel order changed')
        # NaN is retained in the physical diagnostic. Only the tensor boundary
        # supplies a neutral number plus an independent per-channel indicator.
        x=np.where(valid,values/self.definition.velocity_reference_m_s,0.).astype(np.float32)
        if not np.isfinite(x).all():raise FloatingPointError('DOTE conversion overflow; no clipping')
        return x,valid.copy()


class DynamicTerrainModel(nn.Module):
    def __init__(self,b6,fusion,kind):
        super().__init__();self.base=b6;self.fusion=fusion;self.kind=kind
    @property
    def backbone(self):return self.base.backbone
    @property
    def heads(self):return self.base.heads
    @property
    def grid(self):return self.base.grid
    def forward(self,x,valid,*,channel_order,environment,environment_valid,environment_grid,
                environment_keys,dynamic,dynamic_valid,dynamic_grid):
        b=self.base.base;self.grid.assert_same(environment_grid);self.grid.assert_same(dynamic_grid)
        if (tuple(channel_order)!=CHANNELS or tuple(environment_keys)!=MEE_V13_KEYS
            or x.shape[1:]!=(42,501,501) or valid.shape!=x.shape or valid.dtype!=torch.bool
            or not valid.all() or not torch.isfinite(x).all()
            or environment.shape!=(len(x),13,100,100) or environment_valid.shape!=environment.shape
            or environment_valid.dtype!=torch.bool or dynamic.shape!=(len(x),8,100,100)
            or dynamic_valid.shape!=dynamic.shape or dynamic_valid.dtype!=torch.bool
            or not torch.isfinite(dynamic[dynamic_valid]).all()):raise ValueError('Inherited population and explicit dynamic masks required')
        target=b.projection(b.backbone(x))
        mee,used=b.mee(environment,environment_valid,keys=environment_keys)
        f=target+mee+self.base.static(len(x))
        static=self.base.static
        g=torch.cat((torch.where(environment_valid,environment,0.),environment_valid.to(environment.dtype)),1)
        terrain=torch.cat((static.values.expand(len(x),-1,-1,-1),static.valid.expand(len(x),-1,-1,-1).to(environment.dtype),
                           torch.where(dynamic_valid,dynamic,0.),dynamic_valid.to(environment.dtype)),1)
        region=static.region.expand(len(x),-1,-1,-1)
        gm=environment_valid.any(1,keepdim=True)&region
        tm=dynamic_valid.any(1,keepdim=True)&region
        fused=self.fusion([f],[g],[terrain],[region],[gm],[tm],
                          feature_grids=[self.grid],gfs_grids=[self.grid],terrain_grids=[self.grid])
        # Preserve the whole B6 feature outside supervision as well. Only the
        # additional branch is restricted; no supervision pixel is removed.
        output=b.heads(torch.where(region,fused.values[0],f))
        output.target_feature_shape=tuple(target.shape)
        output.target_support_fraction=b.projection.support_fraction(valid.all(1,keepdim=True))
        output.environment_used=used;output.dynamic_used=fused.condition_used[0]
        return output


def model_factory(pack,scalers,*,modulation_limit=.1):
    def create(seed,root):
        models=static_factory({'B6':pack},scalers)(seed,root)
        # Independent auxiliary streams leave inherited B6 and training RNG
        # untouched; both methods share condition projections and fuse tensors.
        with torch.random.fork_rng(devices=[]):
            torch.set_rng_state(torch.Generator().manual_seed(seed+20000).get_state())
            a,b=paired_fusion_candidates(feature_channels=[48],gfs_channels=[26],terrain_channels=[28],
                                         projection_width=16,modulation_limit=modulation_limit)
        b.fuse.load_state_dict(a.fuse.state_dict())
        models['B7']=DynamicTerrainModel(copy.deepcopy(models['B6']),a,'B7')
        models['B8']=DynamicTerrainModel(copy.deepcopy(models['B6']),b,'B8')
        return models
    return create
