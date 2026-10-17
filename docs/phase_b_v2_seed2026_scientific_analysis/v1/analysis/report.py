"""Author editable Chinese paper results directly from audited aggregate tables.

This is a reporting script, not a data loader or a model evaluation entry point.
It does not fit thresholds, resample results again, or change any protocol.
"""
from common import OUT, read, table, load

D=read(OUT/'ANALYSIS_DATA.json');R=D['resource'];A=read(OUT/'CHECKPOINT_PAYLOAD_AUDIT.json')
F=D['final'];gib=1024**3

def tab(headers, rows, spec=None):
    spec=spec or 'l'+'r'*(len(headers)-1)
    return ('\\begin{center}\\small\n\\begin{tabular}{'+spec+'}\\toprule\n'
            +' & '.join(headers)+' \\\\ \\midrule\n'
            +'\n'.join(' & '.join(map(str,r))+' \\\\' for r in rows)
            +'\n\\bottomrule\\end{tabular}\\end{center}\n')

def fig(name,caption,width='\\linewidth'):
    return ('\\begin{figure}[htbp]\\centering\n\\includegraphics[width='+width+']{../figures/'+name+'.pdf}\n'
            +'\\caption{'+caption+'}\\end{figure}\n')

def main():
    runresources=[]
    for (m,a),r in load().items():
        times=[x for x in D['timing'] if x['model']==m and x['arm']==a]
        runresources.append(dict(model=m,arm=a,updates=r['updates'],train_hours=sum(x['train_seconds'] for x in times)/3600,
             validation_hours=sum(x['validation_seconds'] for x in times)/3600,
             committed_total_hours=sum(x['total_seconds'] for x in times)/3600,
             cuda_allocated_bytes=r['cuda_peak_allocated_bytes'],cuda_reserved_bytes=r['cuda_peak_reserved_bytes']))
    table('run_resources.csv',runresources)
    chunks=[r'''\documentclass[UTF8,fontset=windows,10pt,a4paper]{ctexart}
\usepackage[margin=20mm]{geometry}
\usepackage{amsmath,amssymb,booktabs,longtable,graphicx,float,xcolor,hyperref}
\hypersetup{colorlinks=true,linkcolor=blue,urlcolor=blue,pdftitle={YunTAPR-Net seed2026 科学结果分析}}
\setlength{\parskip}{0.35em}
\setlength{\parindent}{2em}
\renewcommand{\arraystretch}{1.2}
\graphicspath{{../figures/}}
\title{YunTAPR-Net：首批消融结果与复现准备\\\large seed2026，2024 开发集探索性分析}
\author{研究者审查稿：基于冻结实验及已发布聚合证据}
\date{2026 年 10 月 17 日}
\begin{document}\maketitle
\begin{abstract}
本报告审查 B0/B1 与 E0/E1/E2 的六个固定第九轮终点，不新增模型推理或优化器更新。
E1 在两个模型上降低 Brier 和十箱可靠性偏差，排序指标变化远小于概率误差变化。
E2 的 q32 覆盖改善主要得到 B0 的开发集证据支持，B1 的探索区间跨零；所有组仍欠覆盖。
B1 的总体排序与条件 Pinball 较好，但最高雨强层和上尾诊断不支持全面优越性。
六份最终 LAST 的内容 SHA 与收据一致；本轮允许范围的跨盘搜索未核验到独立备份。
全部结论限于已反复使用的 2024 开发集及单个初始化 seed，不能解释为独立确认结果。
\end{abstract}
\section{数据、设计与证据口径}
固定矩阵为 B0-Matched-v2（最新一帧 B13）和 B1-v2（六帧因果 B13），
E0：$\alpha=0.5,\gamma=2,\lambda_q=1$；E1：$\gamma=0$，其余同 E0；
E2：$\lambda_q=2$，其余同 E0。seed 均为 2026，沿用 D1/Q1/N0/I3/B9/S0/V0。
每组固定 9 epoch、47,052 次已提交更新，六组合计 282,312 次有效预算内终点更新；
历史失败或重放消耗不能由此抹除，完整消耗继续以原持久化账本为准。
2023 Train 为 10,455 场景；2024 Development 为共同 10,501 场景。
每组第九轮有效暴露 $N_v=36,018,430$，真实有雨暴露 $N_r=4,496,600$。
场景--像元暴露不是独立事件；冻结日期为 3--10 月窗口，不代表完整四季。
2024 已用于历史 BEST 选择及反复诊断，2025 独立测试继续封存。

输入标签由原始 FP32 雨强严格大于 $0.1\,\mathrm{mm/h}$ 判定；条件分位数计算在
FP64 的 $\log(1+\mathrm{mm/h})$ 空间。32 个 $\tau_i=(i-0.5)/32$，最高 $\tau_{32}=0.984375$。
令 $\ell_{\gamma}$ 为保留 $\alpha=0.5$ 的 Focal，$\rho_\tau(u)=\max(\tau u,(\tau-1)u)$。
\begin{align}
S_{\rm occ,\gamma}&=\sum_{j\in V}\tfrac12(1-p_{t,j})^\gamma\operatorname{BCEWithLogits}(z_j,y_j),\\
S_q&=\sum_{j\in R}\frac1{32}\sum_{i=1}^{32}\rho_{\tau_i}\!\left(\log(1+r_j)-q_{ij}\right),\\
L_{\rm train}&=(S_{\rm occ,\gamma}+\lambda_q S_q)/N_v,\\
\mathrm{CommonCore}_{64}&=(S_{\rm occ,2}^{64}+S_q^{64})/N_v,\qquad
\mathrm{CP}=S_q^{64}/N_r.
\end{align}
因此 E1 仍是 $0.5\times$ BCE，且三个臂的训练 loss 不可直接当作共同评价。
CP 未乘 $\lambda_q$。Common Core 固定 $\gamma=2$，并非 E1 的训练目标。
Brier 为 $\sum_{V}(p-y)^2/N_v$；AUROC/AP 使用已发布的精确 score 并列规则，
十箱可靠性不替代排序计算。覆盖率只对真实有雨有效像元统计。

代码映射：上述训练和共同评价分别来自候选
\texttt{phase\_b\_v2\_ablations/focal.py}、\texttt{pinball.py}、\texttt{total.py}、\texttt{metrics.py}；
可靠性、精确并列分数与雨强层来自 \texttt{phase\_b\_v2\_formal\_integration\_candidate/metrics.py}。
具体函数和源码 SHA 见随附 \texttt{manifest.json}，不修改正式源码。

\section{固定第九轮结果}
''']
    chunks.append(tab(['模型/臂','Brier','AUROC','AP','Common Core','CP','q32 覆盖(\\%)'],
        [[r['model']+'/'+r['arm']]+[f"{r[k]:.6f}" for k in ['brier','auroc','average_precision','core_fp64','conditional_pinball']]+[f"{100*r['q32_coverage']:.3f}"] for r in F]))
    chunks.append(r'''表中概率误差和排序指标无量纲；CP 在 $\log(1+\mathrm{mm/h})$ 空间，Common Core 是混合目标，不标为雨强单位。
未进行基于结果的最佳轮次选择。图 1 显示训练与共同评价，图 2 显示完整开发曲线。
E1 的 Common Core 明显较高，不应为突出 Brier 改善而省略这一代价。
总体训练目标下降及开发指标波动只能描述这九轮，不证明收敛或无过拟合。
''')
    chunks.append(fig('fig01_training_common_core','九轮曲线。上排为各臂不同的训练目标，下排为统一 FP64 Common Core；不同面板纵轴独立。'))
    chunks.append(fig('fig02_development_curves','六组完整开发曲线。实线 B1、虚线 B0；仅报告固定第九轮，不据开发表现改变预算。'))
    chunks.append(r'''\clearpage\section{四个预注册主比较与 M-C 复核}
H-O 主效应为 E1$-$E0 的 Brier 差；H-Q 为 E2$-$E0 的
$|\widehat{C}_{32}-0.984375|$ 差。两类效应均以负值为有利方向。
''')
    chunks.append(tab(['模型','对比/指标','点估计','95\\% 探索区间'],[
        [r['model'], 'E1/E0 Brier' if r['metric']=='brier' else 'E2/E0 覆盖绝对误差(pp)',
         f"{r['difference']*(1 if r['metric']=='brier' else 100):+.6f}",
         f"[{r['lower']*(1 if r['metric']=='brier' else 100):+.6f}, {r['upper']*(1 if r['metric']=='brier' else 100):+.6f}]"
        ] for r in D['contrasts']]))
    chunks.append(r'''保留 35 个固定 UTC 七日非重叠日期块，PCG64 seed=2026，2,000 次配对有放回抽样。
每次对所有对比使用同一组块 multiplicities，先合计分子、分母再取比值，
不平均各块指标，也不把 seed$\times$像元当独立样本。q32 每次重采样重新取绝对误差后作差。
采用 NumPy linear 分位数的 2.5\% 和 97.5\% 百分位区间。
已独立复算抽样矩阵 SHA、四个点估计和区间，并用逐抽样直接汇总再次检查矩阵算法。
54 份 epoch 验证收据 SHA、六组样本/日期块身份及同轮训练顺序均一致。

这些是四个逐项探索区间，不是同时区间，未施加确认性多重比较控制，不输出显著性星号或功效保证。
跨周天气过程相关和季节非平稳仍可能使区间低估不确定性。
H-O 在两模型中有一致开发性方向证据；H-Q 的 B0 区间位于改善方向，B1 区间跨零。
尚未建立科学最小有意义效应或副作用容忍值，不能据区间位置直接宣告科学验收通过。
''')
    chunks.append(fig('fig05_registered_contrasts','四个预注册主比较。覆盖误差用百分点(pp)；区间为配对日期块开发性区间，非确认性结论。'))
    chunks.append(r'''\section{E1：概率误差与可靠性}
E1 在 B0/B1 的 Brier 分别下降约 0.02144/0.02208，但 AUROC/AP 变化较小。
冻结十箱揭示 E0 低至中概率范围的高估，以及较高概率范围的低估；
E1 更接近可靠性对角线。实际有雨比例为 12.484\%，E0 平均预测概率约为 25\%，
E1 则接近 12\%。因此此处的改善主要体现在概率数值及其可靠性，而非同等幅度的排序提升。
不能由此认定所有概率区间均已校准，或已经获得未来年份泛化能力。

为便于描述，额外计算十箱 ECE：$\sum_k n_k|\bar p_k-\bar y_k|/N_v$。
它不是新增预注册主指标，也不是不依赖分箱的校准真值；不据此重新选择臂或阈值。
''')
    chunks.append(tab(['模型/臂','平均预测概率','实际频率','均值偏差','描述性 ECE10'],[
        [r['model']+'/'+r['arm']]+[f"{r[k]:.6f}" for k in ['mean_predicted_probability','rain_prevalence','mean_probability_bias','ece10_descriptive']] for r in F]))
    chunks.append(fig('fig03_reliability','冻结十箱可靠性及暴露数。空箱不插值，少于 100 暴露的点以空心仅作绘图提示；该提示不改变统计规则。'))
    chunks.append(r'''E1 的 CP 在两模型中均略高于 E0，B1 的 q32$>100$ 暴露由 58 增至 108。
这与“发生概率更好必然使强度更好”不一致。共享骨干梯度改变可能影响条件头，
但本次结果不能确认该机制；需要预定义种子的复现，不能将猜想写成已证实解释。
\clearpage\section{E2、全部分位数覆盖和上尾}
所有臂的 q32 覆盖仍低于 98.4375\% 目标。E2 的 B0 从 95.744\% 提升到 96.076\%，
B1 从 95.077\% 提升到 95.157\%；均未解决欠覆盖。
B0 的 E2 CP 反而略升，B1 略降，说明覆盖靠近目标不等于分布质量全面改善。
必须联合全部 32 个覆盖率、CP、强雨层及异常上尾判断。
''')
    chunks.append(fig('fig04_quantile_coverage','全部 32 条件覆盖率及上端分位数偏差。分母均为真实有雨有效暴露；下排为覆盖率减目标的百分点。'))
    tail100=[next(t for t in D['tails'] if t['model']==r['model'] and t['arm']==r['arm'] and t['threshold_mm_h']==100) for r in F]
    chunks.append(tab(['模型/臂','q32 最大(mm/h)','最大 log span','>100 暴露','其中无雨','场景/格点'],[
        [r['model']+'/'+r['arm'],f"{r['q32_max_mm_h']:.2f}",f"{r['max_span_log']:.4f}",str(t['exposures']),str(t['dry']),f"{t['scenes']}/{t['unique_grid']}"] for r,t in zip(F,tail100)]))
    chunks.append(r'''这里的 span 是 $q_{32}-q_1=\log[(1+Q_{32})/(1+Q_1)]$，不是 mm/h 宽度，
也不能把 $\exp(\mathrm{span})-1$ 当作 $Q_{32}-Q_1$。
已有聚合证据只保留最大 span，不足以重建完整分布、百分位或逐位置发生概率--q32 联合关系。
这些内容记为 NOT\_AVAILABLE，不额外运行真实推理填补。

高分位数超过 100 mm/h 的统计是条件分布的场景--像元暴露，
不是相同数量的独立暴雨事件或确定性百毫米预报。
无雨指 IMERG 参考未超过冻结 0.1 mm/h 标签阈值，不保证独立站点或雷达证实无雨。
E2 对两个模型的最大值及暴露影响不同；B0 最大值上升而 B1 下降，不能宣称统一压制上尾。
''')
    chunks.append(fig('fig08_upper_tail','固定阈值上尾暴露及最大 q32。阈值计数保留湿/干拆分，不能作为独立事件数或物理验证结论。'))
    chunks.append(r'''\clearpage\section{强雨分层与时序贡献}
原定七层 $(0.1,1],(1,5],(5,10],(10,20],(20,30],(30,50],>50$ mm/h，
暴露数依次为 2,764,086、1,470,675、207,616、46,735、6,053、1,366、69。
总体 CP 主要由低雨强暴露贡献，不能掩盖高雨强误差。
B1 相对 B0 在三臂的总体 Brier、AUROC、AP 和 CP 点估计均较好，
但 q32 覆盖误差均更大，且在 $>50$ mm/h 层的 CP 三臂均更高。
该层仅 69 个相关暴露，不能据此推断 69 次独立极端事件。
E0 在 $>5$ mm/h 各层的 B1 CP 均高于 B0；E1/E2 的层间变化更复杂。
因此“时序信息有贡献”目前只能限定于总体开发性指标，不能推广到全部强度。
''')
    chunks.append(fig('fig06_rain_intensity',r'冻结七个真实雨强层的条件 Pinball。全层数值见 rain\_strata.csv，高雨强小样本需谨慎解释。'))
    chunks.append(fig('fig09_intensity_side_effects','E1/E2 相对 E0 的分层 CP 变化。负值较小；原始层边界保持不变，未据结果重分层。'))
    chunks.append(fig('fig07_temporal_contribution','各臂 B1 减 B0 的固定终点差异。此图为补充描述，不升级为新确认性交互检验。'))
    chunks.append(r'''\clearpage\section{最终 LAST、备份与复现边界}
六份第九轮 payload 使用受控只读句柄逐字节计算 SHA，不反序列化模型。
收据、注册记录和发布摘要的 SHA 相符；句柄对象身份及读取前后元数据稳定。
共读取 315,858,678 字节，全部匹配。未来消费仍须同字节验证，单次 SHA 不是永久不变性证明。
''')
    chunks.append(tab(['模型/臂','SHA-256 前 16 位','读取字节','状态'],[
        [r['run_id'].split('__')[0].replace('_','\\_')+'/'+r['run_id'].split('__')[1],
         '\\texttt{'+r['actual_sha256'][:16]+'}',f"{r['bytes']:,}",r['status']] for r in A['primary']],spec='llrl'))
    chunks.append(r'''完整 SHA、脱敏路径标识、只读句柄身份见 CHECKPOINT\_PAYLOAD\_AUDIT.json。
在用户授权的 C:--H: 文件名搜索中遍历 102,397 个目录、1,196,779 个条目，
拒绝 1,137 个包含 2025 的子项名称，发生 6 处权限拒绝；排除系统/缓存、重解析点。
未核验到六份最终 LAST 的独立副本，尤其不能证明离线盘、压缩包或重命名备份存在或不存在。
首遍达到 120,000 目录上限后已保留收据，第二遍改为各卷轮询并在允许范围完成。
新搜索不对被禁止子路径做主动属性或内容读取；历史 2025 属性访问继续为 NOT\_INSTRUMENTED。

备份建议是未来获准执行时，在完整 epoch+验证+原子 LAST+账本提交之后，
复制到第二物理卷及离线/版本化位置，再计算目标完整 SHA，匹配后提交备份清单。
保留所有第九轮以及每轮事务证据。此分析任务没有自动复制权重或改变账本。

\section{剩余十二组的实测资源估算与暂停}
''')
    chunks.append(tab(['组','训练(h)','验证(h)','合计(h)','CUDA allocated/reserved(GiB)'],[
        [r['model']+'/'+r['arm'],f"{r['train_hours']:.2f}",f"{r['validation_hours']:.2f}",f"{r['committed_total_hours']:.2f}",
         f"{r['cuda_allocated_bytes']/gib:.2f}/{r['cuda_reserved_bytes']/gib:.2f}"] for r in runresources]))
    chunks.append(r'''表为已提交九轮路径，重放、启动和异常开销不在每组求和内。
B0 每轮训练/验证中位耗时约 30.7/13.3 分钟，B1 约 53.1/23.3 分钟。
但 B1/E2 第 5 轮训练约 99.5 分钟、验证约 389.5 分钟，总计约 8.15 小时。
异常慢轮原因 NOT\_ESTABLISHED，不能无遥测归因为热降频、休眠或 I/O。
''')
    chunks.append(fig('fig10_observed_resources','已提交 54 轮的实际训练与验证耗时，含慢轮；黑横线为中位数，不是区间。'))
    chunks.append(tab(['剩余 12 组项目','估算/观测'],[
        ['计划更新 / epoch',f"{R['remaining_planned_updates']:,} / 108"],
        ['完整开发验证场景暴露',f"{R['remaining_validation_scenes']:,}"],
        ['已完成六组 train+validation',f"{R['committed_six_train_validation_hours']:.2f} h"],
        ['12 组按每模型实测均值',f"{R['remaining_core_hours']:.2f} h"],
        ['按历史累计活动时长比例',f"{R['remaining_historical_elapsed_ratio_hours']:.2f} h"],
        ['上述较大值加 25\\% 规划余量',f"{R['planning_25_percent_margin_hours']:.2f} h（{R['planning_25_percent_margin_hours']/24:.2f} 天）"],
        ['预计反复原始内容 I/O',f"{R['remaining_content_bytes_linear_scenario']/1024**4:.2f} TiB"],
        ['108 份 checkpoint payload',f"{R['remaining_108_checkpoint_payload_bytes']/gib:.2f} GiB"],
        ['payload 三份合计',f"{R['three_copy_checkpoint_bytes']/gib:.2f} GiB"],
        ['审计日志线性估计',f"{R['remaining_log_bytes_linear_scenario']/gib:.2f} GiB"],
        ['精确分数暂存实测比例 / 硬预算',f"{R['remaining_score_db_bytes_linear_scenario']/gib:.3f} / {R['remaining_score_db_hard_bound_bytes']/gib:.1f} GiB"],
    ],spec='lr'))
    chunks.append(r'''这些是同类设备单 GPU 被任务占用的墙钟时间，不是 GPU 利用率积分、能耗或 FLOP 测量。
实测每轮 P10/P90 线性情景约 105--126 h，但不构成预测或置信区间，且不能包络极慢轮。
125 h 核心估计保留慢轮；132.5 h 另按历史累计 66.25 h 的两倍计入已观察开销。
166 h 加余量仅是规划假设；未来驱动崩溃、供电、磁盘或可用时间改变均可能超过它。

已观察最大 CUDA allocated/reserved 为 3.31/5.57 GiB；进程 working set 5.26 GiB，
采样 private commit 10.18 GiB。working set 与 private commit 不可相加，后者不是物理驻留量。
原硬限制仍为 CUDA reserved 6 GiB、启动空闲显存至少 5 GiB，
进程 working set 6 GiB、private commit 12 GiB、Job commit 16 GiB，
系统空闲 RAM 6 GiB、commit 余量 10 GiB、磁盘余量 12 GiB。
reserved 余量仅约 0.43 GiB，应按原门槛停止而非降低模型、batch 或精度。
存储可按三份 payload、日志、实测暂存加 12 GiB 空余约 36 GiB 规划；
采用全部精确分数 DB 硬上限则约 63 GiB，再另留文件系统、临时文件余量。
这些不包含原始数据重复存储，不自动放宽原 7 天/32 TiB 等执行硬预算。

已登记 2026-10-14 00:26:59 UTC 的 nvlddmkm 153 / LiveKernelEvent，
对应 1,795 次已核验但未提交到该轮 LAST 的更新消耗；根因未确立。
Windows Job 不能保证操作系统/GPU 驱动崩溃后的状态持久化。
未来应保持供电和通风、记录温度/驱动/事件，仍禁止自动重试或退款。
安全暂停应等完整 epoch、完整开发验证及 LAST 提交后退出，
B1 常态剩余等待可能超过一小时，慢轮可更久；紧急停止后需重新核对具体 LAST 和额度。

\section{论文可用结论及下一步验证目标}
目前支持 H-O 的单 seed 开发性方向证据；H-Q 仅 B0 较明确，B1 尚不稳健。
时序输入有总体排序和平均 CP 的贡献，但欠覆盖、强雨层与高条件上尾风险仍存在。
未建立全面优越性、独立物理验证、未来年份泛化、确认性显著性或严格业务近实时能力。
IMERG V07 Final 仍是回顾性监督参考，不是业务可获取延迟证据。

剩余预定义 seeds 2027/2028 最应检验：H-O 方向是否跨初始化稳定；
H-Q 是否为 B0 特有或可复现于 B1；覆盖改善是否伴随 CP/强雨/上尾副作用；
B1 总体贡献能否在三个 seed 稳定而不牺牲最高雨强。
应逐 seed 报告，再讨论初始化变异，不把三个 seed 当作新增独立天气样本。
禁止根据当前六组修改阈值、资格、层边界或实验配方。本轮没有启动剩余十二组。

\section{复现文件与审查记录}
入口为 \texttt{analysis/analyze.py}、\texttt{plot.py}、\texttt{report.py}。
十个图均附 SVG/PDF/600 dpi PNG，所有表格保留 CSV 全精度。
分析以 Git \texttt{dbccf220e8e88178388433e3d69e4e0e9682d652} 为公开证据基线；
发布 commit 另见交付记录。输入、代码及图表的 SHA 见 manifest。
本轮仅重新汇总已发表统计及登记资源日志；AUROC/AP 沿用精确分数并列口径的已发布值，
没有重新读取全像元 score 数据库或运行推理。
完整 span 分布、逐位置概率与极端 q32 的联合诊断、独立站点/雷达核实均未补造。

初次分析环境版本元数据读取因隔离目录 ACL 失败；同一脚本以获准正常用户令牌重跑后通过，
没有降低数值容差。首遍备份搜索上限收据及修复记录保留。
本轮新优化器更新、模型推理、原始观测内容读取均为零；权重仅作 SHA。
历史恢复治理和 2025 路径属性未计数事实仍保留，不追认、不追溯清零。
\end{document}
''')
    (OUT/'paper/main.tex').write_text('\n'.join(chunks),encoding='utf-8')
    print('REPORT_SOURCE_GENERATED')

if __name__=='__main__':main()
