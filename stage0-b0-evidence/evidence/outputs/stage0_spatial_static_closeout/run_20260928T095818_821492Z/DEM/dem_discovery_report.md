# DEM discovery

限定范围：F:/云南极端降水数据/raw/SRTM、raw/AWS_Skadi；根目录一级发现记录于 logs/discovery_scope.json，未扫描整盘或无关 dataset。

MULTIPLE_DEM_ROOTS_RESEARCHER_REVIEW：SRTM 237 个 zip，AWS_Skadi 3 个 zip，共240；所有归档均含一个 HGT，无其他 sidecar。扩展名 .hgt.zip 作为必要压缩格式纳入。processed 中两个 static_topography_0p1deg*.nc 仅作为旧派生文件列出，未采用其高程、未把它们当原始 DEM、未覆盖。

两个 root 独立 inventory/QC，不自动合并。SRTM root 可独立覆盖本轮云南候选，故用其做共同覆盖工程对照；不是最终科研 DEM 版本批准。
