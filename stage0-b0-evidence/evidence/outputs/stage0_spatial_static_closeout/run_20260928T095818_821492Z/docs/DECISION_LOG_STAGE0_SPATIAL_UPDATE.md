# Stage-0 spatial update — new run only

## ENGINEERING_EVIDENCE
240个DEM归档逐tile只读检查；SRTM对本轮云南polygon为FULL；284条相关polygon feature均valid。两种IMERG130×140候选mask精确对齐，3430与3752格点，差322。小窗口物理距离gradient与临时VRT路径已执行。

## PROVISIONAL
GADM4.1 local候选及版本声明；SRTM作为独立空间对照；中点cell边界；center/intersection mask；native terrain smoke算法；数值共同覆盖。科学原则“最终评价使用云南省全境行政区mask”已冻结，不在provisional之列。

## NOT_YET_FROZEN
model_input_bbox = NOT_YET_FROZEN；具体边界文件/版本、DEM方法和正式terrain参数未冻结。

## DATA_GAP
SRTM大包络存在3个tile缺口，均不侵入本轮云南或共同候选区域；Skadi是独立root。边界官方下载认证/校验回执及DEM本地完整vertical datum证据不足；不以推测补齐。旧processed mask坐标未与实际IMERG精确一致，旧文件保持不变，本轮新候选锚定真实坐标。

## RESEARCHER_DECISION_REQUIRED
mask boundary semantics = RESEARCHER_DECISION_REQUIRED；context margin = engineering evidence only。待决项见RESEARCHER_DECISIONS_REQUIRED.md。GFS provenance/vintage、研究年份、2025-10、B0 HOLD及所有冻结科学约定未改变。
