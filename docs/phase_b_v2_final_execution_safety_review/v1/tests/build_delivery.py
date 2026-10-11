"""Create public summaries from repository evidence and artificial receipts only."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_final_execution_safety_review/v1'
NS=ROOT/'src/yuntapr/experimental/phase_b_v2_execution_watchdog_candidate'
BASE='16e3715f02615c9a6c9d86c1fdc8ee4b87651bef'


def write(name,text): (OUT/name).write_text(text.strip()+'\n',encoding='utf-8',newline='\n')


def main():
    first=json.loads((OUT/'tests/run_d07768eed92a.json').read_text())
    final=json.loads((OUT/'tests/run_6a6862278869.json').read_text())
    abrupt_files=list((OUT/'tests').glob('abrupt_exit_*.json'))
    assert len(abrupt_files)==1
    abrupt=json.loads(abrupt_files[0].read_text()); results=final['results']+[abrupt]
    assert final['failed']==0 and all(r['cleanup_verified'] for r in results)
    old=json.loads((ROOT/'docs/phase_b_v2_real_train_smoke/v1/final_status.json').read_text())
    guard=json.loads((OUT/'protected_validation.json').read_text())
    assert guard['sealed_quota_unchanged'] and guard['sealed_rows_unchanged'] and not guard['changed_preexisting_tracked_paths']
    # Compilation parses source only; never imports a model/scientific dependency.
    for path in list(NS.glob('*.py'))+list((OUT/'tests').glob('*.py')):
        compile(path.read_text(encoding='utf-8'),path.name,'exec'); ast.parse(path.read_text(encoding='utf-8'))
    source={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(NS.glob('*.py'))}
    disk=shutil.disk_usage(ROOT)
    summary=dict(tests_final_distinct=31,tests_final_failed=0,
        process_cases_final_distinct=17,artificial_launches_total=33,launch_hard_limit=40,
        launch_count_unit='Top-level artificial cases; venv stubs/workers/descendants are not separate case reservations',
        first_process_suite_tests=19,first_process_suite_automated_failed=0,
        first_suite_exit_classification_not_verified=['unexpected_exit','worker_exit_tree'],
        initial_protected_audit_failures=1,initial_protected_audit_cause='SQL tuple vs JSON list representation',
        repaired_protected_audit=guard,all_final_test_trees_empty=True,
        peak_sampled_artificial_worker_working_set_bytes=max(r['peak_worker_working_set_bytes'] for r in results),
        peak_sampled_artificial_tree_working_set_bytes=max(r['peak_sampled_tree_working_set_bytes'] for r in results),
        peak_sampled_artificial_worker_private_commit_bytes=max(r['peak_worker_private_commit_bytes'] for r in results),
        longest_case_seconds=max(r['elapsed_seconds'] for r in results),
        allocation_bytes=32*1024**2,cuda_operations=0,real_data_reads=0,optimizer_steps=0,
        repository_volume_free_bytes=disk.free,repository_volume_total_bytes=disk.total,
        source_sha256=source,run_receipt_source_sha_at_launch='NOT_RECORDED_CONTEMPORANEOUSLY',
        final_source_static_parse='PASS',utc=datetime.now(timezone.utc).isoformat())
    write('tests/test_summary.json',json.dumps(summary,indent=2))
    table='\n'.join('| '+r['case']+' | PASS | '+str(r['violation'] or 'NORMAL_COMPLETION')+' | '+f"{r['elapsed_seconds']:.3f}"+' |' for r in results)
    write('README.md',f'''# Phase-B v2 执行安全最终审查 v1

基线及本轮开始时远端 main：`{BASE}`。**WATCHDOG_SYNTHETIC_TERMINATION_PASS**；**正式执行 NOT_READY / NOT_AUTHORIZED**。

本轮只运行 stdlib 人工进程。最终 31 项不同检查通过、0 项失败，其中 17 个进程场景；开发与复核共预留/启动 33 个人工进程用例，上限 40。受控分配 32 MiB（授权上限64 MiB），最长单例 {summary['longest_case_seconds']:.3f} 秒（上限15秒）。没有运行、导入 PyTorch 或调用 GPU，没有真实数据读取、backward、optimizer.step 或历史 checkpoint 读取。

阅读顺序：[终止测试](WATCHDOG_TERMINATION_TEST.md) → [进程身份](PROCESS_IDENTITY_AUDIT.md) → [资源](RESOURCE_SAFETY_REVIEW.md) → [源码审查](FORMAL_RUNNER_CODE_REVIEW.md) → [阻塞](REMAINING_EXECUTION_BLOCKERS.md)。可编辑摘要：`FINAL_EXECUTION_SAFETY_REVIEW.tex` / 配套 PDF。

候选源码位于 `src/yuntapr/experimental/phase_b_v2_execution_watchdog_candidate/`：`winjob.Job` 是内核封闭与终止层，`watchdog.run_case` 只接受固定人工用例，`fixture` 只生成人工进程。此版本没有真实训练启动器，也没有接入旧 smoke 或 IntegratedEngine。旧 smoke 启动器的源码风险仍列出，已封存任务不可重启；本轮没有改写它或旧证据。

`protected_baseline.json` / `protected_validation.json` 核验 {guard['preexisting_tracked_count']} 个既有 src/config/docs 文件及三个封存锚点 SHA：全部不变。已有未跟踪工作保留，提交只选取本目录和新候选命名空间。

所有通过仅限人工终止与静态审查，不代表科学方案批准、真实资源稳定、业务近实时能力或正式训练许可。历史2025路径属性访问保持 NOT_INSTRUMENTED。本轮交付后停止。
''')
    write('WATCHDOG_TERMINATION_TEST.md',f'''# 受控终止测试

状态：**WATCHDOG_SYNTHETIC_TERMINATION_PASS**。使用 Windows venv 包装器及真实底层 CPython 进程，未加载模型或 GPU。Job 在 CreateProcess 时通过属性列表原子加入，未启用 breakaway。`TerminateJobObject` 停止 owned Job；保留句柄等待退出，查询 Job 活跃 PID 为零。外来 PID 不属于此 Job，拒绝后只终止自己的树。

| 用例 | 状态 | 实际结果/停止原因 | 秒 |
|---|---|---|---:|
{table}

`wrapper_exit` 的 root PID 与 worker PID 不同，root 已退出时 worker 继续受监控，正常结束收据才允许成功。`tree_timeout` 有子孙进程，时间超限后清空。`close_job` 关闭最后 Job 句柄，保留的进程句柄全部变为 signaled；关闭后无法查询已销毁 Job，因此该例 job_empty 字段为 null，不伪称查询成功。`driver_crash` 人工监控子进程调用 os._exit(17)，其内层 Job 工作进程在外层 watchdog 终止 Job **之前**已经退出，证明异常退出联动。

内存例分配并触碰32 MiB，模拟工作进程上限24 MiB，未占满系统内存；Job 另有256 MiB合计提交上限与16进程上限。该256 MiB只用于人工测试，不可套到模型训练。轮询20 ms，采样峰值不是连续时间的精确峰值。

最终 19 项主套件 + 8 项新保护检查 + 1 项 JSON/SQL 回归 + 3 项路径词法保护 = 31 PASS。最后三项用mock证明非所属目录/禁止年份/非法类型在mkdir等路径操作前拒绝，没有主动查询2025属性。16个主进程用例加1个异常监控退出，共17个不同进程场景。首轮19项自动PASS，但 unexpected_exit/worker_exit_tree 只得到笼统 MONITOR_OR_IDENTITY_FAILURE；人工审查判其退出分类 NOT_VERIFIED，修复后两例必须得到 WORKER_UNEXPECTED_EXIT。首轮原始收据 `tests/run_d07768eed92a.json` 未改写；修复套件为 `tests/run_6a6862278869.json`。

真正首次失败：保护审计 SQL返回tuple、保存JSON返回list，导致行比较误报。`tests/initial_protected_validation_failure.json` 保留 FAIL；文件SHA始终不变。修复只规范行表示，独立回归通过，未改变数据库。最终保护验证通过。

限制：当时用例收据没有同时记录执行源码SHA，明确 NOT_RECORDED_CONTEMPORANEOUSLY；当前交付 manifest 绑定最终代码，不能追溯声称首轮代码字节已被同时登记。异常内核API、系统死机、掉电、长时间驱动阻塞及真实训练树未验证。没有自动重启/退款路径；cleanup无法证明时失败、关闭Job、停止套件。
''')
    write('PROCESS_IDENTITY_AUDIT.md','''# 进程身份审计

| 项目 | 状态 | 证据与范围 |
|---|---|---|
| venv包装器 / 实际Python区分 | PASS | root与worker PID不同；从工作原子收据绑定成员，root提前退出仍监控 |
| PID + 创建时间 + 原生image绑定 | PASS | GetProcessId/GetProcessTimes/QueryFullProcessImageNameW；JSON的创建时间/image必须与内核身份一致 |
| image真实来源 | PASS | 精确本解释器/venv home的image路径哈希白名单，不信任worker自报路径；公开仅path key |
| 错PID/外来PID/错误nonce/创建时间/image | PASS | 负面拒绝；外来父进程存活并继续测试，未调用PID-only终止 |
| 登记前退出/超时未登记 | PASS | EXIT_BEFORE_IDENTITY / REGISTRATION_TIMEOUT，均有明确失败收据 |
| worker异常退出及监控句柄无效 | PASS | WORKER_UNEXPECTED_EXIT / MONITOR_OR_IDENTITY_FAILURE，Job全树清理 |
| PID复用保护 | PASS（结构审查） | 长持有内核句柄，对象不随PID复用重新绑定；没有强制诱发Windows实际PID复用 |
| 终止后无遗留测试树 | PASS | 活跃成员查询为0、保留句柄signaled；Job关闭和driver_crash例另有句柄证明 |
| 正式Runner中的身份/Job集成 | NOT_VERIFIED | 当前仅新人工候选，未修改或接入IntegratedEngine/真实入口 |

nonce仅关联本次人工消息，不代表研究者签署。启动进程先被内核封闭，工作登记后才接受资源监控；登记失败也能终止Job中所有成员。GetProcessMemoryInfo读的是实际worker持有句柄，不是5 MB启动包装器。

旧 `phase_b_v2_real_train_smoke/launch.py:25 launch` 仍有缺陷：while以包装器poll结束、OpenProcess只凭PID、taskkill未验证全树清空；`run.py` 的原子JSON只有PID和campaign。这里是 **FAIL（不得复用于正式运行）**，不抹去历史失败，也不重跑封存smoke。最小未来变更是另批启动器版本接入受审Job后端、登记身份/完成收据与独立额度，不重启历史任务。

实现依据：[Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[创建时加入Job的属性列表方法](https://devblogs.microsoft.com/oldnewthing/20230209-00/?p=107812)、[AssignProcessToJobObject / 子进程继承及nested jobs](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject)。适用本机Windows；其他系统和不支持Job属性的环境拒绝运行，不作降级。
''')
    write('RESOURCE_SAFETY_REVIEW.md',f'''# 资源安全审查

本表真实smoke数字仅引用旧 `docs/phase_b_v2_real_train_smoke/v1/final_status.json` 与 RESOURCE_REPORT.md，本轮没有测量GPU或访问观测文件。

| 项目 | 状态 | 实际证据与局限 |
|---|---|---|
| 两次smoke CUDA allocated / reserved | PASS（历史有限事务） | B0 2,834,127,872 / 3,416,260,608 bytes；B1 2,858,972,672 / 3,435,134,976 bytes；非设备全局峰值 |
| smoke CUDA admission / reserved上限 | PASS（历史+静态） | free 7,283,408,896 bytes≥5GiB；allocator fraction与阶段reserved守卫6GiB；本轮未调用CUDA |
| CPU working set / commit区分 | PASS | 实际worker peak working set 2,453,544,960 bytes；peak pagefile/commit 7,416,758,272 bytes，不能把后者写成工作集或忽略系统commit压力 |
| 外部CPU/time终止 | PASS（人工） | 真worker句柄；模拟24MiB/1.8秒阈值，清空Job；不代表真实GPU进程终止已复测 |
| 本轮人工采样资源 | PASS | worker WS峰值 {summary['peak_sampled_artificial_worker_working_set_bytes']} bytes；tree WS {summary['peak_sampled_artificial_tree_working_set_bytes']} bytes；worker private commit {summary['peak_sampled_artificial_worker_private_commit_bytes']} bytes；受控分配32MiB |
| 当前仓库卷可用空间 | PASS（时点测量） | {disk.free} bytes可用 / {disk.total} bytes总量；仅仓库卷，非未来正式checkpoint卷承诺 |
| checkpoint空间保护 | PASS（静态） | Store.save预留2×tensor bytes+64MiB且payload上限256MiB；SmokeStore.save有512MiB可用空间检查；无法保证写入期间没有其他进程耗尽空间 |
| 正式资源许可与全过程容量 | NOT_VERIFIED | 未确定真实加载worker/cache、exact-score SQLite、每轮checkpoint保留与系统commit/GPU其他使用者的预算 |
| 不足时修改模型/batch/精度回避 | PASS（源码审查） | 现有准入拒绝与异常停止；本轮人工进程只改模拟限额，无模型配置 |
| 长程稳定性/热降频/驱动挂起 | NOT_VERIFIED | 本轮最长单例{summary['longest_case_seconds']:.3f}秒；两次smoke不能证明九轮稳定 |
| 掉电/文件系统目录持久性 | NOT_VERIFIED | fsync +原子replace / SQLite FULL不等于在所有存储栈上抗掉电；未故意掉电或填满磁盘 |

正式首批六组计划是282,312更新，不按两个smoke耗时外推总耗时。未来独立批准资源测量、正式存储卷/保留方案、commit与CUDA admission、正式watchdog参数及停止策略之后再验收。真实GPU回收、驱动卡死时的Job响应、系统级文件访问零记录尚无本轮证据。
''')
    write('FORMAL_RUNNER_CODE_REVIEW.md','''# 正式候选源码最终审查（静态；无模型实例化）

表中路径统一在 `src/yuntapr/experimental/` 下。PASS只指审查到的限定逻辑或历史证据，正式运行均未执行。本轮未改动以下源码。

| 接口与定位 | 状态 | 结论/最小待审批差异 |
|---|---|---|
| formal_integration_candidate/access.py:15 RealDataAdapter.open_scene/open_manifest/open_artifact；:9 RejectingAuthority | PASS（阻断）；正式能力NOT_VERIFIED | 任何路径操作前拒绝。独立真实approval事件验证服务不存在，不能改bool打开；未来另批版本及connector |
| real_forward_pilot/adapter.py:41 VerifiedReader.authenticate、:67 read、:116 view | PASS（静态及旧限定证据） | 词法拒绝→固定registry→只读句柄→hash→immutable bytes→同字节解码。仅pilot计划/预算，不能直接当全量正式loader |
| formal_integration_candidate/engine.py:27 IntegratedEngine.__init__、:51 _batch、:56 train_epoch、:77 validate_and_commit | NOT_VERIFIED（正式全量集成未实现） | 硬编码seed2026/E0与2/2人工Profile；一个epoch只有一个人工batch，验证仅两个固定日期。需要独立正式实现真实batch iterator、10455/10501覆盖、tail1/5、真实日期、所有预注册arm/seed与全程身份。不得“移除if”直接启用 |
| ablations/config.py get_config；focal.py occurrence_numerator；pinball.py conditional_pinball_numerator；total.py candidate_loss | PASS（静态/旧测试） | E0(.5,2,1)、E1(.5,0,1)、E2(.5,2,2)。BCEWithLogits；gamma0仍有alpha；FP32 rate>.1；32tau均值→雨有效像元求和；FP64 log空间，无修补/排序 |
| ablations/metrics.py:38 common_validation_sums；formal_integration_candidate/metrics.py:50 add、:109 summary | PASS（定义审查）；正式数据规模NOT_VERIFIED | 共同Core始终E0 gamma2/FP64且lambda1，S_q未加权/Nrain；score精确二进制分组保留ties，不用十箱替代AUROC/AP；32覆盖、七雨强层、上尾、UTC块。未来实际scratch预算与整体身份需验收 |
| integration/initialization.py:48 fresh_paired_models；formal_runner_candidate/protocol.py:89 fresh_models_without_observational_artifacts | PASS（旧合成/烟测+静态） | 同名同形状共享参数精确配对；保留B1输入差异，不载历史权重。正式上下文需独立核验整个依赖source、数据/scaler身份和RNG，而不是读取旧smoke产物 |
| formal_integration_candidate/state.py:13 B9State.begin/finish_train/validate/commit_last/endpoint/check_restore | PASS（候选状态约束）；正式事务NOT_VERIFIED | 固定9终点、不采用BEST，完整验证才提交LAST，pending不恢复、不回滚预算；已有LOGICAL_B9不等于真实九轮消费 |
| formal_integration_candidate/state.py:97 ActualQuota.perform；real_train_smoke/quota.py:78 SmokeQuota | PASS（范围内防重复）；正式额度服务NOT_VERIFIED | 前者固定四次人工额度；后者封存两次真实smoke。不能扩展/重置复用作正式run授权。新正式额度必须绑定独立事件与运行矩阵及跨进程原子预留 |
| formal_integration_candidate/checkpoint.py:35 Store.read → runner_candidate/checkpoint.py:76 SyntheticStore.read | FAIL（若用于正式恢复） | 当前继承路径先resolve/stat/hash，再torch.load(path)重新打开；存在SHA与反序列化字节的TOCTOU窗口，且base reader在外来拒绝前resolve。最小另批修复：词法/根范围先拒绝、只读句柄绑定、不可变同字节SHA+weights_only反序列化；复用smoke/checkpoint.py:50 SmokeStore.read的模式而非历史权重 |
| formal_integration_candidate/checkpoint.py:49 validate、engine.py:106 restore_completed_last | PASS（人工字段校验）；正式审批NOT_VERIFIED | 当前只允许自己的人工last_reference；形式化恢复必须额外绑定具体LAST SHA与原授权祖先、独立研究者新决定，未接验真接口 |
| formal_integration_candidate/protocol.py:26 code_sha、:58 identity | NOT_VERIFIED（完整发布身份） | code_sha仅哈希该命名空间，source_commit是候选来源常量，不覆盖复用loss/initializer/reader所有依赖与实际release HEAD。正式版本需完整依赖SHA清单+实际发布commit、审批绑定 |
| formal_integration_candidate/storage.py:25 Workspace.__init__ | NOT_VERIFIED（当前受限环境适用） | 使用mkdtemp；旧交付记录见smoke最终状态中受限临时目录DACL失败。本轮人工目录使用继承ACL的mkdir。另批在正式存储位置验证建目录、读写/锁/fsync，不默认旧workspace可写 |
| real_train_smoke/launch.py:25 launch | FAIL（不能复用旧watchdog） | wrapper寿命当监控寿命、PID缺创建身份、taskkill未检查树清空。新Job后端通过人工验证，但真实入口集成尚未发生；历史smoke不可重启 |

数学复核：训练 `L=(S_occ(gamma)+lambda_q*S_q)/N_valid`；统一Core `(S_occ(gamma=2,FP64)+S_q)/N_valid`；条件Pinball `S_q/N_rain`；tau_i=(i-.5)/32，tau32=.984375；雨标签由原始float32参考值严格>.1定义。Nrain=0报告不可估计，不能作为零技能。科学成功/非劣效阈值与多重比较均不在本轮自动判定。

优先级：正式checkpoint同字节读取与启动树封闭是P1；全量loader/权限/预算/资源/版本身份是进入正式运行的必需门槛。此处只给最小修复建议，没有应用未批准的正式源码差异。
''')
    write('REMAINING_EXECUTION_BLOCKERS.md','''# 剩余执行阻塞

最终工程结论：人工 watchdog 终止 PASS，**正式 Phase-B 执行 NOT_READY / NOT_AUTHORIZED**。

| 阻塞 | 状态 | 必须由研究者新决定/许可的范围 |
|---|---|---|
| 科学协议与统计定位 | NOT_VERIFIED（未批准） | E0/E1/E2×B0/B1×2026/27/28、D1/Q1/N0/I3/B9/S0/V0；M-C仍推荐未签，2024仅开发探索；无依据效应/副作用/功效保留未定 |
| 正式源码集成与审查接受 | NOT_VERIFIED | 正式版本接入已测Job后端、真实loader/完整epoch/validation、checkpoint同字节读取、全依赖身份；本轮候选只能人工输入 |
| 真实数据权限与防火墙 | NOT_VERIFIED（本轮禁止） | 新的独立精确2023/2024范围与同次SHA消费许可；既有全量SHA不保证未来字节不变；不得复用smoke额度或打开2025 |
| 审批验真/原授权祖先/正式更新账本 | NOT_VERIFIED | 独立可核验的研究者批准事件及验真基础设施；真实资源、协议/code/data身份和run范围绑定；每次恢复另批具体LAST SHA |
| 资源与长期稳定 | NOT_VERIFIED | GPU/CPU工作集+系统commit/磁盘/metrics scratch/保留/耗时与停止方案；当前人工256MiB Job配置绝不能用于模型 |
| 首批seed2026六组实际执行 | NOT_VERIFIED（未授权） | 上述门槛满足后另批6×9×5228=282312更新；54次全验证、70902验证batch。方案/代码通过不等于执行授权 |
| 历史B1恢复治理偏差 | NOT_VERIFIED（未追认） | 独立处置，保持NOT_GRANTED；BEST早于恢复不能替代研究者批准 |
| 业务近实时和历史2025系统级访问 | NOT_VERIFIED | 回顾性因果观测定位A仍候选；无传输/入库/业务回放证据；历史2025路径属性访问NOT_INSTRUMENTED不能追溯归零 |

既有两次smoke账本及witness SHA/行保持不变，COMPLETE_SEALED，预留/进入/返回仍各2；本轮新增真实/正式优化器更新均0。沒有自动派生下一任务、自动恢复、模型实验或补样。
''')
    state=dict(overall_status='WATCHDOG_SYNTHETIC_TERMINATION_PASS',formal_engineering_readiness='NOT_READY',
        baseline_commit=BASE,local_and_remote_baseline_verified=True,final_tests_passed=31,final_tests_failed=0,
        artificial_launches_total=33,artificial_launch_hard_limit=40,remaining_test_processes=0,
        prior_tests_reexecuted=False,synthetic_or_real_optimizer_steps_this_task=0,
        real_data_reads_this_task=0,pytorch_imports_this_task=0,gpu_operations_this_task=0,
        historical_checkpoint_reads_this_task=0,initial_audit_failure_preserved=True,
        historical_artifacts_and_sealed_quota_unchanged=True,
        V2_PHASE_B_AUTHORIZED=False,FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED=False,
        RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=True,FORMAL_PHASE_B_OPTIMIZER_STEPS=0,
        HISTORICAL_RECOVERY_RATIFICATION='NOT_GRANTED',
        **{'2025_PIXELS_READ':0,'historical_2025_path_attributes':'NOT_INSTRUMENTED'},
        new_raw_path_queries=0,access_claim_scope='Source/stdlib-process audit; not system-wide telemetry',
        scientific_success='NOT_AUTHORIZED_OR_ESTABLISHED',
        final_commit_identity='Resolve git log -- this directory; exact SHA reported after push',
        source_sha256=source,summary='tests/test_summary.json',stopped_at_approval_boundary=True)
    write('final_status.json',json.dumps(state,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k not in {'source_sha256','repaired_protected_audit'}}))


if __name__=='__main__': main()
