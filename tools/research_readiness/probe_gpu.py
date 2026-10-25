"""Synthetic B2 forward/backward and validation memory, zero optimizer steps."""
from pathlib import Path
import argparse
import gc
import json
import os
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.dont_write_bytecode = True
os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', CUBLAS_WORKSPACE_CONFIG=':4096:8')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error('Do not overwrite a resource receipt')
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)) and os.fsdecode(args[0]).lower().endswith(('.nc', '.hgt', '.hgt.zip', '.pt', '.pth', '.ckpt', '.h5', '.hdf5')):
            raise PermissionError('Synthetic probe forbids raw weather/checkpoint reads')
    sys.addaudithook(audit)
    import torch
    torch.set_num_threads(1)
    from yuntapr.experimental.core_innovation.stage4.engine import resources
    from yuntapr.experimental.core_innovation.stage4 import POPULATION_SHA
    from yuntapr.experimental.research_readiness.b2 import fresh_b2, forward_b2, STEM_RULE
    report = dict(status='IN_PROGRESS', scope='SYNTHETIC_ENGINEERING_ONLY', raw_weather_reads=0,
                  checkpoint_loads=0, optimizer_constructions=0, optimizer_updates=0,
                  python_version=sys.version, torch_version=torch.__version__, cuda_build=torch.version.cuda)
    try:
        report['admission'] = resources()
        model, init = fresh_b2(2029, stem_rule=STEM_RULE, root=ROOT)
        model = model.cuda()
        report['initialization'] = init
        report['parameter_bytes'] = sum(p.numel()*p.element_size() for p in model.parameters())
        report['modes'] = {}
        for name, n, backward in [('train_batch2', 2, True), ('validation_batch8', 8, False)]:
            gc.collect()
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            model.train(backward)
            x = torch.zeros(n, 42, 501, 501, device='cuda')
            region = torch.zeros(n, 1, 100, 100, dtype=torch.bool, device='cuda')
            region.flatten(1)[:, :3430] = True
            batch = SimpleNamespace(x=x, native_valid=torch.ones_like(x, dtype=torch.bool),
                                    identity=dict(population_sha256=POPULATION_SHA), ids=tuple(range(n)),
                                    rate=torch.ones(n, 1, 100, 100, device='cuda'),
                                    valid=torch.ones_like(region), region=region)
            torch.cuda.synchronize()
            start = time.perf_counter()
            with torch.set_grad_enabled(backward), torch.autocast('cuda', dtype=torch.bfloat16):
                out, loss = forward_b2(model, batch)
            if backward:
                loss.training_objective.backward()
                missing = [name for name, p in model.named_parameters() if p.grad is None or not torch.isfinite(p.grad).all()]
                if missing:
                    raise RuntimeError('Missing/nonfinite synthetic gradients: '+repr(missing))
            torch.cuda.synchronize()
            report['modes'][name] = dict(seconds_single_cold_pass=time.perf_counter()-start,
                                         peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                                         peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                                         output_quantile_shape=list(out.conditional_quantiles_log.shape),
                                         finite_loss=bool(torch.isfinite(loss.training_objective)))
            model.zero_grad(set_to_none=True)
            del x, region, batch, out, loss
        report['analytical_AdamW_m_v_additional_bytes'] = 2*report['parameter_bytes']
        report['status'] = 'PASS_SYNTHETIC_ONLY_FORMAL_PEAK_NOT_VERIFIED'
        report['limitations'] = ['No AdamW step or allocated optimizer moments; their bytes are analytical.',
                                 'One cold synthetic pass is not a wall-time benchmark and excludes source decoding, metrics SQLite and checkpoint writes.',
                                 'Actual formal GPU peak and resource availability must be admitted again after researcher approval.']
    except BaseException as exc:
        report.update(status='STOP_RESOURCE_OR_PROBE_FAILURE', error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        with a.output.open('x', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
