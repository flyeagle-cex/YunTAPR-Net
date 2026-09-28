# YunTAPR-Net Stage-0 / P0 数据工程审计

最终状态：**NEEDS_REVIEW**。工程执行：**PASS**。

本轮目录：F:\pytorch\Research\outputs\stage0_p0_audit\run_20260927T161311_417313Z。此前 Himawari Stage-0 dry-run 报告与诊断 cache 均未修改。

- IMERG：2465 个文件；Himawari：仅 2024-07 的 4390 个文件。
- pytest：29 个测试，failures/errors=0。最终结果见 tests/pytest_final_output.txt 和 tests/pytest_final.xml。
- 原始 F/H 数据完整性核验：True。全部 6855 个原件大小和修改时间复核，两库共 10 个跨时段样本 SHA256 再核验。这不是全库内容哈希证明；所有原件只读打开。
- IMERG needs_review 文件数=0；Himawari anomaly_type={'LATENCY_TAIL_REVIEW': 44}。若只有 LATENCY_TAIL_REVIEW，则 NEEDS_REVIEW 表示等待研究者查看尾部，不代表工程失败或数据错误。
- 只新增本任务明确要求的 pytest 及 4 个缺失依赖，全部原有包版本未变。日志：logs/dependency_change_record.json。
- Windows 中文路径 netCDF4 问题已复现，逐文件复制到 F:\pytorch\Research\cache\stage0_p0_audit\run_20260927T161311_417313Z，检查大小并抽检 SHA256，仅清理本流程创建的英文副本，未复制整个原始库。
- 缓存统计：{"copy_count": 6855, "cumulative_copied_bytes": 22106487072, "max_single_copy_bytes": 5935249, "copy_seconds": 71.53838880013063, "read_and_analysis_seconds": 186.09811650042684, "cleanup_failures": 0, "remaining_staged_nc_bytes": 0}。累计复制字节是 I/O 流量，不是持久占用。
- 数据审计耗时：IMERG 176.272 s；Himawari 135.882 s。按单文件/分块处理，没有把整个数据库载入 RAM。
- 单文件异常写入对应 status/error 和日志并继续，未隐瞒或自动修复。

## 输出导航

IMERG/：库存、年度库存、缺日/重复日期、元数据、时间、网格逐值/hash、降水 QC、QI、极值示例及完整 16 项总结。
HIMAWARI_202407/：逐文件时间原值/UTC 解析、延迟分布、分类异常、因果性反例与完整 10 项总结。
tests/：科学逻辑、中文路径 fallback、安全测试与 pytest 结果。
logs/：环境、精确依赖变更、运行日志、源码 hash、源文件完整性、缓存 I/O 和输出核验。
config.json：所有工程规则；audit_final_status.json：最终状态；output_manifest.csv：全部输出路径。

## 研究者本人仍需决定

正式研究年份不因库存更长而改变；降水极值的科学解释、44 个延迟尾部样本的复核、延迟尾部成因由研究者判断。p99 不是剔除/QC/科研阈值。operational availability 需要当前 metadata 之外的链路证据。

首次 pytest 跨盘收集触及系统目录而失败，初始 XML 保留；随后通过 rootdir/confcutdir/cwd 限定测试范围，最终测试真实执行。没有将 NOT_RUN 当作 PASS。

没有模型训练、归一化、划分训练集、重采样、空间插值、IMERG/Himawari 网格对齐、GFS/DEM 处理、重建配对库、Dataset、bbox 修改或全量 Himawari 预处理。全部描述统计为 QC_STAT_ONLY。QI 没有筛选阈值，没有作为模型输入。

Stage-0 P0 engineering audit complete.
Waiting for researcher review.
No scientific convention was changed automatically.
