import json,re,collections,sys
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from config import *
from common import write_csv,write_json,write_text,dumps,sha256
from compat_rules import normalized_forecast_token
from provenance_rules import acquisition_link,vintage_candidates
sys.stdout.reconfigure(encoding='utf-8')
def read(p):return pd.read_csv(p,keep_default_na=False)
def md(rel,text):write_text(OUT/rel,text.strip()+'\n')
S=json.loads((OUT/'logs/evidence_extraction_summary.json').read_text(encoding='utf8'))
raw=json.loads((OUT/'PROVENANCE/selected_case_raw_metadata.json').read_text(encoding='utf8'))
D='https://gdex.ucar.edu/datasets/d084001/'
A='https://registry.opendata.aws/noaa-gfs-bdp-pds/'
C='https://gdex.ucar.edu/datasets/d084001/dataaccess/'
external=[dict(url=D,accessed_utc=datetime.now(timezone.utc).isoformat(),evidence_type='DIRECT_EVIDENCE',scope='official dataset description, not per-file observation',finding='d084001 is the NCEP operational GFS quarter-degree analysis/forecast archive; cycles 00/06/12/18; GRIB2; links NOAA AWS copy.',limitation='No local conversion attestation or historical per-file first-publication timestamps. Ignore dynamic temporal-end field inconsistent with audit clock.'),dict(url=A,accessed_utc=datetime.now(timezone.utc).isoformat(),evidence_type='DIRECT_EVIDENCE',scope='official hosting registry',finding='Registry identifies NCEP GFS and bucket noaa-gfs-bdp-pds, with NewGFSObject notifications.',limitation='No archived notification events obtained; notification availability is not historical timestamp evidence. Do not use stale general model-resolution descriptions to infer local grid.'),dict(url=C,accessed_utc=datetime.now(timezone.utc).isoformat(),evidence_type='DIRECT_EVIDENCE',scope='official access-service description',finding='Archive offers format conversion and spatial/parameter subsetting services.',limitation='Service capability does not prove which script or query produced any local file.')]
write_csv(OUT/'PROVENANCE/official_documentation_evidence.csv',external)
write_json(OUT/'logs/external_lookup_scope.json',{'only_documentation':True,'scientific_data_downloaded':False,'opened_urls':[D,A,C],'no_object_headers_or_grib_downloads':True})
write_json(OUT/'logs/referenced_script_lookup.json',{'reason':'Read exact project script paths identified by historical stack traces; no C drive search','paths':[r'C:\Users\chenerxiao\Documents\极端降水预测\scripts\download_gfs.py',r'C:\Users\chenerxiao\Documents\极端降水预测\scripts\run_full_pipeline.py'],'results':['NOT_FOUND','NOT_FOUND'],'historical_callsite':'full_pipeline_20260721_180015.log lines 50-64 and full_pipeline_20260724_102335.log lines 110-124','execution':False})
# Original-token / legacy metadata reconciliation. The old 3628 class is not a count of all legacy_* fields.
aux=read(BASE_THERMO/'TIME_LINEAGE/auxiliary_time_conflict_classification.csv');templates=read(OUT/'TIME_LINEAGE/template_log_evidence.csv')
template_tokens=set()
for r in templates.itertuples():
 for c,l in re.findall(r'gfs_0p25_(\d{10})_f(\d{3})',r.raw_event):template_tokens.add((c,int(l)))
recon=[]
for r in aux.to_dict('records'):
 ev=json.loads(r['source_token_evidence']);wanted=(r['init_time_unchanged'].replace('-','').replace(':','').replace('T','')[:10],int(float(r['lead_time_unchanged'])))
 stale=[tuple(x) for x in ev['history_tokens'] if tuple(x)!=wanted]
 if stale:recon.append(dict(relative_path=r['relative_path'],prior_classification=r['classification'],stale_history_tokens=dumps(stale),history_fields=dumps(ev['history_fields']),matches_logged_template_token=any(x in template_tokens for x in stale),cause='NOT_ESTABLISHED_WITHOUT_ASSIGNMENT_CODE',real_primary_time_conflict=r['true_forecast_time_conflict_detected']))
