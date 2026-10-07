"""Engineering-only source identity and full-chain CUDA preflight. Never trains formally."""
from pathlib import Path
import gc
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
import torch
from yuntapr.training import formal_phase_a_v2 as f
from yuntapr.training.phase_a_protocol import seed_reproducibility, state_digest
from yuntapr.training.phase_a_audit_v2 import atomic_json, identity, digest, Counters, SourceFirewall, reconcile_io
from yuntapr.training.phase_a_validation_v2 import LogDomainValidation
from yuntapr.training.upper_tail_v2 import UpperTailDiagnostics
from yuntapr.data import dataset_b1 as data


def environment():
    import numpy,netCDF4
    driver=subprocess.check_output(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'],text=True).strip()
    return {'python': platform.python_version(), 'executable': sys.executable,
            'torch': torch.__version__, 'CUDA': torch.version.cuda,
            'cudnn':torch.backends.cudnn.version(),'numpy':numpy.__version__,'netCDF4':netCDF4.__version__,
            'GPU_driver':driver,
            'GPU': torch.cuda.get_device_name(), 'GPU_total_bytes': torch.cuda.get_device_properties(0).total_memory,
            'deterministic': torch.are_deterministic_algorithms_enabled(),
            'PYTHONHASHSEED': os.environ.get('PYTHONHASHSEED'),
            'CUBLAS_WORKSPACE_CONFIG': os.environ.get('CUBLAS_WORKSPACE_CONFIG'),
            'TF32': torch.backends.cuda.matmul.allow_tf32}


def disk_gate(checkpoint_bytes, log_bytes_per_epoch, completed=None):
    completed = completed or {'B0_MATCHED_V2': 0, 'B1_V2': 0}
    remaining = sum(50 - n for n in completed.values())
    f_needed = int(1.2 * (remaining * (checkpoint_bytes + log_bytes_per_epoch) + 2 * checkpoint_bytes + 2 * 734003200))
    c_needed = int(1.2 * max(1024**3, remaining * 2 * 1024**2))
    proof = {}
    for drive, required in (('F:\\', f_needed), (str(f.REPO_ROOT.anchor), c_needed)):
        free = shutil.disk_usage(drive).free
        proof[drive] = {'free_bytes': free, 'required_bytes': required}
        if free < required: raise OSError('Insufficient storage for all retained epochs: ' + drive)
    return proof


def log_budget_from_smoke(run, cases):
    """Scale measured bytes by actual source exposures and forward counts."""
    estimates = {}
    for kind, frames in (('B0_MATCHED_V2', 1), ('B1_V2', 6)):
        directory = Path(run) / 'smoke' / kind
        selected = [c for c in cases if c['model'] == kind]
        exposures = sum(len(c['sample_ids']) * (frames + 1) for c in selected)
        if not exposures or len(selected) != 4: raise ValueError('Complete smoke cases needed for storage estimate')
        io_bytes = sum(p.stat().st_size for p in directory.glob('raw_access_*.jsonl'))
        diagnostic_sizes = [p.stat().st_size for p in directory.glob('*_diagnostics.jsonl')]
        if len(diagnostic_sizes) != 4 or io_bytes == 0: raise ValueError('Actual smoke I/O journals missing')
        predicted_io = math.ceil(io_bytes / exposures * (10455 + 10501) * (frames + 1))
        predicted_diagnostics = max(diagnostic_sizes) * (5228 + 1313)
        estimates[kind] = {'measured_io_bytes': io_bytes, 'measured_source_exposures': exposures,
            'predicted_io_bytes_per_epoch': predicted_io,
            'predicted_diagnostic_bytes_per_epoch': predicted_diagnostics,
            'other_log_allowance_bytes_per_epoch': 64 * 1024**2,
            'total_bytes_per_epoch': predicted_io + predicted_diagnostics + 64 * 1024**2}
    return estimates


def smoke(contract, run, sources):
    # Exact manifest positions, selected before any model output is read.
    indices = {'train_batch2': [0, 1], 'train_singleton': [10454],
               'validation_batch8': list(range(8)), 'validation_tail5': list(range(10496, 10501))}
    atomic_json(run / 'smoke_sample_selection.json', indices, immutable=True)
    results, checkpoint_sizes = [], []
    for kind in f.KINDS:
        io_root = run / 'smoke' / kind; io_root.mkdir(parents=True)
        firewall = SourceFirewall(sources, io_root / 'raw_access_parent.jsonl', mask_path=contract.protocol['identity']['yunnan_mask']['path'])
        with firewall.installed():
            stage = data.STAGE_ROOT / ('v2_preflight_' + run.name + '_' + kind)
            sets, mask = f.datasets(contract, kind, stage, io_root, sources)
            for name, chosen in indices.items():
                models, proof = f.paired_initialization(contract)
                model = models.pop(kind).cuda(); del models
                optimizer, groups = f.optimizer_for(model, kind, contract)
                counters = Counters('ENGINEERING_ONLY')
                training = name.startswith('train')
                phase = 'TRAIN' if training else 'VALIDATION'
                year = 2023 if training else 2024
                # Production workers, staging, normalization, mapping and collate.
                from torch.utils.data import DataLoader
                source = DataLoader(sets[year], batch_sampler=[chosen], num_workers=2, pin_memory=False,
                    persistent_workers=False, prefetch_factor=1, worker_init_fn=data.worker_init, collate_fn=data.collate)
                with f.loader_items(source) as iterator:
                    items = next(iterator); batch = data.make_batch(items)
                observer = UpperTailDiagnostics(mask, phase, io_root / (name + '_diagnostics.jsonl'))
                torch.cuda.reset_peak_memory_stats(); start = time.monotonic()
                if training:
                    model.train(); u = 1 if len(chosen) == 2 else 5228
                    metrics, _ = f.update(model, optimizer, batch, u, counters, observer)
                    if metrics['actual_denominator'] != len(chosen)*3430 or (u == 5228 and metrics['LR'] != 1e-4):
                        raise AssertionError('Smoke actual tail boundary mismatch')
                    # Engineering serialization only, never a formal root/checkpoint.
                    temp = run / (kind + '_' + name + '.fixture.pt')
                    torch.save({'model': model.state_dict(), 'optimizer': optimizer.state_dict()}, temp)
                    ref = identity(temp); checkpoint_sizes.append(ref['bytes'])
                    restored = torch.load(temp, weights_only=False, map_location='cpu')
                    if state_digest(restored['model']) != state_digest(model.state_dict()) or state_digest(restored['optimizer']) != state_digest(optimizer.state_dict()):
                        raise AssertionError('Engineering serialization mismatch')
                    temp.unlink()  # exact owned fixture file, never a recursive delete
                    del restored
                else:
                    model.eval()
                    before = state_digest(model.state_dict())
                    with torch.inference_mode():
                        out, loss = f.forward_loss(model, batch, counters, 'VALIDATION')
                        accumulator = LogDomainValidation(); accumulator.add(out, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask)
                        observer.observe(out.conditional_quantiles_log, batch.sample_ids)
                        metrics = accumulator.report()
                    if state_digest(model.state_dict()) != before: raise AssertionError('Validation mutated model')
                    del out, loss
                torch.cuda.synchronize()
                record = {'model': kind, 'case': name, 'sample_ids': batch.sample_ids, 'metrics': metrics,
                          'wall_seconds': time.monotonic()-start, 'counters': counters.snapshot(),
                          'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
                          'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
                          'diagnostics': observer.report(), 'FORMAL_OPTIMIZER_STEPS': 0}
                atomic_json(io_root / (name + '.json'), record, immutable=True); results.append(record)
                f.progress(run, status='RUNNING', phase='GPU_SMOKE', model=kind, case=name,
                           gpu_memory_allocated=record['peak_allocated_bytes'], diagnostics=record['diagnostics'])
                del model, optimizer, batch, items, observer; gc.collect(); torch.cuda.empty_cache()
    if sum(x['counters']['OPTIMIZER_STEPS'] for x in results) != 4:
        raise AssertionError('Exactly four isolated engineering steps required')
    return {'status': 'PASS', 'cases': results, 'ENGINEERING_OPTIMIZER_STEPS': 4,
            'FORMAL_OPTIMIZER_STEPS': 0, 'max_checkpoint_bytes': max(checkpoint_sizes),
            'temporary_checkpoint_files_remaining': len(list(run.glob('*.fixture.pt')))}


def execute(run, tests_summary):
    run = Path(run).resolve()
    if run.parent != (f.REPO_ROOT / 'docs/v2_phase_a_execution/runs').resolve():
        raise ValueError('Independent v2 engineering evidence root required')
    run.mkdir(parents=True, exist_ok=False)
    try:
        f.progress(run, status='RUNNING', phase='METADATA_PREFLIGHT', FORMAL_OPTIMIZER_STEPS=0, **{'2025_RAW_ACCESS': 0})
        contract = f.Contract.load(); sources = contract.sources()
        atomic_json(run / 'source_allowlist.json', sources, immutable=True)
        atomic_json(run / 'executed_code_identity.json', contract.code, immutable=True)
        tests = json.loads(Path(tests_summary).read_text(encoding='utf-8'))
        if tests.get('status') != 'PASS' or tests.get('code_sha256') != contract.code:
            raise ValueError('Tests must pass on these exact source bytes')
        atomic_json(run / 'test_evidence_identity.json', identity(tests_summary), immutable=True)
        seed_reproducibility(); torch.set_num_threads(2); f.assert_environment()
        env = environment(); atomic_json(run / 'environment.json', env, immutable=True)
        # Independently spawned fresh pair generators, no optimizer or raw reads.
        initial = []
        for index in range(2):
            dest = run / f'initialization_process_{index}.json'
            subprocess.run([sys.executable, '-B', str(f.REPO_ROOT/'scripts/run_paired_phase_a_v2.py'),
                            'initialization-proof', '--output', str(dest)], cwd=f.REPO_ROOT, check=True)
            initial.append(json.loads(dest.read_text(encoding='utf-8')))
        if initial[0] != initial[1]: raise ValueError('Independent process paired initialization mismatch')
        atomic_json(run / 'paired_initialization.json', initial[0], immutable=True)
        # Full source catalogue identity verification, never directory crawling.
        firewall = SourceFirewall(sources, run / 'raw_access_parent.jsonl')
        started = time.monotonic(); checked_bytes = 0
        with firewall.installed():
            for index, (path, ref) in enumerate(sources.items(), 1):
                size = Path(path).stat().st_size
                if ref['expected_bytes'] is not None and size != ref['expected_bytes']:
                    raise ValueError('Source size mismatch: ' + path)
                if digest(path) != ref['sha256']: raise ValueError('Source SHA mismatch: ' + path)
                checked_bytes += size
                from yuntapr.training.phase_a_audit_v2 import append_event
                append_event(run / 'source_identity_checks.jsonl', 'SOURCE_IDENTITY_PASS', path=path, bytes=size, sha256=ref['sha256'])
                if index % 10 == 0 or index == len(sources):
                    f.progress(run, status='RUNNING', phase='SOURCE_SHA_PREFLIGHT', checked_files=index,
                               total_files=len(sources), checked_bytes=checked_bytes,
                               ETA_seconds=(time.monotonic()-started)/index*(len(sources)-index),
                               FORMAL_OPTIMIZER_STEPS=0, **{'2025_RAW_ACCESS': 0})
        actual_smoke = smoke(contract, run, sources)
        atomic_json(run / 'gpu_smoke.json', actual_smoke, immutable=True)
        budgets = log_budget_from_smoke(run, actual_smoke['cases'])
        atomic_json(run / 'measured_log_storage_budget.json', budgets, immutable=True)
        log_bytes = max(v['total_bytes_per_epoch'] for v in budgets.values())
        storage = disk_gate(actual_smoke['max_checkpoint_bytes'], log_bytes)
        contract.unchanged(); io_proof = reconcile_io(run)
        if io_proof['DENIED_ATTEMPTS']: raise PermissionError('Unexpected denied source attempt')
        report = {'status': 'PASS', 'scope': 'ENGINEERING_ONLY', 'code_sha256': contract.code,
                  'science_baseline': f.BASELINE, 'working_commit': f.git('rev-parse','HEAD'),
                  'protocol_sha256': f.PROTOCOL_SHA, 'head_sha256': f.HEAD_SHA,
                  'normalization_sha256': data.SCALER_SHA, 'paired_initialization': initial[0],
                  'environment': env, 'storage': storage, 'log_bytes_per_epoch_budget': log_bytes,
                  'checkpoint_bytes_budget': actual_smoke['max_checkpoint_bytes'],
                  'all_regression_tests_passed': True, 'new_runner_tests_passed': True,
                  'test_evidence': identity(tests_summary), 'source_files_verified': len(sources),
                  'FORMAL_TRAINING_AUTHORIZED': False, 'V2_PHASE_A_AUTHORIZED': False,
                  'V2_PHASE_A_STARTED': False, 'V2_PHASE_B_AUTHORIZED': False,
                  'FORMAL_OPTIMIZER_STEPS': 0, 'ENGINEERING_OPTIMIZER_STEPS': 4,
                  '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'io': io_proof,
                  'RESEARCHER_DECISION_REQUIRED': True}
        atomic_json(run / 'preflight_manifest.json', report, immutable=True)
        f.progress(run, status='COMPLETE', phase='PREFLIGHT_COMPLETE_WAITING_RESEARCHER', **{k:v for k,v in report.items() if k != 'status'})
    except BaseException as exc:
        atomic_json(run / 'failure.json', {'status':'FAILED_STOP', 'error':repr(exc), 'traceback':traceback.format_exc(),
                    'FORMAL_OPTIMIZER_STEPS':0, '2025_RAW_ACCESS':0}, immutable=True)
        f.progress(run, status='FAILED_STOP', phase='PREFLIGHT_FAILED', error=repr(exc), FORMAL_OPTIMIZER_STEPS=0)
        raise
