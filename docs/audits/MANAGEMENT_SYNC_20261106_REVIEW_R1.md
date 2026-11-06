# 2026-11-06 管理归档 R1 限定复核

- 审核者：Harness（独立于 Codex）
- 基准审核：`MANAGEMENT_SYNC_20261106_REVIEW.md`（针对 Codex `9b02e2c`；结论 NEEDS_REVISION）
- R1 对象：Codex `collab/codex-20261102` 的 `fc608c78bb4170d99104ae09490d7455a67aaee2`
- 精确变更：README.md、STAGE_ACCEPTANCE.md、REVIEW_INDEX.md、新增 MANAGEMENT_REVIEW_R1_RECEIPT.json
- 本轮范围：只复核 F1/F2/F3 登记及 R1 回执；不重做 T15–T17 科学审计，不读取 NPZ/权重/2025，不新增计算。

## 1. 结论

**R1 限定复核：PASS。**

F1 已补齐 B3_DOTE_ONLY 与 V3 九模型的范围及 AP 标签区别；F2 已如实登记两个批准时间及同一规则 SHA，并明确待研究者裁定；F3 已用独立修订回执记录审核送达，原 MANAGEMENT_RECEIPT 保留为 `9b02e2c` 历史快照。修订链未把原 NEEDS_REVISION 改写成 Harness 通过，也未改变 H1/H2 的 NOT_VERIFIED。

## 2. 已核实事实

### 2.1 变更范围与指纹

`git diff --name-status 9b02e2c..fc608c78` 仅返回：

- M README.md
- M STAGE_ACCEPTANCE.md
- A docs/research_readiness/20261106_research_convergence/MANAGEMENT_REVIEW_R1_RECEIPT.json
- M docs/research_readiness/20261106_research_convergence/REVIEW_INDEX.md

当前文件指纹与 MANAGEMENT_REVIEW_R1_RECEIPT.json 一致：

| 文件 | 字节 | SHA256 |
|---|---:|---|
| README.md | 13,743 | `C229118FBDF6D6E5095895B982A02FD5FCD5BEFA9C87079A993CAC80EDECA537` |
| STAGE_ACCEPTANCE.md | 25,782 | `6CE77E8D298B8919EA4D1FCD4E8409351D6257E0EDCCC7AFE85D7663FA456DB0` |
| REVIEW_INDEX.md | 6,702 | `E6667BE15B4B179229AE14830D83D9929392FC64CA6AEE5A036068047EFB4F36` |
| MANAGEMENT_REVIEW_R1_RECEIPT.json | 2,694 | `6A43AAFF3392C33D730038C7D37D5610DF9A9B5AE2CD9D4079F671FCD5BF2F28` |

历史 `MANAGEMENT_RECEIPT.json` 当前字节/指纹仍为 **3,618 B / `4B89CA4167EA32B67D21E477F965374D476ED531E3DB3DEE47EC14EA65B27A42`**，与 R1 回执的 `prior_receipt` 一致；R1 未改写该历史快照。

### 2.2 F1：B3_DOTE_ONLY 范围

README.md、STAGE_ACCEPTANCE.md、REVIEW_INDEX.md 均已明确：

- B3_DOTE_ONLY/seed2029 是单 seed 既有收据，处于原 V3 九模型比较范围之外；
- 其 AP 使用降水发生标签，与强雨排序 AP 不是同一标签；
- 强雨点 TP/FP/FN=0/0/717 与单 seed 局限保留。

该修订准确覆盖原 NEEDS_REVISION F1，未引入对 B3_DOTE_ONLY 的额外科学结论。

### 2.3 F2：重复批准记录

REVIEW_INDEX.md 现在直接登记：

- 两个 `YT-GOV-20261105-001` 时间：2026-11-05 08:31:04 与 08:41:55；
- 两者均记 APPROVED，引用同一规则 SHA256 `8631C186735E46DDFE7D07CC5DB2D82CF8E4F484AFDCD100F98510CDC6072440`；
- 唯一正式时间及重复处置待研究者裁定；
- DECISIONS 原账本未被编辑，未代选时间或新增编号。

这正确地**登记了歧义**，没有把歧义擅自解决，也没有把两条记录伪造成唯一批准。F2 仍须研究者最终处置，但不阻塞本次限定复核。

### 2.4 F3：回执与历史快照绑定

MANAGEMENT_REVIEW_R1_RECEIPT.json：

- 绑定 base `9b02e2c`；
- 记录原审核文件 `MANAGEMENT_SYNC_20261106_REVIEW.md` 6,608 B / `C15833E5...C27AAC8` 及 NEEDS_REVISION；
- 保留原 MANAGEMENT_RECEIPT 的 SHA 与历史快照身份；
- 记录 Harness Git 同步仍 PENDING；
- 未新增训练/推理/校准/科学计算，2025 仍 FROZEN。

原审核（NEEDS_REVISION）与 R1 限定复核（PASS）分别保留，没有用 R1 覆盖或改写原结论。

## 3. 保留的边界

- 本 R1 PASS 只表示 **F1/F2 登记及 R1 管理回执**通过，不构成 T15–T17 科学通过，也不构成 T16-R1 第二轮 Harness 科学审查通过。
- H1/H2 仍为 INCONCLUSIVE / INDEPENDENT_NOT_VERIFIED；研究者掌握 NOT_ASSESSED。
- F2 的正式批准时间仍待研究者裁定；本复核不提供该裁定。
- 本复核未读取 NPZ/气象源/权重，未重算指标，未训练/推理/校准，未访问 2025，未修改 ACL/环境。

## 4. Git 回执

- DSH 分支：`collab/dsh-20261102`；本轮开始 HEAD：`f8878eddeb0699d3ab22f5ad829dca1bfd5a0eec`
- 本地提交与远端核对结果记录在 Shared/DSH.md 的对应追加段及最终回执中；本文件不预填尚未发生的 SHA。
