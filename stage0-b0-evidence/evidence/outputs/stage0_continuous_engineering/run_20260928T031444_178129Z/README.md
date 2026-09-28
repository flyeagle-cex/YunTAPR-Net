# YunTAPR-Net Stage-0 continuous engineering run

状态 NEEDS_REVIEW。阅读 FINAL_CONTINUOUS_ENGINEERING_REPORT.md 与 RESEARCHER_DECISIONS_REQUIRED.md。
本轮目录：F:\pytorch\Research\outputs\stage0_continuous_engineering\run_20260928T031444_178129Z。原始数据不在输出目录，全部只读；以前 run 不覆盖。

## 已执行范围与主要文件

- IMERG/：仅2025-06-23和24跨日像元/5×5 patch检查。
- GFS/：主目录全部24,388文件的inventory、grid hash、variable mapping/coverage、time semantics、禁用降水清单、84个月calendar coverage、冲突表与缺口表。
- CROSS_SOURCE/：24研究月矩阵、空间范围与候选数值交集、SRTM ZIP目录、云南polygon存在证据。
- docs/DECISION_LOG_STAGE0.md：五类决策状态；schemas/sample_index_schema.md：定义但未实例化。
- tests/pytest_verified.xml：30 tests passed；logs/：环境、依赖import、staging、raw完整性、CSV/Parquet回读、各阶段结果与日志。
- CSV使用UTF-8 BOM，Parquet使用已有pyarrow/snappy。复杂metadata嵌套结构在CSV中存JSON文本，原文完整保留。Parquet回读等于对应CSV解析结果；不保证CSV能恢复原NetCDF底层dtype，原dtype/属性另存metadata。

## 解释器与重现

解释器固定：F:\pytorch\Research\.venv\Scripts\python.exe。不安装/升级环境包。
脚本从自身位置推导 OUT；重跑必须新建 run_<UTC_TIMESTAMP>，只复制 src/ 与 tests/ 到新目录并创建 docs/IMERG/GFS/CROSS_SOURCE/schemas/logs。
新目录内依序执行：

1. python -B src/gfs_audit.py
2. python -B src/independent_tasks.py
3. python -B src/analyze_results.py
4. python -B src/finish_tables.py
5. python -B -m pytest tests/test_continuous.py -q -p no:cacheprovider --rootdir . --confcutdir . --import-mode importlib --basetemp <new English cache test directory> --junitxml tests/pytest_verified.xml
6. python -B src/write_reports.py
7. python -B src/validate_outputs.py

以上 python 必须替换为前述绝对路径。环境快照/environment_before.json 和静态decision/schema文档需按本run保存的值作为模板在新run开始时重新生成；不能直接用旧时间/旧环境伪装新快照。src/config.py中的前次审计路径是明确证据引用。不得原地重跑覆盖此run；输出创建默认exclusive。finish_tables仅修整本run新表，不触及旧run。

## 英文路径兼容与额外I/O

netCDF4通过 F:\pytorch\Research\cache\stage0_continuous_engineering\run_20260928T031444_178129Z 的独立临时英文文件读数据。每个Reader同一时刻一个源文件，复制后校验大小，关键样本校验SHA256，读完清理；GFS与IMERG独立任务曾可能短暂重叠。
配置总staging阈值128MiB、剩余磁盘最低512MiB；单生产副本最大 1,371,753 bytes。两个独立reader的并发检查不是跨进程原子配额锁；本轮输入最大文件和两个reader的边界使实际候选副本远低于阈值。未仪器化测全局峰值，不报告伪精确峰值。
累计复制 6,910,634,531 bytes，copy 41.044s，read 179.701s；清理失败0。它们是额外I/O成本与调用累计耗时，没有永久保存GFS整库或Himawari19GiB副本。
cache中pytest合成文件保留便于追踪，生产staging nc副本为0。允许删除的只有流程自己创建的本轮临时副本，未操作任何H盘原始文件/旧diagnostic缓存。

## 证据复用和限制

IMERG全库与Himawari 2024-07旧证据路径分别为 F:\pytorch\Research\outputs\stage0_p0_audit\run_20260927T161311_417313Z 和 F:\pytorch\Research\stage0_himawari\outputs\202407\resume_20260927T104625_772423Z。
没有重新运行旧storage benchmark或Himawari全月处理；当前任务是连续P0审计。
月矩阵GFS_inventory_status仅检查观测schedule参考，GFS_available还要求核心变量。NOT_AUDITED不等于PASS、MISSING或坏数据。
未来availability未知不能用mtime/creation/init代替。上游+5h代理保留原文但未采纳。当前CF时间一致不抹去udunits/history来源冲突。
空间交集不是正式bbox或共同有效像元mask；SRTM未解压栅格，Yunnan polygon不是已经验证的评价mask。
