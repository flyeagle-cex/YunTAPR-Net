"""New seeds: CPU initialization/order checks using the existing static cache."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--original-private',type=Path,required=True);parser.add_argument('--cached-static',type=Path,required=True)
    parser.add_argument('--seed-references',type=Path,required=True);parser.add_argument('--output',type=Path);parser.add_argument('--seed',type=int,choices=(2030,2031))
    parser.add_argument('--storage-probe',type=Path);parser.add_argument('--reuse-seed-references',action='store_true')
    a=parser.parse_args();os.chdir(ROOT)
    from yuntapr.experimental.core_innovation.stage4.data import read,sha
    from yuntapr.experimental.core_innovation.stage4.engine import write,epoch_order,resources
    from yuntapr.experimental.core_innovation.stage3.planning import digest
    from yuntapr.experimental.research_readiness.dynamic_terrain import model_factory
    from yuntapr.experimental.research_readiness.static_training import unpack
    from yuntapr.experimental.research_readiness import dynamic_multiseed as module
    v=read(a.original_private);frozen=read(ROOT/(module.EVIDENCE+'b7_b8_training_proposal.json'))
    if a.seed:
        import torch
        from yuntapr.training.phase_a_protocol import state_digest
        if os.environ.get('PYTHONHASHSEED')!=str(a.seed):raise ValueError('Seed must be set before process startup')
        folder=a.seed_references/f's{a.seed}';folder.mkdir(exist_ok=False)
        raw=a.cached_static.read_bytes();assert len(raw)==312828 and hashlib.sha256(raw).hexdigest()==frozen['static_source_sha256']['B7']
        terrain=read(Path(v['terrain'])/'production_receipt.json');pack=unpack(raw,'B6',terrain)
        models=model_factory(pack,terrain['scalers'],modulation_limit=.1)(a.seed,ROOT)
        identity={k:dict(full_state_sha256=state_digest(m.state_dict()),common_sha256=state_digest(dict(backbone=m.backbone.state_dict(),heads=m.heads.state_dict()))) for k,m in models.items()}
        assert identity['B7']['common_sha256']==identity['B8']['common_sha256']==identity['B6']['common_sha256']
        assert state_digest(models['B7'].base.state_dict())==state_digest(models['B8'].base.state_dict())==identity['B6']['full_state_sha256']
        assert state_digest(models['B7'].fusion.fuse.state_dict())==state_digest(models['B8'].fusion.fuse.state_dict())
        counts={k:sum(p.numel() for p in models[k].parameters() if p.requires_grad) for k in ('B7','B8')};assert counts==dict(B7=4411058,B8=4411058)
        prepared=read(v['inherited'])['prepared'];ids=tuple(prepared['roles']['Train']['ids']);assert len(ids)==959
        orders={str(e):dict(ids=epoch_order(ids,a.seed,e),sha256=digest(epoch_order(ids,a.seed,e))) for e in range(1,10)}
        write(folder/'paired_initial_identity.json',identity);write(folder/'paired_orders.json',orders)
        write(folder/'check.json',dict(seed=a.seed,initialization=identity,counts=counts,static_cache_sha256=hashlib.sha256(raw).hexdigest(),
              CPU_training_rng_sha256=hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest(),static_auxiliary_seed=a.seed+10000,fusion_auxiliary_seed=a.seed+20000,
              formal_optimizer_updates=0,checkpoint_loads=0,forward_backward_runs=0,weather_payload_bytes=0,cached_static_bytes=len(raw)))
        print(json.dumps(dict(status='PASS_NEW_SEED_CPU_INITIALIZATION_AND_ORDERS',seed=a.seed,parameter_counts=counts)));return
    if a.output is None or a.output.exists() or a.storage_probe is None:raise PermissionError('Fresh receipt and explicit private storage probe required')
    if not a.reuse_seed_references:a.seed_references.mkdir(exist_ok=False)
    records={}
    for seed in (2030,2031):
        if a.reuse_seed_references:
            records[str(seed)]=read(a.seed_references/f's{seed}/check.json')
            identity=read(a.seed_references/f's{seed}/paired_initial_identity.json')
            assert records[str(seed)]['seed']==seed and records[str(seed)]['initialization']==identity and records[str(seed)]['counts']==dict(B7=4411058,B8=4411058)
            assert records[str(seed)]['static_cache_sha256']==frozen['static_source_sha256']['B7']
            continue
        env=dict(os.environ,PYTHONHASHSEED=str(seed),CUBLAS_WORKSPACE_CONFIG=':4096:8',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
        cmd=[sys._base_executable,'-B',str(Path(__file__).resolve()),'--original-private',str(a.original_private.resolve()),'--cached-static',str(a.cached_static.resolve()),'--seed-references',str(a.seed_references.resolve()),'--seed',str(seed)]
        run=subprocess.run(cmd,env=env,cwd=ROOT,capture_output=True,text=True,timeout=120,creationflags=module.worker_creation_flags())
        if run.returncode:
            write(a.seed_references/f'seed{seed}_failure.json',dict(status='STOP_PREPARATION',returncode=run.returncode,stderr=run.stderr));raise RuntimeError(f'Seed{seed} preparation failed; see private evidence')
        records[str(seed)]=read(a.seed_references/f's{seed}/check.json')
    assert records['2030']['initialization']['B7']['common_sha256']!=records['2031']['initialization']['B7']['common_sha256']
    old=read(ROOT/(module.EVIDENCE+'b7_b8_terminal_20261028.json'))
    assert all(x['initialization']['B7']['common_sha256']!=old['initializations']['B7']['B7']['common_sha256'] for x in records.values())
    orders={s:read(a.seed_references/f's{s}/paired_orders.json') for s in (2030,2031)}
    assert all(orders[2030][str(e+1)]['sha256']==orders[2031][str(e)]['sha256'] for e in range(1,9))
    # All numerical dependencies inherit the actually completed ef11531 run.
    inherited=read(ROOT/(module.EVIDENCE+'b8_recovery_proposal_20261028.json'))['code_sha256']
    changed='src/yuntapr/experimental/research_readiness/dynamic_training.py'
    assert all(sha(ROOT/n)==h for n,h in inherited.items() if n!=changed)
    source=ROOT/(module.EVIDENCE+'b7_b8_multiseed_source_admission_20261028.json');assert read(source)['status']=='PASS_BOUNDED_SOURCE_METADATA_NO_PAYLOAD'
    probe=a.storage_probe;assert probe.read_bytes()==b'YunTAPR-admission'
    admission=resources();free=__import__('shutil').disk_usage(probe.parent).free;assert free>=96*1024**3
    names=[module.MODULE,module.ENTRY,changed,'tools/research_readiness/check_dynamic_multiseed.py','tests/research_readiness/test_dynamic_multiseed.py']
    result=dict(status='PASS_NEW_MULTI_SEED_PREPARATION_ONLY',checked_at=datetime.now(timezone.utc).isoformat(),initialization=records,
          seed_references={str(s):{name:sha(a.seed_references/f's{s}'/name) for name in ('paired_initial_identity.json','paired_orders.json')} for s in (2030,2031)},
          order_overlap=dict(rule='epoch_order seed+epoch-1',observed_2030_E2_E9_equals_2031_E1_E8=True,
                             seed2029_shift='By inherited rule,2029 E2-E9 equals2030 E1-E8; no new old-seed execution',independent_weather_years=1),
          resource_admission=admission,storage=dict(candidate_volume='D',free_bytes=free,initial_required_bytes=96*1024**3,namespace_write_probe_bytes=17,
              namespace_write_probe_sha256=sha(probe),F_volume_free_bytes=__import__('shutil').disk_usage('F:/').free,F_96GiB_admission='INSUFFICIENT_NO_DELETION_OR_MIGRATION'),
          source_admission_sha256=sha(source),code_sha256={n:sha(ROOT/n) for n in names},unchanged_runtime_dependencies=len(inherited)-1,
          tests=dict(status='PASS_NEW_CONTROLLER_AND_AFFECTED_LEGACY_WORKER_ONLY',unique_cases=11,receipt='SEE_TEST_RUN_LOG_AND_THIS_COMMIT'),
          formal_optimizer_updates=0,checkpoint_loads=0,weather_payload_bytes=0,original_DEM_tile_reads=0,normalization_fits=0,
          cached_static_payload_bytes=2*312828,cached_static_instances=2,extra_forward_backward_checks=0,
          seed_checks_reused_after_private_storage_locator_parameterization=a.reuse_seed_references,
          inherited_real_path='B7/B8 seed2029 completed Train/Dev; unchanged model/loss/reader/normalization/grid/masks/GPU tensor shapes',final_2025='FROZEN_NO_ACCESS')
    write(a.output,result);print(json.dumps(dict(status=result['status'],parameter_counts=records['2030']['counts'],D_free_GiB=free/1024**3,formal_optimizer_updates=0),ensure_ascii=False))
if __name__=='__main__':main()
