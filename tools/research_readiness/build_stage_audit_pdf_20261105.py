"""Write the editable LaTeX source for a two-page evaluation audit."""
import hashlib
import json
import sys
from pathlib import Path

out=Path(sys.argv[1]); d=json.loads((out/'evaluation_data_internal.json').read_text(encoding='utf-8'))
t=json.loads((out/'terrain_reaggregation_internal.json').read_text(encoding='utf-8'))
q=json.loads((out/'terrain_distribution.json').read_text(encoding='utf-8'))
budget=d['daily']['provisional_core_estimate']
text=r'''\documentclass[UTF8,a4paper,10pt]{ctexart}
\usepackage[margin=20mm]{geometry}
\usepackage{amsmath,enumitem,xcolor,fancyhdr,hyperref}
\setCJKmainfont{Microsoft YaHei}
\setmainfont{Times New Roman}
\definecolor{ink}{HTML}{344C61}
\hypersetup{unicode=true,colorlinks=true,urlcolor=ink,linkcolor=ink}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{\small YunTAPR-Net 三类反演评价}\fancyhead[R]{\small 2026-11-05}
\fancyfoot[C]{\small\thepage}\setlength{\headheight}{15pt}
\linespread{1.0}
\ctexset{section={format=\normalsize\bfseries,beforeskip=7pt,afterskip=3pt}}
\setlength{\parindent}{0pt}\setlength{\parskip}{4pt}
\setlist{nosep,leftmargin=1.6em}
\begin{document}
{\LARGE\bfseries 三类反演评价：指标计算审计}\par
{\small 本附件记录工程计算范围、缺口与待决事项，不替代研究者作出科学结论。}

\section*{1. 已完成范围}
\begin{itemize}
\item 单时次：策略一至九共19个固定终点，五个雨强阈值的POD、FAR、CSI、HSS，以及整体RMSE和Brier Score。无预测事件等导致分母为零时显示“未定义”。
\item 高程：策略五、八、九各3个Seed，共9份已保存预测，补算三档高程、五个阈值。生成135行逐Seed原始统计，在展示表中按均值及样本标准差分行呈现。
\item 日累计：完成时间语义与日历覆盖审计，正式指标保留“待评价”。核心开发集245个UTC日期只有963个离散窗口，最多4窗/日，共同完整日为0。
\item Excel恰含指定5个页签，使用统一策略颜色、筛选、冻结表头与统一精度。原始编号、Seed和权重SHA仅保留在内部追溯页及档案；策略十只保留名称与暂缓状态。
\end{itemize}

\section*{2. 本轮确认的规则}
预测雨强采用研究者本轮确认的近似期望值：
\[
 \widehat R=p\,\frac{1}{32}\sum_{i=1}^{32}\operatorname{expm1}(q_i),
 \qquad p=P(R>0.1\,\mathrm{mm/h}).
\]
该值是条件雨强分位数的等权近似，不是精确分布期望或尾部外推。分类采用$\widehat R>r$；真值按冻结的float32阈值作严格$>$判定。RMSE使用mm/h。Brier Score继续直接使用真实发生概率$p$，不使用雨强代理概率。

\[
\mathrm{POD}=\frac{TP}{TP+FN},\quad
\mathrm{FAR}=\frac{FP}{TP+FP},\quad
\mathrm{CSI}=\frac{TP}{TP+FP+FN},
\]
\[
\mathrm{HSS}=\frac{2(TP\,TN-FP\,FN)}{(TP+FP)(FP+TN)+(TP+FN)(FN+TN)}.
\]
日界冻结为\textbf{北京时间08:00至次日08:00（对应UTC 00:00至24:00）}。按窗口开始日期命名，左闭右开；必须有48个连续、有效且无重复的30分钟窗口，预测与IMERG窗口完全相同。雨强单位为mm/h，完整日累计为$\sum_{i=1}^{48}R_i\times0.5$，单位mm/day；不完整日不参与，不补零。

\section*{3. 核验与限制}
19份既有结果的一致性门槛、检查点身份与五阈值计数全部核对通过。地形补算对1089个保存分块逐块核对SHA；读取\textbf{9,547,470,594字节}，耗时\textbf{@@SECONDS@@秒}，重试0，总体计数与RMSE均与原收据一致。共230行原始四格计数、780个展示数值通过独立复核；未发现保存公式错误。已查看五页签及关键区域渲染，未启动原生Excel应用测试。

策略一、二为10455/10501 Train/Dev，策略三至九为959/963；两种人口不得直接严格配对归因。单Seed不提供标准差，多Seed使用$n-1$样本标准差，不能把像元数当作独立事件数。全程新训练、新推理、模型加载与原始气象数据读取均0；2025最终测试未访问。

\newpage
{\LARGE\bfseries 未完成指标与研究者待决清单}\par

\section*{4. 尚未计算的指标}
\begin{enumerate}
\item \textbf{全部日累计指标。}共同完整日为0，不能回答日累计哪种策略更好，也不能判断单时次与日累计排序是否一致。四基础阈值的POD/FAR/CSI/HSS、日RMSE与Bias均为待评价。100mm/day扩展未开展。
\item \textbf{其余策略的高程指标。}策略一、二、三、四、六、七未找到可直接配高程的完整逐像元预测。不能仅凭整体统计重建分层混淆矩阵；本轮不新增推理。
\item \textbf{坡度、坡向。}已有静态数据有效，但分组尚未冻结。3430个格点坡度有效，@@SLOPE@@；范围0.0241至13.4648度。只检查分布，未评价分组成绩。
\item \textbf{W/L/M动态分位数分层。}未找到训练集冻结分位数阈值。既有迎背风符号与PWAT参考分组不能替代所要求的W/L/M分位数分层；不从开发集反选阈值。
\end{enumerate}

\section*{5. 待研究者作出的科学决定}
\begin{enumerate}
\item \textbf{日累计评价日期与输入协议。}确定各策略共同可用的完整日期；核心现有GFS为四起报时次的f006回溯场，需要先确定非既有时次的GFS对齐方式、卫星序列有效性及标签可用性。不能直接把旧采样协议扩展成连续日协议。
\item \textbf{坡度、坡向分组。}建议以冻结静态网格的坡度四分位点分组，保留未舍入边界；坡向建议四组：北$[315,360)\cup[0,45)$、东$[45,135)$、南$[135,225)$、西$[225,315)$。对应格点数630/1075/739/986。建议仍待确认。
\item \textbf{动态分层与小样本规则。}确认所需训练集W/L/M阈值来源；若不存在，另定训练集统计方案及预算。样本不足的充分性标准和独立事件定义亦未冻结；当前保留有效数、真值事件数及未定义项，不作显著性或因果判断。
\end{enumerate}
点估计规则与日界已在本轮明确确认，无需重复申请。后续任何新增推理、训练或批量原始读取均须另行明确批准。

\section*{6. 补充推理规模：仅供规划}
若覆盖2024年3至10月全部245天，每个核心终点需补\textbf{10,797个窗口}；15个核心终点共\textbf{161,955次场景前向}。按既有15次开发集遍历的实际耗时与源量线性放大，粗估串行墙钟\textbf{@@HOURS@@小时}、源读取\textbf{@@TIB@@TiB}。这不含策略一、二、标签、重新准入检查，也未证明所有缺窗都可构建；\textbf{不是可执行预算，不构成启动授权}。逐窗口日历缺口清单保留于内部档案，正式预算需在协议确定后制定。

\section*{7. 原件与实现边界}
未找到指定的20261029导师汇报原件及《科研原则.txt》。本轮使用可用20261029 Tier0工作簿作格式参考、20261031已核验收据作数值依据，并读取2026-09-24 V1.3正式方案PDF。策略一、二旧H盘路径当前不可用，继承通过一致性门槛的保存结果，不声称本轮重新验证了权重载荷。策略七实际静态通道为高程、两向米制梯度、坡度、坡向sin/cos；策略九当前为单SP04调制实现，方案名称不代表已有多尺度验证。

\end{document}
'''
text=text.replace('@@SECONDS@@',f"{t['actual_seconds']:.2f}").replace('@@SLOPE@@',
     '，'.join(f"{label}为{q['slope_quantiles_degrees'][k]:.4f}度" for label,k in (('Q25','q25'),('中位数','q50'),('Q75','q75'))))
text=text.replace('@@HOURS@@',f"{budget['linear_wall_hours']:.1f}").replace('@@TIB@@',f"{budget['linear_source_bytes']/2**40:.2f}")
(out/'YunTAPR-Net_指标计算审计_20261105.tex').write_text(text,encoding='utf-8',newline='\n')
public={k:v for k,v in t.items() if k!='rows'}
public['rows']=t['rows']
(out/'terrain_receipt_public.json').write_text(json.dumps(public,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
print('Wrote editable LaTeX audit and sanitized terrain receipt')
