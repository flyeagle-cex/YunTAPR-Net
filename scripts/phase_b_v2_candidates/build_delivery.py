"""Build text-only candidate report; never reads raw observations or checkpoints."""
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import re
import subprocess
from planning import budget, update_budget_parts

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_b_v2_protocol_candidates/v1_20261010"
BASELINE = "6e692625ebdd9bdaeff65e22d0ce59af349d98c5"
DOCS = ["PROTOCOL_CANDIDATES.md", "HYPOTHESES_AND_ABLATIONS.md",
        "INDEPENDENT_REFERENCE_INVENTORY.md", "PHYSICAL_VERIFICATION_DESIGN.md",
        "METHODS_AND_EXPERIMENTAL_DESIGN.md", "RESEARCHER_DECISION_REQUIRED.md",
        "REFERENCES.md"]


def write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def dump_new(path: Path, value: object) -> None:
    write_new(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO).decode("utf-8").strip()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def escape(value: str) -> str:
    """Escape prose and make paths/identifiers breakable without changing source."""
    symbols = {"−":r"\(-\)", "×":r"\(\times\)", "≤":r"\(\le\)",
               "≥":r"\(\ge\)", "≠":r"\(\ne\)", "Σ":r"\(\Sigma\)",
               "∪":r"\(\cup\)", "γ":r"\(\gamma\)"}
    chars = {"\\":r"\textbackslash{}", "&":r"\&", "%":r"\%", "$":r"\$",
             "#":r"\#", "_":r"\_\allowbreak{}", "{":r"\{", "}":r"\}",
             "~":r"\textasciitilde{}", "^":r"\textasciicircum{}", "/":r"/\allowbreak{}"}
    value = value.replace("`", "")
    pieces = []
    for chunk in re.split(r"([0-9a-f]{40,64})", value):
        if re.fullmatch(r"[0-9a-f]{40,64}", chunk):
            pieces.append(r"\allowbreak{}".join(chunk[i:i+12] for i in range(0,len(chunk),12)))
        else:
            pieces.append("".join(symbols.get(c, chars.get(c,c)) for c in chunk))
    return "".join(pieces)


def inline(value: str) -> str:
    pieces, pos = [], 0
    for match in re.finditer(r"\[([^\[\]\n]+)\]\(([^)]+)\)", value):
        pieces.append(escape(value[pos:match.start()]))
        label, url = match.groups()
        # Public URL is carried by the clickable label; full sources are in REFERENCES.
        pieces.append(r"\href{"+url.replace("%",r"\%")+"}{"+escape(label)+"}" if url.startswith("https://") else escape(label))
        pos = match.end()
    pieces.append(escape(value[pos:]))
    return "".join(pieces)


