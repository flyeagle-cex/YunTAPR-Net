"""One bounded attempt. Supervisor stops a blocked read before six hours."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

HERE=Path(__file__).absolute().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_full_payload_integrity.audit import Audit,LIMIT_SECONDS
parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');args=parser.parse_args()
private=HERE/'.local'/'attempt_001'
if args.worker:
    Audit(private).run()
else:
    private.mkdir(parents=True,exist_ok=False) # Never overwrite/retry an attempt.
    started=datetime.now(timezone.utc).isoformat();start=time.monotonic()
    env=dict(os.environ,PYTHONUTF8='1')
    proc=subprocess.Popen([sys.executable,str(Path(__file__).absolute()),'--worker'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    def pump():
        with (private/'worker_private.log').open('wb') as log,(HERE/'execution_progress.log').open('xb') as public:
            for raw in iter(proc.stdout.readline,b''):
                log.write(raw);log.flush()
                try:
                    record=json.loads(raw);safe=(json.dumps(record)+'\n').encode();public.write(safe);public.flush();print(safe.decode(),end='',flush=True)
                except (ValueError,UnicodeDecodeError):pass # Tracebacks remain private.
    thread=threading.Thread(target=pump,daemon=True);thread.start();hard_stop=False
    while proc.poll() is None:
        if time.monotonic()-start>=LIMIT_SECONDS-5:
            hard_stop=True;proc.kill();break
        time.sleep(1)
    proc.wait(timeout=5);thread.join(timeout=5)
    record=dict(supervisor_started_at_utc=started,supervisor_finished_at_utc=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=time.monotonic()-start,worker_exit_code=proc.returncode,hard_time_stop=hard_stop,watchdog_seconds=LIMIT_SECONDS-5)
    (private/'supervisor.json').write_bytes((json.dumps(record,indent=2)+'\n').encode())
    from build_delivery import build
    status=build(private,record)
    print(json.dumps(status),flush=True)
    sys.exit(0 if status['overall_status']=='FULL_PAYLOAD_SHA_PASS' else 2)
