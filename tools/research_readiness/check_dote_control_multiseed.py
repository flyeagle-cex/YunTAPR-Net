"""One seed's CPU initialization/order and tiny fusion-gradient checks only."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed',type=int,choices=(2030,2031),required=True)
    for flag in ('cached-static','terrain-receipt','reference','inherited-preparation','output'):
        p.add_argument('--'+flag,type=Path,required=True)
    a=p.parse_args()
    assert not a.output.exists() and os.environ['PYTHONHASHSEED']==str(a.seed)
    import numpy as np
    import torch
    from yuntapr.training.phase_a_protocol import state_digest
    from yuntapr.experimental.core_innovation.grid import GridSpec
    from yuntapr.experimental.core_innovation.stage4.engine import epoch_order
    from yuntapr.experimental.core_innovation.stage3.planning import digest
    from yuntapr.experimental.research_readiness.dynamic_terrain import model_factory
    from yuntapr.experimental.research_readiness.static_training import unpack
    from yuntapr.experimental.research_readiness.dote_numeric_control import ZeroNumericDote
    def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
    old=read(ROOT/'docs/research_readiness/20261025/evidence/dote_control_proposal_20261029.json')
    raw=a.cached_static.read_bytes();assert len(raw)==312828 and hashlib.sha256(raw).hexdigest()==old['static_source_sha256']['B7']
    receipt=read(a.terrain_receipt);pack=unpack(raw,'B6',receipt)
    models=model_factory(pack,receipt['scalers'],modulation_limit=.1)(a.seed,ROOT)
    identity={k:dict(full_state_sha256=state_digest(m.state_dict()),common_sha256=state_digest(dict(backbone=m.backbone.state_dict(),heads=m.heads.state_dict()))) for k,m in models.items()}
    assert identity==read(a.reference/'paired_initial_identity.json')
    assert sum(p.numel() for p in models['B7'].parameters() if p.requires_grad)==4411058
    prepared=read(a.inherited_preparation)['prepared'];ids=tuple(prepared['roles']['Train']['ids'])
    orders={str(e):dict(ids=epoch_order(ids,a.seed,e),sha256=digest(epoch_order(ids,a.seed,e))) for e in range(1,10)}
    assert json.loads(json.dumps(orders))==read(a.reference/'paired_orders.json')
    # Reuse exactly the actual transform. Sentinel frame arrays are unchanged;
    # only its returned numeric buffer is replaced after physical masking.
    frame={k:np.arange(24,dtype=np.float32).reshape(2,3,4) for k in ('GFS','DEM','labels','supervision_mask')}
    saved={k:v.copy() for k,v in frame.items()}
    numeric=np.ones((8,100,100),np.float32);mask=np.ones_like(numeric,bool);mask[0,1,2]=False;numeric[0,1,2]=np.nan
    control=object.__new__(ZeroNumericDote);control.physical=lambda received:(numeric,mask)
    zero,valid=control(frame);assert not zero.any();np.testing.assert_array_equal(valid,mask)
    for k in frame:np.testing.assert_array_equal(frame[k],saved[k])
    assert np.isnan(numeric[0,1,2]);valid[0,0,0]=False;assert mask[0,0,0]
    # Tiny nonzero residual exposes the loss-gradient response without an
    # optimizer, real model forward, satellite reads, or modifying initial IDs.
    fusion=copy.deepcopy(models['B7'].fusion);torch.manual_seed(a.seed+20000)
    f=torch.randn(1,48,3,3);g=torch.randn(1,26,3,3);terrain=torch.randn(1,28,3,3);terrain[:,12:20]=0
    masks=[torch.ones(1,1,3,3,dtype=torch.bool)];grid=GridSpec([25.,25.1,25.2],[101.,101.1,101.2])
    with torch.no_grad():fusion.fuse[0].weight.fill_(.001)
    result=fusion([f],[g],[terrain],masks,masks,masks,feature_grids=[grid],gfs_grids=[grid],terrain_grids=[grid]).values[0]
    result.square().sum().backward();grad=fusion.terrain[0].weight.grad
    assert torch.isfinite(result).all() and torch.isfinite(grad).all()
    assert grad[:,12:20].numel()==128 and torch.count_nonzero(grad[:,12:20])==0
    assert torch.count_nonzero(grad[:,:12])>0 and torch.count_nonzero(grad[:,20:])>0
    data=dict(status='PASS_NEW_CONTROL_SEED_CPU_CHECKS',seed=a.seed,initialization=identity['B7'],
              full_initial_identity_matches_existing_B7=True,all_nine_orders_match_existing_B7=True,
              epoch_order_sha256={k:v['sha256'] for k,v in orders.items()},static_auxiliary_seed=a.seed+10000,
              fusion_auxiliary_seed=a.seed+20000,nominal_parameters=4411058,loss_inactive_zero_input_weights=128,
              masks_and_other_inputs_unchanged=True,zero_numeric_channels=8,
              static_cache_bytes=len(raw),static_cache_sha256=hashlib.sha256(raw).hexdigest(),
              tiny_synthetic_fusion_backward_runs=1,full_real_model_inference=0,formal_optimizer_updates=0,
              raw_weather_bytes=0,checkpoint_loads=0,normalization_refits=0,final_2025='FROZEN_NO_ACCESS')
    with a.output.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(status=data['status'],seed=a.seed,B7_initial_sha256=identity['B7']['full_state_sha256'],loss_inactive_weights=128)))


if __name__=='__main__':main()
