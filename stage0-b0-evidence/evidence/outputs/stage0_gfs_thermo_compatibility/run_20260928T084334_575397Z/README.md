# GFS_thermo compatibility audit

工程状态PASS；兼容性PARTIALLY_COMPATIBLE；研究期结构覆盖READY candidate。先读最终报告、assessment与RESEARCHER_DECISIONS_REQUIRED.md。
OUT=F:\pytorch\Research\outputs\stage0_gfs_thermo_compatibility\run_20260928T084334_575397Z
Baseline=F:\pytorch\Research\outputs\stage0_continuous_engineering\run_20260928T041855_828904Z
Python=F:\pytorch\Research\.venv\Scripts\python.exe

只审计thermo全库，主库只使用既有审计和9个allowlisted样本。raw和旧输出只读；source_path拒绝未授权主库路径，所有输出限定当前OUT且默认exclusive创建。
初始化先创建全新run（exist_ok=False）、环境快照、baseline fingerprint与hash、全thermo size/mtime清单和9个主库样本allowlist/size/mtime/hash。目录碰撞拒绝；不能原地重跑覆盖本run。
代码使用本run的配置和证据快照，重现应新建run，更新config与初始化清单；不得复制旧时间日志冒充新执行。

依次运行main_samples.py、audit_thermo.py、pairing_audit.py、lineage_integrity.py、unit_pressure_audit.py、final_checks.py、write_reports.py、validate_delivery.py。独立结构probes写在logs/thermo_structure_probes.json；它们只用于reader/语义确认，不代替全库审计。
unit_pressure_compatibility.csv由两库原变量mapping表校验K/%/Pa后生成；README中的运行链需要保留该单位核验步骤。
final_checks.py限定pytest cwd/rootdir/confcutdir/test path并写真实stdout/XML，同时CSV/Parquet双格式回读；输出文件默认exclusive，不隐式复用失败执行。
SOURCE/GRID/TIME不确定项保留，不以UNKNOWN当PASS；source_lineage_status是声明metadata的证据分级，不是下载过的原始GRIB验证。
脚本中的assert与报告描述记录当前快照；未来库存变化须先更新期望，不能机械套用旧计数。

cache=F:\pytorch\Research\cache\stage0_gfs_thermo_compatibility\run_20260928T084334_575397Z；单文件复制、copy size校验、选定hash、netCDF4只读分析、只清理自己创建的副本。累计I/O是多次临时复制的总和，不是峰值占盘；生产staged bytes=0，pytest合成测试文件可保留。
native T/RH数值不转换、不统计train mean/std；file-byte分布仅QC_STAT_ONLY。没有行政mask、bbox、GFS插值、模型输入、训练或数据整合。

CSV/Parquet reader schema见src/table_schema.py。初次1张表的回读错误与恢复记录均保留；最终33测试包含可空布尔用例。recover_finalize.py只用于本次已保留失败结果后的恢复，不是普通新run必须重复执行的步骤。
