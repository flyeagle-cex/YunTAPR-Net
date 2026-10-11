"""Export existing receipts only. Never load raw observations or checkpoints."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_real_train_smoke/v1'
LOCAL=OUT/'.local'
SOURCE=ROOT/'src/yuntapr/experimental/phase_b_v2_real_train_smoke'
status=json.loads((LOCAL/'attempt_001/worker_status.json').read_bytes())
driver=json.loads((LOCAL/'driver_status.json').read_bytes())
assert status['overall_status']=='BOUNDED_REAL_TRAIN_SMOKE_PASS'
assert status['quota']['reserved_step_attempts']==status['quota']['entered_optimizer_calls']==status['quota']['returned_optimizer_calls']==2
assert status['quota']['state']=='COMPLETE_SEALED'
assert all(r['status']=='SHA_PASS' and r['actual_sha256']==r['expected_sha256'] for r in status['raw_reads'])

def write(name,text):
    text=text.replace('\r\r\n','\n').replace('\r\n','\n')
    (OUT/name).write_bytes((text.rstrip()+'\n').encode('utf-8'))
def dump(name,value): write(name,json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))
def gib(value): return f'{value/1024**3:.3f}'
def sha(raw): return hashlib.sha256(raw).hexdigest()

# Preserve exact executed versions, separate from the post-run watchdog repair.
run=(SOURCE/'run.py').read_text(encoding='utf-8').replace('import os\n','')
start=run.index('    # Venv executables on Windows may launch a different interpreter PID.\n')
end=run.index('    pins,code_sha=source_identity()\n',start)
run=run[:start]+run[end:]
launch='''"""One-shot child with external CPU/time watchdog; there is no retry branch."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from . import ROOT,OUT,LIMITS
from .resources import memory,utcnow

