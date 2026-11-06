# Q32-BASELINE-20261106.1｜限定独立审核

- 审核者：Harness（独立于 Codex）
- 审核对象：`docs/research_readiness/20261106_q32_baseline/{CONSENSUS,RESULT,ATTEMPT_V1_FAILED,VERIFICATION}.json`、`general_score_ranking.py`、`restore_saved_q32_ap.py`、DOTE lookup 边界修正、三份对应测试、README/STAGE/REVIEW_INDEX、LIVE.10 tex/PDF
- 范围：独立代码/收据审核，并在自身私有临时目录从逐字节副本运行 26 项新检查；未重新读取真实 NPZ/manifest/权重/缓存/2025，未重算实际数组 AP
- 结论：**PASS（限定代码/收据审核；不是独立逐像元复算）**

## 1. 当前指纹与保存

- Codex 起点 `43d10a9947100ff931e93af7fa4fd68bd4e02eeb`，当前 15 文件已暂存未提交。
- `VERIFICATION.json` 当前 14 个 artifact 指纹全部匹配；其自身为第 15 文件：
  - `general_score_ranking.py` 4,571 B；`restore_saved_q32_ap.py` 28,235 B
  - 三测试 6,331 / 13,438 / 12,984 B
  - `CONSENSUS.json` 11,461 B；`RESULT.json` 8,527 B；`ATTEMPT_V1_FAILED.json` 2,217 B
  - LIVE.10 PDF **18 页 / 617,386 B / `070AC82A...60E7`**；tex **46,533 B / `8EE83AA3...D3AE`**
  - README 22,939 B；STAGE 34,978 B；REVIEW_INDEX 24,376 B——均匹配
- 旧 LIVE.9 保留，599,761 B / `EF90ED55...A4085`。
- 私有 v2 receipt/parent/source_reads 分别为 `440BDCC7...22E0C`、`135845B0...1D4F`、`D577F8F1...94AD`；v1 对应 `B18E8606...6705`、`D0F76D73...C418`、`4F5AB546...33D`，与 RESULT/ATTEMPT 一致。
- `VERIFICATION` 说明 tex 在渲染后仅删除 3 个 TeX 表格行尾空白；当前 tex 46533 B，PDF 070A 对应渲染版；未发现内容/版面变化证据。

## 2. 26 项实际检查

因 DSH 的 `docs/audits` 目录创建被 ACL 拒绝，测试副本放在工作区根目录外的临时私有目录（非 Codex），字节 SHA 与 Codex 源一致后运行；完成后删除，未在 Codex 创建 fixture，未改 ACL。

从副本运行：

```text
python -X utf8 -B -m unittest -v \
  test_general_score_ranking \
  test_restore_saved_q32_ap \
  test_dote_direction_transform.DoteDirectionTransformTests.test_excluded_month_boundary_retains_original_manifest_and_accepted_population \
  test_dote_direction_transform.DoteDirectionTransformTests.test_excluded_rows_still_require_structure_half_hour_and_global_utc_uniqueness
```

结果：**Ran 26 tests, OK**；13 + 11 + 2，failures/errors/skips 均 0。未重跑旧 28/43/8，未读取真实科研数组。

## 3. 代码/收据审查

- `exact_score_ranking` 使用稳定排序、仅正例分数组的 group-end non-interpolated AP、half-credit grouped AUROC；显式拒绝非真实 1D、布尔/复数/非有限评分、掩码数组、空人口；整数/float64 不合并相邻值；测试覆盖手算值、全并列、整数边界、随机并列及单类未定义。
- `restore_saved_q32_ap` 固定 963/3430/717、9 metadata/363 archive、3,182,490,198 archive bytes、1 GiB RSS、600 s/5 s cleanup；完整读取才计数、读前/读后 fstat、SHA/大小、named source only、无 retry；ZIP/NumPy header/形状/dtype/对象数组/异常时间/分位顺序/跨 seed byte identity 均在 `np.load` 前后设门；AP 只按已存 q32 排序，不加载权重/不训练/不推理。
- DOTE lookup 边界修正保留完整原 manifest digest、全部行结构/半小时间隔/全局 analysis 唯一性；仅对原 plan accepted IDs 进行 2023/2024 年月准入，月末跨月拒绝行不被删除或改写；2 项新测试通过。
- 保存结果：v2 `RESULT.json` 报告三 seed 的 n=3,303,090、positive=717、wet=407,820、equal20=2、ge50=6；AP 分别 0.020566094533768432 / 0.014264745852766623 / 0.01350099359125544，AUROC 0.968765682493729 / 0.9682905938817696 / 0.968772956118832；三 seed 标签/像素字节哈希一致，E9 身份为继承元数据绑定。
- v1 在 2029 全部 121 archive 后排序分配 MemoryError，未产 AP，receipt/parent/source ledger 保留；没有重启或第三包。旧+新累计 archive 484 次/4,243,320,264 B、metadata 18 次/8,883,044 B；v1/v2 各自 retry0，但总计 2 次尝试/1 次纠正，未冒称零总重试。

## 4. 非阻断观察

1. 本审核只核对代码、收据和保存 AP 值，没有独立逐像元重算真实 AP；`RESULT` 的 AP 仍属执行方统计，不是 Harness 独立复算。
2. 当前 26 项新测试在私有工作区临时目录运行（DSH 目录 ACL 拒绝创建）；测试文件 SHA 与 Codex 当前测试一致，未写入 Codex，未改 ACL。
3. v1 MemoryError 的直接证据为 receipt 错误；分配点 commit/精确 1 GiB 超限原因未捕获，`ATTEMPT_V1_FAILED` 已如实保留 NOT_VERIFIED。
4. 旧 LIVE.9/旧 28/43/8 和历史来源身份继承，不重跑；`CONSENSUS` 的 AP20[q32] 为 PROPOSED/委托决定，不是 P20 校准、独立事件或 DOTE 对旋转的已验证结果。
5. `VERIFICATION` 自述的 6 个 agent 旧 mode0700 空临时目录仍不可读并触发 git 警告；它们不属于本 15 文件，未被删除/改 ACL。

## 5. 结论与状态

**PASS（限定代码/收据审核）**：当前 14 artifact 指纹一致；26 项新增检查通过；restore 的安全/计费/完整性门和 ranking 数学实现未发现阻断；v1 失败/v2 成功分开保留；实际 AP 值来自保存 receipt，未冒充独立数组复算。

- 工程：**PASS（限定代码/收据审核 + 26 项合成检查；Git 以实际回执为准）**
- 科学：**NOT_VERIFIED**
- 外部 Stage 4.5：**PARTIAL**
- 研究者掌握：**NOT_ASSESSED**

本轮未读取真实数据/标签/权重/训练 manifest/气象缓存/2025，未训练/推理/新评价/校准/bootstrap，未修改 Codex/Shared 共同决策/规则/main。
