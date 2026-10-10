# 云南独立降水参考资料清单

调查日期 2026-10-10；RESEARCHER_DECISION_REQUIRED。只浏览公开产品说明和获取条件，没有登录、下单、发送申请、下载观测文件或读取本地原始资料。访问级别与独立性是两件事；“公开可申请”不等于“已获许可”或“独立真值”。本轮未确认任一站点的 2023/2024 实际完整性，站号、迁站史、QC、分辨率和源链必须以后由提供方元数据证实。

## 1. 地面与雷达优先资料

|ID / 提供方|时间覆盖与时间支撑|空间支撑|获取/许可|独立性及预期限制|
|---|---|---|---|---|
|R1 CMA/国家气象信息中心国家地面站与云南加密自动站|基本观测目录动态更新；2023/2024 分钟/小时档案需询问；日值 V3.0 说明自1951起、滞后3月|站点；云南实际站表、海拔/代表范围未知|基本目录从中国气象数据网获取；日值教育科研实名用户；云南地方服务需单位函、协议和平台审批|优先直接雨量观测；部分国家交换站可能进入 GPCC/IMERG；站点不是0.1°面积平均，仪器分辨率/漏测/迁站影响|
|R2 CMA 雷达共享服务与云南雷达应用单位|公开目录含 radar/QPE 产品；各雷达上线、2023/2024 volume 连续性需查；新增系统不能倒推历史可用|基数据极坐标 beam/gate；QPE 网格/cadence 以实际产品说明为准，本轮未确认|官方共享页面列基数据/图像产品；目录可见不代表云南全部基数据与 QPE 已获批，需实名/定向服务和使用条款|优先未使用待验证站校正的 QPE；山地遮挡、衰减、亮带、Z-R 与地面降水差异；图片 dBZ 不能直接作 mm/h 真值|
|R3 云南省水利厅/水文机构/山洪监测雨量站|2025官方介绍证明平台存在；拟询问2023/2024时段和最小累计间隔，不取得2025数值|雨量站点；平台融合气象/水文/山洪站，站ID及去重未知|与持有单位确认科研申请、费用、共享范围及再分发；公开新闻不是历史API许可|水文独立雨量器可能增强地面验证；平台含气象站，不能按部门不同认定独立；网络建设与运维缺测造成抽样偏差|
|R4 中科院西双版纳森林生态系统国家野外站/CERN|指南有气象/水分长期监测类别；具体降水时间范围与分钟/小时/日频需元数据确认|勐仑站点/站内观测地；不能代表全省地形|注册按指标和时间申请，线下需签字盖章；是否可提供高频2024降水未确认|不同观测链有潜力，但是否提交交换/GPCC未知；局地生态环境、设备高度和林冠代表性需核查|

