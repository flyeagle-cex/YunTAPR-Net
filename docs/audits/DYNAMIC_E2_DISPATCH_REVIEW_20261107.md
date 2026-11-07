# DYNAMIC-E2-DISPATCH-20261107 / LIVE.16｜限定启动差异审核

- 审核者：Harness（独立于 Codex）
- 审核对象：4 份源码、1 份新测试、`EXECUTION_PROPOSAL.json`、`VERIFICATION.json`、README/STAGE/REVIEW_INDEX、LIVE.16
- 范围：只审 E2 启动/派发差异；未生成批准、未启动模型、未读预测/标签/权重/manifest/缓存/2025，未改 Codex
- 结论：**PASS_WITH_LIMITATIONS（限定启动差异）**

## 1. 文件与测试

Codex 基准 `5687c42d6843fab21d367863df331552a9c3e1c8`，当前 12 文件未提交。`VERIFICATION` 的 11 artifact 全部匹配：

- engine.py 19,167 B；dynamic_training.py 22,483 B
- start_dynamic_pair.py 2,242 B；start_independent_process.py 11,992 B
- test 10,885 B
- EXECUTION_PROPOSAL 102,186 B
- README 31,036 B；STAGE 43,075 B；REVIEW_INDEX 29,911 B
- tex 63,855 B；LIVE.16 PDF **25 页 / 692,264 B**
- 旧 LIVE.15 678,471 B / `9904ABEB...9635` 保留

提案：`authorized=false`、`status=READY_WAITING_EXACT_RESEARCHER_APPROVAL`、无输出目录、无 affirmative approval；未执行。

独立运行：

```text
F:\conda_envs\rain-basics\python.exe -B -m unittest -v tests.research_readiness.test_dynamic_loss_dispatch
```

强制 CPU、`CUDA_VISIBLE_DEVICES=''`、`PYTHONDONTWRITEBYTECODE=1`；**Ran 11 tests, OK**，failures/errors/skips 均 0。子进程/文件 mock，无真实模型/数据。

## 2. 代码审查

- `start_independent_process` 仅新增 `start_dynamic_pair` 到 APPROVAL_BOUND_EXECUTION 白名单，未改旧入口；未把 `ENGINEERING_PROBE` 借给 E2。
- 新 gate `validate_dynamic_loss_scope` 要求 `--lambda-q` 2、proposal `protocol.loss=E2/lambda_q=2`、精确 `B7→B8/2029` tasks、解释器 SHA 绑定；外部描述仍要求研究者 approval、提案/预算/选择/输出、干净实际 HEAD 和未消费目录。新入口以 `approval['code_commit']` 与实际 HEAD 绑定，避免 proposal 自引用；旧入口仍用原 `execution_code_commit` 规则。
- `start_dynamic_pair` 的 execute/worker 显式接收 `--lambda-q`；控制器→子进程→worker→engine 均传递 2，默认 1。`RunSpec` 仍把 E2 限定为 B7/B8、seed2029、origin-only。
- `engine` 要求 E2 `origin_reference` 存在，校验全初态 SHA 和九轮 order 后，才创建 ledger/optimizer；缺失绑定在资源前拒绝，初态/顺序不符在 optimizer 前拒绝，ledger 已移到身份检查之后。
- `execute` 生成 `loss_pair_summary`：主指标标注 `S_qr/N_rain` 未加权条件 Pinball，另报 loss effect、B8−B7、interaction、Brier/q32 护栏；不新增 AP20 主结论。E0 默认 schema 和旧入口保持。

## 3. 非阻断观察

1. **空 mapping 边界**：`origin_reference` 为 `None` 时已在资源/模型前拒绝；但若被显式提供为 `{}`，`isinstance(dict)` 通过，可能在资源/输出建立后才在字段访问处失败。实际提案已含完整 origin，当前测试也未覆盖空 mapping；正式启动前建议再加一次完整字段预检（不影响本轮当前提案）。
2. 现有 `prepare`/既有 worker/dispatcher 仍默认 E0，E2 仅由显式新提案/新入口路径提供；尚无批准绑定的正式 E2 dispatcher 或输出目录，这与“等待准确研究者批准”一致。
3. 完整 CUDA/WMI 真实启动未执行；11 项只验证 mock 边界、调度参数和 CPU 合成 gate，不能证明真实 GPU/AdamW/4320 步行为。
4. `start_dynamic_pair` 的直接入口仍依赖其内部 approval/clean-commit 检查；WMI 的精确 E2 gate 只覆盖 APPROVAL_BOUND_EXECUTION 路径。运行规则应要求走 WMI，不应把直接 CLI 当等价监督链。
5. 提案中的 root 两初态/九轮顺序匹配来自执行方记录；本审核未独立读取真实权重，也未逐页复核 LIVE.16 视觉。

## 4. 结论与状态

**PASS_WITH_LIMITATIONS**：新 E2 调度 gate、显式 lambda 传递、旧 proposal 拒绝、origin/order 前置检查、loss 身份记录及旧 E0 保持均与请求一致；未发现借用 `ENGINEERING_PROBE` 或放宽旧入口，但当前提案尚未获批、未启动，且空 origin mapping 仍需防御性预检。

- 工程：**PASS_WITH_LIMITATIONS（限定启动差异；无批准/无执行）**
- 科学：**NOT_VERIFIED**
- 外部 Stage 4.5：**PARTIAL**
- 研究者掌握：**NOT_ASSESSED**

本轮未生成肯定批准、未启动模型、未读科研载荷/缓存/2025，未改 Codex/Shared 共同决策/规则/main。
