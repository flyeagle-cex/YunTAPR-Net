# DTFM-GRADIENT-RELEASE-20261107｜限定新增差异审核

- 审核者：Harness（独立于 Codex）
- 审核对象：`probe_dtfm_gradient_release.py`、`test_dtfm_gradient_release.py`、RESULT/VERIFICATION、README/STAGE/REVIEW_INDEX、LIVE.13 tex/PDF
- 范围：独立核对指纹/代码/合成结果边界，并运行一次新 suite；未读真实载荷/权重/manifest/缓存/2025，未改 Codex
- 结论：**PASS_WITH_LIMITATIONS（仅合成梯度路径；不是有效学习或性能证据）**

## 1. 实际检查与保存

- Codex 起点 `48878aef4bb9c5c81487d534c86dd6c4dae6d7ca`，9 文件未提交。
- 当前 `VERIFICATION` 的 8 个 artifact 指纹全部匹配：
  - tool 9,098 B / `E2A9BC73...6EC`；test 4,393 B / `D91BC4B8...C5F`
  - RESULT 48,065 B / `01205547...E35`
  - README 27,036 B；STAGE 39,075 B；REVIEW_INDEX 26,968 B
  - tex 55,390 B / `2ED1AD4F...9180`；LIVE.13 PDF **22 页 / 659,782 B / `44A8789B...B380`**
- 旧 LIVE.12 648,445 B / `A34C2E8D...FE3B` 保留；新版实际存在的 tex/PDF 与当前 VERIFICATION 一致。
- 独立运行一次 `tests.research_readiness.test_dtfm_gradient_release`：**Ran 7 tests, OK**；7/0/0；该 suite 的 `setUpClass` 真实调用一次 CLI，合计 **10 次合成 SGD optimizer.step**，未安装依赖、未读科学载荷、未在 Codex 创建 fixture。

## 2. 代码/结果核对

- 探针固定 Seed 20261107、48/26/28 通道/width16、小人工 9×9 网格、每臂 5 步、SGD lr=.01/无 momentum/weight_decay=0；真实模型未改、无手填权重、无真实数据/推理/评价。
- 首步残留为 0，B7/B8 外层 fuse 均有非零梯度；首个非零梯度 B7 为 fuse1/mix2/GFS2/terrain2，B8 为 fuse1/mix2/modulation2/GFS3/terrain3；后续梯度有限、非 None。
- **关键限制**：B8 的 GFS/terrain 条件投影在后几步虽出现非零梯度，但五步内实际参数 delta 仍为 **0**；零初始化造成的首步门控只是释放延迟，不等于有效条件学习。测试只断言首步零梯度/零 delta 与首次释放，未逐步断言 B8 参数全程保持 0；RESULT 已记录这一点。
- 探针是 FP32 CPU 诊断 SGD，不是正式 AdamW/BF16/4320 步轨迹；不能推断真实训练动态、性能根因或需要修改初始化。当前外层结论应为 `PASS_WITH_LIMITATIONS`，不能把原始 CLI 的 `PASS` 单独当作有效学习证据。
- `VERIFICATION` 与 README 均保留该限定；未发现把 B8 非零梯度写成有效权重更新、或把 DTFM 合成路径写成性能改善的越界。
- 初始审核请求曾列 tex 55087/CC73，但当前 VERIFICATION/实际为 55390/2ED1，PDF 仍 44A；以当前 VERIFICATION 为准确版本，视为请求快照落后，不影响当前 8 artifact 一致性。

## 3. 非阻断观察

1. 测试没有覆盖 B8 GFS/terrain 参数在全部五步始终为零；该事实来自 RESULT 记录而非断言，正式接入前可补一条逐步 zero-delta 断言。
2. 7 项测试只证明合成图可达与首步门控，不证明 AdamW/BF16/真实 mask/真实损失下的梯度释放。
3. LIVE.13 视觉为执行方自检；本审核未逐页像素复核。
4. 旧 43/28/26、真实数据/权重/2025 未重跑或读取，既有审计继承。

## 4. 结论与状态

**PASS_WITH_LIMITATIONS**：新增探针/测试/收据/文档差异与当前指纹一致，7 项合成检查通过；`SYNTHETIC_GRADIENT_PATH_CHECK` 只能记为合成路径可达，B8 条件投影五步参数 delta 仍为零，不能推断有效学习、正式训练动态或 DTFM 增益。

- 工程：**PASS_WITH_LIMITATIONS（仅合成梯度路径；Git 以实际回执为准）**
- 科学：**NOT_VERIFIED**
- 外部 Stage 4.5：**PARTIAL**
- 研究者掌握：**NOT_ASSESSED**

本轮无真实训练/推理/评价/校准/bootstrap，无科研载荷/2025 读取，未改 Codex/Shared 共同决策/规则/main。
