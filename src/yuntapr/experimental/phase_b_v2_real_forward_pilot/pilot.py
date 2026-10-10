"""One finite real-data/inference transaction; no training or evaluation metrics."""
from __future__ import annotations
from contextlib import ExitStack, contextmanager
import gc
import json
import math
from pathlib import Path
import sys
import time
from unittest.mock import patch
import torch
from yuntapr.models.quantile_v2.models import B0MatchedV2, B1V2
from yuntapr.models.quantile_v2.outputs import LogDomainOutput, validate_log_quantiles
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.experimental.phase_b_v2_integration.initialization import fresh_paired_models, seeded_environment
from yuntapr.experimental.phase_b_v2_full_payload_integrity.audit import reason
from . import BASELINE, FLAGS, LIMITS, SEED, SCOPE
from .resources import Budget, cuda_admission, memory, utcnow
from .plan import FrozenPlan
from .adapter import RealAdapter, RealBatch

@contextmanager
def inference_only_operations():
    def blocker():
        # Distinct callables avoid conflicting torch._dynamo lazy tracing rules.
        def deny(*args, **kwargs): raise PermissionError('PILOT_FORBIDS_GRAD_OPTIMIZER_OR_WEIGHT_IO')
        return deny
    with ExitStack() as stack:
        for target, name in ((torch.Tensor, 'backward'), (torch.autograd, 'backward'),
                             (torch.autograd, 'grad'), (torch.optim.Optimizer, '__init__'),
                             (torch, 'load'), (torch, 'save')):
            stack.enter_context(patch.object(target, name, blocker()))
        yield

def validate_output(output: LogDomainOutput, size: int, device) -> dict:
    if type(output) is not LogDomainOutput:
        raise ValueError('FROZEN_DUAL_HEAD_OUTPUT_REQUIRED')
    for name, channels, dtype in (('rain_logit', 1, torch.bfloat16),
        ('rain_prob', 1, torch.bfloat16), ('conditional_quantiles_log', 32, torch.float64)):
        value = getattr(output, name)
        if value.shape != (size, channels, 100, 100) or value.dtype != dtype or value.device != device:
            raise ValueError('FROZEN_OUTPUT_SHAPE_PRECISION_DEVICE')
        if value.requires_grad or value.grad_fn is not None or not bool(torch.isfinite(value).all()):
            raise FloatingPointError('OUTPUT_GRAPH_OR_NONFINITE')
    validate_log_quantiles(output.conditional_quantiles_log)
    if (not bool(((output.rain_prob >= 0) & (output.rain_prob <= 1)).all())
        or not torch.equal(output.rain_prob, torch.sigmoid(output.rain_logit))):
        raise ValueError('OCCURRENCE_SIGMOID_SUPPORT')
    if output.native_feature_shape != (size, 48, 501, 501) or output.target_feature_shape != (size, 48, 100, 100):
        raise ValueError('REAL_NATIVE_SP04_FEATURE_SHAPES')
    support = output.target_support_fraction
    if support.shape != (size, 1, 100, 100) or not bool((support == 1).all()):
        raise ValueError('REAL_SP04_FULL_SUPPORT')
    if not bool((output.b13_invalid_count == 0).all()) or not bool((output.b13_valid_fraction == 1).all()):
        raise ValueError('REAL_M1_OUTPUT_SUPPORT')
    q = output.conditional_quantiles_log
    return {'probability_shape': list(output.rain_prob.shape), 'probability_dtype': 'bfloat16',
            'quantile_shape': list(q.shape), 'quantile_dtype': 'float64',
            'quantile_space': 'log1p(mm/h)', 'finite': True, 'strictly_monotone': True,
            'support_above_log1p_0_1': True, 'outputs_require_grad': False,
            'FP32_physical_conversion_overflow_risk': bool((q > math.log1p(torch.finfo(torch.float32).max)).any()),
            'FP64_physical_conversion_overflow_risk': bool((q > math.log1p(torch.finfo(torch.float64).max)).any()),
            'physical_conversion_performed': False, 'scientific_performance_evidence': False}

def forward_real(model, batch: RealBatch, kind: str, owner: object) -> tuple[dict, float]:
    batch.validate(kind, owner)
    expected = {'B0_MATCHED_V2': B0MatchedV2, 'B1_V2': B1V2}[kind]
    if type(model) is not expected or model.training or batch.x.device.type != 'cuda':
        raise PermissionError('EXACT_REAL_FRESH_MODEL_EVAL_CUDA')
    if any(p.requires_grad or p.grad is not None or p.dtype != torch.float32 or p.device != batch.x.device for p in model.parameters()):
        raise ValueError('FROZEN_FP32_NO_GRAD_MODEL_PARAMETERS')
    if model.heads.numerics.epsilon_w != 1e-4 or model.heads.numerics.epsilon_span != 1e-4:
        raise ValueError('FROZEN_V2_EPSILON')
    torch.cuda.synchronize(); start = time.perf_counter()
    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
        if torch.is_grad_enabled(): raise PermissionError('INFERENCE_MODE_REQUIRED')
        output = model(batch.x, batch.native_valid)
        result = validate_output(output, 2, batch.x.device)
    torch.cuda.synchronize()
    result['inference_mode_enabled'] = True
    return result, time.perf_counter()-start

