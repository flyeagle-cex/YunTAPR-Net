"""Request-driven B2 monitor; reuses existing read-only monitor utilities."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import importlib.util
import json
import shutil
import sqlite3
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('existing_receipt_monitor', ROOT/'tools/core_stage4/monitor/server.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.HERE = HERE


def process_exited(pid):
    """Distinguish a gone Windows PID from an unavailable query; never control it."""
    if base.os.name!='nt':return None
    from ctypes import wintypes as w
    kernel=base.ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE]
    kernel.GetExitCodeProcess.argtypes=[w.HANDLE,base.ctypes.POINTER(w.DWORD)]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return True if base.ctypes.get_last_error()==87 else None
    try:
        code=w.DWORD()
        return code.value!=259 if kernel.GetExitCodeProcess(handle,base.ctypes.byref(code)) else None
    finally:kernel.CloseHandle(handle)


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


class CampaignReader(base.Reader):
    """Approved serial package metadata only; no model imports or controls."""
    def __init__(self, folder, pid):
        self.folder=Path(folder).resolve()
        self.pid,self.token=pid,base.process_token(pid)
        self.cache,self.cached_at=None,0
        self.lock,self.fixed=threading.Lock(),{}
        self.stopped_queries={}
        self.parent=None
        binding=self.document('authorization_binding.json')
        self.approval=binding['approval'];self.budget=self.approval['budget']
        self.recovery_parent=Path(binding['recovery_parent']) if binding.get('recovery_parent') else None
        listed=[(x['model'],x['seed']) for x in self.approval['tasks']]
        self.control_multi=listed==[('B7_ZERO_DOTE',2030),('B7_ZERO_DOTE',2031)]
        self.control=listed==[('B7_ZERO_DOTE',2029)] or self.control_multi
        self.static=listed==[('B5',2029),('B6',2029)]
        self.innovation=listed==[('B7',2029),('B8',2029)]
        self.innovation_multiseed=listed==[('B7',2030),('B8',2030),('B7',2031),('B8',2031)]
        self.innovation_recovery=self.innovation_multiseed and self.recovery_parent is not None
        self.terrain=self.static or self.innovation
        if self.control_multi:
            if (self.budget['total_updates'],self.budget['total_source_bytes'],self.budget['total_source_files'],self.budget['replay_allowance'],self.budget['max_package_seconds'])!=(8640,955143907680,285626,0,43200):raise ValueError('Not the exact two-control budget')
            if binding.get('control')!='ZERO_NUMERIC_RETAIN_REAL_MASKS_TWO_SEEDS' or self.approval.get('approved_by_researcher') is not True:raise ValueError('Not the approved two-control identity')
            self.tasks=[dict(model='B7',seed=s) for s in (2030,2031)];self.extra_io=(0,0,0)
        elif self.control:
            expected=('0c91ff0f36d5cce3f4516d38663482650f61b03a','d7604c03d38585deca056994b119128cd2b6c2c7cbc50451a491e38b5cd4ea75',4320,477571953840,142813,0)
            if (self.approval['code_commit'],self.approval['proposal_sha256'],self.budget['total_updates'],self.budget['total_source_bytes'],self.budget['total_source_files'],self.budget['replay_allowance'])!=expected:raise ValueError('Not the approved single DOTE control')
            self.tasks=[dict(model='B7',seed=2029)];self.extra_io=(0,0,0)
        elif self.innovation_recovery:
            if (self.budget['replay_allowance'],self.budget['cumulative_updates'],self.budget['total_updates'])!=(441,17721,14400):raise ValueError('Not the approved B7 E6 recovery')
            self.tasks=self.approval['tasks']
            self.extra_io=(self.budget['prior_source_files'],self.budget['prior_source_bytes'],self.budget['prior_source_bytes'])
        elif self.recovery_parent:
            if listed!=[('B4',2030),('B3',2031),('B4',2031)] or self.budget['replay_allowance']!=390 or self.budget['cumulative_updates']!=17670:
                raise ValueError('Not the approved bounded recovery')
            self.tasks=[dict(model=k,seed=s) for k,s in [('B3',2030),('B4',2030),('B3',2031),('B4',2031)]]
            self.extra_io=base.query(self.recovery_parent/'B4_s2030/B4_train_reads_02/reads.sqlite',
                'SELECT COUNT(*),COALESCE(SUM(actual_bytes),0),COALESCE(SUM(expected_bytes),0) FROM file_io')[0]
        else:
            self.tasks=self.approval['tasks'];self.extra_io=(0,0,0)
        if (not self.recovery_parent and not self.terrain and not self.control and ((not self.innovation_multiseed and listed!=[('B3',2030),('B4',2030),('B3',2031),('B4',2031)])
                or self.budget['total_updates']!=17280 or self.budget['replay_allowance']!=0)) or binding['controller_pid']!=pid:
            raise ValueError('Not the approved four-model package')
        if self.innovation_multiseed:
            expected=('e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c','3314231ac64531bf523a06d5ff8e3dc4f688d705fc4f4324b57c1548a846aa3e',1591906721352,476044) if self.innovation_recovery else ('56aae5bc4568df5d91354805aa5d4cb6d34b62b3','27f7e3ed2052b846b626619565810f36ced9f7c8b9ba41925376ac37ce952d41',1910287815360,571252)
            if (self.approval['code_commit'],self.approval['proposal_sha256'],self.budget['total_source_bytes'],self.budget['total_source_files'])!=expected:raise ValueError('Not the approved B7/B8 multiseed identity/budget')
        if self.terrain:
            if self.budget['total_updates']!=8640 or self.budget['replay_allowance']!=0:raise ValueError('Not the approved two-model terrain package')
            self.extra_io=(self.budget.get('prior_source_files',0),self.budget.get('prior_source_bytes',0),self.budget.get('prior_source_bytes',0))
        self.started=datetime.fromtimestamp(self.token/10**7-11644473600,timezone.utc) if self.token else datetime.fromtimestamp((self.folder/'authorization_binding.json').stat().st_mtime,timezone.utc)

    def query(self,path,sql):
        try:return base.query(path,sql)
        except sqlite3.OperationalError as exc:
            if 'readonly database' not in str(exc) or process_exited(self.pid) is not True:raise
        # Abrupt exit can leave a hot journal. SQLite recovery may write ONLY
        # inside a fresh private copy; original databases and journals stay intact.
        source=Path(path)
        files=[p for p in (source,Path(str(source)+'-journal'),Path(str(source)+'-wal'),Path(str(source)+'-shm')) if p.exists()]
        stamps=lambda:tuple((str(p),p.stat().st_size,p.stat().st_mtime_ns) for p in files)
        before=stamps();key=(before,sql)
        if key in self.stopped_queries:return self.stopped_queries[key]
        private=(ROOT/'docs/research_readiness/.local').resolve();private.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='monitor_ledger_copy_',dir=private) as temporary:
            copied=Path(temporary).resolve()
            if copied.parent!=private or not copied.name.startswith('monitor_ledger_copy_'):raise ValueError('Private copy path differs')
            for p in files:shutil.copyfile(p,copied/p.name)
            if stamps()!=before:raise ValueError('Ledger changed during isolated snapshot')
            from contextlib import closing
            with closing(sqlite3.connect(copied/source.name,timeout=.08)) as db:
                db.execute('SELECT COUNT(*) FROM sqlite_master').fetchone()
                db.execute('PRAGMA query_only=ON');rows=db.execute(sql).fetchall()
            if stamps()!=before:raise ValueError('Original ledger changed during snapshot')
        self.stopped_queries[key]=rows
        return rows

    def snapshot(self, include_resources=True):
        with self.lock:
            if self.cache and time.monotonic()-self.cached_at<10:return self.cache
            runs=[];io=dict(zip(('files','bytes','reserved_bytes'),self.extra_io),sealed=0)
            replay_returned=0
            for index,task in enumerate(self.tasks):
                kind,seed=task['model'],task['seed'];name=f'{kind}_s{seed}'
                task_root=self.recovery_parent if self.recovery_parent and not self.innovation_recovery and index==0 else self.folder
                folder=task_root/name
                offset=2880 if self.innovation_recovery and index==0 else 480 if self.recovery_parent and not self.innovation_recovery and index==1 else 0
                returned=reserved=offset
                if (folder/'updates.sqlite').exists():
                    rows=self.query(folder/'updates.sqlite','SELECT model,state,COUNT(*) FROM updates GROUP BY model,state')
                    if any(k!=kind or s not in ('RETURNED','INTENT') for k,s,n in rows):raise ValueError('Unexpected task ledger identity')
                    returned+=sum(n for k,s,n in rows if s=='RETURNED');reserved+=sum(n for k,s,n in rows)
                if self.innovation_recovery and index==0:replay_returned=min(441,returned-offset)
                elif self.recovery_parent and not self.innovation_recovery and index==1:replay_returned=min(390,returned-offset)
                epochs=[]
                for epoch in range(1,10):
                    active=False
                    inherited=self.innovation_recovery and index==0 and epoch<=6
                    legacy_inherited=self.recovery_parent and not self.innovation_recovery and index==1 and epoch==1
                    source=self.recovery_parent if inherited or legacy_inherited else task_root
                    for role in ('train','dev'):
                        sub=source/name/f'{kind}_{role}_reads_{epoch:02d}'
                        receipt=self.document(str(sub/'pass_receipt.json'))
                        if receipt:
                            a=receipt['actual_reads'];counts=(a['opened_files'],a['delivered_bytes'],a['reserved_bytes']);io['sealed']+=1
                        elif (sub/'reads.sqlite').exists():
                            counts=self.query(sub/'reads.sqlite','SELECT COUNT(*),COALESCE(SUM(actual_bytes),0),COALESCE(SUM(expected_bytes),0) FROM file_io')[0];active=True
                        else:continue
                        if not inherited:
                            for key,value in zip(('files','bytes','reserved_bytes'),counts):io[key]+=value
                    train=self.document(str(source/name/f'{kind}_train_{epoch:02d}.json'))
                    dev=self.document(str(source/name/f'{kind}_development_{epoch:02d}.json'))
                    last=self.document(str(source/name/f'{kind}_LAST_epoch_{epoch:02d}.receipt.json'))
                    done=min(480,max(0,returned-(epoch-1)*480))
                    phase='SEALED' if last else 'VALIDATED' if dev else 'VALIDATION' if train else 'TRAINING' if done or active else 'PENDING'
                    epochs.append(dict(epoch=epoch,phase=phase,updates=done,training_loss=train.get('weighted_mean') if train else None,
                        metrics=base.metric_summary(dev).get('all') if dev else None,checkpoint_sha256=last.get('checkpoint_sha256') if last else None))
                completion=self.document(str(folder/'completion.json'));failure=self.document(str(folder/'failure.json'))
                sealed=sum(e['phase']=='SEALED' for e in epochs)
                claim=self.folder/f'task_{index if self.recovery_parent and not self.innovation_recovery else index+1}_claim.json'
                state='COMPLETE' if completion and completion.get('status')=='COMPLETE_TRAIN_AND_DEV_EVALUATION' and returned==4320 and sealed==9 else 'FAILED' if failure else 'RUNNING' if folder.exists() or claim.exists() else 'PENDING'
                current=next((e for e in epochs if e['phase']!='SEALED'),epochs[-1])
                if self.terrain or self.innovation_multiseed or self.control:
                    static_db=self.folder/(f'B7_ZERO_DOTE_s{seed}_static_source.sqlite' if self.control_multi else 'B7_ZERO_DOTE_static_source.sqlite' if self.control else f'{name}_static_source.sqlite' if self.innovation_multiseed else f'{kind}_static_source.sqlite')
                    if static_db.exists():
                        counts=self.query(static_db,'SELECT COUNT(*),COALESCE(SUM(actual_bytes),0),COALESCE(SUM(expected_bytes),0) FROM file_io')[0]
                        for key,value in zip(('files','bytes','reserved_bytes'),counts):io[key]+=value
                runs.append(dict(model='B7_ZERO_DOTE' if self.control else kind,seed=seed,name=name,state=state,returned=returned,reserved=reserved,sealed_epochs=sealed,
                    epochs=epochs,current_epoch=current['epoch'],phase=current['phase']))
            failure=self.document('failure.json');completion=self.document('completion.json')
            if failure:
                # A native-runtime abort can exit before Python writes task failure.json.
                for run in runs:
                    if run['state']=='RUNNING':run['state']='FAILED'
            live=self.token is not None and base.process_token(self.pid)==self.token
            stopped=not live and process_exited(self.pid) is True
            if stopped and not failure and not completion:
                for run in runs:
                    if run['state']=='RUNNING':run['state']='STOPPED'
            prior_replay=441 if self.innovation_recovery else 390 if self.recovery_parent else 0
            returned=sum(r['returned'] for r in runs)+prior_replay
            reserved=sum(r['reserved'] for r in runs)+prior_replay
            if self.control:
                limits=dict(updates=self.budget['total_updates'],bytes=self.budget['total_source_bytes'],files=self.budget['total_source_files'],epochs=9*len(self.tasks),seconds=self.budget['max_package_seconds'])
            elif self.innovation_recovery:
                limits=dict(updates=self.budget['cumulative_updates'],bytes=self.budget['cumulative_source_bytes'],files=self.budget['cumulative_source_files'],epochs=36,seconds=self.budget['max_package_seconds'])
            elif self.recovery_parent:
                verification=self.document('interrupted_source_verification/source_verification_receipt.json')
                if verification:
                    for key,value in zip(('files','bytes','reserved_bytes'),(verification['opened_files'],verification['delivered_bytes'],verification['reserved_bytes'])):io[key]+=value
                limits=dict(updates=17670,bytes=self.budget['cumulative_source_bytes'],files=self.budget['cumulative_source_files'],epochs=36,seconds=self.budget['max_wall_seconds'])
            elif self.terrain:limits=dict(updates=8640,bytes=self.budget.get('cumulative_source_bytes',self.budget['total_source_bytes']),files=self.budget.get('cumulative_source_files',self.budget['total_source_files']),epochs=18,seconds=self.budget['max_package_seconds'])
            else:limits=dict(updates=17280,bytes=self.budget['total_source_bytes'],files=4*self.budget['source_files_per_model'],epochs=36,seconds=86400)
            state='FAILED' if failure else 'COMPLETE' if completion and all(r['state']=='COMPLETE' for r in runs) and returned==limits['updates'] else 'RUNNING' if live else 'STOPPED' if stopped else 'UNKNOWN'
            over=reserved>limits['updates'] or any(r['reserved']>4320 for r in runs) or io['reserved_bytes']>limits['bytes'] or io['files']>limits['files']
            if over:state='BUDGET_ALERT'
            now=datetime.now(timezone.utc)
            terminal=self.folder/'failure.json' if failure else self.folder/'completion.json' if completion else None
            stop=datetime.fromtimestamp(terminal.stat().st_mtime,timezone.utc) if terminal else now
            elapsed=max(0,(stop-self.started).total_seconds())
            result=dict(state=state,snapshot_utc=now.isoformat(),read_only=True,process_observed=live,runs=runs,
                returned=returned,reserved=reserved,uncertain=reserved-returned,io=io,
                sealed_epochs=sum(r['sealed_epochs'] for r in runs),completed_models=sum(r['state']=='COMPLETE' for r in runs),
                limits=limits,dote_control=self.control,dote_control_multiseed=self.control_multi,recovery=bool(self.recovery_parent),static=self.static,innovation=self.innovation,innovation_multiseed=self.innovation_multiseed,innovation_recovery=self.innovation_recovery,replay_returned=replay_returned,
                elapsed_seconds=elapsed,remaining_limit_seconds=max(0,limits['seconds']-elapsed),started_at=self.started.isoformat(),
                source_commit=self.approval['code_commit'],resources=base.resources(self.folder) if include_resources else {},
                message='整包已停止，后续任务不会自动启动；请查看本地失败收据。' if failure else '控制器进程已退出，未留下完成或失败收据；页面按现有账本显示，训练未自动恢复，退出原因尚未核实。' if stopped and not completion else None)
            if self.static and completion:result['paired_summary']=self.document('static_paired_summary.json')
            if self.innovation and state=='COMPLETE':result['paired_summary']=self.document('innovation_paired_summary.json')
            if self.innovation_multiseed and state=='COMPLETE':result['three_seed_summary']=self.document('three_seed_innovation_summary.json')
            if self.control_multi and state=='COMPLETE':result['three_seed_summary']=self.document('three_seed_dote_control_summary.json')
            if self.innovation_recovery:result.update(segment_returned=returned-self.budget['prior_updates'],segment_limit=self.budget['total_updates'],prior_attempts=self.budget['prior_updates'])
            self.cache,self.cached_at=result,time.monotonic()
            return result


class B8RecoveryReader(base.Reader):
    """Only new recovery metadata plus inherited seals; no training controls."""
    def __init__(self,folder,pid,parent):
        self.folder,self.parent=Path(folder).resolve(),Path(parent).resolve()
        self.pid,self.token=pid,base.process_token(pid)
        self.cache,self.cached_at=None,0
        self.lock,self.fixed=threading.Lock(),{}
        binding=self.document('authorization_binding.json');self.approval=binding['approval'];self.budget=self.approval['budget']
        if (binding['controller_pid']!=pid or self.approval['tasks']!=[dict(model='B8',seed=2029)]
                or self.budget['new_updates']!=1440 or self.budget['replayed_updates']!=62):raise ValueError('Not the approved B8 recovery')
        self.stop=json.loads((ROOT/'docs/research_readiness/20261025/evidence/b7_b8_terminal_20261028.json').read_text(encoding='utf-8'))
        if self.stop['tasks'][1]['last_saved_sha256']!=self.approval['approved_checkpoint_sha256']:raise ValueError('E6 identity differs')
        self.started=datetime.fromtimestamp((self.folder/'authorization_binding.json').stat().st_mtime,timezone.utc)

    def snapshot(self,include_resources=True):
        with self.lock:
            if self.cache and time.monotonic()-self.cached_at<10:return self.cache
            cost=self.stop['budget_closure'];caps=self.budget
            io=dict(files=cost['actual_source_files']+caps['diagnostic_files_already_spent'],bytes=cost['actual_source_bytes']+caps['diagnostic_bytes_already_spent'],reserved_bytes=cost['reserved_source_bytes']+caps['diagnostic_bytes_already_spent'],sealed=0)
            folder=self.folder/'B8_s2029';n=reserved=0
            if (folder/'updates.sqlite').exists():
                rows=base.query(folder/'updates.sqlite','SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')
                if any(k!='B8' or state not in ('RETURNED','INTENT') or lo<2881 or hi>4320 for k,state,count,lo,hi in rows):raise ValueError('Unexpected B8 segment ledger')
                n=sum(count for k,state,count,lo,hi in rows if state=='RETURNED');reserved=sum(count for k,state,count,lo,hi in rows)
            runs=[]
            for kind,effective in (('B7',4320),('B8',2880+n)):
                epochs=[]
                for e in range(1,10):
                    inherited=kind=='B7' or e<=6
                    source=(self.parent if inherited else self.folder)/f'{kind}_s2029';active=False
                    if not inherited:
                        for role in ('train','dev'):
                            sub=source/f'{kind}_{role}_reads_{e:02d}';r=self.document(str(sub/'pass_receipt.json'))
                            if r:
                                a=r['actual_reads'];counts=(a['opened_files'],a['delivered_bytes'],a['reserved_bytes']);io['sealed']+=1
                            elif (sub/'reads.sqlite').exists():
                                counts=base.query(sub/'reads.sqlite','SELECT COUNT(*),COALESCE(SUM(actual_bytes),0),COALESCE(SUM(expected_bytes),0) FROM file_io')[0];active=True
                            else:continue
                            for key,value in zip(('files','bytes','reserved_bytes'),counts):io[key]+=value
                    train=self.document(str(source/f'{kind}_train_{e:02d}.json'));dev=self.document(str(source/f'{kind}_development_{e:02d}.json'));last=self.document(str(source/f'{kind}_LAST_epoch_{e:02d}.receipt.json'))
                    done=min(480,max(0,effective-(e-1)*480));phase='SEALED' if last else 'VALIDATED' if dev else 'VALIDATION' if train else 'TRAINING' if done or active else 'PENDING'
                    epochs.append(dict(epoch=e,phase=phase,updates=done,inherited=inherited,training_loss=train.get('weighted_mean') if train else None,metrics=base.metric_summary(dev).get('all') if dev else None,checkpoint_sha256=last.get('checkpoint_sha256') if last else None))
                complete=self.document(str((self.parent if kind=='B7' else self.folder)/f'{kind}_s2029/completion.json'))
                sealed=sum(e['phase']=='SEALED' for e in epochs)
                run_state='COMPLETE' if complete and sealed==9 and effective==4320 else 'FAILED' if self.document(str(source/'failure.json')) else 'RUNNING'
                current=next((e for e in epochs if e['phase']!='SEALED'),epochs[-1])
                runs.append(dict(model=kind,seed=2029,name=f'{kind}_s2029',state=run_state,returned=effective,reserved=effective+reserved-n if kind=='B8' else 4320,sealed_epochs=sealed,epochs=epochs,current_epoch=current['epoch'],phase=current['phase']))
            static=self.folder/'B8_static_source.sqlite'
            if static.exists():
                counts=base.query(static,'SELECT COUNT(*),COALESCE(SUM(actual_bytes),0),COALESCE(SUM(expected_bytes),0) FROM file_io')[0]
                for key,value in zip(('files','bytes','reserved_bytes'),counts):io[key]+=value
            failure=self.document('failure.json');completion=self.document('completion.json');live=self.token is not None and base.process_token(self.pid)==self.token
            if failure:runs[1]['state']='FAILED'
            state='FAILED' if failure else 'COMPLETE' if completion and n==1440 and all(x['state']=='COMPLETE' for x in runs) else 'RUNNING' if live else 'UNKNOWN'
            if reserved>1440 or io['reserved_bytes']>caps['cumulative_source_bytes'] or io['files']>caps['cumulative_source_files']:state='BUDGET_ALERT'
            now=datetime.now(timezone.utc);terminal=self.folder/('failure.json' if failure else 'completion.json')
            stopped=datetime.fromtimestamp(terminal.stat().st_mtime,timezone.utc) if (failure or completion) else now;elapsed=max(0,(stopped-self.started).total_seconds())
            result=dict(state=state,snapshot_utc=now.isoformat(),read_only=True,process_observed=live,runs=runs,returned=7262+n,reserved=7262+reserved,uncertain=reserved-n,
                        io=io,sealed_epochs=sum(x['sealed_epochs'] for x in runs),completed_models=sum(x['state']=='COMPLETE' for x in runs),
                        limits=dict(updates=8702,bytes=caps['cumulative_source_bytes'],files=caps['cumulative_source_files'],epochs=18,seconds=caps['max_wall_seconds']),
                        recovery=True,b8_recovery=True,innovation=True,static=False,replay_returned=min(62,n),segment_returned=n,segment_limit=1440,
                        elapsed_seconds=elapsed,remaining_limit_seconds=max(0,caps['max_wall_seconds']-elapsed),started_at=self.started.isoformat(),source_commit=self.approval['code_commit'],
                        resources=base.resources(self.folder) if include_resources else {},message='B8恢复已停止；保留新旧账本，不自动重试。' if failure else None)
            if state=='COMPLETE':result['paired_summary']=self.document('innovation_paired_summary.json')
            self.cache,self.cached_at=result,time.monotonic();return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--experiment',type=Path,required=True)
    p.add_argument('--training-pid',type=int,required=True)
    p.add_argument('--port',type=int,default=0)
    p.add_argument('--service-dir',type=Path,required=True)
    p.add_argument('--campaign',action='store_true')
    p.add_argument('--b8-recovery',action='store_true')
    p.add_argument('--parent-experiment',type=Path)
    a=p.parse_args()
    if a.b8_recovery:
        if a.parent_experiment is None:p.error('--parent-experiment required for B8 recovery')
        reader=B8RecoveryReader(a.experiment,a.training_pid,a.parent_experiment)
    else:reader=(CampaignReader if a.campaign else B2Reader)(a.experiment,a.training_pid)
    a.service_dir.mkdir(parents=True,exist_ok=True)
    with ThreadingHTTPServer(('127.0.0.1',a.port),base.handler_for(reader)) as server:
        service=dict(url=f'http://127.0.0.1:{server.server_port}/',pid=base.os.getpid(),read_only=True,training_pid=a.training_pid)
        (a.service_dir/'service.json').write_text(json.dumps(service,indent=2),encoding='utf-8')
        shortcut='B7_B8多seed训练进度.url' if getattr(reader,'innovation_multiseed',False) else 'B3_B4多seed训练进度.url' if a.campaign else 'B2训练进度.url'
        (a.service_dir/shortcut).write_text('[InternetShortcut]\nURL='+service['url']+'\n',encoding='utf-8')
        print(service['url'],flush=True)
        server.serve_forever(poll_interval=1)


if __name__=='__main__':main()