write_csv(OUT/'TIME_LINEAGE/history_token_scope_reconciliation.csv',recon)
write_json(OUT/'TIME_LINEAGE/history_token_summary.json',{'prior_auxiliary_conflicts':17665,'prior_stale_history_class':3628,'all_main_rows_with_any_stale_history_field':len(recon),'matched_pair_stale_history_fields':S['stale_history_in_matched_pairs'],'stale_rows_matching_logged_templates':sum(r['matches_logged_template_token'] for r in recon),'old_classification_counts':aux.classification.value_counts().to_dict(),'new_primary_time_conflicts':0,'scope_difference':'Prior classification preserved. Expanded history key search includes legacy_history_before_20260925; not a new time error or raw-file change.'})
# Field inventory: retain observed names and an actual example from every prior global-metadata key.
timefields={}
for branch,p in [('main',BASE_MAIN/'GFS/global_metadata_patterns.jsonl'),('thermo',BASE_THERMO/'THERMO/global_metadata_patterns.jsonl')]:
 with p.open(encoding='utf8') as f:
  for line in f:
   obj=json.loads(line)
   for k,v in obj['global_attrs'].items():
    if re.search('time|date|history|forecast_hour|lead|availability',k,re.I):timefields.setdefault((branch,k),(str(v),str(p),obj.get('example','')))
rows=[]
def add(source,field,example,semantic,reason,confidence='DIRECT'):
 rows.append(dict(source=source,field=field,example=example,semantic_class=semantic,usable_as_operational_release=False,reason=reason,confidence=confidence))
for (branch,k),(v,p,example) in sorted(timefields.items()):
 kl=k.lower()
 semantic='CONSERVATIVE_ASSUMPTION' if 'conservative' in kl or 'availability' in kl else 'FORECAST_VALID_TIME' if 'valid_time' in kl else 'FORECAST_REFERENCE_TIME' if 'initialization' in kl or kl=='forecast_cycle' else 'FORECAST_LEAD_DURATION' if 'lead' in kl or 'forecast_hour' in kl else 'CONVERSION_TIME' if 'conversion' in kl else 'CREATION_CONVERSION_OR_LEGACY_PROVENANCE' if 'history' in kl else 'UNRESOLVED_TIME_METADATA'
 add(p+' example='+example,k,v,semantic,'Observed metadata content only; not independently observed first operational publication')
for item in raw:
 tm=json.loads(item['time']['raw_time_metadata'])
 for field,value in tm.items():
  add(item['path'],field,dumps(value),'CF_FORECAST_COORDINATE_WITH_AUXILIARY_METADATA','CF/reference/valid/udunits clocks are forecast semantics, not delivery clocks')
events=read(OUT/'TIME_AVAILABILITY/download_manifest_case_events.csv')
for field,ex,sem,reason in [('recorded_at/recorded_utc',events.local_timestamp.iloc[0],'LOCAL_MANIFEST_EVENT','Complete/downloaded records are local 2026 acquisition evidence; skipped/failed are not completion. No content hash and no 2023-2025 receipt.'),('local log timestamp','2026-07-26 10:32:08','LOCAL_LOG_CLOCK_TIMEZONE_UNKNOWN','Timezone not explicit; not converted to UTC'),('file_mtime_ns',str(read(OUT/'logs/selected_raw_manifest_before.csv').mtime_ns.iloc[0]),'FILESYSTEM_MTIME','Mutable filesystem clock; never release'),('archive_time','NOT_FOUND_AS_OBSERVED_EVENT','UNKNOWN','Archive name/path is not a timestamp'),('remote Last-Modified','NOT_SAVED_IN_SEARCHED_RECORDS','UNKNOWN','Even an object modification timestamp would need archive-overwrite/backfill semantics'),('HTTP response Date','NOT_SAVED_IN_SEARCHED_RECORDS','UNKNOWN','Server response time is not first publication'),('observed publication time','NOT_FOUND','OBSERVED_OFFICIAL_PUBLICATION','No per-file official observation supplied')]:
 add('Local evidence search',field,ex,sem,reason,'UNKNOWN' if ex.startswith('NOT_') else 'DIRECT')
