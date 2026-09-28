# STAGE0 SPATIAL DECISION FREEZE REPORT

**执行状态：PASS / RESEARCHER_APPROVED_SPATIAL_CONVENTIONS_FROZEN。**

本轮依据研究者明确批准，将指定边界、中心点评价mask与SRTM主来源纳入当前正式执行规范。Freeze ID：`YunTAPR_STAGE0_SPATIAL_v1_run_20260928T102636_513428Z`。独立新run：`F:\pytorch\Research\outputs\stage0_spatial_decision_update\run_20260928T102636_513428Z`。旧审计结果保留不变，本轮更新不改写此前候选状态的历史记录。

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

正式边界：`FROZEN\BOUNDARY\yunnan_gadm41_level1_boundary.geojson`。
正式主评价mask：`FROZEN\MASK\yunnan_evaluation_mask_center_gadm41_imerg_v1.nc`。
坐标锚：`FROZEN\MASK\imerg_actual_coordinates.npz`。
统一冻结登记：`freeze_registry.json`。

原始archive路径：`F:\云南极端降水数据\raw\BOUNDARY\GADM41\gadm41_CHN_1.json.zip`。
成员文件：`gadm41_CHN_1.json`，feature index（0-based）=35，identifier=CHN.30_1。
原archive副本和成员原字节均保存；正式GeoJSON保留该raw feature全部properties与原始geometry。

| 哈希对象 | SHA256 |
|---|---|
| 原始archive及冻结副本 | `656ea3e576a95f1172503c1f416c8a3b8267bc87e6c090c730a676e96d551478` |
| 原始GeoJSON成员字节 | `0cc2dacb44375c1e36cf32145303b1f403e838658fb44de944af94df910deacc` |
| 正式boundary文件 | `263216aac09e7c4548396b5ff91c43a37962b4847db8ad3f9784aac74f60675f` |
| 原始geometry规范JSON | `c721d7125d484d45d1c1fbc1b902167533c635077e739777163b7178c2e92d5c` |
| normalize后2D little-endian WKB（辅助） | `9a0ba6f0388d1cc459b691db5ebc4d973b6a70d5a894590025fa69c714b74f93` |
| 获批center候选原文件 | `48697c58367adf497e502c139549e6e6622026dceea8de3eaaef876723a34d78` |
| 正式主评价mask文件 | `9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef` |
| latitude coordinate hash | `5973fd3c0e1ab758157d30c240a4e33153a86a6228741958e203116139f4df3a` |
| longitude coordinate hash | `ffc033c7d89b2750c907a61844ea599d2e0bd3af26c1c77aeda99f0b4a0fd7a2` |
| freeze_registry.json | `04077f6d33f7535bcff28d426de4c1970da6c86255c32f16ec043fe2c12779df` |

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
- 固定解释器`F:\pytorch\Research\.venv\Scripts\python.exe`；依赖未安装/升级。
- 单个380398-byte英文staging副本大小/SHA256验证通过并清理；临时测试文件也只使用本轮自有副本。
- 没有正式model-input bbox、DEM resampling、DOTE正式特征、Dataset、normalization、split、B0或其他训练。未更改GFS provenance/vintage和研究时间范围。

本次空间决策更新完成后停止，不自动进入下一Stage。
