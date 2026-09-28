import json,sys,re,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from config import *
from common import write_json,write_csv,write_text,sha256,dumps
sys.stdout.reconfigure(encoding='utf-8')
def j(rel):return json.loads((OUT/rel).read_text(encoding='utf8'))
s=j('logs/evidence_extraction_summary.json');integ=j('logs/integrity_verification.json');st=j('logs/staging_summary.json');hist=j('TIME_LINEAGE/history_token_summary.json')
xml=ET.parse(OUT/'tests/pytest_final.xml').getroot();suite=xml.find('testsuite') if xml.tag!='testsuite' else xml
stats={k:int(suite.attrib.get(k,0)) for k in ['tests','failures','errors','skipped']}
assert stats=={'tests':37,'failures':0,'errors':0,'skipped':0}
assert all(integ[k] for k in ['all_selected_raw_unchanged','all_historical_artifacts_unchanged','all_baseline_hashes_unchanged','dependencies_unchanged'])
# Check specifically requested source fields, including explicit absence, over prior metadata records only.
fields={};patterns=0
with (BASE_MAIN/'GFS/global_metadata_patterns.jsonl').open(encoding='utf8') as f:
 for line in f:
  o=json.loads(line);patterns+=1
  for key,value in o['global_attrs'].items():
   if key not in fields:fields[key]={'example':str(value),'evidence_example':o.get('example','')}
requested={'source':['source'],'history':[x for x in fields if 'history' in x.lower()],'institution':['institution'],'references':['references'],'title':['title'],'generating center':[x for x in fields if 'center' in x.lower() or 'centre' in x.lower()],'process id':[x for x in fields if 'process' in x.lower()],'original filename':[x for x in fields if 'original' in x.lower() or 'history' in x.lower()],'archive path':[x for x in fields if 'archive' in x.lower() or 'source' in x.lower()],'download URL':[x for x in fields if 'url' in x.lower() or 'source' in x.lower()]}
coverage={role:{'observed_fields':{k:fields[k] for k in keys if k in fields},'status':'OBSERVED_METADATA_ONLY' if any(k in fields for k in keys) else 'NOT_FOUND_IN_REUSED_GLOBAL_METADATA'} for role,keys in requested.items()}
write_json(OUT/'PROVENANCE/main_source_field_coverage.json',{'metadata_records_checked':patterns,'roles':coverage,'absence_scope':'Only reused main global metadata table; no raw rescan','not_independent_upstream_truth':True})
# Task completion reflects evidence search/report execution, not a declaration that missing science is solved.
tasks=[]
for key,desc,evidence,result in [
 ('A','restricted local artifact search','PROVENANCE/local_artifact_inventory.csv','COMPLETED'),('B','acquisition/conversion script lookup and pipeline reconstruction','logs/referenced_script_lookup.json','COMPLETED_SEARCH_SOURCE_CODE_NOT_FOUND'),('C','provenance chain','PROVENANCE/provenance_chain.csv','COMPLETED_WITH_UNKNOWN_LINKS'),('D','main source roles','PROVENANCE/main_source_fields_interpretation.csv','COMPLETED'),('E','thermo archive role','PROVENANCE/official_documentation_evidence.csv','COMPLETED_FAMILY_VERIFIED_CONTENT_LINK_UNKNOWN'),('F','original token comparison','PROVENANCE/original_filename_token_comparison.csv','COMPLETED'),('G','20 forecast cases','PROVENANCE/forecast_case_trace.csv','COMPLETED'),('H','auxiliary history origin','TIME_LINEAGE/conversion_history_origin.md','COMPLETED_CAUSAL_ASSIGNMENT_NOT_ESTABLISHED'),('I','timestamp semantic inventory','TIME_AVAILABILITY/time_evidence_inventory.csv','COMPLETED'),('J','download records','TIME_AVAILABILITY/download_manifest_case_events.csv','COMPLETED_NO_SAVED_RELEASE_HEADERS'),('K','vintage candidates only','TIME_AVAILABILITY/VINTAGE_RULE_CANDIDATES.md','COMPLETED_NOT_FROZEN'),('L','compatibility reassessment','PROVENANCE/PROVENANCE_CHAIN_REPORT.md','COMPLETED_CAVEATS_RETAINED'),('M','two explicit questions','audit_final_status.json','COMPLETED'),('N','new decision log','docs/DECISION_LOG_STAGE0_PROVENANCE_UPDATE.md','COMPLETED'),('O','actual scoped pytest','tests/pytest_final.xml','PASS_37_NO_SKIPS'),('P','selected raw and old artifact protection','logs/integrity_verification.json','PASS_LIMITED_VERIFICATION_SCOPE')]:
 tasks.append(dict(task=key,description=desc,evidence=evidence,result=result))
