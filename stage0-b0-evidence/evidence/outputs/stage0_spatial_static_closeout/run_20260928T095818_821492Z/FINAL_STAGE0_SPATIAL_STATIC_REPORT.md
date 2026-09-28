# Stage-0 spatial/static engineering audit

工程状态 **PASS**，37项测试通过。本轮完成DEM、云南行政区polygon、IMERG mask候选与共同空间覆盖审计；科研版本、边界规则及model-input bbox未冻结。

**保持已冻结科学原则：最终评价必须使用云南省全境行政区mask。** 具体边界文件、来源版本与边界像元判定待研究者选择。

## 1. Engineering status

PASS。全部授权安全工程任务已实际执行。未全库重扫IMERG/GFS/Himawari；复用正式grid证据并仅重读一个旧审计明确指向的IMERG文件坐标。DEM本轮是首次专门静态审计，240个归档逐tile完整读取有效像元。任务执行及测试不等于科学约定批准。

## 2. DEM roots

`F:/云南极端降水数据/raw/SRTM`与`F:/云南极端降水数据/raw/AWS_Skadi`。MULTIPLE_DEM_ROOTS_RESEARCHER_REVIEW，两个root独立处理，未合并。旧processed地形产品只列出存在，未采用或覆盖。

## 3. DEM file count

SRTM237、AWS_Skadi3，共240个`.hgt.zip`，各含一个HGT，无额外sidecar。受限发现范围与所有访问文件在discovery_scope/input_protection_before记录；未扫描整盘或无关dataset。

## 4. DEM format

