"""Isolated regression and read-only preparation artifact verification."""
import argparse
from datetime import datetime,timezone
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
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts')]
import torch
from prepare_b0_phase_b_finalfit_v1 import read,save,preserve,PRIVATE,REVIEW,sha256
import train_b0_phase_a_formal_v1 as inherited


def main(out):
    if read(out/'engineering_dryrun.json')['status']!='PASS':raise ValueError('Actual dry-run must pass before full artifact tests')
    before=preserve(out)
    parent=Path(read(out/'preparation_manifest.json')['private_directory']).resolve()
    fixture=(parent/('test_fixtures_'+uuid.uuid4().hex)).resolve()
    if not fixture.is_relative_to(parent):raise ValueError('Unsafe test fixture path')
    fixture.mkdir(parents=True,exist_ok=False)
    os.environ.update(TEST_FIXTURE_ONLY='true',TEMP=str(fixture),TMP=str(fixture),
        YUNTAPR_PROTOCOL_DRYRUN_EVIDENCE=str(inherited.DRYRUN),YUNTAPR_SCIENTIFIC_REVIEW_EVIDENCE=str(REVIEW),
        YUNTAPR_PHASE_B_PREPARATION_EVIDENCE=str(out))
    tempfile.tempdir=str(fixture);torch.set_num_threads(2)
    rawroots=[Path(r'H:\葵花202303_202510').resolve(),Path(r'F:\云南极端降水数据\raw\IMERG').resolve()]
    checkpointroot=Path(r'F:\pytorch\Research\outputs\formal_training').resolve()
    best=Path(read(out/'preparation_manifest.json')['formal_best']['absolute_local_path']).resolve()
    artifact_phase={'enabled':False};violations=[]
    def audit(event,args):
        if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
        path=Path(os.fsdecode(args[0])).resolve();mode=args[1] or '';flags=args[2] if len(args)>2 else 0
        writing=any(c in str(mode) for c in 'wax+') or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        bad=any(path.is_relative_to(root) for root in rawroots)
        bad |= path.is_relative_to(checkpointroot) and not (artifact_phase['enabled'] and path==best and not writing)
        bad |= writing and not path.is_relative_to(fixture) and not path.is_relative_to(out.resolve())
        if bad:
            violations.append(str(path));raise PermissionError('Fixture isolation forbids access: '+str(path))
    active={'enabled':True}
    sys.addaudithook(lambda e,a:audit(e,a) if active['enabled'] else None)
    success=False;cleanup=False;results=[]
    try:
        with (out/'test_results.txt').open('x',encoding='utf-8',newline='\n') as stream:
            groups=[(name,str(ROOT/'tests'/name),'test*.py','TEST_FIXTURE_ONLY',None) for name in (*inherited.SUITES,'formal_phase_a')]
            groups += [('scientific_review_units',str(ROOT/'tests/scientific_review'),'test_review_units.py','TEST_FIXTURE_ONLY',None),
                ('scientific_review_full_artifacts',str(ROOT/'tests/scientific_review'),'test_review_full_artifacts.py','READ_ONLY_ARTIFACT_VERIFICATION',None),
                ('phase_b_preparation_units',None,None,'TEST_FIXTURE_ONLY','tests.phase_b_preparation.test_preparation.PreparationUnitTests'),
                ('phase_b_preparation_artifacts',None,None,'READ_ONLY_ARTIFACT_VERIFICATION','tests.phase_b_preparation.test_preparation.PreparationArtifactTests')]
            for name,location,pattern,scope,testname in groups:
                artifact_phase['enabled']=scope=='READ_ONLY_ARTIFACT_VERIFICATION'
                suite=unittest.defaultTestLoader.loadTestsFromName(testname) if testname else unittest.TestLoader().discover(location,pattern=pattern)
                stream.write('\nSUITE '+name+' SCOPE '+scope+'\n')
                result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
                item={'suite':name,'scope':scope,'executed':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
                    'skipped':len(result.skipped),'pass':result.wasSuccessful() and not result.skipped}
                results.append(item);stream.flush();print('TEST '+json.dumps(item),flush=True)
                if not item['pass']:raise RuntimeError('Stop: test suite failed '+name)
            success=True
    finally:
        active['enabled']=False;gc.collect();torch.cuda.empty_cache()
        if fixture.is_relative_to(parent) and fixture.name.startswith('test_fixtures_'):
            shutil.rmtree(fixture);cleanup=not fixture.exists()
        after=preserve(out)
        summary={'status':'PASS' if success and cleanup and not violations else 'FAIL','suites':results,
            'total_tests_executed':sum(r['executed'] for r in results),'existing_171_executed':sum(r['executed'] for r in results[:11]),
            'scientific_review_tests':sum(r['executed'] for r in results if r['suite'].startswith('scientific_review')),
            'new_preparation_tests':sum(r['executed'] for r in results if r['suite'].startswith('phase_b_preparation')),
            'TEST_FIXTURE_ONLY':True,'temporary_fixture_optimizer_backward_steps_only':True,
            'fixture_root':str(fixture),'fixture_cleanup_success':cleanup,'prohibited_accesses':violations,
            'formal_BEST_and_all_baseline_files_unchanged':before==after,'formal_checkpoint_not_applied_to_test_model':True,
            'PHASE_B_FORMAL_TRAINING_STARTED':False,'PHASE_B_AUTHORIZED':False,'2025_PIXELS_READ':0,
            'completed_utc':datetime.now(timezone.utc).isoformat()}
        save(out/'test_summary.json',summary);print('TEST_SUMMARY '+json.dumps(summary),flush=True)
    if not success or not cleanup or violations:raise RuntimeError('Tests or cleanup did not pass')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-dir',type=Path,required=True)
    main(parser.parse_args().run_dir.resolve())
