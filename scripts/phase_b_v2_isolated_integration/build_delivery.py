"""Chinese source-grounded teaching documents, using actual synthetic results."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json

REPO = Path(__file__).resolve().parents[2]
OUT = REPO/"docs/phase_b_v2_isolated_integration/v1"
SOURCE = REPO/"src/yuntapr/experimental/phase_b_v2_integration"
BASELINE = "ca524b1accdcb30524cf106bf40d533d698e61e7"
DOCS = ["INTEGRATION_ARCHITECTURE.md", "MODEL_INTERFACE_AUDIT.md",
        "SYNTHETIC_NUMERICAL_AND_GRADIENT_RESULTS.md", "GPU_RESOURCE_MEASUREMENTS.md",
        "INITIALIZATION_AND_ORDER_AUDIT.md", "EXECUTION_AND_RECOVERY_GATES.md",
        "FORMAL_INTEGRATION_DIFF_AND_GAPS.md", "RESEARCHER_REVIEW_CHECKLIST.md", "MODULE_STUDY_GUIDE.md"]


def write(name, text):
    with (OUT/name).open("x", encoding="utf-8", newline="\n") as stream: stream.write(text)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_new(name, value):
    write(name, json.dumps(value, ensure_ascii=False, indent=2)+"\n")


def main():
    cpu=json.loads((OUT/"tests/cpu_attempt_002.json").read_text())
    cuda=json.loads((OUT/"tests/cuda_attempt_002.json").read_text())
    assert cpu["counts"]["passed"]==91 and cuda["counts"]["passed"]==6
    cases=[json.loads(p.read_text()) for p in sorted((OUT/"tests/cuda_attempt_002_evidence").glob("E*.json"))]
    json_new("SYNTHETIC_NUMERICAL_RESULTS.json", {"scope":"SYNTHETIC_ENGINEERING_ONLY",
        "scientific_performance_evidence":False,"source_attempt":"cuda_attempt_002","cases":cases})
    write("README.md", """# Phase-B v2 隔离集成与合成验证 v1

基线 ca524b1accdcb30524cf106bf40d533d698e61e7；起始本地/远端main一致、已跟踪文件干净，无运行中的Python任务。本轮没有重跑旧177/3项测试，未改历史模型、loss、正式入口、冻结证据或旧候选实现；旧未跟踪文件保留。

当前 SYNTHETIC_INTEGRATION_PASS：CPU91、CUDA6通过，0失败/错误/跳过，静态15项通过。B0/B1完整501×501、batch2、BF16/FP32/FP64路径均完成三臂forward/backward。E0与原loss全部参数梯度最大绝对差为0。结论仅覆盖记录的人工张量和环境。

1. [架构](INTEGRATION_ARCHITECTURE.md)、[接口审计](MODEL_INTERFACE_AUDIT.md)、[合成数值和梯度](SYNTHETIC_NUMERICAL_AND_GRADIENT_RESULTS.md)。
2. [GPU实测](GPU_RESOURCE_MEASUREMENTS.md)、[fresh初始化与排列](INITIALIZATION_AND_ORDER_AUDIT.md)。
3. [执行与恢复门槛](EXECUTION_AND_RECOVERY_GATES.md)、[正式集成差异和缺口](FORMAL_INTEGRATION_DIFF_AND_GAPS.md)。
4. [逐文件学习](MODULE_STUDY_GUIDE.md)、[研究者审查](RESEARCHER_REVIEW_CHECKLIST.md)、[测试记录](tests/README.md)。
5. [可编辑LaTeX](ISOLATED_INTEGRATION_REVIEW.tex)、[中文PDF](ISOLATED_INTEGRATION_REVIEW.pdf)、[最终状态](final_status.json)、[manifest](manifest.json)。

新增源码 src/yuntapr/experimental/phase_b_v2_integration/；测试 tests/phase_b_v2_isolated_integration/；工具 scripts/phase_b_v2_isolated_integration/。实际发布SHA由追加publication_receipt.json绑定，commit不是批准。