def run(folder: Path) -> dict:
    carry_file = folder/'pre_access_carry.json'
    carry = json.loads(carry_file.read_bytes()) if carry_file.exists() else None
    budget = Budget(folder, carry=carry); adapter = None; models = {}; records = []
    status = {'scope': SCOPE, 'baseline_commit': BASELINE, 'limits': LIMITS,
              'started_at_utc': utcnow(), 'seed': SEED, 'overall_status': 'NOT_VERIFIED',
              'scientific_performance_evidence': False, 'failure': None, **FLAGS}
    status['pre_access_failed_attempt'] = carry
    try:
        budget.emit('PILOT_STARTED', limits=LIMITS, baseline=BASELINE, seed=SEED)
        admission = cuda_admission(); budget.check(); status['cuda_admission'] = admission
        with inference_only_operations(), seeded_environment(SEED):
            plan = FrozenPlan(budget)
            status['public_source_pins'] = list(plan.public.pins.values())
            models, proof = fresh_paired_models(SEED)
            status['initialization'] = {'reused_helper': 'fresh_paired_models',
                'helper_origin_scope': proof['scope'], 'historical_checkpoint_loaded': False,
                'paired_same_shape_bit_identical': proof['same_shape_shared_bit_identical'],
                'initial_cpu_state_sha256': proof['state_sha256'], 'parameter_counts': proof['parameter_counts']}
            for model in models.values(): model.eval().requires_grad_(False).to('cuda:0')
            status['state_sha256_before'] = {kind: state_digest(m.state_dict()) for kind, m in models.items()}
            if status['state_sha256_before'] != proof['state_sha256']:
                raise ValueError('FRESH_DEVICE_TRANSFER_CHANGED_STATE')
            budget.check(); cuda_admission()
            adapter = RealAdapter(plan, budget)
            adapter.initialize_geometry()
            for pair in range(24):
                budget.check(); batches, scenes = adapter.pair(pair)
                for kind in ('B0_MATCHED_V2', 'B1_V2'):
                    cuda_admission(); budget.reserve_forward(kind, pair, 2)
                    torch.cuda.reset_peak_memory_stats(); transfer = time.perf_counter()
                    batch = batches[kind].cuda(); torch.cuda.synchronize()
                    transfer_seconds = time.perf_counter()-transfer
                    checks, seconds = forward_real(models[kind], batch, kind, adapter.owner)
                    after = state_digest(models[kind].state_dict())
                    if after != status['state_sha256_before'][kind]:
                        raise ValueError('MODEL_STATE_CHANGED_DURING_REAL_FORWARD')
                    if any(p.grad is not None for p in models[kind].parameters()):
                        raise ValueError('PARAMETER_GRADIENT_APPEARED')
                    resources = budget.check()
                    record = {'model': kind, 'pair': pair, 'scene_keys': list(batch.scene_keys),
                        'input_shape': list(batch.x.shape), 'input_dtype': 'float32',
                        'input_sha256': batch.tensor_sha256, 'supervision_sha256': batch.supervision_sha256,
                        'host_to_device_and_sync_seconds': transfer_seconds, 'forward_and_checks_seconds': seconds,
                        'cuda_peak_allocated_bytes': torch.cuda.max_memory_allocated(),
                        'cuda_peak_reserved_bytes': torch.cuda.max_memory_reserved(), 'cpu': resources,
                        'state_sha256_after': after, 'state_unchanged': True, 'checks': checks}
                    budget.complete_forward(kind); budget.emit('FORWARD_COMPLETED', **record); records.append(record)
                    del batch; gc.collect()
                del batches
                print(json.dumps({'stage': 'REAL_FORWARD', 'decoded_scenes': adapter.next_scene,
                    'successful_model_batches': budget.successes, 'content_GiB': budget.bytes/1024**3,
                    'elapsed_seconds': time.monotonic()-budget.start}), flush=True)
            status['state_sha256_after'] = {kind: state_digest(m.state_dict()) for kind, m in models.items()}
            if status['state_sha256_after'] != status['state_sha256_before'] or budget.successes != {'B0_MATCHED_V2': 24, 'B1_V2': 24}:
                raise ValueError('FINAL_MODEL_OR_COVERAGE_IDENTITY')
            budget.check(); status['overall_status'] = 'BOUNDED_REAL_FORWARD_PILOT_PASS'
    except BaseException as error:
        status['failure'] = reason(error); budget.stopped = True
        status['overall_status'] = 'NOT_VERIFIED_STOPPED'
        budget.emit('PILOT_STOPPED', failure=status['failure'])
    finally:
        if adapter is not None: adapter.reader.close()
        status.update(finished_at_utc=utcnow(), elapsed_seconds=time.monotonic()-budget.start,
            decoded_scenes=adapter.next_scene if adapter is not None else 0,
            model_batch_attempts=budget.attempts, model_batch_successes=budget.successes,
            model_scene_forwards={k: v*2 for k, v in budget.successes.items()},
            accounted_content_bytes=budget.bytes, cpu_resources=memory(),
            raw_reads=adapter.reader.reads if adapter is not None else [],
            memory_netcdf_views=adapter.reader.views if adapter is not None else 0,
            model_batch_records=records, actual_tail_batch=2,
            all_raw_and_model_counters_are_application_scope=True,
            no_real_pixel_or_model_weight_arrays_published=True,
            operational_near_realtime_availability='NOT_VERIFIED',
            prior_full_preflight_overall_status='NOT_VERIFIED_UNCHANGED')
        (folder/'worker_status.json').write_bytes((json.dumps(status, indent=2, allow_nan=False)+'\n').encode())
        budget.close()
    return status
