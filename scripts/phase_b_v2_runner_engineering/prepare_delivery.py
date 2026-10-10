"""Source-bound text-only engineering delivery; does not import a model/runner."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/phase_b_v2_runner_engineering/v1"
CODE = ROOT / "src/yuntapr/experimental/phase_b_v2_runner_candidate"
BASELINE = "8958745558ee0a1a2928454ccf894287d8cbfbe9"


def write(name: str, value: str) -> None:
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value.strip() + "\n")


def dump(name, value):
    write(name, json.dumps(value, ensure_ascii=False, indent=2))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = json.loads((OUT / "source_identity.json").read_text(encoding="utf-8"))
    for entry in source["inherited_files"]:
        assert sha(ROOT / entry["path"]) == entry["sha256"], entry["path"]
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip() == BASELINE
    assert not subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT).strip()
    paths = sorted(CODE.glob("*.py")) + sorted((ROOT / "tests/phase_b_v2_runner_candidate").glob("*.py"))
    paths += sorted(Path(__file__).parent.glob("*.py"))
    for p in paths:
        ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    # No protected formal source imports the new namespace.
    formal_imports = [str(p.relative_to(ROOT)) for p in (ROOT / "src/yuntapr/training").glob("*.py")
                      if "phase_b_v2_runner_candidate" in p.read_text(encoding="utf-8")]
    assert not formal_imports
    digest = hashlib.sha256()
    for p in sorted(CODE.glob("*.py")):
        digest.update(p.name.encode("ascii")); digest.update(p.read_bytes())
    code_sha = digest.hexdigest()
    # Preserve complete original failures locally; publish scrubbed equivalents.
    originals = OUT / ".local/raw_test_logs"
    originals.mkdir(parents=True, exist_ok=True)
    for p in sorted((OUT / "tests").glob("*")):
        if p.suffix not in {".log", ".xml"}:
            continue
        shutil.copy2(p, originals / p.name)
        text = p.read_text(encoding="utf-8")
        for value in (str(ROOT), ROOT.as_posix(), str(ROOT).replace("\\", "\\\\")):
            text = text.replace(value, "<REPOSITORY>")
        text = text.replace("C:\\Users\\chenerxiao", "<USER_HOME>")
        # XML must remain parseable after substitution.
        if p.suffix == ".xml":
            text = text.replace("<REPOSITORY>", "REPOSITORY").replace("<USER_HOME>", "USER_HOME")
        p.write_text(text, encoding="utf-8")
    attempts = []
    for p in sorted((OUT / "tests").glob("*_attempt_*.xml")):
        suite = ET.parse(p).getroot().find("testsuite")
        attempts.append({"path": p.relative_to(ROOT).as_posix(), **{k: int(suite.attrib[k]) for k in
                         ("tests", "failures", "errors", "skipped")}})
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT / "tests").glob("*_synthetic.json"))]
    assert len(cases) == 6 and all(c["status"] == "PASS" for c in cases)
    ledger = json.loads((OUT / ".local/synthetic_checkpoint_workspace/task_step_ledger.json").read_text(encoding="utf-8"))
    assert sum(ledger["completed"].values()) == sum(ledger["reserved"].values()) == 12
    assert ledger["FORMAL_OPTIMIZER_STEPS"] == 0
    assert all(len({c["initial_sha"] for c in cases if c["model"] == model}) == 1 for model in
               ("B0_MATCHED_V2", "B1_V2"))
    flags = {k: source[k] for k in ("V2_PHASE_B_AUTHORIZED", "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED",
             "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED", "HISTORICAL_RECOVERY_RATIFICATION", "2025_RAW_ACCESS", "2025_PIXELS_READ")}
    dump("tests/step_ledger_public.json", ledger)
    dump("tests/final_source_identity.json", {"candidate_code_sha": code_sha, "files": [
        {"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)} for p in paths]})
    dump("tests/static_audit.json", {"scope": "SYNTHETIC_ENGINEERING_ONLY", "protected_files_verified": 333,
         "protected_diff_empty": True, "formal_imports_new_namespace": formal_imports,
         "new_python_files_ast_valid": len(paths), "candidate_code_sha": code_sha, "steps": ledger,
         "18_run_plan_budget": {"updates_per_epoch": 5228, "updates_per_run": 47052, "total": 846936,
            "seed2026_six_run_budget": 282312, "validation_batches_per_epoch": 1313}, **flags})
    dump("tests/attempt_summary.json", {"attempts": attempts,
         "unique_final_passes": {"CPU": 75, "CUDA": 8}, "actual_optimizer_steps": 12,
         "initial_test_failures": 1, "later_collection_errors": 1,
         "current_unresolved_test_failures": 0, "prior_91_CPU_6_CUDA_not_reexecuted": True,
         "extra_cuda_final_code_checks": "2 no-update state tests repeated only after provenance/guard edits"})

    write("README.md", """# Phase-B v2 独立 Runner 工程候选 v1

