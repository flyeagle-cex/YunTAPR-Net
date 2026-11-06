# DOTE-DIRECTION-FREEZE-CANDIDATE-20261106.1 / LIVE.7｜限定方案与身份审核

- 审核者：Harness（独立于 Codex）
- 审核对象：`SOURCE_BINDINGS.json`、`DOTE_FREEZE_CANDIDATE.json`、`VERIFICATION.json`、LIVE.7 PDF/tex 及 README/STAGE/REVIEW_INDEX 当前入口
- 范围：源码与已保存元数据核对、身份绑定、非执行候选设计；未运行模型/梯度检查/测试，未读取权重/预测/标签/气象/缓存/2025
- 结论：**PASS（限定方案准备；不是可执行实验批准）**

## 1. 文件与指纹

Codex 起点 `8642fbd8b2adf9d4db32a814222a0eb5074bc939`，8 文件尚未提交。`VERIFICATION.json` 的 7 个 artifact 指纹全部匹配；其自身为第 8 文件。

- LIVE.7 PDF：**16 页 / 587,127 B / `1624F80A...32D8`**
- LIVE.7 tex：41,050 B / `883EB34A...7DF423`
- README：18,939 B / `7D769F39...497B`
- STAGE：30,978 B / `AAA6AE3D...CD79C`
- REVIEW_INDEX：18,700 B / `E25A0E0B...CA4C4`
- SOURCE_BINDINGS：12,160 B / `EE85A1DB...FEC89`
- DOTE_FREEZE_CANDIDATE：6,928 B / `CA5D9250...6995995`
- 旧 LIVE.6：**556,620 B / `113CBA8E...800F5`**，原字节保留。

## 2. 历史身份与来源

- 14 份 selected source 的字节/SHA256 全部匹配 `SOURCE_BINDINGS.source_documents`；未重读权重载荷。
- 8 个历史固定 E9 身份逐项解析通过：

| 模型/Seed | 来源字段 | 保存权重 SHA |
|---|---|---|
| B6/2029 | `b5_b6.../tasks/1/endpoint_sha256` | `3B3EC78E...AB9D98` |
| B7/2029 | `b7_b8_terminal.../tasks/0/fixed_E9_sha256` | `019A6DFA...F2E35` |
| B7/2030 | `b7_b8_three_seed.../tasks/0/fixed_E9_sha256` | `82079660...FFC15D` |
| B7/2031 | `b7_b8_three_seed.../tasks/2/fixed_E9_sha256` | `4537BE7A...0FC7` |
| ZERO/2030 | `dote_control_three_seed.../tasks/0/fixed_E9_sha256` | `B03EE41C...0BA` |
| ZERO/2031 | `dote_control_three_seed.../tasks/1/fixed_E9_sha256` | `F9995290...DAC0` |
| ZERO/2029 | `dote_control_completion.../endpoint_sha256` | `445E4BE5...4A21` |
| PERP/2029 | `dote_physical_completion.../endpoint_sha256` | `5406E20E...34E6` |

- B6 旧 `b7_b8_training_proposal.json/baseline_E9_sha256/B6 = 5F3E94...947DF` 确实对应 `b5_b6.../sources/"B6/development_09.json"/sha256`；对应权重身份另为 `3B3EC78E...AB9D98`、53,291,781 字节。旧文件未改，未制造假冲突。
- 旧 ZERO 的 128 个 width16 结构零梯度投影权重、真实 mask、名义结构匹配但有效容量不等价均保留；B6→B7 额外融合/参数混杂也保留。旧结果不重训、不主张物理因果。

## 3. 候选设计

