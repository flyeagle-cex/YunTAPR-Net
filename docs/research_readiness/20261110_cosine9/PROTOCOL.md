# SCHEDULE9 单模型执行协议

2026-11-10，北京时间。状态为 PROPOSED，准确新批准尚未取得。

## 科学干预

检验在同一九轮端点前完成余弦衰减是否改善模型。唯一数值改动为 horizon 从50轮、24,000更新改为9轮、4,320更新。保留480更新预热、峰值1e-4、下限1e-6，在第4,320次优化器更新之前使用下限。原调度在此时为9.363027585410777e-5。

B7 concat、E0、均匀分位节点、lambda_q=1、Seed2029、原始全新初始化、AdamW参数、BF16上下文、输入/数据/mask、每轮顺序及固定E9 LAST均继承。候选不能与UQ/E2、新模块或恢复组合。原50轮默认调用原函数，已有执行入口保留。

## 保存对照继承

复用原执行 f43b4225fef462a31035d59a06b85f31e5b257dc 中已完成并经Harness终态复核的 CONTROL_E0。准确本地位置只保存在忽略目录的 PRIVATE_PREPARATION.json。

- completion、E9 report/tail/receipt、initial及orders共六份JSON与既有RESULTS文件身份逐项匹配。
- 原始B7完整状态摘要为 `ab749c88283399a8fe839e872b7dfdc64904aa80bd4d1bc560c399dbeb9a6326`。
- 九轮orders文件SHA256为 `193fcbc6eab5fa3b29b02ecc3419ab7a01b45a143f08f0a7464fbcc1f4067502`，候选在真实构造初态与顺序后再次核对。
- 对照E9权重SHA256继承前轮实际核验值 `a3f9208aa4e25e786c6797e658cc5fda4da9a29a05c87a693aa6a3fdc571565f`。本轮只核尺寸及保存收据，未重新读取权重载荷。
- Python二进制和版本、Torch、CUDA build及NumPy匹配。GPU名称及总显存另行绑定。历史完整驱动/cuDNN指纹缺失，比较保留该环境限定。
- 原模型、数据、损失及评价代码SHA保持。engine、dynamic dispatcher、paired-summary路径及独立launcher四处差异只服务本次调度和继承接线，明确列入差异复核。

训练仅2023 Train的959场景，逐轮评价仅2024 Development的963场景、3,303,090有效/407,820有雨像元时次。717个R>20像元时次的定义继承，独立天气事件 NOT_IDENTIFIED。

## 固定评价

沿用既有七项未加权指标和实现。两项强雨目标为R>20的log1p条件Pinball与物理雨强Pinball。两项均需改善。全湿log1p/物理Pinball、Brier、发生AP和发生AUROC作为五项保护指标，均不得退化。物理评分仍归一化除以20 mm/h，科学容限0，绝对舍入容差1e-10。q32覆盖仅辅助诊断。

配对统计直接读取保存对照及新候选的固定E9摘要。判据、端点及指标方向在结果产生前固定。单Seed和重复使用Development的探索性局限保留，科学验收 NOT_VERIFIED。

## 唯一新增额度

| 项目 | 上限 |
| --- | --- |
| 模型 | B7/E0/2029，COSINE9_V1，1个 |
| 更新 | 4,320 |
| 气象源字节 | 477,571,641,012 |
| 静态源字节 | 312,828，1次 |
| 合计源字节/打开 | 477,571,953,840 / 142,813 |
| 时间 | 单模型和整包均21,600秒 |
| 存储 | 初始和模型启动各至少24GiB可用 |
| 重放/额外重试/检查点加载 | 0 / 0 / 0 |

RAM、GPU和系统可用commit准入沿用既有执行器，启动前再次核对。RAM最低8GiB、GPU可用最低5GiB、系统commit可用最低2GiB，无独立硬RSS上限。旧引擎的配对ledger内部总保护上限8640属于遗留技术常量，本包单模型上限由任务、逐模型4320限制和准确预算共同约束为4320，不增加授权。

正式输出为新的本地忽略命名空间 `cosine9_seed2029_execution_v1`。外部研究者批准必须绑定完整新commit、提案规范摘要、tasks、scientific_choices、准确预算及输出根。原UQ/E2批准已消费。缺少批准或目标已存在时入口拒绝。冻结源卷及H盘根目录在单次调度claim之前检查，执行前再检查，均只查询目录存在性。

## 必要检查与审核

48项CPU合成与回归通过，细目见VERIFICATION。三份测试模块包括21项SCHEDULE9、8项显式损失入口和19项UQ回归，未调用真实优化器step或科研数据。

代理只读差异复核发现H盘检查晚于单次调度claim的问题，现已前移并由合成测试验证。该代理复核单独登记。本轮Harness桌面工具初始化报 `failed to write kernel assets ... os error 3`，新Harness差异审核尚未取得。旧UQ对照的Harness终态审核证据可以继承其既定范围。

当前工程准备 PASS_WITH_LIMITATIONS，实验 NOT_STARTED，科学 NOT_VERIFIED，研究者掌握 NOT_ASSESSED。是否改善须由真实新结果判断。
