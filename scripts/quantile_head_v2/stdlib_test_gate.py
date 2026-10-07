"""Run stdlib-only historical tests in a genuinely clean Python process."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from quantile_head_v2 import common as c
import argparse,importlib,io,os,types,unittest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    def firewall(event,values):
        if event=='open' and isinstance(values[0],(str,bytes,os.PathLike)):
            name=os.fsdecode(values[0]).replace('/','\\').lower()
            if name.startswith('h:\\') or '\\云南极端降水数据\\raw\\' in name or '\\outputs\\formal_training\\' in name:
                raise PermissionError('STDLIB_FIXTURE_RAW_OR_FORMAL_CHECKPOINT_ACCESS_FORBIDDEN')
    sys.addaudithook(firewall)
    package=types.ModuleType('tests');package.__path__=[str(ROOT/'tests')];sys.modules['tests']=package
    module=importlib.import_module('tests.saved_quantile_extremes.test_extremes')
    suite=unittest.defaultTestLoader.loadTestsFromModule(module);planned=suite.countTestCases()
    console=io.StringIO();result=unittest.TextTestRunner(stream=console,verbosity=2,failfast=True).run(suite)
    clean='torch' not in sys.modules and 'netCDF4' not in sys.modules
    value={'description':'stdlib-only fixture（仅标准库测试夹具）：在独立 Python 进程验证未加载模型或原始数据后端，不隐藏父进程模块。',
        'status':'PASS' if result.wasSuccessful() and not result.skipped and clean else 'FAIL',
        'TEST_FIXTURE_ONLY':True,'planned_tests':planned,
        'suite_counts':{'tests/saved_quantile_extremes/test_extremes.py':planned},
        'counts':{'run':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
            'failed':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)},
        'console':console.getvalue(),'torch_imported':'torch' in sys.modules,'netCDF4_imported':'netCDF4' in sys.modules,
        '2025_RAW_ACCESS':0,'FORMAL_OPTIMIZER_STEPS_ADDED':0}
    c.write(args.output,value)
    if value['status']!='PASS':raise AssertionError('Stdlib subprocess test gate failed')
    print(__import__('json').dumps(value['counts']))


if __name__=='__main__':main()