状态：SYNTHETIC_ENGINEERING_ONLY / RESEARCHER_DECISION_REQUIRED。

本轮基线为 8958745558ee0a1a2928454ccf894287d8cbfbe9。本候选仅内部生成 batch=2 的人工张量；没有真实数据入口、正式训练命令或审批开关。

- 源码：src/yuntapr/experimental/phase_b_v2_runner_candidate/，7 个独立模块。
- 测试：tests/phase_b_v2_runner_candidate/；本轮新增 75 CPU、8 CUDA 唯一检查通过。12 次实际合成 AdamW 更新，正式更新 0。旧 91 CPU、6 CUDA 检查未重跑。
- 首先阅读 FINAL_CODE_REVIEW_HANDOFF.md，再阅读 RUNNER_ARCHITECTURE_AND_STUDY.md。
- 数学和评价：E0_E1_E2_CONSISTENCY_REPORT.md。
- 事务与故障：TRANSACTION_AND_FAULT_REPORT.md、TEST_AND_FIX_RECORD.md、tests/。
- 资源：RESOURCES_AND_LIMITS.md；审批：RESEARCHER_DECISION_REQUIRED.md。
- 中文审查文档：RUNNER_ENGINEERING_REVIEW.tex / .pdf；源文件可人工修改。
- manifest.json 记录交付及来源 SHA；publication_receipt.json 在实际推送后追加，不作为授权。

成功仅支持工程接口判断；概率校准、q32 欠覆盖、上尾物理可信性及历史 B1 恢复治理问题均未由本轮解决。
""")
    write("RUNNER_ARCHITECTURE_AND_STUDY.md", """# 源码结构与学习顺序

所有路径均以仓库为根；新命名空间为 src/yuntapr/experimental/phase_b_v2_runner_candidate/。

|顺序 / 文件|重点函数与用途|本人审查要点|
|---|---|---|
|1 identity.py|identity、verify_sources、candidate_plan、reject_formal_execution|18 个封闭身份；333 个冻结来源；本候选源码摘要；审批状态不可升级|
|2 optimizer.py|new_adamw、clip_and_check、PrefixSchedule、check_finite|冻结分组；clip=5；先赋 LR 后 step；step 成功后提交调度计数|
|3 safety.py|install_guard、checkpoint_io、StepLedger.read/_mutate/perform|contextvars 限制操作作用域；独占锁；预算先预留并落盘，失败不退回|
|4 rng.py|capture、validate、restore|Python/NumPy/CPU/CUDA RNG；weights_only 可读类型；本地 generator 校验不修改全局 RNG|
|5 checkpoint.py|SyntheticStore.save/read、validate_payload|SHA 校验先于反序列化；全字段校验先于恢复；部分写入不能当作提交|
|6 runner.py|SyntheticRunner.__init__、empty_rain_gradient_check、update_once、evaluate_synthetic、save/restore|只能内部造数据；双头梯度；FP64 共同评价；恢复失败后 poisoned|
|7 __init__.py|SCOPE|明确人工合成工程用途|

主要张量：B0 输入 [2,1,501,501]、B1 [2,6,501,501]，FP32；参数 FP32，骨干和发生头在 BF16 autocast 下执行；参考 [2,1,100,100] 为 FP32；32 分位数 [2,32,100,100] 为 FP64。人工掩膜每场景含 3430 个格点，用于接口计数，不能代表冻结云南地理分布。

Python 学习提示：dataclasses.replace 保留合成身份只替换无雨 rate；with 管理临时上下文；try/finally 保证释放锁和 contextvars；raise 中止事务而不修补参数。torch.no_grad/inference_mode 用于状态与评价；训练损失的 backward 构建参数梯度；zero_grad(set_to_none=True) 清除上次梯度；AdamW.step 只在额度账本批准的本轮合成上下文中调用。

