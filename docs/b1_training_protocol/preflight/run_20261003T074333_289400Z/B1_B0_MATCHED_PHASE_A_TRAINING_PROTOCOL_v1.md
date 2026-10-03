# B1 + B0-Matched-Control Phase-A Training Protocol v1

本轮完整协议已冻结，两种正式 runner 已实现并通过工程 preflight。**B1 与 B0-Matched-Control 的正式训练均未授权、未启动；正式 optimizer steps=0，2025 raw access/pixels/inference=0。** 本报告不包含模型效果对比，也不执行完整2024 Validation。

Run：`run_20261003T074333_289400Z`；baseline：`207a1872341f4fcdfd85eb534c892400fcf2ba99`。保留1982个既有跟踪文件的原始bytes/SHA及旧run、失败、report、checkpoint identity；本轮仅新增文件。新registry补充冻结旧B1 registry中的训练参数及matched scaler待决项，不回写旧状态。

## 科学设计、样本集合和 preprocessing

2023 Mar-Oct Train=10,455，2024 Mar-Oct Validation=10,501。两模型使用common intersection的相同scene IDs、target/day/index/SHA、mask和排序规则；历史B0不等于matched control，未修改历史B0训练集合、scaler、checkpoint或结果。全部四份manifest和既有scaler的SHA逐个核验，身份列表逐值比对。

B1输入 `[B,6,501,501]`：仅B13，analysis_time=T+30min，nominal=analysis_time−[60,50,40,30,20,10]min，最旧→最新通道0→5；B0-Matched输入 `[B,1,501,501]`，只读同一scene的slot5。T保持既有冻结native IMERG window start。预期扫描bucket只作metadata对照；真实逐帧强制obs_start≤obs_end≤analysis_time，date_created只记录，不声称operational availability。

M1严格完整：任一槽missing/unreadable/partial/all-fill/nonfinite/metadata-invalid/noncausal，整个scene拒绝。无older/nearest fallback、重复、零占位、插值。窗口起点历史不足拒绝，不读February补齐。10月最后target的analysis_time可为11月1日零点，它只是时间标签，全部被读取native帧和IMERG target仍在Mar-Oct内。

两模型均采用研究者批准的frozen B1 shared scaler：mean=271.60515414265217 K，std=19.93959597783802 K，ddof=0；scaler SHA256=`656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31`。B0-Matched正式采纳`USE_FROZEN_B1_SHARED_SCALER`。只加载已冻结的2023 scene-slot exposure拟合产物，**本轮未重新拟合**，2024/2025/IMERG不参与fit。transform：`((decoded_K_float32.astype(float64)-mean_K)/std_K).astype(float32)`。

## Architecture与paired initialization

保持4-level residual U-Net 48→96→192→256、GN/GELU residual、learned stride2、exact resize+concat decoder无crop、SP04 native48×501×501→48×100×100、direct1×1 occurrence48→1与quantile48→32。无额外源、attention、Transformer、recurrent或temporal module。target/mask/head/probability语义完全继承，坐标逐值逐bit核验，无flip/transpose/重构；云南center-in-polygon正式mask=3430 cells。

B0-Matched=4,329,361参数；B1=4,331,761；delta=2,400。不同形tensor恰为`backbone.enc0.conv1.weight`与`backbone.enc0.skip.weight`。分别重新设seed=2026创建fresh B0 anchor/fresh B1，再仅复制同名同形tensor。72个shared tensors逐bit一致；两个B1输入kernel保留自身seed2026的native结果，原生skip零初始化保留，未repeat/average/inflate/zero-fill/映射。完整fresh replay通过；未读取历史trained checkpoint，没有optimizer/scheduler transfer。

- B0-Matched initial model state SHA256：`57a4d103a31aa7be1a52af079cdf7fb81bc73c51ba3e0e97d395513d21d9023d`
- B1 initial model state SHA256：`9aa5dad0456e8d78862fb485d4c37f172aa1360e1d350ac9df101a953799718e`