write_csv(OUT/'TIME_AVAILABILITY/time_evidence_inventory.csv',rows)
write_json(OUT/'TIME_AVAILABILITY/vintage_candidates.json',vintage_candidates())
# Distinguish event matching from identity verification; enrich current-run trace only.
links=[]
for r in events.to_dict('records'):
 size=r['recorded_size'];size=float(size) if size!='' else None
 links.append(dict(case_id=r['case_id'],branch=r['branch'],evidence_path=r['evidence_path'],line=r['line'],status=r['status'],link_status=acquisition_link(r['recorded_path'],r['current_path'],size,r['current_size']),local_timestamp=r['local_timestamp'],operational_release_time='',release_established=False))
write_csv(OUT/'PROVENANCE/case_acquisition_links.csv',links)
trace=read(OUT/'PROVENANCE/forecast_case_trace.csv')
trace['historical_manifest_evidence']=trace.case_id.map(lambda cid:dumps([x for x in links if x['case_id']==cid]))
trace['current_content_to_acquisition_chain']='NOT_ESTABLISHED'
trace.to_csv(OUT/'PROVENANCE/forecast_case_trace.csv',index=False,encoding='utf-8-sig')
chains=[]
for b in ['main','thermo']:
 stages=[('upstream provider','DIRECT_EVIDENCE',D,'Official description identifies NCEP operational GFS','DIRECT'),('upstream dataset/product','DIRECT_EVIDENCE',D+' ; '+A,'d084001 and NOAA GFS bucket support same forecast family, not an independent reanalysis identification','STRONG'),('original filename pattern','DIRECT_EVIDENCE',str(OUT/'PROVENANCE/original_filename_token_comparison.csv'),'12960 paired source-metadata tokens match init/cycle/lead; direct and legacy History fields kept separately','DIRECT'),('download method','DIRECT_EVIDENCE',str(OUT/'TIME_AVAILABILITY/download_manifest_summary.csv'),'Main AWS/NCSS records; thermo NCAR manifests and NCSS URL attributes. Records are retrospective 2026 events.','PARTIAL'),('raw/intermediate file','NOT_ESTABLISHED',str(OUT/'PROVENANCE/case_acquisition_links.csv'),'No independent downloaded-GRIB checksum -> conversion -> current-NetCDF checksum chain; matching logical case or bytes is insufficient','UNKNOWN'),('conversion/subset script','NOT_ESTABLISHED',str(OUT/'logs/referenced_script_lookup.json'),'download_gfs.py referenced by historical log but not located; no acquisition/conversion code read or executed','UNKNOWN'),('current NetCDF','DIRECT_EVIDENCE',str(OUT/'PROVENANCE/selected_case_raw_metadata.json'),'20 targeted files per branch reread, SHA256-protected; current coords and forecast identity match','DIRECT')]
 for stage,etype,path,val,conf in stages:chains.append(dict(dataset_branch=b,stage=stage,evidence_type=etype,evidence_path=path,evidence_value=val,confidence=conf))
