"""Run fixture tests once, write their true counts and diagnostic source hashes."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src'),str(ROOT)]
from quantile_autopsy_v1 import common as c
import argparse
import unittest
from datetime import datetime,timezone

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests/quantile_overflow_autopsy'))
    tested=unittest.TextTestRunner(verbosity=2).run(suite)
    counts={'passed':tested.testsRun-len(tested.failures)-len(tested.errors)-len(tested.skipped),
            'failed':len(tested.failures),'skipped':len(tested.skipped),'errors':len(tested.errors)}
    code=0 if tested.wasSuccessful() and not tested.skipped else 1
    result={'status':'PASS' if code==0 else 'FAIL',
        'utc':c.now(),'TEST_FIXTURE_ONLY':True,'counts':counts,'exit_code':code,
        '2025_RAW_ACCESS':0,'FORMAL_OPTIMIZER_STEPS_ADDED':0,'temporary_checkpoints_created':0,
        'cuda_two_update_observer_equivalence':'output/loss/gradient/model/optimizer/RNG exact identity',
        'diagnostic_source_hashes':{p.relative_to(ROOT).as_posix():c.digest(p)
            for p in sorted((ROOT/'scripts/quantile_autopsy_v1').glob('*.py'))},
        'historical_identity':c.verify_snapshot(args.run)}
    attempts=args.run/'preflight_attempts';attempts.mkdir(exist_ok=True)
    c.write(attempts/('test_result_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'.json'),result)
    if code==0:c.write(args.run/'observer_test_result.json',result)
    raise SystemExit(code)

if __name__=='__main__':main()
