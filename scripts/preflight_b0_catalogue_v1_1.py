"""Zero-2025-access catalogue gate test execution and immutable evidence."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts')]
from yuntapr.evaluation import catalogue_gate_b0 as gate
from yuntapr.evaluation import final_test_b0 as legacy
BASE='65e1086bc2f0d830a6f45e01253b4ccffcae1130'
MODIFIED={'src/yuntapr/evaluation/final_test_b0.py','scripts/test_b0_2025_final_v1.py'}

def baseline():
    rows=subprocess.check_output(['git','ls-tree','-r','-z',BASE],cwd=ROOT).decode().rstrip('\0').split('\0')
    result={}
    for entry in rows:
        meta,name=entry.split('\t',1);data=(ROOT/name).read_bytes()
        digest=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if name not in MODIFIED and digest!=meta.split()[2]:raise ValueError('Immutable historical file changed: '+name)
        result[name]={'baseline_git_blob_sha1':meta.split()[2],'current_sha256':hashlib.sha256(data).hexdigest()}
    return result

def preflight():
    out=ROOT/'docs/final_test_b0/catalogue_gate_v1_1/preflight'/('run_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True,exist_ok=False)
    guard=gate.PreflightSourceGuard()
    try:
        with guard,gate.CatalogueOnlyGuard() as scope_guard:
            protocol=gate.load_protocol();pins=baseline();impl=gate.implementation_hashes()
            gate.save(out/'preflight_manifest.json',{'scope':'IMPLEMENTATION_AND_FIXTURE_TESTS_ONLY',
                'scientific_baseline_commit':'299d3f1080840b24db3ba6fe39684a1e6bca530a','engineering_start_commit':BASE,
                'protocol_sha256':gate.PROTOCOL_SHA,'implementation_sha256':impl,'baseline_files':pins,
                'retired_legacy_gate_files':sorted(MODIFIED),'created_utc':gate.now()})
            names=['tests.final_test_catalogue.test_catalogue_gate',
                   'tests.final_test_b0.test_catalogue_backend_v1_1']
            results=[]
            with (out/'test_results.txt').open('x',encoding='utf-8',newline='\n') as stream:
                for name in names:
                    suite=unittest.defaultTestLoader.loadTestsFromName(name)
                    tested=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);stream.flush()
                    row={'suite':name,'executed':tested.testsRun,'failures':len(tested.failures),
                        'errors':len(tested.errors),'skipped':len(tested.skipped),'pass':tested.wasSuccessful() and not tested.skipped}
                    results.append(row);print('CATALOGUE_PREFLIGHT_SUITE '+json.dumps(row),flush=True)
                    if not row['pass']:raise RuntimeError('Catalogue fixture test suite failed')
            if baseline()!=pins or gate.implementation_hashes()!=impl:raise ValueError('Source or history changed during tests')
            if guard.raw_open_events:raise ValueError('Real raw source opened during preflight')
            gate.save(out/'test_summary.json',{'status':'PASS','suites':results,'total_tests_executed':sum(r['executed'] for r in results),
                'scope':'SYNTHETIC_METADATA_AND_SYNTHETIC_NETCDF_FIXTURES_ONLY',
                'real_raw_sources_opened':0,'actual_checkpoint_loads':0,'actual_model_instantiations':0,
                'actual_model_forward_calls':0,'actual_optimizer_steps':0,'actual_backward_calls':0,
                'blocked_guard_probe_attempts':dict(scope_guard.attempts)})
            status={'FINAL_TEST_PROTOCOL_V1_1_FROZEN':True,'FINAL_TEST_CATALOGUE_RUNNER_READY':True,
                'FINAL_TEST_CATALOGUE_AUTHORIZED':False,'FINAL_TEST_2025_AUTHORIZED':False,
                'FINAL_TEST_2025_EXECUTED':False,'2025_CATALOGUE_QC_ACCESS':False,
                '2025_FINAL_TEST_EXECUTED':False,'2025_MODEL_INFERENCE_SCENES':0,
                '2025_FINAL_TEST_METRICS_COMPUTED':False,'2025_TARGET_OUTCOME_SUMMARIES_EXPOSED':False,
                '2025_PIXELS_READ':0,'2025_PIXELS_READ_semantics':'raw-access telemetry; independent of Final Test execution flags',
                'REAL_2025_CANDIDATE_CATALOGUE':'NOT_RUN_REQUIRES_SEPARATE_CATALOGUE_ONLY_AUTHORITY',
                'REAL_2025_ELIGIBLE_COUNT':'NOT_INSPECTED','REAL_2025_REJECTED_COUNT':'NOT_INSPECTED',
                'MODEL_PARAMETERS_UPDATED':False,'OPTIMIZER_STEPS':0,'BACKWARD_CALLS':0,
                'raw_sources_opened':0,'baseline_files_unchanged_except_retired_legacy_gates':len(pins)-len(MODIFIED),
                'TOTAL_TESTS_EXECUTED':sum(r['executed'] for r in results),'TEST_FAILURES':0,'TEST_ERRORS':0,'TEST_SKIPS':0,
                'completed_utc':gate.now(),'run_id':out.name}
            gate.save(out/'final_status.json',status)
        print('CATALOGUE_PREFLIGHT_PASS '+json.dumps({'run_directory':str(out),**status}),flush=True)
        return out
    except Exception as error:
        gate.save(out/'preflight_failure.json',{'status':'PREFLIGHT_FAILED','error_type':type(error).__name__,
            'FINAL_TEST_CATALOGUE_RUNNER_READY':False,'FINAL_TEST_2025_AUTHORIZED':False,
            'FINAL_TEST_2025_EXECUTED':False,'raw_sources_opened':guard.raw_open_events,
            '2025_PIXELS_READ':0 if guard.raw_open_events==0 else 'UNKNOWN_READ_ACCESS_OCCURRED',
            '2025_MODEL_INFERENCE_SCENES':0,'2025_FINAL_TEST_METRICS_COMPUTED':False,
            'failed_utc':gate.now()})
        raise

if __name__=='__main__':preflight()
