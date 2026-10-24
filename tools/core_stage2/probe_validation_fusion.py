"""New batch-8 inference memory / CUDA AMP fusion boundary checks, synthetic only."""
from probe_models import ROOT, torch, resource_snapshot, require_resources, SpectralCandidate, CandidateNumerics, CHANNELS, MEE_KEYS
from pathlib import Path
import argparse, gc, json
from yuntapr.experimental.core_innovation.stage2.fusion import paired_fusion_candidates
from yuntapr.experimental.core_innovation.grid import GridSpec


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    if not a.output.resolve().is_relative_to(ROOT/'docs/core_stage2') or a.output.exists(): raise PermissionError('New scoped evidence required')
    torch.set_num_threads(1); torch.manual_seed(0)
    report = dict(scope='NEW_SYNTHETIC_VALIDATION_MEMORY_AND_FUSION_AMP', optimizer_updates=0,
        real_weather_reads=0, raw_2025_reads=0, inference=[], fusion=[])
    try:
        require_resources(resource_snapshot(full_backward=True))
        for kind in ('B3', 'B4'):
            require_resources(resource_snapshot(full_backward=True))
            model = SpectralCandidate(kind, numerics=CandidateNumerics(epsilon_w=1e-4, epsilon_span=1e-4),
                mee_width=16 if kind == 'B4' else None).cuda().eval()
            x = torch.randn(8, 42, 501, 501, device='cuda'); valid = torch.ones_like(x, dtype=torch.bool)
            kwargs = {}
            if model.mee:
                env = torch.randn(8, 11, 100, 100, device='cuda')
                kwargs = dict(environment=env, environment_valid=torch.ones_like(env, dtype=torch.bool),
                    environment_keys=MEE_KEYS, environment_grid=model.grid)
            torch.cuda.reset_peak_memory_stats()
            with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
                out = model(x, valid, channel_order=CHANNELS, **kwargs)
            torch.cuda.synchronize()
            report['inference'].append(dict(kind=kind, batch=8, status='PASS', peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_reserved_bytes=torch.cuda.max_memory_reserved(), output_shape=list(out.rain_logit.shape)))
            del out, x, valid, model, kwargs
            if kind == 'B4': del env
            gc.collect(); torch.cuda.empty_cache()
        full_pair = paired_fusion_candidates(feature_channels=[48, 96, 192, 256], gfs_channels=[11]*4,
            terrain_channels=[8]*4, projection_width=16, modulation_limit=.5)
        report['four_scale_active_parameter_counts'] = [sum(p.numel() for p in m.parameters()) for m in full_pair]
        del full_pair
        grid = GridSpec([26., 25., 24.], [101., 102., 103.])
        for model in paired_fusion_candidates(feature_channels=[4], gfs_channels=[11], terrain_channels=[8],
                projection_width=3, modulation_limit=.5):
            model = model.cuda()
            f = torch.randn(1, 4, 3, 3, device='cuda', dtype=torch.bfloat16, requires_grad=True)
            g = torch.randn(1, 11, 3, 3, device='cuda', requires_grad=True)
            t = torch.randn(1, 8, 3, 3, device='cuda', requires_grad=True)
            mask = torch.ones(1, 1, 3, 3, device='cuda', dtype=torch.bool)
            with torch.autocast('cuda', dtype=torch.bfloat16):
                out = model([f], [g], [t], [mask], [mask], [mask], feature_grids=[grid], gfs_grids=[grid], terrain_grids=[grid])
                out.values[0].float().sum().backward()
            if not torch.equal(out.values[0], f) or any(p.grad is None or not bool(torch.isfinite(p.grad).all()) for p in model.parameters()):
                raise AssertionError('CUDA AMP fusion identity/gradient failure')
            report['fusion'].append(dict(kind=model.kind, status='PASS_CUDA_AMP_IDENTITY_FINITE_GRADIENTS', feature_dtype=str(out.values[0].dtype)))
            del out, f, g, t, mask, model
        report['status'] = 'PASS'
    except Exception as exc: report.update(status='STOPPED_NO_RETRY', reason=type(exc).__name__+': '+str(exc))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x', encoding='utf-8') as f: json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2)); raise SystemExit(0 if report['status'] == 'PASS' else 1)
