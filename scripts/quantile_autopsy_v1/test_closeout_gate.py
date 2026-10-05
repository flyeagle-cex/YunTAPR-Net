"""Record actual counts for the torch-free saved-evidence tests."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quantile_autopsy_v1 import common as c
import argparse
import io
import unittest

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);args=p.parse_args()
    output=io.StringIO();suite=unittest.defaultTestLoader.discover(str(c.ROOT/'tests/quantile_autopsy_closeout'))
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    counts={'run':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
            'failed':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)}
    dest=args.run/'readonly_closeout'
    with (dest/'readonly_test_output.txt').open('x',encoding='utf8') as f:f.write(output.getvalue())
    c.write(dest/'readonly_test_result.json',{'status':'PASS' if result.wasSuccessful() and not result.skipped else 'FAIL',
        'utc':c.now(),'counts':counts,'TEST_FIXTURE_ONLY':True,'torch_imported': 'torch' in sys.modules,
        'postprocessing_model_calls':0,'postprocessing_optimizer_steps':0,'postprocessing_raw_source_opens':0,
        'source':c.pin(Path(__file__)),'test_source':c.pin(c.ROOT/'tests/quantile_autopsy_closeout/test_close_readonly.py')})
    print(output.getvalue());raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)

if __name__=='__main__':main()
