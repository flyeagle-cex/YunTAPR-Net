"""Bind unchanged published sources, actual test records and editable teaching text."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/phase_b_v2_candidates"))
from build_delivery import markdown_tex, escape
OUT = REPO / "docs/phase_b_v2_ablation_implementation/v1"
SOURCE = REPO / "src/yuntapr/experimental/phase_b_v2_ablations"
BASELINE = "c6d938f4afc7780b29caf3ae84cfc2ef8ff70ed9"
DOCS = ["IMPLEMENTATION_ARCHITECTURE.md", "ABLATION_CONFIG_CONTRACT.md", "VALIDATION_WALKTHROUGH.md",
        "FOCAL_LOSS_WALKTHROUGH.md", "PINBALL_LOSS_WALKTHROUGH.md", "TOTAL_LOSS_WALKTHROUGH.md",
        "METRICS_WALKTHROUGH.md", "E0_COMPATIBILITY_REPORT.md", "SYNTHETIC_GRADIENT_TEST_REPORT.md",
        "RUNNER_INTEGRATION_PROPOSAL.md", "READINESS_WALKTHROUGH.md", "RESEARCHER_REVIEW_CHECKLIST.md",
        "RESEARCHER_CODE_STUDY_GUIDE.md"]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def new_text(path, text):
    with path.open("x", encoding="utf-8", newline="\n") as stream: stream.write(text)


def new_json(path, data): new_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def with_code_blocks(text):
    pieces = text.split("```python\n")
    rendered = markdown_tex(pieces[0])
    for part in pieces[1:]:
        code, rest = part.split("```", 1)
        rendered += "\n\\begin{lstlisting}\n" + code + "\\end{lstlisting}\n" + markdown_tex(rest)
    return rendered


def main():
    current = json.loads((OUT / "tests/synthetic_attempt_008.json").read_text(encoding="utf-8"))
    cuda = json.loads((OUT / "tests/cuda_attempt_004.json").read_text(encoding="utf-8"))
    if current["counts"]["passed"] != 177 or cuda["counts"]["passed"] != 3: raise ValueError("Tests not confirmed")
    # Preserve the first actual XML before redacting only its machine hostname.
    first = OUT / "tests/synthetic_attempt_001.xml"
    new_text(OUT / ".local/synthetic_attempt_001.unredacted.xml", first.read_text(encoding="utf-8"))
    tree = ET.parse(first)
    for node in tree.iter():
        if "hostname" in node.attrib: node.attrib["hostname"] = "REDACTED_HOST"
    tree.write(first, encoding="utf-8", xml_declaration=True)
    first_log = (OUT / ".local/synthetic_attempt_001.full.log").read_text(encoding="utf-8")
    new_text(OUT / "tests/synthetic_attempt_001.log", first_log.replace(str(REPO), "<WORKSPACE>"))
    new_json(OUT / "tests/failure_and_repair_history.json", {
        "scope": "ACTUAL_ENVIRONMENT_AND_COLLECTION_FAILURES_NOT_SCIENTIFIC_PERFORMANCE",
        "events": [{"attempt": "synthetic_attempt_002", "outcome": "COLLECTION_ERROR_yaml_missing",
                    "repair": "Extract only the unchanged pure mathematical LR function AST, no frozen module import"},
                   {"attempt": "cuda_attempt_001", "outcome": "TIMEOUT_60_SECONDS_0_COMPLETED_TESTS",
                    "context": "Old torch2.7.1+cu118 emitted unsupported sm_120 warning in initial probe",
                    "repair": "Use the existing project cu128 environment located through published engineering metadata"},
                   {"attempt": "synthetic_attempt_005_and_cuda_attempt_002", "outcome": "pytest_missing_NO_TEST_STARTED",
                    "repair": "Install pytest9.1.1 only in task-local target; do not modify project runtime"}],
        "test_tolerances_loosened": False, "final_cpu_passed": 177, "final_cuda_passed": 3,
        "formal_parameters_updated": 0})
    old = json.loads((REPO / "docs/phase_b_v2_ablation_preregistration/v1/source_identity.json").read_text(encoding="utf-8"))
    refs = {r["path"]: r for r in old["repository_files"]}
    for name in ("LOSS_MATHEMATICS_AND_RESEARCHER_EXERCISE.md", "SAFE_IMPLEMENTATION_HANDOFF.md", "TEST_PLAN.md",
                 "protocol_proposed.json", "manifest.json", "publication_receipt.json"):
        path = REPO / "docs/phase_b_v2_ablation_preregistration/v1" / name
        refs[path.relative_to(REPO).as_posix()] = {"path": path.relative_to(REPO).as_posix(), "sha256": sha(path),
                                                  "bytes": path.stat().st_size, "kind": "PUBLISHED_PREREGISTRATION_METADATA"}
    for ref in refs.values():
        if sha(REPO / ref["path"]) != ref["sha256"]: raise ValueError("Historical source changed")
    new_json(OUT / "source_identity.json", {"baseline_commit": BASELINE,
        "recorded_utc": datetime.now(timezone.utc).isoformat(), "repository_files": list(refs.values()),
        "frozen_code_locations": old["code_locations"], "external_pins": old["external_pins"],
        "raw_files_opened": 0, "private_checkpoint_files_opened": 0,
        "original_evidence_modified": False, "new_scientific_approval": "NOT_GRANTED",
        "delegation_scope": "Candidate implementation and synthetic loss/autograd testing expressly requested this turn; not formal execution"})
    overview = """# 研究者代码学习手册与注释源码副本