不要把 optimizer 的权重衰减视为 Pinball 权重。无雨批次的条件头仍连接计算图、梯度为零；若以后允许其执行 AdamW，已有动量或权重衰减仍可能改变参数。本轮无雨检查只 backward、不 step；12 次实际 step 都使用混合人工参考。

练习：解释 gamma=0 为什么仍有 alpha=0.5；手算梯度 [6,8] 被裁剪到近似 [3,4]；解释 LR 更新 1 为 1e-4/5228；找出评价路径中为何没有 lambda_q；解释为何恢复 RNG 不恢复本轮额度账本。

详细损失教学继续使用此前 implementation/v1 的 FOCAL、PINBALL、TOTAL walkthrough，本轮不复制或改写。
""")
    write("E0_E1_E2_CONSISTENCY_REPORT.md", r"""# E0/E1/E2 合成数学一致性

来源：phase_b_v2_ablations/config.py、focal.py、pinball.py、total.py；正式共同评价来自 training/phase_a_validation_v2.py:LogDomainValidation.add/report。来源 SHA 见 source_identity.json。

|臂|alpha|gamma|lambda_q|
|---|---|---|---|
|E0|0.5|2|1|
|E1|0.5|0|1|
|E2|0.5|2|2|

有雨标签先在原 FP32 参考域严格比较 0.1 mm/h，不先转 FP64。固定 tau_i=(i-0.5)/32；Pinball 在 log1p(mm/h) 的 FP64 分位数路径中先对 32 tau 平均，再对有雨有效像元求和。不进行 expm1。

$$
L_{train}=rac{S_{occ,gamma}^{FP32}+lambda_q S_{qr}^{FP64}}{N_{valid}},qquad
L_{common}=rac{S_{occ,gamma=2}^{FP64}+S_{qr}^{FP64}}{N_{valid}},qquad
L_{CPB}=rac{S_{qr}^{FP64}}{N_{rain}}.
$$

共同评价重新用 FP64 logit 计算 gamma=2 的发生分子，不能直接复用训练 E0 的 FP32 分子。E1/E2 的训练 objective 不等于共同科学 Core；lambda_q 仅乘训练分子一次。

6 个模型×臂事务均检查 N_valid=6860、未加权分子、固定目标组合、参数有限性和双头/骨干参与更新；重放得到逐值相同的训练记录和共同评价。每模型三臂的 fresh 初始化 SHA 相同。数据仅为内部人工张量，未观察任何新的真实 Brier、AUROC、AP 或降水性能。

E0 兼容范围：复用已验证候选数学实现、冻结真实 v2 模型和冻结 FP64 共同评价；加入 AdamW 后合成路径可更新并恢复。历史 Phase-A loss/模型/训练入口未修改。本轮没有重新执行先前完整 loss 数值/二阶梯度对照，也未证明真实实验结果改善。
""")
    write("TRANSACTION_AND_FAULT_REPORT.md", """# Checkpoint 事务与恢复

schema=SYNTHETIC_B9_V0_CANDIDATE_v1，实际文件只存在本轮 .local/synthetic_checkpoint_workspace/session_* 临时目录，不发布任何合成权重。

包含 model、AdamW state、S0 scheduler、Python/NumPy/CPU/CUDA RNG、seed、arm、模型、来源 commit、冻结来源 SHA、候选源码 SHA、protocol SHA、initial SHA、人工数据角色及完成边界。formal_epoch=0、FORMAL_OPTIMIZER_STEPS=0；proposed_epochs/endpoint=9 仅为待审批候选字段。FRESH0 的 synthetic_updates=0；LAST1 只表示一个人工微循环完成，不能宣称完整 2023/2024 epoch 或 V0 科学终点评价完成。

原子候选：独占创建锁 → 临时 blob 序列化 → flush/fsync → 文件 SHA → rename blob → flush/fsync 并 rename receipt → 返回可恢复 reference。读取时先核对 byte size/SHA，再 weights_only=True 反序列化。保存未提交不返回 reference，禁止覆盖。原子 rename 和注入测试不证明 Windows 断电后目录持久性；正式集成仍需独立验证。

