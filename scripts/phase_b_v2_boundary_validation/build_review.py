"""Concise source-bound Chinese handoff and editable LaTeX; no experiment execution."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import re

REPO=Path(__file__).resolve().parents[2]
OUT=REPO/"docs/phase_b_v2_boundary_validation/v1"
BASELINE="ccfa6869672c96634fede157b06984741cc71c1b"
DOCS=("FINAL_CODE_REVIEW_HANDOFF.md","BOUNDARY_TEST_AND_RESOURCE_RESULTS.md","MODULE_REVIEW_NOTES.md")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name,text):
    with (OUT/name).open("x",encoding="utf-8",newline="\n") as stream:
        stream.write(text)


def dump(name,value):
    write(name,json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def render_markdown(text,helper):
    parts=re.split(r"(?m)^\$\$[ \t]*$",text)
    if len(parts)%2!=1:
        raise ValueError("Unclosed mathematical block")
    return "\n".join(helper.markdown_tex(part) if index%2==0 else "\\[\n"+part.strip()+"\n\\]"
                     for index,part in enumerate(parts))


def main():
    cpu=json.loads((OUT/"tests/cpu_attempt_002.json").read_text())
    cuda=json.loads((OUT/"tests/cuda_attempt_002.json").read_text())
    assert cpu["counts"]["passed"]==49 and cuda["counts"]["passed"]==12
    cases=[json.loads(p.read_text()) for p in sorted((OUT/"tests/cuda_attempt_002_evidence").glob("B*.json"))
           if not p.stem.endswith("_admission")]
    dump("SYNTHETIC_BOUNDARY_RESULTS.json",{"scope":"SYNTHETIC_ENGINEERING_ONLY","source_attempt":2,
                                          "scientific_performance_evidence":False,"cases":cases})
    index=json.loads((OUT/"review_source_index_002.json").read_text())["symbols"]
    for relative,names in {
        "src/yuntapr/models/quantile_v2/models.py":("B0MatchedV2","B1V2"),
        "src/yuntapr/experimental/phase_b_v2_integration/resources.py":("resource_snapshot","require_resources"),
        "src/yuntapr/experimental/phase_b_v2_integration/safety.py":("install_process_file_guard","synthetic_operation_guards"),
    }.items():
        path=REPO/relative; tree=ast.parse(path.read_text(encoding="utf-8"))
        for name in names:
            node=next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
            index.append({"path":relative,"function_or_class":name,"line":node.lineno,"end_line":node.end_lineno,"sha256":sha(path)})
    dump("HANDOFF_SOURCE_MAP.json",{"status":"RESEARCHER_CODE_REVIEW_REQUIRED","symbols":index,
                                  "approval_event_created":False})
    handoff=r"""# 正式集成前代码审查交接

基线 ccfa6869672c96634fede157b06984741cc71c1b。本轮完成剩余合成批次边界：49 CPU、12 CUDA、16静态项通过；原91 CPU/6 CUDA仅核对身份，未重跑。全部为 SYNTHETIC_ENGINEERING_ONLY，不能证明概率校准、q32欠覆盖或上尾问题已改善。审批状态没有升级。

## 本人应审的准确源码

路径前缀：A=src/yuntapr/experimental/phase_b_v2_ablations/；I=src/yuntapr/experimental/phase_b_v2_integration/；B=src/yuntapr/experimental/phase_b_v2_boundaries/；M=src/yuntapr/models/quantile_v2/；T=src/yuntapr/training/；F=src/yuntapr/losses/。每个函数起止行与完整SHA见 [HANDOFF_SOURCE_MAP.json](HANDOFF_SOURCE_MAP.json)；下表是同一索引中的实际符号，全部需研究者阅读，不含审批勾选。

