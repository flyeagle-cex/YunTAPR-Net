"""Requested compatibility reports; conclusions remain limited to engineering evidence."""
import json,xml.etree.ElementTree as ET
import pandas as pd
from config import *
from common import *
def j(p):return json.loads((OUT/p).read_text(encoding="utf-8"))
def c(p):return pd.read_csv(OUT/p)
def table(df):
    def v(x):return str(x).replace("|","/").replace("\n"," ") if pd.notna(x) else "UNKNOWN"
    return "| "+" | ".join(df.columns)+" |\n| "+" | ".join(["---"]*len(df.columns))+" |\n"+"\n".join("| "+" | ".join(v(x) for x in row)+" |" for row in df.itertuples(index=False,name=None))
def put(p,text):write_text(OUT/p,text.strip()+"\n")
def reports():
    s=j("logs/thermo_summary.json");pair=j("logs/pairing_summary.json");aux=j("TIME_LINEAGE/classification_summary.json");cache=j("logs/staging_summary.json")
    cover=c("COMPATIBILITY/research_period_thermo_coverage.csv");mapping=c("THERMO/gfs_thermo_variable_mapping.csv")
    root=ET.parse(OUT/"tests/pytest_final.xml").getroot()
    suites=[root] if root.tag=="testsuite" else list(root.iter("testsuite"))
    tests={k:sum(int(t.attrib.get(k,0)) for t in suites) for k in ["tests","failures","errors","skipped"]}
    assert tests["tests"]>=18 and tests["failures"]==tests["errors"]==tests["skipped"]==0
    assert pair["research_complete_pairs"]==pair["research_expected_pairs"] and cover.status.eq("READY").all()
    annual=cover.assign(year=cover.month.str[:4]).groupby("year").agg(expected_pairs=("expected_main_forecast_pairs","sum"),
        complete_pairs=("complete_T_RH_pairs","sum"),minimum_month_fraction=("coverage_fraction","min")).reset_index()
    lineage=c("COMPATIBILITY/source_lineage_fields.csv")
    main_source_class=lineage.main_source.map(lambda x:"NOAA AWS declared primary" if "AWS" in x else "NCAR archive declaration").value_counts()
    dims=[
      ("A","file structure compatibility","PASS","All thermo NETCDF4, one structural version; companion variable schema is readable without format rewriting"),
      ("B","grid compatibility","PASS","12960 exact array matches; both coordinate hashes agree; max absolute differences 0"),
      ("C","forecast init compatibility","PASS","All thermo init keys exist in reused main inventory; [00,06,12,18] UTC"),
      ("D","lead compatibility","PASS","All thermo leads [0,3,6]h match main; thermo global coverage is a subset"),
      ("E","valid-time compatibility","PASS","All thermo identities and paired valid times agree"),
      ("F","variable semantic compatibility","PASS","Explicit Temperature_isobaric and Relative_humidity_isobaric at three required levels; no q/dewpoint/potential-T substitution"),
      ("G","unit compatibility","PASS","T K, RH %, pressure Pa agree with available main metadata; no data conversion"),
      ("H","pressure-level compatibility","PASS","50000/70000/85000 Pa present; main PS Pa allows future comparison, no mask computed"),
      ("I","research-period coverage","PASS","24 months and 8820/8820 pairs have all six target metadata fields"),
      ("J","source lineage compatibility","PARTIAL","SUPPORTED_WITH_CAVEATS: declared GFS archive/forecast identifiers agree; converted payload lineage not independently proven"),
      ("K","one-to-one pairing quality","PASS","12960/12960 thermo keys unique and matched; no ambiguous selections")]
    assessment=pd.DataFrame(dims,columns=["item","dimension","status","evidence"])
    write_csv(OUT/"COMPATIBILITY/assessment_dimensions.csv",assessment)
    verdict="PARTIALLY_COMPATIBLE"
    state={"engineering_status":"PASS","researcher_review_status":"NEEDS_REVIEW","thermo_status":"PASS",
        "grid_compatible":True,"time_compatible":True,"variable_compatible":True,
        "source_lineage_status":"SUPPORTED_WITH_CAVEATS","research_period_t_rh_complete":True,
        "compatibility_verdict":verdict,"verdict_scope":"Engineering structure/time/variable coverage passes; conversion lineage remains caveated",
        "predictor_readiness_candidate":"READY_CANDIDATE_STRUCTURAL_METADATA_ONLY",
        "official_predictor_readiness_changed":False,"researcher_approval_required_before_merge":True,
        "raw_data_modified":False,"old_output_runs_modified":False,"main_thermo_merge_performed":False,
        "merged_files_created":False,"dataset_created":False,"operational_release_established":False,
        "main_baseline":str(BASELINE),"main_targeted_raw_files":9,
        "thermo_files":s["files"],"research_expected_pairs":pair["research_expected_pairs"],"research_complete_pairs":pair["research_complete_pairs"],
        "tests":tests,"stage0_closeout_ready":False,
        "review_items":["Approve companion adoption only after reviewing declared conversion lineage",
            "Primary stale history/alternative udunits provenance","Operational availability and forecast vintage"],
        "blocked_engineering_items":[]}
    write_json(OUT/"audit_final_status.json",state)
    put("THERMO/gfs_thermo_inventory_summary.md",f"""
# GFS_thermo inventory summary

Root: {THERMO}. Actual forecast files {s["files"]:,}; total logical bytes {s["total_bytes"]:,}.
Formats {s["formats"]}; data models {s["data_models"]}; extension counts {s["extension_counts"]}.
Read success {s["read_success"]:,}; parse statuses {s["parse_statuses"]}; zero-byte files {s["zero_byte_files"]}; duplicate filename rows {s["duplicate_filename_rows"]}.
Size statistics are QC_STAT_ONLY: {s["size_statistics_QC_STAT_ONLY"]}. These are file-byte statistics, not predictor normalization. No anomaly/exclusion threshold.

Year counts: {s["year_counts"]}. One structural version; variable structure, pressure coordinate, raw global attrs and coordinate values are preserved per file.
Monthly counts:

{table(c("THERMO/gfs_thermo_month_inventory.csv"))}
""")
    put("COMPATIBILITY/source_lineage_comparison.md",f"""
# Source / conversion lineage comparison

Conclusion: **SUPPORTED_WITH_CAVEATS** for all {len(lineage):,} paired thermo forecasts. This is declared-metadata evidence, not independent verification of converted field values.

Thermo declares NCAR RDA d084001 official GFS archive via THREDDS NCSS and per-forecast source URLs containing cycle and lead.
Primary matched files declare either NCAR GDEX/RDA d084001/NCEP GFS or NOAA GFS AWS Open Data, with NCEP center/process metadata, forecast identifiers, History and/or original_grib_url.
Main-source declaration counts among matched pairs: {main_source_class.to_dict()}.

The engineering evidence exceeds matching folder names, times or bbox: every pair has explicit GFS product/archive text and a current source-file identity token matching its cycle/lead. Source URL tokens and retained History tokens are stored separately in source_lineage_fields.csv.
NCAR-style token gfs.0p25.YYYYMMDDHH.fNNN and AWS-style gfs.YYYYMMDD/HH/atmos/gfs.tHHz.pgrb2.0p25.fNNN normalize only forecast identifiers; no weather arrays are modified.
For primary NCAR records without a direct per-file URL, the matching Original Dataset token in History is used with caveats. For AWS records, the current original_grib_url is checked independently of stale inherited History.
A direct current URL token conflict would yield CONFLICTING; missing product/forecast-token evidence would yield NOT_ESTABLISHED. Observed counts: {pair["lineage_counts"]}.

Main subset contains conversion_time, fallback_validation claims and historical template metadata. These are retained claims; this audit did not independently replay download/conversion pipelines, fetch source GRIBs or prove checksummed upstream payload identity.
Thermo has no institution/center/model/process attrs in some structures beyond source/archive/title evidence; absent fields remain absent, not copied from main.
This warrants source-lineage PARTIAL in the overall assessment; no automatic adoption or integration is authorized.
""")
    put("TIME_LINEAGE/AUXILIARY_TIME_CONFLICT_REPORT.md",f"""
# Auxiliary time conflict classification

Reused baseline: {BASELINE}. No full main raw metadata rescan.
All 24,388 prior primary forecast identities remain unchanged. Classified {aux["original_auxiliary_conflicts"]:,} prior auxiliary conflict records:
- ALTERNATIVE_REFERENCE_TIME: {aux["classification_counts"]["ALTERNATIVE_REFERENCE_TIME"]:,}; current CF units and auxiliary udunits refer to different epochs.
- STALE_HISTORY_TOKEN: {aux["classification_counts"]["STALE_HISTORY_TOKEN"]:,}; overlapping subset of the above, not additional unique files.
- TRUE_FORECAST_TIME_CONFLICT detected in primary init/valid/lead evidence: {aux["true_primary_forecast_conflicts"]}.
- NO_AUXILIARY_CONFLICT: {aux["classification_counts"]["NO_AUXILIARY_CONFLICT"]:,}.

CONVERSION_TIMESTAMP, SOURCE_FILENAME_TOKEN and DOWNLOAD_OR_ARCHIVE_RECORD are separate context categories; their mere presence is not an anomaly.
Missing publication timestamps remain UNKNOWN. A generation-center/process identifier is not a generation timestamp.
No evidence here proves that every converted array originated from its claimed forecast; arithmetic consistency and metadata classification do not erase that limitation.

This run reread {aux["targeted_raw_files"]} allowlisted primary files covering {aux["targeted_years"]}, conflict/non-conflict and stale-History examples. Current coordinates and init/valid/lead match prior evidence; sample SHA256 unchanged.
Strata where samples do not exist were not fabricated: 2019 has no auxiliary-conflict files; 2025 has no non-conflict files in the baseline. Selection counts are recorded in logs/main_sample_strata.json.
Detailed raw sample metadata and per-sample comparisons are saved alongside this report. The complete classification table is derived from existing audit metadata only.

Thermo: {s["thermo_auxiliary_conflicts"]} auxiliary conflict flags; all 12,960 primary time identities PASS.
Release/availability for both sources: **NOT ESTABLISHED FROM CURRENT FILE METADATA**. All thermo conservative +5h fields explicitly state an assumption, not observed per-file publication.
""")
    put("COMPATIBILITY/GFS_THERMO_COMPATIBILITY_ASSESSMENT.md",f"""
# GFS_thermo compatibility assessment

Overall engineering verdict: **{verdict}**.

{table(assessment)}

The partial component is source/conversion lineage, not missing T/RH in the requested research months.
Across all historical main keys there are 11,428 MAIN_ONLY entries, outside the requested 2023–2025 March–October period. Thermo is not a complete companion for every historical main-library key.
Within the requested period, all 24 months satisfy the exact structural coverage criteria; they are READY in the monthly audit table.

Can current thermo fill T850/T700/T500/RH850/RH700/RH500 in 2023–2025 March–October?
**Yes as a structural, temporal and metadata-completeness candidate: 8,820/8,820 required forecast pairs.** Dataset adoption remains unapproved because source/conversion provenance and operational vintage decisions require researcher review.
Source lineage: SUPPORTED_WITH_CAVEATS. No assessment item upgrades conservative +5h to observed availability.

READY here is strictly a coverage status. Existing official predictor readiness was not rewritten; READY_CANDIDATE does not mean an approved Dataset, integration, Stage-0 scientific closeout or B0 permission.
""")
    put("schemas/gfs_main_thermo_pair_schema.md",f"""
# Future main/thermo interface schema — definition only

This schema is eligible for researcher review because structure/time/variable coverage evidence exists. No merged file, Dataset, sample pairing database or training sample was constructed.
COMPATIBILITY/main_thermo_pairing.csv is the explicitly requested file-level audit table, with no rain targets, splits, model tensors or operational vintage selection.

| Field | Type / rule |
|---|---|
| forecast_id | Stable identity derived from UTC init + lead, with explicit rule version; not instantiated here |
| init_time, valid_time | UTC timestamp; valid=init+lead |
| lead_time | Numeric hours, not a forecast-selection rule |
| main_file, thermo_file | Separate immutable source paths; multiple candidates retained as ambiguity, never silently selected |
| PWAT_source, CAPE_source, U_source, V_source, PS_source | Main file + explicit raw variable/level name |
| T_source, RH_source | Thermo file + Temperature_isobaric / Relative_humidity_isobaric and pressure index |
| grid_match, time_match | Exact coordinates/hashes and init/lead/valid checks |
| variable_complete | All six thermo variable/level metadata entries present; not per-pixel validity |
| source_lineage_status | STRONGLY_SUPPORTED / SUPPORTED_WITH_CAVEATS / NOT_ESTABLISHED / CONFLICTING |
| pair_quality | MATCHED_COMPLETE / MATCHED_PARTIAL_VARIABLES / MAIN_ONLY / THERMO_ONLY / TIME_CONFLICT / GRID_CONFLICT / METADATA_CONFLICT |
| main_pressure_units, thermo_pressure_units | Retain native Pa; no pressure mask generated |
| T_units, RH_units | Retain K and %; no automatic unit conversion |
| release_time_if_known | Nullable, currently null; conservative timestamp stored separately as assumption |
| vintage_status | NOT_YET_FROZEN |
| researcher_integration_approval | Required, currently false |
| source_status, notes | Evidence run, hashes, unresolved lineage caveats |

PS comes from main; thermo PS absence is expected and not filled using MSLP. Specific humidity, dewpoint and potential temperature do not substitute for target T/RH. GFS precipitation never enters predictor sources.
""")
    put("RESEARCHER_DECISIONS_REQUIRED.md",f"""
# Researcher decisions required

1. **是否采用 thermo 作为 companion、是否批准未来组合接口。** 24研究月8,820/8,820对在时间、坐标、变量与单位metadata上满足条件；工程总判定 PARTIALLY_COMPATIBLE，尚未批准整合。
2. **主库转换来源证据是否足够，是否需要追溯原始GRIB/下载与转换记录。** 声明的GFS archive和forecast token对应，source lineage=SUPPORTED_WITH_CAVEATS；17,665条udunits历史冲突及其中3,628条History token仍需来源复核。没有证据将它们一律判成实际forecast错误，也没有证据证明转换payload全部正确。
3. **GFS operational availability/vintage规则。** 主库与thermo都没有确立真实发布时间；init+5h不能自动采用为observed release。

本轮不需要改变MEE变量、科研年份或bbox才能完成审计；不提出无必要重下载。其他既有科学closeout事项继续保留在旧Stage-0报告，本轮未擅自解决或改写。
""")
    final=f"""
# YunTAPR-Net GFS_thermo compatibility engineering report

1. **engineering_status=PASS；researcher_review_status=NEEDS_REVIEW。** 所有本轮独立工程任务已执行；总兼容性判定 **PARTIALLY_COMPATIBLE**，来源转换环节仍有保留条件。

2. **Thermo root：** {THERMO}。
3. **文件数：** {s["files"]:,}；逻辑大小 {s["total_bytes"]:,} bytes；全部读取成功，0零字节、0重复文件名。文件大小统计仅QC_STAT_ONLY，不是训练mean/std或异常阈值。
4. **年份/月覆盖：** {s["year_counts"]}；全月清单见 THERMO/gfs_thermo_month_inventory.csv，研究24月见下表。
5. **格式/结构：** 全部NetCDF/HDF5 signature、NETCDF4；{s["structural_versions"]}种内部结构。逐文件dimensions、coordinate/pressure变量、dtype、原global attrs均保留。
6. **Grid：** 53×57，0.25°；lat32→19递减、lon95→109递增；float32，一种grid。
7. **与主库比较：** 全12,960文件实际坐标逐值相等，lat/lon hash相等，shape和resolution一致；max_abs_lat_diff=0，max_abs_lon_diff=0。没有只比bbox、近似接受或插值。
8. **T/RH：** 六个必需variable/level均12,960/12,960存在；field shape=(1,3,53,57)。原Temperature_isobaric与Relative_humidity_isobaric保留；Specific_humidity_isobaric单列，未代替RH。未检查所有气象像元数值有效性，metadata presence不是像元QC通过。
9. **单位：** T=K，RH=%；与主库已有T/RH metadata相同。未转degC或0–1，未改原数组。
10. **Pressure：** pressure_level原值[50000,70000,85000]Pa，即500/700/850hPa的metadata对应关系。主库Pressure_surface原单位Pa；未来可比较ps>p_k，feasibility=PASS。thermo自身无PS，未用MSLP替代；未算above-ground mask、DOTE或W/L/M。
11. **时间：** init UTC {s["init_hours"]}，lead {s["leads"]}h、间隔3h、最大6h；12,960/12,960满足valid=init+lead，thermo辅助冲突0。
12. **主库/thermo配对：** MATCHED_COMPLETE=12,960，MAIN_ONLY=11,428；THERMO_ONLY=0；TIME/GRID/METADATA配对冲突0。
13. **一对一比例：** 相对thermo为100%（12,960/12,960），相对全部历史主库约{pair["one_to_one_fraction_of_main_files"]:.6%}（12,960/24,388）；一对多、多对一、歧义均0。记录了{pair["shared_valid_time_groups"]:,}个同valid_time多forecast组，它们由不同init/lead区分，不能当作重复配对错误。
14. **研究期月覆盖：**

{table(cover[["month","expected_main_forecast_pairs","main_present","thermo_present","matched_pairs","complete_T_RH_pairs","coverage_fraction","status"]])}

15. **关键问题：能否补齐2023–2025 March–October六个T/RH？** 从当前文件级时间、坐标和变量metadata看，**可以作为完整补齐候选**：24个月均100%，共8,820/8,820；每月missing init cycles、lead pairs、missing variables均0。
年度证据：

{table(annual)}

16. **Source lineage：SUPPORTED_WITH_CAVEATS。** 每个配对有具体GFS archive/product与当前forecast文件token证据，不只靠目录、时间或grid；matched主库声明来源包括NCAR与NOAA AWS，thermo声明NCAR RDA d084001。未独立验证原始GRIB内容、转换代码或下载日志，不能保证所有转换payload来源，详见 source_lineage_comparison.md。
17. **主库auxiliary time：** 复用已验证旧run，对24,388旧记录分类：17,665为ALTERNATIVE_REFERENCE_TIME，重叠3,628为STALE_HISTORY_TOKEN；真实主时间算术冲突检测0。仅定向读取9个主库样本，覆盖2019/2021/2023/2024/2025及可用冲突/非冲突层，原init/valid/lead未改写。
18. **Release/availability：NOT ESTABLISHED FROM CURRENT FILE METADATA。** thermo全部12,960个+5h字段明确是保守假设；creation/conversion/archive文本不等于observed publication，未冻结vintage规则。
19. **原始完整性：** thermo全库读取前后size/mtime_ns一致；5个分散thermo hash样本一致，6个结构probe读时hash一致；9个主库样本size/mtime/hash一致；复用旧报告hash一致。**size/mtime verification is not full content hash proof.** raw及所有旧run只读，仅清理本run创建的staging副本。
20. **pytest：** {tests["tests"]} passed，failures={tests["failures"]}，errors={tests["errors"]}，skipped={tests["skipped"]}；cwd/rootdir/test path/confcutdir显式限制。实际stdout与XML见tests/pytest_final_output.txt、pytest_final.xml。
21. **依赖：** 没有新增/升级；固定Python {PYTHON}，前后环境清单保存。
22. **Cache I/O：** copy_count={cache["copy_count"]}（thermo12,960全审+6probe，main9个），累计{cache["cumulative_copied_bytes"]:,} bytes，最大单副本{cache["max_single_copy_bytes"]:,} bytes；copy={cache["copy_seconds"]:.3f}s，read={cache["read_seconds"]:.3f}s，cleanup failures={cache["cleanup_failures"]}，remaining staged bytes={cache["remaining_staged_bytes"]}。没有永久复制完整库。
23. **兼容性判定：PARTIALLY_COMPATIBLE。** A–K逐项表见兼容性assessment；结构、grid、时间、变量、单位、压力、研究期覆盖和一对一配对PASS；来源lineage为PARTIAL。保留条件不是研究月T/RH缺文件。
24. **研究者决策：** 是否采纳/允许模型数据层组合、是否追溯原始来源与转换记录、如何冻结availability/vintage。普通工程问题均已处理；初始化NumPy bool日志序列化修复记录保留。
25. **Stage-0 closeout impact：** 本轮消除了研究期T/RH“文件/metadata不可得”的工程缺口，支持 **READY candidate（仅结构覆盖意义）**；没有改写正式predictor readiness或旧run。来源复核、release/vintage及其他既有Stage-0科学项仍待研究者处理，stage0_closeout_ready=false。未启动B0，也未构造Dataset、正式sample pairing database或merged files。

主库证据复用：{BASELINE}，已核验engineering_status=PASS、24388 files、53×57与指定root fingerprint。main_present主要来自该不可变审计快照，仅9个样本本轮重开；不声称对全部主库做了当前原文件重读。
THERMO/COMPATIBILITY/TIME_LINEAGE表是审计证据；配对表不含目标降水、训练split或模型tensor。完整清单见output_manifest.csv。

GFS_thermo compatibility engineering audit complete.
No GFS main/thermo merge was performed.
Researcher approval is required before any dataset integration.
No frozen scientific convention was changed automatically.
"""
    put("FINAL_GFS_THERMO_COMPATIBILITY_REPORT.md",final)
    put("README.md",f"""
# GFS_thermo compatibility audit

工程状态PASS；兼容性PARTIALLY_COMPATIBLE；研究期结构覆盖READY candidate。先读最终报告、assessment与RESEARCHER_DECISIONS_REQUIRED.md。
OUT={OUT}
Baseline={BASELINE}
Python={PYTHON}

只审计thermo全库，主库只使用既有审计和9个allowlisted样本。raw和旧输出只读；source_path拒绝未授权主库路径，所有输出限定当前OUT且默认exclusive创建。
初始化先创建全新run（exist_ok=False）、环境快照、baseline fingerprint与hash、全thermo size/mtime清单和9个主库样本allowlist/size/mtime/hash。目录碰撞拒绝；不能原地重跑覆盖本run。
代码使用本run的配置和证据快照，重现应新建run，更新config与初始化清单；不得复制旧时间日志冒充新执行。

依次运行main_samples.py、audit_thermo.py、pairing_audit.py、lineage_integrity.py、unit_pressure_audit.py、final_checks.py、write_reports.py、validate_delivery.py。独立结构probes写在logs/thermo_structure_probes.json；它们只用于reader/语义确认，不代替全库审计。
unit_pressure_compatibility.csv由两库原变量mapping表校验K/%/Pa后生成；README中的运行链需要保留该单位核验步骤。
final_checks.py限定pytest cwd/rootdir/confcutdir/test path并写真实stdout/XML，同时CSV/Parquet双格式回读；输出文件默认exclusive，不隐式复用失败执行。
SOURCE/GRID/TIME不确定项保留，不以UNKNOWN当PASS；source_lineage_status是声明metadata的证据分级，不是下载过的原始GRIB验证。
脚本中的assert与报告描述记录当前快照；未来库存变化须先更新期望，不能机械套用旧计数。

cache={CACHE}；单文件复制、copy size校验、选定hash、netCDF4只读分析、只清理自己创建的副本。累计I/O是多次临时复制的总和，不是峰值占盘；生产staged bytes=0，pytest合成测试文件可保留。
native T/RH数值不转换、不统计train mean/std；file-byte分布仅QC_STAT_ONLY。没有行政mask、bbox、GFS插值、模型输入、训练或数据整合。
""")
    print(dumps(state),flush=True)
if __name__=="__main__":reports()
