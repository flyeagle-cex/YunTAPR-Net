"""Build an explicit public-source/receipt allowlist, never execute science."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import importlib.util
import io
import json
import re
import shutil
import sqlite3
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
PUB = BASE / 'YunTAPR-Net-publication-20261024'
AUDIT = BASE / 'YunTAPR-Net-completed-review-20261021'
ACTIVE = BASE / 'YunTAPR-Net-seed2027-b1-e1-recovery-v2-20261022'
SAFE = BASE / 'YunTAPR-Net-safe-resume-20261023'
DEST = PUB / 'docs/phase_b_v2_seed2027_completion/20261024'
BRANCH = 'audit/completed-review-seed2027-20261024'
REMOTE_BASE = '50254354f59c50ee9afd409d6820789371f76441'
COPIED = {}
TRACKED = {}


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def sha(raw): return hashlib.sha256(raw).hexdigest()
def digest(value): return sha(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def copy(root, source, dest):
    relative = source.relative_to(root).as_posix()
    if any(part in ('.git','.local','__pycache__') for part in source.relative_to(root).parts):
        raise ValueError('Explicit public receipts must use the receipt-specific copier')
    return copy_bytes(root, source, dest, relative)


def copy_bytes(root, source, dest, relative):
    if not dest.is_relative_to(PUB) or '..' in dest.parts: raise ValueError('PUBLICATION_ROOT_ONLY')
    raw=source.read_bytes()
    if dest.exists() and dest.read_bytes()!=raw: raise ValueError('REFUSE_EXISTING_PUBLICATION_FILE_OVERWRITE:'+str(dest))
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(raw)
    if root not in TRACKED: TRACKED[root]=set(git(root,'ls-files').splitlines())
    COPIED[dest.relative_to(PUB).as_posix()]={
        'source_workspace':root.name,'source_path':relative,'source_head':git(root,'rev-parse','HEAD'),
        'tracked_in_source_index':relative in TRACKED[root],
        'bytes':len(raw),'sha256':sha(raw),'git_blob_sha1':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
    return raw


def main():
    if PUB.resolve()!=BASE/'YunTAPR-Net-publication-20261024' or not (PUB/'.git').is_dir():raise ValueError('ISOLATED_STANDALONE_PUBLICATION_REQUIRED')
    if git(PUB,'branch','--show-current')!=BRANCH:raise ValueError('PUBLICATION_BRANCH_ONLY')
    if (DEST/'PUBLICATION_MANIFEST.json').exists():raise ValueError('ONE_BUILD_ONLY')
    subprocess.check_call(['git','merge-base','--is-ancestor',REMOTE_BASE,'HEAD'],cwd=PUB)
    manifest=json.loads((AUDIT/'docs/audits/20261021_completed_work_review/DELIVERY_MANIFEST.json').read_text())
    for path,pin in manifest['files'].items():
        if sha((PUB/path).read_bytes())!=pin['sha256']:raise ValueError('INHERITED_AUDIT_PIN:'+path)

    sys.path.insert(0,str(SAFE))
    import bootstrap as b
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2 import ancestor
    state=b.control.status()
    if state.get('effective_state')!='COMPLETE':raise ValueError('CAMPAIGN_NOT_COMPLETE')
    if (state['reserved'],state['new_reserved'],state['new_returned_verified'],state['hard_cap'])!=(375425,109788,109788,375425):raise ValueError('FINAL_ACCOUNTING')
    if state['native_probes']['job']['status']!='ABSENT':raise ValueError('WORKER_JOB_STILL_PRESENT')
    DEST.mkdir(parents=True,exist_ok=False)

    components=[('b0_e1',AUDIT,'tools/seed2027_b0_e1_recovery','docs/formal_recovery/seed2027_b0_e1_epoch1_v1'),
      ('b1_e1_v1',BASE/'YunTAPR-Net-seed2027-b1-e1-recovery-20261022','tools/seed2027_b1_e1_epoch6_recovery','docs/formal_recovery/seed2027_b1_e1_epoch6_v1'),
      ('b1_e1_v2',ACTIVE,'tools/seed2027_b1_e1_epoch6_recovery_v2','docs/formal_recovery/seed2027_b1_e1_epoch6_v2')]
    for alias,root,tool,docs in components:
        tracked=git(root,'ls-files').splitlines()
        allowed=[p for p in tracked if (p.startswith('recovery_overlay/') or p.startswith(tool+'/')) and p.endswith('.py')]
        allowed += [p for p in tracked if p.startswith(docs+'/') and Path(p).parent.as_posix()==docs and Path(p).suffix in ('.json','.patch')]
        if alias=='b0_e1':
            allowed += [docs+'/'+n for n in ('RESUME_ASSESSMENT_20261022.json','execution_status.json','watchdog_failure.json') if (root/docs/n).exists()]
        for relative in sorted(set(allowed)):
            copy(root,root/relative,PUB/'research_snapshots/seed2027_recoveries'/alias/relative)
    for relative in git(SAFE,'ls-files').splitlines():
        if Path(relative).suffix in ('.py','.json','.patch'):
            copy(SAFE,SAFE/relative,PUB/'research_snapshots/seed2027_recoveries/safe_pause_operator'/relative)

    source_docs=b.protocol.OUT.relative_to(ACTIVE)
    for name in ('execution_status.json','primary_comparisons.json','paired_bootstrap_multiplicities.json'):
        copy(ACTIVE,b.protocol.OUT/name,DEST/name)
    # Only small, closed, explicitly named operational receipts are public.
    for n,names in ((1,('paused.json','termination.json','gui_termination.json')),
                    (2,('complete.json','termination.json','gui_termination.json','worker_identity.json','supervisor_identity.json'))):
        for name in names:
            source=b.protocol.session_root(n)/name
            copy_bytes(ACTIVE,source,DEST/'runtime_receipts'/f'session_{n:04d}'/name,source.relative_to(ACTIVE).as_posix())
    term=json.loads((b.protocol.session_root(2)/'gui_termination.json').read_text())
    if term['supervisor_exit_code']!=0 or not term['job_empty_and_handles_signaled']:raise ValueError('NORMAL_GUI_EXIT_REQUIRED')

    receipts=[];summaries=[];full={}
    for run in state['runs']:
        ident=run['id']
        source=ancestor.lexical(ancestor.COMPLETE_RESULTS[ident]) if ident in ancestor.COMPLETE_RESULTS else b.protocol.OUT/(ident+'.json')
        root=next(r for r in (ACTIVE,AUDIT,b.protocol.LIVE_ROOT) if source.is_relative_to(r))
        raw=copy(root,source,DEST/'results'/(ident+'.json'));result=json.loads(raw)
        if result['status']!='COMPLETE' or result['updates']!=47052 or len(result['epochs'])!=9:raise ValueError('NINE_COMPLETE_EPOCHS_REQUIRED')
        if result['epochs'][-1]['checkpoint']['payload_sha256']!=run['last_sha']:raise ValueError('FINAL_LAST_LEDGER_MISMATCH')
        for e in result['epochs']:
            report=dict(e['development']);receipt=report.pop('receipt_sha')
            if digest(report)!=receipt or not report['complete']:raise ValueError('EXISTING_VALIDATION_RECEIPT_DIGEST')
            if report['summary']['scenes']!=10501 or report['summary']['n_valid']!=10501*3430:raise ValueError('EXISTING_DEVELOPMENT_POPULATION')
            receipts.append({'run_id':ident,'epoch':e['epoch'],'train_ids_sha256':e['train']['ids_sha'],
                'train_batches':e['train']['batches'],'validation_receipt_sha256':receipt,
                'last_payload_sha256':e['checkpoint']['payload_sha256'],
                'result_file':'results/'+ident+'.json','result_file_sha256':sha(raw)})
        s=result['epochs'][-1]['development']['summary'];full[ident]=s
        summaries.append({'run_id':ident,'epochs':9,'logical_updates':47052,'brier':s['brier'],'auroc':s['auroc'],
            'average_precision':s['average_precision'],'core_fp64':s['core_fp64'],'conditional_pinball':s['conditional_pinball'],
            'q32_coverage':s['coverage'][-1],'q32_signed_bias':s['q32_signed_bias'],'q32_absolute_error':s['q32_absolute_error'],
            'last_sha256':run['last_sha'],'source_receipt_sha256':result['epochs'][-1]['development']['receipt_sha']})
    if len(receipts)!=54 or sum(r['logical_updates'] for r in state['runs'])!=282312:raise ValueError('EXACT_SIX_BY_NINE_RECEIPTS')
    comparisons=json.loads((DEST/'primary_comparisons.json').read_text())
    if comparisons['scope']!='2024_DEVELOPMENT_SEED2027_ONLY':raise ValueError('SCIENTIFIC_SCOPE')
    for c in comparisons['contrasts']:
        arm=c['contrast'].split('-')[0];metric=c['primary_metric']
        expected=full[b.protocol.run_id(c['model'],arm)][metric]-full[b.protocol.run_id(c['model'],'E0')][metric]
        if c['difference']!=expected:raise ValueError('PUBLISHED_POINT_CONTRAST_TRACEABILITY')
    save(DEST/'epoch_receipt_index.json',{'scope':'EXISTING_METADATA_RECEIPTS_ONLY_NO_MODEL_REEVALUATION','epochs':receipts})
    with (DEST/'final_metrics.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
    with b.quota.ro() as con:
        tables={name:[dict(zip([d[0] for d in cur.description],r)) for r in cur.fetchall()]
                for name in ('campaign','runs','sessions','control') for cur in [con.execute('SELECT * FROM '+name)]}
        phases=con.execute('SELECT phase,count(*) FROM epochs GROUP BY phase').fetchall()
        attempts=con.execute('SELECT status,count(*) FROM attempts GROUP BY status').fetchall()
    if phases!=[('LAST_COMMITTED',54)] or attempts!=[('RETURNED_VERIFIED',109788)]:raise ValueError('LEDGER_COMPLETION_COUNTS')
    save(DEST/'ledger_readonly_export.json',{'observed_utc':state['updated_utc'],'source_database_sha256':sha(b.protocol.DB.read_bytes()),
        'tables':tables,'epoch_phase_counts':phases,'new_attempt_status_counts':attempts,'state':state,
        'limitation':'sessions[2] remains ACTIVE because the original complete() only updates campaign; successful worker, supervisor and GUI termination receipts independently confirm completion. Original database was not edited.'})

    readme='''# seed2027 完成记录与审查发布 · 2026-10-24

本分支汇集 2026-10-21 的完成工作审查，以及后来经研究者批准的隔离恢复、2026-10-23 安全暂停接续和最终完成证据。远端基线为 `50254354f59c50ee9afd409d6820789371f76441`（v6）；本分支保留此前未推送的 v7 发布、审查提交及其原始历史。

## 当前完成事实

seed2027 的 B0/B1 × E0/E1/E2 六组实验各完成 9 轮，共 54 份 LAST_COMMITTED，保留逻辑更新 282,312。最终完成收据生成于北京时间 **2026-10-23 23:20:40**。本次恢复新增 109,788 次更新全部成功返回；历史累计预留 375,425、确认返回 375,424，历史 1 次未核验尝试保持原样，没有退款或升级为成功。训练、监管及 GUI owner 已正常退出，Job 清空。

`results/` 保存六份原始结果 JSON 的完整字节；`epoch_receipt_index.json` 索引 54 份已有验证收据与 LAST SHA；`final_metrics.csv` 仅导出现有最终收据中的指标；`primary_comparisons.json` 和 bootstrap 权重保持原始输出。没有重新评价模型。文件来源、字节数、原始 SHA256 与是否在来源 Git 索引中见 `PUBLICATION_MANIFEST.json`。

## 版本和历史说明

- [原审查报告](../../../../audits/20261021_completed_work_review/AUDIT_REPORT.md)是 2026-10-21 的历史快照，其中 v7 退出、后续恢复未授权及当时未推送均是当时事实。后来的两次 LAST 绑定恢复分别获批追加 5,228 次重放，累计上限从 364,969 经 370,197 到 375,425；2026-10-23 的安全暂停接续没有新增额度或重放。旧报告、失败收据和正式结果均未改写。
- `research_snapshots/seed2027_recoveries/` 保留隔离恢复源码、发布元数据、失败证据与独立操作器修复。它们是依赖原本机 sibling 目录、冻结环境和同对象断点注册的工程快照，**不是可直接安装、部署或启动的发布包**。不要执行这些归档启动器；原样保存的代码 pin 和运行时契约也不代表当前目录获得新授权。
- 2026-10-21 的 P1 修复只覆盖 v7 前序账本识别；并未由此验收后来隔离完成账本与 seed2028 的新接口，seed2028 仍未授权。
- 原 `sessions` 表中 session2 的标签仍为 ACTIVE，因为原 `complete()` 只更新 campaign。这是保留的状态字段不一致；54 份封存、campaign COMPLETE、完整退出收据及 native ABSENT 共同证明实际完成。没有修补或重写原账本。

## 科学解释边界

这些是 **2024 开发集、seed2027 的探索结果**，不是 2025 独立最终测试，不据此宣称确认性科研成功。q32 上尾欠覆盖、强降水误差和旧恢复治理问题继续保留。历史 2025 catalogue/QC-only 的既有授权与读取事实见原审查报告；本次没有新读 2025 数据，也没有授权 seed2028、FinalFit、训练重启或修改科学协议。

原始观测、模型权重、私有 mask、完整 SQLite 运行数据库及大型逐步日志未上传；其现有摘要和哈希按清单保留。文本包含原始本机路径和研究元数据，沿用既有公开仓库披露范围。原始字节用于证据追溯，没有为发布而擦除失败历史。
'''
    # The completion directory is docs/phase_b_v2_seed2027_completion/20261024.
    readme=readme.replace('../../../../audits/','../../audits/')
    (DEST/'README.md').write_text(readme,encoding='utf-8',newline='\n')
    attributes=PUB/'.gitattributes'
    previous=attributes.read_text(encoding='utf-8') if attributes.exists() else ''
    attributes.write_text(previous.rstrip()+'\n\n# Preserve original audit/recovery evidence bytes in this review branch.\nresearch_snapshots/** -text\ndocs/phase_b_v2_seed2027_completion/20261024/** -text\n',encoding='utf-8',newline='\n')
    tool=PUB/'tools/publication/completed_review_seed2027_20261024.py';tool.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(__file__,tool)
    save(DEST/'PUBLICATION_MANIFEST.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'branch':BRANCH,
        'remote_base':REMOTE_BASE,'audit_commit':'118fc763b5edf4f3b155a8c04c2b2fee3b8b7221',
        'source_head_is_code_provenance_not_a_claim_that_new_runtime_outputs_were_committed':True,
        'copied_files':COPIED,'generated_files':['README.md','epoch_receipt_index.json','final_metrics.csv','ledger_readonly_export.json'],
        'excluded_payloads':['raw observations','weights','private masks','runtime databases','step/access logs'],
        'checks':{'inherited_audit_sha256':True,'six_nine_epoch_original_results':True,'54_validation_receipt_digests':True,
          'final_LAST_SHA_matches_ledger':True,'original_comparison_point_estimates':True,'no_new_training_or_model_evaluation':True,
          '54_LAST_COMMITTED':True,'109788_new_updates_verified':True,'native_job_absent':True,'original_history_modified':False},
        'reused_tests':{'audit_P1':'5/5 unchanged source; original delivery checks','console_free_v2':'7 contract + 5 metadata tests and native probes; original evidence','safe_pause_operator':'5/5 unchanged source; original targeted_test_results.json'},
        'self_reference':'This manifest excludes its own bytes; Git commit and tree pin the complete publication.'})
    print(json.dumps({'publication_root':str(PUB),'copied_files':len(COPIED),'copied_bytes':sum(v['bytes'] for v in COPIED.values()),'existing_receipts_checked':54,'scientific_execution':False},indent=2))


if __name__=='__main__':main()