|源文件|函数或类|本人审查重点|
|---|---|---|
|A/config.py|get_config, RunSpec, workload, learning_rate_prefix|闭合E0/E1/E2；候选种子与18身份；50epoch轨迹前9epoch|
|A/validation.py|supervision, graph_zero|FP32比较后提升；独立mask；无雨零图与零监督停止|
|A/focal.py|occurrence_numerator|稳定BCE；gamma0仍保留alpha=.5|
|A/pinball.py|frozen_taus, conditional_pinball_numerator|32tau均值、FP64、仅有雨有效像元、无物理转换|
|A/total.py|combine_numerators, candidate_loss, CandidateLossResult|lambda仅乘一次；训练N_valid和报告N_rain|
|M/models.py|B0MatchedV2, B1V2|1/6帧完整501网格；原SP04；不能替换结构|
|M/heads.py|ProbabilityHeadsV2|BF16发生；FP32 raw33；FP64输出q32|
|M/parameterization.py|normalized_monotonic_quantiles|归一化正增量与独立span，epsilon不改|
|M/outputs.py|validate_log_quantiles|严格单调、支撑和非有限值停止|
|I/initialization.py|seeded_environment, fresh_paired_models|独立reseed；同形复制；B1两输入权重保留；状态/非持久buffer身份|
|I/controls.py|synthetic_epoch_order, endpoint_boundary|seed+epoch独立排列；9epoch终点；无BEST替代|
|I/controls.py|reject_resume, reject_formal_start|缺批准永拒；字符串不是批准；不加载LAST|
|A/readiness.py|review_checkpoint_binding, BlockedRunner|具体run/LAST/code/data/init绑定；无启动能力|
|I/resources.py / safety.py|resource_snapshot, require_resources, install_process_file_guard, synthetic_operation_guards|模型构造前准入；不足停止；进程守卫不是OS沙箱|
|B/boundary.py|BoundaryBatch, make_boundary_pair, losses_from_output, forward_boundary|只允许train1、validation8/5；M1/Q1；inference_mode|
|B/boundary.py|evaluation_components, aggregate_evaluation|复用冻结FP64验证器；未加权先累加再相除|
|B/gradients.py|checked_gradients|全部参数梯度；干批分位数头零梯度；NaN/缺失停止|
|F/total_loss.py|b0_core_loss|E0数学参照；零监督返回skip标记与正式入口停止对应|
|T/phase_a_validation_v2.py|LogDomainValidation|固定gamma2，发生项FP64重算；不是训练S_occ|
|T/formal_phase_a_v2.py|paired_initialization, forward_loss, update, loader|只读对照；训练batch2尾1，验证8尾5；update本轮未调用|
|T/checkpoint_v2.py|validate_payload, verify_file, apply_verified, CheckpointStore|Phase-A 50epoch/BEST schema不能直接作B9/V0入口；后3符号未调用|

## 必须理解的公式与实际边界

valid是两个掩膜交集；rain先在原FP32参考上严格比较，不先cast到FP64。人工3430格点仅测试计数，不代表真实云南地理配准。

$$
v=m_{\mathrm{reference}}\land m_{\mathrm{artificial}},\quad
z=\mathbf1\{y_{32}>\operatorname{float32}(0.1)\},\quad
N_v=\sum v,\quad N_r=\sum vz.
$$

Focal映射A/focal.py。E0/E2的gamma=2，E1的gamma=0；所有alpha=.5。BF16 logit的BCE提升FP32，gamma0不等于未加权BCE。

$$
b=\operatorname{BCEWithLogits}(\ell,z),\quad p_t=e^{-b},\quad
S_{\rm occ}=\sum_v\alpha_t(1-p_t)^\gamma b,\quad
\alpha_t=\alpha z+(1-\alpha)(1-z).
$$

q映射M/parameterization.py：32allocation+1span原通道，正权重和FP64前缀；不是排序或截断输出。两个epsilon均1e-4，qlog支撑/单调检查仍由原函数执行。

$$
w_i=\operatorname{softplus}(a_i)+\epsilon_w,\quad
q_i=\log(1+0.1)+(\operatorname{softplus}(s)+\epsilon_s)
\frac{\sum_{j\le i}w_j}{\sum_{j=1}^{32}w_j},\quad
\tau_i=\frac{i-0.5}{32}.
$$

Pinball映射A/pinball.py与A/total.py；先均值32tau，再仅在有雨有效像元求和。lambda不进入科学Conditional Pinball。空雨时S_qr=0、图连接、CPB=None；零有效监督停止。

$$
S_{\rm qr}=\sum_{vz}\frac1{32}\sum_{i=1}^{32}
\max\{\tau_i e_i,(\tau_i-1)e_i\},\quad
e_i=\log(1+y_{32})-q_i,
$$
$$
L_{\rm train}=\frac{S_{\rm occ}+\lambda_qS_{\rm qr}}{N_v},\qquad
\mathrm{CPB}=\frac{\sum S_{\rm qr}}{\sum N_r}\ \ (\sum N_r>0).
$$

