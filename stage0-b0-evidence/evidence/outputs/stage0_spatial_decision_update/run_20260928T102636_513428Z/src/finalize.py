import json,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from config import *
from frozen_contract import sha,verify_frozen
sys.stdout.reconfigure(encoding='utf8')
def j(p):return json.loads((OUT/p).read_text(encoding='utf8'))
def put(p,text):
 with (OUT/p).open('x',encoding='utf8') as f:f.write(text.strip()+'\n')
def outjson(p,v):put(p,json.dumps(v,ensure_ascii=False,indent=2))
r=j('freeze_registry.json');i=j('logs/integrity_summary.json');root=ET.parse(OUT/'tests/pytest_final.xml').getroot();s=root.find('testsuite');stats={k:int(s.attrib.get(k,0)) for k in ['tests','failures','errors','skipped']};assert stats=={'tests':21,'failures':0,'errors':0,'skipped':0};assert verify_frozen(OUT)['status']=='PASS'
assert all(i[k] for k in ['all_size_mtime_unchanged','sha256_all_checked_unchanged','dependencies_unchanged'])
put('docs/RESEARCHER_APPROVAL_RECORD.md','''# Researcher Stage-0 spatial decision

Authority: the researcher's explicit decision in this chat, received before this decision-update run. This is a faithful scope record, not an additional approval request.

1. Main evaluation remains the whole Yunnan provincial administrative mask.
2. Adopt GADM4.1 China Level1 Yunnan feature; all NAME_1/GID_1/HASC_1/ISO_1/ENGTYPE_1 identities must match, preserve source/version/CRS/geometry/archive hashes; no silent boundary replacement.
3. Adopt the verified 130x140/3430-cell center-in-polygon candidate using actual IMERG coordinates, not synthesized coordinates.
4. Preserve intersection candidate for boundary sensitivity/engineering comparison, not primary evaluation.
5. Freeze raw/SRTM as current primary DEM source; retain AWS_Skadi separately without merging or deletion.
6. Model-input bbox and weather-system context margin are not frozen.
7. 97–107E,20–30N is CANDIDATE COMMON NUMERICAL OVERLAP only.
8. DEM aggregation, slope/aspect/relief/curvature parameters, and formal dh/dx,dh/dy production remain unfrozen.
9. Freeze the principle that DOTE gradients require real physical distances; degree-index gradients are not physical gradients.
10. New run only, old audits read-only. Stop on completion. No B0, DEM resampling or formal DOTE features.
''')
put('COMPARISON/ROLE.md','''# NON_PRIMARY_EVALUATION_MASK

The intersection NetCDF here is a SHA256-identical copy of the previous engineering candidate. It remains available for boundary sensitivity / engineering comparison only. Its 3752 selected cells and 322-cell difference from the official center mask are preserved. It is not the formal main evaluation mask.

No prior candidate file was modified or deleted. Roles are registered in freeze_registry.json.
''')
put('docs/DECISION_LOG_STAGE0_SPATIAL_FREEZE_UPDATE.md',f'''# Stage-0 spatial scientific decision update

Decision authority: researcher explicit approval. Freeze ID: `{r['freeze_id']}`. This log adds a new approved state; the prior audit's PROVISIONAL/NOT_YET_FROZEN statements remain immutable historical records.

## FROZEN

- 最终主评价范围为云南省全境行政区mask。
- 当前正式边界：GADM4.1 China Level1、云南feature CHN.30_1；全部五项身份字段同时匹配。
- 正式evaluation mask：center-in-polygon，实际IMERG130×140 grid，true=3430，lat ascending，lat/lon exact match；承接获批候选的strict interior语义，当前恰在边界的中心数0。
- 当前正式DEM主来源：F:/云南极端降水数据/raw/SRTM；对冻结polygon为FULL，无云南NoData gap。此处冻结source，不冻结DEM生产方法。
- DOTE地形梯度必须基于真实物理距离；不得把经纬度索引gradient当物理梯度。

## NOT_YET_FROZEN

model_input_bbox；省界外weather-system context margin；DEM聚合/重采样方法；slope/aspect/relief/curvature参数；dh/dx、dh/dy正式生产流程。

97–107°E、20–30°N继续标记CANDIDATE COMMON NUMERICAL OVERLAP，不能当正式model-input bbox。intersection mask是非主评价敏感性对照；AWS_Skadi保留独立辅助地位。

## RESEARCHER_DECISION_REQUIRED

未来具体bbox/context宽度、DEM聚合方式、正式地形特征参数与gradient生产流程，由研究者另行决定。已获批的当前边界版本、中心mask及SRTM主来源无需再次批准；如将来替换，必须显式决策并建立新版本，不覆盖本run。

## Validation and stop

21项pytest通过；原始输入及旧run无写入，保护范围及哈希见logs/integrity_summary.json。未生成正式DEM/model-input grid/DOTE特征，未开始B0，未改变GFS provenance/vintage或研究年份。当前决策完成后停止。
''')
put('README.md',f'''# YunTAPR-Net approved spatial freeze

This run is the current researcher-approved spatial decision snapshot: `{r['freeze_id']}`.

Primary boundary: FROZEN/BOUNDARY/yunnan_gadm41_level1_boundary.geojson.
Primary evaluation mask: FROZEN/MASK/yunnan_evaluation_mask_center_gadm41_imerg_v1.nc.
Authority and content-addressed registration: freeze_registry.json. Registry SHA256: `{sha(OUT/'freeze_registry.json')}`.

Before consuming frozen files, call `verify_frozen(run_path)` from src/frozen_contract.py. It checks all artifact hashes, all five identity attributes, geometry hash, exact coordinate arrays, ascending orientation, dimensions, 3430 cells and center predicate. A replaced artifact raises ValueError. The registry and report are versioned evidence, not a claim of filesystem-enforced write protection.

The original candidate is byte-preserved under PROVENANCE; the formal mask was copied from it and only its global metadata changed. All variables, dtype, dimensions and values are unchanged. Its inherited cell-bounds arrays do not freeze an input-grid/aggregation convention; the primary rule uses centers only.

Archive source and original-member hashes, canonical original-geometry JSON hash, normalized WKB supplementary hash, coordinate hashes and generation-script hashes are saved. Geometry-hash definitions are explicit. Original raw MultiPolygon structure is preserved; the old union Polygon has identical spatial geometry and center-mask values. No geometry repair/simplification was performed.

COMPARISON intersection is non-primary and byte-identical to old candidate. DEM root inventory registers SRTM without creating a DEM product. AWS_Skadi remains separate. Remaining choices are listed in the report and new decision log.

Python: `{PYTHON}`; dependencies unchanged. Source raw IMERG coordinates were reread through one 380398-byte English temporary copy with size/SHA256 verification, then cleaned. No raw or old-run writes. No next-stage work.

For a future version, require an explicit researcher change decision and a new run; do not rerun freeze.py into this completed directory or overwrite this registry.
''')
b=r['boundary'];a=r['artifacts'];h=r['mask']
report=f'''# STAGE0 SPATIAL DECISION FREEZE REPORT

**执行状态：PASS / RESEARCHER_APPROVED_SPATIAL_CONVENTIONS_FROZEN。**

本轮依据研究者明确批准，将指定边界、中心点评价mask与SRTM主来源纳入当前正式执行规范。Freeze ID：`{r['freeze_id']}`。独立新run：`{OUT}`。旧审计结果保留不变，本轮更新不改写此前候选状态的历史记录。

## FROZEN

| 项目 | 当前正式约定 |
|---|---|
| 主评价范围 | 云南省全境行政区mask，原冻结原则继续保持 |
| 边界来源/版本 | GADM4.1，中国Level-1，云南feature CHN.30_1 |
| 身份判据 | NAME_1=Yunnan；GID_1=CHN.30_1；HASC_1=CN.YN；ISO_1=CN-YN；ENGTYPE_1=Province，五项同时确认 |
| 边界CRS | urn:ogc:def:crs:OGC:1.3:CRS84；WGS84 longitude/latitude 顺序 |
| 正式mask | center-in-polygon，继承已获批候选strict interior contains；本grid中心恰在polygon边界的数量为0 |
| 科学target grid | 真实IMERG lat/lon；130×140；float32原坐标不变；纬度ascending |
| mask true/false cells | 3430 / 14770 |
| DEM主来源 | F:/云南极端降水数据/raw/SRTM，共237个原始归档；对冻结polygon FULL、云南及省界附近无NoData gap |
| DOTE物理约束 | dh/dx、dh/dy必须基于真实物理距离；经纬度索引gradient不得当作物理梯度 |

### 正式文件与来源链

正式边界：`{a['boundary']['relative_path']}`。
正式主评价mask：`{a['primary_mask']['relative_path']}`。
坐标锚：`{a['coordinates']['relative_path']}`。
统一冻结登记：`freeze_registry.json`。

原始archive路径：`{b['original_archive_path']}`。
成员文件：`{b['archive_member']}`，feature index（0-based）={b['feature_index_zero_based']}，identifier={b['feature_identifier']}。
原archive副本和成员原字节均保存；正式GeoJSON保留该raw feature全部properties与原始geometry。

| 哈希对象 | SHA256 |
|---|---|
| 原始archive及冻结副本 | `{b['original_archive_sha256']}` |
| 原始GeoJSON成员字节 | `{b['member_sha256']}` |
| 正式boundary文件 | `{a['boundary']['sha256']}` |
| 原始geometry规范JSON | `{b['geometry_sha256']}` |
| normalize后2D little-endian WKB（辅助） | `{b['normalized_wkb_sha256']}` |
| 获批center候选原文件 | `{h['candidate_source_sha256']}` |
| 正式主评价mask文件 | `{a['primary_mask']['sha256']}` |
| latitude coordinate hash | `{h['lat_hash']}` |
| longitude coordinate hash | `{h['lon_hash']}` |
| freeze_registry.json | `{sha(OUT/'freeze_registry.json')}` |

geometry JSON哈希使用原始geometry对象、sort_keys、紧凑separators、UTF-8，不对坐标舍入或排序。coordinate hash沿用正式P0算法：shape ASCII加little-endian float64数值C-order、signed zero规范化；正式文件坐标仍保持源float32，不是转成float64重建。

生成脚本哈希保存在PROVENANCE/generator_script_hashes.json：包括旧build_masks.py/spatial_rules.py/config.py/common.py的原路径和原字节副本，以及本轮freeze.py/frozen_contract.py/config.py。完整产物清单附每文件SHA256。

### 几何表示核验与provenance

初次严格表示相等检查停止后，已查明：原始feature是单部分MultiPolygon，旧工程候选经过union成为Polygon；两者均4418个坐标点，拓扑完全相等，symmetric difference面积0，规范化union表示精确一致。正式边界保持原始MultiPolygon，未修复、简化或改动raw geometry；正式mask与该原始geometry的中心判定逐值相同。

差异、核查和恢复记录保存在PROVENANCE/geometry_representation_comparison.json与logs/preflight_geometry_check_history.json。旧audit未修改。来源可追溯至该本地GADM归档、feature、既有审计与当前研究者批准；本次未新增官方下载凭据，也未把研究者采用声明成外部来源认证。

### 从已核验candidate正式化

正式mask直接复制旧center candidate，然后只更新**新副本**global metadata为FROZEN/PRIMARY_YUNNAN_EVALUATION_MASK。旧候选原字节另存PROVENANCE/adopted_center_candidate.nc。全部variable的数值、dtype、维度及包括lat/lon的数组逐值未变。未用np.arange生成坐标。

复用保存的真实IMERG坐标，同时只读重读旧审计指定的单个原始IMERG文件，确认lat/lon数组和P0哈希完全一致。无transpose、silent flip或index offset；mask shape=(130,140)、true=3430。候选原有中点cell-bounds数组仅保留来源信息，不参与center主评价判据，也不构成model-input grid或DEM聚合约定冻结。

### 防止静默替换

使用src/frozen_contract.py的verify_frozen(run_path)核验登记哈希、五字段身份、geometry、实际坐标、维度、方向与mask判据。测试已证明：修改自有测试副本中的mask后，核验明确拒绝。任何未来边界/mask版本变化必须有研究者显式新决策并建立新run；不得覆盖本run、静默换文件或改registry后冒充同一版本。哈希登记不等于操作系统只读ACL。

## 保留但不作为主评价或主DEM的资料

- COMPARISON/yunnan_imerg_mask_intersection_candidate.nc：旧文件的SHA256完全一致副本，true=3752，与主mask差322格，角色为boundary sensitivity / engineering comparison，is_primary_evaluation_mask=false。旧candidate未删除、未改动。
- AWS_Skadi：保持独立辅助来源，未拼接到正式SRTM、未删除、未修改。
- SRTM注册见DEM/frozen_primary_root_inventory.csv；以先前完整像元coverage审计为依据，本轮核查237文件size/mtime及已有抽样hash，未重复全库DEM像元处理，未生成DEM派生产品。

## NOT_YET_FROZEN

| 项目 | 状态 |
|---|---|
| model_input_bbox | NOT_YET_FROZEN，未生成正式bbox |
| 省界外weather-system context margin | NOT_YET_FROZEN，未选择宽度 |
| 97–107°E，20–30°N | **CANDIDATE COMMON NUMERICAL OVERLAP**，不是正式model_input_bbox |
| DEM正式聚合/重采样方法 | NOT_YET_FROZEN |
| slope/aspect/relief/curvature参数 | NOT_YET_FROZEN |
| dh/dx、dh/dy正式生产流程 | NOT_YET_FROZEN；仅物理距离原则已冻结 |

## RESEARCHER_DECISION_REQUIRED

未来输入bbox、天气系统context margin、DEM聚合方式、正式地形特征参数及gradient生产流程仍由研究者决定。若需要更换已冻结边界/mask，则另行显式批准新版本。当前获批边界、center mask和SRTM主来源不再列为待批准项。

## 测试、保护与执行边界

- **21 passed / 0 failures / 0 errors / 0 skipped**，真实stdout及JUnit XML位于tests/pytest_final_output.txt、tests/pytest_final.xml。
- 测试覆盖shape、真实IMERG坐标精确一致及dtype、lat ascending、无transpose/flip、3430格、五字段同时身份确认、原始geometry保持、脚本hash、intersection非主角色、未冻结项、静默替换拒绝与旧输入保护。
- 256个登记输入size/mtime全部保持不变；22个完整SHA256检查全部一致。size/mtime verification is not full content hash proof.
- 固定解释器`{PYTHON}`；依赖未安装/升级。
- 单个380398-byte英文staging副本大小/SHA256验证通过并清理；临时测试文件也只使用本轮自有副本。
- 没有正式model-input bbox、DEM resampling、DOTE正式特征、Dataset、normalization、split、B0或其他训练。未更改GFS provenance/vintage和研究时间范围。

本次空间决策更新完成后停止，不自动进入下一Stage。
'''
put('STAGE0_SPATIAL_DECISION_FREEZE_REPORT.md',report)
status={'status':'STAGE0_SPATIAL_DECISION_FREEZE_COMPLETE','engineering_status':'PASS','decision_authority':'EXPLICIT_RESEARCHER_APPROVAL','freeze_id':r['freeze_id'],'boundary_version_frozen':True,'boundary_version':'GADM 4.1 Level1 CHN.30_1','all_five_identity_fields_verified':True,'evaluation_mask_frozen':True,'evaluation_mask_rule':'CENTER_IN_POLYGON','mask_shape':[130,140],'mask_true_cells':3430,'mask_coordinates_exact_real_imerg':True,'mask_lat_ascending':True,'dem_primary_source_frozen':True,'dem_primary_root':r['dem']['primary_root'],'intersection_primary':False,'intersection_retained':True,'model_input_bbox_frozen':False,'context_margin_frozen':False,'dem_aggregation_method_frozen':False,'terrain_parameters_frozen':False,'gradient_production_pipeline_frozen':False,'physical_distance_gradient_principle_frozen':True,'common_overlap_role':'CANDIDATE COMMON NUMERICAL OVERLAP','raw_data_modified':False,'old_runs_modified':False,'dependencies_changed':False,'B0_started':False,'DEM_resampled':False,'formal_DOTE_features_generated':False,'automatic_next_stage':False,'researcher_decision_required_for_remaining_unfrozen_items':True,'tests':stats,'frozen_registry_sha256':sha(OUT/'freeze_registry.json'),'stopped_after_requested_scope':True,'finished_utc':datetime.now(timezone.utc).isoformat()}
outjson('audit_final_status.json',status)
# Convert new inventory/integrity CSV only; no changes to frozen copies or registry.
for name in ['DEM/frozen_primary_root_inventory.csv','logs/input_integrity_after.csv']:
 p=OUT/name;df=pd.read_csv(p,dtype=str,keep_default_na=False);df.to_parquet(p.with_suffix('.parquet'),engine='pyarrow',index=False);pd.testing.assert_frame_equal(df,pd.read_parquet(p.with_suffix('.parquet')))
