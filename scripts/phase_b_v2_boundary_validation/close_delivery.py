"""Append-only source/test/PDF closure. Does not authorize or execute experiments."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import re
import subprocess
import xml.etree.ElementTree as ET

REPO=Path(__file__).resolve().parents[2]
OUT=REPO/"docs/phase_b_v2_boundary_validation/v1"
BASELINE="ccfa6869672c96634fede157b06984741cc71c1b"
NEW=("src/yuntapr/experimental/phase_b_v2_boundaries","tests/phase_b_v2_boundary_validation",
     "scripts/phase_b_v2_boundary_validation")
FLAGS={"V2_PHASE_B_AUTHORIZED":False,"FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED":False,
       "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED":True,"HISTORICAL_RECOVERY_RATIFICATION":"NOT_GRANTED",
       "2025_RAW_ACCESS":0,"2025_PIXELS_READ":0}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT/name).read_text(encoding="utf-8"))


def write(name,data):
    with (OUT/name).open("x",encoding="utf-8",newline="\n") as f:
        json.dump(data,f,ensure_ascii=False,indent=2);f.write("\n")


def public_paths():
    paths=[p for p in OUT.iterdir() if p.is_file() and p.suffix in {".md",".json",".tex",".pdf"}
           and p.name not in ("manifest.json","publication_receipt.json")]
    paths += [p for p in (OUT/"tests").iterdir() if p.is_file() and p.suffix in {".json",".xml",".log",".md"}]
    paths += list((OUT/"tests").glob("*_evidence/*.json"))
    paths += [p for folder in NEW for p in (REPO/folder).glob("*.py")]
    return sorted(paths,key=lambda p:p.relative_to(REPO).as_posix())


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main():
    from pypdf import PdfReader
    checks=[]
    def check(name,condition,details=None):
        if not condition:raise AssertionError(name)
        checks.append({"name":name,"status":"PASS","details":details})
    def git(*args):
        return subprocess.check_output(["git",*args],cwd=REPO).decode().strip()
    check("baseline_clean_tracked_worktree_and_index",git("rev-parse","HEAD")==BASELINE and
          not git("diff","--name-only") and not git("diff","--cached","--name-only"))
    inherited=read("source_identity.json")["inherited_files"]
    check("226_inherited_identities_unchanged",len(inherited)==226 and all(sha(REPO/x["path"])==x["sha256"] for x in inherited))
    source=[p for folder in NEW for p in (REPO/folder).glob("*.py")]
    trees={p:ast.parse(p.read_text(encoding="utf-8")) for p in source}
    check("12_new_python_files_parse",len(trees)==12,{"candidate":3,"tests":3,"scripts":6})
    index=read("HANDOFF_SOURCE_MAP.json")["symbols"]
    for row in index:
        path=REPO/row["path"]; tree=ast.parse(path.read_text(encoding="utf-8"))
        assert sha(path)==row["sha256"] and any(
            isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==row["function_or_class"] and n.lineno==row["line"]
            and n.end_lineno==row["end_line"] for n in ast.walk(tree)),row
    check("46_actual_source_symbols_and_line_hashes",len(index)==46)
    check("final_static_16_pass",read("tests/static_review_002.json")["passed"]==16)
    for phase,count in (("cpu",49),("cuda",12)):
        record=read(f"tests/{phase}_attempt_002.json")
        suites=ET.parse(OUT/f"tests/{phase}_attempt_002.xml").getroot().findall("testsuite")
        totals={k:sum(int(s.get(k,0)) for s in suites) for k in ("tests","failures","errors","skipped")}
        check(phase+"_records_XML_no_warnings",totals=={"tests":count,"failures":0,"errors":0,"skipped":0}
              and record["counts"]["passed"]==count and record["status"]=="PASS" and
              "warnings summary" not in (OUT/f"tests/{phase}_attempt_002.log").read_text(encoding="utf-8").lower())
        used=[x for x in read(f"tests/{phase}_attempt_002_evidence/source_at_execution.json")["files"]
              if not x["path"].endswith("/static_review.py")]
        check(phase+"_runtime_and_test_source_matches_execution",all(sha(REPO/x["path"])==x["sha256"] for x in used),
              "Separate static/doc scripts were not imported by the pytest process")
    cases=read("SYNTHETIC_BOUNDARY_RESULTS.json")["cases"]
    raw=[json.loads(p.read_text()) for p in sorted((OUT/"tests/cuda_attempt_002_evidence").glob("B*.json"))
         if not p.stem.endswith("_admission")]
    check("collated_cases_equal_raw_records",cases==raw)
    check("complete_12_case_matrix_unchanged_parameters",len(cases)==12 and all(
        x["fresh_state_sha256"]==x["after_state_sha256"] and x["prior_seed2026_identity_matches"]
        and x["common_evaluation_numerator_dtype"]=="float64" and not x["FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED"] for x in cases))
    check("exact_train_and_validation_calls",sum(x["full_model_forwards"] for x in cases)==12 and
          sum(x["full_model_backwards"] for x in cases)==12 and
          all(x["full_model_backwards"]==0 for x in cases if x["batch_size"]!=1))
    check("initial_evidence_and_repair_events_retained",
          read("tests/cpu_attempt_001.json")["counts"]["passed"]==49 and
          read("tests/cuda_attempt_001.json")["counts"]["passed"]==12 and
          all((OUT/"tests"/n).exists() for n in ("validation_precision_review_finding.json",
              "document_authoring_repair_001.json","compiler_attempt_001.json","latex_repair_001.json")))
    binding=read("report_source_binding.json")
    check("markdown_tex_binding",all(sha(OUT/x["path"])==x["sha256"] for x in binding["source_markdown"])
          and sha(OUT/"FINAL_CODE_REVIEW_HANDOFF.tex")==binding["tex_sha256"]
          and sha(OUT/"HANDOFF_SOURCE_MAP.json")==binding["source_map_sha256"])
    builder=load_module("boundary_doc_author",REPO/NEW[2]/"build_review.py")
    helper=load_module("prior_doc_author",REPO/"scripts/phase_b_v2_ablation_implementation/author_delivery.py")
    body="\n".join(builder.render_markdown((OUT/n).read_text(encoding="utf-8"),helper) for n in builder.DOCS)
    body=body.replace("\\clearpage\\section","\\section",1)
    check("all_final_markdown_bodies_embedded_in_editable_tex",body in (OUT/"FINAL_CODE_REVIEW_HANDOFF.tex").read_text(encoding="utf-8"))
    pdf=OUT/"FINAL_CODE_REVIEW_HANDOFF.pdf"; pages=PdfReader(pdf).pages
    visual=read("tests/pdf_visual_review_002.json");export=read("tests/export_attempt_002.json")
    check("compiled_rendered_and_visually_inspected_five_pages",len(pages)==5 and
          all(len(p.extract_text().strip())>100 for p in pages) and
          visual["pdf_sha256"]==sha(pdf) and visual["pages_inspected"]==[1,2,3,4,5] and
          visual["status"]==export["status"]=="PASS" and not any(export["warnings"].values()))
    pending={(OUT/n).resolve() for n in ("manifest.json","final_status.json")}
    for md in OUT.glob("*.md"):
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)",md.read_text(encoding="utf-8")):
            if "://" not in link:
                target=(md.parent/link.split("#")[0]).resolve()
                assert target.exists() or target in pending,(md.name,link)
    check("local_markdown_links_resolve",True)
    for path in public_paths():
        text="\n".join(p.extract_text() for p in pages) if path.suffix==".pdf" else path.read_text(encoding="utf-8")
        assert Path.home().name.lower() not in text.lower(),path
        assert not re.search(r"[A-Za-z]:[/\\]Users[/\\][^/\\\s]+",text,re.I),path
    check("narrow_public_scope_privacy_scan",True)
    write("tests/closure_audit_001.json",{"scope":"SYNTHETIC_ENGINEERING_ONLY","checks":checks,
                                      "passed":len(checks),"failed":0,**FLAGS})
    resource_summary={}
    for size in (1,8,5):
        selected=[x for x in cases if x["batch_size"]==size]
        resource_summary[str(size)]={key:[min(x["measurement"][key] for x in selected),
                                        max(x["measurement"][key] for x in selected)] for key in
                                    ("peak_allocated_bytes","peak_reserved_bytes","forward_and_three_losses_seconds")}
    write("final_status.json",{"status":"COMPLETE_WITHIN_SYNTHETIC_BOUNDARY_SCOPE_AT_RESEARCHER_REVIEW",
        "scope":"SYNTHETIC_ENGINEERING_ONLY","baseline_commit":BASELINE,"scientific_performance_evidence":False,
        "current_tests":{"CPU":49,"CUDA":12,"unique":61,"failures":0,"errors":0,"skipped":0,"warnings":0,
                         "static_checks":16,"closure_checks":len(checks)},
        "prior_91_CPU_6_CUDA_reexecuted":False,
        "history":{"pytest_instances":122,"numerical_test_failures":0,"static_precision_finding_fixed":1,
                   "document_authoring_failure_fixed":1,"latex_compilation_failure_fixed":1,"attempt_records_retained":True},
        "model_calls":{"current_full_forwards":12,"current_full_backwards":12,
                       "cumulative_full_forwards":24,"cumulative_full_backwards":24,
                       "fresh_model_instances_current":24,"fresh_model_instances_total":48,
                       "optimizer_steps":0,"validation_backwards":0},
        "matrix":{"models":["B0_MATCHED_V2","B1_V2"],"batch_sizes":[1,8,5],"rain_cases":["MIXED","EMPTY_RAIN"],
                  "loss_arms":["E0","E1","E2"],"seed":2026,"all_complete":True},
        "resources":resource_summary,"OOM":False,"timeout":False,"fallback_or_automatic_retry":False,
        "common_evaluation":"Unchanged LogDomainValidation FP64 gamma2 unweighted numerators; never an arm training objective",
        "remaining_unexecuted":["Real frozen mask/scaler/2023-2024 data preflight and ID order",
            "Formal optimizer/clip/scheduler and durable checkpoint transactions",
            "New B9/V0 runner, long-duration resource and failure-injection tests",
            "Independent approval authenticity, stage execution and LAST-bound restore",
            "CPU full-model forward/backward; boundary seeds2027/2028 (prior identity evidence reused)"],
        "researcher_decisions":["H-O/H-Q, E0/E1/E2, D1/Q1/N0/I3/B9/S0/V0 final acceptance",
            "Minimum scientific effects, guardrail limits and multiplicity NOT_YET_ESTABLISHED",
            "2024 development interpretation, Phase-A acceptance scope and historical recovery independent disposition",
            "Formal integration, data/compute preflight, specific stage execution and recovery approvals"],
        "inherited_files_verified":226,"historical_files_modified":0,
        "raw_2023_2024_data_reads":0,"private_checkpoint_reads":0,
        "pdf_pages":5,"pdf_sha256":sha(pdf),"publication_identity":"Append-only publication_receipt.json and Git history",
        "next_action":"Researcher code review and independent decisions; stop here without deriving new work packages",**FLAGS})
    paths=public_paths()
    assert all(p.resolve().is_relative_to(REPO.resolve()) and ".local" not in p.parts for p in paths)
    write("manifest.json",{"schema":"phase-b-v2-boundary-publication-v1","scope":"SYNTHETIC_ENGINEERING_ONLY",
        "baseline_commit":BASELINE,"files":[{"path":p.relative_to(REPO).as_posix(),"sha256":sha(p),"bytes":p.stat().st_size} for p in paths],
        "excluded":["manifest self-hash","append-only publication_receipt","private .local logs/renders","all historical untracked files"],
        "scientific_approval_created":False})
    print(json.dumps({"closure_passed":len(checks),"failed":0,"manifest_members":len(paths)}))


if __name__=="__main__":
    main()
