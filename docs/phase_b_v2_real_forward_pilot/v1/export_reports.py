"""Publish only safe summaries/journals, never reopen raw observations."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).absolute().parent; ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_real_forward_pilot import BASELINE, FLAGS, LIMITS, SCOPE

def write(name: str, value) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n' if not isinstance(value, str) else value
    (HERE/name).write_bytes(text.encode('utf-8'))

def build(private: Path, supervisor: dict) -> dict:
    events = []; partial = False
    if (private/'events.jsonl').exists():
        for line in (private/'events.jsonl').read_bytes().splitlines():
            try: events.append(json.loads(line))
            except ValueError: partial = True
    decoded = [e for e in events if e['event'] == 'SCENE_DECODED']
    metadata = [e for e in events if e['event'] == 'PUBLIC_METADATA_READ']
    forward = [e for e in events if e['event'] == 'FORWARD_COMPLETED']
    chunks = [e for e in events if e['event'] == 'READ_CHUNK']
    receipt = private/'worker_status.json'
    if receipt.exists():
        status = json.loads(receipt.read_bytes())
    else:
        attempts = Counter(e['model'] for e in events if e['event'] == 'FORWARD_RESERVED')
        successes = Counter(e['model'] for e in forward)
        status = dict(scope=SCOPE, baseline_commit=BASELINE, limits=LIMITS, **FLAGS,
            overall_status='NOT_VERIFIED_STOPPED', decoded_scenes=len(decoded),
            model_batch_attempts={k:attempts[k] for k in ('B0_MATCHED_V2','B1_V2')},
            model_batch_successes={k:successes[k] for k in ('B0_MATCHED_V2','B1_V2')},
            model_scene_forwards={k:successes[k]*2 for k in ('B0_MATCHED_V2','B1_V2')},
            raw_reads=[{k:v for k,v in e.items() if k not in ('event','scope','utc')}
                       for e in events if e['event']=='READ_FINISHED'],
            model_batch_records=forward, failure=supervisor['hard_stop'] or 'WORKER_WITHOUT_FINAL_RECEIPT')
    status['supervisor'] = supervisor
    status['decoded_role_counts'] = dict(Counter(e['role'] for e in decoded))
    status['original_selection_reused_without_reordering'] = len(decoded)==len(set(e['position'] for e in decoded)) and [e['position'] for e in decoded]==list(range(len(decoded)))
    status['historical_2025_path_attributes'] = 'NOT_INSTRUMENTED'
    reads = status['raw_reads']
    status['payload_open_attempts'] = len([e for e in events if e['event']=='READ_RESERVED'])
    status['payload_open_successes'] = sum(bool(e.get('open_success')) for e in reads)
    status['payload_sha_pass_reads'] = sum(e['status']=='SHA_PASS' for e in reads)
    status['payload_unique_file_keys'] = len(set(e['file_key'] for e in reads))
    status['raw_payload_content_bytes'] = sum(e['returned_bytes'] for e in chunks)
    status['public_metadata_content_bytes'] = sum(e['bytes'] for e in metadata)
    status['public_metadata_open_count'] = len(metadata)
    status['pre_access_metadata_content_bytes'] = (status.get('pre_access_failed_attempt') or {}).get('public_metadata_content_bytes',0)
    status['conservative_all_logged_content_bytes'] = status['raw_payload_content_bytes']+status['public_metadata_content_bytes']+status['pre_access_metadata_content_bytes']
    status['journal_partial_line'] = partial
    status['raw_read_bytes_uncertainty_upper_bound'] = 0
    if not receipt.exists():
        last = next((e for e in reversed(events) if e['event'] in ('READ_CHUNK','READ_CHUNK_RESERVED')), None)
        if last and last['event']=='READ_CHUNK_RESERVED': status['raw_read_bytes_uncertainty_upper_bound']=last['requested_bytes']
        status['other_inflight_public_metadata_bytes'] = 'NOT_ESTABLISHED_IF_HARD_KILLED'
    status['scene_receipts_count'] = len(decoded)
    status['late_file_creation_references_in_selected_scenes'] = sum(f['file_created_after_analysis'] for e in decoded for f in e['frames'])
    status['this_pilot_2025_requested_path_operations'] = 0
    status['system_wide_zero_access_proven'] = False
    status['operational_near_realtime_availability'] = 'NOT_VERIFIED'
    status['prior_full_preflight_overall_status'] = 'NOT_VERIFIED_UNCHANGED'
    status['scientific_performance_evidence'] = False
    status['test_scope'] = '48_REAL_SCENES_FRESH_INFERENCE_AND_SYNTHETIC_BOUNDARY_UNITS'
    status['resource_peaks'] = {
        'worker_peak_working_set_bytes': max((status.get('cpu_resources') or {}).get('peak_working_set_bytes',0), (supervisor.get('last_process_resources') or {}).get('peak_working_set_bytes',0)),
        'cuda_peak_allocated_bytes': max((e['cuda_peak_allocated_bytes'] for e in forward),default=0),
        'cuda_peak_reserved_bytes': max((e['cuda_peak_reserved_bytes'] for e in forward),default=0)}
    can_pass = (status.get('overall_status')=='BOUNDED_REAL_FORWARD_PILOT_PASS'
        and not supervisor['hard_stop'] and supervisor['worker_exit_code']==0 and not partial
        and len(decoded)==48 and status['original_selection_reused_without_reordering']
        and status['decoded_role_counts']=={'Train':24,'DevelopmentValidation':24}
        and status['model_batch_successes']=={'B0_MATCHED_V2':24,'B1_V2':24}
        and len(forward)==48 and len(reads)==337 and all(e['status']=='SHA_PASS' for e in reads)
        and status['conservative_all_logged_content_bytes']==status.get('accounted_content_bytes')
        and status.get('state_sha256_before')==status.get('state_sha256_after')
        and all(e['state_unchanged'] and e['checks']['finite'] and e['checks']['strictly_monotone'] for e in forward)
        and supervisor.get('original_budget_elapsed_seconds',supervisor['elapsed_seconds'])<1800 and status['resource_peaks']['worker_peak_working_set_bytes']<=3*1024**3
        and status['conservative_all_logged_content_bytes']<=4*1024**3)
    if not can_pass:
        status['overall_status']='NOT_VERIFIED_STOPPED'
        if not status.get('failure'): status['failure']='EXPORT_COVERAGE_OR_IDENTITY_GATE_NOT_MET'
    write('DATA_ACCESS_LEDGER.json', dict(scope=SCOPE, reads=reads,
        public_metadata_reads=metadata, parent_directory_opens=next((e['count'] for e in events if e['event']=='PARENT_LOCKS'),0),
        native_payload_open_attempts=status['payload_open_attempts'], native_payload_content_bytes=status['raw_payload_content_bytes'],
        application_open_count_scope='selected raw read handles + induced directory handles; netCDF opens are memory views',
        exact_read_bytes=status['raw_read_bytes_uncertainty_upper_bound']==0 and receipt.exists(),
        raw_read_bytes_uncertainty_upper_bound=status['raw_read_bytes_uncertainty_upper_bound'],
        no_os_disk_sector_read_measurement=True, historical_2025_path_attributes='NOT_INSTRUMENTED',
        this_pilot_2025_requested_path_operations=0, system_wide_zero_access_proven=False))
    write('SCENE_PROVENANCE_RECEIPTS.json', dict(scope=SCOPE, scenes=decoded))
    write('FORWARD_RECEIPTS.json', dict(scope=SCOPE, forwards=forward))
    write('source_identity.json',dict(baseline_commit=BASELINE, public_source_pins=status.get('public_source_pins',[]),
        original_selection_sha256='3d63d418fda3e388891379489014d29c2cbe99e8b82adee35f0b168087d90634',
        historical_checkpoints_consumed=False))
    write('final_status.json', status)
    elapsed=supervisor['elapsed_seconds']; peaks=status['resource_peaks']; n=status['decoded_scenes']; batches=status['model_batch_successes']
    write('README.md',f"""# Phase-B v2 限额真实数据前向 pilot v1