这里是initialization fairness control，不是checkpoint transfer。parameter names/shapes/counts及每个shared tensor SHA保存在paired manifest。

## 完整共享训练协议

Occurrence=`P(R>0.1mm/h)`，R==0.1为negative；focal alpha=.5/gamma=2。32 conditional tau_i=(i−.5)/32；FP32 raw head→FP64 monotonic transform/physical quantiles/pinball，epsilon_mono=1e−4。core=`L_occ+L_qr`，quantile axis mean，均除以实际有效监督像元数；无extra multiplier，KD=0，external loss disabled。

AdamW betas=(.9,.999)、eps=1e−8、WD=1e−4，仅Conv2d kernel decay；Conv bias/GN affine no-decay。amsgrad/maximize/capturable/differentiable/foreach/fused全部false。B0-Matched decay=4,322,832/no-decay=6,529；B1 decay=4,325,232/no-decay=6,529；disjoint与complete union通过，unknown参数拒绝。

global grad norm clip=5，error_if_nonfinite=true；记录pre/post norm、clip count/fraction。loss/gradient/parameter/output任何nonfinite均停止；不sort/clamp修复quantiles。forward BF16 autocast，parameters/raw quantile FP32，transform/physical/pinball FP64；GradScaler=false、TF32=false。

GPU实测后冻结physical batch=2、accumulation=1、nominal effective batch=2、drop_last=false；每epoch5227个batch2+1个singleton，实际分母分别6860/3430，单例不补齐、不丢弃、不重复，tail的actual batch=1。Train每scene exactly once；两个模型同一`torch.randperm`，独立Generator seed=2026+zero-based epoch index。50个完整permutation/coverage计划逐个核验。

STEPS_PER_EPOCH=5228，W=5228，U=261400=50×5228，max_epochs=50。U只是数学LR horizon，允许由固定early stopping提前结束。stateless one-based u，LR在optimizer.step前设置：

`lr(u)=1e-4*u/W`，1≤u≤W。

`lr(u)=1e-6+(1e-4−1e-6)*(1+cos(pi*(u−W)/(U−W)))/2`，W<u≤U。

首步LR=1.9127773527161438e−8；u=W精确1e−4；u=U精确1e−6。沿用研究者解释：min_lr下界只用于cosine，warmup不clamp。全部261400个数学值已检查；无validation-dependent LR、ReduceLROnPlateau或cosine compression。

Validation batch=8，两模型相同，固定10501顺序，无shuffle/drop/replacement。每completed epoch完整Validation，仅全样本集合float64原始numerator累计：`val_core=(S_occ+S_qr)/N_valid`，禁止batch-average。继承Brier、AUROC、非插值exact-score-group AP、conditional pinball、32 tau coverage/coverage errors、crossing/nonfinite、DIAGNOSTIC_PROXY定义；POD/FAR/CSI仍THRESHOLD_NOT_FROZEN，不能依据其它diagnostics选择checkpoint。

BEST每模型独立，任何strict lower exact global val_core才更新，tie保留最早epoch。early stop独立patience=8/min_delta=1e−4，仅`val_core<best_es−1e−4`算改善；不可把BEST与ES阈值混用。

## GPU与loader真实工程证据

CUDA Python=`F:\pytorch\Research\.venv-cuda\Scripts\python.exe`，torch2.11.0+cu128、CUDA12.8、RTX5060 Laptop GPU，总8150.5625MiB。保持deterministic algorithms、CUBLAS_WORKSPACE_CONFIG=:4096:8、PYTHONHASHSEED=2026、cuDNN deterministic/benchmark=false。未安装或升级环境包。

继承旧判据：peak_reserved≤(1−margin)×total，并且estimated_min_free≥margin×total；estimated_min_free=min(free_after,free_before−max(0,peak_reserved−reserved_before))。15%为最低安全记录，20%为本轮正式工程配置冻结条件。train均fresh独立、2warmup+5measured真实更新，包含实际AdamW state。

