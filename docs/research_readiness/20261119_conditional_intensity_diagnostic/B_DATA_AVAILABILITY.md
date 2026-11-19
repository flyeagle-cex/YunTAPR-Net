# B：全人口 Dev 读出数据可用性清点

日期：2026-11-19
范围：只读检查已登记的公开证据与本地山区配对评价交付的文件/JSON键/SQLite表结构；没有读取气象源或模型权重，没有训练、推理或指标重算。

## 当前发现

| 所需字段 | 仓库当前可见证据 | 状态 |
|---|---|---|
| 全体有效像元时间的发生概率 `p` | 山区配对收据中的汇总指标/空间时次聚合 | 未发现逐像元预测数组 |
| 32 个条件 `qlog` 节点 | 强雨子集的节点计数与物理量均值 | 未发现全人口节点数组 |
| 与预测逐像元对齐的真值 | 总体计数及强雨子集摘要 | 未发现可与全人口节点一一配对的真值数组 |
| 有效/监督 mask | 既有协议身份和聚合指标 | 未发现本次全人口预测对应的逐像元 mask |
| 模型/检查点/清单身份映射 | 公开评价收据中的模型与范围字段 | 尚不足以证明上述预测数组存在且绑定 B7/seed2029/COSINE9/E9 |

已查看的项目证据：`docs/research_readiness/20261115_mountain_pair_results/CONDITIONAL_INTENSITY_EVIDENCE.json`、`PAIRED_METRICS.json`、`TERMINAL_VERIFICATION.json`、`STAGE_STATUS.json`，以及山区配对本地交付的文件清单和结构元数据。该本地交付共 33 个文件（17 JSON、14 SQLite、2 日志）；SQLite 表仅为分数聚合或读取记账，JSON 为完成收据、汇总指标、人口分组统计等，没有独立逐像元预测数组。私有文件的完整相对路径、SHA256 和字节数保存在被 Git 忽略的 `.local/conditional_intensity_inventory_v1/SCOPED_MANIFEST.json`，没有同步到公开仓库。仓库 `outputs/01a1a906-f017-71f3-bb3f-19b961274f10` 是另一评价交付目录，现有公开收据与工作簿不构成本轮逐像元模型输出。

## 结论边界与下一步

**公开证据和已绑定的山区配对本地结果目录中，均未发现可直接复用的身份绑定全人口数组。** 该否证范围已按路径、文件大小和 SHA256 留存；不涵盖其它未绑定的外部存储位置。当前结论足以判定本项目已登记的两臂评价产物不能直接重建 `p/qlog/truth/mask`，仍不能启动 Dev 推理。

后续如发现其它候选文件，只做文件清单和身份元数据核对，目标字段限于 `p`、32 个 `qlog`、真值和 mask，并核对模型哈希、E9 检查点身份、Dev 样本清单和输出精度。遇到需打开气象源/权重、计算预测或统计的入口即停止。当前已登记评价交付确认缺少完整数组；固定 E9 2024 Dev 前向评价必须另行准备预算与批准提案，不把 A 的训练梯度诊断并入该提案。

## 2026-11-19 网页总控复核后的身份与工程结论

- 固定人口身份从已保存 REAL/COSINE9 `recomputed_report.json` 和冻结 `EVIDENCE_INDEX.md` 交叉绑定：population `2f2cc75c…`、populations 文件 `ea6abae6…`、statistics `53ab2f07…`、target QC `b4bad8ea…`、实际 Dev 场景顺序 `91630241…`、partition `01b95f12…`。旧提案字段 `dev_source_manifest_sha256=65e8…` 未在绑定收据中找到，已移除，不再作为有效身份依据。
- 冻结量化输出实现明确 `qlog[:,0] > log1p(0.1)`，并检查有限值和严格递增；这项 preflight 合同有代码依据。
- `e8d2a9b` 的配对 worker 不保存全人口数组。它只有聚合输出与 `strong_joint_pixels.npz` 强雨子集，因此 B 所需单臂数组导出入口仍未实现，不能用旧代码 SHA 冒充该入口身份。
- 标签/打开次数已澄清：`stage4/data.py` 将 IMERG `imerg_YYYYMMDD.nc` 目标文件放入与卫星/GFS相同的 `ReaderFactory` 去重 source plan，并由同一个 source meter 计数。因此现有 7,950 个 Development 来源已含真值来源，不再额外加 963 个标签文件打开；加 static 1 次和 checkpoint SHA/加载各 1 次，payload reference 为 7,953 opens。
- 预算参考量未见超限矛盾：payload `26,747,379,582 B` / 7,953 opens 对比 `28,000,000,000 B` / 8,100 opens；metadata `195,653,265 B` / 144 opens 对比 `250,000,000 B` / 160 opens。合计 source 上限是 `28,250,000,000 B`。7,200 秒为最大硬上限，不是预计运行时长。这些仍是草案上限，不能启动运行。
- 当前阶段调整为 `B_READOUT_EXPORTER_BLOCKED_NO_COMPUTE_AUTHORIZATION`。下一步只准备单臂 exporter/entry 并绑定清洁代码 commit，再做一次最小合成检查；完成后才提交一次限定审核与单独计算批准。

网页总控裁定 A/B 分项授权、先 B 后 A。任何新 Dev 前向或 A 的训练集反向计算仍须分别明确预算与批准。2025 Final Test 保持封存。