V2_PHASE_B_AUTHORIZED=false；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED；2025_RAW_ACCESS=2025_PIXELS_READ=0。无optimizer.step、真实2023/2024数据、2025数据或私有checkpoint访问。人工3430格点mask不是云南真实地理掩膜。
""")
    write("INTEGRATION_ARCHITECTURE.md", """# 隔离集成架构与边界

范围为 SYNTHETIC_ENGINEERING_ONLY。独立命名空间没有优化器、epoch训练循环、数据集加载器、checkpoint应用器或正式启动能力。模型构造会读取原公开科学合同和SP04静态资料，全部SHA已绑定。

|模块|职责|边界|
|---|---|---|
|pins.py|核验66个已有源码/协议/公开元数据SHA|外部mask仅声明，不打开|
|resources.py|构造前资源准入|不足停止，不改batch/精度/结构|
|synthetic.py|两场景、六槽及末槽、人工参考与mask|无路径和真实年份|
|initialization.py|真实fresh模型、同形复制和字节摘要|不读/存权重|
|adapter.py|原v2模型接到已有候选loss|固定B2、501到100网格|
|controls.py|候选规则、排列、终点、恢复拒绝|不能授权执行|
|safety.py|文件和操作进程守卫|禁止raw/checkpoint/2025、step和expm1|
|__init__.py|scope常量|包本身不构造模型|

调用顺序：资源准入→来源SHA→fresh B0/B1→人工张量→原backbone/SP04/双头→既有candidate_loss→合成backward→参数SHA复核。仅测试代码引用原b0_core_loss作E0对照；未调用正式forward_loss/update。

train()只设置模块模式，backward只计算梯度，没有optimizer实例或step。fresh构造及B0到B1的同形初值复制属于本轮授权范围，不读取历史状态。

scope字符串、frozen dataclass、JSON和SHA都不是认证机制。隔离依据内部人工fixture、调用图、进程守卫和无训练能力的BlockedRunner；这不是操作系统安全沙箱。工程PASS始终不能转成独立人类授权。
""")
    write("MODEL_INTERFACE_AUDIT.md", """# B0/B1 接口兼容性

实际来源为quantile_v2/models.py、heads.py、parameterization.py、outputs.py；backbone_b0.py、b1.py、blocks.py及spatial/projection.py、sp04_mapping.py。来源字节见source_identity.json。正式forward_loss仅只读核对，未调用。

|控制|实际检查|
|---|---|
|B0输入|[2,1,501,501]，取B1人工输入最后一槽|
|B1输入|[2,6,501,501]，60/50/40/30/20/10分钟、最旧到最新|
|M1|独立bool native mask全有效，缺测拒绝|
|中间特征|[2,48,501,501]→冻结SP04→[2,48,100,100]|
|双头|发生raw1；quantile raw33（allocation32+span1）→q32|
|目标/分位数|原FP32[2,1,100,100]；FP64[2,32,100,100]|
|精度|参数FP32、backbone/发生头BF16、raw quantile FP32、变换/Pinball FP64|
|阈值和分母|先float32>float32(0.1)再升精度；训练N_valid、科学CPB N_rain|
|support|SP04全1；原生invalid0；严格q顺序/支撑沿用原守卫|
|候选参数|E0=(.5,2,1)、E1=(.5,0,1)、E2=(.5,2,2)，来自既有get_config|

人工参考包含0、float32阈值、阈值向上相邻数及正雨强。当前N_valid=6860、N_rain=4900只是fixture属性。人工mask在每场景平铺前3430格点为True，不能检验真实云南地理配准。

SP04仍用原公开坐标轴和成员映射，每个目标单元25个原生中心取算术均值；没有重建或替换。shared scaler的身份与N0角色被核验；人工输入直接处于归一化数值空间，没有拟合scaler或对真实Kelvin观测应用它。实际解码、normalization和真实mask对应尚未验证。

CPU用例验证完整目标网格接口与负面条件，不运行CPU完整backbone backward；完整双模型forward/backward在CUDA执行，无CPU或精度降级。
""")
    text="""# 合成数值与梯度结果