write_csv(OUT/'PROVENANCE/provenance_chain.csv',chains)
md('PROVENANCE/local_artifact_summary.md',f'''# 本地证据范围与限制
检索 F:/pytorch/Research 与 F:/云南极端降水数据 中相关工程文本，排除原始数据、缓存、无关数据集及大型输出目录；明确复用的 14 个旧审计产物例外。搜索配置见 logs/search_scope.json。

本轮 inventory 共 {S['artifact_count']} 个文件：202 个本地日志/manifest、14 个复用审计文件、3 个按完成报告引用定向读取的旧 GFS processed 索引/配置。初筛每个文件最多 2 MiB，随后完整读取 10 个相关 GFS JSONL manifest（{S['manifest_records']} 行）与 168 个相关日志（{S['log_lines']} 行）；解析错误 0。旧审计是二次证据，不伪装成独立下载证据。

没有在限定检索范围找到获取/转换源代码。日志直接提到 download_gfs.py；具体工作区路径定向读取结果 NOT_FOUND，见 logs/referenced_script_lookup.json；未扫描系统盘。两个脚本调用片段只证明调用名称，不证明代码内容或运行版本。

下载事件表保留 failed、skipped、downloaded、complete。所选 case 的 91 个事件中 60 个带大小，6 个相同、54 个不同、31 个无大小；重复 manifest 行不是独立下载次数。英语历史根目录与当前中文根目录的物理同一性未建立。旧 vintage index 的 8820 行，两分支大小均与现有审计 inventory 相符，但没有内容哈希，不是发布记录；其旧 frozen 字样不是本轮科研批准。

官方网页只作产品/服务文档核查，未获取 GRIB、NetCDF、对象头或新的科研数据。官方说明及限制见 official_documentation_evidence.csv。''')
for b in ['main','thermo']:
 ismain=b=='main'
 md(f'PROVENANCE/{b}_pipeline_reconstruction.md',f'''# {b} pipeline reconstruction

| 问题 | 结论与证据级别 |
|---|---|
| Provider/product | DIRECT_EVIDENCE：官方 d084001 文档及本地 source/token 指向 NCEP operational GFS family；见 official_documentation_evidence.csv。 |
| 下载位置 | DIRECT_EVIDENCE：{'AWS noaa-gfs-bdp-pds 与 NCAR NCSS 两种来源在主库字段/日志中出现；provider 与 archive/mirror 角色不同，不构成天然冲突' if ismain else 'source URL 是 NCAR THREDDS NCSS 的 d084001 路径；本地 thermo manifest 记录获取事件'}。 |
| 上游格式 | DIRECT_EVIDENCE：官方文档为 GRIB2，本地上游 token/URL 含 .grib2 或 pgrb2；没有重新打开上游载荷证明其内容。 |
| 变量 | DIRECT_EVIDENCE：{'当前主库包含 PWAT/CAPE/U/V/PS；T/RH 覆盖以既有 variable mapping 为准，不能凭 whitelist 推定每文件具备全部变量' if ismain else '当前 thermo 具备 T/RH 的 850/700/500 hPa，T=K、RH=%；q 不代替 RH'}。定向实际变量属性保存在 selected_case_raw_metadata.json。 |
| GRIB→NetCDF | DIRECT_EVIDENCE：本地属性声明转换/创建，当前文件确为 NetCDF；NOT_ESTABLISHED：逐文件上游内容到当前载荷的转换证明。 |
| 转换工具 | {'DIRECT_EVIDENCE：部分 metadata 写有 Netcdf-Java CDM / CFGridCoverageWriter，AWS byte-range subset 属性及模板日志也存在；这只是声明/日志证据' if ismain else 'NOT_ESTABLISHED：创建 history 与 NCSS URL 不足以确定本地写盘库、版本及代码'}。不能把本轮 netCDF4 reader 当历史转换器。 |
| spatial subset | DIRECT_EVIDENCE：实际 53×57、0.25°，95–109°E、19–32°N；{'日志 NCSS query 明确 north/south/east/west，requested_domain 属性也有记录' if ismain else 'source 为 NCSS 服务路径，当前区域坐标确定，但未找到完整原始 query/转换代码'}。区域只是实际覆盖，非 bbox 冻结。 |
| variable subset | DIRECT_EVIDENCE：{'部分请求 query 列出变量，某些当前文件 metadata 声明排除降水；旧索引仍有 5452 文件 precipitation 字段，不可用文件成员资格替代 predictor whitelist' if ismain else '实际 T/RH/q 变量集合及 pressure_level 可核查'}；NOT_ESTABLISHED：所有历史请求参数/版本。 |
| time 改写 | NOT_ESTABLISHED：没有转换赋值代码；当前 CF 与 init+lead 通过不证明历史未改写。 |
| history 改写 | {'DIRECT_EVIDENCE：存在 legacy_history_before_20260925 与新版 History 的并存，且 History 声明 provenance normalized；NOT_ESTABLISHED：对应脚本/赋值行、执行版本' if ismain else 'DIRECT_EVIDENCE：history 保存 2026 创建文本；NOT_ESTABLISHED：生成该字段的源代码'}。 |
| auxiliary reference 生成 | NOT_ESTABLISHED：未找到赋值代码，保留原有 CF/udunits 差异。 |
| 可读脚本 | NOT_ESTABLISHED：没有定位到源代码，因此本轮不虚构 INFERRED_FROM_SCRIPT 结论。 |

INFERRED_FROM_FILENAME 仅可用于命名结构；本轮同源判断采用 metadata 内上游 token，不只采用当前 .nc 文件名。DIRECT_EVIDENCE 表示确实看见该记录，不能提升成对其所宣称内容的独立鉴真。''')
md('PROVENANCE/PROVENANCE_CHAIN_REPORT.md','''# 来源链结论

main_provenance_status = SUPPORTED_WITH_CAVEATS
thermo_provenance_status = SUPPORTED_WITH_CAVEATS
main_thermo_source_lineage_status = SUPPORTED_WITH_CAVEATS
compatibility = PARTIALLY_COMPATIBLE
Dataset-layer question = NEEDS_MORE_PROVENANCE

官方产品身份、12960 组原始 source token、20 组当前文件复核共同支持同一 forecast family 和按 init/lead 配对的工程解释。NCAR 是归档/子集服务，NOAA/NCEP 是生成机构，AWS 是分发途径；多字段出现这些名称不自动构成来源冲突。

关键缺口仍为获取源代码/执行版本、上游载荷或中间文件校验和、当前文件内容与历史转换的关联。60 条带大小的所选事件中 54 条与当前文件大小不同，不能直接关联；大小相同的 6 条也不能替代内容哈希。英语历史根目录映射未证实。文件后续标准化是一种可能解释，不作为已证实原因。

旧索引 8820 行两分支大小全部符合当前 inventory，加强该派生索引的对应关系，但不足以追到上游 GRIB。当前结论保留 caveats，不建议自动升级 COMPATIBLE_CANDIDATE，不建议拒绝已通过的结构/时间/变量证据。研究者决定还需要什么 provenance 才能进入组合准备。
''')
hs=json.loads((OUT/'TIME_LINEAGE/history_token_summary.json').read_text(encoding='utf8'))
md('TIME_LINEAGE/conversion_history_origin.md',f'''# conversion history origin

DIRECT_EVIDENCE：旧分类为 17665 个 auxiliary metadata conflict，其中 14037 为 ALTERNATIVE_REFERENCE_TIME、3628 为 STALE_HISTORY_TOKEN;ALTERNATIVE_REFERENCE_TIME，真实 forecast time conflict 为 0。原分类表保持不变。

DIRECT_EVIDENCE：本轮将所有含 history 的字段（含 legacy_history_before_20260925）纳入文本 token 对照，已有主库证据表中 {len(recon)} 行含非当前 token；其中已匹配 thermo 的范围为 9385 行。这与旧 3628 的分类口径不同，不能当作新增原始时间冲突。详细逐行映射见 history_token_scope_reconciliation.csv。

DIRECT_EVIDENCE：17 条 AWS templates 日志明确记录模板文件。其中 gfs_aws_primary_20260726_103206.log 第 2 行的 instant 模板为 2023062212_f000；在当前文件 legacy_history 中可见相同上游 token。扩展 stale 行中 {hs['stale_rows_matching_logged_templates']} 行至少有一个 token 与日志模板命名相符。该 token 描述另一个 forecast，Translation Date 描述转换时间，二者都不是 operational release。

NOT_ESTABLISHED：模板属性复制可以解释部分旧 token，但未定位到转换脚本，不能证明具体哪条赋值语句写入 History/udunits，不能把“模板复用”确认为已闭环成因。udunits 原始参考值、CF units 及主时间保持原状；未 flip、重写、修补或回填。

DIRECT_EVIDENCE：metadata 中 legacy_history_before_20260925 与 provenance normalized History 并存，能证明当前属性内容；NOT_ESTABLISHED：2026-09-25 标准化的具体代码版本与逐文件执行记录。
''')
md('TIME_AVAILABILITY/VINTAGE_RULE_CANDIDATES.md','''# Vintage rule candidates — researcher review only

没有候选被选择；vintage_rule_frozen=false；X 未指定。旧文件中的 init+5h 只保留为历史假设。所有回放规则还必须约束 forecast 身份、输入数据完整性、决策时刻及 endpoint 的含义。

| 候选 | 所需证据 | 优点 | 局限 / 历史回放 | 泄漏风险 | 可复现性 |
|---|---|---|---|---|---|
| A 真实 operational release | 2023–2025 每个 init/lead 对应的可验证首发/完整可获取时间，发布端及重发语义 | 最接近当时可获得信息 | 当前 NOT_ESTABLISHED；有完整历史记录才可回放 | 用重传/入库/最后修改替代首发会错判；需完整变量可用时间 | 保存原始日志、签名/校验和、UTC 与事件语义 |
| B 历史本地 download/availability | 同时段真实本地成功接收记录、内容哈希、机器时区、文件身份 | 能重放特定本地系统当时可见内容 | 现有是 2026 回溯获取，不能倒推 2023–2025 的近实时可用性 | 把 2026 获得的数据回填至旧 forecast 时间会泄漏假设 | 完整留存收件记录可复现本地获取史；本轮大小/路径关联仍不闭环 |
| C 官方 documented release latency | 对应产品、端点、年代、cycle/lead 的官方延迟定义与异常处理，研究者批准保守界限 | 可形成文档依据一致规则 | 当前页面只有产品/周期说明，无历史 latency 保证；规则回放不是逐文件观测 | 常规发布计划忽略延迟、故障和重发 | 保存文档版本、适用年代、端点与选用理由 |
| D 固定 init+X fallback | 研究者明确 X、适用范围、依据、敏感性与异常策略 | 简单，可复现 | 仅假设情景回放，不建立真实 operational availability；本轮不指定 X | 延迟过短可能使用当时未完成文件；过长改变输入可用性 | 版本化参数和假设，明确标注为假设 |

日志 download time 仅可说明其事件时刻的本地获取；skipped 只证明程序报告跳过，failed 不能记作成功。mtime、conversion、CF init/valid、History 与 archive date 均不得自动当 release。AWS NewGFSObject 服务存在不代表已拿到历史消息。''')
md('EXTERNAL_EVIDENCE_REQUIRED.md',f'''# External evidence still required

已通过官方文档核实产品角色：[{D}]({D})；AWS bucket 注册：[{A}]({A})；转换/子集服务能力：[{C}]({C})。这些是当前文档，不是当年文件的发布或本地转换证明。没有下载科研数据。

| 需核实事项 | 推荐官方来源/标识 | 具体问题与本地不足 |
|---|---|---|
| 历史 operational 首发 | NCEP/NCO GFS pgrb2.0p25 f000/f003/f006；NOAA NODD、NewGFSObject 历史事件 | 2023–2025 对应 endpoint/cycle/lead 的首次完整可获取时间是否留存？本地只有 2026 回溯获取记录。 |
| documented latency | [NCEP GFS 产品页](https://www.nco.ncep.noaa.gov/pmb/products/gfs/) 与年代对应服务变更通知 | 周期不是延迟；是否存在年代/产品适用的发布窗口、异常或 SLA？未核实，不选择 X。 |
| archive/镜像重写语义 | NCAR d084001 DOI 10.5065/D65D8PWK、NOAA AWS GFS archive | 回填、重发、修订、archive date 与 object Last-Modified 各代表什么？本地未保存 headers，不能从归档日期反推首发。 |
| 逐 forecast 内容一致性 | 两端具体 original filename 与版本/校验记录 | 相同 family/token 能否确认相同 cycle/lead 的相同变量内容版本？元数据声明不足以独立证明 payload。 |
| 历史 NCSS 处理 | NCAR THREDDS NCSS / NetCDF-Java 服务版本与请求回执 | 指定 query 是否做了额外重网格、时间/属性转换？当前服务能力页不证明历史执行过程。 |

本地另需恢复 download_gfs.py、AWS/thermo/标准化脚本的确切版本与执行记录、英语/中文根目录迁移记录及内容校验。以上只列需求，不执行下载、联系第三方或科研决策。''')
md('RESEARCHER_DECISIONS_REQUIRED.md','''# Researcher decisions required

1. 当前来源链为 SUPPORTED_WITH_CAVEATS；是否要求找回获取、转换、2026-09-25 metadata 标准化代码与上游/中间校验和后，才批准 main PWAT/CAPE/U/V/PS 与 thermo T/RH 组合准备。本轮回答 NEEDS_MORE_PROVENANCE，未组合。
2. 审查原有 3628 stale 分类与扩大 history 字段范围后的计数差异。不能把 legacy token 当当前 forecast 或由此重写主时间。
3. 批准 vintage 的目标语义与 A/B/C/D 选择条件；目前 operational release 与研究期 contemporaneous local availability 均 NOT_ESTABLISHED。2026 获取史不得改称当时可用。
4. 固定延迟若最终采用，由研究者指定 X、依据与敏感性设计；旧 +5h 未获本轮批准。
5. covers_yunnan_context 继续 PENDING_RESEARCHER_CONFIRMATION。实际 95–109E、19–32N 只是记录，未冻结共同 bbox。
6. Stage-0 整体关闭及进入 B0 仍需科研批准；本次审计工程完成不会自动消除科学待决项。
''')
md('docs/DECISION_LOG_STAGE0_PROVENANCE_UPDATE.md',f'''# Stage-0 provenance decision update

仅新 run 增量记录；旧 decision log、DRY_RUN_FAILED 及所有旧报告不覆盖。

## FROZEN_ENGINEERING_EVIDENCE
既有主库 24388、thermo 12960 的审计表复用；12960 一对一对应、研究期 8820/8820 T/RH complete。20 cases/40 raw 定向复核时间、坐标通过，完整保护结果见 logs/integrity_verification.json。本轮所有“冻结”仅指本次记录证据，不代表科学批准。

## PROVISIONAL
同一 operational GFS family 的解释获官方文档加强；local provenance 仍 SUPPORTED_WITH_CAVEATS。主库 NCAR/AWS 是 provider/archive/retrieval 的不同角色；旧模板继承解释待代码确认。旧索引大小对应 8820/8820 不等于内容校验。

## NOT_YET_FROZEN
vintage_rule、延迟 X、研究者批准的 main+thermo 组合、共同 bbox 全部未冻结。历史 processed whitelist 的 frozen_utc 与旧 init+5h 字段不自动继承科研批准。

## RESEARCHER_DECISION_REQUIRED
来源链最低可接受证据；历史 operational 可用性定义；A/B/C/D 选择；辅助 history 的科学解释；Stage-0 closeout。Q1 NEEDS_MORE_PROVENANCE；Q2 NOT_ESTABLISHED。''')
md('README.md',f'''# GFS provenance / vintage evidence resolution

本轮目录：`{OUT}`。固定解释器：`{PYTHON}`。只读旧日志、manifest、审计表和 40 个预先登记的定向原始文件。没有全库重扫、合并、训练或依赖升级。

- 入口结论：FINAL_GFS_PROVENANCE_VINTAGE_REPORT.md、audit_final_status.json。
- 证据：PROVENANCE/、TIME_LINEAGE/、TIME_AVAILABILITY/；来源和行号保留在表中，所有表提供 CSV/pyarrow Parquet，写入/回读检查见 logs/parquet_validation.csv。
- 准入：NEEDS_MORE_PROVENANCE；historical operational vintage NOT_ESTABLISHED。工程测试通过也不替代科研批准。
- 执行源：src/discover_artifacts.py → src/trace_cases.py → src/extract_evidence.py → src/resolve_evidence.py → src/verify_integrity.py → scoped pytest → src/finalize.py。脚本使用独占新建输出，不能盲目重跑覆盖；新执行应复制到新 run 并更新 config。
- 原始文件只读。英文 staging 上限 32 MiB、单文件逐次复制，校验大小与 SHA256，使用 netCDF4 只读，随后仅清理本轮拥有的临时副本。copy/read 秒数与 bytes 保留 logs/staging_io.jsonl。历史诊断缓存未清理。
- 无 release 推算；未知字段明确 UNKNOWN/NOT_ESTABLISHED，不用 0、空时间或 NOT_RUN 冒充 PASS。缺失时间在表中留空并提供状态列。
- 旧 run 为历史证据，未重写；本轮有限 SHA256 核查不宣称全盘逐文件哈希验证。output_manifest.csv 记录最终产物哈希，自身不自引用。
''')
print(dumps({'history_summary':hs,'time_evidence_rows':len(rows),'chains':len(chains),'reports_written':True}))