|故障 / 风险|实际测试结果|
|---|---|
|序列化后中断、blob 提交后中断|无 commit receipt；保留 part/orphan；不能恢复|
|rename 文件锁异常、预存外部锁|拒绝保存；不删除外部锁|
|文件截断、byte 修改、receipt SHA 错|在反序列化前拒绝|
|model/optimizer 缺失、错误 seed/arm/epoch/source/protocol/code SHA|完整校验拒绝；真实 B0/B1 恢复负面测试证实 live state 不变|
|AdamW moment 缺失/形状/dtype/NaN/Inf/负二阶矩/step/LR 错|纯合成元数据校验拒绝|
|train/validation 边界不完整、未知字段|拒绝保存或恢复|
|apply 阶段注入异常|runner poisoned；后续 update 拒绝；无自动重试|
|FRESH0 重放、完成 LAST1 恢复|6 个完整模型事务的 model/optimizer/scheduler/RNG SHA 完全一致|

恢复不恢复 task_step_ledger，故无法用 checkpoint 回滚获得额外合成额度。当前 synthetic_updates 最多 2；完整 B9 正式 runner 的 epoch 事务、验证 10501 样本完成证明、真实 LAST 祖先与独立批准均尚未实现。
""")
    resource_lines = ["# 实际资源与未测量项", "", "RTX 5060 Laptop，8 GiB；BF16/FP32/FP64 冻结路径，batch=2，完整 501×501 架构。数值来自 tests/*_synthetic.json。", "",
                      "|模型 / 臂|峰值 allocated MiB|峰值 reserved MiB|一次更新+评价秒|整项秒|", "|---|---|---|---|---|"]
    for c in cases:
        resource_lines.append(f'|{c["model"]} / {c["arm"]}|{c["peak_cuda_allocated_bytes"]/2**20:.2f}|{c["peak_cuda_reserved_bytes"]/2**20:.0f}|{c["update_plus_evaluation_seconds"]:.3f}|{c["total_case_seconds"]:.3f}|')
    resource_lines += ["", "峰值统计包含 fresh 初始化、无雨 backward、两次混合更新、合成验证、checkpoint 和恢复。单次更新+评价计时以 CUDA synchronize 包围。整项时间包含首次库启动等开销；共用 GPU 的其他应用不计入 PyTorch allocated/reserved。", "",
                      f'FRESH blob约 {cases[0]["fresh_checkpoint_bytes"]/2**20:.2f} MiB，含模型但无 AdamW moments；LAST blob约 {cases[0]["last_checkpoint_bytes"]/2**20:.2f} MiB，含 AdamW/RNG。本轮实际最大值和全部 byte 数见每项 JSON。', "",
                      "构造前资源门槛为主机可用≥8 GiB、CUDA free≥5 GiB、工作磁盘≥1 GiB。step 前释放未使用 allocator cache 再测 free，不改 batch、结构或精度。没有资源不足跳过项。", "",
                      "这些是人工固定输入的短程测试，未测真实 I/O、数据解码、多个 epoch、验证 batch=8 全流程、缓存、长期显存碎片、磁盘容量增长、热降频或完整正式耗时。正式执行前仍需独立授权的资源/preflight 测量；不得用本轮秒数直接预测 846936 次正式更新的耗时。"]
    write("RESOURCES_AND_LIMITS.md", "\n".join(resource_lines))
    write("FORMAL_EXECUTION_BLOCK_AUDIT.md", """# 正式执行阻断审查

- 仅 SyntheticRunner 内部 make_synthetic_pair；无外部 batch、真实路径、DataLoader 或训练 epoch loop。
- start_formal/reject_formal_execution 无条件抛 PermissionError；bool、APPROVED 字符串、JSON 与 Git commit 均不起作用。
- 真实历史 checkpoint 及原始数据扩展名、含 2025 的访问、未登记 CSV 被进程审计拒绝。唯一 CSV 例外是 SHA 已核验的已发表元数据；合成 .pt/.part 只允许当前专用 store 上下文。
- 标准 optimizer 的直接 step 被阻断；只有账本预留成功的当前 AdamW 事务调用原始实现；6 个闭合模型×臂各≤2，任务总数≤12。
- formal 训练源码未导入候选 namespace；333 个冻结/历史来源全部 SHA 不变。
- step/checkpoint 失败不自动重试、换 seed、改参；恢复 apply 异常使 runner 停用。

