# Stage-0 spatial/static engineering audit

固定解释器 `F:\pytorch\Research\.venv\Scripts\python.exe`。本轮输出 `F:\pytorch\Research\outputs\stage0_spatial_static_closeout\run_20260928T095818_821492Z`。原始F/H数据与旧run只读；仅新run与本轮英文cache可写。

执行顺序：prepare.py → audit_dem.py（约98秒全DEM像元QC）→ build_masks.py → cross_source.py → reports_and_integrity.py → scoped pytest → final_report.py。src脚本用于复现方法，重跑必须先创建独立新run/config；不得覆盖本轮历史结果。

最终评价使用云南省全境行政区mask的原则已冻结。两个mask只是边界规则工程候选，cell bounds由真实坐标中点推导；没有批准来源版本或model-input bbox。README/报告按本任务明确要求为Markdown；未生成未经请求的图表。

依赖最小新增rasterio/shapely/pyproj及affine/attrs，原有包版本不变。所有表CSV+pyarrow Parquet精确字符串回读；真实mask/坐标保留NetCDF/NPZ数值类型。不存在全域正式DEM、resampling、训练特征或Dataset。

英文staging只用于两个小NetCDF坐标读取，每次一文件、大小/SHA256校验、结束删除自有副本；DEM zip通过GDAL虚拟只读访问，无永久复制，GDAL_PAM_ENABLED=NO阻止原目录sidecar写入。临时二tileVRT已清理。保护清单与范围见logs/integrity_summary.json。

size/mtime verification is not full content hash proof.
