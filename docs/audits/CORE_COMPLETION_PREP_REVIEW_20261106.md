# CORE-PREP-20261106.1 / LIVE-20261106.6｜限定独立工程审核

- 审核者：Harness（独立于 Codex）
- 审核对象：三个隔离候选模块及三套测试、README/STAGE/REVIEW_INDEX 入口、LIVE-20261106.6 PDF/tex、WORK_PACKAGES/MULTI_AGENT_DISCUSSION/SYNTHETIC_CHECKS/VERIFICATION
- 范围：静态源码/契约审查，加只读 CPU 人工合成测试；未读取真实 NPZ/预测/标签/权重/原始气象/受限缓存/2025，未训练/推理/评价/校准/bootstrap
- 结论：**PASS（限定工程准备；无阻断发现）**

## 1. 文件与指纹

Codex 当前起点 `5f358de424764c43808e3a383e39f5dee06ecce4`，本轮 15 文件尚未提交。`VERIFICATION.json` 列出的 14 个 artifact（JSON 自身不在其内）实际字节/SHA256 全部匹配；8 个关联旧来源（含旧 LIVE.5、内部初稿、`fusion.py`、`dynamic_terrain.py`、DOTE controls、冻结契约）也保持原指纹。

- LIVE.6 PDF：14 页 / 556,620 B / `113CBA8E...800F5`；tex：36,812 B / `CDB2A550...F98C7`
- 三模块：`multiscale_candidate.py` 7,187 B、`dote_control_candidates.py` 9,459 B、`evaluation_alignment_candidate.py` 8,545 B
- 三测试：10,706 / 11,782 / 9,060 B
- README 17,761 B / `A9D61A6C...5B962`；STAGE 29,800 B / `9433CF51...B1BC8`；REVIEW_INDEX 16,992 B / `CD57B800...A4C04`

## 2. 实际测试

按请求使用 `F:\devtools\miniconda3\python.exe -B`、`PYTHONPATH=src`、CPU、禁止安装依赖，仅运行三个新 suite：

- `test_multiscale_candidate`：13 项
- `test_dote_control_candidates`：10 项
- `test_evaluation_alignment_candidate`：20 项

结果 **Ran 43 tests, OK, failures/errors/skips=0**，与 `SYNTHETIC_CHECKS.json` 的 43/13/10/20 记录一致。旧扩展回归未运行；其缺 PyYAML 的收集失败按原记录保留，未安装依赖，未冒充通过。

## 3. 契约审查

### 3.1 显式多尺度

- 要求 scales 为有序 `Sequence`，至少两个、名称唯一、物理 grid identity 不重复、至少两种 tensor 尺寸；不接受 set/dict/generator/字符串。
- wrapper 对 features 检查非空 4D Tensor、正 batch，并检查不同 scale 的 feature batch 一致；对每个 scale 的 feature/gfs/terrain grid 做 `grid.assert_same`。
- 被复用的 `FusionCandidate` 本身逐 scale 校验 gfs/terrain/mask 的 shape、batch、device、dtype、有限有效值，因此 wrapper 的 feature 跨尺度检查加上原语的对齐检查覆盖了“同非零 batch”的路径；本审核直接读取原 `fusion.py` 确认此依赖。
- 原 concat/DTFM 工厂与零初始化未被改写；`fusion.py` SHA `ED0206FC...AD847D` 与旧指纹一致。模块显式声明 `formal_integration=False`、`native_encoder_connected=False`、`decoder_connected=False`、`real_grid_mapping_verified=False`，没有 encoder/decoder、真实网格映射或训练入口。

### 3.2 DOTE 控制

- 固定方向只在 valid 像元上保留速度，输出 invalid 为 NaN；场景哈希旋转按 `scene_id + UTC time + control_seed` 生成稳定角度，整场景、两压力层同角旋转，保留速度和层间点积，不消费全局 RNG，不接受 label/model seed。
- 去 M、单压力层只置零指定数值通道，保留真实 mask；metadata 明确 `FEATURE_AVAILABILITY_CONDITIONAL_ON_REAL_MASKS`、有效容量不等价、32/64 个 width16 结构零梯度投影权重、mask 信息未移除。
- `reject_post_mask_unmasking` 与 `reject_unbound_specific_humidity` 直接拒绝无 mask 重建和未绑定 q 推导；无文件/网络/进程/优化器启动接口。
- 实际 10 项测试覆盖固定方向与既有 O/W/L/M 公式集成、随机旋转速度/层间点积/RNG、去 M/单层 mask、错误单位/形状/非有限有效值等。

### 3.3 元数据对齐

