"""Only Stage4 changed-code synthetic checks; no optimizer or weather reads."""
from pathlib import Path
import datetime,io,json,os,sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests/core_stage4')]
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import torch
torch.set_num_threads(1)
if __name__=='__main__':
    names=sys.argv[1:] or ['test_stage4.Stage4Tests'];stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
    out=ROOT/'docs/core_stage4/tests'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ');out.mkdir(parents=True)
    original=stream.getvalue();public=original.replace(str(ROOT),'[REPO]').replace(sys.prefix,'[PYTHON_RUNTIME]').replace(sys.base_prefix,'[PYTHON_BASE]')
    (out/'original.log').write_text(original,encoding='utf-8');(out/'public.log').write_text(public,encoding='utf-8')
    summary=dict(tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),success=result.wasSuccessful(),historical_tests_rerun=False,optimizer_updates=0,real_weather_reads=0)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8');print(public);print(summary)
    raise SystemExit(0 if result.wasSuccessful() else 1)
