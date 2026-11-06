# PARALLEL-CORE-20261106.1 / LIVE.9｜限定新增差异审核

- 审核者：Harness（独立于 Codex）
- 审核对象：三个新模块/三新测试、README/STAGE/REVIEW_INDEX、LIVE.9 tex/PDF、`20261106_parallel_core/VERIFICATION.json`
- 范围：只做新增差异审核；继承旧 43/8 测试、14 来源/8 E9 身份，不重跑；未读真实数据/权重/缓存/2025
- 结论：**PASS（限定工程接口准备；不是真实集成或科学执行批准）**

## 1. 文件与实际测试

Codex 起点 `4f94c18c01794939690bee2f6780258e10d7ce83`，12 文件尚未提交。`VERIFICATION.json` 的 11 个 artifact 指纹全部匹配；其自身为第 12 文件。

- `native_multiscale_adapter.py`：8,679 B
- `test_native_multiscale_adapter.py`：9,675 B
- `dote_transform_factory.py`：11,111 B
- `test_dote_transform_factory.py`：11,083 B
- `tail_identifiability.py`：5,367 B
- `test_tail_identifiability.py`：6,735 B
- LIVE.9 PDF：**17 页 / 599,761 B / `EF90ED55...A4085`**；tex 43,629 B
- 旧 LIVE.8：582,954 B / `CA884067...B75B37`，原字节保留
- 7 个 selected old source 指纹全部未变（`dote_direction_transform.py`、`dynamic_training.py`、`dynamic_terrain.py`、`multiscale_candidate.py`、`extreme_diagnostic_candidates.py`、`backbone_b0.py`、`stage2/models.py`）

按请求仅运行三新文件：

```text
python -X utf8 -B -m unittest -v \
  tests.research_readiness.test_native_multiscale_adapter \
  tests.research_readiness.test_dote_transform_factory \
  tests.research_readiness.test_tail_identifiability
```

结果：**Ran 28 tests, OK**；9/7/12，failures/errors/skips 均 0。未重跑旧 43/8；未运行真实数据、模型训练/推理/评价/梯度/反向/优化器。

## 2. 新增接口审查

### 2.1 Native encoder/decoder seam

- `NativeMultiscaleAdapter` 复用实际 `B0Backbone` 的 `enc0..enc3`、`down1..down3` 与 `dec0..dec2/_up`；只把选中的 2+ 层 encoder tensors 送入既有 `ExplicitMultiscaleFusionCandidate`，再放回原 decoder 输入。没有新 encoder/decoder 层、SP04 池化或隐式 resize。
- encoder tap grid 按既有 kernel3/padding1/stride2 中心几何从显式 native GridSpec 推导；条件 grid 必须显式匹配，不自动 interpolate。`native_valid` 要求继承的 fully-valid bool mask；输出要求 native feature shape。
- 明确 `formal_integration=False`、`real_grid_mapping_verified=False`、`probability_heads_connected=False`；未接 MEE/static residual、概率头、损失或执行器。

### 2.2 DOTE factory

- `DirectionTransformFactory` 只接受已加载的完整 Train/Development 原始 manifest、已 materialize 的 `PopulationPlan` identity/rows/ordered IDs 及显式 direction control；不打开文件、不重建 manifest、不注册默认 reader/executor。
- 两角色分别保留原 manifest lookup，按 frame analysis 路由；任一 analysis 跨角色冲突即拒绝。`_terrain_from_pack` 与既有 `PhysicalDote.__init__` 的 B6 六通道 100x100 映射一致；pack/definition 必须显式。
- 明确原 `run_task` 不传 plan、`PopulationPlan` 不保留完整 manifest body；正式 dispatcher、真实 manifest binding、执行 commit/预算/授权均缺失；`EXPERIMENT_READY=False`。

### 2.3 Tail identifiability

- 严格 `>` 复用既有 `exceedance_bounds`/decision API；新增 `>=`、CDF 左右极限和阈值原子质量保守界，不 interpolate 节点、不补全尾部、不生成精确概率。
- 阈值 `.1` 时明确区分 `DELTA_AT_ZERO` 与 `NOT_IDENTIFIED_ON_CLOSED_0_TO_0_1`；调用方必须声明非雨质量假设，不从 occurrence label 自动推断 delta0。
- 阈值 > `.1` 的 inclusive/strict、CDF、mass 界按 32 节点约束推导；节点相等/边界原子不默认为连续；数值退化时 raise 而非 repair。
- AP20[q32] 仅为 PROPOSED 建议，未批准为正式 primary metric；科学阈值/效应/退化/推断均未落实。

## 3. 非阻断观察

1. Native adapter 当前要求 fully-valid native context，且实际 condition-to-native mapping、概率头、MEE/static residual 与完整 Stage2 wrapper 均未接；完整 wrapper 因既有 YAML loader import 失败未运行，未安装依赖。
2. DOTE factory 要求完整原 manifest 与已 materialize plan；旧 `run_task` 没有该上下文，正式 dispatcher/自动绑定未实现。所有合成检查不能替代真实 manifest 读取或授权。
3. Tail 的 nonrain component、support/quantile assumptions 均为调用方声明，不是已核实物理分布；`>=`/CDF/mass 为保守界，不是精确概率或端点可达性证明。
4. 旧尾部入口 14 项为 agent self-reported 14 pass，本审核未重跑；旧 43/8、14 来源/8 E9 身份不重审。
5. LIVE.9 视觉检查为执行方自检（改动页 1/11/12/15/17），未逐页像素复核；首次 32.61066pt 超宽在 Git/审核前停止修正。

## 4. 结论与状态

**PASS（限定新增接口准备）**：三个新接口的 enc/dec taps、两参数 DOTE factory、strict/inclusive/CDF/mass 边界均与请求范围相符；28 项人工 CPU 检查通过；未发现阻断性接口错误。仍不构成真实 mapping/正式执行链/训练推理评价/科学验收。

- 工程：**PASS（限定接口 + 28 项合成检查；Git 以实际回执为准）**
- 科学：**NOT_VERIFIED**
- 外部 Stage 4.5：**PARTIAL**
- 研究者掌握：**NOT_ASSESSED**

本轮未读取真实数据/权重/缓存/2025，未训练/推理/评价/校准/bootstrap，未安装依赖，未改 Codex/Shared 共同决策/规则/main。