共同Core必须从T/phase_a_validation_v2.py在FP64重算固定gamma2发生分子并全局累加，使用lambda=1的未加权分位数项。不能将E1/E2的training_objective当共同Core，甚至E0训练发生分子也不是同精度的验证分子。本轮首次静态发现并修复这一差别，旧attempt完整保留。

## 尚未通过或未执行的检查

本轮定义的49 CPU/12 CUDA边界检查均通过，没有待修的数值失败；下列是未执行项，不能写成通过。

1. 真实2023/2024数据资格、冻结地理mask/SP04配准、shared scaler实际应用、真实ID顺序和读取防火墙。需要独立真实数据preflight许可，2025继续封存。
2. 正式optimizer/clip/scheduler更新事务、长时epoch循环、实际吞吐与共享GPU持续资源风险。没有step；无优化器显存测量。
3. 新v2 runner、B9终点checkpoint schema、原子写入/耐久性、故障注入和审批验真。没有私有checkpoint加载、保存或恢复。
4. 新批次边界本轮仅seed2026；另外两seed初始化与训练顺序核验使用原始已通过证据，不伪称重新覆盖。CPU完整模型forward/backward未运行，实际完整路径在CUDA执行。
5. 正式未来runner中异常停止、阶段批准、LAST绑定审批和失败后人工处置的端到端测试；当前只有隔离保护与静态候选，不能启动训练。

## 必须本人决定的科学与治理问题

全部保持 RESEARCHER_DECISION_REQUIRED：H-O/H-Q及E0/E1/E2最终科学接受；三个seed、D1/Q1/N0/I3/B9/S0/V0；Brier与q32覆盖误差主指标、完整32tau与强雨Pinball/上尾副作用；最小有意义效应、副作用界限、多重比较仍NOT_YET_ESTABLISHED；2024历史开发验证的解释范围，不能作为全新独立确认集。

Phase-A科学接受范围和B1历史恢复处置须独立决定，历史恢复仍NOT_GRANTED。数据权限、计算资源、正式集成范围、具体阶段执行及LAST恢复均另需明确授权。文档、JSON、测试PASS和Git commit不构成批准事件。

建议本人按 A/config→validation→focal/pinball/total→M/heads/parameterization→I/initialization/controls→B/boundary/gradients→测试顺序阅读；现场解释FP32阈值反例、两个分母、空雨零梯度、FP64共同验证、epoch9终点与LAST绑定。随后审查正式集成差异与独立执行授权。本轮在审批边界停止，不派生新工作包。

V2_PHASE_B_AUTHORIZED=false；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED；2025_RAW_ACCESS=2025_PIXELS_READ=0。
"""
    write(DOCS[0],handoff)
    rows=[]
    for size in (1,8,5):
        selected=[r for r in cases if r["batch_size"]==size]
        def span(key,scale):
            vals=[r["measurement"][key]/scale for r in selected]
            return f"{min(vals):.2f}–{max(vals):.2f}"
        rows.append(f"|{size}|{'train forward/backward' if size==1 else 'validation inference'}|{size*3430}|{span('peak_allocated_bytes',1048576)}|{span('peak_reserved_bytes',1048576)}|{span('forward_and_three_losses_seconds',.001)}|")
    results="""# 合成边界测试与资源实测

全部数据为人工有限张量；人工mask每场3430格点、M1全部原生像元有效、Q1参考完整。场景ID显式SYNTHETIC_ENGINEERING_ONLY，没有真实年份或路径。B0末帧取自B1六帧；模型、SP04公开映射、tau与epsilon保持原样。

最终CPU49、CUDA12、静态16通过，0失败/错误/跳过/warning。唯一pytest覆盖61；初次与复测共122个实例，不能相加作独立证据。旧91/6未重跑。两次各12完整forward/12backward，累计24/24；最终4个train1案例各3臂backward，8个validation8/5案例仅inference_mode。

|batch|语义|N_valid|allocated MiB|reserved MiB|forward+三臂loss ms|
|---|---|---|---|---|---|
"""+ "\n".join(rows)+"""

