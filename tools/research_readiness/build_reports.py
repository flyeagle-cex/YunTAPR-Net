"""Render Chinese review documents from receipts; no plots or training."""
from pathlib import Path
import argparse
import csv
import datetime
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'docs/research_readiness/20261025'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(name, text):
    with (OUT/name).open('x', encoding='utf-8', newline='\n') as f:
        f.write(text.strip()+'\n')


def table(head, rows):
    return '\n'.join(['|'+'|'.join(head)+'|', '|'+'|'.join(['---']*len(head))+'|']+
                     ['|'+'|'.join(str(x) for x in row)+'|' for row in rows])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--proposal', type=Path, required=True)
    a = p.parse_args()
    proposal = load(a.proposal)
    budget = proposal['budget']
    public = ROOT/'docs/research_progress'
    records = load(public/'evidence/experiments.json')['experiments']
    groups = load(public/'evidence/seed2029_groups.json')
    b3, b4 = [groups[m]['all']['summary'] for m in ('B3', 'B4')]
    audit = load(OUT/'evidence/state_audit.json')
    gpu = load(OUT/'evidence/b2_gpu_probe.json')
    metrics = [('brier', 'Brier Score（布里尔分数）'), ('auroc', 'AUROC（ROC 曲线下面积）'),
               ('average_precision', 'AP（平均精确率）'), ('conditional_pinball', 'Conditional Pinball（条件分位数损失）'),
               ('q32_coverage', 'q32 Coverage（最高分位数覆盖率）')]
    result_table = table(['指标', 'B3 seed2029', 'B4 seed2029', 'B4−B3'],
                         [[label, f'{b3[k]:.12g}', f'{b4[k]:.12g}', f'{b4[k]-b3[k]:.12g}'] for k,label in metrics])
    qrows = list(csv.DictReader((public/'quantile_calibration.csv').open(encoding='utf-8')))
    qtable = table(['分位数', '名义覆盖', 'B3 覆盖', 'B4 覆盖'],
        [[f'q{i}', f'{(i-.5)/32:.6%}', *[f"{float(next(r['coverage'] for r in qrows if r['experiment_id']==f'{m}__E0__s2029__f006' and int(r['index'])==i)):.6%}" for m in ('B3','B4')]] for i in (8,16,24,32)])
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
    common = f"""核查时间：{now}（北京时间）。研究者为主体，AI 仅辅助核查和实现。本文文件已生成，不代表正式实验或科学验收完成。

本轮授权范围：用户明确确认历史 B3/B4 seed2029 和获批重放不能授权本轮 B2 或新 seed；本轮只做核查、方案、预算和合成测试。正式训练更新=0，原始气象数据读取=0，checkpoint（检查点）反序列化=0。另对两份旧 LAST 权重读取文件字节计算 SHA256，未做推理。

2025最终测试期继续冻结：本轮不读取其原始载荷、不推理、不调参或探索性选模；历史catalogue/QC访问事实单独保留。

版本：GitHub main=`6c505d0ec63ed39f679720b82a65f601139dcd35`；本地代码基线=`0ccb3e26e2d50494aba07788fa94dd40ec89b4aa`；seed2029 恢复执行=`7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35`，首次准备=`5b5298f41025db5b7b718fd736fc3fe6de516875`。本轮最终代码提交见交付消息及 Git 历史；可执行文件 SHA 绑定在最终提案和 `DELIVERY_MANIFEST.json`，不在文档内编造自引用提交。

证据入口：[本轮本机状态](evidence/state_audit.json)、[重新读取129个原件来源的清单](rechecked_snapshot/evidence/source_manifest.json)、[原公开证据边界](../../research_progress/EVIDENCE_INDEX.md)。两次独立摘录的22个实验及126轮数值须相同；核查不等于重跑模型。"""

    write('B2_TRAINING_AND_EVALUATION_REPORT.md', f"""
# B2 七通道单时次训练与配对评价报告

**正式训练：NOT_STARTED；B2/B3 配对结果：NOT_VERIFIED；准备工作：已完成可复核候选，等待研究者审查。**

{common}

## 已恢复的真实状态

本机检查17个 Git 工作区、103个指定输出范围内的 checkpoint 文件条目；已有未提交运行记录保留原状。状态快照中匹配的 Python/训练/WSL/SSH 进程为 {audit['matching_process_count']}；只代表本机观测时刻。未发现比 seed2029 更晚的 B2 或其他 B3/B4 seed 完整收据；不宣称遍历所有主机或全部磁盘。

B0/B1：seed2026、2027 的 E0/E1/E2 共12组正式九轮配对结果；B3/B4：seed2029/E0/f006 各九轮。B2 原来只有7通道接口；本轮新增候选初始化、输入适配和带授权门控的执行器。执行器真实数据完整链路仍为 NOT_VERIFIED，不把候选代码测试写成正式完成。

B3/B4 的第九轮权重文件已重新哈希：B3=`c7780bc6e45992639c90339c88553fe3a722f6d9681bd247a82ad2dce0c08283`；B4=`7c74eb80ab7d754e3262781d85ac370b2319c3bf27d37ac362860c104acfb34d`。完成判据还包括18轮 Train/Dev/LAST 绑定及只读更新账本；累计9,120次历史返回中，8,640次保留、480次获批重放。重放不是独立 seed。

## 待审的公平比较协议

|项目|B2 预案及与 B3 的关系|
|---|---|
|数据人口|固定2023 Train=959、2024 Development（开发集）=963；f006、3–10月、00/06/12/18 UTC；完全继承六帧七通道共同 QC（质量控制）资格|
|人口版本|`{proposal['data']['population_sha256']}`；populations 文件 SHA=`{proposal['data']['populations_sha256']}`|
|统计版本|`{proposal['data']['statistics_sha256']}`；标签 QC SHA=`{proposal['data']['target_QC_sha256']}`|
|输入|B08/B09/B10/B11/B13/B15/B16；建议选择 analysis−10分钟的最后一帧（slot5）；B2为7×501×501，B3为42×501×501|
|标签与时序|沿用分析时刻结束的半小时 IMERG Final V07 标签；六帧位于分析前60/50/40/30/20/10分钟；属于 retrospective（回顾估计），不声称业务近实时|
|归一化|所有通道仅来自2023 Train；六个新增通道使用959场景×6槽位统计；B13继承旧2023训练冻结统计，未在959人口重拟合。不能写成七个通道均由本次959样本重新拟合|
|损失与终点|E0不变、32个冻结条件分位数、九轮固定第九轮 LAST；不选 BEST，不调上尾损失|
|优化器|AdamW：lr=1e−4、betas=(0.9,0.999)、eps=1e−8；仅Conv2d核weight decay=1e−4，其余偏置/GN仿射=0；全局梯度范数上限5|
|学习率|首480步线性warmup（预热）；保持50轮/24,000步余弦原轨迹的前4,320步，不把学习率压缩到九轮归零|
|batch与更新|Train batch=2，最后一批1场景，每轮480步；Dev batch=8，每轮121批；4,320步，无重放额度|
|随机性|seed=2029；Python/NumPy/PyTorch/CUDA、确定性算法、禁TF32、禁cuDNN benchmark；BF16 autocast（混合精度）与原分位数高精度参数化一致|
|顺序与评价|全部九轮样本顺序已与历史B3逐项相同；目标SP04映射、3430云南有效像元/场景、发生事件float32(rate)>float32(0.1 mm/h)、精确分数AUROC/AP保持不变|

初始化是待研究者冻结的核心条目：先按历史 seed2029 构造全新 B3，实际复现其初始化 SHA=`{proposal['input_dimension_difference']['b3_reference_sha256']}`，再复制72个形状兼容张量给 B2。输入层两组核从42维变为7维，候选取最后槽位并乘sqrt(6)校正fan-in（输入连接数）方差；skip核原本为零。其余兼容张量逐位相同。B2参数4,332,290，比B3少16,800；不能声称两模型参数量或首层完全一致。此映射不是既定科研决策，只有批准 `{proposal['config']['stem_rule']}` 后才可执行；若研究者选择另一初始化，必须重新生成提案及收据。

缺测与泄漏检查：Train/Dev ID不相交；清单年份和月份、每个槽位偏移、obs_end≤analysis均通过元数据检查。B2仍拒绝任一历史槽位/通道无效或非有限的样本，不因只消费最后一帧扩大人口。现加载器沿用六帧和GFS读取，B2 forward（前向计算）仅接收最后7通道，不向B2输入GFS。输入维数改变会改变算子计算，确定性仅约束各模型在固定环境中的复现，不能声称B2/B3逐步数值轨迹相同。历史GFS实际发布时刻和完整转换链仍不足，故近实时无泄漏声明为 NOT_VERIFIED。真实载荷完整性沿用已有QC，未用本轮元数据检查替代全量重验。

## 代码、验证与可执行入口

新增 `src/yuntapr/experimental/research_readiness/b2.py`、`b2_runner.py`；旧B3/B4执行代码保持不变。`tools/research_readiness/prepare_b2.py`仅读清单/统计/只读SQLite，拒绝打开原始气象文件及权重；生成提案、逐源预算与本机私有准备绑定。`tools/research_readiness/train_b2.py`默认拒绝执行，须明确--execute、研究者批准文件、精确提交/提案SHA及额度。历史授权、占位符或False模板均不能通过。逐步INTENT/RETURNED账本阻止未确认更新重试；遇额度、数据SHA、掩膜、样本顺序或数值异常即停止，保留失败与历史权重。

本轮新增检查覆盖：首层映射与共同初始化、最后槽位/通道序、未消费帧缺测拒绝、授权拒绝、更新上限与不确定状态、配对人口/掩膜漂移拒绝。已用历史CUDA环境跑合成B2前向/反向和验证，未构造优化器。真实全量训练、恢复及模型评价属于 NOT_STARTED/NOT_VERIFIED。

合成显存：Train batch2峰值allocated（分配）={gpu['modes']['train_batch2']['peak_allocated_bytes']/1024**3:.3f} GiB，reserved（保留）={gpu['modes']['train_batch2']['peak_reserved_bytes']/1024**3:.3f} GiB；Dev batch8分别为{gpu['modes']['validation_batch8']['peak_allocated_bytes']/1024**3:.3f}/{gpu['modes']['validation_batch8']['peak_reserved_bytes']/1024**3:.3f} GiB。AdamW两份动量另按参数量计算约33.1 MiB；未实际分配，不作为正式峰值证明。详见[GPU收据](evidence/b2_gpu_probe.json)。环境：Python3.12.14、PyTorch2.11.0+cu128、CUDA12.8、RTX5060 Laptop 8GiB。

## 待批准资源额度

{table(['资源', 'B2单次九轮预案'], [
 ['优化器更新上限', '4,320；replay=0'],
 ['Train/Dev源遍历', '各9次，共18次'],
 ['源读取实例', f"{budget['logical_source_read_instances']:,}"],
 ['逻辑源字节', f"{budget['logical_source_bytes']:,} bytes（约477.572 GB）"],
 ['Train/Dev单次源字节', '26,424,262,556 / 26,639,253,112 bytes'],
 ['IMERG缓存上限', '512 MiB；两年唯一日文件合计374,860,979 bytes'],
 ['九份LAST张量理论下限', f"{budget['nine_LAST_tensor_bytes_lower_bound']:,} bytes，另有序列化/RNG等开销"],
 ['评价数据库理论上限', '每组256 MiB ×6组×9轮=13.5 GiB，非实际消耗'],
 ['磁盘预留提案', 'B2新输出预留20 GiB，启动前至少24 GiB空闲；不自动清理旧文件'],
 ['GPU/主机入场', '至少5 GiB空闲GPU、8 GiB空闲RAM、2 GiB可用系统commit，执行时重新检查'],
 ['建议运行时间上限', '6小时/单模型，待研究者批准；不是已测耗时或费用报价']])}

这是保守加载器预算，含B2未消费的历史帧/GFS读取；不擅自更改数据流水线省预算。源字节为Python实际接收载荷，不是磁盘扇区流量；不含元数据、checkpoint及评价数据库I/O，不包含另做源验证、重放、归一化重拟合或额外终点评价。历史B4九轮的文件修改时间跨度约3小时51分，仅作本机调度参考，不是严格GPU计时或计费证据。单次冷启动合成耗时不能换算正式总耗时。

## B2/B3 配对评价结果

{table(['指标', 'B2', '历史B3 seed2029', 'B2−B3'], [[label,'NOT_STARTED',f'{b3[k]:.12g}','NOT_VERIFIED'] for k,label in metrics])}

**当前没有B2实验结果，无法交付有效的B2/B3数值比较。** 表内B3来自真实第九轮Dev收据，不能充当B2。未来获批完成后，执行器用同人口、同分组、同掩膜的B2 E9收据与历史B3 E9计算差值；不得改换最佳轮。

最终可复核提案：[{a.proposal.name}](evidence/{a.proposal.name})；[授权模板（False）](B2_RESEARCHER_APPROVAL_TEMPLATE.json)；[最小运行说明](RUNBOOK.md)。
""")

    write('B3_B4_MULTI_SEED_PLAN.md', f"""
# B3/B4 多随机种子复现与上尾诊断方案

**总体多seed验收：IN_PROGRESS；新seed正式训练：NOT_STARTED；创新与物理机制：NOT_VERIFIED。**

{common}

## 有效独立seed和拟补齐任务

|seed|B3|B4|是否计入至少3个seed|
|---|---|---|---|
|2029|E0/f006/九轮及Dev完成|同左|计入1个；失败原段及获批重放不重复计数|
|2030（建议）|NOT_STARTED|NOT_STARTED|研究者确认种子、配置和额度后才可计入|
|2031（建议）|NOT_STARTED|NOT_STARTED|同上|
|2026/2027|只有另一人口的B0/B1证据|无本B3/B4完整证据|不计入|
|2028|仅有其他准备记录|未找到本对照完整证据|不计入|

不重训seed2029。建议按seed2030的B3→B4、再seed2031的B3→B4顺序串行，防止资源并发及额外数据遍历。种子编号是待审提案，不是批准事实。旧 `tools/core_stage4/start_pair.py` 对seed2029硬编码，不可直接改CLI参数冒充新seed；未来新启动器须沿用现有 `FormalDecision`/`PairedExecutor`，外置新seed并绑定独立授权、账本、代码SHA与逐源范围。本轮未把旧启动器改成可任意启动新训练的通道。

## 必须保持的条件

数据人口/统计/标签QC SHA与B2报告完全一致；2023 Train=959、2024 Dev=963；E0、固定f006、13变量MEE（气象环境编码器）、width16、目标SP04 residual（残差）融合、batch2/Dev8、九轮LAST及24,000步原学习率轨迹保持不变。B3/B4每个seed共享backbone（骨干）和heads（输出头）初始化、九轮样本顺序及评价掩膜；跨seed改变初始化和排列。固定32个τ及float32发生阈值，拒绝2025参与训练、调参、分层选择或探索性推理。

Brier使用全部3,303,090个有效场景像元暴露；条件Pinball和q32用407,820个真实雨暴露，量纲为log1p(mm/h)及比例。AUROC/AP必须保留精确并列分数口径，不能用直方图近似或平均逐批AUC替代。零正例/负例分层须标明NOT_ESTIMABLE（不可估计），不得填零。

## seed2029已有结果及反例

{result_table}

q32名义覆盖98.4375%；B3/B4分别差−4.932522/−4.814823个百分点。B4只增加480个covered（已覆盖）雨像元暴露，未解决校准。06 UTC的Brier反而略差，00/18 UTC的q32覆盖下降。

|真实雨强 mm/h|暴露数|B3条件Pinball|B4条件Pinball|解释|
|---|---|---|---|---|
|(20,30]|564|0.828964147280|0.832683392534|未改善|
|(30,50]|147|0.983911312638|0.986955237662|未改善|
|(50,∞)|6|1.38471581132|1.35019753512|样本极少，不能外推极端事件能力|

20–50 mm/h合计711个相关像元暴露，占真实雨暴露约0.1743%，不是711场独立暴雨。总体改善容易由弱雨和常见条件主导；这一比例与损失平均方式构成待检验解释，不能证明GFS融合的因果缺陷。当前缺少这些真实雨强层的q32 covered计数，不从总体覆盖率推导分层覆盖率。

{qtable}

q8/q16/q24覆盖偏高而q32偏低，与条件分布离散度偏窄相容；它不是所有分位数一致向下的简单证据，也不能单凭边际校准表定位模块机制。九轮q32仍明显波动：第8→9轮B3约95.2925%→93.5050%，B4约95.2648%→93.6227%。继续固定第9轮，不能事后选第8轮修饰结论。

## 统计汇总与验收规则（待研究者冻结）

逐seed保存B4−B3的Brier、AUROC、AP、条件Pinball及q32有符号覆盖差；报告三seed均值、样本标准差、每个seed方向和原始数值，不只报最优seed。q32另报相对0.984375的偏差及绝对误差。

同一2024开发年多seed仅检验训练随机性，不能充当独立天气年份。沿用35个既有周区块做配对区块重采样，两模型使用同一重采样和像元掩膜；必要时再对seed层重采样。AUROC/AP须按区块乘数汇总精确分数重新计算，不能平均区块AUC/AP。三seed的不确定性估计很不稳定，应明确其探索性，不擅加显著性结论或像元独立性假设。

预先展示全部UTC分组、七个真实雨强层、总体及强雨场景分组，不事后筛层。以真实雨强定义20–30/30–50层并保存n_rain、q32_covered、pinball_sum、q32短缺log和场景ID；新增 `tail_diagnostics.py` 已有边界、缺测和覆盖率充分量合成测试，B2候选已接入。未来B3/B4新启动器仍须接入同一附加统计，保持原评价脚本为主。地形分层只有在DEM及海拔边界冻结后才使用。

本轮不给出“多seed通过”或统一性能改善门槛：研究者需预注册可接受的总体变化、校准容差与强雨退化容忍度。若seed方向冲突，报告不稳定并分析，不能自动追加seed直到结论满意。

## 诊断与预算拆分

优先复现既定E0，不把上尾加权、后校准或更长训练混入多seed。可讨论的最小后续假设为固定高τ权重；需独立授权与对照，不能用真实雨强权重改变目标分布后仍声称原条件分位数。DOTE/DTFM不能被当成已证实的校准解法。

|待审包|新增模型数|更新上限|源读取实例|逻辑源字节|建议串行时间额度|
|---|---|---|---|---|---|
|seed2030 B3/B4|2|8,640|285,624|955,143,282,024|每模型6小时，共12小时|
|seed2031 B3/B4|2|8,640|285,624|955,143,282,024|同左|
|两新seed合计|4|17,280|571,248|1,910,286,564,048|24小时|
|加B2后的总待审包|5|21,600|714,060|2,387,858,205,060|30小时|

所有额度状态为PROPOSED_NOT_AUTHORIZED。每模型4,320步；不得把四模型误算成34,560步。历史seed2029的9,120次累计返回不占本次“新增”上限，也不能提供可挪用余额。重放/重试额度均为0。每模型建议24GiB可用工作空间，五模型全保留按120GiB预留规划；当前C盘约{gpu['admission']['workspace_free_bytes']/1024**3:.1f}GiB空闲只说明B2单次具备空间，不能据此认定整体留存预算已满足。不自动清理或迁移原件。

可选的旧seed2029上尾补评估包：B3/B4 E9各一遍Dev，0更新、15,900源读取实例、53,278,506,224逻辑源字节，另加载两份旧checkpoint；只新增真实雨强q32/场景充分量并校对原总体值，不改变选模。它不包含在上述五模型训练包中，状态NOT_STARTED，需单独确认。已有元数据无法替代这项真实推理。
""")

    write('B0_B4_STAGE_ACCEPTANCE.md', f"""
# B0–B4 Stage 2–3 科学验收

**总体科学验收：IN_PROGRESS，尚未满足B0–B4完整科研验证；2025最终模型测试：NOT_STARTED。**

{common}

## 按模型验收

|模型|代码|正式训练|独立seed|Dev可靠性与局限|科学结论与进入下一阶段条件|
|---|---|---|---|---|---|
|B0|已有冻结实现|2026/2027各E0/E1/E2九轮|2；损失臂/恢复/Phase-A不另计|相同10,455/10,501人口；有逐轮收据与终点，旧治理不确定尝试保留|可作当前B0/B1对照；若统一要求≥3seed，仍缺第3seed；不能声称最终泛化|
|B1|已有六时次实现|与B0配对完成12组中的6组|2|与各臂B0一致；q32改善不一致|总体概率识别和条件Pinball方向重复改善；全雨强/上尾优势未证明|
|B2|7通道单时次接口；本轮增加待审执行候选|NOT_STARTED|0|NOT_VERIFIED|须批准协议/预算，完成九轮Train/Dev/LAST并与B3配对；仅建文件不通过|
|B3|7通道×6时次实现完整|seed2029 E0/f006九轮|1有效；多seed不足|959/963人口、精确分数评价与18轮配对绑定可核对|可作当前MEE增益对照；需至少3个独立seed及上尾诊断|
|B4|MEE13/width16/SP04残差已执行|seed2029同协议九轮|1有效；多seed不足|总体4项改善但强雨、06UTC及q32有反例|单seed有限结论成立；不满足全链科学验收，不据此启动B5–B8|

“代码完整”只针对所列模型的已执行/候选范围，不证明论文全部机制已实现。52项原接口及20项Stage2旧测试是历史工程证据，本轮只重跑相关地形/网格/边界并新增候选检查。局部单元测试通过不等于科学验收。

## 人口与比较关系

|比较|Train/Dev|允许的解释|
|---|---|---|
|B0 vs B1，同seed、同E臂|10,455/10,501|相同人口下单通道时间信息增量；两个seed方向重复|
|B3 vs B4，seed2029/E0/f006|959/963|相同人口、共同初始化/训练顺序下MEE增量；只限单seed与四UTC时次|
|B2 vs B3，拟seed2029|959/963|尚无B2结果；须保留首层维度和参数数目不同的限制|
|旧B1 vs B3/B4|不同|禁止直接排序为架构或七通道增益；不得用旧B1充当B2|
|E0 vs E1 vs E2|人口可相同，损失目标不同|须明确损失臂；训练loss不能直接同口径比较|
|Phase-A BEST/旧FinalFit vs 固定九轮V2|版本、训练人口、轮数或选择规则不同|单独列示历史，不能算额外seed或当成当前固定九轮终点|

全矩阵见[B0_B4_EXPERIMENT_MATRIX.csv](B0_B4_EXPERIMENT_MATRIX.csv)：保留22条原历史记录，增加B2及4条待审多seed行，不把未训练项标成完成。旧B0 FinalFit十一轮训练完成与旧B0-Matched FinalFit第五轮溢出失败均按原状态保留。

逐行另列源码快照、执行commit绑定状态、数据版本、评价脚本与源SHA清单。B0/B1各结果原JSON本身未直接给出执行commit，本轮标记NOT_VERIFIED_EXECUTION_COMMIT_BINDING；可核对的0ccb3e是源码/证据快照，不能冒充历史执行提交。B3保留轨迹E1–3来自5b5298首次段、E4–9来自7fa609恢复段；B4全九轮来自7fa609恢复段。当前核心评价脚本为 `src/yuntapr/experimental/core_innovation/stage4/evaluation.py`，其中精确数值口径继承 `src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py`。未核实的历史脚本绑定逐行保留NOT_VERIFIED。

即使把旧B0/B1只在963场景上重评价，训练人口仍不同，不能补出完整公平架构阶梯。如研究者要求B0→B4全部同人口的架构归因，应另行预注册小人口B0/B1训练对照及预算；本轮不扩大到这些任务。B0/B1目前两个seed是否满足其单项验收，交由研究者按预注册标准决定，不替研究者降低门槛。

## 结果支持与否证边界

{result_table}

支持：当前开发集单seed的总体环境融合增益，以及另一人口B0/B1两seed的总体方向重复。尚不支持：20–50mm/h改善、q32校准通过、B4全面优于B3、全天业务近实时、多seed B3/B4已复现、DOTE/DTFM有效或物理机制成立。

原件复核没有修复历史授权缺口：seed2027账本1次历史未核验尝试及旧恢复治理问题继续保留。checkpoint存在不作为完成判据；训练/开发逐轮、更新账本、源读取与LAST绑定须同时成立。哈希只约束文件身份，不证明未公开数据本身真实无误。

## Stage 2–3门槛与后续边界

1. B2完成获批固定协议训练与配对评价，且不扩大/漂移人口。
2. B3/B4至少3个独立seed，全部预定指标和反例展示；研究者冻结校准、强雨和总体容差，不事后补seed选结论。
3. 记录强雨q32充分量、真实暴雨事件独立性限制与开发集反复使用影响；仍不能替代最终测试。
4. B5/B6须冻结DEM source/grid/footprint/聚合顺序/全云南有效掩膜/统计及融合位置；DOTE的PWAT尺度、850/700层规则和DTFM尺度/边界等仍待科学决定。
5. 2025属于冻结最终测试期；本轮未进入2025原始数据目录或读取载荷、未做模型forward、调参、探索性选模。历史2025 catalogue/QC读过载荷的事实保留，不能写成历史从未访问2025；全模态最终测试输入完整性仍NOT_VERIFIED。未来解封须独立协议/授权。

当前只允许继续未额外授权的准备和审查；本报告不能作为B5–B8启动许可。
""")

    write('B5_B6_READINESS_REPORT.md', f"""
# B5/B6 地形特征与代码就绪审计

**候选代码：IN_PROGRESS（相关合成检查通过）；生产DEM/参数冻结：NOT_VERIFIED；正式训练：NOT_STARTED。**

{common}

## 已有证据与本轮检查

旧SRTM审计记录237 tiles（瓦片）、云南覆盖FULL及真实小窗口梯度；本轮仅复核旧记录，未打开原始DEM。不能以瓦片几何覆盖FULL推导生产聚合后3430个云南监督格点全部具有有效梯度。

沿用 `core_innovation/terrain.py`：WGS84椭球东/北米制距离，支持纬/经轴反向与非均匀间距；高程m，梯度m/m，坡度degree；坡向为顺时针自北的下坡方向。三点导数需要中心及东西南北有效邻居，边界无效，须先读halo（外扩边界）再计算/裁切。平坦区坡向未定义，不能当成朝北。投影先映射东/北梯度分量再求坡向，禁止普通平均359°与1°。

旧 `stage3/terrain_boundary.py` 的东西共享边界拼接已重测；本轮新增有界南北halo拼接候选，重复边界仅保留一次，掩膜或高程不一致即拒绝，不做接缝平均或推断修补。单次候选join≤65,536格点。合成HGT/ZIP读取测试只读自建fixture（测试样本），不是原始SRTM访问。

## 待审静态输入协议

|模型|静态通道候选|有效性与单位|
|---|---|---|
|B5|elevation_m（海拔）|m；云南监督区域须全部高程有效|
|B6|海拔、east_gradient（向东梯度）、north_gradient（向北梯度）、slope_degrees（坡度）、aspect_sin/aspect_cos（坡向正余弦）|m、m/m、m/m、degree、1、1；梯度/坡度须全云南有效，平坦坡向保留独立无效掩膜|

`pack_terrain`要求显式源SHA、网格SHA和aggregation_rule（聚合规则），不隐藏flip/resize/nearest-fill（翻转/缩放/最近邻填补），拒绝云南内部高程/梯度空洞；不改变原监督掩膜或缩减共同人口。经纬格点须与冻结SP04目标网格精确一致，不凭100×100尺寸猜网格。mask输入必须是对齐的独立bool数组。

静态统计候选仅在2023 Train的空间支持上拟合，每个独特格点计一次，不重复959遍，使用总体方差；常数通道std=1并显式标识，非有限/零有效样本拒绝。DEM虽然无年份变化，仍不使用2024/2025标签或降水结果选特征。B6使用坡向正余弦及缺测指示，禁止把缺测零值解释为物理观测。

## 接入代码候选

新增 `src/yuntapr/experimental/research_readiness/static_terrain.py` 的 `StaticTerrainCandidate`：继承全新B4全部骨干、概率头和MEE13，在目标SP04特征处加独立静态残差适配器；输入为静态值和逐通道valid（有效性）指示，建议width16。输出卷积零初始化，因此合成测试中B5/B6初始输出与真实B4逐位一致。新增参数候选B5=3,440、B6=4,880，须在正式配置冻结时重新核对；无法将附加参数与物理信息增量自动等同。

本轮已检验真实501×501骨干→SP04→概率头的B4/B5/B6零残差输出一致性，以及静态分支有限梯度；没有降水训练或有效性结果。输入特征集合、width16与目标残差位置均为PROPOSED（待审），未替代科研方案核心决策。不添加B5/B6训练启动器，不启动B5–B8。

## 尚未满足的生产与科学条件

|项目|状态与必须补齐内容|
|---|---|
|DEM来源/垂直基准|NOT_VERIFIED；冻结237瓦片实际版本SHA、垂直基准、void处理，不从HGT格式自行推定|
|原始瓦片拼接|部分接口/合成测试通过；全云南接缝、重复边界、外扩范围和真实生产收据仍未完成|
|footprint（聚合覆盖范围）|NOT_VERIFIED；0.02°与0.10°、25格SP04对应关系须研究者决定，不把双线性点插值说成面积平均|
|运算顺序|NOT_VERIFIED；native米制导数后聚合，与先聚合高程再求导数不等价；保存两者选择及理由|
|全云南有效性|NOT_VERIFIED；须对3430监督格点逐项证明高程/梯度有效并记录源/网格/掩膜SHA，不得静默缩小评价人口|
|静态统计与正式接入|候选通过合成检查；真实全域产物、Train-only统计和独立可重现生产命令尚缺|
|B5/B6科研证据|NOT_STARTED；多seed正式训练、配对Dev、海拔分层、地形效应机制均未完成|
|DOTE/DTFM|保留候选；PWAT参考/耦合基底、层选择、调制插入尺度及上界尚待冻结，无本轮训练授权|

下一步由研究者先审查静态通道、footprint、导数聚合顺序和融合位置，再申请有界真实DEM生产检查及单独额度。本轮没有因此自动读取新DEM，也不把合成mask称为云南生产mask。

## 单元检查收据与范围

见[tests/](tests/)中的逐次summary及public.log。涵盖米制尺度/方向/非均匀网格、nodata（缺测）传播、平坦坡向、边界halo、东西/南北接缝、网格移位拒绝、全云南候选掩膜不缩减、Train-only静态统计、零残差身份及梯度。初次默认Python缺PyYAML的失败记录和切换既有环境的修正已保留；没有安装依赖。工程检查只支持上述性质，不支持地形增益或上尾校准结论。
""")

    # Keep history and pending experiments distinct in one inspectable matrix.
    with (public/'EXPERIMENT_MATRIX.csv').open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)+['authorization_status', 'comparison_population', 'protocol_reference',
            'source_snapshot_commit','executed_commit','data_version','evaluation_script','source_manifest_reference']
        matrix = []
        for row in reader:
            row.update(authorization_status='HISTORICAL_RECORD_NOT_NEW_GRANT',
                       comparison_population='CORE_F006_959_963' if row['model_id'] in ('B3','B4') else 'LEGACY_OR_B13_POPULATION_SEE_ROW',
                       protocol_reference='../../research_progress/EVIDENCE_INDEX.md',
                       source_snapshot_commit='0ccb3e26e2d50494aba07788fa94dd40ec89b4aa',
                       executed_commit=('5b5298f41025db5b7b718fd736fc3fe6de516875_E1_3;7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35_E4_9' if row['model_id']=='B3' and 'original_failed_segment' not in row['experiment_id'] else
                                        '5b5298f41025db5b7b718fd736fc3fe6de516875' if row['model_id']=='B3' else
                                        '7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35' if row['model_id']=='B4' else 'NOT_VERIFIED_EXECUTION_COMMIT_BINDING'),
                       data_version=(proposal['data']['population_sha256']+';statistics='+proposal['data']['statistics_sha256'] if row['model_id'] in ('B3','B4') else
                                     'B13_V2_M1_10455_10501_SCALER_656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31' if row['phase']=='PHASE_B_V2' else 'LEGACY_SEPARATE_PROTOCOL_SEE_SOURCE'),
                       evaluation_script=('src/yuntapr/experimental/core_innovation/stage4/evaluation.py' if row['model_id'] in ('B3','B4') else
                                          'src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py' if row['phase']=='PHASE_B_V2' else 'NOT_VERIFIED_HISTORICAL_SCRIPT_BINDING'),
                       source_manifest_reference='rechecked_snapshot/evidence/source_manifest.json')
            matrix.append(row)
    for model, seed in [('B2',2029),('B3',2030),('B4',2030),('B3',2031),('B4',2031)]:
        matrix.append(dict(model_id=model, experiment_id=f'{model}__E0__s{seed}__f006__PROPOSED', seed=seed,
            phase='RESEARCH_READINESS_PROPOSAL', config='PROPOSED_E0_F006_FIXED_E9', loss_arm='E0',
            dataset_split='2023_Train/2024_Development/2025_FORBIDDEN',train_scenes=959, dev_scenes=963,
            epochs=0, global_steps=0, status='NOT_STARTED', metrics_path='NOT_AVAILABLE', checkpoint_reference='NOT_AVAILABLE',
            checkpoint_selection='PROPOSED_FIXED_EPOCH_9',evidence_path='evidence/'+a.proposal.name, verified_at=now,
            notes='9 epochs / 4320 updates are proposed limits, not actual progress; seeds2030/2031 require researcher confirmation.',
            authorization_status='NOT_AUTHORIZED', comparison_population='CORE_F006_959_963',
            protocol_reference='B2_TRAINING_AND_EVALUATION_REPORT.md' if model=='B2' else 'B3_B4_MULTI_SEED_PLAN.md',
            source_snapshot_commit='0ccb3e26e2d50494aba07788fa94dd40ec89b4aa', executed_commit='NOT_STARTED',
            data_version=proposal['data']['population_sha256']+';statistics='+proposal['data']['statistics_sha256'],
            evaluation_script='src/yuntapr/experimental/core_innovation/stage4/evaluation.py',
            source_manifest_reference='rechecked_snapshot/evidence/source_manifest.json'))
    with (OUT/'B0_B4_EXPERIMENT_MATRIX.csv').open('x', encoding='utf-8', newline='') as f:
        w=csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(matrix)
    approval = dict(approved_by_researcher=False, decision_id='RESEARCHER_MUST_SUPPLY_AFTER_REVIEW',
        model='B2', seed=2029, code_commit='REVIEWED_FINAL_CODE_COMMIT_REQUIRED', proposal_sha256=proposal['proposal_sha256'],
        optimizer_update_cap=4320,source_read_byte_cap=budget['logical_source_bytes'],
        source_read_file_cap=budget['logical_source_read_instances'], replay_allowance=0,
        approved_stem_rule=proposal['config']['stem_rule'], max_wall_seconds=21600,
        note='Template only. Not authorization. Researcher must approve the concrete protocol and exact limits.')
    write('B2_RESEARCHER_APPROVAL_TEMPLATE.json', json.dumps(approval, ensure_ascii=False, indent=2))
    write('RUNBOOK.md', f"""
# 运行与审查说明

状态：仅完成准备与合成核查；本轮没有正式训练许可。建议先审查[B2协议](B2_TRAINING_AND_EVALUATION_REPORT.md)，再决定是否批准B2单项，不将多seed或B5–B8自动捆绑启动。

工作目录为本轮独立准备副本根目录。使用历史CUDA Python环境，启动前设置 `PYTHONHASHSEED=2029`、`CUBLAS_WORKSPACE_CONFIG=:4096:8`、`OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1`。本机环境绝对位置保留在私有记录；这里不复制个人数据根路径。

元数据准备命令（只读取已存在清单/统计/SQLite；每次使用新输出名）：

```text
python tools/research_readiness/prepare_b2.py --historical-preparation <历史seed2029/preparation.json> --historical-b3-run <历史恢复运行目录> --output docs/research_readiness/20261025/evidence/b2_proposal_NEXT.json --private-output docs/research_readiness/.local/b2_preparation_NEXT.json
```

本轮最终提案：`evidence/{a.proposal.name}`；私有输入：`docs/research_readiness/.local/b2_preparation_20261025_v3.json`（相对于仓库根目录），包含原清单/统计定位与受限源范围。私有准备文件、气象数据及权重不公开。

针对性合成检查：

```text
python tools/research_readiness/run_checks.py test_candidates
python docs/research_progress/scripts/verify_public.py
python tools/research_readiness/verify_delivery.py
```

以下仅为**未来获批后**的命令模板，本轮未执行：研究者审核最终代码提交、最新提案SHA、首层映射及明确额度后，将批准决定登记到新的私有JSON，不能直接使用False模板；不得把AI自行改True当成批准。

```text
python tools/research_readiness/train_b2.py --execute --proposal docs/research_readiness/20261025/evidence/{a.proposal.name} --private-preparation docs/research_readiness/.local/b2_preparation_20261025_v3.json --researcher-approval <研究者明确批准记录.json> --output docs/research_readiness/.local/B2_s2029_NEW_RUN
```

执行器要求干净的已跟踪代码与批准commit一致、提案/代码/源范围哈希不变、新输出目录、4,320更新及精确读取额度、0重放；至少24GiB空闲磁盘和既定GPU/RAM入场条件。到时限或任何不一致就停止并留失败收据，不自动恢复、不改batch/精度/人口、不覆盖旧LAST。

真实数据端到端执行仍NOT_VERIFIED，不能因存在启动命令而称为已经完成；未来审批也不免除开始时的资源及源完整性检查。
""")
    write('README.md', """
# 本轮科研核查与待审方案

正式训练仍为NOT_STARTED；B0–B4总体科研验收为IN_PROGRESS。

- [B2训练与配对评价报告](B2_TRAINING_AND_EVALUATION_REPORT.md)
- [B3/B4多seed计划与上尾诊断](B3_B4_MULTI_SEED_PLAN.md)
- [B0–B4阶段验收](B0_B4_STAGE_ACCEPTANCE.md)
- [B5/B6就绪审计](B5_B6_READINESS_REPORT.md)
- [完整矩阵](B0_B4_EXPERIMENT_MATRIX.csv)
- [运行与审批入口](RUNBOOK.md)

本轮只读取既有科研证据、执行元数据核对及合成工程检查；没有原始气象载荷读取、权重加载或正式优化器更新。两份旧权重仅做文件SHA复核。交付与检查汇总见DELIVERY_MANIFEST.json和DELIVERY_VERIFICATION.json。
""")
    print(json.dumps(dict(status='REPORTS_CREATED_SCIENTIFIC_ACCEPTANCE_NOT_COMPLETE', report_count=4, matrix_rows=len(matrix), formal_optimizer_updates=0)))


if __name__ == '__main__':
    main()
