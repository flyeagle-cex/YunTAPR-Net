"""Run stage-2 delta tests only, preserving every actual run including failures."""
from pathlib import Path
import argparse, datetime, io, json, os, sys, unittest, warnings
ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True; sys.path.insert(0, str(ROOT/'src'))
os.environ['CUDA_VISIBLE_DEVICES'] = ''; os.environ['OMP_NUM_THREADS'] = '1'; os.environ['MKL_NUM_THREADS'] = '1'


if __name__ == '__main__':
    import torch, numpy
    torch.set_num_threads(1)
    parser = argparse.ArgumentParser(); parser.add_argument('--test'); args = parser.parse_args()
    sys.path.insert(0, str(ROOT/'tests/core_stage2'))
    suite = unittest.defaultTestLoader.loadTestsFromName(args.test) if args.test else unittest.defaultTestLoader.discover(str(ROOT/'tests/core_stage2'), pattern='test_*.py')
    stream = io.StringIO()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always'); result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    folder = ROOT/'docs/core_stage2/test_runs'/stamp; folder.mkdir(parents=True, exist_ok=False)
    log = stream.getvalue().replace(str(ROOT), '[REPO]')
    (folder/'unittest.log').write_text(log, encoding='utf-8', newline='\n')
    (folder/'unittest.public.log').write_text(log.replace(sys.prefix, '[PYTHON_RUNTIME]'), encoding='utf-8', newline='\n')
    report = dict(scope='STAGE2_DELTA_ONLY', inherited_52_tests_rerun=False, tests=result.testsRun,
        errors=len(result.errors), failures=len(result.failures), success=result.wasSuccessful(),
        optimizer_updates=0, raw_data_reads=0, test2025_reads=0, torch=torch.__version__, numpy=numpy.__version__,
        warnings=sorted({str(w.message) for w in caught}), command='python -B tools/core_stage2/run_checks.py'+(' --test '+args.test if args.test else ''))
    (folder/'summary.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(log); print(json.dumps(report, indent=2)); print(folder.relative_to(ROOT))
    raise SystemExit(0 if result.wasSuccessful() else 1)
