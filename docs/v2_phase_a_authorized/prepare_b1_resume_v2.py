"""Read-only LAST-bound B1 precheck and authority binding for existing Phase-A scope.

No formal forward/backward/optimizer step or state application is performed.
Original scientific inputs, epoch artifacts, checkpoints and approvals are immutable.
"""
from datetime import datetime, timezone
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

REPO = Path(__file__).resolve().parents[2]
EXECUTION = REPO.parent / 'YunTAPR-Net-v2-phase-a-execution'
PAIR = 'pair_20261007T070503_825794Z'
ORIGIN_SHA = 'e32404d0d397dd62e1763d3fb16b4a8d8c72fb79ba52bae3f40ac095f4492869'
LAST_SHA = '40f7f1204aba52815e1c8c2f3d2a5ce5d73da6b7b0297e1d79dc843cb3390649'
sys.path[:0] = [str(EXECUTION / 'src'), str(EXECUTION / 'scripts')]


def main():
    now = datetime.now(timezone.utc)
    out = REPO / 'docs/v2_phase_a_authorized' / PAIR / now.strftime('resume_%Y%m%dT%H%M%S_%fZ')
    out.mkdir()
    def save(name, value):
        with (out / name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2); stream.write('\n')
    print(json.dumps({'precheck_directory': str(out)}, ensure_ascii=False), flush=True)
    try:
        import torch
        torch.set_num_threads(2)
        from yuntapr.training import formal_phase_a_v2 as f
        from yuntapr.training.checkpoint_v2 import verify_file
        from paired_phase_a_v2.preflight import environment, disk_gate
        origin_path = REPO / 'docs/v2_phase_a_authorized' / PAIR / 'authorization.json'
        assert f.digest(origin_path) == ORIGIN_SHA
        origin = f.read_json(origin_path)
        contract = f.Contract.load(EXECUTION)
        assert contract.code == origin['code_sha256']
        assert f.git('rev-parse', 'HEAD', root=EXECUTION) == origin['execution_commit']
        assert not f.git('status', '--porcelain', '--untracked-files=normal', root=EXECUTION)
        assert f.digest(origin['preflight_path']) == origin['preflight_sha256']
        assert f.digest(origin['test_summary_path']) == origin['test_summary_sha256']
        gate = f.read_json(origin['preflight_path'])
        public = Path(origin['publication_root'])
        local = Path(origin['checkpoint_roots']['B1_V2']) / origin['run_ids']['B1_V2']
        assert f.read_json(public / 'B0_MATCHED_V2/final_report.json')['status'] == 'COMPLETE'
        last = f.read_json(public / 'B1_V2/last_checkpoint_identity.json')
        assert last['epoch'] == 14 and last['global_update'] == 73192 and last['sha256'] == LAST_SHA
        registry = f.read_json(public / 'B1_V2/checkpoint_registry.json')
        marker = f.read_json(public / 'B1_V2/epoch_014_complete.json')
        assert registry['LAST'] == marker['checkpoint'] == last and marker['status'] == 'PASS'
        assert len(registry['epochs']) == 14
        original_attempt = local / 'audit' / Path(last['absolute_local_path']).parent.name
        provenance = f.read_json(original_attempt / 'provenance.json')
        assert provenance['identity'] == contract.protocol['identity']
        assert provenance['code_sha256'] == contract.code and provenance['origin_authorization_sha256'] == ORIGIN_SHA
        for key in ('protocol_sha256', 'head_sha256', 'normalization_sha256', 'execution_commit', 'pair_id'):
            assert provenance[key] == origin[key]
        payload = verify_file(last, provenance)
        assert payload['completed_epoch'] == 14 and payload['selection']['non_improvement_count'] == 5
        reconciliation = f.reconcile_attempts(local, 14)
        assert reconciliation['all_attempt_updates_lower_bound'] == reconciliation['all_attempt_updates_upper_bound'] == 76287
        assert reconciliation['discarded_updates_lower_bound'] == reconciliation['discarded_updates_upper_bound'] == 3095
        preserved = {str(p): f.digest(p) for p in (origin_path, Path(last['absolute_local_path']),
                     original_attempt / 'failure.json', original_attempt / 'epoch_015/steps.jsonl')}
        for directory in (public, EXECUTION / 'config'):
            for p in directory.rglob('*'):
                if p.is_file(): preserved[str(p)] = f.digest(p)
        print('CHECKPOINT_STATE_AND_FROZEN_IDENTITY_PASS', flush=True)
        f.seed_reproducibility(); f.assert_environment()
        actual_environment = environment()
        assert actual_environment == gate['environment'], 'Runtime environment changed'
        probe = torch.ones((16, 16), device='cuda', dtype=torch.bfloat16)
        assert bool(torch.isfinite(probe).all())
        torch.cuda.synchronize(); del probe; torch.cuda.empty_cache()
        models, initialization = f.paired_initialization(contract)
        assert initialization == gate['paired_initialization'] == provenance['initialization']
        del models; gc.collect()
        storage = disk_gate(gate['checkpoint_bytes_budget'], gate['log_bytes_per_epoch_budget'])
        assert not Path('F:/pytorch/Research/outputs/formal_training/paired_v2_gpu.lock').exists()
        monitor_test_path = REPO / 'docs/v2_phase_a_authorized/monitor_immutable_tail_test_20261009_v1.json'
        monitor_test = f.read_json(monitor_test_path)
        assert monitor_test['status'] == 'PASS' and monitor_test['reader_writer_errors'] == []
        stop_path = REPO / 'docs/v2_phase_a_authorized/monitor_replacement_stop_20261009_v1.json'
        assert f.read_json(stop_path)['remaining_live'] == 0
        # No directory walking or source fallback; metadata yields the full allowlist.
        sources = contract.sources()
        assert len(sources) == gate['source_files_verified'] == 67006
        assert all(ref['year'] in (2023, 2024) and 3 <= ref['month'] <= 10 for ref in sources.values())
        assert Path('H:/葵花202303_202510').is_dir()
        size_checked = 0
        for index, (path, ref) in enumerate(sources.items(), 1):
            stat = Path(path).stat()
            if ref['expected_bytes'] is not None:
                assert stat.st_size == ref['expected_bytes'], path
                size_checked += 1
            if index % 10000 == 0:
                print(f'SOURCE_EXISTS_SIZE_CHECKED {index}/{len(sources)}', flush=True)
        order = f.epoch_permutation(14, count=10455).tolist()  # epoch 15 is zero-based permutation index 14
        first_ids = [contract.records['B1_V2', 2023][index]['sample_id'] for index in order[:2]]
        original_first = None
        with (original_attempt / 'epoch_015/steps.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                event = json.loads(line)
                if event['event'] == 'OPTIMIZER_STEP_COMPLETED':
                    original_first = event; break
        assert original_first['update'] == 73193 and original_first['sample_ids'] == first_ids
        assert original_first['LR'] == payload['scheduler']['next_lr'] == f.lr_for_update(73193, steps_per_epoch=5228)
        hash_checks = []
        seen = set()
        firewall = f.SourceFirewall(sources, out / 'raw_access_precheck.jsonl')
        with firewall.installed():
            for index in order[:2]:
                row = contract.records['B1_V2', 2023][index]
                selected = [(Path(row['imerg_day_path']), row['imerg_sha256'])]
                for slot in range(6):
                    frame = contract.frames[row[f'slot_{slot}_nominal']]
                    selected.append((f.data.H_ROOT / frame['relative_path'], frame['source_sha256']))
                for p, expected in selected:
                    if str(p) in seen: continue
                    actual = f.digest(p)
                    assert actual == expected, str(p)
                    hash_checks.append({'path': str(p), 'sha256': actual, 'bytes': p.stat().st_size})
                    seen.add(str(p))
        io = f.reconcile_io(out)
        assert io['DENIED_ATTEMPTS'] == 0 and io['2025_RAW_ACCESS'] == io['2025_PIXELS_READ'] == 0
        for path, expected in preserved.items(): assert f.digest(path) == expected, path
        contract.unchanged()
        report = {'status': 'PASS', 'scope': 'LAST_BOUND_RESUME_IDENTITY_AND_RUNTIME_PREFLIGHT',
                  'created_utc': now.isoformat(), 'completed_utc': datetime.now(timezone.utc).isoformat(),
                  'checkpoint': last, 'verified_state_sha256': payload['state_sha256'],
                  'scheduler': payload['scheduler'], 'selection': payload['selection'],
                  'completed_permutation_sha256': payload['completed_permutation_sha256'],
                  'next_permutation_sha256': payload['next_permutation_sha256'],
                  'next_epoch': 15, 'next_batch_sample_ids': first_ids,
                  'original_epoch15_first_sample_ids_and_lr_match': True,
                  'frozen_manifest_identities': contract.protocol['identity'],
                  'code_sha256': contract.code, 'initialization_regenerated_and_exactly_verified': True,
                  'environment': actual_environment, 'GPU_BF16_ALLOCATION_PASS': True, 'storage': storage,
                  'source_files_exist': len(sources), 'source_size_checks': size_checked,
                  'next_batch_source_sha_checks': hash_checks, 'all_source_sha_repeated': False,
                  'source_sha_policy': 'Completed 67006-source preflight retained; every actual guarded staging read revalidates source SHA.',
                  'monitor_test': f.identity(monitor_test_path), 'old_monitor_stop': f.identity(stop_path),
                  'monitor_policy': 'Independent observer reads only append-only journals and immutable epoch reports; never mutable formal JSON.',
                  'original_lock_holder_identified': False, 'historical_artifacts_unchanged': True,
                  'reconciliation': reconciliation, 'io': io, 'state_application_performed': False,
                  'formal_optimizer_steps_added': 0, 'engineering_optimizer_steps_added': 0,
                  '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'V2_PHASE_B_AUTHORIZED': False,
                  'resume_launched': False}
        save('resume_precheck.json', report)
        save('historical_preservation_before_resume.json', {'status': 'PASS', 'files': preserved})
        record = out / 'RESEARCHER_RESUME_AUTHORIZATION_RECORD.md'
        record.write_text('''# B1-v2 Phase-A：既有授权的 epoch 14 LAST 恢复绑定

授权来源是研究者原始 paired Phase-A 正式授权及当前持续目标：完成两个已批准 Phase-A，并在中断后仅从最后一个完整 LAST 恢复。本记录登记现有授权的执行绑定，不宣称研究者在本记录生成时间另行作出了新的科学决策。

B0-Matched-v2 已完成 epoch 17 早停，不重训。B1-v2 从 SHA256 40f7f1204aba52815e1c8c2f3d2a5ce5d73da6b7b0297e1d79dc843cb3390649 的完整 epoch 14 LAST 恢复。保留 73,192 次更新，丢弃失败 epoch 15 的 3,095 次未 checkpoint 更新，重跑 epoch 15。只允许既有冻结 Phase-A 到 early stopping 或 50 epoch。

科学、代码、数据、normalization、model/optimizer/scheduler/RNG/permutation 身份已通过当前只读预检；远端 main 包含本记录及绑定提交后才允许执行。冻结 runner 未修改。独立监控只读追加日志与不可变轮次报告，不打开可替换状态文件。原 WinError 5 的历史锁持有者未知，任何后续失败仍保留独立证据并停止。

不允许 Phase-B、FinalFit、2025、自动调参或静默修复。旧正式授权、失败记录、完整 epoch/checkpoint 与原更正证据保持不可变。
''', encoding='utf-8', newline='\n')
        auth = dict(origin)
        auth.update(created_utc=now.isoformat(), V2_PHASE_A_STARTED=True, resume_authorized=True,
                    resume_model='B1_V2', resume_LAST_sha256=LAST_SHA,
                    origin_authorization_path=str(origin_path), origin_authorization_sha256=ORIGIN_SHA,
                    researcher_approval_reference=str(record), researcher_approval_record_sha256=f.digest(record),
                    launch_mode='VERIFIED_EPOCH_14_B1_RESUME_EXISTING_PHASE_A_SCOPE',
                    resume_precheck_path=str(out / 'resume_precheck.json'),
                    resume_precheck_sha256=f.digest(out / 'resume_precheck.json'),
                    inherited_authority_basis='Original researcher formal authorization plus current user-provided persistent Phase-A objective, including completed-LAST-only recovery',
                    diagnostic_monitor_script=str(REPO / 'docs/v2_phase_a_authorized/monitor_immutable_tail_v1.py'),
                    diagnostic_monitor_sha256=f.digest(REPO / 'docs/v2_phase_a_authorized/monitor_immutable_tail_v1.py'))
        save('authorization.json', auth)
        f.authorize(out / 'authorization.json', f.digest(out / 'authorization.json'), contract, resume=True)
        save('preparation_status.json', {'status': 'PASS_AWAITING_REMOTE_PUBLICATION_AND_LAUNCH',
             'authorization_sha256': f.digest(out / 'authorization.json'), 'execution_commit': origin['execution_commit'],
             'formal_optimizer_steps_added': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0})
        print(json.dumps({'status': 'PASS', 'directory': str(out),
                          'authorization_sha256': f.digest(out / 'authorization.json'),
                          'retained_updates': 73192, 'discarded_updates': 3095,
                          'source_files_exist': len(sources)}, ensure_ascii=False), flush=True)
    except BaseException as exc:
        save('preparation_failure.json', {'status': 'FAILED_NO_LAUNCH', 'error': repr(exc),
             'traceback': traceback.format_exc(), 'formal_optimizer_steps_added': 0,
             '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0})
        raise


if __name__ == '__main__':
    main()
