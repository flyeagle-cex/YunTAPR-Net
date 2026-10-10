"""Author an unpublished protocol proposal and self-contained Chinese report."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import ast
import csv
import hashlib
import json
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
sys.path.insert(0,str(REPO / "scripts/phase_b_v2_candidates"))
from scripts.phase_b_v2_candidates.build_delivery import markdown_tex
from scripts.phase_b_v2_preregistration.budgets import run_rows, summary

OUT = REPO / "docs/phase_b_v2_ablation_preregistration/v1"
BASELINE = "8fbc06ba341aeee43136c18f20ebd6acd3463efd"
DOCS = ["SCIENTIFIC_OBJECTIVES.md", "FROZEN_EXPERIMENT_MATRIX_CANDIDATE.md", "CONTROLLED_VARIABLE_MATRIX.md",
        "LOSS_MATHEMATICS_AND_RESEARCHER_EXERCISE.md", "METRICS_AND_GUARDRAILS.md", "STATISTICAL_ANALYSIS_PLAN.md",
        "COMPUTE_AND_STORAGE_BUDGET.md", "RESEARCHER_APPROVAL_CHECKLIST.md", "SAFE_IMPLEMENTATION_HANDOFF.md",
        "TEST_PLAN.md", "RESEARCHER_DECISION_REQUIRED.md", "STATIC_CODE_REVIEW.md"]
SOURCE_PATHS = ["config/science_contract_v1.1.yaml", "config/science_v2/phase_a_protocol_frozen_v1.json",
    "config/science_v2/quantile_head_v2_frozen_v1.json", "src/yuntapr/losses/focal.py",
    "src/yuntapr/losses/pinball.py", "src/yuntapr/losses/total_loss.py",
    "src/yuntapr/models/quantile_v2/parameterization.py", "src/yuntapr/models/quantile_v2/outputs.py",
    "src/yuntapr/models/quantile_v2/heads.py", "src/yuntapr/models/quantile_v2/models.py",
    "src/yuntapr/training/formal_phase_a_v2.py", "src/yuntapr/training/phase_a_protocol.py",
    "src/yuntapr/training/phase_a_validation_v2.py", "src/yuntapr/training/phase_a_validation.py",
    "src/yuntapr/training/scientific_review.py", "src/yuntapr/training/checkpoint_v2.py",
    "src/yuntapr/training/upper_tail_v2.py", "src/yuntapr/data/dataset_b1.py",
    "docs/v2_scientific_acceptance/README.md", "docs/v2_scientific_acceptance/analysis_v1/analysis_preregistration.json",
    "docs/v2_scientific_acceptance/analysis_v1/sufficient_stats.py",
    "docs/phase_a_evidence_hardening/PROBABILITY_AND_TAIL_DIAGNOSTICS.md",
    "docs/phase_a_evidence_hardening/RECOVERY_GOVERNANCE_GAP_REVIEW.md",
    "docs/phase_a_evidence_hardening/PHASE_B_ENTRY_READINESS_CHECKLIST.md",
    "docs/phase_a_evidence_hardening/final_status.json",
    "docs/phase_b_v2_protocol_candidates/v1_20261010/PROTOCOL_CANDIDATES.md",
    "docs/phase_b_v2_protocol_candidates/v1_20261010/HYPOTHESES_AND_ABLATIONS.md",
    "docs/phase_b_v2_protocol_candidates/v1_20261010/RESEARCHER_DECISION_REQUIRED.md",
    "docs/phase_b_v2_protocol_candidates/v1_20261010/candidate_design.json",
    "docs/phase_b_v2_protocol_candidates/v1_20261010/budget_candidates.csv",
    "docs/phase_b_v2_protocol_candidates/v1_20261010/publication_receipt.json",
    "scripts/phase_b_v2_candidates/build_delivery.py", "scripts/phase_b_v2_candidates/planning.py"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8",newline="\n") as stream:
        stream.write(value)


def dump_new(path: Path, value: object) -> None:
    write_new(path,json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def main() -> None:
    head = subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO).decode().strip()
    if head != BASELINE or subprocess.check_output(["git","diff","--name-only"],cwd=REPO).strip():
        raise RuntimeError("Baseline/other tracked work changed")
    protocol = json.loads((REPO / SOURCE_PATHS[1]).read_text(encoding="utf-8"))
    paths = set(SOURCE_PATHS)
    declared = {}
    for key,ref in protocol["identity"].items():
        if key not in {"yunnan_mask","prior_gpu_manifest"}:
            path = ref["path"].replace("\\","/")
            if Path(path).is_absolute() or ":" in path:
                raise ValueError("Unexpected external repository reference")
            paths.add(path)
            declared[path] = ref["sha256"]
    repository_files = []
    locations = []
    for path in sorted(paths):
        observed = sha(REPO/path)
        if path in declared and observed != declared[path]:
            raise ValueError("Inherited source pin mismatch: " + path)
        repository_files.append({"path":path,"sha256":observed,"bytes":(REPO/path).stat().st_size,
                                 "kind":"SOURCE_AST_AND_BYTE_IDENTITY" if path.endswith(".py") else "PUBLISHED_METADATA_BYTE_IDENTITY_ONLY"})
        if path.startswith("src/") and path.endswith(".py"):
            tree = ast.parse((REPO/path).read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
                    locations.append({"path":path,"symbol":node.name,"line":node.lineno,"end_line":node.end_lineno})
    identity = {"baseline_commit":BASELINE,"recorded_utc":datetime.now(timezone.utc).isoformat(),
        "repository_files":repository_files,"code_locations":locations,
        "external_pins":[{"pointer":"config/science_v2/phase_a_protocol_frozen_v1.json#/identity/yunnan_mask",
                          "sha256":protocol["identity"]["yunnan_mask"]["sha256"],"status":"DECLARED_PIN_NOT_REOPENED"}],
        "raw_files_opened":0,"checkpoint_files_opened":0,"sample_manifest_rows_parsed":0,
        "static_scope":"REPOSITORY_SOURCE_AND_METADATA_BYTES_ONLY",
        "initialization_state":"NOT_YET_MATERIALIZED","approval_provenance":"NO_NEW_APPROVAL_EVIDENCED"}
    dump_new(OUT/"source_identity.json",identity)
    decisions = {k:{"status":"NOT_YET_ESTABLISHED","value":None} for k in (
        "minimum_brier_improvement","minimum_abs_q32_error_reduction","maximum_cpb_degradation",
        "maximum_strong_rain_cpb_degradation_by_bin","maximum_brier_degradation_HQ","maximum_AUROC_AP_drop",
        "tail_distribution_acceptance_rule","multiple_comparison_method","raw_p_construction",
        "interval_family","minimum_effective_blocks","minimum_valid_bootstrap_fraction",
        "event_effective_sample_size","statistical_power","gpu_resources","elapsed_time_estimate",
        "actual_checkpoint_bytes","sort_workspace_and_algorithm","data_permissions","execution_roots",
        "manual_retry_and_replay_budget","phase_a_acceptance_scope")}
    controls = {"route":"D1","qualification":"Q1","normalization":"N0","initialization":"I3_PAIRED_FRESH",
        "train":{"year":2023,"months":list(range(3,11)),"scenes":10455},
        "validation":{"year":2024,"months":list(range(3,11)),"scenes":10501,"batch":8,"fixed_order":True},
        "sealed_years":[2025],"input":{"B0_frames":1,"B1_frames":6,"shape":[501,501],"channel":"B13",
            "offset_minutes_before_analysis":[60,50,40,30,20,10],"ordering":"OLDEST_TO_LATEST","missing_policy":"M1_STRICT_COMPLETE_REJECT_NO_FALLBACK"},
        "time":{"target_window":"[T,T+30min)","analysis":"T+30min","causal_rule":"obs_end<=analysis"},
        "target":{"product":"IMERG_V07_Final","shape":[100,100],"yunnan_cells":3430,
            "rain_label":"float32_y>float32(0.1)_BEFORE_PROMOTION","SP04":"UNCHANGED"},
        "normalizer":{"mean_K":271.60515414265217,"std_K":19.93959597783802,"sha256":protocol["normalization_sha256"],"refit":False},
        "head":{"occurrence_raw_channels":1,"quantile_raw_channels":33,"quantiles":32,"tau":"(i-0.5)/32",
            "tau32":0.984375,"epsilon_w":1e-4,"epsilon_span":1e-4,"parameterization":"FROZEN_NORMALIZED_PREFIX_SHARED_ENDPOINT",
            "strict_guards":"UNCHANGED","implicit_physical":False},
        "precision":protocol["precision"],"optimizer":protocol["optimizer"],"gradient":protocol["gradient"],
        "training":{"epochs":9,"physical_batch":2,"accumulation":1,"drop_last":False,"steps_per_epoch":5228,
            "total_updates":47052,"augmentation":"NONE","every_scene_once":True,"performance_early_stop":False},
        "scheduler":protocol["scheduler"],"seeds":[2026,2027,2028],"epoch_order_rule":"seed+zero_based_epoch_index",
        "fresh":{"same_model_across_arms":"IDENTICAL_FULL_INITIAL_STATE","same_name_same_shape_B0_B1_copy":True,"historical_state_transfer":False},
        "validation_cadence":"EVERY_COMPLETED_TRAIN_EPOCH","endpoint_epoch":9,"checkpoint_boundary":"COMPLETED_TRAIN_AND_VALIDATION_EPOCH_ONLY",
        "checkpoint_selection":"FIXED_ENDPOINT_NO_BEST_SELECTION","loader":protocol["loader"],
        "loss_reduction":{"quantile_axis":"mean","train_denominator":"N_valid","scientific_CPB_denominator":"N_rain","common_core_gamma":2,"common_core_lambda_q":1},
        "probability_edges":[i/10 for i in range(11)],"last_probability_bin_includes_one":True,
        "rain_bins":["(0.1,1]","(1,5]","(5,10]","(10,20]","(20,30]","(30,50]","(50,inf)"],
        "tail_thresholds_mm_h":[10,50,100,500,1000],"distribution_summary":{"high_indices":[27,28,29,30,31,32],"percentiles":[.5,.9,.99,.999],"method":"TYPE7_EXACT_CANDIDATE","span":"q32_log-log1p(0.1)_DERIVED"},
        "bootstrap":{"blocks":35,"days_per_block":7,"replicates":2000,"seed":2026,"paired_all_arms_and_seeds":True,"scope":"DEVELOPMENT_EXPLORATORY_ONLY"},
        "auto_retry":False,"auto_resume":False,"resume":"INDEPENDENT_APPROVAL_BOUND_TO_SPECIFIC_LAST_SHA_REQUIRED"}
    rows = run_rows()
    proposal = {"version":"PHASE_B_V2_CORE_ABLATION_PREREGISTRATION_v1","status":"PROPOSED_FOR_RESEARCHER_APPROVAL",
        "decision_status":"RESEARCHER_DECISION_REQUIRED","execution_status":"NOT_EXECUTED","baseline_commit":BASELINE,
        "source_identity_sha256":sha(OUT/"source_identity.json"),
        "governance":{"RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED":True,"V2_PHASE_B_AUTHORIZED":False,"2025_RAW_ACCESS":0,
                      "2025_PIXELS_READ":0,"HISTORICAL_RECOVERY_RATIFICATION":"NOT_GRANTED","can_launch_formal_training":False},
        "controls":controls,"arms":[{"id":"E0","alpha":.5,"gamma":2,"lambda_q":1},{"id":"E1","alpha":.5,"gamma":0,"lambda_q":1},{"id":"E2","alpha":.5,"gamma":2,"lambda_q":2}],
        "models":["B0_MATCHED_V2","B1_V2"],"runs":[{k:r[k] for k in ("run_id","arm","model","seed","stage")} for r in rows],
        "primary_effects":{"H-O":"Brier_E1-Brier_E0_PER_MODEL_PER_SEED","H-Q":"abs(C32_E2-tau32)-abs(C32_E0-tau32)_PER_MODEL_PER_SEED","family_size_proposed":4},
        "stages":[{"id":1,"seed_scope":[2026],"runs":6,"updates":282312,"execution_authorization":None},
                  {"id":2,"seed_scope":[2027,2028],"runs":12,"updates":564624,"execution_authorization":None}],
        "approvals":{"scientific_approval":None,"researcher_loss_implementation_sha256":None,"researcher_code_review":None,
                     "integration_permission":None,"execution_authorization":None,"resume_authorization":None},
        "decision_fields":decisions,"excluded":["E3","E4","TEMPERATURE_SCALING","OTHER_CALIBRATORS","NEW_ARCHITECTURE","GFS","DEM","FINALFIT","2025_TEST"],
        "runner_implemented":False}
    dump_new(OUT/"protocol_proposed.json",proposal)
    def kind(value):
        return "null" if value is None else "boolean" if type(value) is bool else "integer" if type(value) is int else "number" if type(value) is float else "object" if type(value) is dict else "array" if type(value) is list else "string"
    schema = {"$schema":"https://json-schema.org/draft/2020-12/schema","title":"Closed unapproved v1 review proposal",
        "$comment":"No scientific or execution approvals are represented; this exact proposal cannot be promoted by editing a flag.",
        "type":"object","additionalProperties":False,"required":list(proposal),
        "properties":{k:{"type":kind(v),"const":v} for k,v in proposal.items()}}
    dump_new(OUT/"protocol_schema.json",schema)
    with (OUT/"run_budget.csv").open("x",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    dump_new(OUT/"budget_summary.json",summary())
    dump_new(OUT/"baseline_snapshot.json",{"local_HEAD":head,"remote_main_observed":BASELINE,"tracked_dirty_at_start":False,
        "process_query":"Win32_Process names only, external-sandbox read-only query","python_latex_processes_observed":0,
        "candidate_v1_preexisted":False,"previous_87_checks_reexecuted":0,"old_untracked_artifacts":"UNTOUCHED_NOT_STAGED"})
    header = r"""\documentclass[UTF8,fontset=fandol,10pt]{ctexart}
