# YunTAPR-Net Quantile Head v2（分位数输出头第二版）科学决策包

本轮仅完成科研候选的工程实现和数值核验。quantile（分位数：概率分布中某个累计概率位置对应的预测值）v2 尚未获正式科学接受，也没有正式训练授权。

术语：qlog（对数域条件分位数，单位为 log1p(mm/h)）；FP32/FP64（32/64 位浮点格式）；BF16（bfloat16 混合精度格式）；conditional quantiles（以 R>0.1 mm/h 为条件的分位数）；provenance（来源追踪：把结果绑定到产生它的代码、配置与数据身份）。这些名称在下文按此含义使用。

Baseline（工程起点提交）`26fb03894d8fc4099019279a3025ac7cdb541ec9`；独立 run（证据运行目录）`run_20261006T145404_426214Z`。研究者原任务、两项补充确认及 SHA256（字节内容指纹）见本目录 `authority.json` 与原文副本。

## 1. v1 failure mechanism（旧版失败机制）

旧头将 32 个正增量直接累计，`q32=z0+Σ(softplus(a_i)+epsilon_mono)`。未参与 core loss（正式核心损失）的 physical materialization（生成真实物理单位结果）仍在 forward（前向传播）中强制执行，因 `expm1(qlog)` overflow（超过浮点表示范围）阻断优化。

已保存 mask-partitioned replay（按云南评价区域分区的冻结轨迹重放）中：8,625 次成功诊断更新全部零容差一致，第 8,626 次 forward 复现原失败。Yunnan evaluation mask（云南行政区主评价掩膜）内最大 qlog 为 226.39241802550987，外为 721.2174966216189。只有外区越过 FP64（64 位浮点）边界 709.782712893384；这不是“所有高尾值仅在省外”，也不是未来保证。旧证据保持不可变。

## 2. A：training-path decoupling（训练路径解耦）

现有 `L_occ+L_qr` 只读取 rain_logit（降雨发生的原始分数）和 log-domain quantiles（对数域分位数：log1p 降水空间中的预测值）。因此训练无需构造物理分位数或删截均值代理。A 是删除未参与目标的物理生成；它没有修改损失、梯度裁剪或优化器。

兼容 v1 的全新合成夹具分别在 CPU（中央处理器）的 FP32 和 CUDA（GPU 计算后端）的 BF16 主干前向下验证 batch（一次计算的样本批次）2、singleton（单样本尾批次）1。qlog、loss（损失）、裁剪前后 gradient（梯度）、optimizer update（优化器更新）、更新后模型状态和 RNG（随机数状态）逐项零容差一致。每条路径只执行 2 个夹具更新，共 8 个工程夹具更新，新增正式更新为 0。夹具不读取历史训练权重。首轮因 CPU DNNL（处理器张量计算后端）不支持 BF16 backward 而停止的证据保留；本轮不声称该 CPU 支持完整 BF16 训练。

## 3. C：normalized monotonic parameterization（归一化单调参数化）

v2 将最大条件对数分位数由独立 span（总跨度）决定，再用归一化正权重确定相对位置。它消除了旧头“32 个独立无界增量共同决定总跨度”的结构；**S 仍无界，v2 不保证永远没有物理溢出**。这属于模型结构与梯度几何改变，不等于单纯工程修复。

## 4. 完整数学定义与实数证明

保持 occurrence（降雨发生事件）`p=P(R>0.1 mm/h)`，条件事件为 `R>0.1`，32 个 `tau_i=(i-0.5)/32`，`z0=log1p(0.1)`。

$$w_i=softplus(a_i)+epsilon_w,\quad W=\sum_{j=1}^{32}w_j,\quad c_i=\frac{\sum_{j=1}^i w_j}{W}$$
$$S=softplus(s)+epsilon_{span},\quad q_i=z_0+Sc_i,\quad q_{32}=z_0+S.$$