R1 来源：[CMA 基本共享目录](https://www.cma.gov.cn/zfxxgk/gknr/wjgk/qtwj/202302/P020230224377864419023.pdf)、[日值 V3.0 产品说明](https://m.data.cma.cn/data/detail/dataCode/SURF_CLI_CHN_MUL_DAY_V3.0.html)、[楚雄市气象数据提供流程](https://www.cxs.gov.cn/info/14045/363408.htm)。目录的“每日更新”不等于“一日观测分辨率”；日值不能检验半小时 q32。

R2 来源：[国家气象信息中心雷达共享服务](https://k.data.cma.cn/mekb/?r=radar%2Fdata)及上述基本共享目录，目录包含定量估测降水；本轮没有找到公开证据证明所有云南雷达在研究时间都有可下载的定量档案。因此不写统一250m/6min等未经验证的数值。

云南适用性另由[CMA 2024科研榜单](https://www.cma.gov.cn/kjrh/lmdt/xxfb/202407/P020240704341544390758.pdf)确认存在云南C/S/X多波段资料应用需求；榜单中的预报提升是项目目标，不能当作已实现效果。[师宗双偏振云雷达建设公告](https://www.cma.gov.cn/2011xwzx/2011xqxxw/2011xjctz/202501/t20250102_6771347.html)记载2024-12-29建成，晚于本项目2024三月至十月窗口，不适用该期异常复核；云雷达结构参数也不等同定量地面雨强。故后续必须索取逐部雷达上线与档案元数据。

R3 来源：[云南省水利厅2025年新闻发布会](https://wcb.yn.gov.cn/html/2025/xinwenfabuhui_0710/3061514.html)。其公开说明涉及整合站网与X波段测雨系统；网络规模是当时系统能力，不能当作2024独立站点数量。该页直接打开失败、搜索索引可读，来源可达性限制记录在 source_registry.json。R4 来源：[西双版纳站申请指南](https://bnf.cern.ac.cn/content?id=54395)，指南更新时间2025-04-07；本轮没有填写/发送申请。

## 2. 公开全球资料与辅助交叉检查

|ID / 提供方|时间/空间尺度|访问许可|独立性/适用范围|
|---|---|---|---|
|R5 NOAA NCEI GHCNh / GHCNd|全球站点记录长度不一；GHCNh hourly/synoptic 含不同累计期降水，GHCNd daily；云南站点2023/2024重合待检索元数据|官方地图/搜索与公开下载入口；按具体数据条目引用和使用条件，本站未下载|GHCNh 已替代 ISD；GTS/CMA交换观测可能同站，不是新独立仪器；日累计用于背景核对，非半小时分位数验证|
|R6 NASA/JAXA GPM DPR L2 2ADPR|GPM时期2014起；约5km nadir足迹、轨道瞬时采样，云南过境日期/雨样本量未知|GES DISC公开目录，Earthdata用户账号获取；本轮只查看metadata|主动雷达提供垂直结构交叉检查，但DPR/GMI与IMERG算法源链有联系；不称完全算法独立，不是连续地面真值|
|R7 NSMC FY-3G PMR|公开L1目录2023-10-23起、标称5000M；2024云南轨道重合未知；L2地表雨强产品版本/许可另查|风云数据网需中国气象数据网实名注册审核；尚未取得数据|另一主动传感器有独立性潜力，不能仅凭卫星不同断言与标签无共享校准；L1不是可直接比较的地面mm/h，需受审查L2算法与地杂波处理|
|R8 CMA CLDAS-V2.0 / 区域融合实况降水|官方资源目录列实时/近实时产品；公开介绍区域实况最高1km/10min，但具体降水产品、历史范围待确认|资源详情可访问性不稳定；应询问具体版本和使用协议，未获取|站点/雷达/卫星融合，不可充当完全独立真值；用于支撑敏感性或过程背景；不可把全产品族最高分辨率套给CLDAS或某一降水场|
|R9 Copernicus/ECMWF ERA5|1940至今，hourly，常用CDS大气格网0.25°；非原始观测|CDS目录当前CC-BY，需登录接受条款后获取；未获取|模式再分析、IMERG检索存在ERA5辅助关联；只作环流/风和背景，不作独立降水真值；回溯再分析风不能证明业务实时可获得|

R5 来源：[GHCNh官方说明](https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly)、[GHCNd官方说明](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily)。R6：[DPR规格](https://gpm.nasa.gov/missions/GPM/DPR)、[2ADPR产品入口](https://gpm.nasa.gov/data/directory/2a-dpr-ges-disc)、[Earthdata登录说明](https://urs.earthdata.nasa.gov/documentation)。轨道周期不是某站连续采样周期。

R7 来源：[FY-3G官方产品目录](https://satellite.nsmc.org.cn/DataPortal/cn/data/dataset.html?satelliteCode=FY3G)、[实名注册提示](https://satellite.nsmc.org.cn/)；L1目录覆盖不是L2可用性证明。R8：[CMA资源目录](https://k.data.cma.cn/mekb/?r=site%2Findexdata)、[信息中心实况产品说明](https://k.data.cma.cn/mekb/?id=42617&r=site%2Farticle)。R9：[ERA5 CDS目录](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview)，2026-10-10调查；许可与目录可能更新。

## 3. 独立性分级与获取优先级

建议先询问 R1/R2/R3 的 2024 连续合资格记录和源链；R4 用局地交叉验证补充；R5 是可获得性备选但不得重复计同站；R6/R7作主动传感器支撑；R8/R9仅辅助。该顺序是资料准备建议，不是正式评价目录。只能先申请元数据，不能先看 B1 错误再挑有利站点。

INDEPENDENCE_UNVERIFIED 为全部候选默认状态。未来分类：直接观测且证实未进入标签/订正/模型输入者可标验证独立；已共享仪器/交换资料者标 OBSERVATION_SHARED；不同传感器但共享算法校准者标 ALGORITHM_LINKED；融合/再分析标 AUXILIARY。IMERG Final 使用 GPCC 月尺度地面分析，半小时场受月度比例调整；因此“本站未参与训练”还不足以证明与训练标签独立。[NASA IMERG说明](https://gpm.nasa.gov/data/imerg)

未能公开确认的时间、空间、费用、许可、站号或源链统一写待确认，不填虚构值。未证明独立的参考仍可用于一致性研究，但结果须用“参考一致性”措辞；不得宣称已通过独立物理验证。