GPU为RTX5060 Laptop、PyTorch2.11.0+cu128、CUDA12.8。每例先要求主机可用≥8GiB、CUDA API free≥5GiB、工作盘≥1GiB、BF16可用，再构造原模型；验证也保守复用此门槛，snapshot的full_backward=true表示资源门槛选择，不表示验证做了backward。没有OOM、超时、降batch/精度/结构、换seed或自动重试。

每值仅一批，首例冷启动；cuda synchronize+perf_counter计时。allocator峰值包括已有合成输入、三臂loss/梯度及共同FP64评价检查，不含其他进程、AdamW状态、真实I/O、checkpoint事务或長时循环。显存准入不是容量预测，旁路进程仍会影响可用资源。

E0数值与原b0_core_loss在冻结BF16环境比较，12例通过既有rtol=8e-7/atol=1e-8；最大绝对差为 """+f"{max(r['E0_original_loss_abs_difference'] for r in cases):.17g}"+"""。本轮没有重复旧batch2全参数梯度差异检查；新batch1三臂全部74参数梯度存在、形状/dtype/有限性正确。混合有雨两头有信号；空雨分位数头梯度精确为0且不缺失，科学CPB=None。无参数改变，各例初始SHA与原seed2026证据一致。

训练N_valid分别3430/27440/17150；混合雨N_rain分别2450/19600/12250，仅为人工计数。CPU检查掩膜外NaN参考只在低层loss合成夹具中排除，不能视为M1/Q1合格模型场景。完整模型遇到缺原生帧、缺监督、非有限或身份/精度异常必须停止。

所有分子/目标数值保存在 [SYNTHETIC_BOUNDARY_RESULTS.json](SYNTHETIC_BOUNDARY_RESULTS.json)；这是工程算术而非新增降水性能指标。原始case/资源/源码快照见tests/cuda_attempt_002_evidence/。共同科学评价按冻结FP64验证器，训练objective仍各臂独立，不用于共同Core。

初次CPU49/CUDA12通过后，静态发现共同评价接口误用E0 FP32训练发生分子；已改为复用冻结FP64 LogDomainValidation，增加精确source对照，复测49/12/16通过，容差未放宽。初次测试、source index、static16之前的static15与修复说明均保留，不伪造数值失败。详见 [修复记录](tests/validation_precision_review_finding.json)。
"""
    write(DOCS[1],results)
    notes="""# 新增模块审查笔记

本轮仅3个候选Python文件与3个新测试文件；不重写旧损失或旧适配器。完整旧损失学习见 [上一轮学习材料](../../phase_b_v2_ablation_implementation/v1/RESEARCHER_CODE_STUDY_GUIDE.md)。

## boundary.py

verify_inherited_identity只核对226个既有公开文件字节；SHA说明身份，不能证明独立科学批准。BoundaryBatch是frozen dataclass，字段名固定但Tensor内容仍可变，所以每次validate。x为FP32[B,1或6,501,501]；参考FP32[B,1,100,100]；三个bool mask独立且同设备。只接受B=1/8/5和相应phase，data_years必须为空。

make_boundary_pair用arange/reshape/sin生成有限值，expand后clone使人工mask可独立检查。nextafter生成float32(0.1)上下相邻值；这是阈值教学，不是读真实降雨。B0使用最后一帧clone，明确避免输入别名。to用dataclasses.replace返回转设备副本，不能把frozen解释为深度不可变。

losses_from_output校验BF16发生与FP64 qlog、sigmoid一致、shape/有限性；沿用get_config/candidate_loss，返回三臂而非搜索参数。forward_boundary要求原模型精确类型和train/eval状态；with inference_mode(mode=not training)控制计算图；with autocast只控制冻结BF16路径，内部raw33与qlog升精度仍由原头负责。函数不做backward或step。

evaluation_components使用原LogDomainValidation重新算FP64发生分子；不是detach训练FP32分子后冒称FP64。aggregate_evaluation先fsum未加权分子与分母，再求比值；不能平均batch均值或把空雨CPB填0。lambda与gamma变化只影响训练报告。

## gradients.py与包入口

checked_gradients逐一检查parameter.grad；backward累加梯度，所以测试每臂前zero_grad(set_to_none=True)。这只是清梯度，不更新参数。train1同一输出图供三臂使用，前两次retain_graph=True，最后释放；这样只改变loss，不能声称模拟三个正式训练run。空雨graph_zero沿计算图传播0，允许梯度全0，但不允许grad缺失或NaN。包入口仅scope常量，没有runner。