|Train batch2|Peak allocated MiB|Peak reserved MiB|Estimated min free MiB|20%|
|---|---:|---:|---:|---|
|B0_MATCHED|2738.308|3268|3654|通过|
|B1|2758.600|3282|3640|通过|

|真实2024 Validation batch8，纯inference|Peak allocated MiB|Peak reserved MiB|Estimated min free MiB|20%|
|---|---:|---:|---:|---|
|B0_MATCHED|3288.368|4180|2746|通过|
|B1|3331.057|4272|2654|通过|

共同batch8通过；已测试的9/10/12/16更大候选不满足共同20%标准，另用16个真实2024 Validation fixtures独立确认8通过、9/16不安全。最大共同值指当前设备、当前测量条件及已声明整数搜索边界下的选择；没有宣称任意硬件/运行时下的永久最大值。不执行完整10501 validation，不据此比较科学效果。

实际两个worker，pin_memory=false/persistent_workers=false/prefetch_factor=1，两个模型各读取32个不同真实2023 Train scenes；再读取2024 fixtures。B1逐scene六个frame逐个staging+SHA+decode+CF检查；B0 latest与B1slot5 normalized tensor、target逐值相同。worker峰值working-set之和：B0-Matched 1222.602MiB、B1 1296.406MiB；无worker error、deadlock、staging conflict或内存不稳定。

每worker独立ASCII staging，单文件734003200bytes cap，source只读，复制size/hash与冻结源SHA在decode前验证，copy_seconds/read_seconds/temporary bytes/cleanup逐项记录；仅删除本流程UUID副本。两次run staging目录最终均无nc副本；H盘、旧5个diagnostic cache不删除，未永久复制月份数据。

四个独立ENGINEERING_ONLY smoke：

|case|actual batch|forced u|LR|denominator|loss|pre clip|post clip|
|---|---:|---:|---:|---:|---:|---:|---:|
|A B0_MATCHED|2|1|1.9127773527161438e-08|6860|0.12723901|6.34641|5.00000|
|B B1|2|1|1.9127773527161438e-08|6860|0.13739958|7.99370|5.00000|
|C B0_MATCHED|1|5228|0.0001|3430|0.12383510|5.77724|5.00000|
|D B1|1|5228|0.0001|3430|0.12671496|6.84635|5.00000|

四个smoke各1次optimizer.step，加train feasibility14次，总18次ENGINEERING_ONLY updates；不执行tail之前5227步。crossing/support/nonfinite=0，p∈[0,1]；临时fresh模型/optimizer销毁，无正式checkpoint/history。测试fixture另计，正式optimizer steps始终0。

## Formal runner / checkpoint / resume

正式入口：`scripts/train_b1_phase_a_v1.py`、`scripts/train_b0_matched_phase_a_v1.py`。共享实际循环在`scripts/paired_phase_a_entry.py`，合同/数据/模型及checkpoint helper在新增src模块中。入口没有epoch/hyperparameter override和historical checkpoint初始化参数。

缺少另行研究者授权时，在raw训练读取、model/optimizer构造之前拒绝。未来auth必须是repository JSON，SHA固定、AUTHORIZED=true、model-specific、protocol/scaler/Train/Val/code hashes匹配并含researcher approval reference；raw/checkpoint路径作为authorization在hash前拒绝。本轮没有这样的授权文件；提供的模板全部AUTHORIZED=false。

checkpoint本地root固定为`F:\pytorch\Research\outputs\formal_training\b1_phase_a`与`...\b0_matched_phase_a`，仅completed Train+full Validation epoch边界写入。保存完整provenance、model/optimizer/RNG state与checksum、sample order coverage、stateless LR index、BEST/ES独立状态；atomic写入/回读验证后登记BEST/LAST。Git仅identity/path/bytes/SHA/history/manifest/report，不提交任何.pt/.pth/.ckpt或optimizer/model binary。

