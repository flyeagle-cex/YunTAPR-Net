import json,sys,importlib.metadata as metadata
import numpy as np,pandas as pd
from pathlib import Path
from config import *
from common import *
sys.stdout.reconfigure(encoding='utf8')
d=readj('DEM/dem_audit_summary.json');m=readj('MASK/mask_engineering_result.json');s=readj('logs/discovery_scope.json');b=readj('MASK/polygon_selection_evidence.json');c=readj('CROSS_SOURCE/common_overlap_candidate.json');f=pd.read_csv(OUT/'MASK/yunnan_polygon_features.csv');e=pd.read_csv(OUT/'DEM/dem_shared_edge_comparison.csv')
md('DEM/dem_discovery_report.md',f'''# DEM discovery

限定范围：F:/云南极端降水数据/raw/SRTM、raw/AWS_Skadi；根目录一级发现记录于 logs/discovery_scope.json，未扫描整盘或无关 dataset。

MULTIPLE_DEM_ROOTS_RESEARCHER_REVIEW：SRTM 237 个 zip，AWS_Skadi 3 个 zip，共240；所有归档均含一个 HGT，无其他 sidecar。扩展名 .hgt.zip 作为必要压缩格式纳入。processed 中两个 static_topography_0p1deg*.nc 仅作为旧派生文件列出，未采用其高程、未把它们当原始 DEM、未覆盖。

两个 root 独立 inventory/QC，不自动合并。SRTM root 可独立覆盖本轮云南候选，故用其做共同覆盖工程对照；不是最终科研 DEM 版本批准。''')
md('DEM/dem_tile_topology_report.md',f'''# DEM tile topology

每 root 的 footprint、分辨率、CRS、shape、nodata 与 gap 分别列在 dem_inventory.csv、dem_tile_coverage.csv 和 dem_audit_summary.json。所有读取结果为 SRTMHGT、3601×3601、1 band int16、1/3600°、EPSG:4326、nodata=-32768，无 CRS/分辨率不一致。

SRTM 名义中心 footprint 包络为94–110E、18–33N；该包络内缺3个1° tile：N18E107、N19E107、N20E108；缺口总面积约3 degree²，不将整个bbox误报为有效覆盖。AWS_Skadi只有这3个独立tile，不能单独覆盖云南。未合并两root。

HGT为 Point 样点，邻tile复制一行/列边界样点。GDAL pixel-support bounds向外伸半样点，与名义中心 footprint不同。名义tile无面积重叠、无duplicate footprint；像元support存在窄重叠，属于共享边缘表达，不是自动重复数据。439对SRTM邻接边、1对Skadi邻接边逐样点完全一致，unequal=0。

对本轮GADM云南polygon：SRTM FULL，Skadi MISSING。候选共同坐标包络97–107E、20–30N内SRTM实际footprint和有效像元均完整；更大的root包络不能整体宣称context-ready。任何科学context宽度仍待决定。

[GDAL HGT格式说明](https://gdal.org/en/stable/drivers/raster/srtmhgt.html)解释命名HGT压缩档的读取与georeferencing支持；[geotransform说明](https://gdal.org/en/stable/tutorials/geotransforms_tut.html)区分像元corner与center。''')
md('DEM/dem_mosaic_feasibility.md','''# Mosaic feasibility: PASS

已真实构造一个临时VRT，包含SRTM同root相邻N25E102/N25E103两个tile，保留原生1弧秒、共享边缘offset=3600；通过4×4窗口与原tile逐值相等检查。仅VRT metadata，没有生成全域栅格；临时文件已清理，见 mosaic_feasibility_result.json。

该测试未跨root合并，未选定科学seam处理规则，没有正式mosaic或resampled/model-grid DEM。全域正式处理前仍需研究者确定root、边缘重复样点处理和聚合语义。''')
md('DEM/yunnan_dem_coverage_report.md',f'''# Yunnan DEM coverage

SRTM状态：**FULL（针对本轮工程验证的GADM level-1云南polygon）**。省界bounds为97.5341–106.1942E、21.1394–29.2511N。

判据不是bbox包含：SRTM全部237个真实raster footprint的union覆盖polygon，逐tile完整读取3073226637个样点，valid同数，NoData=0、nonfinite=0；all-touched云南区域与省界线像元中invalid均为0。因此省界附近未检测到NoData gap。原生Point采样的像元support用于此工程覆盖检验，不表示高程精度/地形细节完整性已获科学认证。

AWS_Skadi状态：MISSING（对云南本体）。3tile位于外围，不能单独作为云南DEM。SRTM包络中缺少的3tile均不侵入本轮云南polygon或97–107E、20–30N共同候选区域；没有自动用Skadi填补。

所有统计QC_STAT_ONLY。SRTM min=-468m/max=7439m；Skadi min=-94m/max=-18m。负值保留，不截断、不删除、不定义异常阈值。tile总像元计数包含共享边缘重复样点，不是去重地表面积。

最终边界文件版本仍待研究者批准；最终评价使用云南省全境行政区mask这一原则不变。''')
md('DEM/dem_future_processing_feasibility.md','''# Future processing feasibility — no formal resampling

raw DEM为1弧秒Point样点；IMERG真实target约0.1°、130×140；已审计Himawari网格约0.02°、501×501。分辨率差异已明确，但未来model-input grid未冻结，不能因此生成正式网格或正式DEM。

未来可比较average elevation、median、bilinear、area-weighted、min/max及terrain-feature-before-aggregation；本轮不选择。平均/median代表不同区域摘要，bilinear描述点值插值，min/max是极值；area-weighted需要真实cell面积与边界规则；先派生再聚合与先聚合再派生通常不同。Point DEM转cell support的语义、空值权重、海陆/边界与跨root处理需明确后再实现。

DOTE未来所需dh/dx、dh/dy必须以物理距离（米）为水平坐标，不能直接对经纬度索引求gradient。当前GDAL band units=m；本地HGT无完整垂直datum头信息，vertical datum仍NOT_ESTABLISHED_FROM_LOCAL_HEADER；须按选定来源的可靠产品metadata核实，不能从文件名补造。没有正式重采样、特征算法或DOTE。''')
md('DEM/terrain_feature_smoke_test_report.md','''# ENGINEERING_SMOKE_TEST_ONLY

实际读取N25E102的33×33原生窗口，保留纬度descending，不重采样。以WGS84椭球Geod.inv计算相邻点的物理距离，再构造带方向的行/列距离轴，计算dh/dx、dh/dy（m/m）。坡度采用atan(hypot)转度；aspect暂以顺时针自北的下坡方位表示，平坦处NaN，保留sin/cos。临时工程约定仅用于验证代码与单位，不是正式算法批准。

1089个高程和gradient结果有限；坡度0–72.72081073915831°仅QC_STAT_ONLY，无阈值判定或截断。记录于terrain_smoke_result.json及小型terrain_smoke_arrays.npz，未构造全域特征、训练数据、normalization或正式DOTE。pytest另用已知物理斜率验证量纲和纬度降序时的符号。
''')
md('MASK/yunnan_boundary_discovery_report.md',f'''# Boundary discovery

6个候选：raw/BOUNDARY/GADM41下全国level1/2/3三个GeoJSON zip；processed/boundary下云南level1/2/3三个GeoJSON。PROJECT限定扩展名搜索无额外命中；未扫描系统盘。

MULTIPLE_BOUNDARY_CANDIDATES_RESEARCHER_REVIEW。工程验证选择raw gadm41_CHN_1.json.zip中属性明确的云南省level-1 feature，不凭文件名认定；没有选择最终科研版本。processed level1几何与raw选定feature逐坐标完全一致：{b['raw_vs_processed_level1_exact_geometry']}。

本地命名声明GADM4.1，属性含GID/HASC/ISO与行政层级；[GADM官方版本说明](https://gadm.org/data.html)可核对版本标识。本地未找到下载receipt/官方checksum，故来源可追溯到本地raw归档及哈希，外部来源认证仍有限。不能声称它就是获批准的官方行政区界版本。''')
md('MASK/yunnan_polygon_audit.md',f'''# Yunnan polygon audit

6个候选共选出284条云南相关feature（1、16、125及对应processed副本）；全部SOURCE_GEOMETRY_VALID，无empty、无文件内duplicate geometry。具体geometry type、multipart、holes、native面积、bounds、validity reason和完整行政属性见yunnan_polygon_features.csv。native面积是degree²，不能标成km²。

原始文件明确CRS84（WGS84经纬度，x=longitude/y=latitude），与raster EPSG:4326进行工程转换时使用always_xy=True；本次省界无需重投影。没有使用make_valid/buffer(0)替代源几何，本次全部源几何已valid。代码对潜在invalid只允许内存修复试验。

身份由NAME_1=Yunnan、NL_NAME_1含云南、GID_1=CHN.30_1、HASC_1=CN.YN、ISO_1=CN-YN、ENGTYPE_1=Province共同支持，状态ATTRIBUTE_SUPPORTED_YUNNAN。source/版本身份与“最终科研选用”分开记录。

**已冻结原则：最终评价必须使用云南省全境行政区mask。** 具体文件、版本、center/intersection边界语义未冻结。''')
md('MASK/mask_grid_alignment_report.md',f'''# Exact IMERG mask alignment: PASS

未合成target坐标。旧processed mask的lat/lon哈希与正式P0 grid audit不同，因此没有复用其坐标；只读读取P0第一行明确对应的一个原始IMERG文件，恢复float32 lat/lon后两个哈希均完全匹配正式审计。整个IMERG库未重扫。

坐标副本imerg_actual_coordinates.npz及来源证据imerg_coordinate_reuse.json保留真实值。输出两种NetCDF mask的维度严格为(lat,lon)=(130,140)，逐元素lat/lon exact match，latitude ascending保留，无flip/transpose/index offset。DEM/GFS descending不影响目标坐标。

center候选为严格内部contains，精确位于polygon boundary的中心排除；本次恰在边界的中心数0。intersection候选为闭合cell polygon相交，包括触边。cell边界从真实相邻中心中点和首尾局部间距外推构造，不硬编码0.05°偏移；这也是候选工程几何语义，不宣称原IMERG文件提供过这些bounds。

center=3430，intersection=3752，difference=322；差异格点逐row/col/lat/lon保存，center为intersection子集。两者均候选，没有自行批准最终规则。''')
md('CROSS_SOURCE/SPATIAL_COVERAGE_CLOSEOUT.md','''# Spatial coverage closeout — CANDIDATE ONLY

复用正式IMERG/GFS/Himawari grid审计，加入独立SRTM footprint和全像元valid QC及云南polygon。详细lat/lon/resolution/orientation/evidence_source见spatial_coverage_closeout.csv。

numerical common overlap candidate：97–107°E、20–30°N。这是各source坐标中心包络的保守数值交集，SRTM有效像元也覆盖该区域，云南polygon处于其中。AWS_Skadi单独列出，不通过悄悄合并扩展覆盖。

这不是model_input_bbox。IMERG、GFS、Himawari的polygon inclusion是坐标空间包络结论；没有本轮逐时逐变量复核所有有效像元，所以all-time/all-variable common validity仍NOT_ESTABLISHED。本轮static检查不能替代原数据QC、未来regridding或科学外部验证定义。

云南最终评价行政区mask原则保持冻结；共同候选包络仅用于说明可能的输入上下文余量。''')
md('CROSS_SOURCE/yunnan_context_margin_report.md','''# Context margins — engineering evidence only

各来源与共同候选的西/东/南/北余量见context_margins.csv。距离以云南polygon包络到source数值包络edge计算，是最大包络余量，不能跳过footprint holes或时变NoData。负数表示对应方向不足。

共同候选的 west/east/south/north = 0.5341° / 0.8058° / 1.1394° / 0.7489°。以polygon中纬度计算东西方向、以中经度计算南北方向的WGS84测地近似距离约53.83 / 81.22 / 126.14 / 83.01 km。不是沿复杂省界处处等宽的buffer，也不是天气系统所需context的科学估计。

不选择0.5°/1°/2°或其他margin，不冻结bbox。对于SRTM大包络仍有外部3tile缺口，不能直接把所有包络余量认作无缝context。''')
md('RESEARCHER_DECISIONS_REQUIRED.md','''# Researcher decisions required

已冻结且不变：最终评价必须使用云南省全境行政区mask。

1. 哪个行政区边界文件/来源版本作为正式版本，包括本轮GADM4.1候选是否可采用。
2. 最终center或intersection边界像元规则及触边处理。
3. 模型输入bbox。
4. 省界外围天气系统context margin。
5. DEM正式聚合方法与来源组合口径。
6. 正式terrain feature算法、物理坐标处理、尺度及参数。

本轮未把普通读取、修复依赖或测试问题交给研究者决定。''')
md('docs/DECISION_LOG_STAGE0_SPATIAL_UPDATE.md','''# Stage-0 spatial update — new run only

## ENGINEERING_EVIDENCE
240个DEM归档逐tile只读检查；SRTM对本轮云南polygon为FULL；284条相关polygon feature均valid。两种IMERG130×140候选mask精确对齐，3430与3752格点，差322。小窗口物理距离gradient与临时VRT路径已执行。

## PROVISIONAL
GADM4.1 local候选及版本声明；SRTM作为独立空间对照；中点cell边界；center/intersection mask；native terrain smoke算法；数值共同覆盖。科学原则“最终评价使用云南省全境行政区mask”已冻结，不在provisional之列。

## NOT_YET_FROZEN
model_input_bbox = NOT_YET_FROZEN；具体边界文件/版本、DEM方法和正式terrain参数未冻结。

## DATA_GAP
SRTM大包络存在3个tile缺口，均不侵入本轮云南或共同候选区域；Skadi是独立root。边界官方下载认证/校验回执及DEM本地完整vertical datum证据不足；不以推测补齐。旧processed mask坐标未与实际IMERG精确一致，旧文件保持不变，本轮新候选锚定真实坐标。

## RESEARCHER_DECISION_REQUIRED
mask boundary semantics = RESEARCHER_DECISION_REQUIRED；context margin = engineering evidence only。待决项见RESEARCHER_DECISIONS_REQUIRED.md。GFS provenance/vintage、研究年份、2025-10、B0 HOLD及所有冻结科学约定未改变。''')
md('README.md',f'''# Stage-0 spatial/static engineering audit

固定解释器 `{PYTHON}`。本轮输出 `{OUT}`。原始F/H数据与旧run只读；仅新run与本轮英文cache可写。

执行顺序：prepare.py → audit_dem.py（约98秒全DEM像元QC）→ build_masks.py → cross_source.py → reports_and_integrity.py → scoped pytest → final_report.py。src脚本用于复现方法，重跑必须先创建独立新run/config；不得覆盖本轮历史结果。

最终评价使用云南省全境行政区mask的原则已冻结。两个mask只是边界规则工程候选，cell bounds由真实坐标中点推导；没有批准来源版本或model-input bbox。README/报告按本任务明确要求为Markdown；未生成未经请求的图表。

依赖最小新增rasterio/shapely/pyproj及affine/attrs，原有包版本不变。所有表CSV+pyarrow Parquet精确字符串回读；真实mask/坐标保留NetCDF/NPZ数值类型。不存在全域正式DEM、resampling、训练特征或Dataset。

英文staging只用于两个小NetCDF坐标读取，每次一文件、大小/SHA256校验、结束删除自有副本；DEM zip通过GDAL虚拟只读访问，无永久复制，GDAL_PAM_ENABLED=NO阻止原目录sidecar写入。临时二tileVRT已清理。保护清单与范围见logs/integrity_summary.json。

size/mtime verification is not full content hash proof.
''')
# Verify actual protected inputs after all source reads; a sampled full SHA256 subset only.
records=readj('logs/input_protection_before.json');integrity=[]
for path,r in records.items():
 p=Path(path);stat=p.stat();h=hashfile(p) if r['sha256'] is not None else None
 integrity.append(dict(path=path,size_before=r['size'],size_after=stat.st_size,mtime_ns_before=r['mtime_ns'],mtime_ns_after=stat.st_mtime_ns,size_unchanged=stat.st_size==r['size'],mtime_unchanged=stat.st_mtime_ns==r['mtime_ns'],sha256_before=r['sha256'],sha256_after=h,sha256_status='PASS' if h is not None and h==r['sha256'] else 'NOT_SAMPLED' if h is None else 'FAIL'))