本轮研究者已委托Codex先实现候选，再由研究者学习与独立审查。以下副本与实际候选源码按SHA绑定，不是另一份可导入模块；修改学习副本不会修改真实实现。所有代码属于候选，最终科学决定仍由研究者作出。

## 建议学习顺序与小练习

1. config.py：先理解函数/关键字参数、dataclass、tuple和type检查。练习写出三臂的唯一不同项，手算18身份和每run47052更新。
2. validation.py：理解[B,C,H,W]、bool索引、shape/device/dtype与交集。练习画出两个mask交集，并解释invalid reference临时clean不等于修改源数据。
3. focal.py：对照F1–F4，先手算gamma0值/梯度，再理解gamma2对权重也求导。练习指出误删alpha会如何改变E1。
4. pinball.py：先看signed errors内核，再看公开严格q入口。练习手算高tau欠/过预测惩罚，解释mean32与sum像元的顺序。
5. total.py和metrics.py：用T1/T2核对两个分母、lambda一次与无雨None。练习合并两个不同雨数batch的CPB。
6. test_gradients.py：认识requires_grad、叶子、grad_fn、backward、autograd.grad及finite difference。练习从链式法则推导q梯度的lambda/N_valid因子。
7. readiness.py：阅读metadata而非真实state，尝试仅在个人合成副本中更改一个SHA，理解BLOCKED与数学PASS的区别。

## 共同语法与计算图

from .config是包内相对导入，__all__只定义公开名称，不授予权限。->Tensor、tuple[int,...]等是类型提示，不能替代if/raise检查。@dataclass自动生成构造与比较，frozen阻止普通字段重赋值但不冻结内部dict/Tensor。@property允许以属性形式读派生值；@classmethod的cls代表类。

Python中的and/or短路有助在错误dtype之前停止；type(x)is int排除bool。with上下文离开后恢复autocast设置。torch.where返回新Tensor；bool索引选择元素，.movedim重新安排轴，.squeeze(1)只删单例通道。reshape不等于detach，类型转换也保留可微路径。

