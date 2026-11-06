# IMERG 参考路线限定修订｜独立审核

- 审核者：Harness（独立于 Codex）
- 审核对象：`REFERENCE_SCOPE.json`、`VERIFICATION.json`、LIVE-20261106.4 计划 tex/PDF、README/STAGE/EVALUATION_ENTRY_GATES/REVIEW_INDEX 差异，以及冻结 `config/science_contract_v1.1.yaml`
- 范围：只审参考路线差异、证据分类、冻结产品语义与执行边界；未读取 NPZ/预测/标签/权重/原始气象/2025，未下载观测或运行模型/指标/bootstrap
- 结论：**PASS（限定文档与证据边界审查）**

## 1. 变更范围与指纹

Codex `48446c1..66a2a13` 实际仅 8 个文件：

- README.md、STAGE_ACCEPTANCE.md
- 20261106_research_convergence/EVALUATION_ENTRY_GATES.md、REVIEW_INDEX.md
- output/pdf/YunTAPR-Net_Master_Plan_Live.tex、LIVE-20261106.4 PDF
- 20261106_imerg_reference_scope/REFERENCE_SCOPE.json、VERIFICATION.json

独立复核：

- REFERENCE_SCOPE.json：4,712 B / `77D2503D...F9097E`
- VERIFICATION.json：4,123 B / `4E8EA2DE...958302`
- tex：31,500 B / `89216FA6...8355D`
- 新 PDF：523,367 B / `84712A9F...F0A99`，实测 **12 页**
- 旧 `_3` PDF：492,717 B / `8CD615E7...3E882`，未被覆盖
- README/STAGE/gates/index 当前值分别与 `VERIFICATION` 的 16,171/28,210/6,049/13,196 B 及对应 SHA 一致
- 冻结契约 `config/science_contract_v1.1.yaml`：14,085 B / `14209321...756C3`，未改

## 2. 研究者资料事实与 IMERG 定位

- `REFERENCE_SCOPE` 把研究者回复归一化为：目前没有已落实外部参考资料；若无可落实公开替代来源，则以 IMERG 为参考。同时明确：
  - 这是研究者直接报告，不是“所有公开来源不存在”的证明；
  - 不构成新数据/计算/实验批准；
  - 不构成科学验收或研究者掌握。
- 既有监督参考保持 **IMERG_V07_Final**：不使用 Early/Late 替代，不混用 V07/V08；V07 是算法版本、Final Run 是延迟处理流、2025 Final Test 是项目封存数据划分，三者没有被合并。
- NASA 2023-07-13 官方说明被正确解释为：Final 为卫星--雨量站融合估计，月尺度站点分析到达后生成，仍含估计误差，不是无误差物理真值。本轮只核对公开说明，没有获取观测。

## 3. 证据分类与执行边界

以下边界保留正确：

- **参考一致性**：仅针对既有 2024 Dev 的 IMERG 标签一致性、限定消融和排序现象；2024 Dev 已反复使用，不据此宣称独立泛化。
- **外部真实性/Stage 4.5**：独立站点/雷达真值验证仍 `NOT_VERIFIED`；不能由同源 IMERG 评分替代，Stage 4.5 仍 `PARTIAL`。
- **确认性 E**：E 的“未参与拟合/方法选择”使用历史独立性，与观测源链独立性分开；未来未使用的 IMERG 人口不会仅因产品同源自动合格或被永久排除，须另行核查和批准；本轮不寻找/读取 E。
- **物理与业务**：对 IMERG 的改进不证明 DOTE 因果、DTFM 一般/多尺度优势、实时延迟、独立暴雨事件技能或业务验收。
- **717** 被明确定义为 IMERG 参考标签下的强雨像元时次，不是独立暴雨场次；独立事件仍 `NOT_IDENTIFIED`。
- 2025 Final Test 继续封存；本轮没有数据下载、账户/联系、载荷读取、训练/推理/校准/bootstrap/评价或最终模型选择。

## 4. 失败检查与保存

- `VERIFICATION` 保留首次 **25.63934pt overfull** 失败（TeX 116–117），并说明在最终 PDF 复制、Git 暂存/提交/推送或交审前停止；随后把标签定义拆段并重新编译/渲染。另有新增行 CRLF 的 diff-check 失败，修正后重验。
- 未发现失败后被冒充通过；最终 12 页 PDF、无 overfull/缺字、旧 `_3` PDF 保持原字节。
- README/STAGE 历史后缀、gates/index 历史前缀未在本审核中逐字重算；`VERIFICATION` 的自检状态保留为文档自检，不升级为本轮独立全量审计。

## 5. 非阻断观察

1. `REFERENCE_SCOPE` 中研究者语句为归一化解释，逐字原文保存在私有 baseline；这符合隐私/脱敏要求，但后续引用时应保持“归一化”标签。
2. `VERIFICATION` 的视觉检查覆盖页面 1/3/5/7/8/9/10/12，2/4/6/11 继承已审布局；本审核独立核对页数、文件指纹、tex 内容和关键页文本，未做逐页像素级复核。
3. `VERIFICATION.protected_shared_unchanged_before_own_append` 属 Codex 自报保护快照；本轮未重查 Shared 全部文件。
4. NASA 官方 HTML 只核对说明文本与 URL，未取得观测载荷或独立验证证据；IMERG 仍是监督参考，不是外部物理真值。

## 6. 结论与状态

**PASS**：研究者资料事实的条件性表述、IMERG_V07_Final 冻结语义、V07/Final Run/2025 Final Test 的区分、参考一致性与外部真实性/确认性 E/物理业务证据的分层，以及 8 文件差异和失败修正记录，均通过本轮限定核对。

该 PASS 不构成新数据/实验授权、Stage 4.5 完成、独立外部验证或研究者掌握确认。

- 工程：**PASS（限定文档与证据边界审查；Git 以实际回执为准）**
- 科学：**NOT_VERIFIED**
- 研究者掌握：**NOT_ASSESSED**

本轮未读取 NPZ/预测/标签/权重/原始气象/2025，未下载观测、未登录/联系单位、未训练/推理/评价/校准/bootstrap，未修改 Codex/PROJECT_STATE/共同决策或规则。
