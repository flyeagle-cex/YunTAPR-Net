"""Export safe receipts and reports from the journal; never re-open raw files."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

HERE=Path(__file__).absolute().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_full_payload_integrity.audit import BASELINE,FLAGS,LIMIT_BYTES,LIMIT_SECONDS,CHUNK

def write(name,value):
    path=HERE/name
    path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode() if not isinstance(value,str) else value.encode())

def build(private,supervisor):
    con=sqlite3.connect(private/'journal.sqlite');con.row_factory=sqlite3.Row
    meta={r['key']:json.loads(r['value']) for r in con.execute('SELECT * FROM meta')}
    if supervisor['hard_time_stop']:
        meta['stage']='STOPPED';meta['failure']={'type':'TimeoutError','reason':'SUPERVISOR_SIX_HOUR_CAP'}
    counts=dict(con.execute('SELECT status,COUNT(*) FROM files GROUP BY status').fetchall())
    rows=con.execute('SELECT COUNT(*),COALESCE(SUM(read_bytes),0),COALESCE(SUM(payload_attempts),0),COALESCE(SUM(payload_success),0),COALESCE(SUM(metadata_attempts),0),COALESCE(SUM(metadata_success),0) FROM files').fetchone()
    complete=(meta.get('stage')=='COMPLETE' and rows[0]==67006 and counts.get('SHA_PASS',0)==67006 and not supervisor['hard_time_stop'] and supervisor['worker_exit_code']==0)
    status=dict(overall_status='FULL_PAYLOAD_SHA_PASS' if complete else 'NOT_VERIFIED_STOPPED',scope='FROZEN_2023_2024_READ_ONLY_SHA256_ONLY',
        baseline_commit=BASELINE,expected_files=67006,registered_files=rows[0],sha_matched_files=counts.get('SHA_PASS',0),
        coverage_fraction=counts.get('SHA_PASS',0)/67006,remaining_not_sha_matched=67006-counts.get('SHA_PASS',0),status_counts=counts,
        payload_bytes_returned=rows[1],payload_bytes_GiB=rows[1]/1024**3,public_metadata_bytes=meta.get('public_metadata_bytes',0),
        predicted_payload_bytes=meta.get('predicted_bytes'),elapsed_seconds=supervisor['elapsed_seconds'],
        resources=meta.get('resources'),inflight_read_uncertainty_upper_bytes=meta.get('inflight_requested_bytes',0),
        failure=meta.get('failure'),prior_full_preflight_overall_status='NOT_VERIFIED_UNCHANGED',no_global_immutable_snapshot_claim=True,
        no_new_raw_decode=True,no_private_paths_or_payloads_published=True,RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=True,**FLAGS)
    fields=['i','file_key','kind','year','expected_sha','actual_sha','size','frozen_size','status','read_bytes','payload_attempts','payload_success','metadata_attempts','metadata_success','opened_utc','closed_utc','seconds','error']
    with gzip.open(HERE/'PAYLOAD_SHA_RECEIPTS.csv.gz','wt',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(fields)
        for row in con.execute('SELECT '+','.join(fields)+' FROM files ORDER BY i'):writer.writerow(row)
    failed=[dict(r) for r in con.execute("SELECT i,file_key,kind,year,status,error FROM files WHERE status IN ('FAILED','METADATA_FAILED','READING') ORDER BY i")]
    ledger=dict(scope=status['scope'],limits=dict(max_total_content_bytes=LIMIT_BYTES,max_elapsed_seconds=LIMIT_SECONDS,chunk_bytes=CHUNK,max_working_set_bytes=2*1024**3,min_audit_disk_free_bytes=256*1024**2),
        inventory_counts=meta.get('inventory_counts'),order=meta.get('inventory_order'),payload_open_attempts=rows[2],payload_open_successes=rows[3],
        metadata_handle_attempts=rows[4],metadata_handle_successes=rows[5],directory_metadata_handles=meta.get('directory_metadata_opens',0),
        payload_application_bytes=rows[1],public_metadata_bytes=meta.get('public_metadata_bytes',0),total_content_bytes_accounted=rows[1]+meta.get('public_metadata_bytes',0),
        public_metadata_counter_scope='Pinned Audit.public reads only; excludes interpreter imports, git, source-identity lookup, repository review and the local journal',
        actual_physical_storage_bytes='NOT_MEASURED_OS_CACHE_MAY_APPLY',raw_resolve_calls=0,raw_stat_calls=0,
        raw_stat_counter_scope='Python Path.resolve/os.stat only; native metadata handles counted separately',
        controlled_2025_file_metadata_handle_attempts=0,controlled_2025_payload_opens=0,measurement_scope='Exact application handle entrypoints; not system-wide monitoring',
        handle_policy='OPEN_EXISTING, read-only access, FILE_SHARE_READ only, OPEN_REPARSE_POINT, parent directory locks; no write/delete sharing',
        supervisor=supervisor,audit_started_at_utc=meta.get('started_at_utc'),audit_finished_at_utc=meta.get('finished_at_utc'),resources=meta.get('resources'),
        interrupted_read_byte_uncertainty_upper=meta.get('inflight_requested_bytes',0),failed_files=failed,RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=True,**FLAGS)
    write('READ_SCOPE_AND_RESOURCE_LEDGER.json',ledger);write('final_status.json',status)
    write('source_identity.json',dict(baseline_commit=BASELINE,public_source_pins=meta.get('source_pins',[]),real_payload_paths_published=False))
    write('README.md',f'''# 2023/2024 冻结 payload SHA 专项 v1

本轮状态：**{status['overall_status']}**。本地与远端起始基线 {BASELINE}；仅对冻结引用进行完整文件 SHA-256 校验，没有解码、模型推理或训练。

本次匹配 {status['sha_matched_files']:,} / 67,006 文件；应用层 payload 返回 {status['payload_bytes_GiB']:.6f} GiB，监督进程耗时 {status['elapsed_seconds']:.3f} 秒。原 294 个已核验文件也在统一新证据中重新读取，不复用旧 SHA 通过记录。

payload 只读句柄成功 {rows[3]:,} 次，文件属性句柄成功 {rows[5]:,} 次，父目录属性句柄 {meta.get('directory_metadata_opens',0)} 个。峰值工作集 {((meta.get('resources') or {}).get('peak_working_set_bytes',0)/1024**3):.6f} GiB；实际物理磁盘字节和 CPU 时间没有测量，不能用应用返回字节代替物理 I/O。

- [完整性报告](FROZEN_PAYLOAD_SHA_AUDIT.md)、[异常及未解决项](INTEGRITY_FAILURES_AND_BLOCKERS.md)。
- [读取与资源账本](READ_SCOPE_AND_RESOURCE_LEDGER.json)、[逐文件脱敏收据](PAYLOAD_SHA_RECEIPTS.csv.gz)。
- [快照及 TOCTOU 风险](SNAPSHOT_AND_TOCTOU_RISKS.md)、[来源](source_identity.json)、[状态](final_status.json)、[清单](manifest.json)。

脚本仅使用标准库，未导入 PyTorch、netCDF4 或原始数据 decoder。数据文件均使用只读 Windows 句柄；准确引用诱导的父目录句柄在本次审计期间持有，拒绝重解析点、写入和删除共享。没有遍历原始目录、下载、替换文件、修改 cache/scaler/mask 或数据划分。

历史 2025 路径属性访问仍 NOT_INSTRUMENTED。专项 SHA 通过不升级整体真实预检，不证明业务近实时可用性或未来训练消费字节不变。本包完成后停止；不自动启动 preflight、Runner、训练或恢复。
''')
    write('FROZEN_PAYLOAD_SHA_AUDIT.md',f'''# 冻结完整性核验结果

结果 **{status['overall_status']}**；覆盖 {status['sha_matched_files']:,}/67,006（{100*status['coverage_fraction']:.6f}%），未匹配/未完成 {status['remaining_not_sha_matched']:,}。预期去重数量为 B13 66,516、IMERG 490；清单来自原始 2023/2024 B1 manifest、B0配对manifest及16份 frame identity CSV。逐份公开元数据按冻结 SHA 验证，前次修复防火墙源码 SHA 必须匹配 c4d749c2190a0e23a44d86535a02a6ca0d51274f096418d935d2acd294507f35，否则不读取原始文件。

顺序为 2023 再2024、原B1行顺序、每场景IMERG再slot0..5、首次引用去重。67,006 为不同文件数，不是场景数或独立事件数。样本资格和角色没有改变。

先完成全部允许文件的句柄元数据预估，再读取 payload。本轮完整预估字节为 {meta.get('predicted_bytes','NOT_VERIFIED')}；实际 payload 返回 {rows[1]} 字节，公开元数据返回 {meta.get('public_metadata_bytes',0)} 字节。500 GiB 上限保守地涵盖两者。状态分布：`{json.dumps(counts)}`。

每文件收据包含不含绝对路径的 file_key、年份/类型、预期/实际SHA、文件大小、状态、读取字节、句柄成功数、开始/结束UTC与失败原因。file_key 是类型、年份和规范化相对路径的 SHA；不发布相对路径明文或原始数据。数据库保存前先登记读取预约，读取后持久化字节；监督进程可在6小时前强制终止阻塞调用，异常不自动重试。

全部 SHA_PASS 文件从同一个只读句柄完整读取；核对元数据计划与打开对象的 volume/file-index/size/mtime，前后 GetFileInformationByHandle 一致。SHA 缺失、引用冲突、尺寸变化、权限或内容不一致立即停止，无跳过后宣布通过的逻辑。内容结果只证明本次对应读取窗口，不能证明未来消费。
''')
    write('INTEGRITY_FAILURES_AND_BLOCKERS.md',f'''# 异常与剩余阻塞

本轮失败：`{json.dumps(meta.get('failure'),ensure_ascii=False)}`。文件级异常/中断记录 {len(failed)} 个，详见账本；未完成数量 {status['remaining_not_sha_matched']}。只有完整67,006匹配才为 FULL_PAYLOAD_SHA_PASS。已通过前缀不会自动作为未来跳读缓存；本脚本拒绝覆盖既有 attempt，不自动重试。

即使专项通过，首次真实预检整体仍 NOT_VERIFIED：历史首次2025负面测试路径属性查询未计数、业务文件生成/传输/入库可用性未建立、真实正式loader和审批验真服务尚未接入。2024仍为反复使用过的开发验证；IMERG Final仍为回顾性监督。科学协议、代码集成、资源许可、正式运行和具体LAST恢复分别需要独立研究者决定。

本轮 optimizer更新0、模型forward0、历史checkpoint读取0、2025像元读取0；历史恢复NOT_GRANTED，Phase-B及正式科学执行未授权。
''')
    write('SNAPSHOT_AND_TOCTOU_RISKS.md','''# 快照与未来消费风险

本次不用 Path.resolve/stat 检查原始路径。任何 Windows API 调用前先检查封闭年份、准确根、路径词法、日期、扩展名及冻结注册身份。root 名称中可能含历史年份跨度，许可仅覆盖其冻结2023/2024子引用，不把root名称当作2025数据许可。父目录仅为清单诱导的准确路径，没有枚举其他文件。

只读句柄以 OPEN_REPARSE_POINT 拒绝链接；父目录句柄保持至审计结束，并限制写入/删除共享。payload 句柄也不允许写入/删除共享，校验元数据计划、最终句柄路径与文件身份，并在读取结束复核句柄信息。无法获得锁、遇到重解析点或目标变化则停止，不自行追随到另一套文件。这里的审计计数是应用入口，不是内核或全系统追踪。

这是逐文件、不同时间窗口的核验，不是67,006文件同时冻结的全局存储快照。每个payload句柄关闭后文件内容仍可能改变。一次SHA、mtime或大小记录不能担保未来训练读取相同字节，也不能单独证明一个可写缓存可信。

未来正式消费应在新的明确授权下，对实际消费的同一只读句柄字节流再次校验冻结SHA，并让解码器消费该已核验字节或受控不可变副本；或者建立经审查的不可变快照、版本身份、权限与失效机制。不能只凭本包路径/SHA记录跳过读取时校验。本轮没有创建原始数据副本、缓存或快照。

历史2025路径属性查询仍NOT_INSTRUMENTED，本轮不执行真实2025负面路径测试。纯合成词法负面测试必须在任何resolve/stat/open/backend调用前拒绝。不能据此追溯宣称历史或系统级零访问。
''')
    files=sorted(p for base in (ROOT/'src/yuntapr/experimental/phase_b_v2_full_payload_integrity',HERE) for p in base.rglob('*') if p.is_file() and '.local' not in p.parts and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='manifest.json')
    write('manifest.json',dict(baseline_commit=BASELINE,scope='SAFE_PUBLIC_SHA_RECEIPTS_NO_RAW_PAYLOADS',files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in files]))
    con.close();return status
