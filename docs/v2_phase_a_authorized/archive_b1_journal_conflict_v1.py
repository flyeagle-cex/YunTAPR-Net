"""Archive the terminal B1 journal sharing failure; no state application or raw reads.

Use Python shared-write reads, including for append journals. Never use default
.NET ReadLines/Get-Content against a live training journal.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
EXECUTION = REPO.parent / 'YunTAPR-Net-v2-phase-a-execution'
PAIR = 'pair_20261007T070503_825794Z'
AUTH_ROOT = REPO / 'docs/v2_phase_a_authorized' / PAIR
PRIOR = AUTH_ROOT / 'resume_20261009T000335_263611Z'
LOCAL = Path('F:/pytorch/Research/outputs/formal_training/b1_v2_phase_a/run_20261007T070503_825795Z')
OLD = LOCAL / 'audit/run_20261008T010824_279406Z'
FAILED = LOCAL / 'audit/run_20261009T001234_525667Z'
sys.path.insert(0, str(EXECUTION / 'src'))


def read(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return json.load(stream)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def completed(path):
    events = []
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            event = json.loads(line)
            if event['event'] == 'OPTIMIZER_STEP_COMPLETED':
                events.append(event)
    return events


def main():
    now = datetime.now(timezone.utc)
    out = AUTH_ROOT / now.strftime('journal_failure_closeout_%Y%m%dT%H%M%S_%fZ')
    out.mkdir()

    def save(name, value):
        with (out / name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write('\n')

    assert read(PRIOR / 'process_exit.json')['exit_code'] == 1
    failure = read(FAILED / 'failure.json')
    counter = read(FAILED / 'attempt_counters.json')
    assert counter == failure['counters_this_attempt']
    assert failure['status'] == 'FAILED_STOP' and failure['epoch'] == 15 and failure['step'] == 383
    assert counter['OPTIMIZER_STEPS'] == 382 and counter['OPTIMIZER_STEP_ATTEMPTS'] == 383
    assert counter['CHECKPOINT_WRITES'] == 0 and counter['BACKWARD_CALLS'] == 383
    assert counter['TRAIN_FORWARDS'] == 383 and counter['VALIDATION_FORWARDS'] == 0
    assert failure['2025_RAW_ACCESS'] == failure['2025_PIXELS_READ'] == 0
    sources = {}
    copies = [FAILED / name for name in ('failure.json', 'attempt_counters.json', 'resume_identity.json', 'provenance.json')]
    copies += [PRIOR / name for name in ('process_exit.json', 'remote_resume_verification.json', 'resume_process.json',
                'wrapper_process.json', 'applied_resume_identity_verification.json', 'applied_resume_identity_snapshot.json', 'monitor_attempt2_process.json')]
    for source in copies:
        name = ('runner_' if source.parent == FAILED else 'launch_') + source.name
        (out / name).write_bytes(source.read_bytes())
        assert digest(out / name) == digest(source)
        sources[name] = {'original_path': str(source), 'sha256': digest(source), 'bytes': source.stat().st_size}

    a, b = OLD / 'epoch_015/steps.jsonl', FAILED / 'epoch_015/steps.jsonl'
    original, replayed = completed(a), completed(b)
    assert len(original) == 3095 and len(replayed) == 382
    keys = ('update', 'sample_ids', 'indices', 'LR', 'loss', 'L_occ', 'L_qr',
            'pre_clip_norm', 'post_clip_norm', 'actual_denominator', 'clipped')
    mismatch = [{'update': right['update'], 'field': key, 'original': left.get(key), 'replayed': right.get(key)}
                for left, right in zip(original, replayed) for key in keys if left[key] != right[key]]
    assert not mismatch
    save('epoch15_prefix_reconciliation.json', {'status': 'PASS', 'completed_updates_compared': 382,
         'zero_tolerance': True, 'fields': keys, 'mismatches': mismatch,
         'original_journal': {'path': str(a), 'sha256': digest(a)},
         'replayed_journal': {'path': str(b), 'sha256': digest(b)},
         'claim_limit': 'Completed prefix only; no claim for the failed optimizer step or unexecuted suffix.'})

    from yuntapr.training import formal_phase_a_v2 as f
    reconciliation = f.reconcile_attempts(LOCAL, 14)
    assert reconciliation['retained_trajectory_updates'] == 73192
    assert reconciliation['all_attempt_updates_lower_bound'] == reconciliation['all_attempt_updates_upper_bound'] == 76669
    assert reconciliation['discarded_updates_lower_bound'] == reconciliation['discarded_updates_upper_bound'] == 3477
    io = f.reconcile_io(FAILED)
    assert io['DENIED_ATTEMPTS'] == io['2025_RAW_ACCESS'] == io['2025_PIXELS_READ'] == 0
    origin = read(AUTH_ROOT / 'authorization.json')
    assert f.git('rev-parse', 'HEAD', root=EXECUTION) == origin['execution_commit']
    assert not f.git('status', '--porcelain', '--untracked-files=normal', root=EXECUTION)
    for relative, expected in origin['code_sha256'].items():
        assert digest(EXECUTION / relative) == expected, relative
    baseline = read(PRIOR / 'historical_preservation_before_resume.json')['files']
    checked = {}
    for path, expected in baseline.items():
        p = Path(path)
        historical = p.suffix == '.pt' or p.is_relative_to(EXECUTION / 'config') or p in (AUTH_ROOT / 'authorization.json', OLD / 'failure.json', a)
        historical |= p.name.endswith(('_report.json', '_complete.json')) or p.name in {
            'checkpoint_registry.json', 'last_checkpoint_identity.json', 'best_checkpoint_identity.json', 'training_validation_history.json'}
        if historical:
            assert digest(p) == expected, str(p)
            checked[path] = expected
    public = Path(origin['publication_root'])
    checkpoints = {}
    for kind in ('B0_MATCHED_V2', 'B1_V2'):
        registry = read(public / kind / 'checkpoint_registry.json')
        for identity in registry['epochs']:
            p = Path(identity['absolute_local_path'])
            assert p.stat().st_size == identity['bytes'] and digest(p) == identity['sha256']
            checkpoints[str(p)] = identity['sha256']
    assert len(checkpoints) == 31
    last = read(public / 'B1_V2/last_checkpoint_identity.json')
    assert last['epoch'] == 14 and last['global_update'] == 73192
    assert last['sha256'] == '40f7f1204aba52815e1c8c2f3d2a5ce5d73da6b7b0297e1d79dc843cb3390649'
    save('historical_identity_audit.json', {'status': 'PASS', 'execution_commit': origin['execution_commit'],
         'code_and_frozen_config_files_verified': len(origin['code_sha256']),
         'immutable_historical_files_verified': checked, 'checkpoint_files_verified': checkpoints,
         'B1_LAST': last, 'protocol_sha256': origin['protocol_sha256'], 'head_sha256': origin['head_sha256'],
         'normalization_sha256': origin['normalization_sha256'], 'historical_trajectory_changed': False})
    save('failure_reconciliation.json', {'status': 'PASS', **reconciliation, 'failure_counters': counter,
         'io': io, 'formal_optimizer_steps_added_by_this_audit': 0,
         'next_resume_epoch': 15, 'only_permitted_start': 'Verified completed epoch 14 LAST',
         '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'V2_PHASE_B_AUTHORIZED': False})
    test_path = REPO / 'docs/v2_phase_a_authorized/journal_reader_sharing_test_20261009_v1.json'
    test = read(test_path)
    assert test['status'] == 'PASS' and test['fixtures_cleaned']
    save('reader_failure_analysis.json', {'status': 'ENGINEERING_IO_FAILURE',
         'observed_error': failure['error'], 'failed_operation': 'Append OPTIMIZER_STEP_ATTEMPT before optimizer.step',
         'auditor_action': 'Default .NET File.ReadLines used by Codex for live prefix reconciliation at failure time',
         'causal_assessment': 'The auditor reader denies write sharing; isolated fixture reproduces the same PermissionError. The contemporaneous handle was not captured, so exact OS handle ownership is not independently logged.',
         'scientific_numerical_failure_observed': False,
         'responsibility': 'Codex external audit reader; not a frozen protocol or model change',
         'corrective_policy': test['approved_audit_reader_policy'],
         'mutable_atomic_json_policy': test['mutable_atomic_json_policy'],
         'reproduction_test': {'path': str(test_path), 'sha256': digest(test_path)},
         'no_training_code_change': True, 'no_automatic_retry': True})
    (out / 'FAILURE_CLOSEOUT.md').write_text('''# B1-v2 日志读取冲突：失败归档与恢复前提

B1 在 epoch 15 的 batch 383 因追加 steps.jsonl 被拒绝而停止。前 382 次 optimizer update 完成，第 383 次在记录尝试事件时失败，尚未调用 optimizer.step；没有新 checkpoint。正式保留轨迹仍为 epoch 14 的 73,192 次更新。累计实际成功更新为 76,669 次，其中 3,477 次没有进入完整 checkpoint，后续恢复必须丢弃。

本次外部审计曾使用默认 .NET File.ReadLines 读取运行中的日志。其 Windows 文件共享方式不允许其他进程写入；隔离 fixture 复现了相同 PermissionError。读取与本次失败同时发生，证据支持它是冲突来源，但没有独立捕获当时的 OS handle。该读取由 Codex 执行，应由 Codex 承担工程排查责任。

修正只涉及外部观察与审计：运行中追加日志只允许已测试的 Python reader，或显式 FileShare.ReadWrite | FileShare.Delete；不打开训练进程会原子替换的 JSON。显式共享读取下 1,000 次追加均通过。冻结训练代码、模型、loss、LR、normalization 和数据集合未改。

本次重跑的前 382 次更新，其样本、LR、loss、梯度范数、分母及 clipping 与原 epoch 15 日志逐项零容差一致。此结论仅覆盖已完成前缀。model/optimizer/scheduler/RNG 的已应用恢复身份见原始 resume_identity 快照与核验记录。31 个历史 checkpoint 的大小和 SHA256、冻结代码与不可变轮次证据已复核。

当前失败已关闭并独立保留。恢复必须另建运行记录，重新核验 epoch 14 LAST、冻结身份、当前环境和来源；先推送远端 main 绑定后，才可调用未修改的正式 runner。2025_RAW_ACCESS=0，2025_PIXELS_READ=0，V2_PHASE_B_AUTHORIZED=false。配对 Phase-A 尚未完成。
''', encoding='utf-8', newline='\n')
    save('evidence_manifest.json', {'status': 'CLOSED_FAILURE_PRESERVED', 'created_utc': now.isoformat(),
         'completed_utc': datetime.now(timezone.utc).isoformat(), 'source_copies': sources,
         'artifacts': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()},
         'formal_optimizer_steps_added_by_this_audit': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
         'V2_PHASE_B_AUTHORIZED': False, 'PAIR_PHASE_A_COMPLETE': False})
    print(json.dumps({'status': 'PASS', 'output': str(out), 'retained': 73192, 'discarded': 3477,
                     'all_attempt': 76669, 'exact_replay_prefix': 382}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
