"""Read-only risk and source audit. No torch import, dataset preflight or model call."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

REPO=Path(__file__).resolve().parents[2]
OUT=REPO/"docs/phase_b_v2_boundary_validation/v1"
BASELINE="ccfa6869672c96634fede157b06984741cc71c1b"
NEW=("src/yuntapr/experimental/phase_b_v2_boundaries","tests/phase_b_v2_boundary_validation",
     "scripts/phase_b_v2_boundary_validation")
REVIEW={
    "src/yuntapr/experimental/phase_b_v2_ablations/validation.py":["supervision","graph_zero"],
    "src/yuntapr/experimental/phase_b_v2_ablations/focal.py":["occurrence_numerator"],
    "src/yuntapr/experimental/phase_b_v2_ablations/pinball.py":["frozen_taus","conditional_pinball_numerator"],
    "src/yuntapr/experimental/phase_b_v2_ablations/total.py":["combine_numerators","CandidateLossResult","candidate_loss"],
    "src/yuntapr/experimental/phase_b_v2_ablations/config.py":["get_config","RunSpec","learning_rate_prefix","workload"],
    "src/yuntapr/models/quantile_v2/heads.py":["ProbabilityHeadsV2"],
    "src/yuntapr/models/quantile_v2/parameterization.py":["normalized_monotonic_quantiles"],
    "src/yuntapr/models/quantile_v2/outputs.py":["validate_log_quantiles"],
    "src/yuntapr/experimental/phase_b_v2_integration/initialization.py":["seeded_environment","fresh_paired_models"],
    "src/yuntapr/experimental/phase_b_v2_integration/controls.py":["synthetic_epoch_order","endpoint_boundary","reject_resume","reject_formal_start"],
    "src/yuntapr/experimental/phase_b_v2_ablations/readiness.py":["review_checkpoint_binding","BlockedRunner"],
    "src/yuntapr/training/formal_phase_a_v2.py":["paired_initialization","forward_loss","update","loader"],
    "src/yuntapr/training/checkpoint_v2.py":["validate_payload","verify_file","apply_verified","CheckpointStore"],
    "src/yuntapr/losses/total_loss.py":["b0_core_loss"],
    "src/yuntapr/training/phase_a_validation_v2.py":["LogDomainValidation"],
    "src/yuntapr/experimental/phase_b_v2_boundaries/boundary.py":["BoundaryBatch","make_boundary_pair","losses_from_output","forward_boundary","evaluation_components","aggregate_evaluation"],
    "src/yuntapr/experimental/phase_b_v2_boundaries/gradients.py":["checked_gradients"],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT/name).read_text(encoding="utf-8"))


def main(attempt: int):
    if type(attempt) is not int or attempt != 2:
        raise ValueError("This final source review is attempt 2, after the FP64 correction")
    checks=[]
    def check(name,condition,details=None):
        if not condition:
            raise AssertionError(name)
        checks.append({"name":name,"status":"PASS","details":details})
    source=read("source_identity.json")
    check("226_inherited_files_unchanged",len(source["inherited_files"])==226 and
          all(sha(REPO/x["path"])==x["sha256"] for x in source["inherited_files"]))
    check("baseline_and_tracked_worktree_unchanged",
          subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO).decode().strip()==BASELINE and
          not subprocess.check_output(["git","diff","--name-only"],cwd=REPO))
    for phase,count in (("cpu",49),("cuda",12)):
        record=read(f"tests/{phase}_attempt_002.json")
        suites=ET.parse(OUT/f"tests/{phase}_attempt_002.xml").getroot().findall("testsuite")
        totals={k:sum(int(s.get(k,0)) for s in suites) for k in ("tests","failures","errors","skipped")}
        check(phase+"_XML_and_final_record",totals=={"tests":count,"failures":0,"errors":0,"skipped":0}
              and record["status"]=="PASS" and record["counts"]["passed"]==count)
        execution=read(f"tests/{phase}_attempt_002_evidence/source_at_execution.json")["files"]
        used=[x for x in execution if not x["path"].endswith("/static_review.py")]
        check(phase+"_executed_runtime_and_test_source_bytes_unchanged",all(sha(REPO/x["path"])==x["sha256"] for x in used),
              "Source snapshot also inventories static_review.py, which is not imported by pytest and was revised separately")
    cases=[json.loads(p.read_text()) for p in sorted((OUT/"tests/cuda_attempt_002_evidence").glob("B*.json"))
           if not p.stem.endswith("_admission")]
    check("complete_batch_model_rain_matrix",len(cases)==12 and
          {(x["batch_size"],x["model"],x["rain_case"]) for x in cases}==
          {(b,m,r) for b in (1,8,5) for m in ("B0_MATCHED_V2","B1_V2") for r in ("MIXED","EMPTY_RAIN")})
    check("all_three_arms_and_correct_denominators",
          all(set(x["arms"])=={"E0","E1","E2"} and all(a["N_valid"]==x["batch_size"]*3430 for a in x["arms"].values()) for x in cases))
    check("fresh_state_unchanged_and_no_updates",
          all(x["fresh_state_sha256"]==x["after_state_sha256"] and x["prior_seed2026_identity_matches"]
              and x["optimizer_steps"]==x["raw_data_reads"]==x["checkpoint_reads_or_writes"]==0
              and not x["FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED"] for x in cases))
    check("inference_validation_and_train_tail_gradients",
          all(x["full_model_backwards"]==(3 if x["batch_size"]==1 else 0) and
              all(a["gradients"].get("all_parameter_grads_absent") if x["batch_size"]!=1 else
                  a["gradients"]["missing"]==a["gradients"]["nonfinite"]==0 for a in x["arms"].values()) for x in cases))
    paths=[p for folder in NEW for p in (REPO/folder).glob("*.py")]
    trees={p:ast.parse(p.read_text(encoding="utf-8")) for p in paths}
    check("all_current_new_python_parses",bool(trees))
    candidates=[t for p,t in trees.items() if NEW[0] in p.as_posix()]
    forbidden={"step","load_state_dict","save","load","apply_verified","verify_file","optimizer_for","adamw","expm1"}
    names=[n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else ""
           for t in candidates for n in ast.walk(t) if isinstance(n,ast.Call)]
    check("candidate_has_no_optimizer_state_application_or_physical_conversion",not(set(names)&forbidden))
    official=[p for p in (REPO/"src/yuntapr").rglob("*.py") if "experimental" not in p.parts]
    check("no_formal_path_imports_new_candidates",
          all("phase_b_v2_boundaries" not in p.read_text(encoding="utf-8") for p in official))
    cuda=(REPO/NEW[1]/"test_cuda_boundaries.py").read_text(encoding="utf-8")
    check("resource_gate_precedes_any_constructor",cuda.index("require_resources(admission)")<cuda.index("models,proof=fresh_paired_models"))
    boundary=(REPO/NEW[0]/"boundary.py").read_text(encoding="utf-8")
    check("validation_inference_and_precision_are_explicit",
          "torch.inference_mode(mode=not training)" in boundary and 'dtype=torch.bfloat16' in boundary
          and "torch.float64" in boundary and "torch.float32" in boundary)
    check("common_evaluation_reuses_frozen_FP64_accumulator",
          "accumulator = LogDomainValidation()" in boundary and
          all(x["common_evaluation_numerator_dtype"]=="float64" and
              x["common_evaluation_components"]["occurrence_gamma_for_common_core"]==2 for x in cases))
    risk=[
        {"risk":"FP32_LABEL_THRESHOLD","status":"REVIEW_POINT","source":"validation.py:supervision",
         "finding":"Labels compare FP32 reference to FP32 0.1 before FP64 cast; CPU threshold edge counts passed for batch1/8/5."},
        {"risk":"PRECISION_AND_SUPPORT","status":"REVIEW_POINT","source":"heads.py and parameterization.py",
         "finding":"BF16 occurrence; FP32 raw33; FP64 transform/pinball. Strict order/support epsilon unchanged. No expm1 in tested path."},
        {"risk":"EVALUATION_DENOMINATORS","status":"REVIEW_POINT","source":"total.py and boundary.py:evaluation_components",
         "finding":"Train denominator N_valid; conditional report N_rain. E1 gamma and E2 lambda training objectives cannot be common Core. Common gamma2 FP64 numerators are recomputed by unchanged LogDomainValidation, then aggregated. Initial helper precision issue and correction retained."},
        {"risk":"NO_RAIN_VS_NO_SUPERVISION","status":"REVIEW_POINT","source":"validation.py:graph_zero and total_loss.py:b0_core_loss",
         "finding":"Empty rain gives connected zero and conditional report None. Candidate raises on zero valid; old loss returns skip marker, formal forward_loss raises. Integration must preserve stop rather than silently skip."},
        {"risk":"FRESH_AND_ORDER","status":"REVIEW_POINT","source":"initialization.py and controls.py",
         "finding":"New GPU cases match prior seed2026; seeds2027/2028 and 9 epoch synthetic permutations use unchanged prior evidence, not rerun. No real ID order has been validated."},
        {"risk":"EPOCH9_VS_PHASE_A_SCHEMA","status":"RESEARCHER_DECISION_REQUIRED","source":"checkpoint_v2.py:validate_payload",
         "finding":"Historical Phase-A schema allows epochs1..50, BEST/early-stop selection and next permutation at terminal. It is not a reviewed B9/V0 runner. New formal schema/terminal transaction must be independently approved."},
        {"risk":"SHA_IS_NOT_APPROVAL","status":"RESEARCHER_DECISION_REQUIRED","source":"readiness.py and controls.py:reject_resume",
         "finding":"Binding strings cannot authenticate approval. BlockedRunner remains unconditional. No LAST state loader invoked or durable checkpoint transaction tested."},
    ]
    symbols=[]
    for relative,wanted in REVIEW.items():
        path=REPO/relative
        tree=ast.parse(path.read_text(encoding="utf-8"))
        for name in wanted:
            node=next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
            symbols.append({"path":relative,"function_or_class":name,"line":node.lineno,"end_line":node.end_lineno,"sha256":sha(path)})
    for name,data in (("review_source_index_002.json",{"scope":"SOURCE_REVIEW_NOT_APPROVAL","symbols":symbols}),
                      ("RISK_AUDIT_002.json",{"scope":"SYNTHETIC_ENGINEERING_ONLY","risks":risk}),
                      ("tests/static_review_002.json",{"scope":"SYNTHETIC_ENGINEERING_ONLY","checks":checks,"passed":len(checks),
                        "failed":0,"old_91_CPU_6_CUDA_reexecuted":False,"formal_authorization":False})):
        with (OUT/name).open("x",encoding="utf-8",newline="\n") as f:
            json.dump(data,f,ensure_ascii=False,indent=2); f.write("\n")
    print(json.dumps({"static_passed":len(checks),"failed":0,"review_symbols":len(symbols)}))


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument("--attempt",type=int,required=True)
    main(parser.parse_args().attempt)