- 随机刚性旋转为 **PROPOSED main direction control**：场景级固定角度，跨两压力层/所有像元共享，建议独立 seed 20261106；不按 label/结果择优，所有训练 Seed 共享同一场景映射。
- 固定朝东 0° 为 **PROPOSED original-plan direction control**：valid 支持上 `u=hypot(u,v), v=0`，不是气象“风向自东”，不做 angle sweep。
- 仅替换 DOTE 内部局部 u/v，随后用未改 physical gradients/PWAT 重算 O/W/L/M；不改 MEE 风、DEM、PS/PWAT、真实 mask、通道顺序、精度、B7 初始化/优化器/样本顺序/损失。明确禁止旋转已 ReLU 的 W/L/M、恢复 post-mask 值、隐式 RH/T→q、裁剪或删除 changed-mask 样本。
- 真实注入点与 `PhysicalDote.physical` 的实际顺序一致：native/target pressure mask 与 grid mapping 之后、`dote_proxy` 之前替换局部 u/v；未改源码。
- `BatchReader.batch` 当前确实只传 `dynamic_transform(frame)`，没有 sample_id；`TargetBinding` 区分 analysis 与 reference window。候选明确要求未来冻结 manifest 的 `analysis_time -> unique(sample_id, canonical scene_time)` lookup，当前未实现，禁止从 frame.valid/时间猜 scene_id 或静默减 30 分钟。
- q 与 no-mask 均 `NOT_AVAILABLE`；无隐式 q 推导/无 mask 重建。

## 4. 执行与科学边界

- `execution_gate` 的 wrapper、manifest lookup、科学阈值、预算/路径、研究者 grant 全为 false；`executable=false`；`status=PROPOSED_NON_EXECUTABLE_NOT_RESEARCHER_FROZEN`。
- 主指标、最小有意义效应、允许退化、跨 Seed 接受规则、多重性/推断均为 `null`；T16/T17 门槛未移用；2024 仅 development，事件 `NOT_IDENTIFIED`。
- 明确保留：非零风不保证所有通道/梯度非零；三训练 Seed 不是三个独立扰动或独立天气；MEE 中真实风可能保留相关信息；刚性旋转改变分布及天气-地形对应。
- 外部 Stage 4.5 仍 PARTIAL，科学 NOT_VERIFIED，研究者 NOT_ASSESSED；本 PASS 只表示方案/身份准备，不表示正式冻结或可执行实验。

## 5. 非阻断观察

1. `SOURCE_BINDINGS.field_type_correction.actual_matches` 写成 `/sources/B6/development_09.json/sha256`，但实际 `sources` 键是扁平字符串 `"B6/development_09.json"`；若按 JSON Pointer 解释应转义为 `/sources/B6~1development_09.json/sha256`，或显式写 `sources_key`。内容对应事实已独立确认，不影响本 PASS，但建议后续修正路径表达。
2. `canonical_scene_time_proposal=ANALYSIS_TIME_UTC` 仍是建议；当前缺少 `sample_id` 和冻结 manifest lookup，不能把它当作已绑定。
3. 本审核只核对源码/保存元数据和设计文本，未运行 43 项测试、未做梯度/模型检查；LIVE.7 视觉检查为执行方自检，未逐页像素复核。
4. 8 个历史 E9 权重 SHA 只按保存元数据绑定，不是本轮对权重载荷的重新计算。

## 6. 结论与状态

**PASS（限定方案准备）**：8 个历史端点身份、14 份来源、B6 baseline/权重对象类型澄清、ZERO 128 零梯度限制、DOTE 内部注入点、scene lookup 缺口、两套方向控制定义及执行/科学门槛均核对无阻断；候选仍不可执行。

- 工程：**PASS（限定来源/身份/设计审核；Git 以实际回执为准）**
- 科学：**NOT_VERIFIED**
- 外部 Stage 4.5：**PARTIAL**
- 研究者掌握：**NOT_ASSESSED**

本轮未运行模型/梯度检查/测试，未读取权重/预测/标签/气象/缓存/2025，未训练/推理/评价/校准/bootstrap，未修改 Codex/Shared 共同决策/规则或 main。
