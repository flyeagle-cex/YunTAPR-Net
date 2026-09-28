# YunTAPR-Net Stage-0 continuous engineering run

状态 NEEDS_REVIEW。阅读 FINAL_CONTINUOUS_ENGINEERING_REPORT.md 与 RESEARCHER_DECISIONS_REQUIRED.md。
本轮目录：F:\pytorch\Research\outputs\stage0_continuous_engineering\run_20260928T041855_828904Z。原始数据不在输出目录，全部只读；以前 run 不覆盖。

## 已执行范围与主要文件

- IMERG/：仅2025-06-23和24跨日像元/5×5 patch检查。
- GFS/：主目录全部24,388文件的inventory、grid hash、variable mapping/coverage、time semantics、禁用降水清单、84个月calendar coverage、冲突表与缺口表。
- CROSS_SOURCE/：24研究月矩阵、空间范围与候选数值交集、SRTM ZIP目录、云南polygon存在证据。
- docs/DECISION_LOG_STAGE0.md：五类决策状态；schemas/sample_index_schema.md：定义但未实例化。
- tests/pytest_verified.xml：33 tests passed；logs/：环境、依赖import、staging、raw完整性、CSV/Parquet回读、各阶段结果与日志。
- CSV使用UTF-8 BOM，Parquet使用已有pyarrow/snappy。复杂metadata嵌套结构在CSV中存JSON文本，原文完整保留。Parquet回读等于对应CSV解析结果；不保证CSV能恢复原NetCDF底层dtype，原dtype/属性另存metadata。

## 解释器与重现

固定解释器：F:\pytorch\Research\.venv\Scripts\python.exe。没有安装或升级任何依赖。
本轮从先前已验证代码复制到全新run后增强，旧run与raw永久只读。不要在已完成run原地重跑；写文件默认exclusive。

准备新run时只复制src、tests的.py代码以及docs/schema模板，创建输出子目录和新的英文cache父目录；生成当次environment_before.json、baseline_reference_hashes_before.json。src/config.py从自己的位置推导OUT；基线引用明确保留。报告模板中的快照数值和断言适用于这次审计，若未来raw库存变化必须先审核更新报告/验证期望，不能把旧数值作为新结果。

使用上述绝对解释器，在新run的cwd按顺序执行：
1. src/gfs_audit.py
2. src/independent_tasks.py
3. src/analyze_results.py
4. src/current_additions.py
5. src/finish_tables.py
6. src/run_tests.py
7. src/write_reports.py
8. src/current_closeout.py
9. src/validate_outputs.py
10. src/final_manifest.py

每条命令格式为 & 'F:\pytorch\Research\.venv\Scripts\python.exe' -B <script>。本轮脚本只在newrun写输出。
run_tests.py明确限定cwd/rootdir/test path，先创建cache父目录；若pytest basetemp已存在会拒绝，避免pytest隐式删除既有测试目录。
tests/pytest_initial.xml保存首次27 passed/6 setup errors，修复说明见logs/engineering_recovery.json；tests/pytest_final_output.txt和pytest_final.xml是最终真实执行结果，pytest_verified.xml只是同一次最终执行XML的兼容别名。
本轮禁止调用任何源数据下载、Dataset、split、归一化、训练或插值入口。

## 英文路径兼容与额外I/O

netCDF4通过 F:\pytorch\Research\cache\stage0_continuous_engineering\run_20260928T041855_828904Z 的独立临时英文文件读数据。每个Reader同一时刻一个源文件，复制后校验大小，关键样本校验SHA256，读完清理；GFS与IMERG独立任务曾可能短暂重叠。
配置总staging阈值128MiB、剩余磁盘最低512MiB；单生产副本最大 1,371,753 bytes。两个独立reader的并发检查不是跨进程原子配额锁；本轮输入最大文件和两个reader的边界使实际候选副本远低于阈值。未仪器化测全局峰值，不报告伪精确峰值。
累计复制 6,910,634,531 bytes，copy 34.176s，read 180.298s；清理失败0。它们是额外I/O成本与调用累计耗时，没有永久保存GFS整库或Himawari19GiB副本。
cache中pytest合成文件保留便于追踪，生产staging nc副本为0。允许删除的只有流程自己创建的本轮临时副本，未操作任何H盘原始文件/旧diagnostic缓存。

## 证据复用和限制

IMERG全库与Himawari 2024-07旧证据路径分别为 F:\pytorch\Research\outputs\stage0_p0_audit\run_20260927T161311_417313Z 和 F:\pytorch\Research\stage0_himawari\outputs\202407\resume_20260927T104625_772423Z。
没有重新运行旧storage benchmark或Himawari全月处理；当前任务是连续P0审计。
月矩阵GFS_inventory_status仅检查观测schedule参考，GFS_available还要求核心变量。NOT_AUDITED不等于PASS、MISSING或坏数据。
未来availability未知不能用mtime/creation/init代替。上游+5h代理保留原文但未采纳。当前CF时间一致不抹去udunits/history来源冲突。
空间交集不是正式bbox或共同有效像元mask；SRTM未解压栅格，Yunnan polygon不是已经验证的评价mask。

## 本轮正式收口入口

audit_final_status.json 区分 engineering_status/researcher_review_status/gfs_status；stage0_closeout_ready=false 不代表存在未完成的安全独立工程任务。完整 inventory summary、distinct time metadata、原始before manifest及最终pytest日志均在本run。
