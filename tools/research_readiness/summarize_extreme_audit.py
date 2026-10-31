"""Typeset existing extreme-audit results with editable TeX and PDF attachments.

No model, meteorological payload, training, inference, or metric recomputation.
"""
import argparse,csv,hashlib,json,re,shutil,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
AUDIT=ROOT/'docs/research_readiness/20261031_extreme_precipitation_audit'
STEM='YunTAPR-Net_V1.3_极端降水审计结果汇总_20261031'

def escape(v):
    s=str(v)
    return ''.join({'\\':r'\textbackslash{}','_':r'\_','%':r'\%','&':r'\&','#':r'\#','{':r'\{','}':r'\}','$':r'\$'}.get(c,c) for c in s).replace('−','$-$')
def number(v,d=6):return '未定义' if v in ('',None) else f'{float(v):.{d}f}'
def pct(v,d=4):return '未定义' if v in ('',None) else f'{float(v)*100:.{d}f}'
def signed(v,d=6,scale=1):return f'{float(v)*scale:+.{d}f}'
def tex_table(headers,rows,spec=None,size='small'):
    spec=spec or ('l'+'r'*(len(headers)-1))
    return '\n'.join([r'\begin{center}'+'\n'+chr(92)+size,r'\begin{tabular}{@{}'+spec+r'@{}}',r'\toprule',' & '.join(headers)+r' \\',r'\midrule',*(' & '.join(map(str,row))+r' \\' for row in rows),r'\bottomrule',r'\end{tabular}',r'\end{center}'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);a.work.mkdir(parents=True,exist_ok=True)
    tex_path=a.output/(STEM+'.tex');pdf_path=a.output/(STEM+'.pdf')
    if tex_path.exists() or pdf_path.exists():raise PermissionError('Never overwrite a previous delivery')
    csv_path=AUDIT/'EXTREME_PRECIPITATION_AUDIT.csv';md_path=AUDIT/'EXTREME_PRECIPITATION_AUDIT.md'
    with csv_path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    assert len(rows)==1400
    def select(**conditions):return [r for r in rows if all(r.get(k)==str(v) for k,v in conditions.items())]
    def one(**conditions):
        found=select(**conditions)
        if len(found)!=1:raise ValueError(f'Ambiguous saved result: {conditions}: {len(found)}')
        return found[0]
    models=('B4','B7','B8');seeds=(2029,2030,2031)
    cp=select(record_type='CHECKPOINT_CONFIG');assert len(cp)==9 and all(r['status']=='PASS' for r in cp)
    main=select(record_type='CLASSIFICATION',method='A')
    class_rows=[]
    for m in models:
        for s in seeds:
            for threshold in (5.,10.,20.):
                r=one(record_type='CLASSIFICATION',model=m,seed=s,method='A',threshold_mm_h=threshold)
                class_rows.append([m,s,int(threshold),r['TP'],r['FP'],r['FN'],pct(r['CSI']),pct(r['POD']),pct(r['FAR']),pct(r['Precision'])])
    classes=tex_table(['模型','seed','$r$','TP','FP','FN',r'CSI(\%)',r'POD(\%)',r'FAR(\%)',r'Precision(\%)'],class_rows,size='footnotesize')
    detection=[]
    for comparison in ('B7−B4','B8−B4','B8−B7'):
        for threshold in (5.,10.):
            r=one(record_type='PAIRED_SEED_SUMMARY',comparison=comparison,original_record_type='CLASSIFICATION',method='A',threshold_mm_h=threshold,metric='CSI')
            detection.append([escape(comparison),int(threshold),signed(r['value'],5,100),number(float(r['sample_sd'])*100,5),r['improved_seeds']+'/'+r['n_seeds']])
    detect_table=tex_table(['比较','$r$ (mm/h)',r'$\Delta$CSI均值(pp)','样本SD(pp)','改善seed'],detection)
    rain=[];peak=[]
    for m in models:
        for s in seeds:
            a20=one(record_type='RAIN_STRATUM',model=m,seed=s,group='(20,30]')
            a30=one(record_type='RAIN_STRATUM',model=m,seed=s,group='(30,50]')
            a50=one(record_type='RAIN_STRATUM',model=m,seed=s,group='>50')
            both=one(record_type='RAIN_STRATUM',model=m,seed=s,group='(20,50]')
            rain.append([m,s,number(a20['conditional_pinball']),number(a30['conditional_pinball']),number(a50['conditional_pinball']),pct(both['q32_coverage'],3) if both['q32_coverage'] else '缺明细'])
            bound=one(record_type='PEAK_UNDERESTIMATE_LOWER_BOUND',model=m,seed=s,method='A')
            peak.append([m,s,number(bound['value'],5)])
    rain_table=tex_table(['模型','seed','Pinball(20,30]','Pinball(30,50]','Pinball$>50$',r'q32(20,50](\%)'],rain,size='footnotesize')
    rain_summary=[]
    for comparison in ('B7−B4','B8−B4','B8−B7'):
        for band in ('(20,30]','(30,50]'):
            r=one(record_type='PAIRED_SEED_SUMMARY',comparison=comparison,original_record_type='RAIN_STRATUM',group=band,metric='conditional_pinball')
            rain_summary.append([escape(comparison),band,signed(r['value'],8),number(r['sample_sd'],8),r['improved_seeds']+'/'+r['n_seeds']])
    rain_summary_table=tex_table(['比较','雨强层(mm/h)',r'$\Delta$Pinball均值','样本SD','改善seed'],rain_summary)
    csi_a5=one(record_type='PAIRED_SEED_SUMMARY',comparison='B8−B7',original_record_type='CLASSIFICATION',method='A',threshold_mm_h=5.,metric='CSI')
    strong=one(record_type='PAIRED_SEED_SUMMARY',comparison='B7−B4',original_record_type='SAVED_SCENE_OR_UTC_SUBGROUP',group='scene_max_ge20',metric='brier')
    assert strong['improved_seeds']=='3' and csi_a5['improved_seeds']=='1'
    source_commit='cfe525b30db6fc7c36c578d7904da9238d71e7cd'
    csv_sha=hashlib.sha256(csv_path.read_bytes()).hexdigest();md_sha=hashlib.sha256(md_path.read_bytes()).hexdigest()
    population=tex_table(['项目','已核实结果'],[
        ['模型/随机性','B4、B7、B8；2029/2030/2031；共9个模型配置'],
        ['训练与评价','E0、固定E9 LAST；2023 Train=959、2024 Dev=963'],
        ['有效监督/有雨像元时次','3,303,090 / 407,820（有雨定义$R>0.1$）'],
        ['$R>5$ / $R>10$','25,661 / 5,516个像元时次'],
        ['$R>20$','717个像元时次、207个采样窗口'],
        [r'$R\ge20$','至少718个像元时次、208个采样窗口'],
        ['$R>50$','6个像元时次、5个采样窗口'],
        ['独立极端天气事件数','不可识别，不能用像元/窗口/周块数量代替'],
    ],spec='lp{116mm}')
    doc=r'''\documentclass[UTF8,a4paper,10pt,fontset=none]{ctexart}
\usepackage[margin=18mm,headheight=15pt]{geometry}
\usepackage{amsmath,booktabs,array,tabularx,xcolor,fancyhdr,hyperref}
\setmainfont{Arial}
\setCJKmainfont{Microsoft YaHei}
\setCJKmonofont{Microsoft YaHei}
\definecolor{ink}{HTML}{18344C}
\hypersetup{unicode=true,colorlinks=true,urlcolor=ink,linkcolor=ink,pdftitle={YunTAPR-Net V1.3 极端降水审计结果汇总},pdfauthor={YunTAPR-Net Research}}
\pagestyle{fancy}\fancyhf{}\lhead{\small YunTAPR-Net V1.3}\rhead{\small 极端降水专项审计}\cfoot{\small\thepage}
\setlength{\parindent}{0pt}\setlength{\parskip}{4pt}
\setlength{\tabcolsep}{4pt}\renewcommand{\arraystretch}{1.13}
\ctexset{section={format=\large\bfseries,beforeskip=8pt,afterskip=4pt}}
\emergencystretch=2em
\newcommand{\result}[1]{\textcolor{ink}{\textbf{#1}}}
\begin{document}
{\LARGE\bfseries YunTAPR-Net V1.3}\par
{\Large 极端降水审计结果汇总}\par
2026年10月31日\quad 2024 Development\quad 研究者主导，AI辅助证据整理

\section*{1. 先看结论}
\result{当前没有证据表明B7/B8已经取得稳定的强雨点检出增益。}
九个模型配置在A/B/C三种点估计下，严格$R>20$ mm/h均为
\[
 TP=0,\quad FP=0,\quad FN=717,\quad CSI=POD=0.
\]
这些717个像元时次来自相同标签人口，不能乘以模型或seed数量当成新增独立样本。

\textbf{有限正面结果：}B7相对B4在20--30和30--50 mm/h的条件Pinball各有2/3 seed改善；208个强雨发生窗口的总体Brier改善3/3，但窗口还含弱雨和无雨像元，不能等同于极端雨强校准改善。

\textbf{主要反例：}B8相对B7在上述两个强雨层均仅1/3 seed改善，平均Pinball退化；A方案5 mm/h的CSI也仅1/3 seed改善。总体AUROC收益不能替代极端检出、尾部校准或物理机制证据。

\section*{2. 样本、身份与单位}
@@POPULATION@@

九份E9权重SHA256均与索引及原收据一致；共同人口、掩膜、有效性口径与同seed的E9训练顺序一致。使用GADM4.1中心点行政区mask，SP04裁剪100$\times$100、3430有效点；GFS固定f006、回顾估计，分析时刻00/06/12/18 UTC。

\result{阈值边界不能混用：}$>20$有207个窗口，$\ge20$有208个，至少一个窗口最大值恰为20。缺少标签/预测等于20、50的联合计数，不能把原来的$(20,50]$改称$[20,50)$。

IMERG保存单位为mm/h，30分钟累计量=雨强$\times0.5$ h；5/10/20/50 mm/h分别对应2.5/5/10/25 mm每30分钟，不能再把现有雨强标签乘2。

本次只读取已有证据；新增训练、模型推理和2025载荷访问均为0，原始数据及既有结果未覆盖。
\newpage
\section*{3. 超阈检出：A方案逐seed结果}
A=$p\,\mathrm{mean}(\exp(q)-1)$为诊断代理，\textbf{未科学冻结}。下表严格比较Pred$>r$与Truth$>r$；CSI/POD/FAR/Precision均以百分比显示。B/C原值及所有同seed差值保留在PDF附件CSV。
@@CLASSES@@
FAR=$FP/(TP+FP)$，Precision=$TP/(TP+FP)$。没有预测阳性时二者\textbf{未定义}，不能填0或解释为零虚警优势。$>50$ mm/h也可由现有计数严格补出：27组配置/点方案均TP=FP=0、FN=6、TN=3,303,084。

\textbf{A方案CSI的配对变化：}实验组减参考组；pp为百分点，正值较好。
@@DETECTION@@
$>20$的CSI差值全部为0；这表示共同没有命中，不表示模型达到相同且可接受的极端技能。固定概率阈值的判别与点估计检出也不能互换。
\newpage
\section*{4. 20--50 mm/h分位数误差与反例}
Pinball为有雨条件、冻结log1p尺度损失，越低越好，\textbf{不是mm/h的MAE}。七层原值均在附件；这里突出20--50及稀少的$>50$层。
@@RAIN@@
$(20,30]$、$(30,50]$、$>50$分别有564、147、6个像元时次。q32列针对$(20,50]$共711个像元：按真实雨强条件化的覆盖仅作描述，不要求每个雨强层达到98.4375\%名义水平。B4/2029缺逐场景尾部明细，不能填补其缺失覆盖率。

\textbf{同seed差值汇总：}负值改善；SD为三个配对差值的样本标准差。
@@RAIN_SUMMARY@@
改善次数、均值和标准差应一起看，不能只选有利seed或层。三seed是训练随机性的描述性复现，不能证明统计显著、跨年份泛化或独立天气事件稳健性。

\section*{5. 峰值低估：能证明下界，不能伪造精确误差}
QC真值峰值为68.0599976 mm/h。所有27组点估计都没有超过20的float32预测，因此真值峰值位置的低估\textbf{至少约48.06 mm/h}。为覆盖float64转float32舍入，实际计算上界使用nextafter(threshold,$+\infty$)。部分配置的下界更高，见附件。

这只是由保存计数推出的\textbf{下界}，不是精确峰值误差，也不能用下界给模型排名。强雨条件MAE/RMSE/Bias、逐事件预测峰值和峰值位置没有联合明细；已有连续误差只针对全体有效像元，不能冒充强雨误差。
\newpage
\section*{6. 归因、概率识别与仍缺的证据}
\begin{tabularx}{\linewidth}{@{}p{26mm}XX@{}}
\toprule
层次 & 现有证据 & 不能据此声称\\
\midrule
事件 & 963采样窗口，208个窗口最大值$\ge20$；$>50$的6像元在5窗口。 & 没有事件ID/追踪，不能称208或5场独立暴雨。\\
\addlinespace
高程/风/水汽 & B7/B8有三个高程边际；B4对应高程未保存；缺迎/背风和PWAT联合误差。 & 不能从边际总体误差推出高山极端或迎风抬升收益。\\
\addlinespace
DOTE & 真实数值对ZERO三seed的Brier改善3/3，但排序及强雨收益不稳；ZERO有128权重无损失梯度；PERP仅单seed。 & B7减B4还包含静态地形、参数和融合变化；负对照亦有容量/分布/空间混杂，未证物理因果。\\
\addlinespace
DTFM & B8/B7同信息、同名义活跃参数量、同seed，比较的是替换融合形式。 & 总体AUROC改善不证明极端命中、尾部校准或最终年份泛化。\\
\bottomrule
\end{tabularx}

\textbf{极端概率必须用完整混合语义：}
\[
P(R>r)=p_{\rm occ}\,[1-F_{\rm cond}(\log(1+r))].
\]
不能复用$P(R>0.1)\ge0.5$。既有D表的q32支持域因模型不同而变化，原支持子集率不能公平排名。附件另给\texttt{D\_BOUND\_PGE05}：在$q32$及以上，任何与$\tau_{32}=63/64$一致的单调尾部补全均有$P(R>r)\le1/64<0.5$，所以可补全同人口的0.5决策计数；\textbf{这没有恢复精确尾部概率、极端Brier/AUROC/AP}，也没有将未知概率设为0。

\section*{7. 下一步建议：新增训练0，先补评价缺口}
\begin{enumerate}
\item 先冻结独立事件/时间依赖定义，以及$\ge20$、$[20,50)$、$\ge50$的边界；保留原严格$>$结果作对照。
\item 从2023 Train同人口、同掩膜正雨标签确定P95/P99；明确$R>0$或$R>0.1$口径。当前没有可用完整正雨分布，不提供猜测数值，不用Dev或2025选择阈值。
\item 后续如获相应评价预算，只对\textbf{九份既有E9}各一次2024 Dev前向，保存必要的逐像元/逐场景联合量，补强雨连续误差、精确峰值及高程/风/水汽交叉统计；另需独立事件目录，四UTC前向本身不能补足天气系统追踪。
\item 暂不重训B0--B8、不加模块、不选最终模型。任何新增训练或2025揭盲仍需研究者另行明确授权。
\end{enumerate}

\section*{8. 来源与随文件保存的明细}
汇总依据已完成只读审计：109份定位源文件、九份E9身份、1400行CSV。108组点分类、27组混合概率决策界、1438个配对指标单元格已核对；492条seed统计已检验样本标准差口径。此汇总未重算原科研指标。

源交付提交：\href{https://github.com/flyeagle-cex/YunTAPR-Net/commit/@@COMMIT@@}{\texttt{cfe525b}}。PDF附件含\textbf{审计明细.csv、完整审计报告.md、文档源码.tex}；源码可提取后用XeLaTeX编辑编译。附件为脱敏版，原完整私有路径版本继续保存在本地审计交付中。

{\scriptsize CSV SHA256：\texttt{@@CSV1@@}\par\texttt{@@CSV2@@}\par
审计报告SHA256：\texttt{@@MD1@@}\par\texttt{@@MD2@@}}
\end{document}
'''
    for key,value in {'POPULATION':population,'CLASSES':classes,'DETECTION':detect_table,'RAIN':rain_table,'RAIN_SUMMARY':rain_summary_table,'COMMIT':source_commit,'CSV1':csv_sha[:32],'CSV2':csv_sha[32:],'MD1':md_sha[:32],'MD2':md_sha[32:]}.items():doc=doc.replace('@@'+key+'@@',value)
    assert '@@' not in doc and '导师' not in doc
    tex_path.write_bytes(doc.encode('utf-8'))
    engine=shutil.which('xelatex')
    if engine is None:raise RuntimeError('XeLaTeX is required; no fallback authoring format')
    command=[engine,'-no-shell-escape','-halt-on-error','-interaction=nonstopmode','-output-directory='+str(a.work.absolute()),str(tex_path.absolute())]
    result=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (a.work/'compile_stdout.txt').write_bytes(result.stdout)
    if result.returncode:raise RuntimeError('XeLaTeX failed; inspect compile_stdout.txt')
    raw=a.work/(STEM+'.pdf')
    from pypdf import PdfReader,PdfWriter
    reader=PdfReader(raw);writer=PdfWriter();writer.clone_document_from_reader(reader)
    attachments={'审计明细.csv':csv_path.read_bytes(),'完整审计报告.md':md_path.read_bytes(),'文档源码.tex':tex_path.read_bytes()}
    for name,payload in attachments.items():writer.add_attachment(name,payload)
    writer.add_metadata({'/Title':'YunTAPR-Net V1.3 极端降水审计结果汇总','/Author':'YunTAPR-Net Research','/Subject':'2024 Development;read-only extreme precipitation audit;2025 frozen'})
    with pdf_path.open('xb') as f:writer.write(f)
    saved=PdfReader(pdf_path);text='\n'.join(p.extract_text() or '' for p in saved.pages)
    for token in ('717','68.0599976','48.06','2025','P95/P99','CSI','Pinball'):assert token in text,token
    assert len(saved.pages)==4 and len(saved.attachments)==3
    for name,payload in attachments.items():assert saved.attachments[name][0]==payload
    assert not re.search(r'(?i)([A-Z]:[\\/]|chenerxiao|/Users/)',text)
    validation=dict(status='PASS_CONTENT_AND_EMBEDDED_ATTACHMENTS_PENDING_VISUAL',pages=len(saved.pages),source_commit=source_commit,pdf_sha256=hashlib.sha256(pdf_path.read_bytes()).hexdigest(),csv_sha256=csv_sha,markdown_sha256=md_sha,tex_sha256=hashlib.sha256(tex_path.read_bytes()).hexdigest(),attachments=[{'name':n,'sha256':hashlib.sha256(b).hexdigest()} for n,b in attachments.items()],saved_metric_rows=len(rows),training_updates=0,new_inference=0,final_2025='FROZEN_NO_ACCESS')
    (a.work/'validation.json').write_bytes((json.dumps(validation,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({k:v for k,v in validation.items() if k!='attachments'},ensure_ascii=True))

if __name__=='__main__':main()