全部数值为 SYNTHETIC_ENGINEERING_ONLY 工程算术，不是降水性能证据。没有真实Brier/AUROC/AP、校准、覆盖率或物理上尾新结果。

|候选|模型|S_occ|未加权S_qr|训练objective|未加权S_qr/N_rain|
|---|---|---|---|---|---|
"""
    for d in cases:
        a=d["synthetic_arithmetic_not_performance"]
        text+=f'|{d["arm"]}|{d["model"]}|{a["S_occ"]:.9g}|{a["S_qr_unweighted"]:.9g}|{a["weighted_objective"]:.9g}|{a["unweighted_conditional_mean"]:.9g}|\n'
    text+="""
同一初态和输入下，三个条件的未加权分位数分子及CPB完全相同。lambda改变训练objective，不改变同一输出的科学指标定义；这不预测正式训练后的性能。

每个完整case检查74个参数张量：梯度全部存在、shape/dtype一致、全部有限；未裁剪或优化。输出处梯度检查：E2的qlog梯度为E0的2倍、发生logit梯度相同；E1的qlog梯度与E0相同。不能据此要求共享backbone的总梯度整体乘2。

E0复用实际模型输出，在冻结BF16 autocast下计算原b0_core_loss；分别做候选/原loss完整backward，比较全部参数梯度。预定容差rtol=8e-7、atol=1e-8；条件分位数项1e-12/1e-14，未放宽。
"""
    for d in cases:
        if d["arm"]=="E0":
            c=d["E0_original_loss_compatibility"]
            text+=f'\n{d["model"]}：总loss绝对差{c["loss_abs_difference"]:.12g}，全部参数梯度最大绝对差{c["maximum_parameter_gradient_abs_difference"]:.12g}，PASS。\n'
    text+="""
每个case前后state SHA相同。最终矩阵6次完整forward、8次完整backward（两个E0各多一次原loss对照）；连同日志修复前复测，本轮累计12/16。CPU输出张量backward与完整模型计数分开，复测不是新增独立科学证据。

当前唯一pytest用例97=CPU91+CUDA6，0失败/错误/跳过。CPU首轮87通过/4失败，修复后91通过；CUDA首轮6通过/1日志warning，修复后6通过/0warning。全部attempt共194次pytest实例，唯一覆盖仍97；旧177/3未重跑。

这些测试不能证明泛化、校准或q32问题改善，不构成Phase-A验收或历史恢复追认。
"""
    write("SYNTHETIC_NUMERICAL_AND_GRADIENT_RESULTS.md",text)
    text="""# GPU 实测与限制

RTX5060 Laptop GPU，PyTorch2.11.0+cu128、CUDA build12.8。完整case构造前要求主机可用≥8GiB、工作盘剩余≥1GiB、CUDA BF16可用、CUDA API free≥5GiB；单独初始化要求主机≥2GiB。门槛是预设工程准入，不是用量预测。实际快照附各evidence JSON。本轮没有OOM或资源降级。

固定batch2、501×501、原结构和BF16/FP32/FP64。cuda synchronize与perf_counter计时；reset_peak_memory_stats后记录PyTorch峰值。

|候选|模型|forward+loss ms|主backward ms|allocated MiB|reserved MiB|
|---|---|---|---|---|---|
"""
    for d in cases:
        m=d["synthetic_measurement"]
        text+=f'|{d["arm"]}|{d["model"]}|{1000*m["forward_and_loss_seconds"]:.2f}|{1000*m["selected_loss_backward_seconds"]:.2f}|{m["primary_peak_allocated_bytes"]/2**20:.2f}|{m["primary_peak_reserved_bytes"]/2**20:.2f}|\n'
    text+="""
每项只有一批。首项含冷启动，后续可能复用库缓存，不能据此排名模型速度。forward+loss含适配检查和同步；峰值包含同输出三臂梯度检查，E0为原loss对照保留图。JSON还记录完整case额外对照峰值。

allocated/reserved不含完整驱动或其他应用显存。没有AdamW状态、真实I/O、DataLoader staging、batch8验证、checkpoint或长时运行。不能把本表直接乘846936估计正式总时长，也不能批准验证batch8的显存。

