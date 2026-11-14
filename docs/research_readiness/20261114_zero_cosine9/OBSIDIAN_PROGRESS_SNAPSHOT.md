---
type: research-progress-snapshot
project: YunTAPR-Net
date: 2026-11-14
engineering: PASS
scientific: NOT_VERIFIED
researcher_knowledge: NOT_ASSESSED
harness_review: PENDING
---

# ZERO_DOTE / COSINE9 配对实验终态与指标

日期：2026-11-14（北京时间）

## 执行终态

- 工程状态：**PASS**。执行收据为 `COMPLETE_TRAIN_AND_DEV_EVALUATION`；退出码 0，4,320/4,320 更新、9/9 轮封口；未发生自动重试。
- 执行额度：逻辑源读取 477,571,953,840 字节、142,813 次文件打开；总耗时约 16,228 秒（4小时30分28秒），低于批准的 21,600 秒。审批额度已消费。
- 科学状态：**NOT_VERIFIED**。研究者知识掌握：**NOT_ASSESSED**。证据等级：本地保存的执行/结果收据为 **DIRECT_VERIFIED**；未取得 Harness 独立复核，不是 CROSS_VERIFIED。
- 实验代码绑定：`b4f15fb8dfeced23c28824f04b35158077678950`。ZERO 使用 `ZERO_NUMERIC_RETAIN_REAL_MASKS`，与已完成 REAL/COSINE9 在同一 B7 / E0 / seed 2029 / COSINE9 / 固定 E9 条件下作开发集配对。

## 2024 Development 配对指标

下表保留原值和绝对差，差值定义为 **REAL − ZERO**；相对差以 ZERO 为分母。对损失和 Brier，负差有利于 REAL；对 AP/AUROC，正差有利于 REAL。

| 指标 | REAL | ZERO | REAL − ZERO | 相对 ZERO |
|---|---:|---:|---:|---:|
| 全部有雨 log Pinball（主指标） | 0.1258183285 | 0.1257368882 | +0.0000814403 | +0.0648% |
| 全部有雨物理 Pinball / 20 | 0.0193650747 | 0.0193550671 | +0.0000100076 | +0.0517% |
| R>20 log Pinball | 0.8084225693 | 0.8056557191 | +0.0027668502 | +0.3434% |
| R>20 物理 Pinball / 20 | 0.5068646309 | 0.5059964290 | +0.0008682019 | +0.1716% |
| 弱雨 (0.1, 1] log Pinball | 0.0887223116 | 0.0886446608 | +0.0000776508 | +0.0876% |
| 发生 Brier | 0.0923301557 | 0.0923677483 | −0.0000375926 | −0.0407% |
| 发生 AP | 0.6066547556 | 0.6068104663 | −0.0001557108 | −0.0257% |
| 发生 AUROC | 0.8990243639 | 0.8991912417 | −0.0001668778 | −0.0186% |

解释：主指标方向未达到预设的 REAL 优于 ZERO（期望差值 < 0）；强雨及弱雨损失方向也不利于 REAL。Brier 小幅有利于 REAL，而 AP/AUROC 小幅不利，判别指标方向不一致。此结果不支持“DEM/DOTE 显式数值输入带来明确开发集增益”的主张；亦不能据一次单 seed 配对认定 DOTE 无效或存在因果关系。

## 评价人口与范围

- 2024 Development：963 个场景、3,303,090 个有效像元时次；有雨 407,820 个像元时次；R>20 为 717 个像元时次。
- R>20 数量是像元时次，不是独立暴雨事件。独立天气事件数未识别。
- 保存了全部评价组（all、四个 UTC 分组、scene_max_ge20）及七个雨强箱的差值；各分组方向并不统一，需查明事件/时段依赖后再解释。
- 本包**没有**新增 POD/FAR/CSI 等点雨强分类读数、P20/AP20、高程或 W/M 地形分层。因此不报告本包的 POD/FAR；先前 REAL/E0 与 REAL/COSINE9 的点分类结果不能冒充 ZERO 配对读数。

## 解释限制

单 seed 2029、同一 Development 数据参与开发决策；没有跨 seed 稳定性或独立泛化证据。REAL 复用历史模型，对照完整 driver/cuDNN 指纹存在缺口；ZERO 保留真实有效性 mask，128 个零输入投影权重无损失梯度，AdamW 衰减仍可能改变其值。结果只衡量本结构与 mask 条件下的显式数值输入效用，不能证明物理因果或机制。2025 Final Test 未访问。

## 结果来源

配对统计 JSON：`real_zero_descriptive_comparison.json`（原件位于本地忽略的执行目录；此处不复制含原始数据或权重的私有载荷）。其 SHA256：`5582346abcb16504b0a69f703e8cad2b93b99c8cff564298bc62a261a135791a`。终态收据摘要见同目录 `TERMINAL_VERIFICATION.json`。本次核对未读取、复制或计算模型权重载荷。
