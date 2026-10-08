"""Close out B1 failure-publication evidence without training or state application.

Only the previously unverified recovery draft is corrected. Its original bytes
are archived first. Frozen inputs, source data, completed epochs and checkpoints
are never written. The resulting proposal is deliberately not executable by the
pinned formal runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PAIR = 'pair_20261007T070503_825794Z'
LEGACY = 'resume_20261009T000000_000000Z'
ORIGIN_SHA = 'e32404d0d397dd62e1763d3fb16b4a8d8c72fb79ba52bae3f40ac095f4492869'
LEGACY_COMMIT = 'b68569fe2bf5ac0ba2ff8d86486f552c6d04e704'
SCRIPT_REL = 'docs/v2_phase_a_authorized/audit_b1_failure_publication_v1.py'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value, *, replace_draft=False):
    with Path(path).open('w' if replace_draft else 'x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n')


def identity(path):
    p = Path(path)
    return {'absolute_local_path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)}


def git(root, *args):
    return subprocess.check_output(['git', '-c', 'core.longpaths=true', *args], cwd=root).decode('utf-8').strip()


def no_raw_access(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    name = os.fsdecode(args[0]).replace('/', '\\').casefold()
    if name.startswith('h:\\') or '\\云南极端降水数据\\raw\\' in name:
        raise PermissionError('PUBLICATION_AUDIT_FORBIDS_ALL_RAW_SOURCE_OPENS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True, type=Path)
    parser.add_argument('--execution', required=True, type=Path)
    args = parser.parse_args()
    repo, execution = args.repository.resolve(), args.execution.resolve()
    sys.addaudithook(no_raw_access)
    approval_root = repo / 'docs/v2_phase_a_authorized' / PAIR
    public = repo / 'docs/formal_training_v2' / PAIR
    legacy = approval_root / LEGACY
    origin_path = approval_root / 'authorization.json'
    assert sha(origin_path) == ORIGIN_SHA
    origin = read(origin_path)
    assert git(repo, 'remote', 'get-url', 'origin') == 'https://github.com/flyeagle-cex/YunTAPR-Net.git'
    assert git(repo, 'branch', '--show-current') == 'main'
    assert git(execution, 'rev-parse', 'HEAD') == origin['execution_commit']
    assert not git(execution, 'status', '--porcelain', '--untracked-files=normal')

    preserved = {}
    # Snapshot the existing scientific/run evidence, not the three local drafts
    # that this script explicitly corrects after making byte-identical archives.
    for root in (public, execution / 'config'):
        for p in root.rglob('*'):
            if p.is_file():
                preserved[str(p)] = sha(p)
    preserved[str(origin_path)] = sha(origin_path)
    code_checks = []
    for rel, expected in origin['code_sha256'].items():
        actual = sha(execution / rel)
        assert actual == expected, rel
        preserved[str(execution / rel)] = actual
        code_checks.append({'path': rel, 'sha256': actual, 'status': 'PASS'})

    frozen_checks = []
    bindings = [('config/science_v2/phase_a_protocol_frozen_v1.json', origin['protocol_sha256']),
                ('config/science_v2/quantile_head_v2_frozen_v1.json', origin['head_sha256']),
                (origin['preflight_path'], origin['preflight_sha256']),
                (origin['test_summary_path'], origin['test_summary_sha256'])]
    normalization = 'docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z/normalization_b1_2023_shared_v1.json'
    bindings.append((normalization, origin['normalization_sha256']))
    for rel, expected in bindings:
        p = Path(rel)
        if not p.is_absolute():
            p = repo / p
        actual = sha(p)
        assert actual == expected, str(p)
        preserved[str(p)] = actual
        frozen_checks.append({**identity(p), 'status': 'PASS'})

    checkpoint_checks = []
    for kind, count in [('B0_MATCHED_V2', 17), ('B1_V2', 14)]:
        registry = read(public / kind / 'checkpoint_registry.json')
        assert len(registry['epochs']) == count
        assert registry['LAST'] == read(public / kind / 'last_checkpoint_identity.json')
        assert registry['BEST'] == read(public / kind / 'best_checkpoint_identity.json')
        for ep, ref in enumerate(registry['epochs'], 1):
            assert ref['epoch'] == ep and ref['model'] == kind
            marker = read(public / kind / f'epoch_{ep:03d}_complete.json')
            assert marker['status'] == 'PASS' and marker['checkpoint'] == ref
            actual = identity(ref['absolute_local_path'])
            assert all(actual[k] == ref[k] for k in ('bytes', 'sha256', 'absolute_local_path'))
            preserved[ref['absolute_local_path']] = ref['sha256']
            checkpoint_checks.append({**ref, 'file_verification': 'PASS'})

    last = read(public / 'B1_V2/last_checkpoint_identity.json')
    attempt = Path(last['absolute_local_path']).parents[2] / 'audit' / Path(last['absolute_local_path']).parent.name
    failure_path = attempt / 'failure.json'
    failure = read(failure_path)
    provenance = read(attempt / 'provenance.json')
    counters = read(attempt / 'attempt_counters.json')
    assert failure['status'] == 'FAILED_STOP' and failure['epoch'] == 15
    assert failure['counters_this_attempt'] == counters
    assert failure['retained_completed_epoch'] == last['epoch'] == 14
    assert last['global_update'] == 73192
    assert counters['OPTIMIZER_STEPS'] == 76287
    assert counters['OPTIMIZER_STEPS'] - last['global_update'] == 3095
    assert failure['2025_RAW_ACCESS'] == failure['2025_PIXELS_READ'] == 0
    for key in ('pair_id', 'execution_commit', 'protocol_sha256', 'head_sha256', 'normalization_sha256', 'code_sha256'):
        assert provenance[key] == origin[key], key
    assert provenance['origin_authorization_sha256'] == ORIGIN_SHA
    for p in (failure_path, attempt / 'provenance.json', attempt / 'attempt_counters.json', attempt / 'epoch_015/steps.jsonl'):
        preserved[str(p)] = sha(p)

    # Deserialization is CPU-only after the external file identity and frozen
    # provenance checks. No model/optimizer constructor or state application.
    print('FILE_AND_FROZEN_IDENTITY_CHECKS_PASS; verifying saved state on CPU', flush=True)
    sys.path[:0] = [str(execution / 'src'), str(execution / 'scripts')]
    import torch
    torch.set_num_threads(2)
    from yuntapr.training.checkpoint_v2 import verify_file
    from yuntapr.training.formal_phase_a_v2 import Contract, authorize, reconcile_attempts
    contract = Contract.load(execution)
    assert contract.code == origin['code_sha256']
    assert contract.protocol['identity'] == provenance['identity']
    assert provenance['initialization'] == read(origin['preflight_path'])['paired_initialization']
    payload = verify_file(last, provenance)
    assert payload['completed_epoch'] == 14 and payload['global_update'] == 73192
    assert payload['selection']['non_improvement_count'] == 5
    assert payload['selection']['selected_checkpoint_epoch'] == 9
    reconciliation = reconcile_attempts(attempt.parents[1], 14)
    assert reconciliation['discarded_updates_lower_bound'] == reconciliation['discarded_updates_upper_bound'] == 3095
    history = read(public / 'B1_V2/training_validation_history.json')
    assert len(history) == 14 and [row['epoch'] for row in history] == list(range(1, 15))

    now = datetime.now(timezone.utc)
    out = approval_root / now.strftime('publication_correction_%Y%m%dT%H%M%S_%fZ')
    out.mkdir()
    archive = out / 'superseded_draft_original_bytes'
    archive.mkdir()
    archived = []
    for name in ('authorization.json', 'resume_precheck.json', 'RESEARCHER_RESUME_AUTHORIZATION_RECORD.md'):
        p = legacy / name
        original = p.read_bytes()
        with (archive / name).open('xb') as stream:
            stream.write(original)
        assert sha(p) == sha(archive / name)
        archived.append({'original_path': str(p.relative_to(repo)),
                         'archived_path': str((archive / name).relative_to(repo)),
                         'sha256': sha(p), 'bytes': len(original)})

    state = {'schema': 'READ_ONLY_B1_CHECKPOINT_STATE_VERIFICATION_v1', 'status': 'PASS',
             'verified_utc': now.isoformat(), 'checkpoint': last,
             'verified_state_sha256': payload['state_sha256'], 'scheduler': payload['scheduler'],
             'selection': payload['selection'],
             'completed_permutation_sha256': payload['completed_permutation_sha256'],
             'next_permutation_sha256': payload['next_permutation_sha256'],
             'normalization_sha256': origin['normalization_sha256'],
             'manifest_identities': contract.protocol['identity'],
             'code_sha256_verified': True, 'paired_initialization_provenance_verified': True,
             'initialization_regenerated_this_task': False,
             'state_application_performed': False, 'training_started_by_this_task': False,
             'raw_sources_reopened': False, 'all_source_sha_repeated': False,
             '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0}
    save(out / 'checkpoint_state_verification.json', state)
    save(out / 'counter_reconciliation.json', {'status': 'PASS', **reconciliation,
        'failing_epoch': 15, 'failing_step': 3095,
        'failure_snapshot_completed_updates': 76286,
        'authoritative_attempt_completed_updates': 76287,
        'progress_snapshot_lags_successful_optimizer_step_by': 1,
        'explanation': 'The optimizer step completed before progress.json replacement failed. Retain only completed epoch 14; all 3095 epoch-15 updates must be discarded on any future approved resume.',
        'formal_optimizer_steps_added_by_this_task': 0})
    save(out / 'code_and_frozen_sha_verification.json', {'status': 'PASS',
        'execution_commit': origin['execution_commit'], 'code_files': code_checks,
        'frozen_files': frozen_checks, 'completed_checkpoint_files': checkpoint_checks})
    with (out / 'failure_original.json').open('xb') as stream:
        stream.write(failure_path.read_bytes())
    assert sha(out / 'failure_original.json') == sha(failure_path)

    corrected_precheck = {'schema': 'B1_V2_RECOVERY_PROPOSAL_PRECHECK_CORRECTION_v1',
        'status': 'PARTIAL_VERIFICATION_NOT_LAUNCH_READY', 'corrected_utc': now.isoformat(),
        'checkpoint_file_and_saved_state_verification': 'PASS',
        'verification_report': str((out / 'checkpoint_state_verification.json').relative_to(repo)),
        'retained_completed_epoch': 14, 'retained_updates': 73192,
        'discard_on_future_resume_updates': 3095,
        'remaining_gates': ['MONITOR_ATOMIC_REPLACE_CAUSE_AND_MITIGATION_VERIFIED',
                            'RAW_SOURCE_AND_GPU_AND_STORAGE_RESUME_PREFLIGHT',
                            'COMPLETE_LAST_BOUND_EXECUTION_AUTHORITY_AND_REMOTE_VERIFICATION'],
        'resume_launched': False, 'state_application_performed': False,
        'formal_optimizer_steps_added': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
        'V2_PHASE_B_AUTHORIZED': False,
        'superseded_original_bytes': str((archive / 'resume_precheck.json').relative_to(repo))}
    save(legacy / 'resume_precheck.json', corrected_precheck, replace_draft=True)
    corrected_authority = {'schema': 'NON_EXECUTABLE_B1_RECOVERY_PROPOSAL_v1',
        'scope': 'FAILURE_EVIDENCE_PUBLICATION_ONLY', 'corrected_utc': now.isoformat(),
        'pair_id': PAIR, 'model': 'B1_V2', 'checkpoint': last,
        'resume_authorized': False, 'execution_launch_allowed_by_this_record': False,
        'publication_requested_by_researcher': True,
        'researcher_request': '你看着进行一些修改后推送',
        'scope_note': 'This publication request is not treated as a new LAST-bound training-launch approval. Original formal Phase-A authority is preserved in origin_authorization_path.',
        'origin_authorization_path': str(origin_path), 'origin_authorization_sha256': ORIGIN_SHA,
        'protocol_sha256': origin['protocol_sha256'], 'head_sha256': origin['head_sha256'],
        'normalization_sha256': origin['normalization_sha256'],
        'V2_PHASE_B_AUTHORIZED': False, 'formal_optimizer_steps_added': 0,
        '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
        'superseded_original_bytes': str((archive / 'authorization.json').relative_to(repo)),
        'precheck': str((legacy / 'resume_precheck.json').relative_to(repo))}
    save(legacy / 'authorization.json', corrected_authority, replace_draft=True)
    record = '''# B1-v2 失败证据与恢复候选：更正记录

本文件取代此前本地草稿中未经完整核验的“研究者已授权恢复”表述。原始字节已复制归档并由 SHA256 登记，原始正式启动授权、失败原件、完整 epoch 报告和 checkpoint 保留。

当前研究者指令为“你看着进行一些修改后推送”，本次据此整理并发布失败与核验材料。当前 authorization.json 是不可执行的证据发布记录，不能用于启动正式训练。

Epoch 14 LAST 的文件 SHA、保存的 model/optimizer/scheduler/RNG 身份及下一 epoch permutation 已只读核验。Epoch 15 实际完成 3095 次未 checkpoint 更新；任何未来获准恢复必须全部丢弃，重新从 Epoch 14 完整边界开始。监控快照滞后一次 optimizer step，不使用快照计数替代正式 attempt counter。

文件锁持有者及 progress.json 原子替换失败根因尚未确认；恢复数据/GPU/存储预检与远端绑定仍需完成。本次没有训练、state application、forward、backward 或 optimizer update。2025 继续封存，Phase-B 未授权。
'''
    (legacy / 'RESEARCHER_RESUME_AUTHORIZATION_RECORD.md').write_text(record, encoding='utf-8', newline='\n')
    # Exercise the pinned authorization guard against the corrected, deliberately
    # non-executable record. It must reject before constructing any model.
    try:
        authorize(legacy / 'authorization.json', sha(legacy / 'authorization.json'), contract, resume=True)
    except PermissionError as exc:
        rejection = str(exc)
    else:
        raise AssertionError('Evidence-only proposal unexpectedly permitted training')

    preserved_changes = [p for p, expected in preserved.items() if sha(p) != expected]
    assert not preserved_changes, preserved_changes
    save(out / 'preservation_audit.json', {'status': 'PASS', 'scope': 'All pre-existing public pair files, execution configs, origin authorization, 74 pinned code files, 31 registered v2 checkpoints and the failure/step sources used by this audit.',
        'preserved_files': [{'absolute_local_path': p, 'sha256': h} for p, h in sorted(preserved.items())],
        'changes': [], 'source_data_opened': False, 'scientific_changes': False})
    save(out / 'draft_supersession.json', {'status': 'CORRECTED_WITH_ORIGINAL_BYTES_PRESERVED',
        'superseded_commit': LEGACY_COMMIT, 'original_drafts': archived,
        'invalidated_claims': ['Unverified full resume_precheck PASS',
                               'Specific B1 recovery approval assumed from the old launch authority',
                               'Unobserved placeholder UTC folder timestamp treated as observation time'],
        'effective_resume_precheck': 'PARTIAL_VERIFICATION_NOT_LAUNCH_READY',
        'runner_rejects_current_proposal': True, 'runner_guard_message': rejection})
    summary = '''# B1-v2 失败证据发布与恢复核验更正

B1-v2 在 Epoch 15 / Step 3095 写入监控 progress.json 时发生 WinError 5，runner 随后停止。模型数值失败未被该异常记录证明；锁持有者或杀毒/同步干扰等具体根因尚未确定。

只读核验结果：

- 74 个绑定代码文件、冻结 protocol/head/normalization、预检与测试总清单 SHA 一致。
- 两模型共 31 个已登记完整 epoch checkpoint 的文件大小/SHA 一致。
- B1 Epoch 14 LAST 保存的 model、optimizer、scheduler、RNG 与 epoch permutation 身份核验通过；没有应用状态。
- B1 retained trajectory = 73,192 updates；attempt completed = 76,287；未来恢复必须丢弃 3,095 个未 checkpoint updates。原监控快照仅为 76,286，滞后一次更新。
- B0-Matched-v2 已在 Epoch 17 早停；B1 尚未完成，不能输出完整配对实验已完成。

此前本地恢复草稿的 PASS 和特定恢复批准表述已更正，原始字节完整归档。当前恢复文件为不可执行的发布证据，已测试 pinned runner 会在模型构造前拒绝该文件。此前实际失败原件、已完成 epoch 产物、正式启动授权和冻结科学规则未修改。

2025_RAW_ACCESS=0 / 2025_PIXELS_READ=0 指本次审计，受进程审计 hook 强制禁止全部 raw-source open；历史训练的零访问声明引用原 failure 与完整 epoch markers。本次没有重扫全部历史 raw-access logs，不声称新增了该范围的独立验证。

后续恢复所需：查明并验证监控写入问题的处理方式，执行数据/GPU/存储恢复预检，并形成完整 LAST-bound 执行记录与远端核验。本次只发布证据，没有恢复训练或进入 Phase-B。
'''
    (out / 'FAILURE_PUBLICATION_REVIEW.md').write_text(summary, encoding='utf-8', newline='\n')
    checks = {'CHECKPOINT_FILE_SHA_PASS': True, 'SAVED_STATE_IDENTITY_PASS': True,
              'FROZEN_CODE_CONFIG_SHA_PASS': True, 'HISTORICAL_PAIR_ARTIFACTS_UNCHANGED': True,
              'CORRECTED_PROPOSAL_REJECTED_BY_PINNED_RUNNER': True,
              'ORIGINAL_DRAFT_BYTES_ARCHIVED': True, 'COUNTER_RECONCILIATION_PASS': True}
    status = {'status': 'EVIDENCE_CORRECTION_VERIFIED_PUBLICATION_PENDING', **checks,
              'FULL_RECOVERY_PREFLIGHT_PASS': False, 'RESUME_LAUNCHED': False,
              'FORMAL_OPTIMIZER_STEPS_ADDED': 0, 'FORWARD_CALLS_ADDED': 0,
              'BACKWARD_CALLS_ADDED': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
              'V2_PHASE_B_AUTHORIZED': False, 'PAIRED_PHASE_A_COMPLETE': False,
              'RESEARCHER_DECISION_REQUIRED': True}
    save(out / 'publication_review_status.json', status)
    additions = sorted(p for p in out.rglob('*') if p.is_file())
    updated_drafts = [legacy / n for n in ('authorization.json', 'resume_precheck.json', 'RESEARCHER_RESUME_AUTHORIZATION_RECORD.md')]
    manifest = {'schema': 'B1_FAILURE_CORRECTION_PUBLICATION_MANIFEST_v1', 'created_utc': now.isoformat(),
        'repository': 'https://github.com/flyeagle-cex/YunTAPR-Net.git', 'branch': 'main',
        'base_commit': git(repo, 'rev-parse', 'HEAD'), 'scientific_commit': origin['scientific_commit'],
        'implementation_commit': origin['execution_commit'], 'final_preflight_commit': origin['finalized_preflight_commit'],
        'files': [{'path': str(p.relative_to(repo).as_posix()), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                  for p in [repo / SCRIPT_REL, *additions, *updated_drafts]],
        'excluded': ['checkpoint/model/optimizer binaries', 'raw data', 'mask payloads', 'unrelated untracked files'],
        'publication_contains_absolute_local_paths': True,
        'publication_contains_failure_and_superseded_recovery_records': True,
        'training_launched': False}
    assert not any(Path(row['path']).suffix.lower() in ('.pt', '.pth', '.ckpt', '.nc', '.npz') for row in manifest['files'])
    save(out / 'publication_manifest.json', manifest)
    print(json.dumps({'status': status['status'], 'directory': str(out),
                      'verified_checkpoint_files': len(checkpoint_checks),
                      'verified_code_files': len(code_checks), 'checks': checks,
                      'manifest': str(out / 'publication_manifest.json')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