只从verified completed LAST恢复下一完整epoch，无mid-epoch exact resume。先验证文件root/name/bytes/SHA，再检查全部provenance、boundary、model keys/shapes/dtypes、optimizer settings/moment/step counts及RNG兼容性，然后才能应用任何state。已完成的epoch禁止覆盖；fresh paired initialization和历史checkpoint initialization互不混用。checkpoint保存train numerators，支持LAST先写成功而history中断时恢复该边界记录。Resume next-update/RNG exact replay在隔离toy fixture中通过。

本轮未启动正式runner的训练循环，未运行完整Train/Val epoch，未产生正式checkpoint；runner ready依赖真实forward/loss/backward/update、覆盖/选择/恢复/授权的独立测试，而非科学效果证据。

## 测试、历史与失败记录

|suite|不同case数|最终结果|
|---|---:|---|
|NEW_PROTOCOL_MODEL_DATA_RUNNER|33|PASS|
|NEW_REAL_PREFLIGHT_ARTIFACTS|16|PASS|
|INHERITED_B0_DATA_SPATIAL_MODEL_LOSS|20|PASS|
|INHERITED_SCIENTIFIC_CONTRACTS|72|PASS|
|INHERITED_QC|8|PASS|
|INHERITED_QUANTILE_NUMERICS|14|PASS|
|INHERITED_PHASE_A_PROTOCOL|17|PASS|
|INHERITED_PHASE_A_RUNNER|9|PASS|
|INHERITED_PHASE_B_RUNNER|32|PASS|
|INHERITED_GPU_SAFETY|6|PASS|
|INHERITED_B1_AUDIT|30|PASS|
|INHERITED_B1_SCIENCE_SCALER|31|PASS|

共288个不同case全部通过、0skip；含初始失败与复验实际调用299次。48项最初新增case及后补真实2024 artifact case=49项新增，其余为相关继承regression。TEST_FIXTURE_ONLY中28次optimizer/51次backward，临时模型/checkpoint清理；不计入18次真实工程GPU更新，更不计入正式更新。测试无真实raw/checkpoint打开。

首轮31-case单位检查失败（analysis标签跨月与Windows临时ACL）保留；修正后32-case检查通过，授权路径新检查加入后为33新单位case。`run_20261003T072548_191803Z`因psutil监测依赖缺失在GPU前失败，保留源码/trace；新run采用Windows原生working-set计数器，未改变loader设置或安装包。

第一次回归缺少两项旧证据目录绑定，后补只读绑定；旧Phase-B hash test还发现其glob清单包含后来新增的B1/evaluation源码，不能等同于原执行清单。复验在TEST_FIXTURE_ONLY中复制并逐SHA验证原清单全部当前文件bytes，再调用原hash函数检查原inventory；旧测试/证据未修改，后来新增源码由本轮独立hash测试验证。所有失败、setUpClass error及复验日志均保留，无跳过、删除测试或用NOT_RUN作PASS。

GPU检查后仅强化授权JSON路径guard与history恢复；执行源码已归档，optimizer/forward/loss/clip/batch plan/EpochCoverage/protocol body的AST逐项一致，最终source hashes经独立artifact测试核验。不因工程结果擅自改变冻结科学约定。

## 交付身份与最终状态

Protocol SHA256：`284f71ca6677f23c018ed9ee3e8d8b298fe3e472735689953cd42d73f4ea57b6`。

Scalers、四份sample manifests、SP04、mask、science/engineering及旧GPU判据路径/SHA见protocol manifest；初始model SHA见paired manifest；代码与schema的最终SHA见runner closure manifest；交付全文哈希见delivery index。

FROZEN：设计、M1、common sample sets、两模型shared normalization、paired initialization、完整Phase-A protocol、physical2/accum1/validation8及loader配置。

NOT_AUTHORIZED / NOT_STARTED：B1 training、B0-Matched training、2025 Final Test。FORMAL_OPTIMIZER_STEPS=0；2025_RAW_ACCESS=2025_PIXELS_READ=2025_MODEL_INFERENCE_SCENES=0。不自动进入B2/下一阶段。正式训练仍需要另行研究者授权；当前没有未闭环的参数待决项。
