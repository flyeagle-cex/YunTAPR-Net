# Stage 4.5 公开外部参考元数据｜限定独立审核

- 审核者：Harness（独立于 Codex）
- 审核对象：`METADATA_FEASIBILITY.json`、`VERIFICATION.json`、`YunTAPR-Net_Master_Plan_Live.tex`、LIVE-20261106.2 PDF、README/STAGE/REVIEW_INDEX 当前进度入口，以及本地保存的公开元数据/HTTP 回执
- 范围：只查公开出处、参数、响应指纹、元数据与观测载荷的区分、保存覆盖及执行边界；未重算预测/标签指标，未训练/推理/校准/bootstrap
- 结论：**PASS（限定公开元数据准备）**

## 1. 元数据身份与指纹

本地 9 份原始公开元数据/回执的字节与 SHA256 均与 `METADATA_FEASIBILITY.json` 一致，包括：

- `homr_kunming_2023_2024.json`：2,747 B / `933EB3A1...574B8F`
- `cmr_2adpr_v07_collection.json`：30,731 B / `BE4922C0...8762BA`
- `cmr_2adpr_v07_2023_discovery.json`：20,411 B / `B6F5C387...B39B1A`
- `cmr_2adpr_v07_2024_discovery.json`：20,395 B / `465B4BF2...4A978`
- `ghcnh_documentation.pdf`：423,879 B / `DF5694EF...F591B7`
- `ghcnh-station-list.txt`：3,459,429 B / `FF451FAF...D4182A`
- 三份 attempt receipt：7,843/26,829/17,627 B，SHA 均与汇总一致

`METADATA_FEASIBILITY.json`（13,377 B / `D44F6DF0...2E79E1`）、`VERIFICATION.json`（2,837 B / `D200B276...B2A0F2`）、计划 tex（24,576 B / `CC55570C...B17A2`）、新版 PDF（459,643 B / `A87BF0C2...B81EC6`）均与保存记录一致；旧 Live.pdf 仍为 **436,565 B / `2F20DBBB...D6DCD11`**，未被覆盖。

## 2. 官方出处与参数

- HOMR 昆明查询返回 **2 条身份记录**；其中 WMO 56778 / GHCND `CHM00056778`、坐标约 25.017°N/102.683°E、海拔 1892 m。期间字段为 `Unknown/Present`，不能据此证明 2023/2024 实际小时降水覆盖。
- GHCNh 官方身份表为 **3,459,429 B**；在发现框 98–107°E、21–30°N 内实测 **176 条身份记录**。这包含境外站、历史别名和不同网络记录，**不是 176 个云南可用雨量站**，也不是省界内独立站点数。
- `CHM00056778` 未出现在检索到的 GHCNh 表中；`CHU00056778` 及 WUJIABA 等昆明条目存在，但摘要没有自动把 CHU 与 CHM 绑定或替换。该 `NOT_VERIFIED` 处理正确。
- CMR 集合 `C2179081499-GES_DISC`（`GPM_2ADPR / 07`）在发现框、2023-03-01–2023-10-31 与 2024-03-01–2024-10-31 的命中数分别为 **325/324**；每年按开始时间仅保存前 **3** 条元数据。命中和示例均不是全省配对像元、可用雨强、独立事件或有效验证样本。
- 保存示例 2023 为 V07A、2024 为 V07C；摘要明确不推断所有颗粒版本、不无说明混用。正确。
- `attempt_02/03` HTTP 回执与 7 次 GET 的记录一致：6 次成功、1 次 404、0 重试，6 个响应体合计 3,957,592 B；没有观测载荷。该统计与本地文件字节相加一致。

## 3. 元数据与观测载荷的区分

以下边界均保留正确：

- 本轮仅有官方公开产品文档、站号身份、CMR 元数据和 HTTP 回执；**没有下载降水观测、没有登录/申请权限、没有读取预测/标签/权重/气象源或 2025 Final Test**。
- 176 是发现框身份记录，不是云南可用站数；HOMR 的 `Unknown/Present` 不是历史覆盖；CMR 325/324 是目录命中，不是实际重叠或事件数；每年 3 条示例不是完整档案。
- GHCNh 降水元素可能具有可变累计间隔，小时/半小时可用性、QC、站号历史与 GPCC/GTS 源链仍未核实；CMA 近 7 日/月值产品不能替代历史小时降水；雷达目录存在不等于历史 QPE 产品、许可或观测载荷可用。
- DPR 与 IMERG 存在共享上游链（NASA 文档所述 CORRA 使用 DPR/GMI），不能把 DPR 判为完全独立真值；`ALGORITHM_LINKED / OBSERVATION_LINKED_CANDIDATE` 的保留合理。
- 没有把上述元数据准备写成 Stage 4.5 完成、独立验证通过或科学验收。

## 4. 计划书与入口

- 新版计划 PDF 为 **10 页 / 459,643 B / `A87BF0C2...B81EC6`**，tex 为 LIVE-20261106.2；旧 436,565 B PDF 原字节保留。README、STAGE、REVIEW_INDEX 当前入口均指向新版 PDF 与元数据收据，未把旧版误报为丢失或覆盖。
- 计划书明确 Stage 4.5 为 **PARTIAL**：元数据已取得，但实际观测、许可、源链、独立性和配准未完成；H1/H2 仍 INCONCLUSIVE / INDEPENDENT_NOT_VERIFIED，科学 NOT_VERIFIED，研究者掌握 NOT_ASSESSED。
- 未新增观测获取、模型执行、训练/推理/评价预算或 2025 访问；未改变原 V1.3 科学批准或共同决策。

## 5. 非阻断观察

1. PDF 的视觉检查记录为页面 1/3/6/7/8/10，2/4/5/9 继承旧版布局；本审核独立核对了页数、文件指纹、tex 内容和关键页文本，未做逐页像素级视觉复核。
2. `VERIFICATION.shared_protected_before_own_append` 的共享历史指纹属 Codex 自报保护快照；本轮未重查 Shared 全部文件，只核对本任务必要文件与不触碰 main/他人的边界。
3. 旧 v1.1 的最终测试范围、CMA 历史小时产品和雷达归档仍是待研究者/资料提供方确认的缺口，不应由本 PASS 自动补齐。

## 6. 结论与状态

**PASS**：官方出处、参数、响应指纹、176/325/324 的元数据含义、仅保存 3 条示例、V07A/V07C 差异、元数据与观测载荷分离，以及计划/README/STAGE/REVIEW_INDEX 的状态边界均通过本轮限定核对。该 PASS 不是观测验证、Stage 4.5 科学完成、数据/实验授权或研究者掌握确认。

- 工程：**PASS（限定公开元数据与文档审查；Git 以实际回执为准）**
- 科学：**NOT_VERIFIED**
- 研究者掌握：**NOT_ASSESSED**

本轮未读取 NPZ/真实标签/权重/气象源/2025，未下载观测、未训练/推理/评价/校准/bootstrap，未修改 ACL/配置/共同决策或 Codex 文件。
