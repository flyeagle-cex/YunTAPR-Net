# Formal B0 architecture requirements

要求范围：single B13、single time，U-Net / GPROF-IR-style baseline，输出与冻结 IMERG 目标坐标显式对齐。输入不包含 GFS、GFS_thermo、GFS vintage、DEM terrain、DOTE、DTFM、MEE 或 ERA5 Teacher；不能把这些后续阶段模块当作 B0 必需入口。

正式层数、通道宽度、下采样倍率、padding、native-to-target 对齐/缺测传播、输出支持范围均 NOT_YET_FROZEN。旧 smoke small U-Net 仅证明工程链可运行，单确定性输出不构成正式 B0 deterministic regression 的批准。

需要研究者决定：第一版 B0 是否含概率头；若含，采用哪类概率表示（例如待评估的分位数或显式概率分布）；若先做确定性对照，也须明确其仅为经批准的对照角色以及与总体概率目标的关系。本轮无默认选项。输出非负性/无雨表示、极端阈值、概率一致性、loss、valid-mask reduction、评价与模型选择指标、随机种子/重复次数和校准协议，均需与 Train/Val 设计共同批准。

概率/确定性选项不是本轮性能推荐，也未下载源码、调用外部模型或训练。GPROF-IR-style 仅描述 baseline 家族，不声称已复现任何论文的全部配置。最后输出要对齐目标 lat/lon；裁剪候选不得改变正式云南 mask 或将 invalid/padding 计入评价。

B0 工程 smoke 保持 PASS。正式 architecture/loss/output 冻结状态仍 false。本轮没有重复 Dataset、DataLoader、forward/backward、optimizer、checkpoint 或 inference 验证。