状态：`{status['overall_status']}`。范围：`{SCOPE}`，来源基线 `{BASELINE}`。

复用首次只读预检的固定 48 场景及顺序，冻结 seed 2026 配对 fresh 初始化，不加载历史权重。真实完成 {n} 场景，B0/B1 batch 前向分别 {batches['B0_MATCHED_V2']}/{batches['B1_V2']} 次，batch 固定为 2。

导航：[适配实现](REAL_ADAPTER_IMPLEMENTATION.md)、[前向检查](REAL_FORWARD_VALIDATION.md)、[同字节与访问审计](BYTE_IDENTITY_AND_ACCESS_AUDIT.md)、[资源](RESOURCE_AND_LATENCY_REPORT.md)、[失败与阻塞](BLOCKERS_AND_FAILURES.md)、[最终机器状态](final_status.json)。

`run_pilot.py` 默认只允许新建本地 `attempt_001`。本轮另保留一次明确的访问前 PyTorch 包装冲突修复续接 attempt_002，继承原始时间和字节额度；任何真实场景/forward 已开始的失败都不能走该入口，既存尝试不覆盖。`test_pilot.py` 仅作新保护逻辑的合成单元测试，不构建模型。公开 JSON 不含真实像元数组、权重或私有路径。

本轮通过仅证明随机初态下受控接口可用。Phase-B、科学接受、历史恢复和业务近实时能力仍未获批准或未验证；历史 2025 路径属性访问继续为 `NOT_INSTRUMENTED`。
""")
    write('REAL_ADAPTER_IMPLEMENTATION.md',"""# 隔离真实适配器