正式前另需获准测量：真实数据防火墙；两worker各734003200字节staging上限；训练batch2/验证batch8峰值；AdamW状态与checkpoint临时空间；设备共用、电源温度、驱动和余量；真实吞吐及恢复时间。

FP32模型加两份FP32 AdamW矩的张量存储下界为12×参数数：B0 51952920字节，B1 51981720字节。若保留18run各9epoch共162份，下界约8.42GB（十进制），不含容器、step/RNG、元数据、日志、原子临时副本。这不是实测checkpoint大小或已批准保留策略；正式runner必须另定磁盘预算并在不足时停止。
"""
    write("GPU_RESOURCE_MEASUREMENTS.md",text)
    write("INITIALIZATION_AND_ORDER_AUDIT.md","""# Fresh 初始化、排列与固定终点

CPU对三个seed各为E0/E1/E2独立构造一对真实模型，共18实例。不同seed的state SHA不同；同模型同seed跨三臂state、buffer和post-pair RNG摘要一致。CUDA的seed2026初态与CPU证据一致。没有保存正式初始化权重。

依据原paired_initialization规则分别重置Python/NumPy/Torch/CUDA，构造B0与B1，然后只复制同名同形状张量。唯一不同形状为backbone.enc0.conv1.weight和backbone.enc0.skip.weight；B1二者原生SHA保持，skip为0。参数总数4329410/4331810。使用原state_digest和parameter_groups分类，没有构造optimizer。

PYTHONHASHSEED在进程启动时固定2026，CUBLAS_WORKSPACE_CONFIG=:4096:8；逐run的Python/NumPy/Torch/CUDA seed取2026/2027/2028。context退出恢复调用者状态。SHA证明当前初始化字节，不证明批准；正式全程随机性和环境仍需绑定。

仅用10455个人工order_ID，独立Generator(seed+epoch_index)做randperm。每seed的9个epoch无丢失/重复，重复调用一致；seed2026与原epoch_permutation纯数学规则对照。未读取真实样本内容。

S0复用上一轮全部47052个LR位置通过证据，并核对源码字节未变；不重跑旧套件。新增epoch0/1/8/9边界检查，epoch9剩余0、next_epoch/next_lr为None。没有压缩50epoch cosine、按表现选BEST或自动换seed。

18候选run每个47052潜在更新，共846936；验证每epoch1313批，共212706。实际更新0。新命名空间以SYNTHETIC_ENGINEERING_ONLY__phase_b_v2_integration_v1__开头，与历史正式run隔离。
""")
    write("EXECUTION_AND_RECOVERY_GATES.md","""# 执行与恢复负面检查

|尝试|处理|
|---|---|
|无独立批准|BlockedRunner无条件抛错|
|True、APPROVED、AUTHORIZED_TO_EXECUTE、自报JSON|不能获得启动能力|
|gamma/lambda/alpha、seed、样本资格越界|闭合配置重验后拒绝|
|2025、错误年份、样本数或normalization改变|候选计划拒绝，文件守卫另禁2025|
|epoch>9、batch/accum/drop_last/LR horizon变化|拒绝，不自动修正|
|LAST/run/code/protocol/data/init身份错配|先绑定核验再拒绝|
|BEST、partial/train-only、更新数不完整|不能恢复|
|缺少独立LAST批准|FormalExecutionBlocked|
|只有批准reference字符串|未认证，仍拒绝；无state应用器|
|资源不足或完整GPU case失败|停止该测试/套件，不自动重试或降级|

复用既有review_checkpoint_binding，SHA字符串匹配不证明真实文件和批准事件。本轮未调用checkpoint_v2.verify_file/apply_verified，未打开BEST/LAST，未生成审批记录。

文件守卫拒绝raw、checkpoint、2025及非白名单CSV；白名单只含SHA绑定的精确公开元数据路径。操作守卫阻断step、torch.load/save、Module.load_state_dict和expm1。负面用例只检查人工路径，没有打开真实禁用文件。守卫属于独立测试进程，不能替代正式授权。