def markdown_tex(text: str) -> str:
    lines, result, index = text.splitlines(), [], 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                cells = [v.strip() for v in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", v) for v in cells):
                    rows.append(cells)
                index += 1
            n = len(rows[0])
            if any(len(row) != n for row in rows):
                raise ValueError("Inconsistent Markdown table columns")
            width = r"\dimexpr(\linewidth-"+str(2*n)+r"\tabcolsep)/"+str(n)+r"\relax"
            columns = "".join(r">{\raggedright\arraybackslash}p{"+width+"}" for _ in range(n))
            result.extend([r"\begingroup\small\setlength{\tabcolsep}{3pt}\renewcommand{\arraystretch}{1.12}",
                           r"\begin{longtable}{"+columns+"}", r"\toprule"])
            for row_index, row in enumerate(rows):
                result.append(" & ".join(inline(v) for v in row)+r" \\")
                if row_index == 0:
                    result.extend([r"\midrule\endfirsthead", " & ".join(inline(v) for v in row)+r" \\", r"\midrule\endhead"])
            result.extend([r"\bottomrule\end{longtable}\endgroup"])
            continue
        if line.startswith("# "):
            result.append(r"\clearpage\section{"+inline(line[2:])+"}")
        elif line.startswith("## "):
            result.append(r"\subsection{"+inline(line[3:])+"}")
        elif line.startswith("### "):
            result.append(r"\subsubsection{"+inline(line[4:])+"}")
        elif line.startswith("- ") or re.match(r"\d+\. ", line):
            result.append(r"\noindent\textbullet\quad "+inline(re.sub(r"^(- |\d+\. )", "", line))+r"\par")
        elif re.match(r"^S\d+\.",line):
            # Long URLs in the references get a dedicated breakable URL paragraph.
            title, url, depth = line.split(" | ",2)
            result.append(inline(title)+r"\par\url{"+url.replace("%",r"\%")+r"}\par "+inline(depth)+r"\par\medskip")
        else:
            result.append(inline(line))
        index += 1
    return "\n".join(result)


def main() -> None:
    if git("rev-parse", "HEAD") != BASELINE or git("diff", "--name-only"):
        raise RuntimeError("Baseline or pre-existing tracked work changed")
    sources = json.loads((OUT/"source_registry.json").read_text(encoding="utf-8"))
    refs = ["# 引用来源与证据深度", "", "检索日2026-10-10；仅公开metadata/服务条件。搜索索引可见不等于完整文档阅读、原始数据获取或许可。网页变化与直接读取失败如实记录。", ""]
    bib = []
    for i, source in enumerate(sources["sources"],1):
        refs.append(f"S{i}. {source['publisher']}：{source['title']} | {source['url']} | {source['evidence_depth']}。支持范围：{source['supports']}。")
        refs.append("")
        bib.append("@misc{"+source["id"]+",\n  title = {"+source["title"]+"},\n  author = {{"+source["publisher"]+"}},\n  url = {"+source["url"]+"},\n  note = {Accessed 2026-10-10; "+source["evidence_depth"]+"}\n}\n")
    refs.extend(["## 本地权威证据", "", "冻结协议：config/science_contract_v1.1.yaml、config/science_v2/phase_a_protocol_frozen_v1.json；模型：src/yuntapr/models/quantile_v2/；训练与评价：src/yuntapr/training/formal_phase_a_v2.py、scientific_review.py。", "", "科学证据：docs/v2_scientific_acceptance/README.md及run_20261009T112710_013267Z/delivery_v2/；本轮引用现有聚合材料，不重跑推理或87项检查。", "", "补强：docs/phase_a_evidence_hardening/README.md、诊断、入口准备、治理复核、final_status与publication_receipt。证据commit=d9db4fad6244c18c45d6a5fa417eab8248228650，接续commit=6e692625ebdd9bdaeff65e22d0ce59af349d98c5。", "", "本轮引用不是对历史偏差的追认；新Git交付身份在追加publication_receipt中记录。", ""])
    write_new(OUT/"REFERENCES.md", "\n".join(refs))
    write_new(OUT/"references.bib", "\n".join(bib))
    with (OUT/"budget_candidates.csv").open("x",encoding="utf-8",newline="") as stream:
        fields = list(asdict(budget(10455,2,9)))
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for scenes in (10455,20956):
            for epochs in (9,17,50):
                writer.writerow(asdict(budget(scenes,2,epochs)))
    historical = ["config/science_contract_v1.1.yaml", "config/science_v2/phase_a_protocol_frozen_v1.json",
                  "config/science_v2/quantile_head_v2_frozen_v1.json", "src/yuntapr/models/quantile_v2/parameterization.py",
                  "src/yuntapr/training/scientific_review.py", "docs/phase_a_evidence_hardening/PROBABILITY_AND_TAIL_DIAGNOSTICS.md",
                  "docs/phase_a_evidence_hardening/PHASE_B_ENTRY_READINESS_CHECKLIST.md", "docs/phase_a_evidence_hardening/RECOVERY_GOVERNANCE_GAP_REVIEW.md",
                  "docs/phase_a_evidence_hardening/final_status.json", "docs/phase_a_evidence_hardening/publication_receipt.json"]
    dump_new(OUT/"baseline_snapshot.json", {
        "local_HEAD":BASELINE,"initial_remote_main_observed":BASELINE,
        "branch":git("branch","--show-current"),"tracked_dirty_at_start":False,
        "prior_delivery_checks_reexecuted":0,"historical_inputs":[{"path":p,"sha256":sha(REPO/p)} for p in historical],
        "new_v2_candidate_directory_previously_present":False,
        "preexisting_untracked_artifacts":"LEFT_UNTOUCHED_NOT_INCLUDED_IN_PUBLICATION",
        "python_training_processes_observed":0,"existing_old_v1_phase_b":"NOT_REUSED_AS_V2",
        "governance":"NO_NEW_RESEARCHER_SCIENTIFIC_OR_PHASE_B_APPROVAL_EVIDENCED; CANDIDATES_ONLY",
        "partial_epoch_example":update_budget_parts(20956,2,47052)})
    header = r"""\documentclass[UTF8,fontset=fandol,10pt]{ctexart}
\usepackage[a4paper,margin=19mm]{geometry}
\usepackage{amsmath,amssymb,array,longtable,booktabs,url}
\def\UrlBreaks{\do\/\do-\do\.\do\_\do\?\do\&\do\=\do\a\do\b\do\c\do\d\do\e\do\f\do\g\do\h\do\i\do\j\do\k\do\l\do\m\do\n\do\o\do\p\do\q\do\r\do\s\do\t\do\u\do\v\do\w\do\x\do\y\do\z\do\0\do\1\do\2\do\3\do\4\do\5\do\6\do\7\do\8\do\9}
\usepackage[colorlinks=true,linkcolor=blue,urlcolor=blue]{hyperref}
\usepackage{fancyhdr}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{YunTAPR-Net / v2 candidate design}
\fancyhead[R]{2026-10-10 / v1}\fancyfoot[C]{\thepage}
\setlength{\headheight}{14pt}\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}
\setlength{\emergencystretch}{3em}
\title{YunTAPR-Net\\Phase-B v2 科学协议候选\\与独立物理验证资料准备}
\author{研究者审阅材料 / 尚未批准}
\date{2026年10月10日 / v1}
\begin{document}\maketitle
\textbf{RESEARCHER\_DECISION\_REQUIRED。}所有新方案未执行；Phase-B、FinalFit、校准拟合及数据获取均未授权。

基线为\texttt{6e692625ebdd\allowbreak{}9bdaeff65e22\allowbreak{}d0ce59af349d98c5}。
本报告引用已发表2024开发验证；2025测试封存，正式参数更新为零。Markdown、机器候选、来源和预算与本LaTeX共同交付。

\setcounter{tocdepth}{1}\tableofcontents
"""
    equations = r"""
\clearpage\section{数学定义补充（既有 v2 与候选量）}
\[
z=\mathbf{1}\{y>0.1\},\quad u=\log(1+y),\quad
\tau_i=\frac{i-0.5}{32},\quad i=1,\ldots,32.
\]
\[
w_i=\operatorname{softplus}(a_i)+\epsilon_w,\quad
c_i=\frac{\sum_{j=1}^{i}w_j}{\sum_{j=1}^{32}w_j},\quad
s=\operatorname{softplus}(b)+\epsilon_s,\quad q_i=\log(1.1)+s c_i.
\]
\[
\rho_\tau(e)=e(\tau-\mathbf{1}\{e<0\}),\quad
L_{\mathrm{core}}=\frac{S_{\mathrm{occ}}+S_{\mathrm{qr}}}{N_{\mathrm{valid}}},\quad
\mathrm{CPB}=\frac{S_{\mathrm{qr}}}{N_{\mathrm{rain}}}.
\]
量化输出为log域条件分位数；物理单位为mm/h。候选E2改变固定\(\lambda_q\)，E3增添干位span惩罚，均非现有冻结loss：
\[
L_{\mathrm{candidate}}=\frac{S_{\mathrm{occ}}+\lambda_q S_{\mathrm{qr}}}{N_{\mathrm{valid}}}
+\lambda_d\frac{\sum_{\mathrm{valid}}(1-z)s^2}{N_{\mathrm{valid}}}.
\]
这里仅列公式，没有实现、优化或选择新参数。q32目标coverage为\(0.984375\)，不是\(p\times q_{32}\)意义上的均值。
\end{document}
"""
    body = "\n".join(markdown_tex((OUT/name).read_text(encoding="utf-8")) for name in DOCS)
    write_new(OUT/"PHASE_B_V2_CANDIDATE_REVIEW.tex",header+body+equations)
    dump_new(OUT/"report_source_binding.json", {"created_utc":datetime.now(timezone.utc).isoformat(),
        "source_markdown":[{"path":name,"sha256":sha(OUT/name)} for name in DOCS],
        "tex_sha256":sha(OUT/"PHASE_B_V2_CANDIDATE_REVIEW.tex"),"self_contained_tex":True,
        "figures_added":0,"content_status":"CANDIDATES_AND_PUBLISHED_FACTS_ONLY"})
    print(json.dumps({"status":"TEXT_AND_BUDGET_BUILT","candidate_directory":OUT.relative_to(REPO).as_posix()}))


if __name__ == "__main__":
    main()
