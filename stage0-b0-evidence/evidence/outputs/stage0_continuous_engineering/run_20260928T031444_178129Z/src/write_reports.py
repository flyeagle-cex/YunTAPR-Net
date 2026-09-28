"""Generate the requested review documents from executed evidence, without freezing science."""
import json
from pathlib import Path
from datetime import datetime,timezone
import xml.etree.ElementTree as ET
import pandas as pd
from config import *
from common import *

def table(df):
    def fmt(v):
        return str(v).replace("|","/").replace("\n"," ") if pd.notna(v) else "UNKNOWN"
    return "| "+" | ".join(map(str,df.columns))+" |\n| "+" | ".join(["---"]*len(df.columns))+" |\n"+"\n".join(
        "| "+" | ".join(fmt(v) for v in row)+" |" for row in df.itertuples(index=False,name=None))
def readj(p):return json.loads((OUT/p).read_text(encoding="utf-8"))
def readc(p):return pd.read_csv(OUT/p)
def write(p,s):write_text(OUT/p,s.strip()+"\n")
def reports():
    s=readj("logs/analysis_summary.json");d=readj("GFS/discovery.json");pq=readj("logs/parquet_summary.json")
    variables=readc("GFS/gfs_variable_coverage.csv");years=readc("GFS/gfs_year_variable_coverage.csv")
    temporal=readc("GFS/gfs_temporal_coverage.csv");matrix=readc("CROSS_SOURCE/research_period_data_matrix.csv")
    spatial=readc("CROSS_SOURCE/spatial_coverage_ranges.csv");static=readj("CROSS_SOURCE/static_evidence.json")
    times=readc("GFS/gfs_time_semantics_audit.csv")
    boundary=readc("IMERG/imerg_boundary_values.csv");stage=s["stage_io"]
    tests=ET.parse(OUT/"tests/pytest_verified.xml").getroot()
    suites=[tests] if tests.tag=="testsuite" else list(tests.iter("testsuite"))
    counts={k:sum(int(t.attrib.get(k,0)) for t in suites) for k in ["tests","failures","errors","skipped"]}
    assert counts["tests"]>=30 and counts["failures"]==0 and counts["errors"]==0 and counts["skipped"]==0
    assert s["raw_stat_all_unchanged"] and s["raw_hash_sample_all_unchanged"] and not s["dependency_changes"]
    assert len(matrix)==24 and matrix.set_index("YYYY-MM").loc["2025-10","IMERG_available"]=="MISSING"
    assert len(pq["failed"])==0
    history_count=int(times.auxiliary_metadata_notes.fillna("").str.contains("History Original Dataset",regex=False).sum())
    g2025=temporal[temporal.month.between("2025-03","2025-10")]
    write("GFS/gfs_discovery_report.md",f"""
# GFS discovery report

状态：{d["status"]}。

主目录：{GFS}。按用户优先路径直接找到；没有扫描系统盘或无关大目录。
对 raw 下名称以 GFS 开头的兄弟目录做受限发现和文件名清单统计。

{table(pd.DataFrame([{"root":r["root"],"selected_main":r["selected_main"],"file_count":r["file_count"],"extensions":str(r["extensions"])} for r in d["roots"]]))}

MULTIPLE_GFS_ROOTS_RESEARCHER_REVIEW：主目录 GFS 进入全库只读 metadata 审计；GFS_thermo 只发现/计数，没有读取其科学变量，也未自动补充主目录。不能依据 thermo 名称直接认定它可以合并。

实际主库 2019–2025，24,388 个 .nc；magic 为 NetCDF/HDF5，netCDF4 data_model=NETCDF4，全部可读。
""".replace("{{","{").replace("}}","}"))
    write("GFS/GFS_TIME_SEMANTICS_SUMMARY.md",f"""
# GFS time semantics summary

24,388/24,388 文件的当前 filename、CF reference/valid time 及可用 global cycle/lead metadata 一致，valid_time = init_time + lead_time 全部 PASS；没有重复 init/lead 对。时间均按 UTC 输出。

init hours：{s["init_hours_utc"]} UTC；lead hours：{s["lead_hours"]}；lead 间隔 {s["lead_intervals_hours"]} 小时，maximum lead={s["maximum_lead_hours"]} 小时。跨年 valid time 可延伸至 2026-01-01T00:00Z，不自动改写研究年份。
accumulation_time 是降水累积时段相关坐标，不替代 predictor 的 instantaneous valid_time。

但 {s["auxiliary_metadata_conflict_count"]:,} 文件存在陈旧辅助 udunits 与当前 CF units 冲突，其中 {history_count:,} 文件还包含与当前 cycle/lead 不同的 History Original Dataset token。见 gfs_auxiliary_time_metadata_needs_review.csv。
本轮以当前 CF units 和相互一致的 filename/global cycle 重建索引，同时完整保留冲突。算术一致不能证明实际数组来自正确 forecast；需要原始转换来源追溯。没有改写任何 raw metadata。

{int(s["raw_availability_proxy_count"]):,} 文件包含 conservative_available_time_utc；其 availability_note 明示 +5h 是 conservative assumption，而非 observed per-file publication timestamp。
其他 source archive URL、history、conversion_time 等原文保存在每文件时间审计与 global_metadata_patterns.jsonl 中；不把下载、转换或文件 mtime 视为业务可用时间。

**GFS operational release/availability: NOT ESTABLISHED FROM CURRENT FILE METADATA.**
release_time 和 operational_availability_time 为空值；GFS vintage rule=NOT_YET_FROZEN。该证据不足不阻塞其余工程审计。

日历月缺口表使用观测到的四个 init hour 与 lead union [0,3,6] 作为诊断参考，不是新的科学要求。
2019–2020 主要只有 f000，所以相对该 union 会出现 f003/f006 缺口；不自动将这些文件判坏。
2023–2025 年研究月没有该参考下的缺失 cycle/lead 对，但主目录必需 T/RH 缺失，数据准备状态仍 PARTIAL。
""")
    write("CROSS_SOURCE/spatial_coverage_report.md",f"""
# Multi-source spatial coverage

**CANDIDATE ONLY.** covers_yunnan_context=PENDING_RESEARCHER_CONFIRMATION；model_input_bbox=null。

{table(spatial[["source","lat_min","lat_max","lon_min","lon_max","shape","resolution_lat","resolution_lon","lat_direction","lon_direction"]])}

数值包络交集：lat 20–30°N，lon 97–107°E，仅为 CANDIDATE ONLY。
没有据此设置 model_input_bbox，也没有采用历史 96–108°E、20–31°N 建议范围。
Himawari 范围仅由已完成 2024-07 grid audit 支持；其他年份/月 grid 未在本轮审计。IMERG 复用前次全库坐标审计；GFS 为本轮全库逐文件坐标 hash。
GFS 唯一 grid：53×57，纬度 32→19 递减，经度 95→109 递增，0.25°。没有自动 flip 或重采样。

SRTM：237 个 SRTMGL1 zip，文件名推定包络 lat18–33、lon94–110。只读 ZIP central directory，检查 HGT 成员大小，不解压或读取 DEM 像元。
矩形包络缺 N18E107、N19E107、N20E108 三个瓦片；它们与候选交集内部不相交。包络内没有瓦片缺口不等于 DEM 无 void 或共同像元有效。
按 [USGS SRTM User Guide](https://lpdaac.usgs.gov/documents/179/SRTM_User_Guide_V3.pdf) 的西南角命名与 1°/1 arcsecond 网格约定解释；3601×3601 还得到每个 HGT 成员字节数的目录证据支持。
实际 raster coordinate direction、void、数据有效性与垂直 datum 本轮 NOT_AUDITED，SRTM 准备状态 PARTIAL。

云南边界：GADM41 CHN level1 中唯一 NAME_1=Yunnan/GID_1=CHN.30_1，MultiPolygon、4,418 坐标点。
几何包络 lat {static["mask"]["lat_min"]}–{static["mask"]["lat_max"]}，lon {static["mask"]["lon_min"]}–{static["mask"]["lon_max"]}；CRS84 元数据。该多边形源存在，但评价 mask 的栅格化、边界像元与对齐尚未定义/验证；状态 PARTIAL。
数值交集包络包含该云南多边形包络，不能据此声称足够天气系统上下文或最终 mask 已就绪。

共同有效覆盖需后续结合每源有效性 mask、行政评价范围与省界外天气上下文，由研究者决定。没有插值、裁剪、行政 mask 生成或科学 bbox 冻结。
""")
    write("RESEARCHER_DECISIONS_REQUIRED.md",f"""
# Researcher decisions required

工程总状态 NEEDS_REVIEW：独立审计已完成，以下科学/来源问题未代替研究者决定。

| 事项 | 实际证据 | 需要研究者复核的内容 |
|---|---|---|
| GFS 核心 T/RH 缺口 | 主目录 2023–2025 全年 13,152 文件均没有所需 T/RH；PWAT/CAPE/U/V/PS 存在 | 是否批准审计 GFS_thermo、验证同源 cycle/lead/grid/units 后设计显式补充方案；本轮未合并 |
| GFS 辅助时间来源冲突 | {s["auxiliary_metadata_conflict_count"]:,} 个 udunits/history 冲突；其中 {history_count:,} 个 History token 冲突；当前 CF 算术均一致 | 追溯转换代码/原始 archive，确认数组真实 forecast 身份；不要仅靠索引算术判定科学可用 |
| GFS operational availability/vintage | 无直接业务发布证据；{s["raw_availability_proxy_count"]:,} 个 +5h 字段明确是上游假设 | 明确来源证据和可用性规则；不自动采用 +5h、mtime 或 init_time |
| IMERG native window 语义 | converted CF 坐标严格半小时；native 窗口对应关系仍 PROVISIONAL | 确认 [T,T+30min) 与 analysis_time=T+30min 绑定 |
| Himawari availability | date_created 是 product/file creation；obs_end 是物理结束 | 如采用 proxy 需明确其证据及适用范围，不能写成真实 availability |
| model_input_bbox/上下文 | 数值共同包络 lat20–30、lon97–107，仅候选 | 决定云南全境与省界外上下文；covers_yunnan_context 保持待确认 |
| IMERG 2025-10 | 定向检查 0 文件；先前全库止于 2025-09-30 | 补齐同版本数据或另行科学决策；本轮不缩短研究期 |
| SRTM/云南 mask | 237 瓦片目录与云南 polygon 存在；raster values/grid mask 未验证 | DEM 有效性与 mask 栅格化/边界规范待后续授权工程 |
| 独立外部验证 | NOT_AUDITED | 指定已准备的数据与独立性证据，不能把未审计写成 READY/MISSING |
| split/quantiles | 正式精确划分块、32 quantile levels 尚未冻结 | 由研究者决定；未执行 split、统计或训练 |

没有必须先回答才能完成的剩余独立工程任务；本文件是统一复核清单，不是本轮暂停请求。
下一阶段仅建议：先复核来源时间冲突与核心变量补充方案，再冻结 availability/vintage 和窗口语义；确认后另行执行配对工程。不得直接跳到模型实验。
""")
    summary_columns=["year","file_count","core_complete_files","RH_850_count","T_850_count","PS_count"]
    final=f"""
# YunTAPR-Net Stage-0 continuous engineering report

1. **总状态：NEEDS_REVIEW。** TASK A–I 独立工程执行完成；没有把未知 release 或未审计数据写成 PASS。科研可用性受核心变量缺口、辅助时间来源冲突及待冻结规则约束。

2. **IMERG boundary sanity check：已完成。** 同一最近像元 (lat24.9499988556, lon95.4499969482)，时间按 converted CF coordinate 原值：
{table(boundary[["time_utc","precipitation","units","missing"]])}
00:00 的 5×5 patch 已保存于 IMERG/imerg_20250624_boundary_extreme_check.txt 与 CSV/Parquet；这是邻时次/空间数值证据，不能单独证明极值真伪。未设阈值、删样本或改训练规则；两份文件 SHA256 前后一致。

3. **GFS 根目录：** {GFS}。另发现 {SUPPLEMENT}，共 12,960 文件，只盘点不合并；标记 MULTIPLE_GFS_ROOTS_RESEARCHER_REVIEW。

4. **GFS 文件数：** {s["file_count"]:,}，{s["total_bytes"]:,} bytes，{s["read_success"]:,} 成功读取，0 读取失败。审计 metadata、坐标和时间，不宣称所有 predictor 像元值都已 QC。

5. **年份覆盖：** 真实磁盘为 2019–2025，不能沿用“仅 2021–2024”的旧推测。
{table(years[summary_columns])}

6. **文件格式：** 24,388 NetCDF/HDF5 signature + NETCDF4 data_model；没有 GRIB1/2 或 other 文件，不需要安装 cfgrib/eccodes。

7. **Grid：** 唯一 grid，53×57，0.25°；纬度32→19递减，经度95→109递增。全部坐标与首文件相等，hash 保留在 gfs_grid_audit.csv。无 flip、插值或重采样。

8. **核心变量实际覆盖：**
{table(variables[["canonical_name","file_count","total_files","availability_fraction"]])}
这是 metadata presence fraction，不是像元有效比例。T/RH 全层仅 3,148 文件存在（2019、2020、2021年部分）；2022–2025 主库均无所需 T/RH。研究候选期2023–2025年3–10月因此全部 GFS_available=PARTIAL。
Pressure_surface 在全部文件真实存在，未用 MSLP 替代；pressure coordinate 与 surface pressure 单位可比较，surface_pressure_support_status=PASS，表示未来 m_k=I(ps>p_k) metadata 可行。未计算 mask 或 DOTE，未做地下层像元 QC。

9. **禁用 precipitation predictors：** {s["forbidden_files"]:,} 文件检测到降水累积等变量，逐项登记，全部 model_predictor_allowed=False。PWAT 是整层水汽，保留为允许变量；禁用变量存在不意味着文件坏。

10. **init/valid/lead：** 当前 filename/CF/global 可一致重建，24,388 条均满足 valid=init+lead。init UTC [0,6,12,18]，lead [0,3,6]h，间隔3h，最大6h，重复init/lead=0。
但 {s["auxiliary_metadata_conflict_count"]:,} 条 auxiliary metadata 冲突，含 {history_count:,} 条陈旧 History 原始数据 token，必须来源追溯；时间算术 PASS 不等于真实数组来源已确认。

11. **Release/availability：NOT ESTABLISHED FROM CURRENT FILE METADATA。** {s["raw_availability_proxy_count"]:,} 个上游 +5h conservative 字段不是 observed publication；本轮未采用。release/operational availability 保持 null，vintage NOT_YET_FROZEN。

12. **2025 GFS 缺口：** 全年4,380文件；3–10月共 {int(g2025.file_count.sum()):,} 文件，观测调度参考下 missing cycle={int(g2025.missing_cycles.sum())}，missing init/lead pair={int(g2025.missing_init_lead_pairs_reference.sum())}。文件调度齐全，但 T/RH 核心变量缺失；二者分开报告。

13. **2025-10 IMERG：MISSING。** 前次全库2,465日文件止于2025-09-30，本轮定向 imerg_202510*.nc 仍0文件。未重扫全库，未修改研究时间范围。

14. **跨源矩阵：已生成24行。** 2023–2025每年3–10月，包含Himawari、IMERG、GFS、SRTM、mask、external validation。Himawari仅2024-07有旧月审计证据为PARTIAL（4390/4464时次）；其他月仅查目录，NOT_AUDITED。IMERG除2025-10为MISSING外为READY（复用前次审计）。GFS研究月均PARTIAL；SRTM/mask为PARTIAL；external为NOT_AUDITED。READY列含义限于相应工程审计证据，非正式训练许可。

15. **空间数值共同包络：lat20–30，lon97–107，CANDIDATE ONLY。** model_input_bbox=null；covers_yunnan_context=PENDING_RESEARCHER_CONFIRMATION。SRTM仅瓦片目录证据、尚无像元有效性；云南 polygon 存在但评价mask未验证，详见空间报告。

16. **测试：{counts["tests"]} passed，0 failures/errors/skipped。** 覆盖filename、跨年init/valid/lead、未知/冲突时间、坐标hash、变量/层映射、surface pressure、降水禁入、主辅目录、raw只读/staging清理、完整日历月、跨源矩阵与2025-10缺口。CSV/Parquet {pq["passed"]}/{pq["attempted"]} 表回读一致，另含验证表自身一对。

17. **依赖：新增0、升级0。** 解释器 {PYTHON}。zarr3.4.0、numcodecs0.17.0、pyarrow25.0.1、xarray2026.7.0、netCDF4 1.7.4 均实测可import；全部环境包前后快照无差异。

18. **完整性/只读：** 全部24,388 GFS大小与mtime_ns复核一致；5个分散GFS样本、2个IMERG文件及GADM边界SHA256前后一致。完整库未做全字节hash，不能把stat一致说成全库逐字节证明。全部raw以只读打开，未修改/移动/删除F/H科研原件；仅清理由流程创建的本轮英文cache副本。旧失败记录、报告和5个diagnostic cache未覆盖/删除。
本轮GFS+IMERG staging共24,390次，累计临时复制 {stage["temporary_bytes_sum"]:,} bytes，copy累计 {stage["copy_seconds_sum"]:.3f}s，read累计 {stage["read_seconds_sum"]:.3f}s；清理失败0，原始stat变化0，遗留生产nc副本0。不是永久复制整库，耗时是调用累计值，不等于整体wall time或新storage benchmark。

19. **研究者决策清单：** RESEARCHER_DECISIONS_REQUIRED.md；decision log五类状态与未来配对schema均已完成。Himawari既有p99只保留review marker：p99 is a distribution-tail review marker only; it is not an exclusion criterion, QC threshold, or scientific threshold.

20. **下一阶段仅建议：** 复核GFS转换来源/辅助时间冲突，批准后另行审计thermo补充可行性，明确availability/vintage与native IMERG窗口，再决定bbox/mask及缺月处理。本轮未运行训练、normalization、split、正式样本构建、DOTE/DTFM/MEE、GFS插值或Himawari重采样。

证据目录与重现步骤见 README.md；完整输出清单见 output_manifest.csv。所有报告结论均限定于本轮实际执行及明确标注的前次审计证据。

Stage-0 continuous engineering run complete.
Waiting for researcher scientific review.
No frozen scientific convention was changed automatically.
"""
    write("FINAL_CONTINUOUS_ENGINEERING_REPORT.md",final)
    write("README.md",f"""
# YunTAPR-Net Stage-0 continuous engineering run

状态 NEEDS_REVIEW。阅读 FINAL_CONTINUOUS_ENGINEERING_REPORT.md 与 RESEARCHER_DECISIONS_REQUIRED.md。
本轮目录：{OUT}。原始数据不在输出目录，全部只读；以前 run 不覆盖。

## 已执行范围与主要文件

- IMERG/：仅2025-06-23和24跨日像元/5×5 patch检查。
- GFS/：主目录全部24,388文件的inventory、grid hash、variable mapping/coverage、time semantics、禁用降水清单、84个月calendar coverage、冲突表与缺口表。
- CROSS_SOURCE/：24研究月矩阵、空间范围与候选数值交集、SRTM ZIP目录、云南polygon存在证据。
- docs/DECISION_LOG_STAGE0.md：五类决策状态；schemas/sample_index_schema.md：定义但未实例化。
- tests/pytest_verified.xml：30 tests passed；logs/：环境、依赖import、staging、raw完整性、CSV/Parquet回读、各阶段结果与日志。
- CSV使用UTF-8 BOM，Parquet使用已有pyarrow/snappy。复杂metadata嵌套结构在CSV中存JSON文本，原文完整保留。Parquet回读等于对应CSV解析结果；不保证CSV能恢复原NetCDF底层dtype，原dtype/属性另存metadata。

## 解释器与重现

解释器固定：{PYTHON}。不安装/升级环境包。
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

netCDF4通过 {CACHE} 的独立临时英文文件读数据。每个Reader同一时刻一个源文件，复制后校验大小，关键样本校验SHA256，读完清理；GFS与IMERG独立任务曾可能短暂重叠。
配置总staging阈值128MiB、剩余磁盘最低512MiB；单生产副本最大 {stage["single_file_max_bytes"]:,} bytes。两个独立reader的并发检查不是跨进程原子配额锁；本轮输入最大文件和两个reader的边界使实际候选副本远低于阈值。未仪器化测全局峰值，不报告伪精确峰值。
累计复制 {stage["temporary_bytes_sum"]:,} bytes，copy {stage["copy_seconds_sum"]:.3f}s，read {stage["read_seconds_sum"]:.3f}s；清理失败0。它们是额外I/O成本与调用累计耗时，没有永久保存GFS整库或Himawari19GiB副本。
cache中pytest合成文件保留便于追踪，生产staging nc副本为0。允许删除的只有流程自己创建的本轮临时副本，未操作任何H盘原始文件/旧diagnostic缓存。

## 证据复用和限制

IMERG全库与Himawari 2024-07旧证据路径分别为 {P0} 和 {HIM_AUDIT}。
没有重新运行旧storage benchmark或Himawari全月处理；当前任务是连续P0审计。
月矩阵GFS_inventory_status仅检查观测schedule参考，GFS_available还要求核心变量。NOT_AUDITED不等于PASS、MISSING或坏数据。
未来availability未知不能用mtime/creation/init代替。上游+5h代理保留原文但未采纳。当前CF时间一致不抹去udunits/history来源冲突。
空间交集不是正式bbox或共同有效像元mask；SRTM未解压栅格，Yunnan polygon不是已经验证的评价mask。
""")
    status={"run":OUT.name,"completed_utc":datetime.now(timezone.utc).isoformat(),"status":"NEEDS_REVIEW",
        "engineering_execution":"PASS","tasks_A_to_I":"EXECUTED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS",
        "tests":counts,"csv_parquet_roundtrip":pq,"raw_integrity":"FULL_GFS_STAT_AND_STATED_SAMPLE_SHA256_PASS",
        "researcher_review_required":["GFS T/RH gaps and secondary root","auxiliary time metadata provenance",
            "operational availability and vintage","IMERG native window mapping","bbox/admin mask","IMERG 2025-10","independent validation"],
        "not_executed_by_design":["training","normalization","split","interpolation","resampling","formal sample generation","DOTE","DTFM","MEE"],
        "historical_runs_overwritten":False,"scientific_conventions_changed_automatically":False}
    write_json(OUT/"final_continuous_engineering_status.json",status)
    append_json(OUT/"logs/audit_run.log",{"phase":"reports_written","status":"NEEDS_REVIEW","utc":datetime.now(timezone.utc).isoformat()})
    print(dumps(status),flush=True)
if __name__=="__main__":reports()