\usepackage[a4paper,margin=19mm]{geometry}
\usepackage{amsmath,amssymb,array,longtable,booktabs,url}
\usepackage[colorlinks=true,linkcolor=blue,urlcolor=blue]{hyperref}
\usepackage{fancyhdr}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{YunTAPR-Net / v2 ablation proposal}
\fancyhead[R]{2026-10-10 / v1}\fancyfoot[C]{\thepage}
\setlength{\headheight}{14pt}\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}
\setlength{\emergencystretch}{3em}
\title{YunTAPR-Net\\Phase-B v2 核心模型消融\\预注册候选与安全工程准备}
\author{研究者独立审查材料 / 尚未批准}
\date{2026年10月10日 / v1}
\begin{document}\maketitle
\textbf{PROPOSED\_FOR\_RESEARCHER\_APPROVAL。}不是科学批准、执行授权或历史恢复追认。

基线\texttt{8fbc06ba341a\allowbreak{}eee43136c18f\allowbreak{}20ebd6acd3463efd}；本轮正式参数更新、模型forward和2025访问均为零。

提案：18 runs、846,936 updates；保留逐epoch验证，共212,706 batches；仅工作量估计，未占用训练GPU。
研究者需先独立实现并理解最小loss，再经审查和明确集成许可。所有效应界限、容忍值、多重比较与资源字段尚未批准。
\setcounter{tocdepth}{1}\begingroup\small\setlength{\parskip}{0pt}\tableofcontents\endgroup
"""
    formulas = r"""
