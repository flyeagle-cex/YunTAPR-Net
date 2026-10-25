"""Run only the new bounded interface tests; CPU, no formal training/data scan."""
from pathlib import Path
import datetime
import io
import json
import os
import sys
import unittest
import warnings

ROOT=Path(__file__).resolve().parents[2]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'src'))
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'


def main():
    import numpy,torch,netCDF4
    torch.set_num_threads(1)
    log=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests/core_innovation'),pattern='test_*.py')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    text=log.getvalue().replace(str(ROOT),'[REPO]')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder=ROOT/'docs/core_innovation/test_runs'/stamp;folder.mkdir(parents=True,exist_ok=False)
    (folder/'unittest.log').write_text(text,encoding='utf-8',newline='\n')
    report={'scope':'NEW_INTERFACE_TESTS_NOT_FORMAL_SCIENTIFIC_EXPERIMENTS','tests_run':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'success':result.wasSuccessful(),
        'python':sys.version.split()[0],'torch':torch.__version__,'numpy':numpy.__version__,'netCDF4':netCDF4.__version__,
        'torch_threads':torch.get_num_threads(),'cuda_initialized':torch.cuda.is_initialized(),
        'new_training_launched':False,'new_formal_model_evaluation':False,'raw_2025_reads':0,
        'dependency_warnings':sorted({w.category.__name__+': '+str(w.message) for w in caught}),
        'command':'python -B tools/core_innovation/run_checks.py'}
    (folder/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(text);print(json.dumps(report,ensure_ascii=False,indent=2));print('Evidence: '+folder.relative_to(ROOT).as_posix())
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
