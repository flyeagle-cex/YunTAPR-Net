"""One-page editable LaTeX summary, bound to the actual safe final receipt."""
from pathlib import Path
import json
HERE=Path(__file__).absolute().parent
s=json.loads((HERE/'final_status.json').read_bytes())
if s['overall_status'] != 'BOUNDED_REAL_FORWARD_PILOT_PASS':
    raise ValueError('SUMMARY_REQUIRES_ACTUAL_PASS_RECEIPT')
g=s['resource_peaks']
text=r'''\documentclass[UTF8,10pt,a4paper]{ctexart}
\usepackage[margin=20mm]{geometry}
\usepackage{amsmath,amssymb,booktabs,url}
\setlength{\parindent}{0pt}
\setlength{\parskip}{5pt}
\begin{document}
\begin{center}\Large\bfseries YunTAPR-Net 真实前向 Pilot 审查摘要\end{center}
\textbf{仅限工程验证：}\texttt{BOUNDED\_REAL\_FORWARD\_PILOT\_PASS}。
来源基线：\path{edf883b55dd01dbf397b52224db58be85550c42a}。

\textbf{真实完成范围}\quad 复用原预检的 48 个场景及顺序：2023 Train 24 个，
2024 Development 24 个；fresh seed 2026，无历史权重。
\begin{center}
\begin{tabular}{ll}
\toprule
项目 & 实测结果 \\
\midrule
B0 / B1 前向 & 各 24 次 batch，各 48 场景；batch=2 \\
只读 payload SHA & 337 次全部匹配；295 个不同来源（含 mask） \\
原始内容读取 & __RAW__ 字节（__RAWG__ GiB） \\
CPU 工作集峰值 & __CPU__ GiB（上限 3 GiB） \\
CUDA allocated / reserved 峰值 & __GPUA__ / __GPUR__ GiB \\
本次实际执行 & __TIME__ 秒；原始总时间额度未重置 \\
\bottomrule
\end{tabular}
\end{center}
\textbf{接口与精度}\quad 输入 FP32，发生头 BF16，条件分位数 FP64：
\[
 X_0\in\mathbb R^{2\times1\times501\times501},\quad
 X_1\in\mathbb R^{2\times6\times501\times501},\quad
 p\in[0,1]^{2\times1\times100\times100},\quad
 q\in\mathbb R^{2\times32\times100\times100}.
\]
所有输出有限，$q_1>\log(1+0.1)$ 且 $q_{i+1}>q_i$。
真实云南 mask、SP04、共享 scaler 身份保持冻结；有效性与地理掩膜独立。
B0 使用 B1 最新一帧。所有 forward 在 \texttt{inference\_mode} 内，
前后模型 state SHA 相同；backward 和 optimizer 更新均为零。

\textbf{同字节消费}\quad 路径词法拒绝先于属性/打开操作；
只读句柄逐字节 SHA 匹配后转 immutable bytes，netCDF 仅解码该内存对象。
源文件关闭后可能变化，未来正式消费仍须重新校验。

\textbf{初次失败已保留}\quad 公开清单配对参数顺序错误在读取原始数据前修复。
pilot 首次包装函数与 PyTorch 延迟规则冲突，真实读取和 forward 都为零；
修复后续接继承原始时间/字节额度。新增 37 项合成单元测试通过。

\textbf{审批边界}\quad Phase-B、科学协议、正式运行和历史 B1 恢复仍未批准。
2025 像元读取为零，历史路径属性查询继续 \texttt{NOT\_INSTRUMENTED}；
未证明系统级历史零访问。旧完整预检仍为 \texttt{NOT\_VERIFIED}。
62 个选中时相引用的文件生成晚于分析时刻；观测因果通过不等于业务实时可获取。
随机初始化输出不构成任何降水性能或物理可靠性结论。

\textbf{审查来源}\quad 同目录 \path{final_status.json}、\path{FORWARD_RECEIPTS.json}、
\path{DATA_ACCESS_LEDGER.json}、\path{SCENE_PROVENANCE_RECEIPTS.json}；
源码见独立 \path{phase_b_v2_real_forward_pilot} 命名空间。
\end{document}
'''
for key,value in {
    '__RAW__':f"{s['raw_payload_content_bytes']:,}",
    '__RAWG__':f"{s['raw_payload_content_bytes']/1024**3:.3f}",
    '__CPU__':f"{g['worker_peak_working_set_bytes']/1024**3:.3f}",
    '__GPUA__':f"{g['cuda_peak_allocated_bytes']/1024**3:.3f}",
    '__GPUR__':f"{g['cuda_peak_reserved_bytes']/1024**3:.3f}",
    '__TIME__':f"{s['supervisor']['elapsed_seconds']:.3f}"}.items(): text=text.replace(key,value)
(HERE/'REAL_FORWARD_PILOT_REVIEW.tex').write_bytes(text.encode())