write_json(OUT/'logs/task_completion_matrix.json',tasks)
status=dict(engineering_status='PASS',audit_completion_status='COMPLETE_WITH_SCIENTIFIC_DECISIONS_PENDING',main_provenance_status='SUPPORTED_WITH_CAVEATS',thermo_provenance_status='SUPPORTED_WITH_CAVEATS',main_thermo_source_lineage_status='SUPPORTED_WITH_CAVEATS',compatibility_verdict='PARTIALLY_COMPATIBLE',compatibility_upgraded=False,dataset_layer_combination_status='NEEDS_MORE_PROVENANCE',historical_operational_vintage_status='NOT_ESTABLISHED',operational_release_status='NOT_ESTABLISHED',local_historical_availability_status='PARTIALLY_ESTABLISHED',local_historical_availability_scope='2026 retrospective local acquisition logs exist; current-content identity incomplete',research_period_2023_2025_contemporaneous_local_availability_status='NOT_ESTABLISHED',vintage_rule_frozen=False,vintage_candidate_selected=None,fixed_latency_hours=None,researcher_decision_required=True,raw_data_modified=False,raw_integrity_verification_scope='40 selected raw files SHA256 + size + mtime; no whole-library rescan',old_output_runs_modified=False,historical_artifacts_verified=219,explicit_baselines_verified=14,full_raw_rescan=False,scientific_data_downloaded=False,official_documentation_lookup_performed=True,main_thermo_integration_performed=False,merged_files_created=False,dataset_created=False,sample_pairing_database_created=False,training_started=False,normalization_computed=False,split_created=False,bbox_frozen=False,covers_yunnan_context='PENDING_RESEARCHER_CONFIRMATION',dependencies_changed=False,python=str(PYTHON),targeted_cases=20,targeted_raw_files=40,source_token_pairs=12960,source_token_matching_pairs=12960,research_period_t_rh_complete_pairs=8820,research_period_t_rh_expected_pairs=8820,acquisition_conversion_code_status='NOT_FOUND_IN_SEARCH_SCOPE_OR_EXPLICIT_LOG_REFERENCES',tests=stats,staging=st,stage0_closeout_ready=False,main_baseline=str(BASE_MAIN),thermo_baseline=str(BASE_THERMO),finished_utc=datetime.now(timezone.utc).isoformat())
write_json(OUT/'audit_final_status.json',status)
ending='GFS provenance and vintage evidence audit complete.\nNo operational release time was fabricated.\nNo GFS main/thermo integration was performed.\nNo vintage rule was frozen automatically.\nResearcher scientific approval remains required.'
text=f'''# GFS provenance and vintage evidence audit

本轮审计工程 **PASS**；科学来源链仍 **SUPPORTED_WITH_CAVEATS**，总体保持 **PARTIALLY_COMPATIBLE**。

- **Question 1 / Dataset-layer combination：NEEDS_MORE_PROVENANCE**。
- **Question 2 / historical operational vintage：NOT_ESTABLISHED**。

本报告记录证据强度与缺口，不批准 main/thermo 组合，也不冻结 vintage。此前 DRY_RUN_FAILED 与后续旧 run 均作为历史保留。

## 1. Engineering status 与实际范围

engineering_status=PASS，audit_completion_status=COMPLETE_WITH_SCIENTIFIC_DECISIONS_PENDING。任务 A–P 的执行结果见 logs/task_completion_matrix.json；未找到代码/发布时间的结果明确标记 NOT_FOUND/NOT_ESTABLISHED，未将 NOT_RUN 当 PASS。

复用两轮既有主库与 thermo 审计，未全量重读 24388+12960 文件。本轮定向 20 cases/40 文件，覆盖 2023-03、2023-07、2024-01、2024-07、2025-03、2025-07、2025-10，各有 00/12 UTC；除 2024-01 只有可配 thermo f000 外，其余时期涵盖 f000/f003/f006。全部当前时间与坐标检查通过。

本地证据 inventory 219 文件；10 个 GFS manifest 共 87991 条记录，0 解析错误；168 个日志共 596255 行。搜索排除原始库、缓存及无关数据，随后仅定向补读三个旧 GFS processed 文件。证据行号、检索范围与读取限制均落盘。

## 2. Main GFS provenance chain

NCEP GFS 产品声明 → NCAR d084001 或 NOAA AWS 分发 → source/URL 内 forecast token → 2026 获取事件/NCSS query 或 AWS request → **原始/中间内容校验链 UNKNOWN** → **转换/标准化脚本未找到** → 当前 NetCDF 定向验证。

链条逐阶段的 confidence 见 PROVENANCE/provenance_chain.csv；DIRECT 是直接观测到记录，不是对记录宣称的载荷来源独立鉴真。主库 source/institution/references/title/center/process/history/original/archive/URL 的实际出现与缺失另见 main_source_field_coverage.json；缺失字段不补造。

## 3. Thermo provenance chain

d084001 源 URL 与同一 init/lead token → NCAR thermo manifest 中 downloaded/skipped/failed 事件 → **逐文件下载载荷到当前内容的校验链 UNKNOWN** → **本地写盘/转换代码未找到** → 当前 T/RH NetCDF。

creation history 是 2026 创建记录，不是 2023–2025 发布时刻。部分历史路径使用英语根目录；未证明其与当前中文根目录的物理映射。详见 thermo_pipeline_reconstruction.md。

## 4. Main vs thermo source relationship

官方 d084001 目录确认它是 NCEP operational GFS 的 0.25° analysis/forecast 历史归档，包含本任务对应循环，并指向 NOAA AWS copy；AWS registry 也标识 GFS bucket。由此推断两种来源属于同一 forecast family 有依据；这并不证明每个本地文件的转换和内容完全一致。[NCAR d084001](https://gdex.ucar.edu/datasets/d084001/)；[AWS 官方数据目录](https://registry.opendata.aws/noaa-gfs-bdp-pds/)。

NCAR/AWS/NCEP 同时出现在元数据中不自动构成冲突：生成机构、归档服务、分发途径及历史模板可分属不同字段。当前文档对动态时间范围/旧模型描述不用于推断历史具体版本或可用时间。

## 5. Original filename token evidence

从旧 source_lineage_fields.csv 的 metadata 原始源 token 重新对照 12960 对，12960 对当前 init/cycle/lead 与声明 family 一致，direct token conflict=0。没有只凭当前 .nc 名称判同源。source token、history token 分列，后者的 stale 项保留。independent GRIB content identity 仍 NOT_ESTABLISHED。

## 6. Conversion pipeline evidence

存在 NCSS 失败请求日志中的完整变量/bbox/accept=netcdf query、AWS 请求/完成记录、17 条模板选择日志，以及 metadata 中的 Netcdf-Java CDM / CFGridCoverageWriter、byte-range subset、provenance normalized 等文字。这些分别是请求记录与属性声明，不能提升为成功执行某一转换代码的证明。

两个历史日志调用片段指向 download_gfs.py；明确引用的当前工作区脚本路径读取结果为 NOT_FOUND，未搜索系统盘。获取/转换/2026-09-25 标准化源代码、版本与逐文件执行对应关系均未建立。没有伪造 INFERRED_FROM_SCRIPT 结论。

所选 forecast 的 91 条 manifest 事件中，37 complete、23 downloaded、30 skipped、1 failed；带大小的 60 条中 6 相同、54 不同、其余31无大小。重复记录不当作独立下载。大小不同表示无法直接关联当前版本，不表示当前文件损坏；后续处理可能解释差异，但没有据此声称已经证实原因。

旧 vintage index 的 8820 行，两分支大小各 8820/8820 对应当前 inventory；这是派生索引的一致性证据，不是上游内容或 official release 证明。

## 7. Auxiliary time conflict source

保留旧 17665 auxiliary conflict、其中 3628 stale-history 分类与 0 primary time conflict。扩展到所有 history 字段（含 legacy_history_before_20260925）后，已有主库表中 11805 行带非当前 token；matched-pair 范围 9385 行。11803 行至少有一个 token 对应已记录的模板文件命名。口径差异逐行保存在 TIME_LINEAGE/history_token_scope_reconciliation.csv。

日志确实选用模板，旧 token 确实能对应模板；“哪条赋值代码写入 History/udunits”仍 NOT_ESTABLISHED。没有修补、覆盖或改写 CF init/valid/lead。不能把扩大 history 检索得出的数量当作新增预报时间冲突。

## 8. 实际发现的时间字段

TIME_AVAILABILITY/time_evidence_inventory.csv 共124行，保存实际字段名与例值：initialization/forecast_cycle、valid_time、forecast_hour/lead_time_hours、CF valid/reference coordinate、auxiliary udunits、conversion_time、history created/Translation Date/metadata frozen、legacy_history、conservative_available_time_utc/availability_note、manifest recorded_at/recorded_utc、日志本地时钟、file_mtime_ns。

archive_time、observed publication time、保存的 remote Last-Modified/HTTP response Date 未找到可用事件证据，明确保留 UNKNOWN。无时区的日志时间未擅自解释为 UTC。

## 9. 不得作为 release 的字段

init、valid、lead 是 forecast 语义；creation/conversion/History 是后处理记录；mtime 是可变文件系统属性；download 是本地获取；archive/object 修改时间即使将来取得也需验证回填/重写语义；HTTP Date 是响应时间。以上均不能自动成为 operational 首发时刻。

旧 init+5h 和 frozen_utc 保留为旧文件内容；未采纳为当前科学规则。此处不指定任何替代 X。

## 10. Official release

operational_release_status=NOT_ESTABLISHED。官方产品身份/循环/服务说明未提供本研究历史文件的首次完整发布记录。没有利用当前对象头、下载时刻或转换时间伪造首发时间。

## 11. Local historical availability

local_historical_availability_status=PARTIALLY_ESTABLISHED，严格限定于 **2026 retrospective acquisition history**。manifest/log 能证明程序记录了当时的获取事件，内容版本链仍不完整。

**2023–2025 contemporaneous local availability=NOT_ESTABLISHED**。2026 回溯下载不能支持“目标时刻当时可获得”。失败与跳过均未转换为成功完成；日志时间不带偏移时保留未知时区。

## 12. Compatibility 是否升级

不升级。main、thermo 及二者 source_lineage_status 均 SUPPORTED_WITH_CAVEATS；总体仍 PARTIALLY_COMPATIBLE。官方 family 身份加强了证据，但获取、转换、当前内容链仍有关键缺口，不能自动宣布 COMPATIBLE_CANDIDATE 或 researcher approved。

## 13. 2023–2025 T/RH coverage

继续保留此前 24 个研究月份 8820/8820 complete-pair、T/RH 850/700/500 hPa 工程结论。全体 thermo 12960 matched、无 thermo-only/时间/grid 冲突。q 不代替 RH。该结论来自复用审计与本轮定向复核，没有全库重扫或生成样本配对数据库。

## 14. Dataset-layer combination question

**NEEDS_MORE_PROVENANCE**。PWAT/CAPE/U/V/PS 与 thermo T/RH 的 init/lead/grid 结构条件具备，但本轮不批准采用、不执行组合、merge、Dataset 或数据集准备。研究者需决定可接受的来源证据门槛。

## 15. Vintage candidates

A：真实官方首发；B：真实同时段本地获得；C：有适用官方文档支持的延迟规则；D：研究者指定 init+X 假设回放。各自所需证据、利弊、历史可回放范围、泄漏风险与可复现性见 TIME_AVAILABILITY/VINTAGE_RULE_CANDIDATES.md。四者均未选择，X=null，vintage_rule_frozen=false。

## 16. 仍需外部官方证据

EXTERNAL_EVIDENCE_REQUIRED.md 逐项列出历史 per-file 发布/完整可获取事件、产品年代对应 latency、archive 重写/回填语义、两端内容版本、NCSS 历史处理语义。当前只访问官方说明页面，未下载科研数据、未调用下载脚本、未联系第三方。还需恢复本地代码和路径迁移/内容校验记录。

## 17. Pytest

真实限定运行：**37 passed，0 failure，0 error，0 skipped**。覆盖直接/推断/未知证据、下载/mtime/转换/init 禁止替代 release、源 token 匹配及错误样例、原始路径边界、旧 run 哈希、candidate 不自动冻结、时间口径、事件失败保留与 CSV/Parquet 回读。

输出 tests/pytest_final_output.txt 与 tests/pytest_final.xml。22 个业务/保护 CSV 的 pyarrow Parquet 回读逐字段一致；为精确保留空字符串与 UNKNOWN，导出 schema 全部为字符串，语义状态有明确列。parquet_validation 自身也有双格式。

## 18. Raw integrity 与 staging

40 个原始样本 size/mtime/SHA256 前后完全一致；219 个历史证据文件同样一致；14 个明确复用的 baseline 哈希一致。该保护验证限于登记文件，不宣称全盘逐文件校验。所有原始/历史写入操作为0；旧诊断缓存未删除。

staging copy_count=40，copied_bytes=7510442，copy_seconds={st['copy_seconds']:.6f}，read_seconds={st['read_seconds']:.6f}，单次最大临时字节302316，32 MiB上限；cleanup_failures=0，remaining_staged_bytes=0。临时副本均验证SHA256；复制/读时长来自本次本地缓存状态，不是通用性能 benchmark。

## 19. Dependencies

解释器固定为 `{PYTHON}`；前后完整包清单一致，未安装/升级依赖。已实际 import zarr 3.4.0、numcodecs 0.17.0、pyarrow 25.0.1、netCDF4 1.7.4、xarray 2026.7.0、h5netcdf 1.8.1；完整日志见 environment_before/after.json。

## 20. Researcher decisions required

见 RESEARCHER_DECISIONS_REQUIRED.md：来源链最低门槛、转换/模板成因、historical vintage 目标语义及候选、固定 X 的依据、共同有效覆盖 bbox、Stage-0 科学关闭。covers_yunnan_context=PENDING_RESEARCHER_CONFIRMATION。实际 grid 范围只是观测记录。

## 21. Stage-0 closeout impact

本轮受限证据审计已完成，无待执行的已授权安全工程步骤。来源链/历史可用性未闭环，Stage-0 科学 closeout 仍 false；没有进入 B0、训练、normalization、split、正式 Dataset、插值、DOTE/DTFM/MEE。下一步需研究者审查，不以工程 PASS 覆盖科学不确定性。

{ending}
'''
write_text(OUT/'FINAL_GFS_PROVENANCE_VINTAGE_REPORT.md',text)
write_text(OUT/'logs/audit_completion.log',datetime.now(timezone.utc).isoformat()+' engineering PASS; 37 pytest passed; scientific decisions pending; no raw or old output writes\n')
# Existence and semantic gates before creating the final manifest.
required=['PROVENANCE/local_artifact_inventory.csv','PROVENANCE/local_artifact_summary.md','PROVENANCE/main_pipeline_reconstruction.md','PROVENANCE/thermo_pipeline_reconstruction.md','PROVENANCE/provenance_chain.csv','PROVENANCE/PROVENANCE_CHAIN_REPORT.md','PROVENANCE/main_source_fields_interpretation.csv','PROVENANCE/original_filename_token_comparison.csv','PROVENANCE/forecast_case_trace.csv','TIME_LINEAGE/conversion_history_origin.md','TIME_AVAILABILITY/time_evidence_inventory.csv','TIME_AVAILABILITY/VINTAGE_RULE_CANDIDATES.md','docs/DECISION_LOG_STAGE0_PROVENANCE_UPDATE.md','tests/pytest_final_output.txt','tests/pytest_final.xml','EXTERNAL_EVIDENCE_REQUIRED.md','FINAL_GFS_PROVENANCE_VINTAGE_REPORT.md','RESEARCHER_DECISIONS_REQUIRED.md','README.md','audit_final_status.json']
assert all((OUT/x).is_file() for x in required)
assert len(re.findall(r'^## \d+\.',text,flags=re.M))==21
assert text.rstrip().endswith(ending)
write_json(OUT/'logs/final_completeness_check.json',{'required_outputs':required,'required_output_count':len(required),'all_exist':True,'report_numbered_topics':21,'final_wording_exact':True,'no_missing_task_output':True,'engineering_not_scientific_approval':True})
manifest=[]
for p in sorted(OUT.rglob('*')):
 if p.is_file() and p.name not in ['output_manifest.csv','output_manifest.parquet']:
  manifest.append(dict(relative_path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=sha256(p)))
write_csv(OUT/'output_manifest.csv',manifest)
df=pd.read_csv(OUT/'output_manifest.csv',dtype=str,keep_default_na=False);df.to_parquet(OUT/'output_manifest.parquet',engine='pyarrow',index=False);pd.testing.assert_frame_equal(df,pd.read_parquet(OUT/'output_manifest.parquet'))
print(dumps({'status':status,'manifest_entries':len(manifest),'report':str(OUT/'FINAL_GFS_PROVENANCE_VINTAGE_REPORT.md')}))