对所有有限**实数** raw outputs（原始模型输出）及正 epsilon，有 `w_i>0`、`W>0`、`S>0`，因此 `0<c1<...<c32=1`，`q1>z0`，且 `q_i-q_(i-1)=S*w_i/W>0`。

工程上使用同一 FP64 prefix sum（前缀累计和）的末项作 W，使可表示情况下 `c32=1` 精确成立；不对结果做排序或修复。所有有限 raw 的实数证明**不等于**任意有限浮点输入均可表示严格不同的 q。FP64 raw=1e20 的反例会舍入出相等值，严格保护报错；纯 FP32（32 位浮点）在指定 ±1e4 范围内亦存在反例。研究者已批准这一区分。

## 5. Tensor shapes（张量维度）与 API（接口）

|对象|维度与语义|
|---|---|
|B0-Matched-v2 输入|`[B,1,501,501]`，最近一帧 B13|
|B1-v2 输入|`[B,6,501,501]`，最旧至最新，offset（相对分析时刻的偏移）为 60/50/40/30/20/10 分钟|
|native features（原生网格特征）|`[B,48,501,501]`|
|SP04 projected features（沿用冻结空间映射的目标格点特征）|`[B,48,100,100]`|
|v2 raw head|`[B,33,100,100]`，通道 0–31 为 allocation logits（分配权重原始分数），通道 32 为 span logit（总跨度原始分数）|
|rain_logit / rain_prob（发生概率）|`[B,1,100,100]`|
|conditional_quantiles_log（条件对数分位数）|`[B,32,100,100]`，FP64|

`LogDomainOutput`（对数域输出）只含核心输出与原网格/有效性元数据，没有隐式物理属性。`PhysicalQuantileOutput`（显式物理分位数输出）仅由 `materialize_physical` 主动调用生成。

## 6. 实测 parameter counts（可训练参数量）与配对公平性

|模型|v1 总数|v2 总数|增加|v2 衰减组|v2 不衰减组|
|---|---:|---:|---:|---:|---:|
|B0-Matched|4,329,361|4,329,410|49|4,322,880|6,530|
|B1|4,331,761|4,331,810|49|4,325,280|6,530|

两模型的 head family（输出头族）完全一致，均为 `48→1` 和 `48→33` 的直接 1×1 卷积，共 1,666 个头参数。二者唯一张量形状差异仍是最前端两个输入 kernel（卷积核）；相差 2,400 个参数。没有 attention（注意力模块）、recurrent（循环时序模块）或新增信息源。

全新 seed（随机种子）2026 初始化的确定性已验证，但它仍是待批准候选。分别重新设相同种子并不自动使形状不同模型的后续参数同值。本轮仅在独立夹具中研究旧版“全新 anchor（配对参照模型）的同名同形参数复制”政策，并验证头逐值一致、B1 原生输入核未变；没有形成正式初始化状态。

## 7. Gradient path（梯度路径）

`input→backbone（主干网络）→SP04→occurrence head→33 raw outputs→FP64 qlog→L_occ+L_qr→backward（反向求导）`。

数学上 `dq_i/dw_k=S*(1[k≤i]*W-prefix_i)/W²`，`dq_i/ds=c_i*sigmoid(s)`；分配权重共同改变内部位置，q32 对分配 logits 的导数为 0。损失沿用冻结的 occurrence focal loss（发生事件焦点损失）、conditional pinball loss（条件分位数损失）及实际云南有效像元分母。没有引入 KD（知识蒸馏）或外部损失。

## 8. Physical-output path（物理输出路径）与风险可见性

显式 `Q_i=expm1(q_i)` 使用 FP64。实际非有限数仍抛出异常，绝不替换。`threshold_censored_mean`（阈值删截均值代理）沿用 `p*mean_32(Q_i)`，属于既有 DIAGNOSTIC_PROXY（诊断代理指标），不是完整无条件降水均值的新科学定义。

只读 physical-risk diagnostic（物理转换风险诊断）报告最大 qlog、32 个 tau 范围及 FP32/FP64 `log1p(finfo.max)` 风险。它不执行 expm1、不接入损失、不改变 RNG 或梯度、不自动跳过 batch。qlog 有限性、支持域与严格单调 guard（运行时保护）仍是必须执行的检查。