保护范围是合作式候选 Python 进程的工程防误用，不是抵御任意恶意 Python/系统管理员的安全沙箱。发布此代码并未产生任何真实训练能力或授权。真实接入必须另建正式集成版本，进行本人审查与独立许可，不能靠修改一个布尔值启动。

V2_PHASE_B_AUTHORIZED=false；FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED=false；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED；2025_RAW_ACCESS=0；2025_PIXELS_READ=0。
""")
    write("TEST_AND_FIX_RECORD.md", """# 实际测试、失败与修复

本轮唯一检查：75 CPU + 8 CUDA 全部有通过记录，未解决失败 0。执行日志保留每次尝试；重复尝试不增加唯一检查数。12 次真实合成 AdamW.step，FORMAL_OPTIMIZER_STEPS=0；mocked dispatch 不调用原 AdamW，不计更新。

1. cpu_attempt_001：22 passed、1 failed。Windows 在锁句柄仍打开时不能 unlink。修复为独占创建后先 close，再 finally unlink；checkpoint 和账本两处同时修复。失败文件及初次 part/lock 留在本轮私有临时目录。
2. cpu_attempt_002：56 passed。含配置、LR、解析 clipping、额度、RNG、I/O、完整性与故障矩阵。
3. cuda_attempt_001：6 passed，12 actual synthetic steps。每模型×臂一次混合更新和一次 FRESH0 重放；额外无雨 backward 不 step。出现一次 requires_grad scalar 转换 warning，后续改为 detach 后读取，未更改数学。
4. hardening_attempt_001：3 CPU + 2 CUDA passed，0 steps；绑定候选源码 SHA，真实对象的恢复拒绝和 poisoned 检查。
5. final_static_attempt_001：14 passed。增加 AdamW moments 的元数据边界及其他 optimizer 阻断。
6. final_static_attempt_002：收集阶段 1 error、0 tests executed。追加 fsync 时缩进错误，未执行更新；修正后 final_static_attempt_003：16 passed。
7. final_cuda_state_attempt_001：最终候选源码身份的 2 个无更新 CUDA 恢复检查通过；为源码/guard 变化后的针对性复核，没有重新执行 12 次 step。

最终源码在 checkpoint 身份字段、额度持久化、guard、dtype 校验和 warning 处理处比首次 CUDA 更新版本更严格。executed_source_before_hardening.json 保留实际完成更新时的文件摘要；final_source_identity.json 保留最终摘要。最后的无更新 CUDA 检查与 CPU dispatch spy 校验覆盖这些追加保护。受硬上限约束，最终源码没有再次完整重跑优化器更新；不把分阶段结果伪称为同一源码的一次全套运行。

完整原始日志保存在 .local/raw_test_logs；公开 log/XML 仅替换机器路径，不改测试结果。JSON、XML、stdout 均保留真实次数和失败原因。以前 91 CPU / 6 CUDA 及既有边界/loss 测试未重跑。
""")
    write("RESEARCHER_DECISION_REQUIRED.md", """# 独立研究者待决事项

所有项目均 RESEARCHER_DECISION_REQUIRED；没有代填批准结论。D01/D02 是初步科学讨论，不是签署。下面的统计选项来自既有 preregistration/v1 的 METRICS_AND_GUARDRAILS、STATISTICAL_ANALYSIS_PLAN 和 RESEARCHER_APPROVAL_CHECKLIST；本轮未据合成表现选择阈值。