required=['STAGE0_SPATIAL_DECISION_FREEZE_REPORT.md','freeze_registry.json','docs/DECISION_LOG_STAGE0_SPATIAL_FREEZE_UPDATE.md','docs/RESEARCHER_APPROVAL_RECORD.md','PROVENANCE/generator_script_hashes.json','FROZEN/BOUNDARY/yunnan_gadm41_level1_boundary.geojson','FROZEN/MASK/yunnan_evaluation_mask_center_gadm41_imerg_v1.nc','COMPARISON/yunnan_imerg_mask_intersection_candidate.nc','tests/pytest_final_output.txt','tests/pytest_final.xml','audit_final_status.json']
assert all((OUT/p).is_file() for p in required)
assert not list(CACHE.iterdir())
# pytest's lock is removed at exit; no data-bearing temp file is retained.
tempfiles=[str(p) for p in (OUT/'tests/tmp').rglob('*') if p.is_file()];assert not tempfiles,tempfiles
outjson('logs/completion_checks.json',{'required_outputs':required,'all_exist':True,'frozen_contract':verify_frozen(OUT),'staging_empty':True,'test_temporary_files_remaining':tempfiles,'next_stage_started':False})
rows=[{'relative_path':str(p.relative_to(OUT)),'size_bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ['output_manifest.csv','output_manifest.parquet']]
pd.DataFrame(rows).to_csv(OUT/'output_manifest.csv',index=False,encoding='utf-8-sig');pd.read_csv(OUT/'output_manifest.csv',dtype=str,keep_default_na=False).to_parquet(OUT/'output_manifest.parquet',engine='pyarrow',index=False)
print(json.dumps({'status':status,'manifest_entries':len(rows),'report':str(OUT/'STAGE0_SPATIAL_DECISION_FREEZE_REPORT.md')}))