历史B1恢复仍NOT_GRANTED。SYNTHETIC_INTEGRATION_PASS与FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED明确分开，后者始终false。后续需要真实独立事件、验真及run/LAST绑定，不能将自报元数据升级为批准器。
""")
    write("FORMAL_INTEGRATION_DIFF_AND_GAPS.md","""# 正式集成差异与缺口

本轮只新增独立候选源码/测试/文档，没有应用正式路径补丁。后续应另建v2消融runner，旧v1 FinalFit不能冒充本入口。

|正式源码参考|当前隔离对应|获准集成还需实现|
|---|---|---|
|Contract.load|公开SHA检查|真实样本、年份/路径防火墙、scaler/mask/data身份|
|paired_initialization|三seed真实fresh摘要|正式run初态与源码/环境/RNG绑定、保留策略|
|forward_loss|合成适配器+既有candidate_loss|正式Batch接口与资格；不能用人工mask|
|update|仅backward诊断|另审optimizer、clip、scheduler、事务计数|
|epoch loop|纯endpoint_boundary|9epoch及逐epoch验证，无BEST替代终点|
|checkpoint_v2|声明身份负面检查|独立schema、完整epoch事务、immutable LAST和孤儿文件处置|
|authorization|永远阻断的BlockedRunner|独立批准验真及具体阶段绑定|

SyntheticBatch固定两个人工ID、人工mask和归一化数值，不能直接成为正式数据入口。真实尾batch1、验证batch8/尾batch5尚未验证；本轮未通过改batch制造完整矩阵通过。

另获授权的真实preflight：2023/2024读取、冻结真实mask/SP04配准、scaler应用、完整ID与时间因果性、staging及异常停止。2025继续封存。checkpoint耐久性、原子写入、中断故障注入、独立LAST恢复及长时资源需另审；非有限、缺监督、丢样本、源码/SHA漂移必须停止，不自动跳batch或历史恢复。

已有：闭合loss接口、双模型合成路径、真实fresh跨臂身份、数学预算和边界、负面证据。未有：正式runner、真实preflight、optimizer事务、checkpoint耐久性、长时稳定性、批准验真。缺口需要独立数据/资源和执行授权，不能填入合成结果。

科学待决：H-O/H-Q及E0/E1/E2最终接受、效应界限/副作用容忍、多重比较、2024开发验证解释范围、Phase-A接受及B1历史恢复独立处置。均为RESEARCHER_DECISION_REQUIRED。
""")
    write("RESEARCHER_REVIEW_CHECKLIST.md","""# 研究者审查清单（未批准）

本清单无签名、批准勾选或token。研究者已委托先实现后学习，最终科学决定仍独立发生。

1. 核对来源SHA与Git新增范围，确认正式模型/损失/入口及旧候选未改。
2. 理解B0末槽与B1时序、独立masks、float32阈值；人工3430布局不是真实地理资格。
3. 审查raw33到q32、三种精度、闭合get_config和两种评价分母。
4. 审查独立reseed、同名同形复制及两个B1原生张量；理解state与非持久SP04 buffer分别摘要。
5. 理解backward不等于更新、输出处lambda加倍不等于共享backbone总梯度加倍。
6. 审查E0容差与全参数梯度结果；不能据此接受校准、q32覆盖或物理性能。
7. 理解GPU冷启动、allocator和无optimizer限制；实际batch8、I/O、checkpoint未测。
8. 阅读4项首轮失败修复及旧XML格式限制；字符串和SHA不产生审批。
9. 独立决定候选科学协议、正式集成范围、真实preflight许可与阶段执行授权。
10. 独立处置Phase-A接受范围及B1历史恢复；2024仍为开发验证，2025封存。

安全接续：核对commit/SHA→研究者学习与代码审查→正式集成范围审批→独立v2 runner与获准preflight→绑定真实数据/初态/资源→再批准具体阶段执行。本轮在审批边界停止。
""")
    guide="""# 新增源码逐文件学习

先阅读上一轮[损失手册](../../phase_b_v2_ablation_implementation/v1/RESEARCHER_CODE_STUDY_GUIDE.md)。本轮顺序：synthetic→adapter→initialization→controls→resources/pins/safety→测试与工具。

