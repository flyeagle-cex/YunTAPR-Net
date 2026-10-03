from pathlib import Path
import copy,datetime,io,json,os,sys,unittest
ROOT=Path(__file__).parent;REPO=ROOT/'YunTAPR-Net-push-chunks';sys.path[:0]=[str(REPO/'src'),str(REPO),str(REPO/'scripts')]
from yuntapr.evaluation.catalogue_gate_b0 import PreflightSourceGuard
a=json.loads((ROOT/'YunTAPR-active-b1-protocol-v1.json').read_text());run=Path(a['run_directory'])
prior=run/'test_summary_20261003T075021_078563Z.json';summary=json.loads(prior.read_text());assert summary['total_tests_executed']==279
os.environ['YUNTAPR_PROTOCOL_DRYRUN_EVIDENCE']=str(REPO/'docs/phase_a_optimizer_dryrun/runs/run_20261001T030242Z')
os.environ['YUNTAPR_PHASE_B_RUNNER_EVIDENCE']=str(REPO/'docs/phase_b_formal_runner/runs/run_20261002T031500_884240Z')
names=['tests.phase_a_protocol_v1.test_protocol_v1.ProtocolTests.test_real_replay_and_resume_evidence',
       'tests.formal_phase_b.test_finalfit.FinalFitArtifactTests',
       'tests.b1_training_protocol.test_preflight_artifacts.ArtifactTests.test_actual_2024_validation_only_gpu_confirmation']
log=io.StringIO();results=[]
with PreflightSourceGuard() as guard:
    for name in names:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName(name))
        results.append({'suite':name,'executed':result.testsRun,'passed':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)})
    assert guard.raw_open_events==0
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
with (run/('fixture_binding_recheck_'+stamp+'.txt')).open('x',encoding='utf-8',newline='\n') as f:f.write(log.getvalue())
with (run/('fixture_binding_recheck_'+stamp+'.json')).open('x',encoding='utf-8') as f:json.dump({'results':results,'fixture_environment':{k:os.environ[k] for k in ('YUNTAPR_PROTOCOL_DRYRUN_EVIDENCE','YUNTAPR_PHASE_B_RUNNER_EVIDENCE')},'raw_source_open_events':0,'formal_optimizer_steps':0},f,indent=2)
assert all(r['passed'] and r['skipped']==0 for r in results),log.getvalue()
out=copy.deepcopy(summary)
for r in out['suites']:
    if r['suite']=='INHERITED_PHASE_A_PROTOCOL':r.update(failures=0,passed=True,repaired_by_readonly_recheck_of_failed_test=True)
    if r['suite']=='INHERITED_PHASE_B_RUNNER':r.update(errors=0,passed=True,executed=r['executed']+results[1]['executed'],artifact_setUpClass_rechecked_with_existing_evidence=True)
    if r['suite']=='NEW_REAL_PREFLIGHT_ARTIFACTS':r['executed']+=1
out.update(all_passed=True,total_tests_executed=sum(r['executed'] for r in out['suites']),
           actual_test_invocations_including_rechecks=summary['total_tests_executed']+sum(r['executed'] for r in results),
           prior_failure_summary=str(prior.relative_to(REPO)),recheck_results=results,
           test_count_convention='Unique executed cases after failed fixture binding was resolved; actual invocation count separately recorded',
           completed_utc=stamp)
with (run/'test_summary.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps(out),flush=True)
