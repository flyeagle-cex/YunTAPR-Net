"""One synthetic full-grid forward/backward per candidate; no optimizer steps.

Not a throughput benchmark, loss validation or training authorization. Stop on
resource failure; no smaller-batch fallback or automatic retry is performed.
"""
from pathlib import Path
import argparse, gc, json, os, sys, time
ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True; sys.path.insert(0, str(ROOT/'src'))
os.environ['OMP_NUM_THREADS'] = '1'; os.environ['MKL_NUM_THREADS'] = '1'
import torch
from yuntapr.experimental.phase_b_v2_integration.resources import resource_snapshot, require_resources
from yuntapr.experimental.core_innovation.stage2 import CHANNELS, MEE_KEYS
from yuntapr.experimental.core_innovation.stage2.models import SpectralCandidate
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    if not a.output.resolve().is_relative_to(ROOT/'docs/core_stage2') or a.output.exists():
        raise PermissionError('New scoped evidence path required')
    torch.set_num_threads(1); torch.manual_seed(0)
    report = dict(scope='SYNTHETIC_FULL_NATIVE_GRID_NO_OPTIMIZER', batch=2, native_shape=[501, 501],
        mixed_precision='BF16_AUTOCAST_FP32_PARAMETERS', optimizer_constructed=False,
        optimizer_updates=0, raw_weather_reads=0, raw_2025_reads=0, candidates=[])
    try:
        admission = resource_snapshot(full_backward=True); require_resources(admission)
        report['admission'] = admission
        for kind in ('B3', 'B4', 'B1_GFS_PILOT'):
            require_resources(resource_snapshot(full_backward=True))
            model = SpectralCandidate(kind, numerics=CandidateNumerics(epsilon_w=1e-4, epsilon_span=1e-4),
                mee_width=None if kind == 'B3' else 16).cuda()
            x = torch.randn(2, model.input_channels, 501, 501, device='cuda')
            mask = torch.ones_like(x, dtype=torch.bool)
            extra = {}
            if model.mee:
                env = torch.randn(2, 11, 100, 100, device='cuda')
                env_valid = torch.ones_like(env, dtype=torch.bool)
                env_valid[:, [2, 4, 6, 7], :20] = False
                extra = dict(environment=env, environment_valid=env_valid, environment_grid=model.grid, environment_keys=MEE_KEYS)
            torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats(); started = time.perf_counter()
            with torch.autocast('cuda', dtype=torch.bfloat16):
                out = model(x, mask, channel_order=('B13',) if kind == 'B1_GFS_PILOT' else CHANNELS, **extra)
                # Numerical probe only: no frozen scientific loss is replaced.
                scalar = out.rain_logit.float().square().mean()+out.conditional_quantiles_log.mean()
            scalar.backward(); torch.cuda.synchronize()
            if any(p.grad is None or not bool(torch.isfinite(p.grad).all()) for p in model.parameters()):
                raise AssertionError('Missing/nonfinite parameter gradient')
            report['candidates'].append(dict(kind=kind, status='PASS', parameters=sum(p.numel() for p in model.parameters()),
                elapsed_seconds=time.perf_counter()-started, peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_reserved_bytes=torch.cuda.max_memory_reserved(), output_logit_shape=list(out.rain_logit.shape),
                output_quantile_shape=list(out.conditional_quantiles_log.shape), all_parameter_gradients_finite=True,
                nonzero_parameter_gradient_tensors=sum(bool((p.grad != 0).any()) for p in model.parameters()),
                parameter_tensors=sum(1 for _ in model.parameters()), identity_initialized_paths_may_start_with_zero_gradients=True))
            del out, scalar, x, mask, model, extra
            if kind != 'B3': del env, env_valid
            gc.collect(); torch.cuda.empty_cache()
        report['status'] = 'PASS'
    except Exception as exc:
        report.update(status='STOPPED_NO_RETRY', reason=type(exc).__name__+': '+str(exc))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x', encoding='utf-8') as f: json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['status'] == 'PASS' else 1)