`plan.FrozenPlan` 校验公开 frozen manifest、原取样清单和 scaler 的 SHA，按原索引取 24+24 场景；仅登记所选 294 个不同 B13/IMERG 引用。读取之前按原冻结根、年份、扩展名、精确注册身份进行词法拒绝，不调用旧 loader 的 resolve/staging 路径。

`adapter.VerifiedReader` 复用已修复的 Windows 只读句柄：不共享写入/删除，拒绝 reparse point，保留选中父目录句柄，绑定实际目标与句柄元数据。逐块 SHA 对同次读取的 bytearray 计算，匹配后转 immutable bytes；冻结 netCDF 读函数只能通过精确内存别名消费这些字节，不重新打开原路径。

`RealAdapter.initialize_geometry` 使用真实冻结云南 mask 和 SP04，不用人工排列。冻结 shared scaler 不再拟合，保持 FP64 预处理算术至 FP32 输入。有效参考掩膜和云南地理掩膜独立；3430 个中心入界格点不变。`scene` 校验六帧 −60/−50/−40/−30/−20/−10 分钟及实际观测截止；文件生成晚于分析并不改变已冻结的回顾性资格。

`RealBatch.validate` 检查精确形状、dtype、设备、来源 owner、输入 SHA 和参考/地理 SHA。B0 输入必须是 B1 最后一帧，双方共用同一参考和地理身份。`pair` 保持原顺序，不依据参考雨量或输出取样。

`pilot.forward_real` 只接受精确冻结模型类和适配器来源，eval、参数 FP32 且 requires_grad=False。CUDA BF16 主干/发生头及 FP64 条件分位数保持已审查的正式精度语义。所有模型 forward 均在 inference_mode 内。

`resources.Budget` 固定 48 场景、48 batch 调用、4 GiB 内容、30 分钟和 3 GiB 工作集；父进程每 0.2 秒审计工作集并在期限前停止。无 CPU 降级、精度降级、自动重试或扩额。`formal_entry` 永久拒绝；未改动正式 Runner 的 always-deny 审批边界。
""")
    write('REAL_FORWARD_VALIDATION.md',f"""# 真实输出结构验证

实际状态 `{status['overall_status']}`；完成 {n}/48 场景。B0/B1 成功 batch：{batches}；场景前向：{status['model_scene_forwards']}。

要求输入 [2,1,501,501]/[2,6,501,501] FP32；参考 [2,1,100,100] FP32；有效和真实云南掩膜 bool。输出发生 logit/probability [2,1,100,100] BF16，分位数 [2,32,100,100] FP64，log1p(mm/h)。验证有限性、sigmoid 一致、严格单调、首分位数 > log1p(0.1)、SP04 全支撑、无梯度图、模型 state SHA 不变。

逐批实测证据见 `FORWARD_RECEIPTS.json`。未进行 expm1、loss、Brier、AUROC、AP、Pinball 或降水性能评价。E0/E1/E2 不参与本轮随机初始化输出比较。FP32/FP64 物理转换风险只比较浮点界限，不作物理可信性结论。

24+24 场景均可被 batch=2 整除，最后一批为 2；没有额外构造 batch=1 真实尾批。训练、backward、optimizer、私有权重读写均受阻断。PASS 不等于正式训练就绪。
""")
    write('BYTE_IDENTITY_AND_ACCESS_AUDIT.md',f"""# 同字节 SHA 与访问审计

原全量 67,006 文件 SHA 是身份基线，本轮不重复扫描。实际原始 payload 只读打开尝试 {status['payload_open_attempts']} 次、成功 {status['payload_open_successes']} 次、SHA 匹配 {status['payload_sha_pass_reads']} 次；不同来源身份 {status['payload_unique_file_keys']} 个（包括真实 mask）。B13/IMERG 每场景重新只读绑定，重复引用不会被替换成未经验证的缓存。

原始 payload 内容读取 {status['raw_payload_content_bytes']:,} 字节；公开冻结元数据内容 {status['public_metadata_content_bytes']:,} 字节；保守合计 {status['conservative_all_logged_content_bytes']:,} 字节，均计入 4 GiB 上限。netCDF 仅打开 immutable 内存视图，不额外读取原文件。计数是应用层 read 返回字节和受限句柄，不是 OS 磁盘扇区/I/O 总量。

