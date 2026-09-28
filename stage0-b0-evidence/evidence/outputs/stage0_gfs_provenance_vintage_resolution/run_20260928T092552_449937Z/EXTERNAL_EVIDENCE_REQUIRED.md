# External evidence still required

已通过官方文档核实产品角色：[https://gdex.ucar.edu/datasets/d084001/](https://gdex.ucar.edu/datasets/d084001/)；AWS bucket 注册：[https://registry.opendata.aws/noaa-gfs-bdp-pds/](https://registry.opendata.aws/noaa-gfs-bdp-pds/)；转换/子集服务能力：[https://gdex.ucar.edu/datasets/d084001/dataaccess/](https://gdex.ucar.edu/datasets/d084001/dataaccess/)。这些是当前文档，不是当年文件的发布或本地转换证明。没有下载科研数据。

| 需核实事项 | 推荐官方来源/标识 | 具体问题与本地不足 |
|---|---|---|
| 历史 operational 首发 | NCEP/NCO GFS pgrb2.0p25 f000/f003/f006；NOAA NODD、NewGFSObject 历史事件 | 2023–2025 对应 endpoint/cycle/lead 的首次完整可获取时间是否留存？本地只有 2026 回溯获取记录。 |
| documented latency | [NCEP GFS 产品页](https://www.nco.ncep.noaa.gov/pmb/products/gfs/) 与年代对应服务变更通知 | 周期不是延迟；是否存在年代/产品适用的发布窗口、异常或 SLA？未核实，不选择 X。 |
| archive/镜像重写语义 | NCAR d084001 DOI 10.5065/D65D8PWK、NOAA AWS GFS archive | 回填、重发、修订、archive date 与 object Last-Modified 各代表什么？本地未保存 headers，不能从归档日期反推首发。 |
| 逐 forecast 内容一致性 | 两端具体 original filename 与版本/校验记录 | 相同 family/token 能否确认相同 cycle/lead 的相同变量内容版本？元数据声明不足以独立证明 payload。 |
| 历史 NCSS 处理 | NCAR THREDDS NCSS / NetCDF-Java 服务版本与请求回执 | 指定 query 是否做了额外重网格、时间/属性转换？当前服务能力页不证明历史执行过程。 |

本地另需恢复 download_gfs.py、AWS/thermo/标准化脚本的确切版本与执行记录、英语/中文根目录迁移记录及内容校验。以上只列需求，不执行下载、联系第三方或科研决策。