## synthetic.py：人工张量与资格

SyntheticBatch是frozen dataclass，但Tensor内容仍可变，因此每次validate。x为FP32[2,1或6,501,501]；native_valid同形bool；rate为原FP32[2,1,100,100]，reference_valid/region_mask独立同形bool。输入/参考不要求梯度，模型参数需要梯度。

validate(kind)先核验scope、空data_years、两个人工ID、槽顺序，再检查shape/device/dtype/finite及3430有效监督。计数不能证明地理资格。to(device)用dataclasses.replace返回新batch，元数据保留。

make_synthetic_pair没有外部路径。arange/reshape/广播生成有限sin模式，clone使末槽成为独立Tensor。mask用<3430造人工布局；nextafter生成阈值上侧相邻值。练习：解释先double后比较0.1为什么可能改变边界，缺native像元为什么整场景拒绝。

## adapter.py：原输出到既有loss

forward_synthetic先验证batch/实验ID，检查exact模型类型、train模式、FP32参数与epsilon；autocast以BF16执行模型，原quantile头内部保留FP32 raw/FP64 q。函数返回output与loss，没有backward/optimizer。

loss_from_output检查LogDomainOutput、三个输出shape/device/finite、q守卫、概率support和sigmoid一致性，再调用已有candidate_loss。get_config决定唯一候选参数，科学CPB不乘lambda。练习：为何99×100不能自动resize为100×100。

## initialization.py：真实fresh与同形复制

seeded_environment是contextmanager：yield前固定随机源和确定性，finally恢复调用者；torch.random.fork_rng恢复Torch状态，Python/NumPy另存另还。进程hashseed保持2026，不伪称运行中修改环境变量可改变hash。

fresh_paired_models先过资源/SHA，再构造B0、重新seed构造B1。state_dict中的Tensor引用实际新参数，b[name].copy_(a[name])在no_grad中写入新初态，不是梯度优化。不同shape的两个输入权重before/after SHA必须相同，零skip保留。parameter_groups只分类计数，不构造AdamW。

state_digest包含dtype/shape/字节；state_dict不含非持久projection.indices，所以另摘要named_buffers。proof保存SHA和事实，不保存权重或批准。练习：同seed为何不能让不同输入通道的两模型天然拥有相同后续参数。

## controls.py：规则不是执行权

isolated_run_id重验RunSpec并加合成前缀。candidate_plan生成设计元数据；audit_plan比字段集合/类型/值，额外自报批准字段拒绝，合法仍can_launch=false。

synthetic_epoch_order用独立Generator(seed+epoch_index)，randperm不消耗全局模型随机流。endpoint_boundary是假想预算，不证明epoch实际完成；9之后next为None。

reject_resume复用旧身份检查后继续拒绝未认证批准；reject_formal_start调用永远抛错的BlockedRunner。练习：分别传True、APPROVED和dict观察为什么都不能启动。

## resources.py：构造前的资源检查

host_available_bytes读取Windows系统资源。resource_snapshot(full_backward)记录主机/磁盘，完整backward额外检查CUDA BF16和free/total；require_resources不足即抛ResourceLimit，不替调用者改参数。门槛不保证绝无OOM，其他进程可能改变资源。

## pins.py：来源身份

verify_frozen_sources先核验身份清单自身SHA，再读66个仓库公开文件字节；resolve/is_relative_to禁止外部路径。私有mask只声明未打开。SHA证明相同字节，不证明科学结论。

## safety.py：独立进程保护

reject_restricted_path拒绝raw/checkpoint/2025，CSV必须为绑定的精确仓库路径。install_process_file_guard安装sys.addaudithook监听open，先核验清单SHA再建立允许集。守卫不能在该测试进程撤销，退出进程即释放。

synthetic_operation_guards用ExitStack和patch临时把step、load/save/load_state_dict/expm1替为抛错函数，退出恢复。未构造optimizer来试step。Python仍可被外部代码改变，因此不是OS沙箱；正式权限须另行独立批准。