- 仅接收调用方显式元数据；字段闭集、canonical UTC、SHA256、pixel_count、`mm/h`、`START_INCLUSIVE_END_EXCLUSIVE`、精确 30 分钟窗口。
- 必须提供独立、唯一、有序的 expected scene-ID 清单；prediction/label 必须逐字段相同，长度、顺序、时间递增和窗口不重叠均检查，不排序/不重新配对/不丢行。
- `calendar_days` 保留空日；`contiguous_half_hour_windows` 只描述采样窗口，不产生天气事件；`event_id_status=NOT_IDENTIFIED`。
- `scene_timestamp_role`、`reference_window_extent_verified`、`reference_window_timestamp_relation_verified` 均显式标记未核验；调用方共同错误元数据仍只是调用方声明，不能变真。
- 20 项测试覆盖身份/时间/窗口/单位/清单/空日/闰日/重叠/2025 拒绝等。当前实现明确只接收 2024 元数据；这是本候选的范围限制，不是真实 2023/2024 覆盖证明。

### 3.4 多智能体记录与计划

- `MULTI_AGENT_DISCUSSION.json` 记录三位辅助代理的初始分工、交叉审查和两处 source finding（跨尺度 batch、无序容器）及修复；source review 不等于执行失败。
- `WORK_PACKAGES.json` 正确保持 PROPOSED/ENGINEERING、Stage 4.5 PARTIAL、外部第 6 项缺口、无新实验预算、2025 封存、事件 NOT_IDENTIFIED；P1/P2/P3 的后续均要求独立协议/批准。
- LIVE.6 为 14 页更新版，旧 LIVE.5 和内部初稿原字节保留；PDF 首次 3.63248pt 超宽在 Git 前停止修正，最终无 overfull/missing-character 自检记录保留。Codex 的视觉检查只列 1/2/11/12/13/14 页，不等于逐页像素独立审查。

## 4. 非阻断观察

1. `evaluation_alignment_candidate` 当前仅接收 2024 元数据；若未来需要 2023 开发/训练身份，必须显式扩展并另行审核，不能把本候选当成 2023/2024 通用对齐实现。
2. wrapper 的跨尺度 batch 检查针对 features；gfs/terrain/mask 的 batch/shape 对齐依赖未改的原 `FusionCandidate` 逐 scale 校验。该依赖在源码层成立，但未来若替换 fusion 原语，必须重新验证。
3. 本审核只运行 43 项人工合成 CPU 检查；未运行旧扩展回归，未读取真实载荷，未做真实网格/encoder/decoder 集成或科学有效性验证。
4. PDF 页数/指纹/内容与请求一致；视觉检查为 Codex 自检，本审核未做逐页像素审查。
5. `VERIFICATION.json` 自身未列入 artifacts（避免自引用）；15 文件口径由 14 artifact + 该 JSON 自身构成。

## 5. 结论与状态

**PASS（限定工程准备）**。三个候选没有发现阻断性接口、batch/顺序、mask/单位、元数据或启动边界错误；43 项合成测试可重复通过；旧 Fusion/默认来源/冻结契约保持原指纹；计划与工作包未把工程准备写成真实集成、科学验收或实验授权。

- 工程：**PASS（限定静态审查 + 43 项合成测试；Git 以实际回执为准）**
- 科学：**NOT_VERIFIED**
- 外部 Stage 4.5：**PARTIAL**（研究者报告当前无法完成，缺口未豁免）
- 研究者掌握：**NOT_ASSESSED**

本轮未读取真实 NPZ/预测/标签/权重/原始气象/受限缓存/2025，未训练/推理/新评价/校准/bootstrap，未安装依赖，未修改 Codex/Shared 共同决策/规则或 main。

## 6. 格式纠正补充核验（2026-11-06）

- 触发：提交前 `git diff --cached --check` 将四个新 JSON 的 CRLF 判为 trailing whitespace；Codex 未 commit，保存 `staged_crlf_failure.txt`，仅将四个 JSON 规范化为 LF。
- 独立比较 `.reviewed_before_lf.bin` 与当前文件：
  - `WORK_PACKAGES.json`：8,400 B / `59C3A263...896BA`，解析语义与旧 8,540 B 版本完全相同；
  - `MULTI_AGENT_DISCUSSION.json`：3,690 B / `E3737058...11C1`，解析语义相同；
  - `SYNTHETIC_CHECKS.json`：1,740 B / `2ED91DDB...E58FEB2`，解析语义相同；
  - `VERIFICATION.json`：6,756 B / `1D2A0848...7E0DBE`，与旧 6,922 B 版本仅三个 artifact 的 size/SHA 条目不同，其他字段相同；这三个条目正好对应前三份规范化的 JSON。
- 当前 `VERIFICATION` 的 14 个 artifact 指纹全部重新核对通过；三模块、三测试、LIVE.6 PDF/tex 的字节/SHA 与首审时一致，未重跑 43 项测试。
- 四个当前 JSON 均无 CRLF；首审 PASS 的代码/契约结论与历史保持，不被本格式补丁改写。
- 结论：**PASS（格式补充核验）**；仍为限定工程准备，不是真实集成、科学验收或实验授权。

补充核验本身未读取真实 NPZ/预测/标签/权重/原始气象/2025，未训练/推理/评价/校准/bootstrap，未安装依赖，未修改 Codex 文件或 Shared 共同决策/规则。
