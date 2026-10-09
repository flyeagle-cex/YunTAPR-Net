"""Explicit full-2024 read-only BEST review after BOTH v2 Phase-A runs finish.

No training default, optimizer, backward, reselection, physical materialization,
Phase-B or 2025. Uses pinned training modules without editing their bytes.
"""
import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
EXECUTION = REPO.parent / 'YunTAPR-Net-v2-phase-a-execution'
PAIR = REPO / 'docs/formal_training_v2/pair_20261007T070503_825794Z'
ORIGIN = REPO / 'docs/v2_phase_a_authorized/pair_20261007T070503_825794Z/authorization.json'
ORIGIN_SHA = 'e32404d0d397dd62e1763d3fb16b4a8d8c72fb79ba52bae3f40ac095f4492869'
sys.path[:0] = [str(EXECUTION / 'src'), str(EXECUTION / 'scripts')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--authorization', required=True, type=Path)
    parser.add_argument('--authorization-sha256', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    # Reuse the already tested lifecycle gate, including the latest process exit,
    # full early-stop history and all completed-epoch transaction markers.
    with args.authorization.open('rb') as stream:
        actual_authorization_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual_authorization_sha != args.authorization_sha256:
        raise PermissionError('Completion authorization SHA mismatch')
    sys.path.insert(0, str(REPO / 'docs/v2_phase_a_review'))
    from completion_gate import check_pair
    completion_gate = check_pair(args.authorization)
    if completion_gate['status'] != 'METADATA_COMPLETION_GATE_PASS' or not args.execute:
        print(json.dumps(completion_gate, ensure_ascii=False), flush=True); return
    if completion_gate['origin_authorization_sha256'] != ORIGIN_SHA:
        raise PermissionError('Another experiment authority')
    from review_v2_helpers import ReadOnlyMetrics, inference_only
    out = args.output.resolve()
    if not out.is_relative_to(REPO / 'docs/v2_paired_phase_a_review/runs'):
        raise PermissionError('Independent v2 review evidence root required')
    if Path('F:/pytorch/Research/outputs/formal_training/paired_v2_gpu.lock').exists():
        raise PermissionError('Formal runner must exit before read-only review')
    out.mkdir(parents=True, exist_ok=False)
    def save(path, value):
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')
    try:
        import torch
        torch.set_num_threads(2)
        from yuntapr.training import formal_phase_a_v2 as f
        from yuntapr.training.checkpoint_v2 import verify_file
        from yuntapr.training.phase_a_audit_v2 import SourceFirewall, reconcile_io, append_event
        from yuntapr.training.upper_tail_v2 import UpperTailDiagnostics
        from paired_phase_a_v2.preflight import environment
        assert f.digest(ORIGIN) == ORIGIN_SHA
        origin = f.read_json(ORIGIN)
        assert f.git('rev-parse', 'HEAD', root=EXECUTION) == origin['execution_commit']
        assert not f.git('status', '--porcelain', '--untracked-files=normal', root=EXECUTION)
        contract = f.Contract.load(EXECUTION)
        assert contract.code == origin['code_sha256']
        gate = f.read_json(origin['preflight_path'])
        assert f.digest(origin['preflight_path']) == origin['preflight_sha256']
        f.seed_reproducibility(); f.assert_environment()
        assert environment() == gate['environment']
        sources = {path: ref for path, ref in contract.sources().items() if ref['year'] == 2024}
        assert sources and all(ref['year'] == 2024 and 3 <= ref['month'] <= 10 for ref in sources.values())
        frozen_before = {str(p): f.digest(p) for p in (ORIGIN, EXECUTION / f.PROTOCOL, EXECUTION / f.HEAD)}
        historical_refs = []
        completion_auth = f.read_json(args.authorization)
        for kind in f.KINDS:
            local_root = Path(completion_auth['checkpoint_roots'][kind]) / completion_auth['run_ids'][kind]
            for row in f.read_json(PAIR / kind / 'training_validation_history.json'):
                for ref in [row['checkpoint'], *row['local_epoch_artifacts']]:
                    path = Path(ref['absolute_local_path']).resolve()
                    if not path.is_relative_to(local_root.resolve()):
                        raise PermissionError('Historical artifact outside frozen model root')
                    assert path.stat().st_size == ref['bytes'] and f.digest(path) == ref['sha256']
                    historical_refs.append(ref)
        save(out / 'pre_inference_identity.json', {'status': 'PASS', 'metadata_completion_gate': completion_gate,
             'completion_authorization_sha256': args.authorization_sha256,
             'historical_checkpoint_and_epoch_artifacts': historical_refs,
             'evaluation_year': 2024, 'OPTIMIZER_STEPS': 0, 'BACKWARD_CALLS': 0})
        reports = {}
        for kind in f.KINDS:
            evidence = out / kind; evidence.mkdir()
            source = PAIR / kind
            best = f.read_json(source / 'best_checkpoint_identity.json')
            final = f.read_json(source / 'final_report.json')
            assert best['epoch'] == final['best_checkpoint_epoch'] and best['model'] == kind
            registry = f.read_json(source / 'checkpoint_registry.json')
            assert best == registry['BEST']
            marker = f.read_json(source / f"epoch_{best['epoch']:03d}_complete.json")
            assert marker['status'] == 'PASS' and marker['checkpoint'] == best
            expected_report = f.read_json(source / f"epoch_{best['epoch']:03d}_report.json")
            local_root = Path(best['absolute_local_path']).parents[2]
            provenance = f.read_json(local_root / 'audit' / Path(best['absolute_local_path']).parent.name / 'provenance.json')
            assert provenance['code_sha256'] == contract.code
            assert provenance['identity'] == contract.protocol['identity']
            assert provenance['origin_authorization_sha256'] == ORIGIN_SHA
            payload = verify_file(best, provenance)
            assert payload['validation'] == expected_report['validation']
            save(evidence / 'inference_scope.json', {
                'operation': 'V2_PHASE_A_BEST_FULL_2024_READ_ONLY_REVIEW', 'model': kind,
                'source_authority': f.identity(ORIGIN), 'BEST': best,
                'code_sha256': contract.code, 'manifest_identities': contract.protocol['identity'],
                'review_code': {p.name: f.digest(p) for p in [Path(__file__), Path(__file__).with_name('review_v2_helpers.py')]},
                'MODEL_PARAMETERS_UPDATED': False, 'OPTIMIZER_STEPS': 0, 'BACKWARD_CALLS': 0,
                '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'V2_PHASE_B_AUTHORIZED': False})
            before = {str(p): f.digest(p) for p in source.rglob('*') if p.is_file()}
            before[best['absolute_local_path']] = best['sha256']
            firewall = SourceFirewall(sources, evidence / 'raw_access_parent.jsonl',
                                     mask_path=contract.protocol['identity']['yunnan_mask']['path'])
            counters = SimpleNamespace(FORWARD_CALLS=0, TRAIN_FORWARDS=0, VALIDATION_FORWARDS=0)
            seen, worker_pids = [], set()
            exposure_count = 0
            with firewall.installed(), inference_only():
                model = f.FACTORIES[kind](numerics=f.CandidateNumerics(epsilon_w=1e-4, epsilon_span=1e-4), root=EXECUTION)
                model.load_state_dict(payload['model'], strict=True)
                state_before = f.state_digest(model.state_dict())
                assert state_before == payload['state_sha256']['model']
                del payload; gc.collect()
                model = model.cuda().eval()
                assert f.state_digest(model.state_dict()) == state_before
                stage = f.data.STAGE_ROOT / ('v2_review_' + out.name + '_' + kind)
                datasets, mask = f.datasets(contract, kind, stage, evidence, sources)
                accumulator = ReadOnlyMetrics()
                diagnostics = UpperTailDiagnostics(mask, 'VALIDATION', evidence / 'validation_diagnostics.jsonl')
                with f.loader_items(f.loader(datasets[2024], validation=True)) as batches:
                    for step, items in enumerate(batches, 1):
                        worker_pids.update(item['worker_pid'] for item in items)
                        exposure_count += sum(len(item['staging']) for item in items)
                        batch = f.data.make_batch(items)
                        output, loss = f.forward_loss(model, batch, counters, 'VALIDATION')
                        accumulator.add(output, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask)
                        diagnostics.observe(output.conditional_quantiles_log, batch.sample_ids)
                        seen.extend(batch.indices)
                        append_event(evidence / 'review_forwards.jsonl', 'READ_ONLY_VALIDATION_FORWARD_COMPLETE',
                                     step=step, scenes=len(seen), sample_ids=batch.sample_ids,
                                     MODEL_PARAMETERS_UPDATED=False, OPTIMIZER_STEPS=0, BACKWARD_CALLS=0)
                        if step % 50 == 0:
                            print(json.dumps({'operation': 'READ_ONLY_2024_REVIEW', 'model': kind,
                                              'scenes': len(seen), 'total_scenes': 10501}), flush=True)
                        del batch, output, loss, items
                assert seen == list(range(10501)) and counters.VALIDATION_FORWARDS == 1313
                metrics = accumulator.report()
                assert metrics['N_valid'] == 36018430 and metrics['scenes'] == 10501
                original = expected_report['validation']
                keys = ('S_occ', 'S_qr', 'N_valid', 'N_rain', 'scenes', 'forwards', 'global_val_core_loss',
                        'global_L_occ', 'global_core_L_qr', 'strict_crossing_count', 'support_violation_count', 'nonfinite_count')
                mismatches = {key: {'training': original[key], 'review': metrics[key]} for key in keys if original[key] != metrics[key]}
                assert not mismatches, mismatches
                assert f.state_digest(model.state_dict()) == state_before
                tail = diagnostics.report()
                del model, accumulator; gc.collect(); torch.cuda.empty_cache()
            io = reconcile_io(evidence)
            assert io['DENIED_ATTEMPTS'] == io['2025_RAW_ACCESS'] == io['2025_PIXELS_READ'] == 0
            assert io['RAW_SOURCE_OPENS'] == 2 * exposure_count
            assert all((evidence / f'raw_access_worker_{pid}.jsonl').exists() for pid in worker_pids)
            staging_left = [str(p) for p in stage.rglob('*') if p.is_file()] if stage.exists() else []
            assert not staging_left, staging_left
            assert all(f.digest(path) == expected for path, expected in before.items())
            result = {'status': 'FULL_2024_BEST_REVIEW_PASS', 'model': kind, 'BEST': best,
                      'metrics': metrics, 'upper_tail_diagnostics': tail, 'io': io,
                      'training_best_metric_reconciliation': {'tolerance': 0, 'mismatches': mismatches, 'keys': list(keys)},
                      'model_state_sha256_before': state_before, 'model_state_sha256_after': state_before,
                      'validation_sample_ids_sha256': f.state_digest([row['sample_id'] for row in contract.records[kind, 2024]]),
                      'MODEL_PARAMETERS_UPDATED': False, 'OPTIMIZER_STEPS': 0, 'BACKWARD_CALLS': 0,
                      'REVIEW_FORWARD_CALLS': counters.FORWARD_CALLS, 'staging_temporary_files_remaining': 0,
                      '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'V2_PHASE_B_AUTHORIZED': False}
            save(evidence / 'final_review.json', result); reports[kind] = result
        assert reports['B0_MATCHED_V2']['validation_sample_ids_sha256'] == reports['B1_V2']['validation_sample_ids_sha256']
        assert all(f.digest(path) == expected for path, expected in frozen_before.items())
        for ref in historical_refs:
            path = Path(ref['absolute_local_path'])
            assert path.stat().st_size == ref['bytes'] and f.digest(path) == ref['sha256']
        contract.unchanged()
        save(out / 'paired_best_metrics.json', {'status': 'PAIRED_FULL_2024_REVIEW_PASS',
             'comparison_sample_set': 'SAME_FROZEN_10501_VALIDATION_SCENES', 'models': reports,
             'checkpoint_selection_performed': False, 'MODEL_PARAMETERS_UPDATED': False,
             'OPTIMIZER_STEPS': 0, 'BACKWARD_CALLS': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
             'V2_PHASE_B_AUTHORIZED': False, 'RESEARCHER_PHASE_A_REVIEW_REQUIRED': True,
             'completed_utc': datetime.now(timezone.utc).isoformat()})
    except BaseException as exc:
        save(out / 'failure.json', {'status': 'FAILED_STOP', 'error': repr(exc), 'traceback': traceback.format_exc(),
             'MODEL_PARAMETERS_UPDATED': False, 'OPTIMIZER_STEPS': 0, 'BACKWARD_CALLS': 0,
             '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'V2_PHASE_B_AUTHORIZED': False})
        raise


if __name__ == '__main__':
    main()