## 测试与工具

test_cpu_boundaries用完整目标网格核对两个分母、float32阈值、掩膜、异常与不等批次汇总；不是CPU完整模型训练。test_cuda_boundaries每例先资源准入、再fresh原模型，再forward，train1才backward；原始权重、全参数梯度和buffer身份只存SHA/范数，不保存模型。conftest复用旧step/load/save/expm1保护；Python守卫可被进程外代码改写，不能成为正式授权认证。

run_checks调用新测试子进程，保存原始私有log及脱敏公开XML、执行时源码SHA，不自动重试。static_review只AST/文件哈希/已发表记录，不import模型。build_review/export/close只处理文档与身份；doc自身成功不构成批准。

研究者小练习：解释为何float32(0.1)先double再比较Python0.1可能错标有雨；手算batch1的3430分母；解释空雨q头zero与缺失梯度的区别；用8+5批次证明先累加分子、再相除；找出Phase-A checkpoint的50epoch/BEST字段为何不能直接替代B9/V0。
"""
    write(DOCS[2],notes)
    write("README.md","""# Phase-B v2 合成边界验证 v1

[研究者最终代码审查交接](FINAL_CODE_REVIEW_HANDOFF.md) · [测试与资源实测](BOUNDARY_TEST_AND_RESOURCE_RESULTS.md) · [新增模块笔记](MODULE_REVIEW_NOTES.md)。

最终49 CPU/12 CUDA/16静态通过；旧91/6未重跑。batch1训练forward/backward、batch8/5验证inference完成，无OOM/降级。首次共同评价FP32/FP64问题发现与修复记录完整保留。

源码src/yuntapr/experimental/phase_b_v2_boundaries/；测试tests/phase_b_v2_boundary_validation/；工具scripts/phase_b_v2_boundary_validation/。历史226文件SHA不变。只新增公开候选，实际发布身份由publication_receipt.json和Git历史给出。

[可编辑LaTeX](FINAL_CODE_REVIEW_HANDOFF.tex) · [中文PDF](FINAL_CODE_REVIEW_HANDOFF.pdf) · [源码函数/SHA索引](HANDOFF_SOURCE_MAP.json) · [最终状态](final_status.json) · [manifest](manifest.json)。

V2_PHASE_B_AUTHORIZED=false；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED；2025_RAW_ACCESS=2025_PIXELS_READ=0。本轮在研究者审批边界停止。
""")
    spec=importlib.util.spec_from_file_location("prior_review_author",REPO/"scripts/phase_b_v2_ablation_implementation/author_delivery.py")
    helper=importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    body="\n".join(render_markdown((OUT/name).read_text(encoding="utf-8"),helper) for name in DOCS)
    body=body.replace("\\clearpage\\section","\\section",1)
    header=r"""\documentclass[UTF8,fontset=fandol,10pt]{ctexart}
\usepackage[a4paper,margin=19mm]{geometry}
\usepackage{amsmath,amssymb,array,longtable,booktabs,url,xcolor,fancyhdr}
\usepackage[colorlinks=true,linkcolor=blue,urlcolor=blue]{hyperref}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{YunTAPR-Net / synthetic boundaries}
\fancyhead[R]{2026-10-10 / v1}\fancyfoot[C]{\thepage}\setlength{\headheight}{14pt}
\setlength{\parindent}{0pt}\setlength{\parskip}{4pt}\setlength{\emergencystretch}{4em}
\begin{document}
\begin{center}\Large YunTAPR-Net：Phase-B v2\\合成边界验证与最终代码审查交接
\end{center}
\noindent\textbf{SYNTHETIC\_ENGINEERING\_ONLY；研究者待审，正式执行未授权。}
"""
    write("FINAL_CODE_REVIEW_HANDOFF.tex",header+body+"\n\\end{document}\n")
    dump("report_source_binding.json",{"source_markdown":[{"path":n,"sha256":sha(OUT/n)} for n in DOCS],
         "tex_sha256":sha(OUT/"FINAL_CODE_REVIEW_HANDOFF.tex"),
         "baseline_commit":BASELINE,"source_map_sha256":sha(OUT/"HANDOFF_SOURCE_MAP.json")})
    print(json.dumps({"documents":4,"review_symbols":len(index),"tex_created":True}))


if __name__=="__main__":
    main()