## __init__.py：scope标记

只有包说明与SCOPE常量；改变字符串不能让BlockedRunner获得训练循环。

## 测试与计算图

test_adapter_controls有86个CPU实例，覆盖完整目标接口、身份/shape/dtype/mask、候选越界、恢复/文件/资源拒绝。test_initialization有5例：3seed真实跨臂初态、顺序对照、SHA。test_cuda_e2e有6例完整模型，E0额外比较原loss全参数梯度。conftest限定CPU线程、安装守卫并独立写JSON。

autograd.grad(loss,(logit,qlog))检查输出处梯度；loss.backward沿完整图累积parameter.grad。retain_graph只用于E0二次反向对照，不是训练策略；zero_grad清梯度，不更新参数；detach只用于日志，objective保留计算图。

## 执行与交付脚本

run_checks启动有上限的子进程，append-only记录XML/log/JSON，无自动重试；test_process先过文件/资源门，CUDA首次失败停止。static_audit只读AST/SHA/结果，不import torch。build_delivery及export/close工具只处理文档和身份。

复现：项目CUDA Python运行scripts/phase_b_v2_isolated_integration/run_checks.py，指定--phase cpu或cuda、--attempt新编号。pytest复用上一轮私有依赖，不改项目环境。更换源码或依赖必须新测，旧PASS不自动继承。
"""
    index=[]
    for p in sorted(SOURCE.glob("*.py")):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
                index.append({"path":p.relative_to(REPO).as_posix(),"symbol":node.name,"line":node.lineno,
                              "end_line":node.end_lineno,"sha256":sha(p)})
    json_new("candidate_symbol_index.json",{"scope":"NEW_CANDIDATE_SOURCE","symbols":index})
    guide+="\n## 实际代码摘录\n\n完整实现见源码目录，下列摘录不作为第二份可导入实现。\n"
    fence=chr(96)*3
    for name,symbol in [("adapter.py","forward_synthetic"),("initialization.py","fresh_paired_models"),("controls.py","reject_resume")]:
        p=SOURCE/name
        node=next(n for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))) if isinstance(n,ast.FunctionDef) and n.name==symbol)
        start,end=node.lineno,node.end_lineno
        snippet="\n".join(p.read_text(encoding="utf-8").splitlines()[start-1:end])+"\n"
        guide+=f"\n### {name}：第{start}行起\n\nSHA256：{sha(p)}。\n\n"+fence+"python\n"+snippet+fence+"\n"
    write("MODULE_STUDY_GUIDE.md",guide)
    write("tests/README.md","""# 实际测试记录

当前cpu_attempt_002为91通过、cuda_attempt_002为6通过，均0失败/错误/跳过/warning；static_audit_001为15通过。唯一覆盖97，不加旧177/3或重复attempt。

cpu_attempt_001为87通过/4失败：公开CSV身份核验被过严守卫阻止，完整模型尚未构造；repair_001改为SHA清单绑定的精确路径白名单。cuda_attempt_001为6通过/1标量日志warning；repair_002使用detach并启用CUDA失败即停止；第二次6通过无warning。全部原始console私存.local，公开XML/log已脱敏，失败原因保留。

legacy_record_format_review记录上一轮失败XML既有未转义占位符问题，未重写历史；本轮在解析节点中脱敏并回读XML。

CPU最终初始化18个真实fresh模型实例，CUDA两次各构造6对模型，共24实例；合计42实例，无权重保存。完整模型累计12forward/16backward，最终矩阵6/8。CPU输出张量backward另计。没有OOM、超时或降级，没有真实数据、checkpoint或step。

资源与原始完整日志保留。raw/2025/step为0描述本轮受控调用图，不能把Python守卫当操作系统安全沙箱。
""")
    spec=importlib.util.spec_from_file_location("prior_author",REPO/"scripts/phase_b_v2_ablation_implementation/author_delivery.py")
    author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author)
    header=r"""\documentclass[UTF8,fontset=fandol,10pt]{ctexart}