## 9. 与 v1 的明确差异

|项目|v1|v2 候选|
|---|---|---|
|分位数输出通道|32 个累计增量|32 个分配 logits + 1 个跨度 logit|
|q32|32 个正增量之和 + z0|单独 S + z0|
|相邻间距|softplus(raw)+epsilon_mono|S*w_i/W|
|核心训练|隐式物理生成，溢出会阻断|只使用对数域结果|
|物理生成|每次 forward|显式请求，并如实保护|
|浮点限制|已有 FP64 保护|FP64 变换与保护，披露实数证明和机器表示差异|

## 10. 保持不变的科学语义

事件严格 `R>0.1 mm/h`、32 个条件 tau、log1p 域、云南行政区评价 mask、SP04、target（监督目标）、主干和 decoder（解码器）结构、occurrence 头、`L_occ+L_qr` 损失族均保持不变。数据、标准化和训练协议是否复用于 v2 仍是研究者决策，不冒称已经批准。

## 11. 改变的科学与数值语义

总跨度与分配之间的耦合、参数自由度、梯度路径的几何和 epsilon 的含义发生改变。`epsilon_w=epsilon_span=1e-4` 只作为已批准工程测试候选；旧 `epsilon_mono=1e-4` 的“每步增量下界”语义不再成立。v2 间距没有固定 1e-4 下界；不自行引入新的科学常数。

## 12. Phase-A（开发训练阶段）是否需要重跑

如果研究者最终接受 v2，需要用独立的新 Phase-A 验证新模型方法；旧 Phase-A 指标和 BEST（旧规则选中的最优 checkpoint）不能当作 v2 的结果或正式权重初始化。是否批准、何时开始和具体协议均未决定。本轮没有正式训练。

## 13. Phase-B（最终合并拟合阶段）是否从 scratch（全新起点）开始

若以后进入 v2 Phase-B，必须建立独立全新初始化流程，不能从旧 epoch 4、旧 Phase-A BEST 或旧 optimizer/scheduler（优化器/学习率调度）状态恢复。新 epoch budget（训练轮数预算）不由本轮自动选择；本轮不恢复旧 Phase-B，也不启动 B1 Phase-B。

## 14. B0-v2 / B1-v2 fairness（公平比较）

候选继续使用 common intersection（共同满足资格条件的样本集合），Train（训练集）10,455、Validation（验证集）10,501；两模型 target 身份逐值相同。B0 使用最近 B13，B1 使用冻结六槽，除此之外共用头族、主干、空间映射、mask 与候选共享标准化。v1 历史结果不能替代新的 v2 配对实验。

## 15. 2025 governance（2025 数据治理）

开发 guard 禁止本轮所有原始源访问，2025 原始读取和 outcome（评价结果）查看为 0。使用合成张量、历史配置、历史 manifest 与已保存诊断记录；没有读取 2025 IMERG 降水值、模型输出或 prevalence（降雨发生率）。数据选择不根据 2025 结果进行。

## 16. 待研究者批准的事项

最终 v2 科学接受；两个 epsilon 的正式值；seed 2026 与全新配对初始化政策；10,455/10,501 样本和 train-only（仅训练集拟合）共享标准化复用；独立 Phase-A 训练协议；未来 Phase-B 的数据、标准化、预算、初始化与授权。任何正式训练均需后续明确批准。

## 工程测试与状态

v2 新测试 39 项；相关 v1 回归 653 项；总计 692 项，全部通过且无跳过。随机压力覆盖每种原始 dtype（数据类型）50,000 个混合像元与 81 个常数组合；指定 ±1e4 范围采用 FP64 变换全部通过。实测结果及反例见 `test_attempts/attempt_007/numerical_verification.json`。

