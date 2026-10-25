"""Request-driven B2 monitor; reuses existing read-only monitor utilities."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import importlib.util
import json
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('existing_receipt_monitor', ROOT/'tools/core_stage4/monitor/server.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.HERE = HERE


class B2Reader(base.Reader):
    def __init__(self, folder, pid):
        self.folder = Path(folder).resolve()
        self.pid, self.token = pid, base.process_token(pid)
        self.cache, self.cached_at = None, 0
        self.lock, self.fixed = threading.Lock(), {}
        self.parent = None
        self.identity = json.loads(base.query(self.folder/'updates.sqlite', 'SELECT value FROM identity')[0][0])
        approval = self.identity['approval']
        if approval['model'] != 'B2' or approval['seed'] != 2029 or approval['optimizer_update_cap'] != 4320:
            raise ValueError('Not the approved B2 run')
        self.approval = approval
        binding = self.document('authorization_binding.json')
        self.started = datetime.fromisoformat(binding['approval']['approved_at'])

    def snapshot(self, include_resources=True):
        with self.lock:
            if self.cache and time.monotonic()-self.cached_at < 10:
                return self.cache
            rows = base.query(self.folder/'updates.sqlite', 'SELECT state,COUNT(*),MAX(u) FROM updates GROUP BY state')
            returned = sum(n for state,n,_ in rows if state == 'RETURNED')
            reserved = sum(n for _,n,_ in rows)
            io = dict(files=0, bytes=0, reserved_bytes=0, sealed=0, active=[], states={})
            epochs = []
            for epoch in range(1,10):
                active = []
                for role in ('Train','Development'):
                    folder = self.folder/f'B2_{role}_reads_{epoch:02d}'
                    receipt = self.document(f'{folder.name}/pass_receipt.json')
                    if receipt:
                        a = receipt['actual_reads']
                        count, delivered, expected = a['opened_files'], a['delivered_bytes'], a['reserved_bytes']
                        states = a['states']
                        io['sealed'] += 1
                    elif (folder/'reads.sqlite').exists():
                        count,delivered,expected = base.query(folder/'reads.sqlite',
                            'SELECT COUNT(*),COALESCE(SUM(actual_bytes),0),COALESCE(SUM(expected_bytes),0) FROM file_io')[0]
                        states = dict(base.query(folder/'reads.sqlite','SELECT state,COUNT(*) FROM file_io GROUP BY state'))
                        active.append(role)
                        io['active'].append(dict(epoch=epoch,role=role))
                    else:
                        continue
                    io['files'] += count
                    io['bytes'] += delivered
                    io['reserved_bytes'] += expected
                    for key,value in states.items():
                        io['states'][key] = io['states'].get(key,0)+value
                train = self.document(f'B2_train_{epoch:02d}.json')
                dev = self.document(f'B2_development_{epoch:02d}.json')
                last = self.document(f'B2_LAST_epoch_{epoch:02d}.receipt.json')
                done = min(480,max(0,returned-(epoch-1)*480))
                phase = 'SEALED' if last else 'VALIDATED' if dev else 'VALIDATION' if train else 'TRAINING' if done or active else 'PENDING'
                epochs.append(dict(epoch=epoch,phase=phase,updates=done,training_loss=train.get('weighted_mean') if train else None,
                    metrics=base.metric_summary(dev).get('all') if dev else None,checkpoint_sha256=last.get('checkpoint_sha256') if last else None))
            failure = self.document('failure.json')
            complete = self.document('completion.json')
            live = self.token is not None and base.process_token(self.pid) == self.token
            limits = dict(updates=4320,bytes=self.approval['source_read_byte_cap'],files=self.approval['source_read_file_cap'],epochs=9,seconds=21600)
            over = reserved > limits['updates'] or io['reserved_bytes'] > limits['bytes'] or io['files'] > limits['files']
            state = 'FAILED' if failure else 'COMPLETE' if complete and returned==4320 and sum(bool(e['checkpoint_sha256']) for e in epochs)==9 else 'RUNNING' if live else 'UNKNOWN'
            if over:
                state = 'BUDGET_ALERT'
            current = next((e for e in epochs if e['phase'] != 'SEALED'), epochs[-1])
            now = datetime.now(timezone.utc)
            terminal = self.folder/'failure.json' if failure else self.folder/'completion.json' if complete else None
            stopped_at = datetime.fromtimestamp(terminal.stat().st_mtime,timezone.utc) if terminal else now
            elapsed = max(0,(stopped_at-self.started).total_seconds())
            result = dict(state=state,snapshot_utc=now.isoformat(),refresh_seconds=15,read_only=True,process_observed=live,
                returned=returned,reserved=reserved,uncertain=reserved-returned,io=io,epochs=epochs,
                sealed_epochs=sum(bool(e['checkpoint_sha256']) for e in epochs),current_epoch=current['epoch'],phase=current['phase'],
                limits=limits,elapsed_seconds=elapsed,remaining_limit_seconds=max(0,21600-elapsed),
                started_at=self.started.isoformat(),source_commit=self.approval['code_commit'],
                population_sha256=self.identity['data']['population_sha256'],data_identity=self.identity['data'],
                resources=base.resources(self.folder) if include_resources else {},failure=bool(failure),completion=bool(complete),
                message='运行已停止；具体原因见本地failure.json' if failure else None)
            self.cache,self.cached_at = result,time.monotonic()
            return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--experiment',type=Path,required=True)
    p.add_argument('--training-pid',type=int,required=True)
    p.add_argument('--port',type=int,default=0)
    p.add_argument('--service-dir',type=Path,required=True)
    a=p.parse_args()
    reader=B2Reader(a.experiment,a.training_pid)
    a.service_dir.mkdir(parents=True,exist_ok=True)
    with ThreadingHTTPServer(('127.0.0.1',a.port),base.handler_for(reader)) as server:
        service=dict(url=f'http://127.0.0.1:{server.server_port}/',pid=base.os.getpid(),read_only=True,training_pid=a.training_pid)
        (a.service_dir/'service.json').write_text(json.dumps(service,indent=2),encoding='utf-8')
        (a.service_dir/'B2训练进度.url').write_text('[InternetShortcut]\nURL='+service['url']+'\n',encoding='utf-8')
        print(service['url'],flush=True)
        server.serve_forever(poll_interval=1)


if __name__=='__main__':main()
