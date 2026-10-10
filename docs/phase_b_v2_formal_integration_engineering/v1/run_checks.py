"""Logged focused checks; GPU is opt-in and retains the nonrefundable quota."""
import argparse
import datetime
import json
import os
import re
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--gpu',action='store_true');args=parser.parse_args()
env=dict(os.environ,PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT/'docs/phase_b_v2_ablation_implementation/v1/.local/test_dependencies'),PYTHONHASHSEED='2026',CUBLAS_WORKSPACE_CONFIG=':4096:8',PYTHONUTF8='1')
mode='gpu' if args.gpu else 'cpu';stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(HERE/'tests'),'-p',f'test_{mode}.py','-v','-f'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
# Public logs omit machine-specific workspace/user paths.
output=result.stdout.decode('utf-8',errors='replace').replace('\r','').replace(str(ROOT),'<REPOSITORY>').replace(str(ROOT).replace('\\','/'),'<REPOSITORY>').replace(str(Path(sys.executable).parent.parent),'<PYTHON_ENV>')
output='\n'.join(line.rstrip() for line in re.sub(r'\x1b\[[0-9;]*m','',output).splitlines())+'\n'
(HERE/'tests'/f'{mode}_{stamp}.log').write_bytes(output.encode())
print(output,end='');sys.exit(result.returncode)