两个 v2 模型另以真实 CUDA BF16 合成输入完成 `[B,1/6,501,501]→SP04→v2 head→核心损失→反向梯度`，批次 2 和单样本尾批次均核验；分母为 6860/3430，主干、分配头、跨度头的梯度均非零且有限。此项只求导及裁剪，没有优化器更新。

历史 2713 个文件（含 41 个 checkpoint）前后字节一致。v2 与 A 等价性模型全部是临时全新夹具，没有正式 checkpoint 写入。既有完成运行的回归只读反序列化旧 Phase-A BEST/LAST 共 4 次，均先核验 SHA/大小，未将状态应用于 v2；没有加载旧 Phase-B epoch 4。旧依赖身份核验采用明示隔离的当时冻结清单，不把新 v2 文件混入旧身份，原代码、模型计算、损失、优化器、scheduler 均未修改。相关适配与旧证据目录绑定详见 `legacy_regression_scope.json`。

首轮 CPU BF16 后端限制、第二轮旧测试证据目录缺失、第三轮旧 Final Test 报告与后来修订入口的身份差异、第四轮旧 Phase-B 递归清单包含后来新增模块的身份差异、第五轮适配器误将真实仓库清单用于临时伪源码夹具，均单独保存，未改写为通过。第三项复用既有历史源码夹具适配器，从旧 Git 字节重建报告所绑定的源码；第四项独立逐文件核验旧报告的每个冻结哈希；第五项将适配严格限定为真实仓库根目录，临时夹具继续执行原函数及其负例拒绝。这些隔离仅作用于历史报告身份测试；当前数值测试仍使用当前代码。详见 `historical_final_test_fixture_identity.json`、`historical_phase_b_inventory_identity.json` 和 `legacy_regression_scope.json`。实际通过的 suite（完整测试套件）身份以最后完成的 attempt（测试尝试记录）及其代码 SHA 为准。

另有针对性检查因 Windows 默认 GBK（中文传统文本编码）解码含中文路径的旧日志而失败，保留在 `adapter_targeted_check/`；进程启动时固定 `PYTHONUTF8=1` 后，`adapter_targeted_check_002/` 的 76 项授权与历史状态检查全部通过。它们属于额外排查，未重复计入最终完整套件总数。

第六轮在只允许标准库的旧诊断测试处停止：合并运行的父进程已加载 torch，违背其进程隔离断言。原失败保留；最终完整套件将该模块 16 项原测试放入真正独立、未加载 torch/netCDF4 的 Python 进程，保留原断言，计入完整回归总数一次，未删除或跳过测试。详见 `stdlib_regression_tests.json`。

末段针对性检查另有两次沙箱拒绝 Python 私有临时目录访问的错误，保留在 `late_regression_targeted_check/` 与 `late_regression_targeted_check_002/`。后续将 TEMP/TMP（临时文件目录）固定到受控英文目录，并以获准测试进程权限执行同一套测试；未修改测试或扩大原始数据访问范围。

```text
V2_IMPLEMENTATION_READY=true
V2_TESTS_PASS=true
V2_SCIENTIFIC_FREEZE_READY_FOR_RESEARCHER_REVIEW=true
V2_SCIENTIFIC_FREEZE_APPROVED=false
V2_PHASE_A_AUTHORIZED=false
V2_PHASE_A_STARTED=false
V2_PHASE_B_AUTHORIZED=false
FORMAL_TRAINING_AUTHORIZED=false
B0_MATCHED_V2_PHASE_A_STARTED=false
B1_V2_PHASE_A_STARTED=false
B0_MATCHED_PHASE_B_RESUME_AUTHORIZED=false
B1_PHASE_B_STARTED=false
FORMAL_OPTIMIZER_STEPS_ADDED=0
2025_RAW_ACCESS=0
RESEARCHER_DECISION_REQUIRED=true
```

实现位于 `src/yuntapr/models/quantile_v2/`；候选配置位于 `config/science_v2/`。所有 code SHA（实现代码字节指纹）、config SHA（配置字节指纹）、decision packet SHA（决策包字节指纹）将在独立 `final_manifest.json` 登记，避免自引用 hash。