|事项|候选选择与利弊|依赖 / 未建立字段|
|---|---|---|
|1 E0/E1/E2 科学范围|固定 gamma / lambda 单因素、B0/B1 分别报告；仅2024开发探索|Phase-A接受范围、H-O/H-Q正式协议未签署|
|2 Brier 最小改善|绝对 Brier 差便于统一解释；相对改善依赖 E0 基准|数值 NOT_YET_ESTABLISHED；由应用价值和未来独立证据支持，不以当前点估计倒推|
|3 q32 覆盖误差|abs(coverage-0.984375) 的百分点下降；或预定误差容忍区间|数值 NOT_YET_ESTABLISHED；仅覆盖改善不足以排除过宽分布|
|4 副作用界限|Conditional Pinball用原log1p损失单位或相对增幅；AUROC/AP绝对下降|三个独立容忍界限 NOT_YET_ESTABLISHED；同时查看强雨分层、全部tau、span/上尾|
|5 多重比较|Holm：需有效p值和预定检验家族；配对max-stat：保留相关但需成立的重抽样假设；仅探索效应与区间：不作确认性显著结论|方法/家族/效应界限未选；35日期块不能解决跨周相关和季节非平稳；功效 NOT_YET_ESTABLISHED|
|6 历史 B1 恢复|独立处置治理偏差，分别记录技术证据与研究者判断|不得把 BEST9 早于恢复阶段或合成通过视为追认|
|7 正式 Runner 集成|审查本候选后另做正式版本，接入审计授权服务和执行入口|正式 loss/runner 集成许可未授予|
|8 真实数据 preflight|仅经独立许可核对2023/2024身份、资格、顺序、scaler、mask|本轮没读真实数据；2025保持封存|
|9 资源预算|预定GPU、磁盘、运行窗口、异常停止与保存策略|真实I/O/耗时/存储尚未测；18运行846936更新是计划非执行|
|10 首批seed2026六组|固定D1/Q1/N0/B9/S0/V0，不据中途表现改规则；以后独立许可补齐其他seed|282312计划更新；六组正式执行许可未授予；一个seed不构成完整多种子证据|

真实 LAST 恢复还必须绑定具体文件 SHA、原始授权祖先、完成 epoch/验证边界并由研究者独立批准。合成 checkpoint 恢复仅验证状态接口，绝不授予正式恢复权。
""")
    write("FINAL_CODE_REVIEW_HANDOFF.md", """# 本人代码审查与正式集成前交接

现在可以审查候选工程；正式训练仍不能启动。

1. 配置：phase_b_v2_ablations/config.py:get_config/RunSpec/learning_rate_prefix，以及 runner_candidate/identity.py。核对 E0=(2,1)、E1=(0,1)、E2=(2,2)，alpha=0.5，三个seed，18运行，禁止warm-start。
2. 数学：phase_b_v2_ablations/focal.py:occurrence_numerator、pinball.py:conditional_pinball_numerator、total.py:candidate_loss/combine_numerators。核对 FP32>0.1、32tau平均、FP64、训练分母N_valid、科学条件分母N_rain。
3. 精度与双头：quantile_v2/heads.py:ProbabilityHeadsV2.forward、parameterization.py:normalized_monotonic_quantiles；原 33 raw channels → 32 quantiles、epsilon1e-4不改、BF16发生/FP64分位数边界。
4. 更新：runner_candidate/optimizer.py 与 runner.py:update_once。核对正式冻结 parameter_groups、AdamW参数、clip=5、LR在step前赋值、成功后commit；核心 loss 无重写。
5. 评价：training/phase_a_validation_v2.py:LogDomainValidation.add/report 与 runner.py:evaluate_synthetic。共同Core用gamma2 FP64重算，lambda_q不进入评价。
6. 事务与身份：checkpoint.py:SyntheticStore/validate_payload、rng.py、safety.py:StepLedger，以及 runner.py:save/restore。核对先验证再应用、失败停用、拒绝未完成边界、恢复不回滚额度。

未通过的检查：没有当前失败。尚未执行/尚未具备：最终收尾源码再次完整 optimizer 更新回归（12次硬额度已耗尽）；多步连续长期轨迹；正式完整 epoch/验证事务；真实数据权限/preflight；正式审批证据服务和 LAST 祖先链；Windows断电/磁盘满及长期文件系统耐久性；正式资源、调度、报告和9epoch结果。不能把这些记为已通过。

独立授权后的安全顺序：本人审查核心loss/控制变量/决策材料 → 确定科学效应与副作用界限并独立签署协议 → 授予正式集成版本开发许可 → 另建真实数据preflight许可及审计机制 → 确认资源和失败/恢复机制 → 单独签署seed2026六组执行范围。其余seed及任何恢复另受相应许可约束。本候选没有正式执行入口，不能直接翻转布尔值开始训练。

本轮合成工程开发是研究者委托AI的工作，不代替本人理解或最终科研审查。
""")
    # Compact editable Chinese review. No raster/chart assets are generated.
    tex = r"""\documentclass[UTF8,11pt,a4paper]{ctexart}