\usepackage[a4paper,margin=20mm]{geometry}
\usepackage{amsmath,amssymb,array,longtable,booktabs,url,listings,xcolor,fancyhdr}
\usepackage[colorlinks=true,linkcolor=blue,urlcolor=blue]{hyperref}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{YunTAPR-Net / synthetic integration}
\fancyhead[R]{2026-10-10 / v1}\fancyfoot[C]{\thepage}\setlength{\headheight}{14pt}
\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}\setlength{\emergencystretch}{4em}
\lstset{language=Python,basicstyle=\ttfamily\scriptsize,columns=fullflexible,breaklines=true,
breakatwhitespace=false,numbers=left,numberstyle=\tiny,numbersep=5pt,xleftmargin=8pt,
frame=single,keepspaces=true,showstringspaces=false,tabsize=4}
\title{YunTAPR-Net\\Phase-B v2 隔离集成\\合成端到端验证与研究者学习材料}
\author{SYNTHETIC\_ENGINEERING\_ONLY}\date{2026年10月10日 / v1}
\begin{document}\maketitle
\textbf{真实模型架构的合成工程集成通过；正式科学执行未授权。}

当前CPU91 / CUDA6 / 静态15项通过；完整双模型batch2、501×501、BF16/FP32/FP64。
没有optimizer更新、真实观测或私有checkpoint访问。人工mask不是云南地理掩膜。
\setcounter{tocdepth}{1}\begingroup\small\setlength{\parskip}{0pt}\tableofcontents\endgroup
"""
    body="\n".join(author.with_code_blocks((OUT/name).read_text(encoding="utf-8")) for name in DOCS)
    formulas=r"""
\clearpage\section{接口中的关键数学}
\[
 x_{\rm B0}=x_{\rm B1}[:,5:6,:,:],\quad
 x_{\rm B1}\in\mathbb R^{2\times6\times501\times501},\quad
 q_{\log}\in\mathbb R^{2\times32\times100\times100}.
\]
\[
 v=m_{\rm reference}\land m_{\rm artificial},\quad
 z=\mathbf1\{y_{32}>\mathrm{float32}(0.1)\},\quad N_v=\sum v,\quad N_r=\sum vz.
\]
\[
 L=\frac{S_{\rm occ}+\lambda_q S_{\rm qr}}{N_v},\qquad
 \mathrm{CPB}_{\rm synthetic}=\frac{S_{\rm qr}}{N_r}.
\]
\[
 \frac{\partial L_{\rm E2}}{\partial q_{\log}}=2\frac{\partial L_{\rm E0}}{\partial q_{\log}},
 \qquad \frac{\partial L_{\rm E2}}{\partial l}=\frac{\partial L_{\rm E0}}{\partial l}.
\]
这些关系针对同一输出与参考，不能把共享backbone总梯度整体乘2。输出处梯度与完整参数梯度分别检查。
\[
 \pi_{s,e}=\operatorname{randperm}(n;\operatorname{Generator}(s+e)),\quad e=0,\ldots,8.
\]
\[
 U_{\rm run}=9\lceil10455/2\rceil=47052,\qquad U_{\rm all}=18U_{\rm run}=846936.
\]
以上是候选预算，原50epoch学习率轨迹不变；epoch9后不产生下一个候选epoch，实际正式更新为0。

模型分位数参数化来自冻结quantile\_v2源码；loss数学复用上一轮，均由本版source\_identity与源码索引绑定。
\end{document}
"""
    write("ISOLATED_INTEGRATION_REVIEW.tex",header+body+formulas)
    json_new("report_source_binding.json",{"source_markdown":[{"path":n,"sha256":sha(OUT/n)} for n in DOCS],
        "tex_sha256":sha(OUT/"ISOLATED_INTEGRATION_REVIEW.tex"),"candidate_modules":[
            {"path":p.relative_to(REPO).as_posix(),"sha256":sha(p)} for p in sorted(SOURCE.glob("*.py"))],
        "scope":"SYNTHETIC_ENGINEERING_ONLY","baseline_commit":BASELINE})
    print(json.dumps({"main_markdown_documents":10,"candidate_symbols":len(index),"tex_written":True}))


if __name__=="__main__":
    main()
