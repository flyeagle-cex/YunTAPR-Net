# DYNAMIC-LAMBDA-ENTRY-20261107 / LIVE.15｜限定新增差异审核

- 审核者：Harness（独立于 Codex）
- 审核对象：`stage4/engine.py`、`dynamic_training.py`、`test_dynamic_loss_entry.py`、README/STAGE/REVIEW_INDEX、LIVE.15 tex/PDF
- 范围：只审 lambda entry 新增差异，继承旧测试/历史审计；未运行正式训练/真实模型前向，未读预测/标签/权重/manifest/缓存/2025
- 结论：**PASS（限定代码接线与 8 项 CPU 合成检查）**

## 1. 文件与测试

Codex 基准 `bc62b8b69d2e12e570bd6db60e695632f03a21c2`，当前 9 文件未提交。`VERIFICATION` 的 8 artifact 指纹全部匹配：

- engine.py 18,215 B / `459CB600...356C7`
- dynamic_training.py 19,146 B / `F8AB5A62...19E40`
- test 11,038 B / `97429668...A7331`
- README 29,810 B；STAGE 41,849 B；REVIEW_INDEX 29,220 B
- tex 61,133 B / `6A199F57...AAA9`
- LIVE.15 PDF **24 页 / 678,471 B / `9904ABEB...9635`**
- 旧 LIVE.14 及 4 个旧源码/测试源指纹保持，`git diff --check` 记录通过。

独立运行新增 suite：

```text
F:\conda_envs\rain-basics\python.exe -B -m unittest -v tests.research_readiness.test_dynamic_loss_entry
```

强制 `CUDA_VISIBLE_DEVICES=''`、`PYTHONDONTWRITEBYTECODE=1`；**Ran 8 tests, OK**，failures/errors/skips 均 0。测试仅使用人工输出张量/mock 源边界，`optimizer.step=0`，无真实模型/数据。

## 2. 代码审查

- `RunSpec` 与旧 B0/B1 RunSpec 分离；只接受 B7/B8、lambda∈{1,2}，lambda2 仅 seed2029；`E0/E2` 来自既有 closed config。
- `run_task` 在源 IO 前校验 `protocol.loss/lambda_q` 与显式参数一致；旧/不一致协议拒绝。lambda 传入真实 `PairedExecutor`，`forward` 使用选定 `loss_config`；Train/Dev 两个 callsite 均显式传递，AST 检查覆盖。
- `engine` 默认 lambda1 仍为 E0；`PairedExecutor` lambda2 严格要求单一 B7/B8 seed2029、无 recovery；identity、train `loss_arm/lambda_q`、checkpoint identity、LAST receipt、completion 均记录非默认 loss 身份，E0 默认 schema 未改。
- 人工张量验证：lambda1 与旧 E0 目标及 logit/qlog 导数逐位一致；lambda2 只把 qlog 项权重和其导数加倍，occurrence、S_qr、分母、条件 Pinball 不变；全 dry 时发生概率梯度非零、条件分位梯度连接但为零；无隐藏初始化/样本顺序/LR 改动。

## 3. 非阻断观察

1. 现有 `prepare` 仍生成不带 loss/lambda 的 E0 protocol，既有 `worker` 也不选择 lambda2；E2 目前只可由低层 `run_task` 的显式协议调用，尚无批准绑定的正式 E2 dispatcher/输出预算。这与 `VERIFICATION.outstanding` 一致，不是本审核可放行的执行路径。
2. 完整 CUDA 训练循环未运行；本审核只验证代码接线、人工损失/导数和 mocked executor，未验证真实网络参数梯度、AdamW/BF16 或 4320 步动态。
3. 初测缺依赖/fixture 失败已在 VERIFICATION 保留，未安装依赖；本次 8 项使用现有环境。
4. LIVE.15 视觉为执行方自检（页 1/21/24），本审核未逐页像素复核。

## 4. 结论与状态

**PASS（限定代码接线与 8 项 CPU 合成检查）**：lambda1/2 的损失、导数、scope 限制、身份记录及旧协议拒绝均与请求一致；未发现隐藏初始化/顺序/LR 变化或旧 E0 schema 破坏。该 PASS 不包含真实 CUDA 循环、正式 E2 dispatcher、科学判据或性能结论。

- 工程：**PASS（限定新增代码 + 8 项合成检查；Git 以实际回执为准）**
- 科学：**NOT_VERIFIED**
- 外部 Stage 4.5：**PARTIAL**
- 研究者掌握：**NOT_ASSESSED**

本轮无真实训练/推理/评价/校准/bootstrap，无预测/标签/权重/manifest/缓存/2025 读取，未改 Codex/Shared 共同决策/规则/main。