\usepackage[margin=21mm]{geometry}
\usepackage{amsmath,booktabs,array,longtable,xurl,hyperref,fancyhdr}
\hypersetup{colorlinks=true,urlcolor=blue,linkcolor=black}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{YunTAPR-Net 工程候选审查}\fancyhead[R]{合成工程专用}\fancyfoot[C]{\thepage}
\setlength{\headheight}{16pt}\setlength{\parindent}{0pt}\setlength{\parskip}{6pt}
\begin{document}
\begin{center}{\Large Phase-B v2 独立 Runner 工程审查}\par
{\small 2026-10-10 · 候选 v1 · 未批准正式科学执行}\end{center}
\textbf{本轮结果：}75 CPU、8 CUDA 唯一检查通过；12 次真实合成 AdamW 更新；正式更新 0。旧 91 CPU、6 CUDA 检查未重跑。两次工程错误已修复并保留：Windows 锁释放顺序导致 1 个失败；追加 fsync 时缩进错误导致 1 个测试收集错误。

新代码只在 \path{src/yuntapr/experimental/phase_b_v2_runner_candidate/}。没有真实数据入口或正式 epoch 循环；checkpoint 全部留在本轮专用临时目录，没有发布任何模型权重。
\section*{更新及共同评价的区别}
\[
L_{train}=\frac{S_{occ,\gamma}^{FP32}+\lambda_qS_{qr}^{FP64}}{N_{valid}},\qquad
L_{common}=\frac{S_{occ,2}^{FP64}+S_{qr}^{FP64}}{N_{valid}},\qquad
L_{CPB}=\frac{S_{qr}^{FP64}}{N_{rain}}.
\]
E0：$(\gamma,\lambda_q)=(2,1)$；E1：$(0,1)$；E2：$(2,2)$；$\alpha=0.5$。
参考有雨标签先在原 FP32 域比较 $r>0.1$ mm/h；$\tau_i=(i-0.5)/32$。32 个 Pinball 先平均，再只对有雨有效格点求和。共同评价重新以 FP64、gamma=2 计算发生分子，不复用训练发生分子，不引入 $\lambda_q$。

人工 batch=2：B0输入 $[2,1,501,501]$，B1输入 $[2,6,501,501]$；监督 $[2,1,100,100]$，分位数 $[2,32,100,100]$。人工掩膜每场景3430格点，不代表云南地理。AdamW沿用冻结分组衰减 $10^{-4}/0$、betas $(0.9,0.999)$、eps $10^{-8}$、clip=5。LR在更新前赋值，沿原50epoch轨迹前缀，首次为 $10^{-4}/5228$。

\textbf{兼容范围：}6 个完整模型事务证实双头和骨干参与更新、参数/状态有限、同初态重放及 LAST 恢复完全一致。无雨批次验证了条件头连接的零梯度，但没有对无雨批次 step。本轮没有新的真实科学性能结果，也没有证明校准、q32或上尾问题已解决。
\newpage
\section*{Checkpoint 与故障边界}
schema为 \path{SYNTHETIC_B9_V0_CANDIDATE_v1}。包含模型、AdamW、S0调度、所有RNG、seed/arm、源commit、冻结来源SHA、候选源码SHA、protocol SHA、fresh祖先及人工完成边界。正式epoch、正式更新均固定为0；候选终点9仅为元数据。

保存：独占锁、临时序列化、flush/fsync、SHA、rename blob、提交 receipt；只有 receipt 完成才可恢复。读取先核对SHA，再 weights\_only=True。恢复在任何状态应用前验证全部字段；apply异常后runner停用，不自动重试。回滚模型/RNG不回滚本轮更新账本。

\begin{longtable}{p{0.43\linewidth}p{0.49\linewidth}}\toprule
测试故障&实际结果\\\midrule
保存中断、blob后中断&没有receipt，不可恢复；保留临时/orphan证据\\
锁异常、外部预存锁&拒绝保存；不删除外部锁\\
截断、byte修改、错误SHA&反序列化前拒绝\\
缺失模型/optimizer、错误seed/arm/epoch/来源&校验拒绝；真实B0/B1 live状态保持不变\\
AdamW moments/shape/dtype/非有限/step/LR异常&人工元数据边界测试拒绝\\
apply异常&runner poisoned，后续更新拒绝\\
FRESH0重放及LAST1恢复&6组model、optimizer、scheduler、RNG摘要一致\\\bottomrule
\end{longtable}
LAST1只表示一个人工微循环完成，不是正式完整epoch。Windows rename/fsync与故障注入不证明断电目录持久性，正式集成仍需专门验证。

