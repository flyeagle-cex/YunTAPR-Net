"""Fixed read-only GUI monitor; no train/start/recovery command is imported."""
from pathlib import Path
import os,runpy,sys
if len(sys.argv)!=1:raise PermissionError('FIXED_READ_ONLY_MONITOR_ONLY')
root=Path(__file__).absolute().parents[2]
sys.path.insert(0,str(root/'src'));os.environ.update(PYTHONPATH=str(root/'src'),PYTHONUTF8='1')
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v4.console import isolate
isolate()
folder=Path(__file__).parent/'.local';folder.mkdir(exist_ok=True)
from datetime import datetime,timezone
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
sys.stdout=(folder/(stamp+'.stdout.txt')).open('x',encoding='utf-8',buffering=1)
sys.stderr=(folder/(stamp+'.stderr.txt')).open('x',encoding='utf-8',buffering=1)
sys.argv=[str(Path(__file__).with_name('server.py')),'--port','53085']
runpy.run_path(sys.argv[0],run_name='__main__')