GDAL SRTMHGT、3601×3601、单band int16、AREA_OR_POINT=Point。归档通过GDAL `/vsizip/`只读访问，未永久解压复制DEM库。[GDAL格式说明](https://gdal.org/en/stable/drivers/raster/srtmhgt.html)说明命名HGT压缩档读取与georeferencing支持。

## 5. CRS

全部raster由SRTMHGT driver解析为EPSG:4326/WGS84，经纬度单位degree；HGT没有嵌入完整CRS头，georeferencing依据格式与member命名。不是从未知CRS猜EPSG。实际affine、axis direction及依据逐tile写入dem_crs_georeferencing_audit.csv。band高程单位m；完整vertical datum在本地头信息中NOT_ESTABLISHED，未自动补写EGM96。

## 6. Raw resolution

每轴1/3600°，约1弧秒；纬度descending，经度ascending。没有flip/resample。Point样点名义tile范围与向外半样点的GDAL pixel support bounds分别记录，不把center/edge混淆；没有用DEM方向覆盖IMERG方向。

## 7. Tile topology

SRTM名义包络94–110E、18–33N，内部缺N18E107、N19E107、N20E108，共约3 degree²。AWS_Skadi仅这3tile，单独不覆盖云南。本轮不将两来源拼成正式产品。

无名义重复footprint，无CRS/resolution mismatch。相邻Point tile共享边缘样点，pixel-support窄重叠不是错误重复；439对SRTM和1对Skadi共享边逐样点一致。已执行两tile临时VRT及4×4逐值读取验证，PASS并清理；没有全域mosaic。

## 8. NoData / valid pixels

SRTM total=3073226637、valid=3073226637、nodata=0、nonfinite=0；Skadi total=38901603、valid=38901603、nodata=0、nonfinite=0。全tile完整读取，没有用bbox或抽样值替代有效像元检验。NoData标记-32768保留；0和负值正常参与valid判定。

SRTM min/max=-468/7439m；Skadi=-94/-18m，均QC_STAT_ONLY。不截负值、删极值、填补、平滑或定义异常阈值。总样点数包含tile共享边缘，不是去重面积或train statistics。

## 9. Yunnan polygon roots

raw/BOUNDARY/GADM41中的CHN level1/2/3归档及processed/boundary中的Yunnan level1/2/3 GeoJSON，共6候选。MULTIPLE_BOUNDARY_CANDIDATES_RESEARCHER_REVIEW；本轮选raw level1中云南feature做工程验证，没有批准正式版本。该feature与旧processed level1逐坐标一致。

## 10. Polygon CRS

源文件显式CRS84，WGS84经纬度顺序longitude/latitude；与DEM EPSG:4326数值比较时明确always_xy。无需实际重投影；测试了带always_xy的正反变换，避免EPSG轴定义引起lon/lat交换。

## 11. Geometry validity

全部6候选中的284条云南相关feature均SOURCE_GEOMETRY_VALID，无empty或文件内duplicate。geometry type、multipart、holes、bounds、native面积和validity reason逐feature记录。native面积单位degree²，没有伪写km²。本次无需修复源几何，未覆盖任何polygon。

## 12. Yunnan identity and source trace

NAME_1=Yunnan、NL_NAME_1含云南、GID_1=CHN.30_1、HASC_1=CN.YN、ISO_1=CN-YN、ENGTYPE_1=Province提供文件自身身份依据；状态ATTRIBUTE_SUPPORTED_YUNNAN，不只依据文件名。

版本GADM4.1由本地archive/member命名及schema声明，[GADM官方版本页](https://gadm.org/data.html)提供版本参照。本地raw archive与processed几何对应、哈希可追溯，但没有找到官方下载receipt/checksum，外部认证仍有边界；不等于研究者已批准正式行政区版本。

## 13. Full Yunnan DEM coverage

**FULL，限定本轮GADM level1云南候选及SRTM root。** Polygon bounds为97.5341–106.1942E、21.1394–29.2511N。真实raster footprint union覆盖polygon，全部样点有效，云南all-touched区域与省界线的invalid像元均0，未发现边界NoData gap。

结论基于footprint与实际valid像元，不仅bbox；不证明地形高程精度或最终行政区版本合法性。Skadi对云南本体为MISSING。SRTM外围3tile缺口不侵入云南或共同候选区。

## 14. Center-based mask candidate

MASK/yunnan_imerg_mask_center_candidate.nc，130×140，true=3430，false=14770。使用严格中心点在polygon内部contains；精确位于边界的中心不包含，本次这类中心数0。仅工程候选。

## 15. Intersection-based mask candidate

MASK/yunnan_imerg_mask_intersection_candidate.nc，130×140，true=3752，false=14448。由实际相邻中心中点及首尾局部间距外推形成闭合cell polygon，与云南polygon相交即包含，触边计入。没有硬编码0.05°；推导cell bounds是明确的候选工程语义，不冒充原始IMERG bounds。

## 16. Candidate difference

intersection比center多322格点，center为其子集。每个差异格点row/col/lat/lon保存在MASK/boundary_difference_cells.csv；候选shape、比例、bbox索引与坐标范围见yunnan_imerg_mask_comparison.csv。未因某种规则格点更多而自动选用。

## 17. Exact IMERG grid alignment

PASS。旧processed mask坐标哈希不等于正式P0审计值，故未采用其坐标；该旧文件保持原样。按旧audit第一条记录读取唯一指定原始IMERG文件（380398 bytes），恢复真实float32坐标，lat/lon哈希与P0完全一致。

正式坐标复用文件MASK/imerg_actual_coordinates.npz；两个候选NetCDF读回均shape=(130,140)、dims=(lat,lon)、lat/lon逐元素与dtype一致、lat ascending保持、无flip/transpose/index offset。没有np.arange重建真实target grid。旧mask不匹配只是本轮确认的精确grid不一致，不据此推断其全部像元用途。

## 18. Multi-source common overlap

**CANDIDATE ONLY：97–107°E、20–30°N**。来源为IMERG/GFS/Himawari已审计坐标中心包络与独立SRTM范围的数值交集。SRTM实际有效像元覆盖该候选。不是model_input_bbox；未生成正式model-input grid。

## 19. Yunnan coverage by each source

IMERG/GFS/Himawari均在已有坐标中心包络意义上包含本轮云南polygon；SRTM额外通过实际footprint/valid全像元检验。Skadi独立root不含云南本体。

坐标包络不等于所有时次所有变量均可用。本轮不重做时变库QC，因此all-time/all-variable common valid coverage=NOT_ESTABLISHED_THIS_STATIC_AUDIT。没有将静态工程结论改称全变量数值完整性。

## 20. Context margins

共同候选相对云南包络的west/east/south/north余量为0.5341°/0.8058°/1.1394°/0.7489°，WGS84近似距离53.83/81.22/126.14/83.01km。各source详细值见context_margins.csv；东西取polygon中纬度、南北取中经度，是包络余量上限，不是复杂省界均匀buffer。

没有选择0.5°/1°/2°或任何科学context宽度；更大的DEM envelope还存在外部tile缺口。

## 21. Terrain smoke test

ENGINEERING_SMOKE_TEST_ONLY：N25E102原生33×33窗口，elevation、dh/dx、dh/dy、slope、aspect、sin/cos路径已执行。以Geod.inv物理米距离构造带符号行列坐标，gradient单位m/m，保持纬度descending。

1089个高程与gradient有限；flat aspect明确NaN；坡度0–72.72081073915831°只是QC统计。已知物理斜率合成测试验证单位与方向。未来DOTE必须在物理距离上计算；本轮没有正式DOTE、全域地形特征或算法冻结。

## 22. Pytest

最终**37 passed，0 failures，0 errors，0 skipped**。覆盖附件20项要求：CRS、NoData、gap/overlap、polygon有效性与身份、真实grid、shape/exact坐标、ascending、transpose、两mask差异、FULL证据门槛、候选/bbox、原始/旧run保护、cache、物理gradient、lon/lat顺序。

首轮1 failed/36 passed已保留tests/pytest_attempt1_failed_*。原因是pandas默认CSV解析将1/3600°文本引入7.77915e-17误差；改为float_precision=round_trip后误差0，未放宽断言、未修改数据。修复记录见logs/test_repair_record.json。NetCDF写入遇到库内NumPy2.5弃用提示，写入与精确读回均通过，不隐藏为数据错误，也未为其升级环境。

## 23. Dependencies

固定Python为`F:\pytorch\Research\.venv\Scripts\python.exe`。新增rasterio1.5.1、shapely2.1.2、pyproj3.8.0及必需affine3.0.1、attrs26.1.0。所有原有包均锁定并保持版本，包括torch/numpy/xarray/pandas/scipy。GeoJSON用标准json读取，无需安装geopandas/fiona。pip check通过，完整安装计划/报告与版本差异记录在logs。

## 24. Raw integrity

实际登记253个输入，size/mtime_ns前后全部一致；其中17个完整SHA256样本全部一致。DEM、boundary、旧审计grid/status、原始及旧派生坐标来源均按登记范围保护；raw及旧run写入操作0。GFS上一轮结论文件也有哈希保护。

**size/mtime verification is not full content hash proof.** 不宣称全库全部字节都做过前后哈希。F/H原始科研数据永久只读，本轮没有操作H原始库。

## 25. Cache

只为两个小NetCDF坐标读取执行英文staging：copy_count=2，cumulative_bytes=392466，max_single_copy=380398，复制大小/SHA256均通过。cleanup_failures=0，remaining_staged_bytes=0。DEM直接虚拟只读，无全库复制；临时VRT也已清理。未删除历史diagnostic cache。

## 26. Researcher decisions required

只保留具体边界文件与来源版本、center/intersection mask规则、模型输入bbox、天气系统context margin、DEM正式聚合方法、正式terrain算法和参数。已冻结的云南全境行政区评价原则保持不变；普通工程问题已处理完毕。

## 27. Stage-0 closeout impact

本轮空间静态工程审计完成，mask工程构造可行，SRTM对候选云南polygon全覆盖。科学spatial closeout仍需研究者批准；stage0_scientific_closeout_ready=false。

B0/Dataset/normalization/split/DOTE/DTFM/MEE/训练继续HOLD；没有正式DEM/model-grid产品、Himawari重采样或GFS插值。GFS provenance仍SUPPORTED_WITH_CAVEATS、整体PARTIALLY_COMPATIBLE、operational vintage NOT_ESTABLISHED；本轮没有修改这些结论、研究年份或删除2025-10。

Stage-0 spatial/static engineering audit complete.
A Yunnan evaluation-mask candidate may have been generated, but no scientific mask convention was frozen automatically.
No model-input bounding box was frozen.
No formal DEM/model-grid product was generated.
No frozen scientific convention was changed automatically.
