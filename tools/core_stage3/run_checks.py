"""Stage3 delta checks only; CPU, synthetic arrays/SQLite, no weather reads."""
from pathlib import Path
import argparse,datetime,io,json,os,sys,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'))
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--test',action='append');a=p.parse_args();sys.path.insert(0,str(ROOT/'tests/core_stage3'))
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromNames(a.test) if a.test else unittest.defaultTestLoader.discover(str(ROOT/'tests/core_stage3'),pattern='test_*.py')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ');folder=ROOT/'docs/core_stage3/tests'/stamp;folder.mkdir(parents=True)
    original=stream.getvalue();public=original.replace(str(ROOT),'[REPO]').replace(sys.prefix,'[PYTHON_RUNTIME]')
    (folder/'original.log').write_text(original,encoding='utf-8',newline='\n');(folder/'public.log').write_text(public,encoding='utf-8',newline='\n')
    summary=dict(tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),success=result.wasSuccessful(),
        inherited_72_tests_rerun=False,optimizer_updates=0,new_weather_reads=0,raw_2025_reads=0,scope='STAGE3_DELTA_SYNTHETIC_ONLY')
    (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(public);print(json.dumps(summary,indent=2));print(folder.relative_to(ROOT));raise SystemExit(0 if result.wasSuccessful() else 1)