`DATA_ACCESS_LEDGER.json` 记录脱敏文件 key、预期/实际 SHA、大小、时间、错误与句柄结果。只读共享锁+读取前后句柄身份降低竞态；解码用同一已验 bytes，排除校验后重开另一版本的间隙。句柄关闭后源文件仍可变化，未来正式消费须再次验证。

本轮请求的 2025 路径操作为零，原始像元读取零；不追溯声称系统级全历史零访问。首次预检历史 2025 路径属性查询为 `NOT_INSTRUMENTED`，仍不能量化。旧完整预检整体 `NOT_VERIFIED` 保持不变。
""")
    write('RESOURCE_AND_LATENCY_REPORT.md',f"""# 实测资源与耗时

实际成功执行的父进程计时 {elapsed:.3f} 秒；包括首败与访问前修复等待的原始预算计时 {supervisor.get('original_budget_elapsed_seconds',elapsed):.3f} 秒，未重置 30 分钟额度。worker 工作集峰值 {peaks['worker_peak_working_set_bytes']:,} 字节（{peaks['worker_peak_working_set_bytes']/1024**3:.3f} GiB）。CUDA 峰值 allocated {peaks['cuda_peak_allocated_bytes']:,} 字节，reserved {peaks['cuda_peak_reserved_bytes']:,} 字节。设备与启动前可用显存见 final_status.cuda_admission；没有假定或外推正式九轮训练耗时。

Win32 private commit 最终值 {status.get('cpu_resources',{}).get('private_bytes',0):,} 字节、peak pagefile/commit {status.get('cpu_resources',{}).get('peak_pagefile_bytes',0):,} 字节；这些指标与物理驻留工作集不同。本轮 3 GiB 约束按研究者指定的进程工作集实施，不以 commit 值冒充工作集。公开元数据准备核验不读取原始内容；本表 I/O 计数以实际 pilot 的受限句柄为范围。

`SCENE_PROVENANCE_RECEIPTS.json` 提供逐场景 SHA+解码+固定预处理耗时；`FORWARD_RECEIPTS.json` 提供逐 batch transfer/sync、forward+结构检查耗时及显存。GPU 数值是 PyTorch allocator 统计，不等于设备全部进程占用；CPU 是 Win32 进程工作集。父进程监督间隔 0.2 秒，系统采样和硬停止有调度延迟，未声称无穷精度的瞬时零超调保证。

所选场景中共有 {status['late_file_creation_references_in_selected_scenes']} 个文件生成晚于分析时刻的时相引用；实际卫星观测因果性与业务可获取时间是不同证据。此测量含读取和审计开销，不构成业务近实时传输、入库、可用延迟验证。IMERG Final 仅为回顾性参考。
""")
    write('BLOCKERS_AND_FAILURES.md',f"""# 失败、修复与剩余边界

最终实际数据尝试异常：`{status.get('failure')}`；父进程停止原因：`{supervisor['hard_stop']}`。访问前 attempt_001 的 PyTorch 包装函数冲突已修复，真实读取和 forward 均为零，其失败收据见 tests/PRE_ACCESS_FAILURE.json；attempt_002 未重置原时间/字节额度。原始日志仅留本地 .local，公开的脱敏收据保留实际失败。其他检查初次结果与修复见 tests/ 记录。任何真实场景失败只公布部分覆盖，不选替代场景、不自动重跑。

正式集成仍需研究者独立审核与批准协议、M-C 统计定位、尚未建立的效应/副作用界限，验真实际授权事件、代码版本、真实数据消费范围和资源额度。初批 seed2026 六组训练需单独执行许可；恢复需独立绑定具体 LAST SHA 与原执行授权祖先。未追认 B1 历史恢复。

本轮没有训练入口升级，没有正式 optimizer step/backward，没有历史 checkpoint 读取；2025 继续封存。真实训练事务、正式权限服务、完整数据持续身份与业务实时可用性均不由本 pilot 证明。完成此包后停止。
""")
    return status

def manifest() -> None:
    public = sorted(p for p in HERE.rglob('*') if p.is_file() and '.local' not in p.parts and '__pycache__' not in p.parts and p.name!='manifest.json')
    public += sorted(p for p in (ROOT/'src/yuntapr/experimental/phase_b_v2_real_forward_pilot').rglob('*.py'))
    write('manifest.json', dict(baseline_commit=BASELINE, publication_scope='code and deidentified engineering receipts only',
        files=[dict(path=p.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size) for p in public]))

if __name__=='__main__': manifest()