csv('logs/input_integrity_after.csv',integrity)
staging=[json.loads(x) for x in (OUT/'logs/staging_io.jsonl').read_text().splitlines()]
cache=dict(copy_count=len(staging),cumulative_bytes=sum(r['bytes'] for r in staging),max_single_copy=max(r['bytes'] for r in staging),cleanup_failures=sum(not r['cleanup_success'] for r in staging),remaining_staged_bytes=sum(p.stat().st_size for p in CACHE.iterdir() if p.is_file()),remaining_files=[p.name for p in CACHE.iterdir()],all_copy_hash_verified=all(r['sha256_verified'] for r in staging),temporary_vrt_cleaned=readj('DEM/mosaic_feasibility_result.json')['temporary_cleaned'])
packages={x.metadata['Name']:x.version for x in metadata.distributions()};before=readj('logs/environment_before.json')['packages'];unchanged=all(packages.get(k)==v for k,v in before.items())
summary=dict(input_files_checked=len(integrity),size_mtime_all_unchanged=all(x['size_unchanged'] and x['mtime_unchanged'] for x in integrity),sha256_sampled=sum(x['sha256_status']!='NOT_SAMPLED' for x in integrity),sha256_sampled_all_pass=all(x['sha256_status']!='FAIL' for x in integrity),raw_write_operations=0,old_run_write_operations=0,existing_dependencies_unchanged=unchanged,statement='size/mtime verification is not full content hash proof.',cache=cache)
writej('logs/integrity_summary.json',summary);writej('logs/environment_after.json',{'python':sys.executable,'packages':packages});writej('logs/cache_summary.json',cache)
assert summary['size_mtime_all_unchanged'] and summary['sha256_sampled_all_pass'] and unchanged and cache['remaining_staged_bytes']==cache['cleanup_failures']==0
par=[]
for p in sorted(OUT.rglob('*.csv')):
 df=pd.read_csv(p,dtype=str,keep_default_na=False);q=p.with_suffix('.parquet');df.to_parquet(q,engine='pyarrow',index=False);pd.testing.assert_frame_equal(df,pd.read_parquet(q));par.append({'csv':str(p.relative_to(OUT)),'rows':len(df),'status':'PASS','schema':'CSV text exactly preserved; arrays in NC/NPZ retain numeric types'})
csv('logs/parquet_validation.csv',par);writej('logs/report_pretest_status.json',{'reports_generated':True,'pytest_status':'PENDING_ACTUAL_RUN','parquet_tables':len(par)})
print(json.dumps({'integrity':summary,'parquet_tables':len(par),'reports':'written, pytest pending'}))