forward是由输入算出loss并构图；backward按链式法则累加叶子.grad。autograd.grad直接返回梯度，默认不会像backward一样累加到.grad。detach/no_grad用于报告分支，不能放到训练loss中截断梯度。gradcheck把自动微分与FP64中央差分比较；在折点不适用唯一经典导数。当前仅合成叶子参与图，没有模型参数更新或Optimizer。

工程保护包括finite/shape/device/type拒绝、SHA检查和BlockedRunner；科学定义包括alpha/gamma、32tau、log域、雨阈值和分母。两者都重要，但工程PASS不能自动批准科学假设。[PyTorch autograd](https://docs.pytorch.org/docs/2.7/notes/autograd.html)及[混合精度说明](https://docs.pytorch.org/docs/2.7/amp.html)提供API背景；项目公式与来源定位见对应walkthrough/source_identity。

## 测试和交付工具也应理解

conftest.py的autouse fixture在每个测试前禁止step、torch.load/save和expm1，结束后由monkeypatch恢复原方法。synthetic_case只用linspace/arange/tensor构造小张量，clone().requires_grad_()建立可观察梯度的叶子。rate/masks没有梯度。test_losses用手算和冻结函数，不与新实现自己互证；test_gradients用解析式/差分；test_readiness只改内存metadata；test_cuda是可选独立进程的三臂CPU/GPU对照。

run_checks.py调用pytest子进程而不是模型runner，60秒timeout会终止自己启动的测试进程，保存完整输出与XML，不中断别人的任务。static_review.py只AST与SHA，无torch import；author_delivery.py/后续export/close工具处理文档和元数据，不读观测或权重。若修改真实候选源码，必须重新测试并用新版本身份归档，不能只改副本或覆盖已发表结果。
"""
    catalogue = []
    for name in ("__init__.py", "config.py", "validation.py", "focal.py", "pinball.py", "total.py", "metrics.py", "readiness.py"):
        path = SOURCE / name; code = path.read_text(encoding="utf-8"); tree = ast.parse(code)
        overview += f"\n## {name}：实际源码、函数位置与副本\n\n来源src/yuntapr/experimental/phase_b_v2_ablations/{name}；SHA256={sha(path)}。参数语义、形状、dtype和异常按对应walkthrough逐段阅读。副本保留实际docstring与行内注释，顺序与源码完全相同。\n\n"
        overview += "|函数或方法|源码行|阅读入口|\n|---|---|---|\n"
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                signature = ast.unparse(node.args)
                overview += f"|{node.name}({signature.replace('|', '/')} )|{node.lineno}|见上列对应模块说明与下面源码|\n"
                catalogue.append({"path": path.relative_to(REPO).as_posix(), "symbol": node.name,
                                  "line": node.lineno, "end_line": node.end_lineno})
        overview += "\n```python\n" + code + "```\n"
    new_text(OUT / "RESEARCHER_CODE_STUDY_GUIDE.md", overview)
    new_json(OUT / "candidate_function_index.json", {"scope": "NEW_CANDIDATE_SOURCE_AST", "functions": catalogue})
    header = r"""\documentclass[UTF8,fontset=fandol,10pt]{ctexart}
\usepackage[a4paper,margin=19mm]{geometry}
\usepackage{amsmath,amssymb,array,longtable,booktabs,url,listings,xcolor,fancyhdr}
\usepackage[colorlinks=true,linkcolor=blue,urlcolor=blue]{hyperref}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{YunTAPR-Net / candidate loss implementation}
\fancyhead[R]{2026-10-10 / v1}\fancyfoot[C]{\thepage}\setlength{\headheight}{14pt}
\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}\setlength{\emergencystretch}{3em}
\lstset{language=Python,basicstyle=\ttfamily\scriptsize,columns=fullflexible,breaklines=true,
breakatwhitespace=false,numbers=left,numberstyle=\tiny,numbersep=5pt,xleftmargin=8pt,
frame=single,keepspaces=true,showstringspaces=false,tabsize=4}
\title{YunTAPR-Net\\Phase-B v2 消融候选实现\\合成验证与研究者代码学习材料}
\author{工程候选 / 独立科学审查仍待研究者}\date{2026年10月10日 / v1}
\begin{document}\maketitle
\textbf{实际实现与合成验证已完成；正式科学协议和训练仍未批准。}

