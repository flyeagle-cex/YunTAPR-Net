"""Synthetic-only checks, no real weather data, checkpoint load or optimizer."""
from pathlib import Path
import datetime
import io
import json
import os
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests/research_readiness'), str(ROOT/'tests/core_innovation'), str(ROOT/'tests/core_stage3')]
import torch
torch.set_num_threads(1)


def main():
    names = sys.argv[1:] or ['test_candidates', 'test_terrain.TerrainTests', 'test_grid']
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
    out = ROOT/'docs/research_readiness/20261025/tests'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    out.mkdir(parents=True)
    log = stream.getvalue().replace(str(ROOT), '[REPO]').replace(sys.prefix, '[PYTHON]')
    (out/'public.log').write_text(log, encoding='utf-8')
    summary = dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
                   failures=len(result.failures), errors=len(result.errors), formal_optimizer_updates=0,
                   real_weather_reads=0, checkpoint_loads=0, data_scope='SYNTHETIC_FIXTURES_ONLY')
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(log)
    print(json.dumps(summary))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
