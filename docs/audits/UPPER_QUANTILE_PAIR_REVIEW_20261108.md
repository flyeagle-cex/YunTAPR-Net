# UPPER-QUANTILE-PAIR-20261108｜改动代码与 19 项合成检查审核

- 审核者：Harness（独立于 Codex）
- 审核对象：Codex commit `f43b4225fef462a31035d59a06b85f31e5b257dc` 的 changed code、`test_upper_quantile.py`、PROTOCOL 与 EXECUTION_PROPOSAL
- 范围：只审 changed code 和新增 synthetic tests；未读数据/权重，未训练/推理，未安装依赖，未使用 2025，未生成批准
- 结论：**PASS_WITH_LIMITATIONS（限定 changed-code/19 项 CPU synthetic 审核；科学 NOT_VERIFIED）**

## 0. 先报阻断/非阻断

**阻断性（当前不能直接启动，不是代码逻辑错误）：**

1. **当前 Codex 工作树不干净。** 审核期间 `git status` 显示 `README.md`、`STAGE_ACCEPTANCE.md`、`REVIEW_INDEX.md`、`Master_Plan_Live.tex` 有修改，且出现新的 LIVE.25 PDF 和若干未跟踪输出文件。`start_upper_quantile_pair.py` 的 execute 路径会先执行 `git status --porcelain` 并要求 clean；当前状态会被拒绝。审核只按 commit `f43b422` 的代码，未修改这些文件。
2. **尚无研究者批准。** PROPOSAL 状态为 `READY_WAITING_EXACT_RESEARCHER_APPROVAL`、`authorized=false`；未生成/填写 approval，不能启动。

**代码审核未发现新的代码级阻断项。**

## 1. 文件与证据

- commit：`f43b4225fef462a31035d59a06b85f31e5b257dc`
- `PROTOCOL.md`：3,654 B
- `EXECUTION_PROPOSAL.json`：97,042 B / `DE5EA32EC5F078B747BBE24ACCACD3FA09A6D56AFD103AF3055D7599187B787D`
- `VERIFICATION.json`：91,169 B；记录 19 new synthetic、29 affected old、合计 48
- test_upper_quantile.py：19,321 B
- 本轮实际只独立运行了新增 19 项，没有重跑旧 29 项。

## 2. 19 项合成测试

使用既有 `F:\conda_envs\rain-basics\python.exe -B`，强制 CPU、禁 pycache、自身私有临时目录：

```text
Ran 19 tests in 0.130s
OK
```

19/19 通过。测试只使用人工张量、mock proposal/approval/worker，`optimizer.step=0`；没有真实数据、权重、checkpoint 或训练。

## 3. changed code 核对

### 3.1 UQ_MILD_V1 损失
- 权重为原 32 个中点 tau 上的 `w(tau)=2(1+tau)/3`，正、单调、和=32；测试覆盖首尾 65/96、127/96 与和。
- `upper_quantile_loss` 只替换条件分位 numerator，按权重和归一化；原 `s_occ`、`s_qr` 和 `scientific_conditional_pinball` 保持未加权语义。测试确认 occurrence 梯度不变，只有 32 个分位节点梯度按权重缩放。
- 全 dry 时条件分位梯度为连接零，不发生 `None` 或非有限值。
- 训练 objective 使用 `combine_numerators` 的 `(S_occ + S_qr_weighted)/N_valid` 语义；测试比较了候选 objective 与 `s_occ/N_valid + weighted_quantile_per_valid`。

### 3.2 Engine 的身份与 scope
- `forward` 只有明确 `UQ_MILD_V1` 且 B7/E0 时使用新损失；B8、E2、未知 profile 都会在模型前拒绝。
- `PairedExecutor` 将 UQ 限制为单一 B7/seed2029/lambda1/无 recovery；要求 origin reference，校验完整初态 SHA 与九轮 order。
- UQ 身份进入 update ledger、train 记录、checkpoint identity、LAST receipt；control E0 不声明修改损失。
- 训练记录保留 `s_qr_unweighted`，另记 `sqr_training` 与加权 mean。

### 3.3 物理诊断与七项 gate
- `PhysicalPinball` 从已有 Development 前向输出计算：`expm1(qlog)`、原 32 中点 tau、mm/h Pinball、固定除以 20；bins 为严格 `lower < R <= upper`，R>20 取后三箱。
- 非有限/溢出立即失败，不裁剪、不静默剔除；physical bins 与 log bins 的雨量计数必须相同。
- `pair_summary` 同时计算 strong log/strong physical 两项改善，及 all-log/all-physical/Brier 不上升、occurrence AP/AUROC 不下降；q32 只作 auxiliary，不进入成功 gate。
- 科学状态保持 NOT_VERIFIED；没有把 synthetic gate 当作真实模型结论。

### 3.4 两臂启动/来源/审批
- `upper_quantile_training` 固定 CONTROL_E0 → CANDIDATE_UQ_MILD，两个 B7/2029；candidate 使用 control 的完整初态 SHA 和九轮 order 作为 origin/pair reference。
- 两臂各 4320 更新、477,571,953,840 B/142,813 次，合计 8640/955,143,907,680 B/285,626 次；21600 秒/臂、43200 秒/包、24 GiB/task、48 GiB 初始、零 replay、零额外重试、零 checkpoint load。
- `start_upper_quantile_pair` 要求外部 approval、准确 commit、proposal/private/output；`start_independent_process` 新增 exact B7 E0/UQ_MILD 两臂 gate，旧入口规则未改，也没有借用 ENGINEERING_PROBE。
- 未生成 approval，未启动。

## 4. 局限

1. **19 项是 synthetic/mock**；未运行真实 B7/2024 Dev、真实 32 节点输出、真实物理 Pinball 或实际 CUDA 训练。`VERIFICATION` 的 29 项 affected old 检查未由本审核重跑。
2. **成功执行路径未端到端测试**：19 项覆盖损失、profile、origin、physical diagnostics、gate、缺失 approval 和首臂失败；未启动真实 `prepare`→两臂成功→closure，worker 使用 mock。实际 source meter、completion 字段与 package closure 未由本审核执行。
3. **`PhysicalPinball` 对 qlog 要求有限、正、严格递增**；如果真实模型的 32 个分位输出发生 crossing，当前实现会立即失败而不是裁剪。该行为符合“不静默剔除”，但真实频率未验证。
4. `start_upper_quantile_pair` 直接 CLI 仍依赖内部 approval/clean-commit 检查；正式启动应走既有独立 WMI/start_independent 路径，不能用直接 CLI 代替监督链。
5. 当前 Codex 工作树被非本提交的文档/PDF/未跟踪输出弄脏；在 clean 恢复前 execute 会被拒绝。未改任何文件。

## 5. 结论

**PASS_WITH_LIMITATIONS**：changed code 的 UQ_MILD 权重、未加权科学指标保留、B7/E0/seed2029 身份、origin/order、physical diagnostics、七项 gate、两臂预算和启动门禁均与 PROTOCOL/PROPOSAL 一致，新增 19 项测试在本环境独立通过。当前**未获批准**且**工作树不干净**，所以不能启动；成功执行路径、真实 CUDA/数据与科学效果未验证。

- 工程：**PASS_WITH_LIMITATIONS（限定 changed-code + 19 synthetic checks）**
- 科学：**NOT_VERIFIED**
- 外部 Stage 4.5：**PARTIAL**
- 研究者掌握：**NOT_ASSESSED**

本轮未读任何真实数据/权重/缓存/2025，未训练/推理/评价，未安装依赖，未改 Codex/Shared 共同决策或 main，未生成批准。