\clearpage\section{重要公式与真实源码映射}
\subsection{发生、Pinball与共同分母}
标签在原FP32判断：\(z=\mathbf1\{y_{32}>\operatorname{float32}(0.1)\}\)。
设\(v\)为IMERG有效mask与云南mask的交集，\(N_v=\sum v\)，\(N_r=\sum vz\)。
\begin{align*}
b(l,z)&=\max(l,0)-lz+\log(1+e^{-|l|}), &p_t&=e^{-b},\\
\alpha_z&=\alpha z+(1-\alpha)(1-z), & S_o&=\sum v\alpha_z(1-p_t)^\gamma b,\\
\tau_i&=(i-0.5)/32,&e_i&=\log(1+y)-q_i,\\
\rho_{\tau_i}(e_i)&=\max(\tau_i e_i,(\tau_i-1)e_i), & S_q&=\sum vz\,\frac1{32}\sum_{i=1}^{32}\rho_{\tau_i}(e_i),\\
L_{\rm proposed}&=(S_o+\lambda_q S_q)/N_v, &\operatorname{CPB}&=S_q/N_r.
\end{align*}
Focal numerator 对应 focal.py 的 BCEWithLogits/exp/weight/sum；Pinball对应pinball.py的maximum/mean/sum；总分母对应total\_loss.py。这里写的是提案公式，不是新PyTorch实现。\(\gamma=0,\alpha=.5\)时\(S_o=.5\sum vb\)，不是unweighted BCE。共同core固定\(\gamma=2,\lambda_q=1\)的FP64分子，而训练目标按各臂取参数。\(N_r=0\)时CPB/coverage不可估计。
\subsection{v2单调分位数与覆盖}
\begin{align*}
w_i&=\operatorname{softplus}(a_i)+10^{-4}, & W&=\left(\operatorname{cumsum}(w)\right)_{32},\\
c_i&=\left(\operatorname{cumsum}(w)\right)_i/W,&s&=\operatorname{softplus}(b)+10^{-4},\\
q_i&=\log(1.1)+s c_i,&q_{32}&=\log(1.1)+s,\\
C_i&=\frac{\sum vz\,\mathbf1\{\log(1+y)\le q_i\}}{N_r},&M_{32}&=|C_{32}-0.984375|.
\end{align*}
quantile\_v2/parameterization.py用相同FP64 prefix终点作分母，outputs.py守卫finite、支撑与严格序；不新增epsilon/clamp或head。span\_log\_derived由\(q_{32}-\log(1.1)\)反推，有FP64舍入。\(q\)在log1p(mm/h)域，物理输出需显式FP64 expm1与溢出检查。
\subsection{学习率与主效应}
\[
\eta(u)=\begin{cases}
10^{-4}u/5228,&1\le u\le5228,\\
10^{-6}+(10^{-4}-10^{-6})\dfrac{1+\cos(\pi(u-5228)/(261400-5228))}{2},&5228<u\le261400.
\end{cases}
\]
phase\_a\_protocol.py的lr\_for\_update；本提案仅用\(u\le47052\)，更新前应用；min LR下界只在cosine段，warmup不clamp。
\[
D_O(m,s)=\operatorname{Brier}_{E1,m,s}-\operatorname{Brier}_{E0,m,s},\quad
D_Q(m,s)=M_{32,E2,m,s}-M_{32,E0,m,s}.
\]
每seed先算效应再平均；日期块bootstrap每次pool分子/分母、共用multiplicity；不把seed乘像元当独立重复。科学minimum effects与guardrails尚未建立，负效应方向也不能自动判定通过。
\end{document}
"""
    body="\n".join(markdown_tex((OUT/name).read_text(encoding="utf-8")) for name in DOCS)
    write_new(OUT/"PHASE_B_V2_ABLATION_REVIEW.tex",header+body+formulas)
    dump_new(OUT/"report_source_binding.json",{"source_markdown":[{"path":name,"sha256":sha(OUT/name)} for name in DOCS],
        "tex_sha256":sha(OUT/"PHASE_B_V2_ABLATION_REVIEW.tex"),"self_contained":True,"new_figures":0})
    print(json.dumps({"status":"PROPOSED_PACKAGE_AUTHORED","references":len(repository_files),"runs":18}))


def repair_unpublished_report() -> None:
    """Reflow current uncommitted prose only; never regenerate historical inputs."""
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO).decode().strip()
    path=OUT/"PHASE_B_V2_ABLATION_REVIEW.tex"
    tracked=subprocess.check_output(["git","ls-tree","--name-only","HEAD","--",path.relative_to(REPO).as_posix()],cwd=REPO)
    if head!=BASELINE or tracked: raise RuntimeError("Cannot repair published or foreign report")
    original=path.read_text(encoding="utf-8")
    write_new(OUT/".local/source_before_format_repair.tex",original)
    header=original[:original.index(r"\clearpage\section{")]
    header=header.replace("每epoch验证212,706 batches", "保留逐epoch验证，共212,706 batches")
    suffix=original[original.index(r"\clearpage\section{重要公式与真实源码映射}"):]
    body="\n".join(markdown_tex((OUT/name).read_text(encoding="utf-8")) for name in DOCS)
    path.write_text(header+body+suffix,encoding="utf-8")
    dump_new(OUT/"tests/report_format_repair.json",{"cause":"Two overfull prose/table lines and ambiguous total-validation header wording",
        "repair":"Space allocation/span labels, separate primary-effect paragraphs, label total validation across all epochs",
        "scientific_values_changed":False,"before_tex_sha256":hashlib.sha256(original.encode()).hexdigest(),"after_tex_sha256":sha(path)})


def compact_unpublished_toc() -> None:
    path=OUT/"PHASE_B_V2_ABLATION_REVIEW.tex"
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO).decode().strip()
    tracked=subprocess.check_output(["git","ls-tree","--name-only","HEAD","--",path.relative_to(REPO).as_posix()],cwd=REPO)
    if head!=BASELINE or tracked: raise RuntimeError("Cannot reflow a published report")
    original=path.read_text(encoding="utf-8")
    write_new(OUT/".local/source_before_toc_repair.tex",original)
    marker=r"\setcounter{tocdepth}{1}\tableofcontents"
    if original.count(marker)!=1: raise ValueError("Unexpected TOC identity")
    path.write_text(original.replace(marker,r"\setcounter{tocdepth}{1}\begingroup\small\setlength{\parskip}{0pt}\tableofcontents\endgroup"),encoding="utf-8")
    dump_new(OUT/"tests/report_toc_repair.json",{"cause":"TOC final entry occupied an otherwise empty second page",
        "repair":"Use compact small TOC with zero paragraph skip","scientific_content_changed":False,
        "after_tex_sha256":sha(path)})


if __name__ == "__main__":
    if "--toc-repair" in sys.argv: compact_unpublished_toc()
    elif "--format-repair" in sys.argv: repair_unpublished_report()
    else: main()
