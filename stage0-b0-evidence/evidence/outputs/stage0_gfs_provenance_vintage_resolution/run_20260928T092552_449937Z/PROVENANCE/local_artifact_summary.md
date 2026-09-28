# 本地证据范围与限制
检索 F:/pytorch/Research 与 F:/云南极端降水数据 中相关工程文本，排除原始数据、缓存、无关数据集及大型输出目录；明确复用的 14 个旧审计产物例外。搜索配置见 logs/search_scope.json。

本轮 inventory 共 219 个文件：202 个本地日志/manifest、14 个复用审计文件、3 个按完成报告引用定向读取的旧 GFS processed 索引/配置。初筛每个文件最多 2 MiB，随后完整读取 10 个相关 GFS JSONL manifest（87991 行）与 168 个相关日志（596255 行）；解析错误 0。旧审计是二次证据，不伪装成独立下载证据。

没有在限定检索范围找到获取/转换源代码。日志直接提到 download_gfs.py；具体工作区路径定向读取结果 NOT_FOUND，见 logs/referenced_script_lookup.json；未扫描系统盘。两个脚本调用片段只证明调用名称，不证明代码内容或运行版本。

下载事件表保留 failed、skipped、downloaded、complete。所选 case 的 91 个事件中 60 个带大小，6 个相同、54 个不同、31 个无大小；重复 manifest 行不是独立下载次数。英语历史根目录与当前中文根目录的物理同一性未建立。旧 vintage index 的 8820 行，两分支大小均与现有审计 inventory 相符，但没有内容哈希，不是发布记录；其旧 frozen 字样不是本轮科研批准。

官方网页只作产品/服务文档核查，未获取 GRIB、NetCDF、对象头或新的科研数据。官方说明及限制见 official_documentation_evidence.csv。