CPU 177 / CUDA 3 合成测试通过，静态检查11项；没有模型forward、optimizer step、原始观测或checkpoint读取。
本轮开发委托替代上轮候选阶段的练习先行顺序，但不接受Phase-A科学结果或追认历史B1恢复。
\setcounter{tocdepth}{1}\begingroup\small\setlength{\parskip}{0pt}\tableofcontents\endgroup
"""
    formulas = r"""
\clearpage\section{关键数学、解析梯度与源码对应}
\(v=m_{\rm IMERG}\land m_{\rm Yunnan}\)，\(z=\mathbf1\{y_{32}>\operatorname{float32}(0.1)\}\)，
\(N_v=\sum v\)，\(N_r=\sum vz\)；比较在提升精度前完成。
\begin{align*}
b(l,z)&=\max(l,0)-lz+\log(1+e^{-|l|}),&p_t&=e^{-b},\\
\alpha_z&=\alpha z+(1-\alpha)(1-z),&S_o&=\sum v\alpha_z(1-p_t)^\gamma b,\\
\tau_i&=(i-0.5)/32,&e_i&=\log(1+y)-q_i,\\
\rho_{\tau_i}(e_i)&=\max(\tau_i e_i,(\tau_i-1)e_i),&S_q&=\sum vz\,\frac1{32}\sum_i\rho_{\tau_i}(e_i),\\
L_{\rm train}&=(S_o+\lambda_q S_q)/N_v,&\operatorname{CPB}&=S_q/N_r.
\end{align*}
Focal对应focal.py中的BCEWithLogits、exp、pow、sum；Pinball对应pinball.py中的固定tau、maximum、mean、sum；total.py只乘一次lambda。\(\gamma=0,\alpha=.5\)仍为\(.5\,\mathrm{BCE}\)。CPB不带权重，无雨不可估计。
\[
\frac{\partial S_o}{\partial l}=\alpha_z(p-z)\{m^\gamma+\gamma b p_t m^{\gamma-1}\},\quad m=1-p_t,\quad\gamma>0;
\qquad\gamma=0:\ \alpha_z(p-z).
\]
\[
\frac{\partial L}{\partial q_i}=\frac{\lambda_q}{32N_v}\begin{cases}-\tau_i,&e_i>0,\\1-\tau_i,&e_i<0.\end{cases}
\]
以上梯度仅在有效位置并按相应雨标签生效；\(e=0\)为折点。test\_gradients.py独立核对解析式、FP64差分和全部32tau；不是实际模型性能结论。
\[
\eta(u)=\begin{cases}10^{-4}u/5228,&1\le u\le5228,\\
10^{-6}+(10^{-4}-10^{-6})\dfrac{1+\cos(\pi(u-5228)/(261400-5228))}{2},&5228<u\le47052.\end{cases}
\]
config.py的learning\_rate\_prefix逐位置与冻结纯数学函数对照；没有optimizer或正式更新。BlockedRunner只抛错。V2\_PHASE\_B\_AUTHORIZED=false，历史恢复NOT\_GRANTED，2025访问0。工程交付到此停止。
\end{document}
"""
    body = "\n".join(with_code_blocks((OUT / name).read_text(encoding="utf-8")) for name in DOCS)
    new_text(OUT / "PHASE_B_V2_IMPLEMENTATION_STUDY.tex", header + body + formulas)
    new_json(OUT / "report_source_binding.json", {"source_markdown": [{"path": p, "sha256": sha(OUT/p)} for p in DOCS],
        "tex_sha256": sha(OUT / "PHASE_B_V2_IMPLEMENTATION_STUDY.tex"), "new_figures": 0,
        "code_copy_role": "Exact commented source copies in Markdown and LaTeX, not executable modules"})
    print(json.dumps({"docs": len(DOCS), "published_source_refs": len(refs), "candidate_functions": len(catalogue)}))


def reflow_unpublished():
    """Only reflow current unpublished text; preserve the prior source."""
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
    tex = OUT / "PHASE_B_V2_IMPLEMENTATION_STUDY.tex"
    tracked = subprocess.check_output(["git", "ls-tree", "--name-only", "HEAD", "--", tex.relative_to(REPO).as_posix()], cwd=REPO)
    if head != BASELINE or tracked: raise ValueError("Published report cannot be reflowed")
    previous = tex.read_text(encoding="utf-8")
    new_text(OUT / ".local/source_before_reflow.tex", previous)
    guide = OUT / "RESEARCHER_CODE_STUDY_GUIDE.md"
    text = guide.read_text(encoding="utf-8")
    new_text(OUT / ".local/study_guide_before_reflow.md", text)
    text = re.sub(r"来源(src/[^；]+)；SHA256=([0-9a-f]{64})。", r"来源 \1。\n\nSHA256：\2。", text)
    for name in ("__init__.py", "config.py", "validation.py", "focal.py", "pinball.py", "total.py", "metrics.py", "readiness.py"):
        tree = ast.parse((SOURCE / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                old = ast.unparse(node.args).replace("|", "/")
                args = [a.arg for a in node.args.args]
                if node.args.kwonlyargs: args += ["*"] + [a.arg for a in node.args.kwonlyargs]
                if node.args.vararg: args += ["*" + node.args.vararg.arg]
                if node.args.kwarg: args += ["**" + node.args.kwarg.arg]
                text = text.replace(f"|{node.name}({old} )|{node.lineno}|", f"|{node.name}({', '.join(args)})|{node.lineno}|")
    guide.write_text(text, encoding="utf-8", newline="\n")
    header = previous[:previous.index(r"\clearpage\section{")]
    formulas = previous[previous.index(r"\clearpage\section{关键数学"):]
    body = "\n".join(with_code_blocks((OUT / name).read_text(encoding="utf-8")) for name in DOCS)
    tex.write_text(header + body + formulas, encoding="utf-8", newline="\n")
    new_json(OUT / "tests/report_reflow_repair.json", {"cause": "Two prose overflows and missing membership glyph",
        "repair": "Space signature commas, separate source/hash paragraphs, write set-membership in prose; table lists parameter names with exact types retained in source copy",
        "scientific_definitions_or_candidate_code_changed": False, "prior_tex_sha256": hashlib.sha256(previous.encode()).hexdigest(),
        "after_tex_sha256": sha(tex)})


def refresh_final_unpublished():
    """Reflect a verified scalar-device repair without altering prior records."""
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
    tex = OUT / "PHASE_B_V2_IMPLEMENTATION_STUDY.tex"
    tracked = subprocess.check_output(["git", "ls-tree", "--name-only", "HEAD", "--", tex.relative_to(REPO).as_posix()], cwd=REPO)
    if head != BASELINE or tracked: raise ValueError("Published report cannot be refreshed")
    previous = tex.read_text(encoding="utf-8")
    new_text(OUT / ".local/source_before_final_refinement.tex", previous)
    for name in ["README.md", "E0_COMPATIBILITY_REPORT.md", "SYNTHETIC_GRADIENT_TEST_REPORT.md", "tests/README.md"]:
        path = OUT / name; text = path.read_text(encoding="utf-8")
        text = text.replace("synthetic_attempt_006", "synthetic_attempt_008").replace("cuda_attempt_003", "cuda_attempt_004")
        text = text.replace("CPU176", "CPU177").replace("CPU 176", "CPU 177").replace("176 passed", "177 passed")
        text = text.replace("CPU suite attempt006", "CPU suite attempt008").replace("CUDA attempt003", "CUDA attempt004")
        text = text.replace("当前独立测试用例179", "当前独立测试用例180").replace("共179个不同", "共180个不同")
        text = text.replace("CPU176/0/0", "CPU177/0/0")
        text += "\n最终边界复核的CPU007为176通过/1失败：标量设备错配应在finite算术前拒绝。代码将device检查前移并保留同形dtype合同，容差未改；CPU008=177通过/0失败，CUDA004=3通过/0失败。详见tests/scalar_device_repair.json与原失败日志。\n" if name != "README.md" else ""
        path.write_text(text, encoding="utf-8", newline="\n")
    guide = OUT / "RESEARCHER_CODE_STUDY_GUIDE.md"
    text = guide.read_text(encoding="utf-8")
    new_text(OUT / ".local/study_guide_before_final_refinement.md", text)
    sections = re.split(r"\n## ([^\n]+)：实际源码、函数位置与副本\n", text)
    result, catalogue = sections[0], []
    for index in range(1, len(sections), 2):
        name = sections[index]; path = SOURCE / name; code = path.read_text(encoding="utf-8")
        result += f"\n## {name}：实际源码、函数位置与副本\n\n来源 src/yuntapr/experimental/phase_b_v2_ablations/{name}。\n\nSHA256：{sha(path)}。参数语义见对应walkthrough；下面是实际完整注释源码副本。\n\n"
        result += "|函数或方法（参数名）|源码行|阅读入口|\n|---|---|---|\n"
        for node in ast.walk(ast.parse(code)):
            if isinstance(node, ast.FunctionDef):
                args = [a.arg for a in node.args.args]
                if node.args.kwonlyargs: args += ["*"] + [a.arg for a in node.args.kwonlyargs]
                if node.args.vararg: args += ["*" + node.args.vararg.arg]
                if node.args.kwarg: args += ["**" + node.args.kwarg.arg]
                result += f"|{node.name}({', '.join(args)})|{node.lineno}|完整type/default见下面源码|\n"
                catalogue.append({"path": path.relative_to(REPO).as_posix(), "symbol": node.name,
                                  "line": node.lineno, "end_line": node.end_lineno})
        result += "\n```python\n" + code + "```\n"
    guide.write_text(result, encoding="utf-8", newline="\n")
    index_path = OUT / "candidate_function_index.json"
    new_text(OUT / ".local/function_index_before_final_refinement.json", index_path.read_text(encoding="utf-8"))
    index_path.write_text(json.dumps({"scope": "NEW_CANDIDATE_SOURCE_AST", "functions": catalogue}, indent=2), encoding="utf-8")
    header = previous[:previous.index(r"\clearpage\section{")].replace("CPU 176", "CPU 177")
    formulas = previous[previous.index(r"\clearpage\section{关键数学"):]
    body = "\n".join(with_code_blocks((OUT / name).read_text(encoding="utf-8")) for name in DOCS)
    tex.write_text(header + body + formulas, encoding="utf-8", newline="\n")
    new_json(OUT / "tests/scalar_device_repair.json", {"failure": "synthetic_attempt_007: 176 passed, 1 failed",
        "cause": "combine_numerators checked finite before numerator device equality",
        "repair": "Reject device mismatch and unsupported device before any scalar tensor arithmetic",
        "loss_formula_changed": False, "tolerances_changed": False,
        "final_cpu": "synthetic_attempt_008:177 passed/0 failed", "final_cuda": "cuda_attempt_004:3 passed/0 failed",
        "initial_failure_history_record_role": "failure_and_repair_history.json preserves pre-final-refinement state"})


if __name__ == "__main__":
    if "--refresh-final" in sys.argv: refresh_final_unpublished()
    elif "--reflow" in sys.argv: reflow_unpublished()
    else: main()
