"""Researcher-approved fixture-only regression process, separate from inference."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"src"),str(ROOT/"scripts")]
import torch
from yuntapr.contracts.loader import sha256
from yuntapr.training.formal_phase_a import atomic_json, CHECKPOINT_ROOT
from review_b0_phase_a_scientific_v1 import PUBLIC, PRIVATE, BLOCKED_RUN, read, assert_unchanged
import train_b0_phase_a_formal_v1 as inherited


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-id",required=True)
    args=parser.parse_args()
    if Path(args.run_id).name!=args.run_id or args.run_id==BLOCKED_RUN:
        raise ValueError("Explicit new run identifier required")
    out=PUBLIC/args.run_id
    manifest=read(out/"review_manifest.json")
    if not manifest["approved_test_scope"]["TEST_FIXTURE_ONLY"]:
        raise ValueError("Explicit researcher fixture scope approval required")
    if read(out/"reinference_summary.json")["status"]!="PASS":
        raise ValueError("Full reinference must pass before full test execution")
    before=assert_unchanged(out)
    fixture=(PRIVATE/args.run_id/("test_fixtures_"+uuid.uuid4().hex)).resolve()
    if not fixture.is_relative_to((PRIVATE/args.run_id).resolve()):
        raise ValueError("Unsafe fixture root")
    fixture.mkdir(parents=True,exist_ok=False)
    os.environ.update(TEST_FIXTURE_ONLY="true",TEMP=str(fixture),TMP=str(fixture),
        YUNTAPR_PROTOCOL_DRYRUN_EVIDENCE=str(inherited.DRYRUN),YUNTAPR_SCIENTIFIC_REVIEW_EVIDENCE=str(out))
    tempfile.tempdir=str(fixture)
    torch.set_num_threads(2)
    raw_roots=[Path(r"H:\葵花202303_202510").resolve(),Path(r"F:\云南极端降水数据\raw\IMERG").resolve()]
    checkpoint_root=CHECKPOINT_ROOT.resolve()
    violations=[]
    def audit(event, args):
        if event!="open" or not isinstance(args[0],(str,bytes,os.PathLike)):
            return
        path=Path(os.fsdecode(args[0])).resolve()
        mode=args[1] or ""
        flags=args[2] if len(args)>2 else 0
        writing=any(c in str(mode) for c in "wax+") or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        if path.is_relative_to(checkpoint_root) or any(path.is_relative_to(root) for root in raw_roots):
            violations.append(str(path))
            raise PermissionError("TEST_FIXTURE_ONLY forbids formal checkpoint/raw-source access: "+str(path))
        if writing and not path.is_relative_to(fixture) and not path.is_relative_to(out.resolve()):
            violations.append(str(path))
            raise PermissionError("Test writes must belong to this fixture or test report: "+str(path))
    # Full artifact tests perform the explicitly allowed read-only BEST SHA check.
    # They never call torch.load or attach BEST tensors to any test model.
    fixture_phase={"enabled":True}
    def scoped_audit(event,args):
        if fixture_phase["enabled"]:
            audit(event,args)
    sys.addaudithook(scoped_audit)
    results=[]
    success=False
    cleanup=False
    try:
        with (out/"test_results.txt").open("x",encoding="utf-8",newline="\n") as stream:
            groups=[(suite,str(ROOT/"tests"/suite),"test*.py","TEST_FIXTURE_ONLY") for suite in (*inherited.SUITES,"formal_phase_a")]
            groups += [("scientific_review_units",str(ROOT/"tests/scientific_review"),"test_review_units.py","TEST_FIXTURE_ONLY"),
                ("scientific_review_full_artifacts",str(ROOT/"tests/scientific_review"),"test_review_full_artifacts.py","READ_ONLY_ARTIFACT_VERIFICATION")]
            for name,location,pattern,scope in groups:
                if scope=="READ_ONLY_ARTIFACT_VERIFICATION":
                    fixture_phase["enabled"]=False
                stream.write("\nSUITE "+name+" SCOPE "+scope+"\n")
                result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestLoader().discover(location,pattern=pattern))
                entry={"suite":name,"scope":scope,"executed":result.testsRun,"failures":len(result.failures),
                    "errors":len(result.errors),"skipped":len(result.skipped),"pass":result.wasSuccessful() and not result.skipped}
                results.append(entry)
                stream.flush()
                print("TEST "+json.dumps(entry),flush=True)
                if not entry["pass"]:
                    raise RuntimeError("STOP: review test suite failed: "+name)
            if sum(r["executed"] for r in results[:11])!=171:
                raise RuntimeError("Existing test count changed; investigate and report actual counts")
            success=True
    finally:
        fixture_phase["enabled"]=False
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        # Only this process-created, resolved child may be removed.
        if fixture.is_relative_to((PRIVATE/args.run_id).resolve()) and fixture.name.startswith("test_fixtures_"):
            shutil.rmtree(fixture)
            cleanup=not fixture.exists()
        after=assert_unchanged(out)
        evidence={"status":"PASS" if success and cleanup and not violations else "FAIL", "suites":results,
            "existing_tests_executed":sum(r["executed"] for r in results[:11]),
            "scientific_review_unit_tests_executed":sum(r["executed"] for r in results if r["suite"]=="scientific_review_units"),
            "full_review_artifact_tests_executed":sum(r["executed"] for r in results if r["suite"]=="scientific_review_full_artifacts"),
            "total_tests_executed":sum(r["executed"] for r in results),"TEST_FIXTURE_ONLY":True,
            "researcher_fixture_optimizer_backward_steps_approved":True,"fixture_root":str(fixture),"fixture_cleanup_success":cleanup,
            "fixture_artifacts_remaining":[] if cleanup else [str(p) for p in fixture.rglob("*") if p.is_file()],
            "formal_BEST_loaded_into_test_model":False,"review_inference_model_shared_with_tests":False,
            "formal_BEST_and_baseline_unchanged_before_after":before==after,"prohibited_accesses":violations,
            "fixture_steps_counted_as_review_steps":False,"review_OPTIMIZER_STEPS":0,"review_BACKWARD_CALLS":0,
            "completed_utc":datetime.now(timezone.utc).isoformat()}
        atomic_json(out/"test_summary.json",evidence)
        print("TEST_SUMMARY "+json.dumps(evidence),flush=True)
    if not cleanup or violations:
        raise RuntimeError("Fixture cleanup/scope failed")


if __name__=="__main__":
    main()