def launch():
    root=OUT/'.local'; root.mkdir(exist_ok=True)
    if (root/'attempt_001').exists() or (root/'driver_status.json').exists():
        raise PermissionError('NO_SMOKE_LAUNCH_RETRY')
    env=os.environ.copy(); env.update(PYTHONPATH=str(ROOT/'src'),PYTHONHASHSEED='2026',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    started=time.monotonic(); peak=0; violation=None
    with (root/'worker_console.private.log').open('xb') as log:
        process=subprocess.Popen([sys.executable,'-m','yuntapr.experimental.phase_b_v2_real_train_smoke.run'],
            cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        while process.poll() is None:
            try: peak=max(peak,memory(process._handle)['working_set_bytes'])
            except OSError:
                if process.poll() is None: violation='CPU_WATCHDOG_UNAVAILABLE'
            if peak>LIMITS['MAX_CPU_WORKING_SET_BYTES']: violation='CPU_WATCHDOG_LIMIT'
            if time.monotonic()-started>=LIMITS['MAX_ELAPSED_SECONDS']: violation='TIME_WATCHDOG_LIMIT'
            if violation:
                process.kill(); process.wait(); break
            time.sleep(.1)
    status=dict(finished_at_utc=utcnow(),exit_code=process.returncode,watchdog_violation=violation,
        elapsed_seconds=time.monotonic()-started,peak_sampled_child_working_set_bytes=peak,
        monitor_interval_seconds=.1,retries=0)
    (root/'driver_status.json').write_text(json.dumps(status,indent=2)+'\\n',encoding='utf-8')
    print(json.dumps(status))
    return process.returncode

if __name__=='__main__': raise SystemExit(launch())
'''
snapshot=OUT/'execution_source_snapshot'; snapshot.mkdir(exist_ok=True)
for name,text in (('run.py',run),('launch.py',launch)):
    rel=(SOURCE/name).relative_to(ROOT).as_posix()
    assert sha(text.encode())==status['source_pins'][rel], ('EXECUTION_SNAPSHOT_MISMATCH',name)
    (snapshot/(name+'.txt')).write_bytes(text.encode())
delivered={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(SOURCE.glob('*.py'))}
changed=[p for p,h in delivered.items() if status['source_pins'].get(p)!=h]
assert {Path(p).name for p in changed}=={'run.py','launch.py'}
dump('source_identity.json',dict(baseline_commit=status['baseline_commit'],
    executed_aggregate_sha256=status['source_sha256'],executed_source_pins=status['source_pins'],
    delivered_smoke_source_pins=delivered,post_execution_changes=changed,
    post_execution_reason='Actual worker PID watchdog repair only; no real smoke rerun',
    exact_changed_execution_sources='execution_source_snapshot/*.py.txt'))

# Keep source-derived scalar summaries only; deny any private absolute paths.
public={k:v for k,v in status.items() if k not in ('initialization','source_pins')}
public['initialization']={k:status['initialization'][k] for k in (
    'seed','state_sha256','buffers_sha256','same_shape_shared_bit_identical',
    'native_zero_skip_preserved','parameter_counts','historical_checkpoint_loaded')}
public['external_watchdog_limitation']='VENV_WRAPPER_PID_MONITORED; actual-worker PID repair only statically tested after execution'
public['driver']=driver
public['driver']['peak_sampled_child_working_set_bytes_is_actual_worker_peak']=False
public['post_execution_watchdog_end_to_end_status']='NOT_VERIFIED_NO_REAL_RERUN'
public['static_tests']=dict(final_passed=39,final_failed=0,actual_optimizer_calls=0,
    initial_runs=[{'tests':36,'errors':2},{'tests':37,'errors':1},{'tests':37,'errors':0}],
    post_environment_change_failed_runs=[{'tests':39,'errors':28},{'tests':39,'errors':28}],
    final_run={'tests':39,'errors':0})
public['final_commit_identity']='Resolve via git log for this directory; self-referential commit SHA is not embedded'
dump('final_status.json',public)
dump('DATA_ACCESS_RECEIPTS.json',dict(raw_reads=status['raw_reads'],scene_receipts=status['decoded_scene_receipts'],
    raw_unique_files=len({r['file_key'] for r in status['raw_reads']}),raw_open_successes=sum(r['open_success'] for r in status['raw_reads']),
    raw_payload_bytes=sum(r['bytes'] for r in status['raw_reads']),
    public_metadata_bytes=sum(p['bytes'] for p in status['public_source_pins']),
    accounted_content_bytes=status['accounted_content_bytes'],historical_2025_path_attributes='NOT_INSTRUMENTED'))
dump('QUOTA_RECEIPT.json',status['quota'])
events=(LOCAL/'attempt_001/events.jsonl').read_bytes()
write('TRANSACTION_EVENTS.jsonl',events.decode())

# Redact every local absolute path from development logs; retain raw originals.
for p in sorted((LOCAL/'development').glob('*.raw.log')):
    text=p.read_bytes().decode('utf-8',errors='replace')
    text=re.sub(r'File "[A-Za-z]:[^"\n]*[\\/]([^\\/"\n]+)"',r'File "<local-redacted>/\1"',text)
    text=re.sub(r'[A-Za-z]:[\\/][^\n]*','<local-path-redacted>',text)
    write('tests/'+p.name.replace('.raw.log','.redacted.log'),text)

b0,b1=status['models']
rows='\n'.join(f"| {m['model']} | {m['loss']['training_objective']:.12f} | {m['loss']['n_valid']} | {m['loss']['n_rain']} | {m['clipping']['pre_clip_norm']:.9f} | {m['clipping']['post_clip_norm']:.9f} | 1 |" for m in (b0,b1))
cpu=status['cpu_resources']; raw_bytes=sum(r['bytes'] for r in status['raw_reads'])
write('README.md',f'''# 首次真实数据训练链路冒烟测试

本轮完成 `BOUNDED_REAL_TRAIN_SMOKE_PASS`：B0/E0、B1/E0 各一次真实更新，永久账本 `COMPLETE_SEALED`，不再执行。
这是限定工程测试，正式 Phase-B 更新为 **0**。原始数据、像元数组、模型权重和私有路径未纳入公开交付。

基线本地与 GitHub main：`{status['baseline_commit']}`；新提交身份以本目录的 Git 历史为准。
实际执行 UTC：{status['started_at_utc']} 至 {status['finished_at_utc']}；上海时间为 2026-10-10 23:52 至 23:53。

- [真实训练审计](REAL_TRAINING_SMOKE_AUDIT.md)：固定样本、次数、结构与公式。
- [梯度和优化器](GRADIENT_AND_OPTIMIZER_REPORT.md)：分组、裁剪、参数 SHA。
- [Checkpoint 事务](CHECKPOINT_TRANSACTION_REPORT.md)：两份本地工程产物及安全读取。
- [数据身份](DATA_IDENTITY_AND_ACCESS_REPORT.md)、[资源](RESOURCE_REPORT.md)、[问题](FAILURES_AND_BLOCKERS.md)。
- `final_status.json`、`DATA_ACCESS_RECEIPTS.json`、`QUOTA_RECEIPT.json` 和 `TRANSACTION_EVENTS.jsonl` 为脱敏机器收据。
- [源码身份](source_identity.json) 区分真实执行版本与执行后 PID 监控修复；准确执行源码副本在 `execution_source_snapshot/`。
- 新代码：`src/yuntapr/experimental/phase_b_v2_real_train_smoke/`。入口是一次性工程任务，正式入口始终拒绝。

最终新增静态/微型张量防护测试 **39 通过、0 失败**；实际 smoke 2 个事务通过。保留首轮失败及后续环境权限失败记录。
外部 watchdog 曾监控 venv 包装进程，不能采用其 5 MB 数字作为工作进程峰值；该修复未重跑真实 smoke。
实际进程自身 Win32 峰值工作集 {gib(cpu['peak_working_set_bytes'])} GiB，GPU 峰值 reserved {gib(max(m['cuda_peak_reserved_bytes'] for m in (b0,b1)))} GiB，均未超过本轮上限。

学习与审查顺序：`data.py` → `quota.py` → `operations.py` → `run.transaction` → `checkpoint.py` → `resources.py`/`launch.py`。
保留科学审批边界，IMERG Final 仅为回顾性监督，随机初态 loss 不作科研比较。
''')
write('REAL_TRAINING_SMOKE_AUDIT.md',f'''# 真实训练工程审计

直接研究者任务指令只授权本次 smoke；无科学协议批准事件生成，无正式 Runner 启动。
冻结 2023 Train 原排序第 0、1 行：`{status['frozen_scene_ids'][0]}`、`{status['frozen_scene_ids'][1]}`。
没有读取标签后选样、补帧或跳样。两个模型共享相同监督 SHA `{b0['supervision_sha256']}`。

| 模型 | 初态训练目标，仅工程数值 | N_valid | N_rain | 裁剪前 L2 | 裁剪后 L2 | 更新调用 |
|---|---:|---:|---:|---:|---:|---:|
{rows}

45 是两个场景上的有雨有效像元暴露数，不能解释为独立事件。两个场景全部合资格，N_valid=2×3430。
E0 固定 alpha=0.5、gamma=2、lambda_q=1：`L=(S_occ+S_qr)/N_valid`。
发生项在全部有效云南监督像元上求和；32 个固定 tau 的 log1p Pinball 先求均值，再只对真实有雨有效像元求和。
阈值是原始 FP32 雨强严格大于 FP32(0.1 mm/h)，计算图中的 q 路径为 FP64。
科学 Conditional Pinball 的定义仍是未加权 S_qr/N_rain；本轮未计算开发验证指标或给出科学改善判断。
公式源：`phase_b_v2_ablations/total.py:candidate_loss`、`focal.py:occurrence_numerator`、`pinball.py:conditional_pinball_numerator`，来源 SHA 见 `source_identity.json`。

B0 输入 `[2,1,501,501]`、B1 `[2,6,501,501]`，均为 FP32；监督 `[2,1,100,100]` FP32；独立有效/云南 mask 为 bool。
输出概率 `[2,1,100,100]` BF16，条件分位数 `[2,32,100,100]` FP64。
输出有限、严格单调、支撑下界通过；检测使用同次训练输出的 detach 视图，无额外 forward。
每模型训练 forward/backward/step 各一次，额外无梯度前向 **0**。没有完整 epoch、验证或 BEST/LAST 选择。
''')
write('GRADIENT_AND_OPTIMIZER_REPORT.md',f'''# 梯度与优化器

fresh 配对初始化使用 seed2026，同名同形状状态一致；保留 B1 原生输入初始化及零 skip，未加载历史权重。
每模型 74 个实际参数张量（骨干 70、发生头 2、分位数头 2）均有有限梯度，无断图。
本批有 45 个真实有雨有效像元，两输出头均有非零梯度；若无雨，候选损失保留连接的零分位数梯度，不重新选样。

冻结 AdamW：Conv2d kernel decay=1e-4；Conv2d bias 和 GroupNorm affine 无 decay；betas=(0.9,0.999)、eps=1e-8、foreach/fused=False。
每模型 optimizer 全新且初始 state 为空；更新后 74 份 state 的 step 均为 1、moments 为 FP32、有限且二阶矩非负。
S0 使用原 50-epoch/5228-step warmup 轨迹第一更新，LR=`{b0['lr_used']:.17g}`；scheduler.completed=1，没有完成 epoch。
裁剪阈值 5，实测前后范数见训练审计及 `final_status.json`。

| 模型 | 更新前完整状态 SHA | 更新后完整状态 SHA |
|---|---|---|
| B0 | `{b0['parameter_sha256_before']}` | `{b0['parameter_sha256_after']}` |
| B1 | `{b1['parameter_sha256_before']}` | `{b1['parameter_sha256_after']}` |

两模型均有 60/74 个参数张量的字节发生变化：骨干 56、发生头 2、分位数头 2。
所有梯度、参数和 optimizer 数值检查通过；冻结 buffers 不变。
极小第一步 LR 下部分 FP32 参数字节不变可正常出现；未用变化幅度判断科学质量，也没有二次更新验证。
''')
write('CHECKPOINT_TRANSACTION_REPORT.md',f'''# 工程 checkpoint 事务

两份独立 schema=`REAL_TRAIN_SMOKE_ENGINEERING_v1` 的 checkpoint 均保存并读取成功，只存在本轮私有临时目录。
复用旧 SyntheticStore 的原子传输步骤，返回前将提交收据标记为本轮 smoke schema；未改旧模块。
新目录以只读句柄返回的真实长路径绑定，解决 Windows 8.3 别名问题。
读取仅接受自身收据和字节；只读句柄绑定对象，检查大小/前后快照/SHA 后，由 `torch.load(BytesIO(immutable), weights_only=True, map_location='cpu')` 消费同一内容。
没有把读回状态装载到模型，没有读取历史 checkpoint。

| 模型 | 文件字节 | SHA256 | 全状态逐字段逻辑摘要匹配 |
|---|---:|---|---|
| B0 | {b0['checkpoint']['bytes']} | `{b0['checkpoint']['sha256']}` | 是 |
| B1 | {b1['checkpoint']['bytes']} | `{b1['checkpoint']['sha256']}` | 是 |

保存 model、AdamW、scheduler、Python/NumPy/CPU/CUDA RNG、seed/arm、两个样本 ID、实际文件 SHA、scaler/mask/SP04、协议/代码身份、更新前后 SHA、额度和直接指令范围。
checkpoint.progress 明确 formal_epoch=0、complete_epoch=false、validation_complete=false、formal Phase-B step=0、本模型 smoke update=1。
固定 LAST/恢复祖先不适用于这个未完成 epoch 的工程产物。`formal_restore` 无条件拒绝，禁止 warm-start、正式恢复及公开权重。

新防护测试实际注入：序列化后中断、blob 后未提交、rename lock、已有锁、截断、SHA 错误、越界收据、schema 缺失。
均按预期拒绝/保留残件；这些是微型人工 payload，未重试真实更新。
文件 fsync/原子替换不证明所有文件系统断电持久性；内容校验也不保证未来文件不变。
''')
write('DATA_IDENTITY_AND_ACCESS_REPORT.md',f'''# 数据身份与访问

本轮未重扫全量数据。引用此前 FULL_PAYLOAD_SHA_PASS 67,006 文件结果，并重新核验本次实际消费字节。
公开 2023 B0/B1 冻结 manifest 完整 SHA 与同一 M1 配对 ID 通过，样本固定于标签读取前。
直接复用 `RealAdapter`/`VerifiedReader`、B13/IMERG 读取、SP04 和 shared scaler；本轮只加两场景限制。
旧 RealBatch 的 forward-pilot 来源标签只表示解码契约的来源，本轮动作权限来自本次限定研究者指令，不是该标签或布尔值。

- 原始 payload 打开 **15 次**，均 SHA_PASS：B13 12 次、IMERG 日文件 2 次、真实云南 mask 1 次；去重 **11 文件**。
- 原始 payload 内容读取 **{raw_bytes:,} bytes**（{raw_bytes/1024**2:.3f} MiB）；B13 重叠时相和同日 IMERG 的重复读取均计费。
- 9 个公开元数据文件消费 **{sum(p['bytes'] for p in status['public_source_pins']):,} bytes**；合计受预算计费内容 **{status['accounted_content_bytes']:,} bytes**。
- 只读句柄拒绝 write/delete sharing、拒绝 reparse，保持父目录句柄；SHA、大小及对象快照通过后，解码器使用同一不可变内存字节，未二次路径打开。
- 真实 mask=3430 中心格点，SP04 100×100，valid 与 region 独立，FP32 阈值与六时相顺序通过。
- B1 帧为分析时刻前 60/50/40/30/20/10 分钟，B0 等于最新 slot5；无观测晚于分析时刻。
- 12 个场景-时相引用中，2 个文件生成时间晚于分析时刻；这不代表已验证业务可获取时间。

本轮应用范围 2024 原始文件读取=0、2025 内容/像元读取=0、历史模型 checkpoint 读取=0，无主动 2025 文件属性查询。
历史首次 2025 负面测试的路径属性访问继续为 **NOT_INSTRUMENTED**，不作系统级或追溯零访问声明。
IMERG V07 Final 是回顾性监督参考，不证明严格近实时业务延迟。
源代码、SP04 公共配置的校验读与本地 checkpoint 读写单独于原始内容计数；checkpoint 两份各约 50 MiB，未公开其数组。
''')
resource_rows='\n'.join(f"| {m['model']} | {gib(m['cuda_peak_allocated_bytes'])} | {gib(m['cuda_peak_reserved_bytes'])} | {m['forward_and_loss_seconds']:.4f} | {m['backward_seconds']:.4f} | {m['optimizer_step_seconds']:.4f} | {m['checkpoint_seconds']:.4f} |" for m in (b0,b1))
write('RESOURCE_REPORT.md',f'''# 资源与耗时

GPU `{status['cuda_admission']['name']}`，PyTorch {status['cuda_admission']['torch_version']} / CUDA {status['cuda_admission']['cuda_build']}。
执行前 CUDA free={gib(status['cuda_admission']['free_bytes'])} GiB，满足 ≥5 GiB；分模型准入也通过。
allocator 设置 6 GiB fraction cap，并逐阶段检查 max_memory_reserved；没有改模型、batch、精度或转 CPU。

| 模型 | CUDA peak allocated GiB | CUDA peak reserved GiB | forward+loss 秒 | backward 秒 | step 秒 | checkpoint 秒 |
|---|---:|---:|---:|---:|---:|---:|
{resource_rows}

实际工作进程 Win32 **peak working set={cpu['peak_working_set_bytes']:,} bytes ({gib(cpu['peak_working_set_bytes'])} GiB)**，低于 4 GiB。
peak pagefile/commit={cpu['peak_pagefile_bytes']:,} bytes ({gib(cpu['peak_pagefile_bytes'])} GiB)；它不同于物理工作集，本轮未将 commit 上限伪写为 4 GiB。
自身 Win32 计数器包含进程此前峰值，输出即使已清理对象也保留峰值。
worker 有限执行 {status['elapsed_seconds']:.3f} 秒，含启动器端到端 {driver['elapsed_seconds']:.3f} 秒，低于 1800 秒。
两场景解码与固定预处理共 {sum(r['seconds'] for r in status['decoded_scene_receipts']):.4f} 秒；逐文件 read/SHA 时间和 UTC 见收据。

**外部 watchdog 限制：**实际首次运行监控的是 venv 启动包装进程，得到 {driver['peak_sampled_child_working_set_bytes']:,} bytes，不是工作进程峰值，不能用来声称外部保护已经验证。
本轮自身 peak 工作集证明实际未越界；外部 PID 绑定已在执行后改为工作进程写入原子身份、OpenProcess 读取。
新增 PID 句柄测试通过，但完整 kill/超限联动仍 **NOT_VERIFIED**，且没有重跑真实 smoke。
计时是单次工程事务，不含多 epoch I/O 和全验证，也未消除缓存/首个 kernel 开销；不能据此估算科研吞吐或业务实时能力。
''')
write('FAILURES_AND_BLOCKERS.md', '''# 首次失败、修复与剩余阻塞

1. 首轮 36 项测试：34 通过、2 错误。原因是 Windows 临时目录 8.3 别名与只读句柄长路径不同；绑定新目录的句柄身份后修复。
2. 第二轮 37 项：36 通过、1 错误。测试夹具误用了 Linear，冻结参数分组仅接受 Conv2d/GroupNorm；换为微型 Conv2d，正式规则未改。
3. 真实 smoke 前 37/37 通过，随后唯一真实进程完成 B0/B1 各一次更新。真实事务失败=0、重试=0、额外推理=0、资源越限=0。
4. 执行后发现外部监控拿到 venv stub PID，实际 worker 峰值由自身 Win32 记录。修复 run.py/launch.py 的 PID 绑定，准确旧版本保存在源码快照；不补做真实更新。
5. 环境切换为受限模式后两次 39 项测试各有 28 个临时目录权限错误，11 项通过；Windows tempfile mode0700 ACL 不允许受限令牌写入子项。最终使用工作区内默认继承 ACL 的专用测试目录，39/39 通过。未清理他人目录，完整私有日志保留，公开脱敏日志在 tests/。

剩余：外部 watchdog 的完整停止联动未作端到端验证；真实异常路径（数据错误、CUDA OOM、AdamW 中途失败、真实 checkpoint 写失败）没有主动在这两个真实更新中注入。
人工 checkpoint 故障测试不能替代真实运行所有故障保证。
共同 Git 目录永久账本与第二 witness 阻止普通重启、改代码 SHA、改名/新目录、删除单个 witness 的重置；没有退款接口。
本地工程保护不是对恶意任意改代码或删除全部证据的安全沙箱，也不提供独立科研批准验真服务。

正式 Phase-B 仍需独立签署科学协议/统计与副作用界限、正式源码版本集成审查、真实数据权限和资源预算、首批 seed2026 六组的明确执行授权。
正式恢复额外绑定具体 LAST SHA、执行授权祖先及新的独立研究者决定。本次 smoke checkpoint 永不作为 warm-start 或恢复源。
Phase-A 科学接受范围、历史 B1 恢复治理偏差仍待研究者独立处置。
本轮完成后停止，不运行其他 seed/arm、整 epoch、B9、FinalFit 或最终测试。
''')

# Validate export before any public staging.
for p in list(OUT.glob('*.json'))+list(OUT.glob('*.jsonl'))+list((OUT/'tests').glob('*.redacted.log')):
    raw=p.read_bytes().decode('utf-8',errors='replace')
    assert not re.search(r'[A-Za-z]:[\\/]',raw), ('PRIVATE_ABSOLUTE_PATH',p.name)
print(json.dumps(dict(export_status='PASS',actual_updates=2,raw_bytes=raw_bytes,
    passed_static_tests=39,post_execution_changed_sources=changed)))
