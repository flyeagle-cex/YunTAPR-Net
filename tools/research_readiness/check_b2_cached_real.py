"""Fill only the B2 real-tensor gap using existing metered caches. No raw I/O."""
from pathlib import Path
import argparse
import datetime
import gc
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'src'))
os.environ.update(CUBLAS_WORKSPACE_CONFIG=':4096:8', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--proposal', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    a = parser.parse_args()
    if a.output.exists() or os.environ.get('PYTHONHASHSEED') != '2029':
        parser.error('New receipt and PYTHONHASHSEED=2029 required')
    cache = a.cache.resolve()
    allowed = {cache/'train_batch.pt', cache/'dev_batch.pt'}
    raw_attempts = []
    def audit(event, args):
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(args[0]))
        name = str(p).lower()
        if name.endswith(('.nc', '.hgt', '.hgt.zip', '.h5', '.hdf5')) or (name.endswith(('.pt', '.pth', '.ckpt')) and p.resolve() not in allowed):
            raw_attempts.append(p.name)
            raise PermissionError('CACHED_ONLY: no weather-source or model-checkpoint reads')
    sys.addaudithook(audit)
    import torch
    torch.set_num_threads(1)
    from yuntapr.experimental.core_innovation.stage4.data import Batch, read, sha
    from yuntapr.experimental.core_innovation.stage4.engine import resources, state_digest
    from yuntapr.experimental.research_readiness.b2 import fresh_b2, forward_b2, STEM_RULE

    def forbid_optimizer(*args, **kwargs):
        raise PermissionError('REAL_CACHE_CHECK_FORBIDS_OPTIMIZER_CONSTRUCTION_OR_STEP')
    torch.optim.Optimizer.__init__ = forbid_optimizer
    torch.optim.AdamW.step = forbid_optimizer
    proposal = read(a.proposal)
    evidence = read(ROOT/'docs/core_stage4/evidence.json')
    for name in ('batch_receipt.json', 'completion.json', 'cached_verification.json'):
        if sha(cache/name) != evidence['receipt_sha256'][name]:
            raise ValueError('Existing real-cache receipt changed: '+name)
    receipt = read(cache/'batch_receipt.json')
    prior = read(cache/'cached_verification.json')
    if prior['final_data_identity'] != proposal['data']:
        raise ValueError('Cached data/statistics/QC version differs')
    admission = resources()
    if admission['workspace_free_bytes'] < 24*1024**3:
        raise RuntimeError('Formal workspace below 24GiB; retain existing files and stop')
    model, initialization = fresh_b2(2029, stem_rule=STEM_RULE, root=ROOT)
    if initialization['b2_initial_sha256'] != proposal['input_dimension_difference']['b2_initial_sha256']:
        raise ValueError('Frozen numerical initialization changed')
    model = model.cuda()
    before = state_digest(model.state_dict())
    report = dict(status='IN_PROGRESS', scope='EXISTING_REAL_CACHE_B2_ONLY_NOT_SCIENTIFIC_METRICS',
        as_of=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds'),
        source_commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
        inherited_loader_and_read_receipt='docs/core_stage4/evidence.json',
        current_code_sha256={p:sha(ROOT/p) for p in ('src/yuntapr/experimental/research_readiness/b2.py',
            'src/yuntapr/experimental/core_innovation/stage4/data.py','tools/research_readiness/check_b2_cached_real.py')},
        cache_receipt_sha256=sha(cache/'batch_receipt.json'), cache_tensor_sha256=receipt['tensor_sha256'],
        data=proposal['data'], seed=2029, source_read_byte_cap=0, raw_weather_reads=0, raw_2025_reads=0,
        model_checkpoint_loads=0, optimizer_constructions=0, optimizer_updates=0, normalization_refits=0,
        inherited_checks='129 sources,126 epoch summaries and unchanged synthetic checks are reused, not rerun',
        initialization=initialization, resource_admission=admission, cases={})
    try:
        for role, key, n in (('Train','train',2),('Development','dev',1)):
            path = cache/(key+'_batch.pt')
            if sha(path) != receipt['tensor_sha256'][key]:
                raise ValueError('Cached normalized tensor SHA differs')
            batch = torch.load(path,map_location='cpu',weights_only=False)
            if batch.role != role or any(proposal['data'][k] != v for k,v in batch.identity.items()):
                raise ValueError('Cached role or ancestry differs')
            if any(not sid.startswith('2023-' if role=='Train' else '2024-') for sid in batch.ids):
                raise ValueError('Forbidden cached sample year')
            batch = Batch(*(getattr(batch,k)[:n] for k in ('x','native_valid','environment','environment_valid','rate','valid','region')),
                          batch.ids[:n],batch.analyses[:n],role,proposal['data'])
            model.train(role=='Train')
            batch = batch.to('cuda')
            started = time.monotonic()
            with torch.set_grad_enabled(role=='Train'),torch.autocast('cuda',dtype=torch.bfloat16):
                output, loss = forward_b2(model,batch)
            if not torch.isfinite(loss.training_objective):
                raise FloatingPointError('Nonfinite real-data loss')
            if role=='Train':
                loss.training_objective.backward()
                if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):
                    raise FloatingPointError('Missing or nonfinite B2 real-data gradients')
            torch.cuda.synchronize()
            report['cases'][role] = dict(ids=list(batch.ids), cached_native_shape=list(batch.x.shape),
                b2_input_shape=[n,7,501,501], quantile_shape=list(output.conditional_quantiles_log.shape),
                n_valid=loss.n_valid,n_rain=loss.n_rain,loss_finite=True,backward=role=='Train',
                loss=float(loss.training_objective.detach()),elapsed_seconds=time.monotonic()-started)
            model.zero_grad(set_to_none=True)
            del batch,output,loss
            gc.collect()
            torch.cuda.empty_cache()
        if before != state_digest(model.state_dict()):
            raise RuntimeError('Zero-update precheck changed model state')
        report.update(status='PASS_CACHED_REAL_B2_ZERO_UPDATES',weights_unchanged=True,raw_source_open_attempts=raw_attempts)
    except BaseException as exc:
        report.update(status='STOP_NO_AUTOMATIC_RETRY',error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open('x',encoding='utf-8') as f:
            json.dump(report,f,indent=2,allow_nan=False)
        print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