首次完成12次更新后补强源码身份、dtype、quota落盘和guard。原始更新代码摘要与最终代码摘要分别保留；追加CPU及2个无更新CUDA检查通过。受12次硬上限约束，最终收尾版本没有再完整重复optimizer更新，不能伪称一次同版本全套运行。

\newpage
\section*{本人审查顺序与实际资源}
先看 \path{FINAL_CODE_REVIEW_HANDOFF.md}，再按 identity、optimizer、safety、rng、checkpoint、runner 的顺序阅读。核心损失仍位于已有 ablations命名空间；评价来源是 \path{training/phase_a_validation_v2.py} 的 LogDomainValidation；来源SHA见 manifest与source\_identity。333个冻结/历史来源未改变；正式训练源码没有导入候选模块。

\begin{center}\small
\begin{tabular}{lrrr}\toprule 模型/臂&allocated MiB&reserved MiB&更新+评价秒\\\midrule
__RESOURCE_ROWS__
\bottomrule\end{tabular}\end{center}
RTX5060 Laptop；固定完整架构和精度。峰值包含初始化、无雨backward、两次step、评价及保存恢复。计时使用CUDA synchronize。这些短程人工数据测量不包括真实I/O、长期缓存、完整验证或热降频，不能直接外推正式耗时。

未完成正式工程事项：真实数据资格/preflight、完整epoch与验证完成证明、正式审批审计服务、恢复授权祖先链、真实资源与存储测量、长期中断/断电耐久性、多步正式训练回归。当前所有科学效应仍待独立研究者决定。

18个候选运行：两个模型、三个臂、seeds2026/2027/2028，固定9epoch、第9epoch终点。每epoch5228更新；每运行47052，计划总846936；首批seed2026六组282312。上述数值全部是计划，实际正式更新0。
\newpage
\section*{独立研究者决策清单}
\begin{enumerate}
\item 独立接受Phase-A证据的范围；H-O/H-Q及E0/E1/E2科学协议。
\item Brier最小有意义改善：绝对差或相对改善的标准；数值尚未建立。
\item q32覆盖误差标准：相对 $0.984375$ 的绝对误差（百分点）；不得只因覆盖提高宣称更好。
\item Conditional Pinball、AUROC、AP副作用容忍界限：原单位/相对增幅及绝对下降，分别预定。
\item 多重比较：有效p值基础上的Holm、适用假设成立的配对max-stat，或保持探索性效应与区间；检验家族及功效尚未建立。
\item 历史B1恢复治理偏差的独立处置；不得以本轮测试追认。
\item 正式Runner集成许可；须另建真实数据接入版本。
\item 2023/2024真实数据preflight许可；2025封存。
\item GPU/磁盘/时间窗口、停止与恢复策略及正式预算。
\item seed2026六组的单独执行许可；其他seed以后按独立许可补齐，不能按首批表现修改规则。
\end{enumerate}
数值效应界限、统计功效均为 \path{NOT_YET_ESTABLISHED}；全部项目 \path{RESEARCHER_DECISION_REQUIRED}。D01/D02初步讨论不等于签署。

真实LAST恢复必须另行绑定具体SHA及授权祖先，并由本人独立批准。本轮合成checkpoint恢复不授予正式恢复权。固定保持：Phase-B未授权，正式执行未授权，科学审批必需，历史恢复未追认，2025原始访问和像元读取均为0。

\textbf{审批边界停止：}没有正式训练入口；批准字符串、JSON、Git提交或合成测试通过都不能启动正式训练。保护是候选Python进程的防误用机制，不是恶意代码安全沙箱。
\end{document}
"""
    rows = "\n".join(f'{c["model"].replace("_", "")}/{c["arm"]}&{c["peak_cuda_allocated_bytes"]/2**20:.2f}&{c["peak_cuda_reserved_bytes"]/2**20:.0f}&{c["update_plus_evaluation_seconds"]:.3f}'+r"\\" for c in cases)
    write("RUNNER_ENGINEERING_REVIEW.tex", tex.replace("__RESOURCE_ROWS__", rows))
    print(json.dumps({"documents_created": 10, "CPU_unique_pass": 75, "CUDA_unique_pass": 8,
                      "synthetic_steps": 12, "protected_sources": 333}, ensure_ascii=False))


if __name__ == "__main__":
    main()

