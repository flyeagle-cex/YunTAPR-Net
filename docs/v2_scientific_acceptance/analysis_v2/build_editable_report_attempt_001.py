"""Editable Chinese LaTeX report, generated only from completed evidence."""
import json,csv,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/run_20261009T112710_013267Z'; OUT=RUN/'delivery_v2'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def csvrows(name):
    with (OUT/name).open(encoding='utf-8') as f:return list(csv.DictReader(f))
def esc(s):
    return str(s).replace('_',r'\_').replace('%',r'\%').replace('&',r'\&')
def num(v):return f'{float(v):.7g}'
def sha(label,value):return label+r'：\par\noindent\texttt{'+value[:32]+r'}\par\noindent\texttt{'+value[32:]+r'}\par'
def main():
    metrics=read(RUN/'paired_best_metrics.json'); u=read(OUT/'paired_uncertainty.json'); strata=csvrows('PAIRED_STRATIFIED_ANALYSIS.csv'); exposure=csvrows('upper_tail_exposure_units.csv');coverage=csvrows('conditional_quantile_calibration.csv')
    table=[]
    names={'Core_loss':'Core loss','Brier':'Brier','AUROC':'AUROC','AP':'AP','conditional_pinball':'条件 pinball'}
    for key,v in u['comparisons']['ALL'].items():
        ci=v['paired_difference_95_percentile_interval']
        table.append(' & '.join([names[key],num(v['B0']),num(v['B1']),num(v['B1_minus_B0']),f"{v['relative_percent_of_B0']:.4g}"+r'\%', '['+num(ci['lower'])+','+num(ci['upper'])+']'])+r'\\')
    overall='\n'.join(table)
    seasonal=[];rain=[]
    for group in u['comparisons']:
        if group=='ALL':continue
        a,b=[next(x for x in strata if x['group']==group and x['model']==m) for m in ('B0_MATCHED_V2','B1_V2')]
        comp=u['comparisons'][group]
        if group.startswith('(') or group=='DRY_LE_0.1':
            qp='不可计算' if not a['conditional_pinball'] else num(a['conditional_pinball'])+' / '+num(b['conditional_pinball'])
            rain.append(' & '.join([esc(group.replace('DRY_LE_0.1','干条件 ≤0.1').replace('inf',r'$\infty$')),f"{int(a['N_valid']):,}",num(a['Brier'])+' / '+num(b['Brier']),qp])+r'\\')
        else:
            seasonal.append(' & '.join([esc(group.replace('MONTH_','月 ').replace('SO_PARTIAL_AUTUMN','SO（不完整秋季）').replace('CIVIL_DAY_PROXY','民用时钟白天').replace('CIVIL_NIGHT_PROXY','民用时钟夜间')),f"{int(a['N_valid']):,}",num(comp['Core_loss']['B1_minus_B0']),num(comp['AP']['B1_minus_B0']),num(comp['conditional_pinball']['B1_minus_B0'])])+r'\\')
    tail=[];physical=[]
    for model,v in metrics['models'].items():
        for region,t in v['upper_tail_diagnostics'].items():
            tail.append(' & '.join(['B0' if model.startswith('B0') else 'B1','云南内' if region.endswith('INSIDE') else '云南外',num(t['max_qlog']),num(math.expm1(t['max_qlog'])),num(t['q32_per_forward_max_p99']),num(t['q32_per_forward_max_p99_9'])])+r'\\')
    for x in exposure:
        if x['region']!='YUNNAN_INSIDE':continue
        physical.append(' & '.join(['B0' if x['model'].startswith('B0') else 'B1',x['threshold_mm_h'],x['scene_pixel_tau_exposure'],x['scene_pixel_any_tau_exposure'],x['unique_grid_cells'],x['scenes']])+r'\\')
    hist=read(ROOT.parent/'v2_phase_a_review/upper_tail_full_history_comparison_20261009_v1.json');ht=[]
    for m,phases in hist['models'].items():
        for phase,regions in phases.items():
            for region,v in regions.items():
                ht.append(' & '.join(['B0' if m.startswith('B0') else 'B1',phase,'云南内' if region.endswith('INSIDE') else '云南外',num(v['max_qlog_across_all_completed_epochs']),str(v['max_qlog_epoch']),num(math.expm1(v['max_qlog_across_all_completed_epochs']))])+r'\\')
    covlines=[]
    for model in metrics['models']:
        selected=[x for x in coverage if x['model']==model]; last=selected[-1]
        mean_abs=sum(abs(float(x['coverage_error'])) for x in selected)/32
        covlines.append(esc(model)+'：32 tau 平均绝对覆盖误差 '+num(mean_abs)+'；q32 覆盖 '+num(last['coverage'])+'，95\% 探索区间 ['+num(last['coverage_ci_lower'])+','+num(last['coverage_ci_upper'])+']。\par')
    body=r'''\documentclass[UTF8,a4paper,10pt,fontset=windows]{ctexart}
\usepackage[margin=20mm]{geometry}
\usepackage{booktabs,longtable,array,graphicx,hyperref,amsmath}
\hypersetup{colorlinks=true,linkcolor=blue,urlcolor=blue}
\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}
\renewcommand{\arraystretch}{1.18}\sloppy
\newcommand{\fig}[2]{\begin{center}\includegraphics[width=\linewidth]{figures/#1.png}\end{center}\small #2\normalsize\par}
\begin{document}
\begin{center}{\LARGE YunTAPR-Net v2 paired Phase-A}\par{\Large 科学验收证据与研究者决策材料}\par 2024 完整开发验证集；只读冻结 BEST；2026-10-09\end{center}
\section*{1. 总体证据与验收边界}
两个模型均保持 Epoch 9 BEST，不重新训练、不重新选择 checkpoint。B0-Matched-v2 使用最新 B13；B1-v2 使用六个因果 B13 时次。正式训练已完成；本轮仅准备科学证据，\textbf{不自动验收、不批准 Phase-B}。

主评价集合为冻结 common intersection 的 10,501 场景，云南 mask 内 36,018,430 个有效 scene-pixel 暴露；其中真实雨暴露 4,496,600。Train=10,455，不在本轮重新拟合。场景及格点均有相关性，不能视作数千万个独立试验。

\begin{center}\scriptsize\begin{tabular}{lrrrrl}\toprule
指标 & B0 & B1 & B1$-$B0 & 相对 B0 & 配对差异 95\% 探索区间\\\midrule
@OVERALL@
\bottomrule\end{tabular}\end{center}
Core、Brier、conditional pinball 越小越好；AUROC/AP 越大越好。相对差异为 $(B1-B0)/|B0|\times100\%$，不是百分比点。Pinball 在 log1p(mm/h) 空间、真实雨条件集合上计算。

Core、Brier、AUROC、AP 的配对区间方向一致，但 conditional pinball 区间跨零。5 mm/h 以上固定真实雨区间 pinball 点估计均为 B1 更高；不能宣称全部强雨条件改善。概率区分改善也不代表预测已校准。B1 云南 q32$>$100 mm/h 暴露为 58 个 scene-pixel，B0 为零，需单独审查。

B0/B1 参数分别为 4,329,410 / 4,331,810，差 2,400，仅来自输入接口；其余冻结 backbone、SP04、heads、loss、normalization、训练集合和评价保持相同。六时相可能携带云系移动、演变和生命周期信息，但未做机制消融，不能证明某个物理机制导致增益。单一 paired seed、输入参数差异与开发集 BEST 选择限制外推。

\textbf{本材料全部是不确定性明确标注的开发验证分析。}没有 2025 结果，不能推出独立最终测试泛化结论。
\newpage
\section*{2. 配对重采样、数据口径与限制}
以 target window\_start 的 UTC 日期分组，2024-03-01 至 2024-10-31 的 245 日期预声明为 35 个固定、不重叠的连续 7 日块。每次有放回抽 35 块，两模型共享同一块次数；seed=2026，2,000 次。保存实际次数矩阵，逐指标记录有效 replicate 数。

块内保留所有时次、空间像元与原 mask/有效条件。Core、Brier 和 pinball 按整体分子/分母重算；AUROC/AP 按精确 BF16 概率分数组及原 tie 规则重算，不平均日期 AUC，不独立抽像元。采用 2.5/97.5 百分位点对点探索区间；相对差异区间也单独保存。没有确认性 p 值或多重比较校正。

假设跨周依赖足够弱。天气系统可跨块边界，季节分布不平稳；35 块和单一年份限制独立信息量。7 日长度未依结果优化，不声称最优。区间未校正同一验证集挑选 BEST 的乐观偏差，不估计训练 seed 变异，不代表未来年份置信区间。

区块重采样背景：\href{https://doi.org/10.1214/aos/1176347265}{Künsch (1989)}、\href{https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870}{Politis--Romano (1994)}。本实现是固定非重叠周块，不是随机长度 stationary bootstrap。

原已发表全量 BEST 的 frozen core 12 字段、概率评价与既有 upper-tail 逐字段零容差复核。新 CPU observer 日期汇总因浮点求和顺序不同，采用 $10^{-12}$ 核验全量分子/分母及点估计。两个标准明确分开；总体表直接复用已发表点估计。

雨标签沿用 float32 IMERG$>$float32(0.1)。Conditional coverage 为真实雨、有效云南像元上的 $\log(1+y)\le q_i$。干/雨真值分层只作诊断，不更改样本资格；单一正类区间 AUROC 不定义、AP=1 是平凡值，不是检测成功。POD/FAR/CSI 保持 THRESHOLD\_NOT\_FROZEN，没有依据 2024 挑选新概率阈值。

DIAGNOSTIC\_PROXY 仅为 $p_{rain}\,\mathrm{mean}(\mathrm{expm1}(32\ q_i))$ 的描述性 Bias/MAE/RMSE，\textbf{不是分布精确期望或正式确定性点预测}。只在 detached 只读 observer 做物理转换；训练核心路径无改变。

没有既有预定义地形分区或独立降水事件目录，因此两项均 NOT\_ESTIMABLE；未读取 DEM、未造新区域/事件。IMERG 为监督参考，不能当作无误差绝对真值。
\newpage
\section*{3. 固定雨强分层}
沿用已有 Scientific Review 的右闭真实雨区间，不依据预测值选择。下表 Brier/pinball 为 B0 / B1，完整误差、发生评分、探索区间与不可计算理由见 PAIRED\_STRATIFIED\_ANALYSIS.csv / paired\_uncertainty.json。
\begin{center}\small\begin{tabular}{lrrr}\toprule
IMERG mm/h & 有效暴露数 & Brier（B0 / B1） & pinball（B0 / B1）\\\midrule
@RAIN@
\bottomrule\end{tabular}\end{center}
\fig{rain_stratified_pinball}{图 1：全部预声明真实雨强区间；竖线是周块点对点 95\% 探索区间。N 为 scene-pixel 暴露，非独立事件。最强区间只有 69 个暴露，不能以大量弱雨样本的信息量替代其不确定性。干条件 pinball 不定义，不填零。}
\newpage
\section*{4. 月、季节与民用时钟日夜}
预声明 MAM、JJA、SO（不完整秋季），月度 3--10 月。Civil-clock proxy 为最新冻结 B13 nominal 转 UTC+8 后的 [06:00,18:00)，不是天文日出日落；该新增描述定义在补充推理前登记，不从输出反向挑选。
\begin{center}\small\begin{tabular}{lrrrr}\toprule
固定分组 & 有效暴露 & $\Delta$Core & $\Delta$AP & $\Delta$pinball\\\midrule
@SEASON@
\bottomrule\end{tabular}\end{center}
差异统一为 B1$-$B0；完整配对区间见 paired\_uncertainty.json。月份、季节和日夜集合互有重叠，不将这些行视为独立确认试验。9/10 月与 SO 的 conditional pinball 点估计上升，结论应与整体均值区分。

地形分层：NOT\_ESTIMABLE\_NO\_PREDEFINED\_SUBREGION\_MASK\_AVAILABLE。历史 region audit 的缺项与本次定义搜索审计保留，没有依据模型输出划选山地/河谷。补充地形科学定义需要单独研究者决策。
\newpage
\section*{5. Occurrence 概率可靠性}
使用全部有效云南干/雨像元，固定 10 箱 [0,0.1)、\ldots、[0.9,1]。每箱的平均预测概率、真实雨频率、暴露数、预测/真实频率区间见 reliability\_fixed\_bins.csv；空箱不填值。横向与纵向区间均来自同一日期块重采样。
\fig{occurrence_reliability}{图 2：点及区间保持原始概率，没有温度缩放、Platt/isotonic、阈值调优或后验校准。最右箱为空；高概率箱样本很少，其大区间不可隐藏。箱内暴露数非独立像元试验次数。}
低预测概率箱普遍高估真实雨频率，中高概率箱出现低估。曲线与参考对角线的偏离表明仍有校准问题；Brier 改善不能替代可靠性检查。Focal 训练下的分数仍按既有概率语义评价，本材料没有更改预测或声称已完成校准修正。
\newpage
\section*{6. 条件分位数覆盖}
冻结 32 tau，$\tau_i=(i-0.5)/32$；$q_{32}$ 的 tau=0.984375。仅包含真实雨且有效云南像元，N=4,496,600；不把真实干像元带入条件分位数校准。全部 tau 同时呈现，没有挑选效果好的 tau。
\fig{conditional_quantile_calibration}{图 3：左为 empirical coverage；右为 coverage$-$tau。阴影是点对点探索区间，\textbf{不是 32 tau 同时置信带}，也不估计 BEST 选择偏差。}
@COV@
低 tau 覆盖偏高、较高 tau 覆盖偏低，B1 上尾欠覆盖更明显。整体条件 pinball 的细小改善与高 tau 校准问题可以同时存在，不能互相抵消。
\newpage
\section*{7. 冻结 BEST 的上尾与物理解释}
q32 是条件 98.4375\% 分位数，不是无条件均值或确定性点预测。对高分位数不能要求每次等于真值；也不能将过高值自动判定合理。FP64 边界 $\log(1+\mathrm{float64\_max})\approx709.782712893384$，两个 BEST 全部区域未观察到超过边界。\textbf{浮点安全不等于物理合理，亦不是未来保证。}
\begin{center}\small\begin{tabular}{llrrrr}\toprule
模型 & 区域 & 最大 qlog & 对应 mm/h & forward-max p99 & p99.9\\\midrule
@TAIL@
\bottomrule\end{tabular}\end{center}
\begin{center}\small\begin{tabular}{lrrrrr}\toprule
模型 & 阈值 mm/h & pixel-tau & any-tau pixel & 去重格点 & 场景数\\\midrule
@PHYSICAL@
\bottomrule\end{tabular}\end{center}
上表为云南内。pixel-tau 逐场景、像元、tau 计数；any-tau 每场景像元只计一次（严格单调时等同 q32）；去重格点是跨场景空间去重；场景是有任何暴露的场景数。\textbf{四者均不是独立降水事件}。无事件目录，不估计事件数。云南外对照及完整五阈值见 upper\_tail\_exposure\_units.csv。
阈值 10/50/100/500/1000 只作描述，非新训练规则或 QC。B1 云南 q32$>$100 的 58 暴露仅有 44 个去重格点；其真值和发生概率完整登记，不能称为 58 次极端降雨。
\newpage
\section*{8. 上尾预测与监督真值，以及逐 epoch 历史}
\fig{inside_q32_vs_truth}{图 4：预声明 q32$>$50 的预测条件描述集合。颜色为 p\_rain；横轴 symlog 保留真实干值零，不 clamp。所有有效云南选定暴露均画出，没有挑个案。该图不是完整校准集合，也不是概率阈值检测。}
完整 sample\_id / row / column / q32 / IMERG / p\_rain 见 inside\_q32\_gt50\_observations.csv；最大值位置和 >100/>500/>1000 条件下真值/概率 min/max 见 UPPER\_TAIL\_PHYSICAL\_REVIEW.md。云南外 invalid target 不当作零雨真值。高条件分位数在真实干条件缺少 quantile 直接监督，须联合 p\_rain 解释。
\begin{center}\small\begin{tabular}{lllrrr}\toprule
模型 & 历史阶段 & 区域 & 最大 qlog & epoch & 对应 mm/h\\\midrule
@HISTORY@
\bottomrule\end{tabular}\end{center}
直接复用已发表 17 epoch 描述性历史，Train/Validation 分开。反复暴露不是新观测，不平均逐 epoch p99，不把 extrema 当作 pooled percentile。完整阈值计数和每 epoch p99/p99.9 保留原 upper\_tail\_history.csv。历史聚合不能恢复每 epoch 独立事件/去重格点，缺项保留。
\newpage
\section*{9. B1 恢复治理偏差：事实与影响}
已冻结恢复规范要求：\textbf{另有绑定具体 LAST SHA 和原授权祖先的研究者恢复批准}。实际 B1 epoch 14 LAST 恢复却沿用原始 Phase-A 授权及持续目标，并明确记录没有新的研究者科学决策。因此，登记文件不能证明研究者另行给出 LAST-bound 恢复批准。

恢复执行绑定 SHA：\par\texttt{73d8e76649ac1310ff1a541cb7f0e7518c4}\par\texttt{ad527c8571113726b56312c7115a2}\par
远端提交：\path{f269272c821b49c5226ddf6d75eeb7108522cd34}；核验时刻 2026-10-09T00:40:57.273183+00:00。Codex 生成 authorization JSON、发布和技术预检不是人类独立批准，不能追认或补签。

工程状态：完整 epoch 14 LAST（update=73,192）model、optimizer、scheduler、RNG 有实际恢复收据；epoch 15 两次未 checkpoint 的 3,095+382=3,477 更新全部丢弃。重跑保留前缀的 sample order/LR/loss/grad/denominator/clipped 与保存记录零容差一致。最终 retained=88,876，all-attempt=92,353。该对账支持工程可追溯性，不证明审批合规。

冻结 BEST 为 epoch 9（update=47,052），早于受影响恢复段，其参数并非由恢复段产生；后续早停、历史闭合及未出现更优 checkpoint 的确认仍经历恢复过程。不能用 BEST 时间关系将治理偏差抹去。

未经核验的历史授权草稿、原始字节、后续更正、文件锁中断/失败证据全部保留。本次材料没有删除失败、制造历史时间戳或追认授权。当前“批准上述所有申请”只作为本轮本地科学绘图例外，不解释为历史恢复追认。

独立审批缺失削弱治理合规及研究者对失败后继续执行的控制；严格冻结身份和重放证据降低调参/轨迹改变的工程风险，但不能消除治理偏差。既不据此自动否定数值结果，也不自动认可科学验收。\textbf{技术可信度、治理处置、科学接受应分别由研究者决定。}

逐来源 SHA、恢复身份、原始授权祖先和 BEST 时间关系见 recovery\_governance\_source\_audit.json / recovery\_best\_chronology\_note.json。确切历史口头批准时间无法由文件恢复，未虚构。
\newpage
\section*{10. 身份、只读计数与交付审计}
完成证据基线：\path{166b1f86291bbcde167dbec30d3ae43ac23bba4c}\par
科学批准：\path{d049f7ab7b8a382f47a5fe54384ea9416a22cde9}\par
冻结执行 checkout：\path{a1af0325b481202941c57e8fc94f3b20e441630a}\par
@SHAS@
@BESTSHAS@
Normalization mean=271.60515414265217 K；std=19.93959597783802 K，未重新拟合。BEST 前后 model-state SHA 相同；238 项历史 checkpoint/epoch 文件前后 SHA 核验，冻结执行源文件/配置/manifest 身份保持。

新增只读 2024 推理：每模型 10,501 场景、1,313 forwards，共 2,626。B0 raw opens=42,004/native decodes=31,504；B1=147,014/84,009；合计 189,018 / 115,513。此为受控父/worker 调用路径计数，非所有 OS 进程声明。后续统计与本地绘图没有重新 forward，没有 raw source 读取。

MODEL\_PARAMETERS\_UPDATED=false；BACKWARD\_CALLS=0；OPTIMIZER\_STEPS=0；FORMAL\_OPTIMIZER\_STEPS\_ADDED=0；2025\_RAW\_ACCESS=0；2025\_PIXELS\_READ=0；V2\_PHASE\_B\_AUTHORIZED=false。

原报告渲染在末步发生变量遮蔽 TypeError，失败日志和 v1 部分文档原样保留。本独立 delivery\_v2 仅修复报告生成，不重跑推理或重采样。prior\_closeout\_preservation.json 登记旧字节 SHA；本地绘图获明确批准，figure\_provenance.json 登记实际输入/输出与库版本。LaTeX 可编辑，SVG 图和 CSV 可独立复核。

最终总清单 acceptance\_manifest.json 逐文件记录来源、代码、生成物、SHA；verification\_tests.json、visual\_delivery\_audit.json、final\_status.json 分开记录实际检查结果。未执行项不得称 PASS。Checkpoint 及 model/optimizer 二进制仅在原 F 盘，不上传 GitHub。
\newpage
\section*{11. 研究者科学决策表（未填写）}
本表仅准备决策，不构成自动接受或 Phase-B 授权。
\begin{longtable}{p{.28\linewidth}p{.34\linewidth}p{.28\linewidth}}\toprule
决策项 & 证据 / 限制 & 研究者结论\\\midrule
两模型 Phase-A 科学验收 & 总体指标、探索区间、冻结样本和 BEST & 待填写\\
六时相增益与实际意义 & 单 seed、输入参数差异、机制未消融 & 待填写\\
概率可靠性 / 条件覆盖 & 固定分箱及全部 32 tau，不做校准修正 & 待填写\\
云南 q32 上尾可接受性 & 超阈值、去重格点、真实干雨与 p\_rain & 待填写\\
强雨 / 季节 / 日夜证据 & 预声明分层；强雨有限独立信息 & 待填写\\
地形 / 独立事件不足 & 无预定义掩膜或事件目录，未虚构 & 待填写\\
恢复治理偏差处置 & 独立审批缺失；技术对账不能追认 & 待填写\\
是否需要新科研工作 & 后续任务需独立授权 & 待填写\\\bottomrule
\end{longtable}
研究者姓名：\underline{\hspace{35mm}}\quad 日期：\underline{\hspace{30mm}}\par
签字 / 审批记录：\underline{\hspace{90mm}}

\textbf{RESEARCHER\_SCIENTIFIC\_APPROVAL\_REQUIRED=true}\par
\textbf{V2\_PHASE\_B\_AUTHORIZED=false}\par
2025\_RAW\_ACCESS=0；2025\_PIXELS\_READ=0。交付并发布后 STOP，等待研究者审查。
\end{document}
'''
    values={'OVERALL':overall,'RAIN':'\n'.join(rain),'SEASON':'\n'.join(seasonal),'TAIL':'\n'.join(tail),'PHYSICAL':'\n'.join(physical),'HISTORY':'\n'.join(ht),'COV':'\n'.join(covlines),'SHAS':'\n'.join([sha('Protocol','a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be'),sha('Head','3a865a6e4ab180f61d7ab6e2f684ab6b814bfe6b2e59a34d127ddf1d772fc97e'),sha('Normalization','656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31')]),'BESTSHAS':'\n'.join(sha(m+' BEST Epoch 9',v['BEST']['sha256']) for m,v in metrics['models'].items())}
    for key,v in values.items():body=body.replace('@'+key+'@',v)
    # Every generated symbol is escaped only in text contexts, never in formulas.
    body=body.replace('B0_MATCHED_V2 BEST','B0\\_MATCHED\\_V2 BEST').replace('B1_V2 BEST','B1\\_V2 BEST')
    assert not any('@'+k+'@' in body for k in values)
    with (OUT/'PHASE_A_SCIENTIFIC_ACCEPTANCE.tex').open('x',encoding='utf-8',newline='\n') as f:f.write(body)
    print('Editable LaTeX source created; PDF compilation/visual audit still pending')
if __name__=='__main__':main()
